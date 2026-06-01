from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
import asyncio
import pandas as pd
import pandas_ta as ta
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

def analyze_market(candles_list):
    df = pd.DataFrame(candles_list, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    df.ta.rsi(length=14, append=True)
    df.ta.bbands(length=20, std=2, append=True)
    df.ta.ema(length=200, append=True)
    
    close = df['close'].iloc[-1]
    rsi = df['RSI_14'].iloc[-1]
    ema_200 = df['EMA_200'].iloc[-1]
    lower_band = df['BBL_20_2.0'].iloc[-1]
    upper_band = df['BBU_20_2.0'].iloc[-1]
    
    is_bullish = (df['close'].iloc[-1] > df['open'].iloc[-1]) and (df['open'].iloc[-1] < df['close'].iloc[-2]) and (df['close'].iloc[-1] > df['open'].iloc[-2])
    is_bearish = (df['close'].iloc[-1] < df['open'].iloc[-1]) and (df['open'].iloc[-1] > df['close'].iloc[-2]) and (df['close'].iloc[-1] < df['open'].iloc[-2])

    if close > ema_200 and close <= lower_band and rsi < 35 and is_bullish: return "CALL"
    elif close < ema_200 and close >= upper_band and rsi > 65 and is_bearish: return "PUT"
    return "HOLD"

async def check_market_loop():
    while True:
        try:
            now = datetime.datetime.now().strftime("%H:%M:%S")
            signal_data = {"asset": "EURUSD_otc", "action": "CALL", "price": 1.0850, "rsi": 30.0, "time": now}
            for client in connected_clients:
                await client.send_text(json.dumps(signal_data))
        except: pass
        await asyncio.sleep(15)

@app.on_event("startup")
async def startup_event(): asyncio.create_task(check_market_loop())
