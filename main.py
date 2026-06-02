from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
import asyncio
import json
import datetime
import os

app = FastAPI()
connected_clients = []

# تفعيل مكتبة التداول بحذر لتفادي أخطاء التشغيل
try:
    from tradingview_ta import TA_Handler, Interval
    handler = TA_Handler(
        screen="forex",
        exchange="FX_IDC",
        symbol="EURUSD",
        interval=Interval.INTERVAL_1_MINUTE
    )
except Exception as e:
    print(f"CRITICAL ERROR IMPORTING TRADINGVIEW: {e}")
    handler = None

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
    # التأكد من وجود الملف لمنع توقف السيرفر
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read(), status_code=200)
    return HTMLResponse(content="<h1>ملف index.html غير موجود في المستودع الرئيسي!</h1>", status_code=404)

async def check_market_loop():
    while True:
        try:
            if handler:
                analysis = handler.get_analysis()
                rsi = analysis.indicators.get("RSI", 50)
                close = analysis.indicators.get("close", 0)
                upper_band = analysis.indicators.get("BB.upper", 0)
                lower_band = analysis.indicators.get("BB.lower", 0)
                
                action = "HOLD"
                if close <= lower_band or rsi < 30:
                    action = "CALL"
                elif close >= upper_band or rsi > 70:
                    action = "PUT"
            else:
                # وضع احتياطي في حال فشل الاتصال بـ TradingView
                action = "HOLD"
                close, rsi = 0.0, 50.0

            now = datetime.datetime.now().strftime("%H:%M:%S")
            signal_data = {
                "asset": "EURUSD (Live)",
                "action": action,
                "price": round(close, 5),
                "rsi": round(rsi, 2),
                "time": now
            }
            
            for client in connected_clients:
                await client.send_text(json.dumps(signal_data))
                
        except Exception as e:
            print(f"Error fetching data loop: {e}")
            
        await asyncio.sleep(15)

@app.on_event("startup")
async def startup_event(): 
    asyncio.create_task(check_market_loop())
