from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, HTMLResponse, FileResponse
from pydantic import BaseModel
import asyncio
import os

from routers import iot, access_control, wifi_bt, reports
from database import init_db, get_db, Setting
from sqlalchemy.orm import Session
from fastapi import Depends
from models import SettingUpdate

# تهيئة قاعدة البيانات عند بدء التطبيق
init_db()

# ===================== AUTH =====================
VALID_USERNAME = "admin"
VALID_PASSWORD = "pentex2024"

class LoginRequest(BaseModel):
    username: str
    password: str
# =================================================

app = FastAPI(title="Pentex One API", description="Backend API for Pentex One security testing device.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(iot.router)
app.include_router(access_control.router)
app.include_router(wifi_bt.router)
app.include_router(reports.router)

@app.get("/settings")
def get_settings(db: Session = Depends(get_db)):
    settings = db.query(Setting).all()
    return {s.key: s.value for s in settings}

@app.put("/settings")
def update_settings(updates: SettingUpdate, db: Session = Depends(get_db)):
    if updates.simulation_mode is not None:
        setting = db.query(Setting).filter(Setting.key == "simulation_mode").first()
        if setting: setting.value = updates.simulation_mode
    if updates.nmap_timeout is not None:
        setting = db.query(Setting).filter(Setting.key == "nmap_timeout").first()
        if setting: setting.value = updates.nmap_timeout
    db.commit()
    return {"status": "success"}

# التأكد من وجود مجلد static قبل توجيهه (لتجنب الأخطاء إذا لم يُنشأ بعد)
os.makedirs("static", exist_ok=True)
app.mount("/dashboard", StaticFiles(directory="static", html=True), name="static")

@app.post("/auth/login")
def login(req: LoginRequest):
    if req.username == VALID_USERNAME and req.password == VALID_PASSWORD:
        return {"status": "ok"}
    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.get("/login")
def login_page():
    return FileResponse("static/login.html")

@app.get("/")
def read_root():
    return RedirectResponse(url="/login")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            await websocket.send_json({"event": "heartbeat", "status": "active"})
            await asyncio.sleep(5)
    except Exception as e:
        print(f"WebSocket Error: {e}")
