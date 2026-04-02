from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime
import serial
import serial.tools.list_ports
import random
import time

from database import get_db, RFIDCard, Setting
from models import RFIDCardOut
from security_engine import calculate_risk

router = APIRouter(prefix="/rfid", tags=["Access Control"])

def _simulate_rfid_read(db: Session):
    # Mock data generation
    mock_uids = ["04:A1:B2:C3:D4:E5:F6", "DE:AD:BE:EF:00:11", "AA:BB:CC:DD:EE:FF"]
    uid = random.choice(mock_uids)
    card_type = random.choice(["Mifare Classic 1K", "NFC NTAG213", "EM4100"])
    
    risk_flags = {}
    if "Mifare" in card_type:
        risk_flags["RFID_MIFARE_DEFAULT_KEY"] = True
    if "EM4100" in card_type:
        risk_flags["RFID_EASILY_CLONABLE"] = True
        
    return uid, card_type, risk_flags

def _real_rfid_read():
    """Attempt to read from a real serial RFID reader"""
    ports = serial.tools.list_ports.comports()
    if not ports:
        return None
    
    # Very basic serial read, assuming a simple reader on the first port at 9600
    try:
        with serial.Serial(ports[0].device, 9600, timeout=2) as ser:
            ser.write(b'\x02\x01\x26\x03') # example command
            time.sleep(0.5)
            if ser.in_waiting:
                data = ser.read(ser.in_waiting).hex()
                return data[:14].upper(), "Unknown Reality Card", {"RFID_EASILY_CLONABLE": True}
    except Exception:
        pass
    return None

@router.post("/scan")
async def scan_rfid(db: Session = Depends(get_db)):
    # Check if simulation is enabled
    sim_setting = db.query(Setting).filter(Setting.key == "simulation_mode").first()
    is_sim = sim_setting and sim_setting.value.lower() == "true"
    
    uid = None
    card_type = "Unknown"
    risk_flags = {}
    
    if not is_sim:
        result = _real_rfid_read()
        if result:
            uid, card_type, risk_flags = result
        else:
            return {"status": "error", "message": "No real RFID hardware found. Please enable Simulation Mode in Settings."}
    else:
        uid, card_type, risk_flags = _simulate_rfid_read(db)
        
    # Calculate Risk
    risk_result = calculate_risk([], "RFID", risk_flags)
    
    # Save to Database
    existing = db.query(RFIDCard).filter(RFIDCard.uid == uid).first()
    if existing:
        card = existing
        card.last_seen = datetime.utcnow()
    else:
        card = RFIDCard(
            uid=uid,
            card_type=card_type,
            risk_level=risk_result["risk_level"],
            risk_score=risk_result["risk_score"]
        )
        db.add(card)
        
    db.commit()
    return {"status": "success", "message": f"Card scanned: {uid}"}

@router.get("/cards", response_model=list[RFIDCardOut])
async def list_cards(db: Session = Depends(get_db)):
    return db.query(RFIDCard).order_by(RFIDCard.last_seen.desc()).all()

@router.delete("/cards")
async def clear_cards(db: Session = Depends(get_db)):
    db.query(RFIDCard).delete()
    db.commit()
    return {"status": "success", "message": "All cards deleted"}
