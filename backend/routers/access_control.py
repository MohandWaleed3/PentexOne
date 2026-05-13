from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime
import serial
import serial.tools.list_ports
import random
import time
import json
import asyncio
from pydantic import BaseModel
from typing import Optional

from database import get_db, RFIDCard, Setting, RFIDScanReport, SessionLocal
from models import RFIDCardOut, RFIDScanReportOut
from security_engine import calculate_risk
from websocket_manager import manager

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


def generate_mock_rfid_card():
    """Generate realistic simulated RFID card data from predefined profiles with high entropy."""
    def random_uid():
        # Standard 7-byte UID or 4-byte UID
        length = random.choice([4, 7])
        return ":".join([f"{random.randint(0, 255):02X}" for _ in range(length)])

    profile = random.choice(CARD_PROFILES)
    vulns = list(profile["known_vulns"])
    
    # Randomize sectors slightly based on type
    sectors = profile["data_sectors"]
    if sectors > 0:
        sectors = max(1, sectors + random.randint(-2, 2))

    # Dynamic Integrity check
    integrity_options = ["Valid", "Valid", "Valid", "Valid", "Compromised", "Tampered", "Invalid Checksum"]
    tag_integrity = random.choice(integrity_options)
    
    # Override risk if integrity is bad
    risk_level = profile["base_risk"]
    if tag_integrity != "Valid":
        vulns.append(f"Tag Integrity Error: {tag_integrity}")
        risk_level = "RISK"

    # Dynamic risk score with some jitter
    base_score = 85.0 if risk_level == "RISK" else 15.0
    risk_score = min(100, max(0, base_score + random.uniform(-10, 10)))

    return {
        "uid": random_uid(),
        "card_type": profile["card_type"],
        "sak": profile["sak"] if profile["sak"] != "N/A" else f"{random.randint(0, 31):02X}",
        "encryption_type": profile["encryption_type"],
        "auth_mode": profile["auth_mode"],
        "replay_protection": profile["replay_protection"],
        "tag_integrity": tag_integrity,
        "risk_level": risk_level,
        "risk_score": round(risk_score, 1),
        "vulnerabilities": vulns,
        "data_sectors": sectors,
        "simulation_status": "Simulated",
    }


def _simulate_rfid_read():
    """Simulate an RFID read by generating mock data."""
    return generate_mock_rfid_card()


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
                       data_sectors: int, success_level: str) -> list:
    """Build step-by-step console logs for an attack simulation."""
    templates = ATTACK_LOGS.get(attack_type, [])
    session_id = f"SES-{random.randint(100000, 999999)}"
    packet_count = random.randint(12, 256)

    if success_level == "Success":
        if encryption_type in ("None", "Crypto1", "DES"):
            key_crack_step = f"KEY CRACKED — Default key FFFFFFFFFFFF accepted on sector 0"
        else:
            key_crack_step = f"Encryption: {encryption_type} — Attempting known-plaintext attack...\n  [SUCCESS] Key recovered."
        result_line = f" [COMPROMISED] ⚠ ATTACK SUCCESS — CARD IS VULNERABLE"
    elif success_level == "Partial":
        key_crack_step = f"Encryption: {encryption_type} — Partial bypass achieved.\n  [WARNING] Recovered limited data sectors."
        result_line = f" [WARNING] ⚠ ATTACK PARTIAL — PARTIAL COMPROMISE"
    else:
        # Realistic brute-force failure sequence for protected cards
        key_crack_step = (
            f"Attempting brute-force on {encryption_type}...\n"
            f"  [TRY] Key: 4D6966617265...\n"
            f"  [TRY] Key: 536563757265...\n"
            f"  [FAIL] Brute-force failed — AES-128 hardware protection active."
        )
        result_line = f" [SAFE] ✓ ATTACK FAILED — CARD IS SECURE"

    logs = []
    for tmpl in templates:
        line = tmpl.format(
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
        )
        # Split by newline if we added them in key_crack_step
        if "\n" in line:
            logs.extend(line.split("\n"))
        else:
            logs.append(line)
    return logs


# ── Endpoints ────────────────────────────────────────────────

@router.post("/scan")
async def scan_rfid(db: Session = Depends(get_db)):
    """Scan for an RFID card (simulated or real). Always falls back to simulation if no hardware."""
    sim_setting = db.query(Setting).filter(Setting.key == "simulation_mode").first()
    is_sim = sim_setting and sim_setting.value.lower() == "true"

    if not is_sim:
        return {"status": "error", "message": "RFID scanning is currently restricted to Simulation Mode. Please enable Simulation Mode in the dashboard settings to proceed."}
    
    card_data = _simulate_rfid_read()

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
        "message": f"Card scanned: {card_data['uid']} ({card_data['simulation_status']})",
        "card": card_data,
        "simulated": card_data["simulation_status"] == "Simulated"
    }


@router.post("/scan/mock")
async def scan_rfid_mock(db: Session = Depends(get_db)):
    """Explicitly scan for a mock RFID card."""
    card_data = _simulate_rfid_read()
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
        "message": f"Card scanned: {card_data['uid']} (Simulated)",
        "card": card_data,
        "simulated": True
    }


class AttackSimRequest(BaseModel):
    attack_type: str
    target_uid: Optional[str] = None
    card_id: Optional[int] = None


async def run_attack_simulation_streamed(attack_type: str, target_uid: Optional[str],
                                         card_id: Optional[int], db_session: Session):
    """Execute attack simulation and stream logs via WebSocket."""
    db = db_session
    try:
        # If a target UID or card ID was given, look it up; otherwise pick the latest card or generate one
        card = None
        if card_id is not None:
            card = db.query(RFIDCard).filter(RFIDCard.id == card_id).first()
        elif target_uid:
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
            data_sectors = 16
            uid = card.uid
        else:
            mock = _simulate_rfid_read()
            card_type = mock["card_type"]
            encryption_type = mock["encryption_type"]
            auth_mode = mock["auth_mode"]
            replay_protection = mock["replay_protection"]
            tag_integrity = mock["tag_integrity"]
            vulnerabilities = json.dumps(mock["vulnerabilities"])
            data_sectors = mock["data_sectors"]
            uid = mock["uid"]

        # Determine attack outcome
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
            remediation = "Unknown attack type."

        attack_result = "Success (Vulnerable)" if success else "Failed (Secure)"
        risk_level = "RISK" if success else "SAFE"

        # Map boolean success to the 3-level success_level string
        if success:
            success_level = "Success"
        else:
            success_level = "Failed"

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
            success_level=success_level,
        )

        # Broadcast start event
        manager.broadcast({
            "event": "attack_simulation_start",
            "attack_type": attack_type,
            "target_uid": uid,
            "card_type": card_type,
            "status": "Starting attack simulation..."
        })

        # Stream each log line with typing delay
        for step, log_line in enumerate(logs, 1):
            manager.broadcast({
                "event": "attack_simulation_log",
                "attack_type": attack_type,
                "target_uid": uid,
                "step": step,
                "total_steps": len(logs),
                "log_line": log_line,
                "timestamp": datetime.utcnow().isoformat()
            })
            # Typing delay: 0.8-1.5s per line for realistic effect
            await asyncio.sleep(random.uniform(0.8, 1.5))

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

        # Broadcast completion event
        manager.broadcast({
            "event": "attack_simulation_complete",
            "attack_type": attack_type,
            "target_uid": uid,
            "success": success,
            "attack_result": attack_result,
            "risk_level": risk_level,
            "remediation": remediation,
            "status": "Attack simulation complete"
        })

    except Exception as e:
        manager.broadcast({
            "event": "attack_simulation_error",
            "attack_type": attack_type,
            "error": str(e)
        })
    finally:
        db.close()


@router.post("/attack/simulate")
async def simulate_attack(req: AttackSimRequest, db: Session = Depends(get_db)):
    """Run a simulated RFID attack and return step-by-step logs."""
    attack_type = req.attack_type
    target_uid = req.target_uid

    # If a target UID or card ID was given, look it up; otherwise pick the latest card or generate one
    card = None
    if req.card_id is not None:
        card = db.query(RFIDCard).filter(RFIDCard.id == req.card_id).first()
    elif target_uid:
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
        mock = _simulate_rfid_read()
        card_type = mock["card_type"]
        encryption_type = mock["encryption_type"]
        auth_mode = mock["auth_mode"]
        replay_protection = mock["replay_protection"]
        tag_integrity = mock["tag_integrity"]
        vulnerabilities = json.dumps(mock["vulnerabilities"])
        data_sectors = mock["data_sectors"]
        uid = mock["uid"]

    # ── Determine attack outcome ──
    # Base probability on encryption type and other attributes
    base_vuln_score = 0
    if encryption_type in ("None", "Crypto1", "DES"): base_vuln_score += 40
    if auth_mode in ("UID-Only", "Key A/B"): base_vuln_score += 30
    if replay_protection == "None": base_vuln_score += 30
    
    # Add some randomness to simulate dynamic real-world conditions
    roll = random.randint(0, 100)
    total_score = base_vuln_score + roll

    success_level = "Failed"
    if total_score > 120:
        success_level = "Success"
    elif total_score > 80:
        success_level = "Partial"

    remediation = ""

    if attack_type == "Clone":
        if success_level == "Success":
            remediation = "Upgrade to AES-128 (e.g. MIFARE DESFire) to prevent cloning."
        elif success_level == "Partial":
            remediation = "Cloning partially succeeded. Ensure UID is not the sole authentication factor."
        else:
            remediation = "Strong encryption prevented cloning."

    elif attack_type == "Replay":
        if success_level == "Success":
            remediation = "Implement challenge-response or timestamp-based replay protection."
        elif success_level == "Partial":
            remediation = "Replay window was limited but exploitable. Enforce strict timing."
        else:
            remediation = "Replay protection blocked the attack."

    elif attack_type == "Impersonation":
        if success_level == "Success":
            remediation = "Use mutual authentication between tag and reader."
        elif success_level == "Partial":
            remediation = "Partial impersonation achieved. Ensure full session validation."
        else:
            remediation = "Mutual authentication prevented impersonation."

    elif attack_type == "Eavesdropping":
        if success_level == "Success":
            remediation = "Encrypt all RF communication with AES-128 or higher."
        elif success_level == "Partial":
            remediation = "Some plaintext data recovered. Enhance encryption algorithms."
        else:
            remediation = "Encryption prevented plaintext data recovery."

    elif attack_type == "Tampering":
        if success_level == "Success":
            remediation = "Use cryptographic signatures for tag data integrity."
        elif success_level == "Partial":
            remediation = "Minor data tampering bypassed checks. Strengthen integrity verification."
        else:
            remediation = "Integrity checks detected and blocked tampering."
    else:
        raise HTTPException(status_code=400, detail=f"Unknown attack type: {attack_type}")

    attack_result = f"{success_level} ({'Vulnerable' if success_level != 'Failed' else 'Secure'})"
    risk_level = "RISK" if success_level == "Success" else ("MEDIUM" if success_level == "Partial" else "SAFE")
    success = success_level != "Failed"

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
        success_level=success_level,
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
        "success": success,
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


@router.post("/attack/simulate-stream")
async def simulate_attack_stream(req: AttackSimRequest, background_tasks: BackgroundTasks):
    """Run attack simulation with real-time WebSocket streaming of logs."""
    db = SessionLocal()
    background_tasks.add_task(run_attack_simulation_streamed, req.attack_type, req.target_uid, req.card_id, db)
    return {
        "status": "started",
        "message": f"Attack simulation '{req.attack_type}' started. Logs streaming via WebSocket...",
        "attack_type": req.attack_type
    }


@router.get("/reports", response_model=list[RFIDScanReportOut])
async def list_reports(db: Session = Depends(get_db)):
    return db.query(RFIDScanReport).order_by(RFIDScanReport.timestamp.desc()).all()


@router.delete("/reports")
async def clear_reports(db: Session = Depends(get_db)):
    db.query(RFIDScanReport).delete()
    db.commit()
    return {"status": "success", "message": "All RFID reports deleted"}


@router.get("/vulnerability-report")
async def rfid_vulnerability_report(db: Session = Depends(get_db)):
    cards = db.query(RFIDCard).order_by(RFIDCard.last_seen.desc()).all()
    total_cards = len(cards)
    secure_cards = sum(1 for c in cards if c.risk_level == "SAFE")
    vulnerable_cards = total_cards - secure_cards
    average_risk_score = round(sum(c.risk_score for c in cards) / total_cards, 1) if total_cards else 0.0

    card_items = [
        {
            "id": c.id,
            "uid": c.uid,
            "card_type": c.card_type,
            "sak": c.sak,
            "encryption_type": c.encryption_type,
            "auth_mode": c.auth_mode,
            "replay_protection": c.replay_protection,
            "tag_integrity": c.tag_integrity,
            "vulnerabilities_json": c.vulnerabilities_json,
            "risk_level": c.risk_level,
            "risk_score": c.risk_score,
            "last_seen": c.last_seen,
        }
        for c in cards
    ]

    return {
        "cards": card_items,
        "total_cards": total_cards,
        "secure_cards": secure_cards,
        "vulnerable_cards": vulnerable_cards,
        "average_risk_score": average_risk_score,
    }


@router.get("/analyze/{card_id}")
async def analyze_rfid_card(card_id: int, db: Session = Depends(get_db)):
    card = db.query(RFIDCard).filter(RFIDCard.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="RFID card not found")

    vulnerabilities = []
    try:
        vulnerabilities = json.loads(card.vulnerabilities_json or "[]")
    except Exception:
        vulnerabilities = []

    insights = []
    if card.encryption_type in ("None", "DES", "Crypto1"):
        insights.append("Weak encryption detected. The tag is highly susceptible to cloning and eavesdropping.")
    elif card.encryption_type == "AES-128":
        insights.append("Strong AES-128 encryption is present, but replay and integrity protections should still be verified.")
    else:
        insights.append("Unknown encryption type. Validate the tag against your security baseline.")

    if card.replay_protection in ("None", "Unknown"):
        insights.append("No replay protection detected. This increases risk of replay attacks.")
    else:
        insights.append(f"Replay protection is enabled ({card.replay_protection}).")

    if card.tag_integrity not in ("Valid", "Unknown"):
        insights.append(f"Tag integrity check triggered: {card.tag_integrity}. This could indicate tampering.")

    recommendation = "Review the card profile and migrate to a secure tag family such as MIFARE DESFire EV2 with AES and mutual authentication."
    if card.risk_level == "SAFE":
        recommendation = "Card appears secure, but continue monitoring and enforce strong key management."

    return {
        "status": "success",
        "analysis": {
            "uid": card.uid,
            "card_type": card.card_type,
            "risk_level": card.risk_level,
            "risk_score": card.risk_score,
            "insights": insights,
            "vulnerability_count": len(vulnerabilities),
            "recommendation": recommendation,
        }
    }


@router.get("/cards", response_model=list[RFIDCardOut])
async def list_cards(db: Session = Depends(get_db)):
    return db.query(RFIDCard).order_by(RFIDCard.last_seen.desc()).all()


@router.delete("/cards")
async def clear_cards(db: Session = Depends(get_db)):
    db.query(RFIDCard).delete()
    db.query(RFIDScanReport).delete()
    db.commit()
    return {"status": "success", "message": "All cards and reports deleted"}
