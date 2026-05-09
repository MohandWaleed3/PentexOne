from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
import serial
import serial.tools.list_ports
import random
import time
import json
from pydantic import BaseModel
from typing import Optional

from database import get_db, RFIDCard, Setting, RFIDScanReport
from models import RFIDCardOut, RFIDScanReportOut
from security_engine import calculate_risk

router = APIRouter(prefix="/rfid", tags=["Access Control"])

# ── Mock RFID Card Pools ──────────────────────────────────────
CARD_PROFILES = [
    {
        "card_type": "Mifare Classic 1K",
        "encryption_type": "Crypto1",
        "auth_mode": "Key A/B",
        "replay_protection": "None",
        "sak": "08",
        "data_sectors": 16,
        "known_vulns": ["Default Keys Detected (FFFFFFFFFFFF)", "Weak Crypto1 Cipher"],
        "base_risk": "RISK",
    },
    {
        "card_type": "Mifare Classic 4K",
        "encryption_type": "Crypto1",
        "auth_mode": "Key A/B",
        "replay_protection": "None",
        "sak": "18",
        "data_sectors": 40,
        "known_vulns": ["Default Keys Detected (FFFFFFFFFFFF)", "Crypto1 Vulnerable to Nested Attack"],
        "base_risk": "RISK",
    },
    {
        "card_type": "NFC NTAG213",
        "encryption_type": "AES-128",
        "auth_mode": "Mutual",
        "replay_protection": "Counter-Based",
        "sak": "00",
        "data_sectors": 45,
        "known_vulns": [],
        "base_risk": "SAFE",
    },
    {
        "card_type": "NFC NTAG216",
        "encryption_type": "AES-128",
        "auth_mode": "Mutual",
        "replay_protection": "Counter-Based",
        "sak": "00",
        "data_sectors": 231,
        "known_vulns": [],
        "base_risk": "SAFE",
    },
    {
        "card_type": "EM4100",
        "encryption_type": "None",
        "auth_mode": "UID-Only",
        "replay_protection": "None",
        "sak": "N/A",
        "data_sectors": 0,
        "known_vulns": ["No Encryption (Plaintext UID)", "Easily Clonable with T5577"],
        "base_risk": "RISK",
    },
    {
        "card_type": "HID iCLASS",
        "encryption_type": "DES",
        "auth_mode": "Key Diversification",
        "replay_protection": "None",
        "sak": "N/A",
        "data_sectors": 2,
        "known_vulns": ["Legacy DES Encryption", "Susceptible to Loclass Attack"],
        "base_risk": "RISK",
    },
    {
        "card_type": "MIFARE DESFire EV2",
        "encryption_type": "AES-128",
        "auth_mode": "Mutual (3-pass)",
        "replay_protection": "Transaction MAC",
        "sak": "20",
        "data_sectors": 28,
        "known_vulns": [],
        "base_risk": "SAFE",
    },
]

# ── Attack Simulation Log Templates ──────────────────────────

ATTACK_LOGS = {
    "Clone": [
        "Initializing Cloning Attack Module...",
        "Powering up Proxmark3 emulator...",
        "Scanning for target card UID: {uid}",
        "Target UID detected — Card Type: {card_type}",
        "Attempting to read authentication keys...",
        "Analyzing encryption: {encryption_type}",
        "Reading card sectors ({sectors} sectors)...",
        "{key_crack_step}",
        "Generating cloned credential on blank T5577...",
        "{result_line}",
    ],
    "Replay": [
        "Initializing Replay Attack Module...",
        "Setting up NFC relay equipment...",
        "Intercepting reader ↔ card session for UID: {uid}",
        "Captured session ID: {session_id}",
        "Checking replay protection: {replay_protection}",
        "Analyzing authentication tokens...",
        "Recording {packet_count} authentication packets...",
        "Replaying captured packets to reader...",
        "{result_line}",
    ],
    "Impersonation": [
        "Initializing Impersonation Attack Module...",
        "Loading stolen credential database...",
        "Target UID: {uid} — Card Type: {card_type}",
        "Evaluating authentication mode: {auth_mode}",
        "Crafting impersonation payload...",
        "Emulating card on Chameleon Mini...",
        "Presenting cloned identity to reader...",
        "Awaiting authentication response...",
        "{result_line}",
    ],
    "Eavesdropping": [
        "Initializing Eavesdropping Module...",
        "Deploying passive sniffing antenna...",
        "Tuning to 13.56 MHz carrier frequency...",
        "Intercepting RF communication for UID: {uid}",
        "Analyzing encryption layer: {encryption_type}",
        "Captured {packet_count} data frames...",
        "Attempting plaintext extraction...",
        "Running frequency analysis on captured data...",
        "{result_line}",
    ],
    "Tampering": [
        "Initializing Tag Tampering Module...",
        "Scanning target tag: {uid}",
        "Current tag integrity: {tag_integrity}",
        "Evaluating write-protection status...",
        "Authentication mode: {auth_mode}",
        "Attempting sector write on Block 4...",
        "Modifying access control bits...",
        "Attempting privilege escalation via data injection...",
        "{result_line}",
    ],
}


def _generate_mock_rfid_card():
    """Generate realistic simulated RFID card data from predefined profiles."""
    def random_uid():
        return ":".join([f"{random.randint(0, 255):02X}" for _ in range(7)])

    profile = random.choice(CARD_PROFILES)
    vulns = list(profile["known_vulns"])  # copy
    risk_level = profile["base_risk"]

    tag_integrity = random.choice(["Valid", "Valid", "Valid", "Valid", "Compromised", "Tampered"])
    if tag_integrity != "Valid":
        vulns.append(f"Tag Integrity Check Failed: {tag_integrity}")
        risk_level = "RISK"

    risk_score = 85.0 if risk_level == "RISK" else 15.0

    return {
        "uid": random_uid(),
        "card_type": profile["card_type"],
        "sak": profile["sak"],
        "encryption_type": profile["encryption_type"],
        "auth_mode": profile["auth_mode"],
        "replay_protection": profile["replay_protection"],
        "tag_integrity": tag_integrity,
        "risk_level": risk_level,
        "risk_score": risk_score,
        "vulnerabilities": vulns,
        "data_sectors": profile["data_sectors"],
        "simulation_status": "Simulated",
    }


def _real_rfid_read():
    """Attempt to read from a real serial RFID reader."""
    ports = serial.tools.list_ports.comports()
    if not ports:
        return None

    try:
        with serial.Serial(ports[0].device, 9600, timeout=2) as ser:
            ser.write(b'\x02\x01\x26\x03')
            time.sleep(0.5)
            if ser.in_waiting:
                data = ser.read(ser.in_waiting).hex()
                return {
                    "uid": data[:14].upper(),
                    "card_type": "Unknown Reality Card",
                    "sak": "??",
                    "encryption_type": "Unknown",
                    "auth_mode": "Unknown",
                    "replay_protection": "Unknown",
                    "tag_integrity": "Unknown",
                    "risk_level": "RISK",
                    "risk_score": 70.0,
                    "vulnerabilities": ["RFID_EASILY_CLONABLE"],
                    "data_sectors": 0,
                    "simulation_status": "Real",
                }
    except Exception:
        pass
    return None


def _build_attack_logs(attack_type: str, uid: str, card_type: str,
                       encryption_type: str, auth_mode: str,
                       replay_protection: str, tag_integrity: str,
                       data_sectors: int, success: bool) -> list:
    """Build step-by-step console logs for an attack simulation."""
    templates = ATTACK_LOGS.get(attack_type, [])
    session_id = f"SES-{random.randint(100000, 999999)}"
    packet_count = random.randint(12, 256)

    if success:
        if encryption_type in ("None", "Crypto1", "DES"):
            key_crack_step = f"KEY CRACKED — Default key FFFFFFFFFFFF accepted on sector 0"
        else:
            key_crack_step = f"Encryption: {encryption_type} — Attempting known-plaintext attack..."
        result_line = f"⚠ ATTACK SUCCESS — CARD IS VULNERABLE"
    else:
        key_crack_step = f"Key brute-force failed — {encryption_type} encryption held"
        result_line = f"✓ ATTACK FAILED — CARD IS SECURE"

    logs = []
    for tmpl in templates:
        logs.append(tmpl.format(
            uid=uid,
            card_type=card_type,
            encryption_type=encryption_type,
            auth_mode=auth_mode,
            replay_protection=replay_protection,
            tag_integrity=tag_integrity,
            sectors=data_sectors,
            session_id=session_id,
            packet_count=packet_count,
            key_crack_step=key_crack_step,
            result_line=result_line,
        ))
    return logs


# ── Endpoints ────────────────────────────────────────────────

@router.post("/scan")
async def scan_rfid(db: Session = Depends(get_db)):
    """Scan for an RFID card (simulated or real)."""
    sim_setting = db.query(Setting).filter(Setting.key == "simulation_mode").first()
    is_sim = sim_setting and sim_setting.value.lower() == "true"

    if not is_sim:
        card_data = _real_rfid_read()
        if not card_data:
            return {"status": "error", "message": "No real RFID hardware found. Please enable Simulation Mode in Settings."}
    else:
        card_data = _generate_mock_rfid_card()

    vulns_json = json.dumps(card_data["vulnerabilities"])

    # Upsert RFIDCard
    existing = db.query(RFIDCard).filter(RFIDCard.uid == card_data["uid"]).first()
    if existing:
        card = existing
        card.last_seen = datetime.utcnow()
        card.card_type = card_data["card_type"]
        card.sak = card_data["sak"]
        card.encryption_type = card_data["encryption_type"]
        card.auth_mode = card_data["auth_mode"]
        card.replay_protection = card_data["replay_protection"]
        card.tag_integrity = card_data["tag_integrity"]
        card.vulnerabilities_json = vulns_json
        card.risk_level = card_data["risk_level"]
        card.risk_score = card_data["risk_score"]
    else:
        card = RFIDCard(
            uid=card_data["uid"],
            card_type=card_data["card_type"],
            sak=card_data["sak"],
            encryption_type=card_data["encryption_type"],
            auth_mode=card_data["auth_mode"],
            replay_protection=card_data["replay_protection"],
            tag_integrity=card_data["tag_integrity"],
            vulnerabilities_json=vulns_json,
            risk_level=card_data["risk_level"],
            risk_score=card_data["risk_score"],
        )
        db.add(card)

    # Persist to RFIDScanReport
    report = RFIDScanReport(
        uid=card_data["uid"],
        card_type=card_data["card_type"],
        encryption_type=card_data["encryption_type"],
        auth_mode=card_data["auth_mode"],
        replay_protection=card_data["replay_protection"],
        tag_integrity=card_data["tag_integrity"],
        risk_level=card_data["risk_level"],
        vulnerabilities=vulns_json,
        simulation_status=card_data["simulation_status"],
    )
    db.add(report)
    db.commit()

    return {
        "status": "success",
        "message": f"Card scanned: {card_data['uid']}",
        "data": card_data,
    }


class AttackSimRequest(BaseModel):
    attack_type: str
    target_uid: Optional[str] = None


@router.post("/attack/simulate")
async def simulate_attack(req: AttackSimRequest, db: Session = Depends(get_db)):
    """Run a simulated RFID attack and return step-by-step logs."""
    attack_type = req.attack_type
    target_uid = req.target_uid

    # If a target UID was given, look it up; otherwise pick the latest card or generate one
    card = None
    if target_uid:
        card = db.query(RFIDCard).filter(RFIDCard.uid == target_uid).first()

    if not card:
        card = db.query(RFIDCard).order_by(RFIDCard.last_seen.desc()).first()

    # Extract properties from the card or use vulnerable defaults
    if card:
        card_type = card.card_type
        encryption_type = card.encryption_type
        auth_mode = card.auth_mode
        replay_protection = card.replay_protection
        tag_integrity = card.tag_integrity
        vulnerabilities = card.vulnerabilities_json
        data_sectors = 16  # default
        uid = card.uid
    else:
        # No card in DB — generate a mock vulnerable card for the demo
        mock = _generate_mock_rfid_card()
        card_type = mock["card_type"]
        encryption_type = mock["encryption_type"]
        auth_mode = mock["auth_mode"]
        replay_protection = mock["replay_protection"]
        tag_integrity = mock["tag_integrity"]
        vulnerabilities = json.dumps(mock["vulnerabilities"])
        data_sectors = mock["data_sectors"]
        uid = mock["uid"]

    # ── Determine attack outcome ──
    success = False
    remediation = ""

    if attack_type == "Clone":
        success = encryption_type in ("None", "Crypto1", "DES")
        remediation = ("Upgrade to AES-128 (e.g. MIFARE DESFire) to prevent cloning."
                       if success else "Strong encryption prevented cloning.")

    elif attack_type == "Replay":
        success = replay_protection == "None"
        remediation = ("Implement challenge-response or timestamp-based replay protection."
                       if success else "Replay protection blocked the attack.")

    elif attack_type == "Impersonation":
        success = auth_mode in ("UID-Only", "Key A/B")
        remediation = ("Use mutual authentication between tag and reader."
                       if success else "Mutual authentication prevented impersonation.")

    elif attack_type == "Eavesdropping":
        success = encryption_type in ("None", "DES")
        remediation = ("Encrypt all RF communication with AES-128 or higher."
                       if success else "Encryption prevented plaintext data recovery.")

    elif attack_type == "Tampering":
        success = tag_integrity in ("Compromised", "Tampered") or auth_mode == "UID-Only"
        remediation = ("Use cryptographic signatures for tag data integrity."
                       if success else "Integrity checks detected and blocked tampering.")
    else:
        raise HTTPException(status_code=400, detail=f"Unknown attack type: {attack_type}")

    attack_result = "Success (Vulnerable)" if success else "Failed (Secure)"
    risk_level = "RISK" if success else "SAFE"

    # Build console-style logs
    logs = _build_attack_logs(
        attack_type=attack_type,
        uid=uid,
        card_type=card_type,
        encryption_type=encryption_type,
        auth_mode=auth_mode,
        replay_protection=replay_protection,
        tag_integrity=tag_integrity,
        data_sectors=data_sectors,
        success=success,
    )

    # Persist to RFIDScanReport
    report = RFIDScanReport(
        uid=uid,
        card_type=card_type,
        encryption_type=encryption_type,
        auth_mode=auth_mode,
        replay_protection=replay_protection,
        tag_integrity=tag_integrity,
        risk_level=risk_level,
        vulnerabilities=vulnerabilities,
        attack_type=attack_type,
        attack_result=attack_result,
        remediation=remediation,
        simulation_status="Simulated",
    )
    db.add(report)
    db.commit()

    return {
        "status": "success",
        "attack_type": attack_type,
        "target_uid": uid,
        "card_type": card_type,
        "encryption_type": encryption_type,
        "auth_mode": auth_mode,
        "replay_protection": replay_protection,
        "tag_integrity": tag_integrity,
        "attack_result": attack_result,
        "risk_level": risk_level,
        "remediation": remediation,
        "logs": logs,
    }


@router.get("/reports", response_model=list[RFIDScanReportOut])
async def list_reports(db: Session = Depends(get_db)):
    return db.query(RFIDScanReport).order_by(RFIDScanReport.timestamp.desc()).all()


@router.delete("/reports")
async def clear_reports(db: Session = Depends(get_db)):
    db.query(RFIDScanReport).delete()
    db.commit()
    return {"status": "success", "message": "All RFID reports deleted"}


@router.get("/cards", response_model=list[RFIDCardOut])
async def list_cards(db: Session = Depends(get_db)):
    return db.query(RFIDCard).order_by(RFIDCard.last_seen.desc()).all()


@router.delete("/cards")
async def clear_cards(db: Session = Depends(get_db)):
    db.query(RFIDCard).delete()
    db.query(RFIDScanReport).delete()
    db.commit()
    return {"status": "success", "message": "All cards and reports deleted"}
