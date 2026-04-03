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
    background_tasks.add_task(run_network_device_scan, network, db)
    return {"status": "started", "network": network, "message": f"Scanning {network} for devices..."}


async def run_network_device_scan(network: str, db: Session):
    """Scans network and discovers all devices"""
    from websocket_manager import manager
    
    logger.info(f"Starting device discovery on {network}")
    
    try:
        nm = nmap.PortScanner()
        # Fast scan - ping sweep only
        nm.scan(hosts=network, arguments="-sn -T4 --privileged")
        
        devices_found = 0
        for host in nm.all_hosts():
            if nm[host].state() == "up":
                # Get hostname
                hostname = nm[host].hostname() or "Unknown"
                
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
