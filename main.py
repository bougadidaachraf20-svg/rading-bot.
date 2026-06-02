from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
import asyncio
import json
import datetime
from tradingview_ta import TA_Handler, Interval

app = FastAPI()
connected_clients = []

# إعداد الاتصال بـ TradingView لسحب بيانات EURUSD الحية
handler = TA_Handler(
    screen="forex",
    exchange="FX_IDC",
    symbol="EURUSD",
    interval=Interval.INTERVAL_1_MINUTE  # التحليل على فريم الدقيقة
)

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

async def check_market_loop():
    while True:
        try:
            # جلب التحليل الفني والمؤشرات من قلب السوق مباشرة
            analysis = handler.get_analysis()
            rsi = analysis.indicators.get("RSI", 50)
            close = analysis.indicators.get("close", 0)
            upper_band = analysis.indicators.get("BB.upper", 0)
            lower_band = analysis.indicators.get("BB.lower", 0)
            
            # خوارزمية اتخاذ القرار (الاستراتيجية الرقمية)
            action = "HOLD"
            if close <= lower_band or rsi < 30:
                action = "CALL"  # إشارة صعود (شراء)
            elif close >= upper_band or rsi > 70:
                action = "PUT"   # إشارة هبوط (بيع)

            now = datetime.datetime.now().strftime("%H:%M:%S")
            signal_data = {
                "asset": "EURUSD (Live)",
                "action": action,
                "price": round(close, 5),
                "rsi": round(rsi, 2),
                "time": now
            }
            
            # بث الإشارة الحية إلى شاشة هاتفكِ فوراً
            for client in connected_clients:
                await client.send_text(json.dumps(signal_data))
                
        except Exception as e:
            print(f"Error: {e}")
            
        # فحص السوق يتكرر تلقائياً كل 15 ثانية لملاحقة الشموع
        await asyncio.sleep(15)

@app.on_event("startup")
async def startup_event(): 
    asyncio.create_task(check_market_loop())
