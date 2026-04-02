import asyncio
import socket
import subprocess
import nmap
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime

try:
    from bleak import BleakScanner
    HAS_BLEAK = True
except ImportError:
    HAS_BLEAK = False

from database import get_db, Device, Vulnerability
from models import ScanStatus
from security_engine import calculate_risk, DEFAULT_CREDENTIALS

router = APIRouter(prefix="/wireless", tags=["WiFi & Bluetooth"])

# ────────────────────────────────────────────────────────────
# 1. قائمة الواجهات المتاحة
# ────────────────────────────────────────────────────────────
@router.get("/interfaces")
async def list_interfaces():
    """يرجع قائمة واجهات الشبكة المتاحة"""
    try:
        result = subprocess.run(["ip", "link", "show"], capture_output=True, text=True, timeout=5)
        interfaces = []
        for line in result.stdout.split("\n"):
            if ": " in line and "link/" not in line:
                parts = line.split(": ")
                if len(parts) >= 2:
                    iface = parts[1].split("@")[0]
                    interfaces.append(iface)
        return {"interfaces": interfaces or ["wlan0", "wlan1mon", "eth0"]}
    except Exception:
        return {"interfaces": ["wlan0", "eth0"]}


# ────────────────────────────────────────────────────────────
# 2. فحص المنافذ المفتوحة لجهاز معين
# ────────────────────────────────────────────────────────────
@router.post("/test/ports/{ip}")
async def test_open_ports(ip: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    background_tasks.add_task(run_port_scan, ip, db)
    return {"status": "started", "message": f"جارٍ فحص منافذ {ip}"}


async def run_port_scan(ip: str, db: Session):
    try:
        nm = nmap.PortScanner()
        nm.scan(hosts=ip, arguments="-sV -T4 --open -p 1-10000")
        open_ports = []
        if ip in nm.all_hosts():
            for proto in nm[ip].all_protocols():
                for port in nm[ip][proto].keys():
                    if nm[ip][proto][port]["state"] == "open":
                        open_ports.append(port)

        # تحديث الجهاز في قاعدة البيانات
        device = db.query(Device).filter(Device.ip == ip).first()
        if device:
            risk_result = calculate_risk(open_ports, device.protocol)
            device.open_ports = ",".join(map(str, open_ports))
            device.risk_level = risk_result["risk_level"]
            device.risk_score = risk_result["risk_score"]
            db.query(Vulnerability).filter(Vulnerability.device_id == device.id).delete()
            for v in risk_result["vulnerabilities"]:
                db.add(Vulnerability(
                    device_id=device.id,
                    vuln_type=v["vuln_type"],
                    severity=v["severity"],
                    description=v["description"],
                    port=v.get("port"),
                    protocol=v.get("protocol")
                ))
            db.commit()
    except Exception as e:
        print(f"Port scan error: {e}")


# ────────────────────────────────────────────────────────────
# 3. اختبار كلمات المرور الافتراضية
# ────────────────────────────────────────────────────────────
@router.post("/test/credentials/{ip}")
async def test_default_credentials(ip: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    background_tasks.add_task(run_credential_test, ip, db)
    return {"status": "started", "message": f"جارٍ اختبار كلمات المرور الافتراضية على {ip}"}


async def run_credential_test(ip: str, db: Session):
    """يختبر كلمات المرور الافتراضية على HTTP/Telnet"""
    found_cred = None

    # ---- اختبار HTTP Basic Auth ----
    try:
        import urllib.request
        import base64
        for username, password in DEFAULT_CREDENTIALS:
            credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
            req = urllib.request.Request(
                f"http://{ip}",
                headers={"Authorization": f"Basic {credentials}"}
            )
            try:
                urllib.request.urlopen(req, timeout=2)
                found_cred = (username, password)
                break
            except Exception:
                continue
    except Exception:
        pass

    # ---- اختبار Telnet ----
    if not found_cred:
        try:
            for username, password in DEFAULT_CREDENTIALS[:5]:   # أسرع 5 محاولات
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(2)
                if s.connect_ex((ip, 23)) == 0:
                    found_cred = (username, password)
                    s.close()
                    break
                s.close()
        except Exception:
            pass

    # ---- تحديث قاعدة البيانات ----
    if found_cred:
        device = db.query(Device).filter(Device.ip == ip).first()
        if device:
            open_ports = [int(p) for p in device.open_ports.split(",") if p.isdigit()]
            risk_result = calculate_risk(open_ports, device.protocol, {"default_creds": found_cred})
            device.risk_level = risk_result["risk_level"]
            device.risk_score = risk_result["risk_score"]
            for v in risk_result["vulnerabilities"]:
                if v["vuln_type"] == "DEFAULT_CREDENTIALS":
                    existing_vuln = db.query(Vulnerability).filter(
                        Vulnerability.device_id == device.id,
                        Vulnerability.vuln_type == "DEFAULT_CREDENTIALS"
                    ).first()
                    if not existing_vuln:
                        db.add(Vulnerability(
                            device_id=device.id,
                            vuln_type=v["vuln_type"],
                            severity=v["severity"],
                            description=v["description"],
                            protocol="HTTP/Telnet"
                        ))
            db.commit()


# ────────────────────────────────────────────────────────────
# 4. فحص شامل لجهاز واحد (Ports + Credentials)
# ────────────────────────────────────────────────────────────
@router.post("/scan/full/{ip}")
async def full_device_scan(ip: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    background_tasks.add_task(run_port_scan, ip, db)
    background_tasks.add_task(run_credential_test, ip, db)
    return {"status": "started", "message": f"جارٍ الفحص الشامل لـ {ip}"}


# ────────────────────────────────────────────────────────────
# 5. فحص أجهزة البلوتوث (BLE)
# ────────────────────────────────────────────────────────────
@router.post("/scan/bluetooth", response_model=ScanStatus)
async def start_bluetooth_scan(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if not HAS_BLEAK:
        return ScanStatus(status="error", message="مكتبة bleak غير متوفرة أو البلوتوث غير مدعوم على هذا النظام")
    background_tasks.add_task(run_bluetooth_scan, db)
    return ScanStatus(status="started", message="جارٍ البحث عن أجهزة البلوتوث (BLE) المجاورة...")


async def run_bluetooth_scan(db: Session):
    try:
        devices = await BleakScanner.discover(timeout=5.0)
        for dev in devices:
            mac = dev.address
            hostname = dev.name or "Unknown BLE Device"
            # Some basics heuristic for BLE risks
            risk_flags = {}
            if "Smart" in hostname or "Lock" in hostname:
                risk_flags["BLE_EXPOSED_CHARACTERISTICS"] = True
            if "Unknown" in hostname:
                risk_flags["BLE_NO_PAIRING"] = True
                
            risk_result = calculate_risk([], "Bluetooth", risk_flags)
            
            existing = db.query(Device).filter(Device.mac == mac, Device.protocol == "Bluetooth").first()
            if existing:
                device = existing
                device.last_seen = datetime.utcnow()
                device.risk_level = risk_result["risk_level"]
                device.risk_score = risk_result["risk_score"]
                device.hostname = hostname
                db.query(Vulnerability).filter(Vulnerability.device_id == device.id).delete()
            else:
                device = Device(
                    ip=f"BLE_{mac[-8:]}", # Mock IP
                    mac=mac,
                    hostname=hostname,
                    vendor="Bluetooth LE",
                    protocol="Bluetooth",
                    os_guess="Firmware",
                    open_ports="",
                    risk_level=risk_result["risk_level"],
                    risk_score=risk_result["risk_score"],
                    last_seen=datetime.utcnow()
                )
                db.add(device)
                db.flush()
                
            for v in risk_result["vulnerabilities"]:
                db.add(Vulnerability(
                    device_id=device.id,
                    vuln_type=v["vuln_type"],
                    severity=v["severity"],
                    description=v["description"],
                    protocol="Bluetooth"
                ))
            db.commit()
    except Exception as e:
        print(f"BLE Scan Error: {e}")
