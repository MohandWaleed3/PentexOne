import asyncio
import socket
import nmap
from zeroconf import ServiceBrowser, Zeroconf
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List

from database import get_db, Device, Vulnerability
from models import DeviceOut, ScanRequest, ScanStatus
from security_engine import calculate_risk

router = APIRouter(prefix="/iot", tags=["IoT Security"])

# ====== حالة الـ Scan (Global State) ======
scan_state = {
    "running": False,
    "progress": 0,
    "message": "جاهز",
    "devices_found": 0
}


# ────────────────────────────────────────────────────────────
# 1. بدء فحص الشبكة (Wi-Fi / Nmap)
# ────────────────────────────────────────────────────────────
@router.post("/scan/wifi", response_model=ScanStatus)
async def start_wifi_scan(request: ScanRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if scan_state["running"]:
        return ScanStatus(status="busy", message="فحص آخر جارٍ بالفعل", devices_found=scan_state["devices_found"])

    background_tasks.add_task(run_nmap_scan, request.network, db)
    return ScanStatus(status="started", message=f"بدأ فحص الشبكة: {request.network}", devices_found=0)


async def run_nmap_scan(network: str, db: Session):
    """يشغل Nmap في background ويحفظ النتائج في قاعدة البيانات"""
    scan_state["running"] = True
    scan_state["progress"] = 0
    scan_state["message"] = "جارٍ اكتشاف الأجهزة..."

    try:
        nm = nmap.PortScanner()
        # فحص سريع: اكتشاف الأجهزة + أهم المنافذ
        scan_state["message"] = "جارٍ مسح الشبكة..."
        nm.scan(hosts=network, arguments="-sV -T4 --open -p 21,22,23,25,53,80,443,554,1900,2323,4444,5555,8080,8888,9000")

        devices_found = 0
        for host in nm.all_hosts():
            if nm[host].state() != "up":
                continue

            # استخراج بيانات الجهاز
            hostname = nm[host].hostname() or "Unknown"
            mac = nm[host]["addresses"].get("mac", "Unknown")
            vendor = nm[host]["vendor"].get(mac, "Unknown") if mac != "Unknown" else "Unknown"

            # المنافذ المفتوحة
            open_ports = []
            for proto in nm[host].all_protocols():
                for port in nm[host][proto].keys():
                    if nm[host][proto][port]["state"] == "open":
                        open_ports.append(port)

            # os guess
            os_guess = "Unknown"
            if "osmatch" in nm[host] and nm[host]["osmatch"]:
                os_guess = nm[host]["osmatch"][0].get("name", "Unknown")

            # تقييم الأمان
            risk_result = calculate_risk(open_ports, "Wi-Fi")

            # حفظ في قاعدة البيانات (أو تحديث إذا موجود)
            existing = db.query(Device).filter(Device.ip == host).first()
            if existing:
                device = existing
                device.last_seen = datetime.utcnow()
                device.open_ports = ",".join(map(str, open_ports))
                device.risk_level = risk_result["risk_level"]
                device.risk_score = risk_result["risk_score"]
                # حذف الثغرات القديمة وإعادة إضافتها
                db.query(Vulnerability).filter(Vulnerability.device_id == device.id).delete()
            else:
                device = Device(
                    ip=host,
                    mac=mac,
                    hostname=hostname,
                    vendor=vendor,
                    protocol="Wi-Fi",
                    os_guess=os_guess,
                    open_ports=",".join(map(str, open_ports)),
                    risk_level=risk_result["risk_level"],
                    risk_score=risk_result["risk_score"],
                    last_seen=datetime.utcnow()
                )
                db.add(device)
                db.flush()

            # حفظ الثغرات
            for v in risk_result["vulnerabilities"]:
                vuln = Vulnerability(
                    device_id=device.id,
                    vuln_type=v["vuln_type"],
                    severity=v["severity"],
                    description=v["description"],
                    port=v.get("port"),
                    protocol=v.get("protocol")
                )
                db.add(vuln)

            db.commit()
            devices_found += 1
            scan_state["devices_found"] = devices_found

        scan_state["message"] = f"اكتمل الفحص — {devices_found} جهاز مكتشف"
        scan_state["progress"] = 100

    except Exception as e:
        scan_state["message"] = f"خطأ أثناء الفحص: {str(e)}"
    finally:
        scan_state["running"] = False


# ────────────────────────────────────────────────────────────
# 2. فحص أجهزة Matter (mDNS Discovery)
# ────────────────────────────────────────────────────────────
@router.post("/scan/matter", response_model=ScanStatus)
async def start_matter_scan(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    background_tasks.add_task(run_matter_scan, db)
    return ScanStatus(status="started", message="جارٍ البحث عن أجهزة Matter...", devices_found=0)


async def run_matter_scan(db: Session):
    """يكتشف أجهزة Matter عبر mDNS (Zeroconf)"""
    discovered = []

    class MatterListener:
        def add_service(self, zc, type_, name):
            info = zc.get_service_info(type_, name)
            if info:
                ip = socket.inet_ntoa(info.addresses[0]) if info.addresses else "Unknown"
                discovered.append({"ip": ip, "hostname": name, "protocol": "Matter"})

        def remove_service(self, *args): pass
        def update_service(self, *args): pass

    zc = Zeroconf()
    browser = ServiceBrowser(zc, "_matter._tcp.local.", MatterListener())
    await asyncio.sleep(5)  # انتظار 5 ثواني للاكتشاف
    zc.close()

    for dev in discovered:
        risk_result = calculate_risk([], "Matter", {
            "MATTER_OPEN_COMMISS": True,
        })
        existing = db.query(Device).filter(Device.ip == dev["ip"]).first()
        if not existing:
            device = Device(
                ip=dev["ip"],
                hostname=dev["hostname"],
                protocol="Matter",
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
                    protocol=v.get("protocol")
                ))
            db.commit()


# ────────────────────────────────────────────────────────────
# 3. فحص أجهزة Zigbee (Simulated — يحتاج Dongle على الـ Pi)
# ────────────────────────────────────────────────────────────
@router.post("/scan/zigbee", response_model=ScanStatus)
async def start_zigbee_scan(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    background_tasks.add_task(run_zigbee_scan, db)
    return ScanStatus(status="started", message="جارٍ البحث عن أجهزة Zigbee...", devices_found=0)


async def run_zigbee_scan(db: Session):
    """
    في البيئة الحقيقية: يستخدم KillerBee/zbdump مع محول Zigbee USB.
    حالياً: يحاكي اكتشاف Zigbee للاختبار.
    """
    # Mock Zigbee devices for testing (استبدلها بـ KillerBee على الـ Pi الحقيقي)
    mock_zigbee = [
        {"ip": "ZB:00:11:22:33:44:55", "mac": "00:11:22:33:44:55",
         "hostname": "Zigbee Bulb", "vendor": "Philips Hue"},
        {"ip": "ZB:AA:BB:CC:DD:EE:FF", "mac": "AA:BB:CC:DD:EE:FF",
         "hostname": "Zigbee Sensor", "vendor": "IKEA"},
    ]

    for dev in mock_zigbee:
        risk_result = calculate_risk([], "Zigbee", {
            "ZIGBEE_DEFAULT_KEY": True,
            "ZIGBEE_REPLAY": True
        })
        existing = db.query(Device).filter(Device.ip == dev["ip"]).first()
        if not existing:
            device = Device(
                ip=dev["ip"],
                mac=dev["mac"],
                hostname=dev["hostname"],
                vendor=dev["vendor"],
                protocol="Zigbee",
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
                    protocol=v.get("protocol")
                ))
            db.commit()


# ────────────────────────────────────────────────────────────
# 4. حالة الفحص الحالية
# ────────────────────────────────────────────────────────────
@router.get("/scan/status")
async def get_scan_status():
    return scan_state


# ────────────────────────────────────────────────────────────
# 5. قائمة الأجهزة
# ────────────────────────────────────────────────────────────
@router.get("/devices", response_model=List[DeviceOut])
async def get_all_devices(db: Session = Depends(get_db)):
    devices = db.query(Device).order_by(Device.risk_score.desc()).all()
    return devices


@router.get("/devices/{device_id}", response_model=DeviceOut)
async def get_device(device_id: int, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="الجهاز غير موجود")
    return device


@router.delete("/devices")
async def clear_all_devices(db: Session = Depends(get_db)):
    db.query(Vulnerability).delete()
    db.query(Device).delete()
    db.commit()
    return {"message": "تم مسح جميع الأجهزة"}
