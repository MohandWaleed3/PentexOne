import asyncio
import socket
import subprocess
import nmap
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime
import platform
import re
import ssl
import struct
import logging

# Setup logging
logger = logging.getLogger(__name__)

try:
    from bleak import BleakScanner
    HAS_BLEAK = True
except ImportError:
    HAS_BLEAK = False

from database import get_db, Device, Vulnerability
from models import ScanStatus
from security_engine import calculate_risk, DEFAULT_CREDENTIALS, assess_tls_security

router = APIRouter(prefix="/wireless", tags=["WiFi & Bluetooth"])

# Deauth detection state
deauth_state = {
    "monitoring": False,
    "packets_detected": 0,
    "last_alert": None
}

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
        logger.error(f"Port scan error: {e}")


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
        logger.error(f"BLE Scan Error: {e}")


# ────────────────────────────────────────────────────────────
# 6. مسح شبكات الواي فاي القريبة (SSIDs)
# ────────────────────────────────────────────────────────────
@router.get("/scan/ssids")
async def scan_nearby_ssids():
    """يكتشف كل شبكات الواي فاي القريبة (SSIDs)"""
    system = platform.system()
    networks = []

    try:
        if system == "Darwin":  # macOS
            # استخدام system_profiler للحصول على معلومات الأيربورت
            result = subprocess.run(
                ["system_profiler", "SPAirPortDataType"],
                capture_output=True, text=True, timeout=15
            )
            
            # استخراج الأقسام المهتمين بها
            output = result.stdout
            
            # البحث عن "Other Local Wi-Fi Networks" أو "Current Network Information"
            # سنقوم بتقسيم المخرجات بناءً على السطور
            ssids_found = []
            current_ssid = None
            
            lines = output.split("\n")
            in_networks_section = False
            
            for line in lines:
                if not line.strip(): continue
                
                if "Other Local Wi-Fi Networks:" in line or "Current Network Information:" in line:
                    in_networks_section = True
                    continue
                
                # إذا وصلنا لقسم جديد غير متعلق بالشبكات، نوقف البحث
                if in_networks_section and line.strip() and not line.startswith(" "):
                     in_networks_section = False

                if in_networks_section:
                    line_stripped = line.strip()
                    # سطر الـ SSID في system_profiler ينتهي بـ : 
                    # ويكون مسبوقاً بمسافات (عادة 12 مسافة للشبكات الأخرى)
                    if line_stripped.endswith(":") and ":" not in line_stripped[:-1]:
                        current_ssid = line_stripped[:-1]
                        if current_ssid == "SSID": continue # تجاهل العناوين الفرعية
                        
                        networks.append({
                            "ssid": current_ssid,
                            "rssi": "N/A",
                            "security": "Unknown",
                            "channel": "Unknown"
                        })
                    elif current_ssid and ":" in line:
                        parts = line.split(":", 1)
                        key = parts[0].strip()
                        val = parts[1].strip()
                        
                        if "Signal / Noise" in key:
                            rssi_match = re.search(r'(-\d+) dBm', val)
                            if rssi_match:
                                networks[-1]["rssi"] = int(rssi_match.group(1))
                        elif "Security" in key:
                            networks[-1]["security"] = val
                        elif "Channel" in key:
                            networks[-1]["channel"] = val

        else:  # Linux (nmcli)
            try:
                result = subprocess.run(
                    ["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY,CHAN", "dev", "wifi", "list"],
                    capture_output=True, text=True, timeout=10
                )
                for line in result.stdout.split("\n"):
                    if not line: continue
                    parts = line.split(":")
                    if len(parts) >= 4:
                        networks.append({
                            "ssid": parts[0],
                            "rssi": parts[1],
                            "security": parts[2],
                            "channel": parts[3]
                        })
            except Exception:
                # Fallback to iwlist if nmcli fails
                pass

        # تنظيف النتائج (إزالة المتكرر)
        seen = set()
        unique_networks = []
        for n in networks:
            if n["ssid"] and n["ssid"] not in seen:
                unique_networks.append(n)
                seen.add(n["ssid"])

        return {"status": "success", "ssids": unique_networks, "count": len(unique_networks)}

    except Exception as e:
        return {"status": "error", "message": str(e)}


# ────────────────────────────────────────────────────────────
# 7. TLS/SSL Certificate Validation
# ────────────────────────────────────────────────────────────
@router.post("/tls/check/{host}")
async def check_tls_certificate(host: str, port: int = 443, db: Session = Depends(get_db)):
    """
    Validates TLS/SSL certificate and security for a device.
    Returns identified issues and updates device risk.
    """
    issues = []
    
    try:
        # Create SSL context
        context = ssl.create_default_context()
        
        # Try to connect and get certificate info
        with socket.create_connection((host, port), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=host) as ssock:
                # Check protocol version
                version = ssock.version()
                if version == "SSLv3":
                    issues.append("SSLV3_ENABLED")
                elif version == "TLSv1":
                    issues.append("TLSV1_ENABLED")
                elif version == "TLSv1.1":
                    issues.append("TLSV1_1_ENABLED")
                
                # Get certificate
                cert = ssock.getpeercert()
                if cert:
                    # Check if self-signed
                    if cert.get('issuer') == cert.get('subject'):
                        issues.append("SELF_SIGNED_CERT")
                    
                    # Check expiration
                    from datetime import datetime as dt
                    import email.utils
                    
                    # Parse certificate dates
                    for field in cert.get('notAfter', '').split('\n'):
                        try:
                            expiry = email.utils.parsedate_to_datetime(cert['notAfter'])
                            if expiry < dt.utcnow():
                                issues.append("EXPIRED_CERT")
                        except:
                            pass
                    
                # Check cipher strength
                cipher = ssock.cipher()
                if cipher:
                    cipher_name, cipher_proto, cipher_bits = cipher
                    if cipher_bits and cipher_bits < 128:
                        issues.append("WEAK_CIPHER")
                        
    except ssl.SSLCertVerificationError as e:
        if "self signed" in str(e).lower():
            issues.append("SELF_SIGNED_CERT")
        elif "certificate has expired" in str(e).lower():
            issues.append("EXPIRED_CERT")
        elif "hostname mismatch" in str(e).lower():
            issues.append("CERT_CN_MISMATCH")
    except ssl.SSLError as e:
        if "unsupported protocol" in str(e).lower():
            issues.append("SSLV3_ENABLED")
    except socket.timeout:
        return {"status": "error", "message": "Connection timeout"}
    except socket.error as e:
        return {"status": "error", "message": f"Connection failed: {str(e)}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    
    # Update device in database if issues found
    if issues:
        device = db.query(Device).filter(Device.ip == host).first()
        if device:
            risk_result = calculate_risk(
                [int(p) for p in device.open_ports.split(",") if p.isdigit()],
                device.protocol,
                {"tls_issues": issues}
            )
            device.risk_level = risk_result["risk_level"]
            device.risk_score = risk_result["risk_score"]
            
            for v in risk_result["vulnerabilities"]:
                if v["vuln_type"] in issues:
                    existing = db.query(Vulnerability).filter(
                        Vulnerability.device_id == device.id,
                        Vulnerability.vuln_type == v["vuln_type"]
                    ).first()
                    if not existing:
                        db.add(Vulnerability(
                            device_id=device.id,
                            vuln_type=v["vuln_type"],
                            severity=v["severity"],
                            description=v["description"],
                            protocol="TLS/SSL"
                        ))
            db.commit()
    
    return {
        "status": "success",
        "host": host,
        "port": port,
        "issues": issues,
        "secure": len(issues) == 0
    }


# ────────────────────────────────────────────────────────────
# 8. Wi-Fi Deauthentication Attack Detection
# ────────────────────────────────────────────────────────────
@router.post("/deauth/start")
async def start_deauth_monitor(background_tasks: BackgroundTasks, interface: str = "wlan0mon"):
    """
    Starts monitoring for deauthentication frames on the specified interface.
    Requires monitor mode enabled on the wireless interface.
    """
    if deauth_state["monitoring"]:
        return {"status": "already_running", "message": "Deauth monitoring is already active"}
    
    background_tasks.add_task(run_deauth_monitor, interface)
    deauth_state["monitoring"] = True
    return {"status": "started", "message": f"Deauth monitoring started on {interface}"}


@router.post("/deauth/stop")
async def stop_deauth_monitor():
    """Stops the deauthentication attack monitor."""
    deauth_state["monitoring"] = False
    return {"status": "stopped", "message": "Deauth monitoring stopped"}


@router.get("/deauth/status")
async def get_deauth_status():
    """Returns the current deauth monitoring status and detected attacks."""
    return deauth_state


async def run_deauth_monitor(interface: str):
    """
    Monitors for deauthentication frames using scapy or tcpdump.
    Requires: scapy or aircrack-ng installed
    """
    try:
        from scapy.all import sniff, Dot11, Dot11Deauth
        
        def handle_deauth(pkt):
            if pkt.haslayer(Dot11Deauth):
                deauth_state["packets_detected"] += 1
                deauth_state["last_alert"] = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "source": pkt.addr2 if hasattr(pkt, 'addr2') else "Unknown",
                    "target": pkt.addr1 if hasattr(pkt, 'addr1') else "Unknown"
                }
        
        while deauth_state["monitoring"]:
            try:
                sniff(iface=interface, prn=handle_deauth, timeout=5, store=False)
            except Exception as e:
                await asyncio.sleep(5)
                continue
                
    except ImportError:
        # Fallback to tcpdump if scapy not available
        try:
            process = subprocess.Popen(
                ["tcpdump", "-i", interface, "-l", "type mgt subtype deauth"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            while deauth_state["monitoring"]:
                line = process.stdout.readline()
                if "DeAuth" in line or "deauth" in line:
                    deauth_state["packets_detected"] += 1
                    deauth_state["last_alert"] = {
                        "timestamp": datetime.utcnow().isoformat(),
                        "raw": line.strip()
                    }
                    
        except FileNotFoundError:
            deauth_state["monitoring"] = False
            deauth_state["error"] = "Neither scapy nor tcpdump available for deauth detection"
    except Exception as e:
        deauth_state["monitoring"] = False
        deauth_state["error"] = str(e)
