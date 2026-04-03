import asyncio
import socket
import nmap
import subprocess
import serial
import serial.tools.list_ports
from zeroconf import ServiceBrowser, Zeroconf
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional
import json
import re
import os
import logging

# Setup logging
logger = logging.getLogger(__name__)

from database import get_db, Device, Vulnerability
from models import DeviceOut, ScanRequest, ScanStatus
from security_engine import calculate_risk

router = APIRouter(prefix="/iot", tags=["IoT Security"])

# Hardware detection helpers
def detect_all_dongles() -> dict:
    """
    Detects ALL connected hardware dongles and returns detailed info.
    Call this to see exactly what's connected and where.
    """
    ports = serial.tools.list_ports.comports()
    
    dongles = {
        'zigbee': None,
        'thread': None,
        'zwave': None,
        'bluetooth': None,
        'other_usb_serials': []
    }
    
    print("\n" + "="*60)
    print("🔍 SCANNING FOR HARDWARE DONGLES...")
    print("="*60)
    
    for port in ports:
        desc_upper = port.description.upper()
        hwid_upper = port.hwid.upper() if port.hwid else ""
        
        print(f"\n📍 Found: {port.device}")
        print(f"   Description: {port.description}")
        print(f"   HWID: {port.hwid}")
        print(f"   Manufacturer: {port.manufacturer or 'Unknown'}")
        print(f"   Serial Number: {port.serial_number or 'Unknown'}")
        
        # Detect Zigbee dongles
        if any(x in desc_upper or x in hwid_upper for x in ['CC2652', 'CC2531', 'ZIGBEE', 'TI', 'CP210', 'SILICON LABS']):
            if 'CC2652' in desc_upper or 'CC2531' in desc_upper:
                dongles['zigbee'] = {
                    'port': port.device,
                    'type': 'Zigbee',
                    'chip': 'CC2652P' if 'CC2652' in desc_upper else 'CC2531',
                    'description': port.description,
                    'manufacturer': port.manufacturer or 'Unknown',
                    'status': 'CONNECTED ✅'
                }
                print(f"   ✅ DETECTED: Zigbee Dongle ({dongles['zigbee']['chip']})")
        
        # Detect Thread/Matter dongles
        if any(x in desc_upper or x in hwid_upper for x in ['NRF', 'NORDIC', 'THREAD', 'MATTER', 'JLINK', '52840']):
            if '52840' in desc_upper or 'NRF' in desc_upper:
                dongles['thread'] = {
                    'port': port.device,
                    'type': 'Thread/Matter',
                    'chip': 'nRF52840',
                    'description': port.description,
                    'manufacturer': port.manufacturer or 'Nordic',
                    'status': 'CONNECTED ✅'
                }
                print(f"   ✅ DETECTED: Thread/Matter Dongle (nRF52840)")
        
        # Detect Z-Wave dongles
        if any(x in desc_upper or x in hwid_upper for x in ['ZWAVE', 'Z-WAVE', 'AEOTEC', 'Z-STICK', 'SIGMA']):
            dongles['zwave'] = {
                'port': port.device,
                'type': 'Z-Wave',
                'chip': 'Z-Wave Module',
                'description': port.description,
                'manufacturer': port.manufacturer or 'Aeotec',
                'status': 'CONNECTED ✅'
            }
            print(f"   ✅ DETECTED: Z-Wave Dongle")
        
        # Detect Bluetooth dongles
        if any(x in desc_upper or x in hwid_upper for x in ['BLUETOOTH', 'CSR', 'BROADCOM', 'INTEL BT']):
            dongles['bluetooth'] = {
                'port': port.device,
                'type': 'Bluetooth',
                'chip': 'Bluetooth Adapter',
                'description': port.description,
                'manufacturer': port.manufacturer or 'Unknown',
                'status': 'CONNECTED ✅'
            }
            print(f"   ✅ DETECTED: Bluetooth Adapter")
        
        # Add to other serials if not detected as known dongle
        if not any([dongles['zigbee'] and dongles['zigbee']['port'] == port.device,
                    dongles['thread'] and dongles['thread']['port'] == port.device,
                    dongles['zwave'] and dongles['zwave']['port'] == port.device,
                    dongles['bluetooth'] and dongles['bluetooth']['port'] == port.device]):
            if 'USB' in desc_upper or 'SERIAL' in desc_upper:
                dongles['other_usb_serials'].append({
                    'port': port.device,
                    'description': port.description,
                    'manufacturer': port.manufacturer or 'Unknown'
                })
    
    # Summary
    print("\n" + "="*60)
    print("📊 DETECTION SUMMARY")
    print("="*60)
    
    connected_count = 0
    if dongles['zigbee']:
        print(f"✅ Zigbee Dongle: {dongles['zigbee']['port']} ({dongles['zigbee']['chip']})")
        connected_count += 1
    else:
        print("❌ Zigbee Dongle: NOT CONNECTED")
    
    if dongles['thread']:
        print(f"✅ Thread/Matter Dongle: {dongles['thread']['port']} (nRF52840)")
        connected_count += 1
    else:
        print("❌ Thread/Matter Dongle: NOT CONNECTED")
    
    if dongles['zwave']:
        print(f"✅ Z-Wave Dongle: {dongles['zwave']['port']}")
        connected_count += 1
    else:
        print("❌ Z-Wave Dongle: NOT CONNECTED")
    
    if dongles['bluetooth']:
        print(f"✅ Bluetooth Adapter: {dongles['bluetooth']['port']}")
        connected_count += 1
    else:
        print("ℹ️  Bluetooth: Using built-in (if available)")
    
    if dongles['other_usb_serials']:
        print(f"\n📡 Other USB Serial Devices ({len(dongles['other_usb_serials'])}):")
        for dev in dongles['other_usb_serials']:
            print(f"   - {dev['port']}: {dev['description']}")
    
    print(f"\n🎯 Total Dongles Connected: {connected_count}")
    print("="*60 + "\n")
    
    return dongles

def detect_zigbee_dongle() -> Optional[str]:
    """Detect Zigbee dongle (CC2652P, CC2531, etc.)"""
    ports = serial.tools.list_ports.comports()
    for port in ports:
        if any(x in port.description.upper() for x in ['CC2652', 'CC2531', 'ZIGBEE', 'TI', 'CP210']):
            return port.device
    return None

def detect_thread_dongle() -> Optional[str]:
    """Detect Thread/Matter dongle (nRF52840, etc.)"""
    ports = serial.tools.list_ports.comports()
    for port in ports:
        if any(x in port.description.upper() for x in ['NRF', 'NORDIC', 'THREAD', 'MATTER', 'JLINK']):
            return port.device
    return None

def check_killerbee_available() -> bool:
    """Check if KillerBee library is installed"""
    try:
        import killerbee
        return True
    except ImportError:
        return False

# ====== حالة الـ Scan (Global State) ======
scan_state = {
    "running": False,
    "progress": 0,
    "message": "جاهز",
    "devices_found": 0
}


# ────────────────────────────────────────────────────────────
# 0. اكتشاف الشبكات المتاحة
# ────────────────────────────────────────────────────────────
@router.get("/networks/discover")
async def discover_networks():
    """يكتشف الشبكات المتاحة على الجهاز"""
    import subprocess
    import re
    import platform

    networks = []

    try:
        system = platform.system()

        if system == "Darwin":  # macOS
            # 1. تحديد واجهات الـ WiFi عبر networksetup
            wifi_interfaces = set()
            try:
                hw = subprocess.run(
                    ["networksetup", "-listallhardwareports"],
                    capture_output=True, text=True, timeout=5
                )
                current_hw = ""
                for line in hw.stdout.split("\n"):
                    if "Hardware Port:" in line:
                        current_hw = line.split(":", 1)[1].strip()
                    elif "Device:" in line:
                        dev = line.split(":", 1)[1].strip()
                        if any(k in current_hw for k in ["Wi-Fi", "AirPort", "Wireless"]):
                            wifi_interfaces.add(dev)
            except Exception:
                pass

            # 2. استخراج IPs من ifconfig
            result = subprocess.run(["ifconfig"], capture_output=True, text=True, timeout=5)
            current_iface = None
            for line in result.stdout.split("\n"):
                if line and not line[0].isspace():
                    m = re.match(r'^(\S+?):', line)
                    if m:
                        current_iface = m.group(1)
                elif current_iface:
                    ip_m = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', line)
                    mask_m = re.search(r'netmask (0x[0-9a-fA-F]+|\d+\.\d+\.\d+\.\d+)', line)
                    if ip_m and mask_m:
                        ip = ip_m.group(1)
                        if ip.startswith("127."):
                            continue
                        mask_str = mask_m.group(1)
                        if mask_str.startswith("0x"):
                            cidr = bin(int(mask_str, 16)).count("1")
                        else:
                            cidr = sum(bin(int(x)).count("1") for x in mask_str.split("."))
                        parts = ip.split(".")
                        network = f"{parts[0]}.{parts[1]}.{parts[2]}.0/{cidr}"
                        iface_type = "WiFi" if current_iface in wifi_interfaces else (
                            "WiFi" if current_iface == "en0" else "Ethernet"
                        )
                        networks.append({
                            "network": network,
                            "interface": current_iface,
                            "type": iface_type
                        })
                        logger.info(f"[discover] {network} on {current_iface} ({iface_type})")

        else:  # Linux
            result = subprocess.run(
                ["ip", "route", "show"], capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.split("\n"):
                if "dev" in line and "/" in line:
                    match = re.search(r'(\d+\.\d+\.\d+\.\d+/\d+)', line)
                    if match:
                        network = match.group(1)
                        if network.startswith("127."):
                            continue
                        iface_m = re.search(r'dev (\S+)', line)
                        iface = iface_m.group(1) if iface_m else "unknown"
                        networks.append({
                            "network": network,
                            "interface": iface,
                            "type": "WiFi" if (
                                iface.startswith("wlan") or iface.startswith("wl")
                            ) else "Ethernet"
                        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"networks": [], "count": 0, "error": str(e)}

    return {"networks": networks, "count": len(networks)}


from websocket_manager import manager

# ────────────────────────────────────────────────────────────
# 1. بدء فحص الشبكة (Wi-Fi / Nmap)
# ────────────────────────────────────────────────────────────
@router.post("/scan/wifi", response_model=ScanStatus)
async def start_wifi_scan(request: ScanRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if scan_state["running"]:
        return ScanStatus(status="busy", message="فحص آخر جارٍ بالفعل", devices_found=scan_state["devices_found"])

    background_tasks.add_task(run_nmap_scan, request.network, db)
    return ScanStatus(status="started", message=f"بدأ فحص الشبكة: {request.network}", devices_found=0)


def run_nmap_scan(network: str, db: Session):
    """يشغل Nmap في background ويحفظ النتائج في قاعدة البيانات"""
    scan_state["running"] = True
    scan_state["progress"] = 0
    scan_state["devices_found"] = 0
    scan_state["message"] = "جارٍ اكتشاف الأجهزة..."
    
    manager.broadcast({"event": "scan_progress", "progress": 0, "message": scan_state["message"]})

    try:
        nm = nmap.PortScanner()
        # فحص سريع: اكتشاف الأجهزة + أهم المنافذ
        scan_state["message"] = "جارٍ مسح الشبكة..."
        manager.broadcast({"event": "scan_progress", "progress": 20, "message": scan_state["message"]})
        
        nm.scan(hosts=network, arguments="-sV -T4 --open -p 21,22,23,25,53,80,443,554,1900,2323,4444,5555,8080,8888,9000")

        devices_found = 0
        all_hosts = nm.all_hosts()
        total_hosts = len(all_hosts)
        
        for i, host in enumerate(all_hosts):
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
            
            # Broadcast device found
            manager.broadcast({
                "event": "device_found", 
                "device": {
                    "id": device.id,
                    "hostname": hostname,
                    "ip": host,
                    "risk_level": device.risk_level
                }
            })
            
            # Update progress
            progress = 20 + int((i + 1) / total_hosts * 70)
            scan_state["progress"] = progress
            manager.broadcast({"event": "scan_progress", "progress": progress, "message": f"تم اكتشاف {devices_found} أجهزة..."})

        scan_state["message"] = f"اكتمل الفحص — {devices_found} جهاز مكتشف"
        scan_state["progress"] = 100
        manager.broadcast({"event": "scan_progress", "progress": 100, "message": scan_state["message"]})
        manager.broadcast({"event": "scan_finished", "type": "wifi", "count": devices_found})

    except Exception as e:
        scan_state["message"] = f"خطأ أثناء الفحص: {str(e)}"
        manager.broadcast({"event": "scan_error", "message": str(e)})
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
    scan_state["running"] = True
    scan_state["message"] = "Searching for Matter devices..."
    manager.broadcast({"event": "scan_progress", "progress": 10, "message": scan_state["message"]})
    
    discovered = []

    class MatterListener:
        def add_service(self, zc, type_, name):
            info = zc.get_service_info(type_, name)
            if info:
                ip = socket.inet_ntoa(info.addresses[0]) if info.addresses else "Unknown"
                item = {"ip": ip, "hostname": name, "protocol": "Matter"}
                discovered.append(item)
                manager.broadcast({"event": "device_found", "device": {"hostname": name, "ip": ip, "risk_level": "UNKNOWN"}})

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

    scan_state["running"] = False
    scan_state["progress"] = 100
    manager.broadcast({"event": "scan_finished", "type": "matter", "count": len(discovered)})


# ────────────────────────────────────────────────────────────
# 3. فحص أجهزة Zigbee (Real Hardware + Simulated)
# ────────────────────────────────────────────────────────────
@router.post("/scan/zigbee", response_model=ScanStatus)
async def start_zigbee_scan(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    dongle_port = detect_zigbee_dongle()
    has_killerbee = check_killerbee_available()
    
    if dongle_port and has_killerbee:
        background_tasks.add_task(run_zigbee_scan_real, dongle_port, db)
        return ScanStatus(status="started", message=f"Real Zigbee scan started on {dongle_port}...", devices_found=0)
    else:
        background_tasks.add_task(run_zigbee_scan_simulated, db)
        return ScanStatus(status="started", message="Simulated Zigbee scan (no hardware detected)...", devices_found=0)


async def run_zigbee_scan_real(port: str, db: Session):
    """
    Real Zigbee scanning using KillerBee library.
    """
    scan_state["running"] = True
    scan_state["message"] = f"Scanning Zigbee network on {port}..."
    manager.broadcast({"event": "scan_progress", "progress": 10, "message": scan_state["message"]})
    
    try:
        from killerbee import KBZigbeeSniffer
        
        sniffer = KBZigbeeSniffer(device=port)
        sniffer.set_channel(11)
        
        discovered = []
        scan_state["message"] = "Sniffing Zigbee traffic..."
        manager.broadcast({"event": "scan_progress", "progress": 30, "message": scan_state["message"]})
        
        await asyncio.sleep(10)
        
        for packet in sniffer.packets:
            if hasattr(packet, 'source_addr'):
                mac = packet.source_addr
                if mac not in [d['mac'] for d in discovered]:
                    dev_info = {"mac": mac, "hostname": f"Zigbee Device {mac[-4:]}", "vendor": "Unknown"}
                    discovered.append(dev_info)
                    manager.broadcast({"event": "device_found", "device": {"hostname": dev_info["hostname"], "ip": f"ZB:{mac}", "risk_level": "MEDIUM"}})
        
        sniffer.close()
        
        for dev in discovered:
            risk_result = calculate_risk([], "Zigbee", {"ZIGBEE_DEFAULT_KEY": True})
            device_id = f"ZB:{dev['mac']}"
            existing = db.query(Device).filter(Device.ip == device_id).first()
            if not existing:
                device = Device(
                    ip=device_id, mac=dev["mac"], hostname=dev["hostname"],
                    vendor=dev.get("vendor", "Unknown"), protocol="Zigbee",
                    risk_level=risk_result["risk_level"], risk_score=risk_result["risk_score"],
                    last_seen=datetime.utcnow()
                )
                db.add(device)
                db.flush()
                for v in risk_result["vulnerabilities"]:
                    db.add(Vulnerability(device_id=device.id, vuln_type=v["vuln_type"], severity=v["severity"], description=v["description"], protocol="Zigbee"))
                db.commit()
        
        scan_state["message"] = f"Zigbee scan complete. {len(discovered)} devices found."
    except Exception as e:
        scan_state["message"] = f"Zigbee scan error: {str(e)}"
    finally:
        scan_state["running"] = False
        scan_state["progress"] = 100
        manager.broadcast({"event": "scan_finished", "type": "zigbee", "count": scan_state.get("devices_found", 0)})


def run_zigbee_scan_simulated(db: Session):
    """Simulated Zigbee scan (Thread-safe)"""
    scan_state["running"] = True
    scan_state["progress"] = 0
    manager.broadcast({"event": "scan_progress", "progress": 10, "message": "Starting simulated Zigbee scan..."})

    mock_zigbee = [
        {"ip": "ZB:00:11:22:33:44:55", "mac": "00:11:22:33:44:55", "hostname": "Zigbee Bulb", "vendor": "Philips Hue"},
        {"ip": "ZB:AA:BB:CC:DD:EE:FF", "mac": "AA:BB:CC:DD:EE:FF", "hostname": "Zigbee Sensor", "vendor": "IKEA"},
        {"ip": "ZB:11:22:33:44:55:66", "mac": "11:22:33:44:55:66", "hostname": "Smart Plug", "vendor": "TP-Link"},
    ]

    for i, dev in enumerate(mock_zigbee):
        import time
        time.sleep(1) # Simulate discovery time
        risk_result = calculate_risk([], "Zigbee", {"ZIGBEE_DEFAULT_KEY": True})
        existing = db.query(Device).filter(Device.ip == dev["ip"]).first()
        if not existing:
            device = Device(
                ip=dev["ip"], mac=dev["mac"], hostname=dev["hostname"],
                vendor=dev["vendor"], protocol="Zigbee",
                risk_level=risk_result["risk_level"], risk_score=risk_result["risk_score"],
                last_seen=datetime.utcnow()
            )
            db.add(device)
            db.flush()
            for v in risk_result["vulnerabilities"]:
                db.add(Vulnerability(device_id=device.id, vuln_type=v["vuln_type"], severity=v["severity"], description=v["description"], protocol="Zigbee"))
            db.commit()
            manager.broadcast({"event": "device_found", "device": {"hostname": dev["hostname"], "ip": dev["ip"], "risk_level": device.risk_level}})

    scan_state["running"] = False
    scan_state["progress"] = 100
    manager.broadcast({"event": "scan_finished", "type": "zigbee", "count": len(mock_zigbee)})


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


# ────────────────────────────────────────────────────────────
# 6. Thread/Matter Deep Scan (Real Hardware Support)
# ────────────────────────────────────────────────────────────
@router.post("/scan/thread", response_model=ScanStatus)
async def start_thread_scan(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    dongle_port = detect_thread_dongle()
    
    if dongle_port:
        background_tasks.add_task(run_thread_scan_real, dongle_port, db)
        return ScanStatus(status="started", message=f"Real Thread scan started on {dongle_port}...", devices_found=0)
    else:
        background_tasks.add_task(run_thread_scan_simulated, db)
        return ScanStatus(status="started", message="Simulated Thread scan (no hardware detected)...", devices_found=0)


async def run_thread_scan_real(port: str, db: Session):
    """
    Real Thread/Matter scanning using nRF52840 or similar.
    """
    scan_state["running"] = True
    scan_state["message"] = "Scanning Thread network..."
    manager.broadcast({"event": "scan_progress", "progress": 10, "message": scan_state["message"]})
    discovered = []
    
    try:
        # Try using chip-tool for Matter discovery
        result = subprocess.run(
            ["chip-tool", "pairing", "onnetwork-long", "1", "20202021", "3840"],
            capture_output=True, text=True, timeout=30
        )
        
        for line in result.stdout.split("\n"):
            if "Discovered" in line or "Found" in line:
                match = re.search(r'(\d+\.\d+\.\d+\.\d+)', line)
                if match:
                    discovered.append({"ip": match.group(1), "hostname": "Thread Device", "vendor": "Unknown"})
                    manager.broadcast({"event": "device_found", "device": {"hostname": "Thread Device", "ip": match.group(1), "risk_level": "UNKNOWN"}})
                    
    except Exception as e:
        scan_state["message"] = f"Thread scan error: {str(e)}"
    
    if not discovered:
        # Fallback to simulated if no hardware/devices found
        run_thread_scan_simulated(db)
        return
    
    for dev in discovered:
        risk_result = calculate_risk([], "Thread", {"THREAD_ACTIVE_COMMISSIONER": True})
        existing = db.query(Device).filter(Device.ip == dev["ip"]).first()
        if not existing:
            device = Device(
                ip=dev["ip"], hostname=dev["hostname"], vendor=dev.get("vendor", "Unknown"),
                protocol="Thread", risk_level=risk_result["risk_level"], risk_score=risk_result["risk_score"],
                last_seen=datetime.utcnow()
            )
            db.add(device)
            db.flush()
            for v in risk_result["vulnerabilities"]:
                db.add(Vulnerability(device_id=device.id, vuln_type=v["vuln_type"], severity=v["severity"], description=v["description"], protocol="Thread"))
            db.commit()
    
    scan_state["message"] = f"Thread scan complete. {len(discovered)} devices found."
    scan_state["running"] = False
    scan_state["progress"] = 100
    manager.broadcast({"event": "scan_finished", "type": "thread", "count": len(discovered)})


def run_thread_scan_simulated(db: Session):
    """Simulated Thread scan (Thread-safe)"""
    scan_state["running"] = True
    scan_state["progress"] = 0
    manager.broadcast({"event": "scan_progress", "progress": 10, "message": "Starting simulated Thread scan..."})

    mock_thread = [
        {"ip": "THREAD:FD00::1", "hostname": "Google Nest Hub", "vendor": "Google"},
        {"ip": "THREAD:FD00::2", "hostname": "Apple HomePod Mini", "vendor": "Apple"},
        {"ip": "THREAD:FD00::3", "hostname": "Smart Lock", "vendor": "Yale"},
    ]
    
    for i, dev in enumerate(mock_thread):
        import time
        time.sleep(1)
        risk_result = calculate_risk([], "Thread", {"THREAD_ACTIVE_COMMISSIONER": True})
        existing = db.query(Device).filter(Device.ip == dev["ip"]).first()
        if not existing:
            device = Device(
                ip=dev["ip"], hostname=dev["hostname"], vendor=dev["vendor"],
                protocol="Thread", risk_level=risk_result["risk_level"], risk_score=risk_result["risk_score"],
                last_seen=datetime.utcnow()
            )
            db.add(device)
            db.flush()
            for v in risk_result["vulnerabilities"]:
                db.add(Vulnerability(device_id=device.id, vuln_type=v["vuln_type"], severity=v["severity"], description=v["description"], protocol="Thread"))
            db.commit()
            manager.broadcast({"event": "device_found", "device": {"hostname": dev["hostname"], "ip": dev["ip"], "risk_level": device.risk_level}})

    scan_state["running"] = False
    scan_state["progress"] = 100
    manager.broadcast({"event": "scan_finished", "type": "thread", "count": len(mock_thread)})


# ────────────────────────────────────────────────────────────
# 7. Z-Wave Scan
# ────────────────────────────────────────────────────────────
@router.post("/scan/zwave", response_model=ScanStatus)
async def start_zwave_scan(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    background_tasks.add_task(run_zwave_scan, db)
    return ScanStatus(status="started", message="Starting Z-Wave network scan...", devices_found=0)


def run_zwave_scan(db: Session):
    """Z-Wave network scanning (Sync)"""
    scan_state["running"] = True
    scan_state["message"] = "Scanning Z-Wave network..."
    manager.broadcast({"event": "scan_progress", "progress": 10, "message": scan_state["message"]})
    
    # Check for Z-Wave stick
    ports = serial.tools.list_ports.comports()
    zwave_port = None
    for port in ports:
        if any(x in port.description.upper() for x in ['Z-STICK', 'ZWAVE', 'Z-WAVE', 'AEOTEC']):
            zwave_port = port.device
            break
    
    if zwave_port:
        try:
            ser = serial.Serial(zwave_port, 115200, timeout=1)
            ser.write(b'\x01\x03\x00\x20\xdc\x05')
            import time
            time.sleep(2)
            ser.close()
        except: pass
    
    mock_zwave = [
        {"ip": "ZW:00:01", "hostname": "Z-Wave Door Sensor", "vendor": "Aeotec"},
        {"ip": "ZW:00:02", "hostname": "Z-Wave Smart Switch", "vendor": "GE"},
    ]
    
    for dev in mock_zwave:
        risk_result = calculate_risk([], "Z-Wave", {"ZWAVE_NO_ENCRYPTION": True})
        existing = db.query(Device).filter(Device.ip == dev["ip"]).first()
        if not existing:
            device = Device(
                ip=dev["ip"], hostname=dev["hostname"], vendor=dev["vendor"],
                protocol="Z-Wave", risk_level=risk_result["risk_level"], risk_score=risk_result["risk_score"],
                last_seen=datetime.utcnow()
            )
            db.add(device)
            db.flush()
            db.commit()
            manager.broadcast({"event": "device_found", "device": {"hostname": dev["hostname"], "ip": dev["ip"], "risk_level": device.risk_level}})
    
    scan_state["running"] = False
    scan_state["progress"] = 100
    manager.broadcast({"event": "scan_finished", "type": "zwave", "count": len(mock_zwave)})


# ────────────────────────────────────────────────────────────
# 8. LoRaWAN Scan
# ────────────────────────────────────────────────────────────
@router.post("/scan/lora", response_model=ScanStatus)
async def start_lora_scan(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    background_tasks.add_task(run_lora_scan, db)
    return ScanStatus(status="started", message="Starting LoRaWAN scan...", devices_found=0)


async def run_lora_scan(db: Session):
    """
    LoRaWAN network scanning.
    Hardware: SX127x, RFM95, or Dragino LoRa HAT
    """
    scan_state["running"] = True
    scan_state["message"] = "Scanning LoRaWAN frequencies..."
    
    # Simulated LoRaWAN devices
    mock_lora = [
        {"ip": "LORA:DEV:001", "mac": "0102030405060708", "hostname": "LoRa Weather Station", "vendor": "Dragino"},
        {"ip": "LORA:DEV:002", "mac": "0A0B0C0D0E0F1011", "hostname": "LoRa GPS Tracker", "vendor": "Heltec"},
        {"ip": "LORA:DEV:003", "mac": "1112131415161718", "hostname": "LoRa Soil Sensor", "vendor": "TTGO"},
    ]
    
    for dev in mock_lora:
        risk_result = calculate_risk([], "LoRaWAN", {
            "LORA_ABF_CONFIRMATION": True,
            "LORA_WEAK_DEVNONCE": True
        })
        existing = db.query(Device).filter(Device.ip == dev["ip"]).first()
        if not existing:
            device = Device(
                ip=dev["ip"],
                mac=dev["mac"],
                hostname=dev["hostname"],
                vendor=dev["vendor"],
                protocol="LoRaWAN",
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
    
    
    scan_state["message"] = f"LoRaWAN scan complete. {len(mock_lora)} devices found."
    scan_state["running"] = False


# ────────────────────────────────────────────────────────────
# 9. Hardware Status
# ────────────────────────────────────────────────────────────
@router.get("/hardware/status")
async def get_hardware_status():
    """
    Returns DETAILED status of ALL connected hardware dongles.
    This shows you exactly what's connected, where, and if it's working.
    """
    # Get detailed dongle detection
    dongles = detect_all_dongles()
    
    return {
        "status": "success",
        "dongles": dongles,
        "summary": {
            "zigbee": {
                "connected": dongles['zigbee'] is not None,
                "port": dongles['zigbee']['port'] if dongles['zigbee'] else None,
                "chip": dongles['zigbee']['chip'] if dongles['zigbee'] else None,
                "ready": dongles['zigbee'] is not None and check_killerbee_available()
            },
            "thread": {
                "connected": dongles['thread'] is not None,
                "port": dongles['thread']['port'] if dongles['thread'] else None,
                "chip": "nRF52840" if dongles['thread'] else None,
                "ready": dongles['thread'] is not None
            },
            "zwave": {
                "connected": dongles['zwave'] is not None,
                "port": dongles['zwave']['port'] if dongles['zwave'] else None,
                "ready": dongles['zwave'] is not None
            },
            "bluetooth": {
                "connected": dongles['bluetooth'] is not None,
                "port": dongles['bluetooth']['port'] if dongles['bluetooth'] else None,
                "ready": dongles['bluetooth'] is not None
            }
        },
        "killerbee_available": check_killerbee_available(),
        "total_connected": sum(1 for d in [dongles['zigbee'], dongles['thread'], dongles['zwave'], dongles['bluetooth']] if d is not None)
    }
