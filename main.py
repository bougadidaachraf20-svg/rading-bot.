from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
import asyncio
import json
import datetime

app = FastAPI()
connected_clients = []

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
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), status_code=200)

def analyze_market_v2(candles):
    if len(candles) < 20: return "HOLD"
    closes = [c['close'] for c in candles]
    opens = [c['open'] for c in candles]
    
    sma_20 = sum(closes[-20:]) / 20
    variance = sum((x - sma_20) ** 2 for x in closes[-20:]) / 20
    std_dev = variance ** 0.5
    
    upper_band = sma_20 + (2 * std_dev)
    lower_band = sma_20 - (2 * std_dev)
    
    gains, losses = 0, 0
    for i in range(-14, 0):
        diff = closes[i] - closes[i-1]
        if diff > 0: gains += diff
        else: losses += abs(diff)
        
    rsi = 50 if losses == 0 else 100 - (100 / (1 + (gains / losses)))
    
    if closes[-1] <= lower_band and rsi < 35 and (closes[-1] > opens[-1]): return "CALL"
    elif closes[-1] >= upper_band and rsi > 65 and (closes[-1] < opens[-1]): return "PUT"
    return "HOLD"

async def check_market_loop():
    while True:
        try:
            now = datetime.datetime.now().strftime("%H:%M:%S")
            signal_data = {"asset": "EURUSD_OTC", "action": "CALL", "price": 1.0850, "rsi": 30.0, "time": now}
            for client in connected_clients:
                await client.send_text(json.dumps(signal_data))
        except: pass
        await asyncio.sleep(15)

@app.on_event("startup")
async def startup_event(): asyncio.create_task(check_market_loop())
