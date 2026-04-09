from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, HTMLResponse, FileResponse
from pydantic import BaseModel
import asyncio
import os
import logging

# Load .env file if it exists
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    with open(dotenv_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip())

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from routers import iot, access_control, wifi_bt, reports, ai
from database import init_db, get_db, Setting
from sqlalchemy.orm import Session
from fastapi import Depends
from models import SettingUpdate

# تهيئة قاعدة البيانات عند بدء التطبيق
init_db()

# ===================== AUTH =====================
# SECURITY: In production, use environment variables or a secure vault
VALID_USERNAME = os.getenv("PENTEX_USERNAME", "admin")
VALID_PASSWORD = os.getenv("PENTEX_PASSWORD", "pentex2024")  # Change this!

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
app.include_router(ai.router)
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


from websocket_manager import manager

# Export manager to other routers
app.manager = manager

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # We keep the heartbeat for connection stability
            await websocket.send_json({"event": "heartbeat", "status": "active"})
            await asyncio.sleep(10)
    except Exception as e:
        logger.debug(f"WebSocket connection closed: {e}")
    finally:
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    # Disable reload in production to prevent disconnects
    reload_mode = os.getenv("PENTEX_RELOAD", "false").lower() == "true"
    
    # RPi 5 optimization: use 1 worker to save RAM on 4GB model
    workers = int(os.getenv("PENTEX_WORKERS", "1"))
    
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=reload_mode,
        workers=workers if not reload_mode else 1,  # reload and workers are incompatible
        log_level="info",
        access_log=False,  # Reduce log noise
        timeout_keep_alive=30  # Keep WebSocket connections alive
    )
