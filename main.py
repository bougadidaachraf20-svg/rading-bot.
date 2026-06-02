from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
import asyncio
import json
import datetime
import os
import urllib.request

app = FastAPI()
connected_clients = []

# دالة لسحب أسعار الشموع الحية من Binance مباشرة وبأمان
def get_live_candles():
    try:
        # سحب بيانات زوج EURUSDT (فريم الدقيقة)
        url = "https://api.binance.com/api/v3/klines?symbol=EURUSDT&interval=1m&limit=30"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            candles = []
            for c in data:
                candles.append({
                    "open": float(c[1]),
                    "high": float(c[2]),
                    "low": float(c[3]),
                    "close": float(c[4])
                })
            return candles
    except Exception as e:
        print(f"Binance Fetch Error: {e}")
        return []

# حساب المؤشرات الفنية بدقة (RSI + Bollinger Bands) وتحديد الصفقات
def calculate_indicators(candles):
    if len(candles) < 20:
        return "HOLD", 0.0, 50.0
        
    closes = [c['close'] for c in candles]
    opens = [c['open'] for c in candles]
    current_price = closes[-1]
    
    # 1. حساب البولينجر باندز (SMA 20 + الانحراف المعياري)
    sma_20 = sum(closes[-20:]) / 20
    variance = sum((x - sma_20) ** 2 for x in closes[-20:]) / 20
    std_dev = variance ** 0.5
    upper_band = sma_20 + (1.9 * std_dev) # تم تحسين الحواف لاقتناص صفقات أكثر
    lower_band = sma_20 - (1.9 * std_dev)
    
    # 2. حساب مؤشر القوة النسبية RSI (14 دقيقة)
    gains, losses = 0, 0
    for i in range(-14, 0):
        diff = closes[i] - closes[i-1]
        if diff > 0: gains += diff
        else: losses += abs(diff)
    rsi = 50 if losses == 0 else 100 - (100 / (1 + (gains / losses)))
    
    # 3. اتخاذ قرار الصفقة
    action = "HOLD"
    if current_price <= lower_band or rsi < 35:
        action = "CALL"  # صفقة صعود (شراء)
    elif current_price >= upper_band or rsi > 65:
        action = "PUT"   # صفقة هبوط (بيع)
        
    return action, current_price, rsi

@app.websocket("/ws/signals")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        while True: await websocket.receive_text()
    except:
        connected_clients.remove(websocket)

@app.get("/")
async def get_index():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read(), status_code=200)
    return HTMLResponse(content="<h1>index.html not found</h1>", status_code=404)

async def check_market_loop():
    while True:
        try:
            candles = get_live_candles()
            action, price, rsi = calculate_indicators(candles)
            
            now = datetime.datetime.now().strftime("%H:%M:%S")
            signal_data = {
                "asset": "EURUSD (Live)",
                "action": action,
                "price": round(price, 5) if price > 0 else 1.0850,
                "rsi": round(rsi, 2),
                "time": now
            }
            
            for client in connected_clients:
                await client.send_text(json.dumps(signal_data))
        except Exception as e:
            print(f"Loop Error: {e}")
            
        await asyncio.sleep(15)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(check_market_loop())
