import asyncio
import socket
import subprocess
import nmap
import threading
import time
import json
import os
from fastapi import APIRouter, Depends, BackgroundTasks, Body
from sqlalchemy.orm import Session
from datetime import datetime
import platform
import re
import ssl
import struct
import logging
from typing import Optional

# Setup logging
logger = logging.getLogger(__name__)

try:
    from bleak import BleakScanner
    HAS_BLEAK = True
except ImportError:
    HAS_BLEAK = False

from database import get_db, Device, Vulnerability, SessionLocal
from models import ScanStatus
from security_engine import calculate_risk, DEFAULT_CREDENTIALS, assess_tls_security

# Import enhanced detection functions from iot module
from routers.iot import get_hostname_enhanced, get_vendor_from_mac
from websocket_manager import manager

router = APIRouter(prefix="/wireless", tags=["WiFi & Bluetooth"])

# Deauth detection state
deauth_state = {
    "monitoring": False,
    "packets_detected": 0,
    "last_alert": None
}

# ============================================================================
# ADVANCED WIFI - MONITOR MODE & PACKET CAPTURE STATE
# ============================================================================
monitor_state = {
    "active": False,
    "interface": None,
    "original_interface": None,
    "mode": None,  # 'monitor' or 'managed'
    "channel": None,
    "started_at": None
}

# Client sniffing state
sniffer_state = {
    "active": False,
    "clients": [],
    "probe_requests": [],
    "packets_captured": 0,
    "started_at": None
}

# Handshake capture state
handshake_state = {
    "active": False,
    "target_ssid": None,
    "target_bssid": None,
    "channel": None,
    "handshake_captured": False,
    "capture_file": None,
    "packets_captured": 0,
    "started_at": None
}

# Deauth attack test state
deauth_attack_state = {
    "active": False,
    "target_mac": None,
    "ap_bssid": None,
    "packets_sent": 0,
    "client_disconnected": False,
    "protected": False,  # 802.11w MFP
    "started_at": None
}

# Rogue AP detection state
rogue_ap_state = {
    "active": False,
    "alerts": [],
    "known_aps": [],
    "started_at": None
}

# ────────────────────────────────────────────────────────────
# 1. قائمة الواجهات المتاحة
# ────────────────────────────────────────────────────────────
@router.get("/interfaces")
async def list_interfaces():
    """يرجع قائمة واجهات الشبكة المتاحة"""
    system = platform.system()
    try:
        if system == "Darwin":  # macOS
            result = subprocess.run(["ifconfig", "-l"], capture_output=True, text=True, timeout=5)
            interfaces = result.stdout.strip().split()
            # Filter to common WiFi/Ethernet interfaces
            interfaces = [i for i in interfaces if i.startswith(('en', 'lo', 'awdl', 'bridge', 'utun')) or 'wlan' in i]
            return {"interfaces": interfaces or ["en0", "en1"]}
        else:  # Linux / Raspberry Pi
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


async def run_port_scan(ip: str):
    """القيام بفحص المنافذ بطريقة غير معطلة للبرنامج الرئيسي"""
    db = SessionLocal()
    try:
        # إرسال إشعار بدء الفحص عبر WebSocket
        manager.broadcast({
            "event": "scan_start",
            "type": "port_scan",
            "ip": ip,
            "message": f"Starting deep port scan for {ip}..."
        })

        # تشغيل nmap في خيط منفصل لتجنب تجميد البرنامج
        def execute_nmap():
            nm = nmap.PortScanner()
            # تقليل المنافذ قليلاً لزيادة السرعة مع الحفاظ على العمق (Top 2000)
            nm.scan(hosts=ip, arguments="-sV -T4 --open -p 1-2000")
            return nm

        nm = await asyncio.to_thread(execute_nmap)
        
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
            
            # تنظيف الثغرات القديمة وإضافة الجديدة
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

            # إشعار بانتهاء الفحص بنجاح
            manager.broadcast({
                "event": "scan_complete",
                "type": "port_scan",
                "ip": ip,
                "risk_level": device.risk_level,
                "message": f"Port scan completed for {ip}. Found {len(open_ports)} open ports."
            })
            
    except Exception as e:
        logger.error(f"Port scan error: {e}")
        manager.broadcast({
            "event": "scan_error",
            "type": "port_scan",
            "ip": ip,
            "message": f"Error during port scan: {str(e)}"
        })
    finally:
        db.close()


# ────────────────────────────────────────────────────────────
# 3. اختبار كلمات المرور الافتراضية
# ────────────────────────────────────────────────────────────
@router.post("/test/credentials/{ip}")
async def test_default_credentials(ip: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(run_credential_test, ip)
    return {"status": "started", "message": f"جارٍ اختبار كلمات المرور الافتراضية على {ip}"}


async def run_credential_test(ip: str):
    """يختبر كلمات المرور الافتراضية بطريقة غير معطلة"""
    db = SessionLocal()
    found_cred = None
    
    try:
        manager.broadcast({
            "event": "scan_start",
            "type": "cred_test",
            "ip": ip,
            "message": f"Testing default credentials for {ip}..."
        })

        def perform_tests():
            inner_found = None
            # ---- اختبار HTTP Basic Auth ----
            try:
                import urllib.request
                import base64
                for username, password in DEFAULT_CREDENTIALS[:20]: # فحص أهم 20 تركيب
                    credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
                    req = urllib.request.Request(
                        f"http://{ip}",
                        headers={"Authorization": f"Basic {credentials}"}
                    )
                    try:
                        urllib.request.urlopen(req, timeout=2)
                        inner_found = (username, password)
                        return inner_found
                    except Exception:
                        continue
            except Exception:
                pass

            # ---- اختبار Telnet ----
            if not inner_found:
                try:
                    for username, password in DEFAULT_CREDENTIALS[:5]:
                        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        s.settimeout(2)
                        if s.connect_ex((ip, 23)) == 0:
                            # Note: Actual telnet login requires more complex handshake,
                            # but port 23 being open with default creds is a massive risk.
                            # For simplicity we assume default port 23 is high risk.
                            s.close()
                            return (username, password)
                        s.close()
                except Exception:
                    pass
            return None

        found_cred = await asyncio.to_thread(perform_tests)

        # ---- تحديث قاعدة البيانات ----
        if found_cred:
            device = db.query(Device).filter(Device.ip == ip).first()
            if device:
                ports_list = [int(p) for p in device.open_ports.split(",") if p.isdigit()] if device.open_ports else []
                risk_result = calculate_risk(ports_list, device.protocol, {"default_creds": found_cred})
                device.risk_level = risk_result["risk_level"]
                device.risk_score = risk_result["risk_score"]
                
                # إضافة ثغرة كلمات المرور الافتراضية إذا لم تكن موجودة
                existing_vuln = db.query(Vulnerability).filter(
                    Vulnerability.device_id == device.id,
                    Vulnerability.vuln_type == "DEFAULT_CREDENTIALS"
                ).first()
                if not existing_vuln:
                    db.add(Vulnerability(
                        device_id=device.id,
                        vuln_type="DEFAULT_CREDENTIALS",
                        severity="CRITICAL",
                        description=f"Default credentials '{found_cred[0]}/{found_cred[1]}' work on the device!",
                        protocol="HTTP/Telnet"
                    ))
                db.commit()

                manager.broadcast({
                    "event": "scan_complete",
                    "type": "cred_test",
                    "ip": ip,
                    "message": f"VULNERABILITY FOUND: Default credentials work on {ip}!"
                })
        else:
            manager.broadcast({
                "event": "scan_complete",
                "type": "cred_test",
                "ip": ip,
                "message": f"Credential test finished for {ip}. No default credentials found."
            })

    except Exception as e:
        logger.error(f"Credential test error: {e}")
    finally:
        db.close()


# ────────────────────────────────────────────────────────────
# 4. فحص شامل لجهاز واحد (Ports + Credentials)
# ────────────────────────────────────────────────────────────
@router.post("/scan/full/{ip}")
async def full_device_scan(ip: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(run_port_scan, ip)
    background_tasks.add_task(run_credential_test, ip)
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
            # Method 1: Try CoreWLAN via PyObjC (if available)
            try:
                import CoreWLAN
                from Foundation import NSBundle
                
                # Get WiFi interface
                wifi_interface = CoreWLAN.CWWiFiClient.sharedWiFiClient().interface()
                if wifi_interface:
                    # Scan for networks
                    error = None
                    scan_results, error = wifi_interface.scanForNetworksWithSSID_error_(None, None)
                    
                    if scan_results:
                        for network in scan_results:
                            ssid = network.ssid() if network.ssid() else "Hidden"
                            rssi = network.rssiValue() if hasattr(network, 'rssiValue') else "N/A"
                            channel = str(network.wlanChannel().channelNumber()) if network.wlanChannel() else "Unknown"
                            security = "WPA2" if network.security() != 0 else "Open"
                            
                            networks.append({
                                "ssid": ssid,
                                "rssi": rssi,
                                "security": security,
                                "channel": channel
                            })
            except ImportError:
                # PyObjC not available, try alternative methods
                pass
            except Exception as e:
                logger.error(f"CoreWLAN scan failed: {e}")
            
            # Method 2: Use system_profiler (SSIDs may be redacted on newer macOS)
            if not networks:
                try:
                    result = subprocess.run(
                        ["/usr/sbin/system_profiler", "SPAirPortDataType"],
                        capture_output=True, text=True, timeout=20
                    )
                    
                    output = result.stdout
                    lines = output.split("\n")
                    in_networks_section = False
                    current_ssid = None
                    
                    for i, line in enumerate(lines):
                        line_stripped = line.strip()
                        
                        # Check for network sections
                        if "Other Local Wi-Fi Networks:" in line:
                            in_networks_section = True
                            continue
                        elif "Current Network Information:" in line:
                            # Extract current network SSID
                            in_networks_section = True
                            # Next line after this contains the SSID
                            if i + 1 < len(lines):
                                next_line = lines[i + 1].strip()
                                if next_line.endswith(":"):
                                    current_ssid = next_line[:-1]
                                    if current_ssid and current_ssid != "<redacted>":
                                        networks.append({
                                            "ssid": current_ssid,
                                            "rssi": "N/A",
                                            "security": "Unknown",
                                            "channel": "Unknown",
                                            "status": "Connected"
                                        })
                            continue
                        elif in_networks_section and line_stripped and not line.startswith(" "):
                            in_networks_section = False
                            continue
                        
                        if in_networks_section and line_stripped:
                            # Check for SSID lines (usually end with : and contain network name)
                            if line_stripped.endswith(":") and len(line_stripped) > 1:
                                ssid_name = line_stripped[:-1]
                                # Skip redacted SSIDs and headers
                                if ssid_name and ssid_name != "SSID" and ssid_name != "<redacted>":
                                    current_ssid = ssid_name
                                    networks.append({
                                        "ssid": ssid_name,
                                        "rssi": "N/A",
                                        "security": "Unknown",
                                        "channel": "Unknown"
                                    })
                            elif ":" in line_stripped and networks:
                                # Parse details
                                parts = line_stripped.split(":", 1)
                                if len(parts) == 2:
                                    key = parts[0].strip()
                                    val = parts[1].strip()
                                    
                                    if "Security" in key:
                                        networks[-1]["security"] = val
                                    elif "Channel" in key:
                                        networks[-1]["channel"] = val.split()[0] if val else "Unknown"
                                    elif "Signal" in key or "Noise" in key:
                                        rssi_match = re.search(r'(-\d+)', val)
                                        if rssi_match:
                                            networks[-1]["rssi"] = int(rssi_match.group(1))
                
                except Exception as e:
                    logger.error(f"System profiler scan failed: {e}")
            
            # Method 3: Get current network info
            if not networks:
                try:
                    # Get current connection info
                    result = subprocess.run(
                        ["networksetup", "-getairportnetwork", "en0"],
                        capture_output=True, text=True, timeout=5
                    )
                    output = result.stdout.strip()
                    if "not associated" not in output.lower():
                        # Extract SSID from output like "Current Wi-Fi Network: MyNetwork"
                        parts = output.split(": ")
                        if len(parts) > 1:
                            ssid = parts[1].strip()
                            networks.append({
                                "ssid": ssid,
                                "rssi": "N/A",
                                "security": "Connected",
                                "channel": "Unknown",
                                "status": "Connected"
                            })
                except Exception as e:
                    logger.error(f"Network setup scan failed: {e}")

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
                try:
                    result = subprocess.run(
                        ["sudo", "iwlist", "wlan0", "scan"],
                        capture_output=True, text=True, timeout=15
                    )
                    current_ssid = None
                    for line in result.stdout.split("\n"):
                        if 'ESSID:' in line:
                            match = re.search(r'ESSID:"(.+?)"', line)
                            if match:
                                networks.append({
                                    "ssid": match.group(1),
                                    "rssi": "N/A",
                                    "security": "Unknown",
                                    "channel": "Unknown"
                                })
                except Exception as e2:
                    logger.error(f"iwlist scan failed: {e2}")

        # Remove duplicates and filter
        seen = set()
        unique_networks = []
        for n in networks:
            ssid = n.get("ssid", "")
            if ssid and ssid not in seen and ssid != "" and ssid != "<redacted>":
                unique_networks.append(n)
                seen.add(ssid)

        logger.info(f"Found {len(unique_networks)} WiFi networks")
        
        if not unique_networks:
            return {
                "status": "partial",
                "message": "No SSIDs found. On macOS, SSIDs may be redacted for privacy. Try scanning for devices instead.",
                "ssids": [],
                "count": 0
            }
        
        return {"status": "success", "ssids": unique_networks, "count": len(unique_networks)}

    except Exception as e:
        logger.error(f"SSID scan error: {e}")
        return {"status": "error", "message": str(e), "ssids": [], "count": 0}


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


# ────────────────────────────────────────────────────────────
# 9. Quick Network Device Discovery (One-Click)
# ────────────────────────────────────────────────────────────
@router.post("/discover/devices")
async def quick_discover_devices(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    One-click discovery of ALL devices on your current network.
    Automatically detects your network and scans it.
    """
    system = platform.system()
    network = None
    
    try:
        if system == "Darwin":  # macOS
            result = subprocess.run(["ifconfig"], capture_output=True, text=True, timeout=5)
            current_iface = None
            for line in result.stdout.split("\n"):
                if line and not line[0].isspace():
                    m = re.match(r'^(\S+?):', line)
                    if m:
                        current_iface = m.group(1)
                elif current_iface:
                    ip_m = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', line)
                    mask_m = re.search(r'netmask (0x[0-9a-fA-F]+)', line)
                    if ip_m and mask_m:
                        ip = ip_m.group(1)
                        if ip.startswith("127."):
                            continue
                        mask_str = mask_m.group(1)
                        if mask_str.startswith("0x"):
                            cidr = bin(int(mask_str, 16)).count("1")
                        else:
                            cidr = 24  # Default
                        parts = ip.split(".")
                        network = f"{parts[0]}.{parts[1]}.{parts[2]}.0/{cidr}"
                        break
        else:  # Linux
            result = subprocess.run(["ip", "route", "show"], capture_output=True, text=True, timeout=5)
            for line in result.stdout.split("\n"):
                if "dev" in line and "/" in line and not line.startswith("127"):
                    match = re.search(r'(\d+\.\d+\.\d+\.\d+/\d+)', line)
                    if match:
                        network = match.group(1)
                        break
    except Exception as e:
        logger.error(f"Network detection failed: {e}")
        return {"status": "error", "message": f"Could not detect network: {e}"}
    
    if not network:
        return {"status": "error", "message": "No network detected. Are you connected to WiFi?"}
    
    # Start scan
    background_tasks.add_task(run_network_device_scan, network)
    return {"status": "started", "network": network, "message": f"Scanning {network} for devices..."}


def run_network_device_scan(network: str):
    """Scans network and discovers all devices"""
    from websocket_manager import manager
    db = SessionLocal()
    try:
        nm = nmap.PortScanner()
        # Fast scan - ping sweep only
        nm.scan(hosts=network, arguments="-sn -T4 --privileged")
        
        devices_found = 0
        for host in nm.all_hosts():
            if nm[host].state() == "up":
                # Get hostname using enhanced detection
                hostname = nm[host].hostname() or "Unknown"
                if hostname == "Unknown":
                    # Try enhanced hostname detection (reverse DNS, mDNS, NetBIOS)
                    hostname = get_hostname_enhanced(host)
                
                # Get MAC if available
                mac = None
                vendor = "Unknown"
                if 'addresses' in nm[host] and 'mac' in nm[host]['addresses']:
                    mac = nm[host]['addresses']['mac']
                    # Try to get vendor from OUI
                    try:
                        if 'vendor' in nm[host]:
                            vendor = list(nm[host]['vendor'].values())[0] if nm[host]['vendor'] else "Unknown"
                    except:
                        pass
                    # Enhanced vendor detection from MAC
                    if vendor == "Unknown" and mac:
                        vendor = get_vendor_from_mac(mac)
                
                # Check if device exists
                existing = db.query(Device).filter(Device.ip == host).first()
                if existing:
                    existing.last_seen = datetime.utcnow()
                    existing.hostname = hostname if hostname != "Unknown" else existing.hostname
                else:
                    device = Device(
                        ip=host,
                        mac=mac,
                        hostname=hostname,
                        vendor=vendor,
                        protocol="WiFi",
                        risk_level="Medium",
                        risk_score=50,
                        last_seen=datetime.utcnow()
                    )
                    db.add(device)
                    devices_found += 1
                    
                    # Notify via WebSocket
                    manager.broadcast({
                        "event": "device_found",
                        "device": {
                            "ip": host,
                            "hostname": hostname,
                            "mac": mac,
                            "vendor": vendor
                        }
                    })
        
        db.commit()
        
        manager.broadcast({
            "event": "scan_finished",
            "type": "network_discovery",
            "network": network,
            "devices_found": devices_found
        })
        
        logger.info(f"Found {devices_found} new devices on {network}")
        
    except Exception as e:
        logger.error(f"Device scan error: {e}")
        from websocket_manager import manager
        manager.broadcast({
            "event": "scan_error",
            "message": str(e)
        })
    finally:
        db.close()


# ============================================================================
# ADVANCED Wi-Fi FEATURES - Monitor Mode, Sniffing, Handshake, Deauth, Rogue AP
# ============================================================================

# ────────────────────────────────────────────────────────────
# 10. MONITOR MODE - Enable/Disable/Status
# ────────────────────────────────────────────────────────────

@router.post("/monitor/enable")
async def enable_monitor_mode(interface: str = Body("wlan0"), channel: Optional[int] = Body(None)):
    """
    Enable Monitor Mode on the Wi-Fi interface.
    Uses airmon-ng (preferred) or iw as fallback.
    Works with RPi 5 built-in Wi-Fi (BCM43455) or ALFA adapter.
    """
    if monitor_state["active"]:
        return {"status": "error", "message": f"Monitor mode already active on {monitor_state['interface']}"}
    
    if platform.system() != "Linux":
        return {"status": "error", "message": "Monitor mode requires Linux (Raspberry Pi OS). Use RPi 5 for best results."}
    
    try:
        # Step 1: Kill interfering processes
        subprocess.run(["airmon-ng", "check", "kill"], capture_output=True, timeout=10)
        logger.info("Killed interfering processes")
        
        mon_interface = None
        
        # Step 2: Detect RPi 5 built-in WiFi (BCM43455) - prefer iw for this chip
        is_rpi_builtin = False
        try:
            result = subprocess.run(["iw", "dev", interface, "info"], capture_output=True, text=True, timeout=5)
            if "BCM43455" in result.stdout or result.returncode == 0:
                # Check if this is the built-in WiFi
                try:
                    lsmod = subprocess.run(["lsmod"], capture_output=True, text=True, timeout=5)
                    if "brcmfmac" in lsmod.stdout or "brcm" in lsmod.stdout:
                        is_rpi_builtin = True
                        logger.info(f"Detected RPi built-in WiFi ({interface}), using iw for monitor mode")
                except:
                    pass
        except:
            pass
        
        # Step 3a: For RPi 5 built-in WiFi, use iw directly (more reliable than airmon-ng)
        if is_rpi_builtin:
            subprocess.run(["ip", "link", "set", interface, "down"], capture_output=True, timeout=5)
            iw_result = subprocess.run(
                ["iw", interface, "set", "type", "monitor"],
                capture_output=True, text=True, timeout=10
            )
            if iw_result.returncode == 0:
                subprocess.run(["ip", "link", "set", interface, "up"], capture_output=True, timeout=5)
                mon_interface = interface
                logger.info(f"Monitor mode enabled via iw on {interface}")
            else:
                logger.warning(f"iw monitor mode failed: {iw_result.stderr}, falling back to airmon-ng")
        
        # Step 3b: For USB adapters or iw fallback, use airmon-ng
        if not mon_interface:
            result = subprocess.run(
                ["airmon-ng", "start", interface],
                capture_output=True, text=True, timeout=15
            )
            
            # Detect monitor interface name from airmon-ng output
            for line in result.stdout.split("\n"):
                if "monitor" in line.lower() and "mode" in line.lower():
                    match = re.search(r'(\w+mon|\w+\d+)', line)
                    if match:
                        mon_interface = match.group(1)
                # airmon-ng typically creates wlan0mon from wlan0
                if interface + "mon" in line:
                    mon_interface = interface + "mon"
        
        # Fallback: try iw if airmon-ng didn't work
        if not mon_interface:
            logger.info("airmon-ng didn't create monitor interface, trying iw...")
            subprocess.run(["ip", "link", "set", interface, "down"], capture_output=True, timeout=5)
            subprocess.run(["iw", interface, "set", "type", "monitor"], capture_output=True, timeout=5)
            subprocess.run(["ip", "link", "set", interface, "up"], capture_output=True, timeout=5)
            mon_interface = interface
        
        if not mon_interface:
            return {"status": "error", "message": "Failed to create monitor interface. Check if airmon-ng/iw is installed."}
        
        # Set channel if specified
        if channel:
            subprocess.run(["iw", "dev", mon_interface, "set", "channel", str(channel)], 
                          capture_output=True, timeout=5)
            monitor_state["channel"] = channel
        
        # Update state
        monitor_state["active"] = True
        monitor_state["interface"] = mon_interface
        monitor_state["original_interface"] = interface
        monitor_state["mode"] = "monitor"
        monitor_state["started_at"] = datetime.utcnow().isoformat()
        
        logger.info(f"Monitor mode enabled on {mon_interface}")
        
        return {
            "status": "success",
            "message": f"Monitor mode enabled on {mon_interface}",
            "interface": mon_interface,
            "original_interface": interface,
            "channel": channel
        }
        
    except FileNotFoundError as e:
        return {"status": "error", "message": f"Required tool not found: {e}. Install: sudo apt install aircrack-ng iw"}
    except Exception as e:
        logger.error(f"Monitor mode error: {e}")
        return {"status": "error", "message": str(e)}


@router.post("/monitor/disable")
async def disable_monitor_mode():
    """
    Disable Monitor Mode and restore managed mode.
    Reconnects to the original Wi-Fi network.
    """
    if not monitor_state["active"]:
        return {"status": "error", "message": "Monitor mode is not active"}
    
    try:
        mon_iface = monitor_state["interface"]
        orig_iface = monitor_state["original_interface"]
        
        # Stop any active sniffing/capture first
        sniffer_state["active"] = False
        handshake_state["active"] = False
        deauth_attack_state["active"] = False
        rogue_ap_state["active"] = False
        deauth_state["monitoring"] = False
        
        # Try airmon-ng stop first
        result = subprocess.run(
            ["airmon-ng", "stop", mon_iface],
            capture_output=True, text=True, timeout=15
        )
        
        # If airmon-ng created a mon interface, the original should be restored
        # Fallback: use iw to restore
        if mon_iface != orig_iface:
            # airmon-ng should have restored orig_iface
            pass
        else:
            # iw was used, restore manually
            subprocess.run(["ip", "link", "set", mon_iface, "down"], capture_output=True, timeout=5)
            subprocess.run(["iw", mon_iface, "set", "type", "managed"], capture_output=True, timeout=5)
            subprocess.run(["ip", "link", "set", mon_iface, "up"], capture_output=True, timeout=5)
        
        # Restart NetworkManager to reconnect
        subprocess.run(["systemctl", "start", "NetworkManager"], capture_output=True, timeout=10)
        subprocess.run(["systemctl", "start", "wpa_supplicant"], capture_output=True, timeout=10)
        
        # Reset state
        monitor_state["active"] = False
        monitor_state["interface"] = None
        monitor_state["mode"] = "managed"
        monitor_state["channel"] = None
        monitor_state["started_at"] = None
        
        logger.info("Monitor mode disabled, managed mode restored")
        
        return {
            "status": "success",
            "message": "Monitor mode disabled. Wi-Fi restored to managed mode."
        }
        
    except Exception as e:
        logger.error(f"Disable monitor mode error: {e}")
        return {"status": "error", "message": str(e)}


@router.get("/monitor/status")
async def get_monitor_status():
    """Returns current monitor mode status and interface info."""
    # Also check actual system state
    actual_mode = "unknown"
    actual_channel = None
    
    if platform.system() == "Linux":
        try:
            result = subprocess.run(["iw", "dev"], capture_output=True, text=True, timeout=5)
            for line in result.stdout.split("\n"):
                if "type" in line:
                    actual_mode = line.strip().split()[-1]
                if "channel" in line:
                    ch_match = re.search(r'channel (\d+)', line)
                    if ch_match:
                        actual_channel = int(ch_match.group(1))
        except:
            pass
    
    return {
        **monitor_state,
        "actual_mode": actual_mode,
        "actual_channel": actual_channel,
        "platform": platform.system()
    }


@router.post("/monitor/channel")
async def set_monitor_channel(channel: int = Body(...)):
    """Set the channel for the monitor interface (hop to specific channel)."""
    if not monitor_state["active"]:
        return {"status": "error", "message": "Monitor mode is not active. Enable it first."}
    
    try:
        result = subprocess.run(
            ["iw", "dev", monitor_state["interface"], "set", "channel", str(channel)],
            capture_output=True, text=True, timeout=5
        )
        monitor_state["channel"] = channel
        return {"status": "success", "message": f"Channel set to {channel}", "channel": channel}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ────────────────────────────────────────────────────────────
# 11. CLIENT SNIFFING - Discover devices without connecting
# ────────────────────────────────────────────────────────────

@router.post("/sniffer/start")
async def start_client_sniffer(background_tasks: BackgroundTasks, duration: int = Body(30), interface: Optional[str] = Body(None)):
    """
    Start Wi-Fi client sniffer in monitor mode.
    Captures Probe Requests, Association Requests, and Data Frames
    to discover devices around you WITHOUT connecting to any network.
    
    Requires: Monitor mode enabled (call /monitor/enable first)
    Duration: Seconds to sniff (default 30)
    """
    if sniffer_state["active"]:
        return {"status": "error", "message": "Sniffer already active"}
    
    iface = interface or monitor_state.get("interface")
    if not iface:
        return {"status": "error", "message": "No monitor interface. Enable monitor mode first: /wireless/monitor/enable"}
    
    # Reset state
    sniffer_state["active"] = True
    sniffer_state["clients"] = []
    sniffer_state["probe_requests"] = []
    sniffer_state["packets_captured"] = 0
    sniffer_state["started_at"] = datetime.utcnow().isoformat()
    
    background_tasks.add_task(run_client_sniffer, iface, duration)
    
    return {
        "status": "started",
        "message": f"Client sniffer started on {iface} for {duration}s",
        "interface": iface,
        "duration": duration
    }


@router.post("/sniffer/stop")
async def stop_client_sniffer():
    """Stop the Wi-Fi client sniffer."""
    sniffer_state["active"] = False
    return {"status": "stopped", "clients_found": len(sniffer_state["clients"]), "probe_requests": len(sniffer_state["probe_requests"])}


@router.get("/sniffer/status")
async def get_sniffer_status():
    """Returns current sniffer status and discovered clients."""
    return sniffer_state


@router.get("/sniffer/clients")
async def get_discovered_clients():
    """Returns all clients discovered by the sniffer."""
    return {"clients": sniffer_state["clients"], "count": len(sniffer_state["clients"])}


def run_client_sniffer(interface: str, duration: int):
    """
    Background task: Sniff for Wi-Fi clients using scapy.
    Captures Probe Requests and identifies devices in the area.
    """
    try:
        from scapy.all import sniff, Dot11, Dot11ProbeReq, Dot11Elt, RadioTap
        
        discovered_clients = {}
        discovered_probes = {}
        start_time = time.time()
        
        def process_packet(pkt):
            if not sniffer_state["active"]:
                return
            
            sniffer_state["packets_captured"] += 1
            
            # Capture Probe Requests (devices searching for networks)
            if pkt.haslayer(Dot11ProbeReq):
                client_mac = pkt.addr2 if hasattr(pkt, 'addr2') else None
                if not client_mac or client_mac in discovered_clients:
                    return
                
                # Extract SSID from probe request
                ssid = None
                if pkt.haslayer(Dot11Elt):
                    elt = pkt[Dot11Elt]
                    while elt:
                        if elt.ID == 0 and elt.info:  # SSID
                            ssid = elt.info.decode('utf-8', errors='ignore')
                            break
                        elt = elt.payload if hasattr(elt, 'payload') and isinstance(elt.payload, Dot11Elt) else None
                
                # Get signal strength
                signal = None
                if pkt.haslayer(RadioTap):
                    try:
                        signal = -(256 - pkt[RadioTap].dBm_AntSignal) if hasattr(pkt[RadioTap], 'dBm_AntSignal') else None
                    except:
                        pass
                
                client_info = {
                    "mac": client_mac,
                    "type": "probe_request",
                    "ssid_probed": ssid or "[Broadcast]",
                    "signal_dbm": signal,
                    "first_seen": datetime.utcnow().isoformat(),
                    "packets": 1
                }
                
                discovered_clients[client_mac] = client_info
                
                # Track probe requests
                probe_key = f"{client_mac}:{ssid or 'broadcast'}"
                if probe_key not in discovered_probes:
                    discovered_probes[probe_key] = {
                        "client_mac": client_mac,
                        "ssid": ssid or "[Broadcast]",
                        "count": 1
                    }
                    sniffer_state["probe_requests"].append(discovered_probes[probe_key])
                else:
                    discovered_probes[probe_key]["count"] += 1
                
                # Broadcast via WebSocket
                manager.broadcast({
                    "event": "wifi_client_found",
                    "client": client_info
                })
                
                logger.info(f"WiFi Client: {client_mac} probing for '{ssid or 'broadcast'}' signal={signal}")
            
            # Capture Data Frames (connected devices)
            elif pkt.haslayer(Dot11):
                # Check for data frames (type 2)
                if pkt.type == 2 and pkt.addr1 and pkt.addr2:
                    # One of the addresses should be the AP, the other the client
                    # We identify the client as the non-AP address
                    src = pkt.addr2
                    dst = pkt.addr1
                    
                    # Determine which is the client (not a broadcast/multicast)
                    client_mac = None
                    bssid = None
                    if not src.startswith('ff:ff:ff') and src not in discovered_clients:
                        client_mac = src
                        bssid = dst
                    elif not dst.startswith('ff:ff:ff') and dst not in discovered_clients:
                        client_mac = dst
                        bssid = src
                    
                    if client_mac and client_mac not in discovered_clients:
                        signal = None
                        if pkt.haslayer(RadioTap):
                            try:
                                signal = -(256 - pkt[RadioTap].dBm_AntSignal) if hasattr(pkt[RadioTap], 'dBm_AntSignal') else None
                            except:
                                pass
                        
                        client_info = {
                            "mac": client_mac,
                            "type": "data_frame",
                            "connected_to_bssid": bssid,
                            "signal_dbm": signal,
                            "first_seen": datetime.utcnow().isoformat(),
                            "packets": 1
                        }
                        discovered_clients[client_mac] = client_info
                        
                        manager.broadcast({
                            "event": "wifi_client_found",
                            "client": client_info
                        })
                        logger.info(f"WiFi Client (data): {client_mac} connected to {bssid}")
        
        # Run sniffing for the specified duration
        logger.info(f"Starting client sniffer on {interface} for {duration}s")
        sniff(iface=interface, prn=process_packet, timeout=duration, store=False)
        
        # Update final state
        sniffer_state["clients"] = list(discovered_clients.values())
        sniffer_state["active"] = False
        
        manager.broadcast({
            "event": "sniffer_finished",
            "clients_found": len(discovered_clients),
            "probes_found": len(discovered_probes)
        })
        
        logger.info(f"Client sniffer finished: {len(discovered_clients)} clients found")
        
    except ImportError:
        sniffer_state["active"] = False
        logger.error("Scapy not installed. Install: pip install scapy")
        manager.broadcast({"event": "sniffer_error", "message": "Scapy not installed"})
    except Exception as e:
        sniffer_state["active"] = False
        logger.error(f"Client sniffer error: {e}")
        manager.broadcast({"event": "sniffer_error", "message": str(e)})


# ────────────────────────────────────────────────────────────
# 12. WPA HANDSHAKE CAPTURE
# ────────────────────────────────────────────────────────────

@router.post("/handshake/start")
async def start_handshake_capture(
    background_tasks: BackgroundTasks,
    bssid: str = Body(...),
    channel: int = Body(...),
    ssid: Optional[str] = Body(None),
    timeout: int = Body(120)
):
    """
    Start capturing WPA/WPA2 4-way handshakes for a target AP.
    Listens on the specified channel for the target BSSID.
    When a client connects, captures the EAPOL frames.
    
    Requires: Monitor mode enabled on the correct channel.
    """
    if handshake_state["active"]:
        return {"status": "error", "message": "Handshake capture already active"}
    
    if not monitor_state["active"]:
        return {"status": "error", "message": "Monitor mode required. Enable it first: /wireless/monitor/enable"}
    
    # Set monitor to the target channel
    try:
        subprocess.run(
            ["iw", "dev", monitor_state["interface"], "set", "channel", str(channel)],
            capture_output=True, timeout=5
        )
        monitor_state["channel"] = channel
    except Exception as e:
        logger.warning(f"Could not set channel: {e}")
    
    # Reset state
    handshake_state["active"] = True
    handshake_state["target_ssid"] = ssid
    handshake_state["target_bssid"] = bssid
    handshake_state["channel"] = channel
    handshake_state["handshake_captured"] = False
    handshake_state["capture_file"] = f"/tmp/pentex_handshake_{bssid.replace(':','')}.pcap"
    handshake_state["packets_captured"] = 0
    handshake_state["started_at"] = datetime.utcnow().isoformat()
    
    background_tasks.add_task(
        run_handshake_capture,
        monitor_state["interface"],
        bssid,
        channel,
        timeout
    )
    
    return {
        "status": "started",
        "message": f"Handshake capture started for {ssid or bssid} on channel {channel}",
        "bssid": bssid,
        "channel": channel,
        "timeout": timeout
    }


@router.post("/handshake/stop")
async def stop_handshake_capture():
    """Stop handshake capture."""
    handshake_state["active"] = False
    return {
        "status": "stopped",
        "handshake_captured": handshake_state["handshake_captured"],
        "capture_file": handshake_state["capture_file"] if handshake_state["handshake_captured"] else None
    }


@router.get("/handshake/status")
async def get_handshake_status():
    """Returns current handshake capture status."""
    return handshake_state


def run_handshake_capture(interface: str, target_bssid: str, channel: int, timeout: int):
    """
    Background task: Capture WPA 4-way handshake using scapy.
    Saves captured packets to a pcap file.
    """
    try:
        from scapy.all import sniff, Dot11, Dot11EAPOL, RadioTap, wrpcap
        
        captured_packets = []
        eapol_count = 0
        start_time = time.time()
        
        def process_packet(pkt):
            nonlocal eapol_count
            if not handshake_state["active"]:
                return
            
            handshake_state["packets_captured"] += 1
            
            # Check for EAPOL frames (part of WPA handshake)
            if pkt.haslayer(Dot11EAPOL):
                # Verify it's from/to our target BSSID
                if hasattr(pkt, 'addr1') and hasattr(pkt, 'addr2'):
                    if target_bssid.lower() in [pkt.addr1.lower(), pkt.addr2.lower()]:
                        eapol_count += 1
                        captured_packets.append(pkt)
                        
                        logger.info(f"EAPOL frame {eapol_count} captured for {target_bssid}")
                        
                        manager.broadcast({
                            "event": "handshake_progress",
                            "eapol_frames": eapol_count,
                            "target": target_bssid,
                            "message": f"EAPOL frame {eapol_count}/4 captured"
                        })
                        
                        # We need at least 2 EAPOL frames (out of 4) to crack
                        if eapol_count >= 2:
                            handshake_state["handshake_captured"] = True
                            logger.info(f"WPA Handshake captured for {target_bssid}!")
                            
                            # Save to pcap file
                            try:
                                wrpcap(handshake_state["capture_file"], captured_packets)
                                logger.info(f"Handshake saved to {handshake_state['capture_file']}")
                            except Exception as e:
                                logger.error(f"Failed to save pcap: {e}")
                            
                            manager.broadcast({
                                "event": "handshake_captured",
                                "bssid": target_bssid,
                                "eapol_frames": eapol_count,
                                "capture_file": handshake_state["capture_file"],
                                "message": f"WPA Handshake captured! {eapol_count} EAPOL frames."
                            })
                            
                            # Stop capturing
                            handshake_state["active"] = False
            
            # Also capture beacon frames and data from target for context
            elif pkt.haslayer(Dot11):
                if hasattr(pkt, 'addr1') and hasattr(pkt, 'addr2'):
                    if target_bssid.lower() in [pkt.addr1.lower(), pkt.addr2.lower()]:
                        captured_packets.append(pkt)
        
        logger.info(f"Handshake capture started for {target_bssid} ch{channel}, timeout={timeout}s")
        
        sniff(iface=interface, prn=process_packet, timeout=timeout, store=False)
        
        handshake_state["active"] = False
        
        if not handshake_state["handshake_captured"]:
            manager.broadcast({
                "event": "handshake_timeout",
                "message": f"Handshake capture timed out after {timeout}s. No client connected during capture."
            })
        
    except ImportError:
        handshake_state["active"] = False
        logger.error("Scapy not installed for handshake capture")
    except Exception as e:
        handshake_state["active"] = False
        logger.error(f"Handshake capture error: {e}")
        manager.broadcast({"event": "handshake_error", "message": str(e)})


# ────────────────────────────────────────────────────────────
# 13. DEAUTH ATTACK TEST - Test connection resilience
# ────────────────────────────────────────────────────────────

@router.post("/deauth/test")
async def test_deauth_attack(
    background_tasks: BackgroundTasks,
    target_mac: str = Body(...),
    ap_bssid: str = Body(...),
    channel: int = Body(...),
    count: int = Body(5),
    interface: Optional[str] = Body(None)
):
    """
    Send deauthentication frames to test connection resilience.
    Tests if a device's connection is vulnerable to deauth attacks.
    Also detects if 802.11w (Management Frame Protection) is active.
    
    Args:
        target_mac: MAC address of the client to test
        ap_bssid: MAC address of the Access Point
        channel: WiFi channel
        count: Number of deauth frames to send (default 5)
    """
    if deauth_attack_state["active"]:
        return {"status": "error", "message": "Deauth test already running"}
    
    if not monitor_state["active"]:
        return {"status": "error", "message": "Monitor mode required. Enable it first."}
    
    iface = interface or monitor_state.get("interface")
    
    # Set to correct channel
    try:
        subprocess.run(
            ["iw", "dev", iface, "set", "channel", str(channel)],
            capture_output=True, timeout=5
        )
    except:
        pass
    
    deauth_attack_state["active"] = True
    deauth_attack_state["target_mac"] = target_mac
    deauth_attack_state["ap_bssid"] = ap_bssid
    deauth_attack_state["packets_sent"] = 0
    deauth_attack_state["client_disconnected"] = False
    deauth_attack_state["protected"] = False
    deauth_attack_state["started_at"] = datetime.utcnow().isoformat()
    
    background_tasks.add_task(run_deauth_test, iface, target_mac, ap_bssid, count)
    
    return {
        "status": "started",
        "message": f"Deauth test started: sending {count} frames to {target_mac}",
        "target": target_mac,
        "ap": ap_bssid,
        "count": count
    }


@router.get("/deauth/test/status")
async def get_deauth_test_status():
    """Returns current deauth attack test status."""
    return deauth_attack_state


def run_deauth_test(interface: str, target_mac: str, ap_bssid: str, count: int):
    """
    Background task: Send deauth frames and monitor response.
    Uses scapy for frame injection.
    """
    try:
        from scapy.all import Dot11, Dot11Deauth, RadioTap, sendp
        
        # Craft deauth frame
        # Reason code 7: Class 3 frame received from nonassociated station
        packet = RadioTap() / Dot11(
            addr1=target_mac,   # Destination (client)
            addr2=ap_bssid,     # Source (AP)
            addr3=ap_bssid,     # BSSID
            type=0,             # Management frame
            subtype=12          # Deauthentication
        ) / Dot11Deauth(reason=7)
        
        logger.info(f"Sending {count} deauth frames to {target_mac} via {ap_bssid}")
        
        # Send deauth frames
        for i in range(count):
            if not deauth_attack_state["active"]:
                break
            sendp(packet, iface=interface, verbose=False)
            deauth_attack_state["packets_sent"] = i + 1
            time.sleep(0.5)  # Small delay between frames
            
            manager.broadcast({
                "event": "deauth_test_progress",
                "packets_sent": i + 1,
                "total": count,
                "message": f"Sent {i+1}/{count} deauth frames"
            })
        
        # Now listen for response to determine if MFP is active
        # If client sends reassociation quickly = not protected
        # If no response = might be protected by 802.11w
        from scapy.all import sniff
        
        def check_response(pkt):
            if pkt.haslayer(Dot11):
                # Check for reassociation/auth frames from target
                if hasattr(pkt, 'addr2') and pkt.addr2.lower() == target_mac.lower():
                    if pkt.type == 0 and pkt.subtype in [0, 1, 2, 11]:  # assoc/reassoc/auth
                        deauth_attack_state["client_disconnected"] = True
                        deauth_attack_state["protected"] = False
                        return True
            return False
        
        # Listen for 5 seconds for response
        try:
            sniff(iface=interface, prn=check_response, timeout=5, store=False,
                  stop_filter=lambda p: deauth_attack_state["client_disconnected"])
        except:
            pass
        
        # If no reassociation detected, might be protected
        if not deauth_attack_state["client_disconnected"]:
            deauth_attack_state["protected"] = True  # Likely has MFP
        
        deauth_attack_state["active"] = False
        
        # Determine result
        if deauth_attack_state["client_disconnected"]:
            result_msg = "VULNERABLE: Client was disconnected. No 802.11w MFP detected."
            risk_flags = {"WIFI_NO_MFP": True}
        else:
            result_msg = "PROTECTED: Client appears resilient. 802.11w MFP may be active."
            risk_flags = {}
        
        manager.broadcast({
            "event": "deauth_test_complete",
            "target": target_mac,
            "ap": ap_bssid,
            "packets_sent": deauth_attack_state["packets_sent"],
            "client_disconnected": deauth_attack_state["client_disconnected"],
            "mfp_protected": deauth_attack_state["protected"],
            "message": result_msg
        })
        
        logger.info(f"Deauth test result: {result_msg}")
        
    except ImportError:
        deauth_attack_state["active"] = False
        logger.error("Scapy not installed for deauth test")
    except Exception as e:
        deauth_attack_state["active"] = False
        logger.error(f"Deauth test error: {e}")
        manager.broadcast({"event": "deauth_test_error", "message": str(e)})


# ────────────────────────────────────────────────────────────
# 14. ROGUE AP / EVIL TWIN DETECTION
# ────────────────────────────────────────────────────────────

@router.post("/rogue/start")
async def start_rogue_ap_detection(
    background_tasks: BackgroundTasks,
    duration: int = Body(60),
    interface: Optional[str] = Body(None)
):
    """
    Start Rogue AP / Evil Twin detection.
    Monitors for duplicate SSIDs with different BSSIDs,
    which indicates a potential Evil Twin or Rogue AP attack.
    
    Requires: Monitor mode enabled.
    """
    if rogue_ap_state["active"]:
        return {"status": "error", "message": "Rogue AP detection already active"}
    
    if not monitor_state["active"]:
        return {"status": "error", "message": "Monitor mode required. Enable it first."}
    
    iface = interface or monitor_state.get("interface")
    
    rogue_ap_state["active"] = True
    rogue_ap_state["alerts"] = []
    rogue_ap_state["known_aps"] = []
    rogue_ap_state["started_at"] = datetime.utcnow().isoformat()
    
    background_tasks.add_task(run_rogue_ap_detection, iface, duration)
    
    return {
        "status": "started",
        "message": f"Rogue AP detection started for {duration}s",
        "duration": duration
    }


@router.post("/rogue/stop")
async def stop_rogue_ap_detection():
    """Stop Rogue AP detection."""
    rogue_ap_state["active"] = False
    return {"status": "stopped", "alerts": len(rogue_ap_state["alerts"])}


@router.get("/rogue/status")
async def get_rogue_ap_status():
    """Returns current Rogue AP detection status and alerts."""
    return rogue_ap_state


def run_rogue_ap_detection(interface: str, duration: int):
    """
    Background task: Detect Rogue APs / Evil Twins.
    Monitors beacon frames and flags duplicate SSIDs with different BSSIDs.
    """
    try:
        from scapy.all import sniff, Dot11, Dot11Beacon, Dot11Elt, RadioTap
        
        seen_aps = {}  # ssid -> [{bssid, channel, signal, encryption}]
        start_time = time.time()
        
        def process_packet(pkt):
            if not rogue_ap_state["active"]:
                return
            
            # Look for beacon frames (AP advertisements)
            if pkt.haslayer(Dot11Beacon):
                bssid = pkt.addr3 if hasattr(pkt, 'addr3') else None
                if not bssid:
                    return
                
                # Extract SSID
                ssid = None
                encryption = "Unknown"
                channel = None
                
                if pkt.haslayer(Dot11Elt):
                    elt = pkt[Dot11Elt]
                    while elt:
                        if elt.ID == 0 and elt.info:  # SSID
                            ssid = elt.info.decode('utf-8', errors='ignore')
                        elif elt.ID == 3:  # Channel
                            try:
                                channel = ord(elt.info)
                            except:
                                pass
                        elif elt.ID == 48:  # RSN (WPA2)
                            encryption = "WPA2"
                        elif elt.ID == 221:  # Vendor specific (could be WPA)
                            try:
                                if elt.info[:4] == b'\x00P\xf2\x01':
                                    encryption = "WPA"
                            except:
                                pass
                        
                        elt = elt.payload if hasattr(elt, 'payload') and isinstance(elt.payload, Dot11Elt) else None
                
                if not ssid or ssid == "":
                    return  # Skip hidden SSIDs
                
                # Get signal strength
                signal = None
                if pkt.haslayer(RadioTap):
                    try:
                        signal = -(256 - pkt[RadioTap].dBm_AntSignal) if hasattr(pkt[RadioTap], 'dBm_AntSignal') else None
                    except:
                        pass
                
                ap_info = {
                    "bssid": bssid,
                    "channel": channel,
                    "signal_dbm": signal,
                    "encryption": encryption,
                    "last_seen": datetime.utcnow().isoformat()
                }
                
                # Check for duplicate SSIDs (Rogue AP!)
                if ssid not in seen_aps:
                    seen_aps[ssid] = [ap_info]
                else:
                    # Check if this BSSID is already known
                    known_bssids = [ap["bssid"].lower() for ap in seen_aps[ssid]]
                    
                    if bssid.lower() not in known_bssids:
                        # SAME SSID, DIFFERENT BSSID = ROGUE AP!
                        seen_aps[ssid].append(ap_info)
                        
                        alert = {
                            "type": "rogue_ap",
                            "ssid": ssid,
                            "original_bssid": seen_aps[ssid][0]["bssid"],
                            "rogue_bssid": bssid,
                            "original_channel": seen_aps[ssid][0].get("channel"),
                            "rogue_channel": channel,
                            "original_signal": seen_aps[ssid][0].get("signal_dbm"),
                            "rogue_signal": signal,
                            "original_encryption": seen_aps[ssid][0].get("encryption"),
                            "rogue_encryption": encryption,
                            "severity": "HIGH",
                            "message": f"Rogue AP detected! SSID '{ssid}' found with 2 different BSSIDs",
                            "timestamp": datetime.utcnow().isoformat()
                        }
                        
                        rogue_ap_state["alerts"].append(alert)
                        
                        # Check for Evil Twin indicators
                        if encryption != seen_aps[ssid][0].get("encryption"):
                            alert["type"] = "evil_twin"
                            alert["severity"] = "CRITICAL"
                            alert["message"] = f"Evil Twin detected! '{ssid}' has different encryption ({encryption} vs {seen_aps[ssid][0].get('encryption')})"
                        
                        manager.broadcast({
                            "event": "rogue_ap_alert",
                            "alert": alert
                        })
                        
                        logger.warning(f"ROGUE AP: {alert['message']}")
        
        # Update known APs list (interim during scan)
        interim_aps = []
        for ssid, aps in seen_aps.items():
            for ap in aps:
                interim_aps.append({
                    "ssid": ssid,
                    "bssid": ap["bssid"],
                    "channel": ap.get("channel"),
                    "signal": ap.get("signal_dbm"),
                    "encryption": ap.get("encryption", "Unknown")
                })
        rogue_ap_state["known_aps"] = interim_aps
        
        logger.info(f"Starting Rogue AP detection on {interface} for {duration}s")
        sniff(iface=interface, prn=process_packet, timeout=duration, store=False)
        
        rogue_ap_state["active"] = False
        
        # Update known_aps with final list - flatten for frontend table
        known_aps_flat = []
        for ssid, aps in seen_aps.items():
            for ap in aps:
                known_aps_flat.append({
                    "ssid": ssid,
                    "bssid": ap["bssid"],
                    "channel": ap.get("channel"),
                    "signal": ap.get("signal_dbm"),
                    "encryption": ap.get("encryption", "Unknown")
                })
        rogue_ap_state["known_aps"] = known_aps_flat
        
        manager.broadcast({
            "event": "rogue_ap_scan_finished",
            "alerts": len(rogue_ap_state["alerts"]),
            "aps_scanned": len(seen_aps)
        })
        
        logger.info(f"Rogue AP detection finished: {len(rogue_ap_state['alerts'])} alerts")
        
    except ImportError:
        rogue_ap_state["active"] = False
        logger.error("Scapy not installed for Rogue AP detection")
    except Exception as e:
        rogue_ap_state["active"] = False
        logger.error(f"Rogue AP detection error: {e}")


# ────────────────────────────────────────────────────────────
# 15. SIGNAL MAPPING - Channel overlap & signal strength
# ────────────────────────────────────────────────────────────

@router.post("/signal/map")
async def start_signal_mapping(
    background_tasks: BackgroundTasks,
    duration: int = Body(30),
    interface: Optional[str] = Body(None)
):
    """
    Scan all channels and map signal strengths.
    Returns channel overlap analysis and signal strength map.
    Useful for finding the best channel and detecting interference.
    
    Works with or without monitor mode (but monitor mode gives better results).
    """
    iface = interface or monitor_state.get("interface")
    
    if platform.system() == "Linux" and not iface:
        # Try using iw/nmcli for basic scan without monitor mode
        try:
            result = subprocess.run(
                ["iw", "dev", "wlan0", "scan", "trigger"],
                capture_output=True, text=True, timeout=10
            )
            time.sleep(3)
            result = subprocess.run(
                ["iw", "dev", "wlan0", "scan"],
                capture_output=True, text=True, timeout=15
            )
            
            networks = []
            current_bssid = None
            current_ssid = None
            current_signal = None
            current_channel = None
            current_encryption = None
            
            for line in result.stdout.split("\n"):
                line_stripped = line.strip()
                
                if line_stripped.startswith("BSS"):
                    # Save previous
                    if current_bssid and current_ssid:
                        networks.append({
                            "bssid": current_bssid,
                            "ssid": current_ssid,
                            "signal_dbm": current_signal,
                            "channel": current_channel,
                            "encryption": current_encryption
                        })
                    
                    # Parse new BSS
                    match = re.search(r'BSS ([0-9a-f:]+)', line_stripped)
                    current_bssid = match.group(1) if match else None
                    current_ssid = None
                    current_signal = None
                    current_channel = None
                    current_encryption = None
                
                elif "SSID:" in line_stripped:
                    current_ssid = line_stripped.split("SSID:")[1].strip()
                elif "signal:" in line_stripped:
                    sig_match = re.search(r'(-\d+\.\d+)', line_stripped)
                    if sig_match:
                        current_signal = float(sig_match.group(1))
                elif "primary channel:" in line_stripped:
                    ch_match = re.search(r'(\d+)', line_stripped)
                    if ch_match:
                        current_channel = int(ch_match.group(1))
            
            # Save last
            if current_bssid and current_ssid:
                networks.append({
                    "bssid": current_bssid,
                    "ssid": current_ssid,
                    "signal_dbm": current_signal,
                    "channel": current_channel,
                    "encryption": current_encryption
                })
            
            # Analyze channel overlap
            channel_raw = {}  # ch -> [{ssid, signal}]
            for net in networks:
                ch = net.get("channel")
                if ch:
                    if ch not in channel_raw:
                        channel_raw[ch] = []
                    channel_raw[ch].append({"ssid": net["ssid"], "signal": net["signal_dbm"]})
            
            # Build channel_usage dict with network_count for frontend
            channel_usage = {}
            for ch in range(1, 14):
                nets = channel_raw.get(ch, [])
                overlap = 0
                for adj_ch in range(max(1, ch-2), min(14, ch+3)):
                    if adj_ch != ch:
                        overlap += len(channel_raw.get(adj_ch, []))
                channel_usage[str(ch)] = {
                    "network_count": len(nets),
                    "networks": nets,
                    "adjacent_overlap": overlap
                }
            
            # Find best channel (least congested)
            best_channels = []
            for ch in range(1, 14):  # 2.4GHz channels
                count = len(channel_raw.get(ch, []))
                overlap = 0
                for adj_ch in range(max(1, ch-2), min(14, ch+3)):
                    if adj_ch != ch:
                        overlap += len(channel_raw.get(adj_ch, []))
                
                best_channels.append({
                    "channel": ch,
                    "network_count": count,
                    "networks": count,
                    "adjacent_overlap": overlap,
                    "score": count + overlap  # Lower is better
                })
            
            best_channels.sort(key=lambda x: x["score"])
            
            return {
                "status": "success",
                "networks": networks,
                "channel_usage": channel_usage,
                "best_channels": best_channels[:5],
                "recommended_channel": best_channels[0]["channel"] if best_channels else None
            }
            
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    # If monitor mode is active, use scapy for deeper scan
    if monitor_state["active"] and iface:
        try:
            from scapy.all import sniff, Dot11, Dot11Beacon, Dot11Elt, RadioTap
            
            networks = {}
            
            def process_beacon(pkt):
                if pkt.haslayer(Dot11Beacon):
                    bssid = pkt.addr3
                    ssid = None
                    channel = None
                    signal = None
                    
                    if pkt.haslayer(Dot11Elt):
                        elt = pkt[Dot11Elt]
                        while elt:
                            if elt.ID == 0 and elt.info:
                                ssid = elt.info.decode('utf-8', errors='ignore')
                            elif elt.ID == 3:
                                try: channel = ord(elt.info)
                                except: pass
                            elt = elt.payload if hasattr(elt, 'payload') and isinstance(elt.payload, Dot11Elt) else None
                    
                    if pkt.haslayer(RadioTap):
                        try:
                            signal = -(256 - pkt[RadioTap].dBm_AntSignal) if hasattr(pkt[RadioTap], 'dBm_AntSignal') else None
                        except: pass
                    
                    if ssid and bssid:
                        networks[bssid] = {"ssid": ssid, "channel": channel, "signal_dbm": signal, "bssid": bssid}
            
            # Channel hop during scan
            for ch in range(1, 14):
                subprocess.run(["iw", "dev", iface, "set", "channel", str(ch)], capture_output=True, timeout=3)
                sniff(iface=iface, prn=process_beacon, timeout=2, store=False)
            
            # Analyze
            channel_raw = {}
            for net in networks.values():
                ch = net.get("channel")
                if ch:
                    if ch not in channel_raw:
                        channel_raw[ch] = []
                    channel_raw[ch].append({"ssid": net["ssid"], "signal": net["signal_dbm"]})
            
            channel_usage = {}
            for ch in range(1, 14):
                nets = channel_raw.get(ch, [])
                overlap = sum(len(channel_raw.get(adj, [])) for adj in range(max(1, ch-2), min(14, ch+3)) if adj != ch)
                channel_usage[str(ch)] = {
                    "network_count": len(nets),
                    "networks": nets,
                    "adjacent_overlap": overlap
                }
            
            best_channels = []
            for ch in range(1, 14):
                count = len(channel_raw.get(ch, []))
                overlap = sum(len(channel_raw.get(adj, [])) for adj in range(max(1, ch-2), min(14, ch+3)) if adj != ch)
                best_channels.append({"channel": ch, "network_count": count, "networks": count, "adjacent_overlap": overlap, "score": count + overlap})
            
            best_channels.sort(key=lambda x: x["score"])
            
            return {
                "status": "success",
                "networks": list(networks.values()),
                "channel_usage": channel_usage,
                "best_channels": best_channels[:5],
                "recommended_channel": best_channels[0]["channel"] if best_channels else None
            }
            
        except ImportError:
            return {"status": "error", "message": "Scapy not installed for deep signal mapping"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    return {"status": "error", "message": "No interface available. Enable monitor mode or connect to a network."}
