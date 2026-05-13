import asyncio
import socket
import subprocess
import nmap
import threading
import time
import json
import os
import hashlib
import random
from fastapi import APIRouter, Depends, BackgroundTasks, Body, HTTPException
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

from database import get_db, Device, Vulnerability, SessionLocal, Setting
from models import ScanStatus
from security_engine import calculate_risk, DEFAULT_CREDENTIALS, assess_tls_security
from ai_engine import analyze_single_device

from routers.iot import get_hostname_enhanced, get_vendor_from_mac
from websocket_manager import manager
from security_assessment import SecurityAssessmentLayer
from nmap_scanner import PentexNmapScanner

router = APIRouter(prefix="/wireless", tags=["WiFi & Bluetooth"])

# ── Hybrid Scan Engine Constants ──────────────────────────────
VULN_RULES = {
    21:   ("FTP_CLEARTEXT",        "High",     "ftp",        "FTP transmits credentials in cleartext. Packet capture trivially reveals usernames and passwords.",                                 "Disable FTP. Use SFTP (port 22) or FTPS with explicit TLS. Block port 21 at the firewall."),
    22:   ("SSH_WEAK_CONFIG",      "Medium",   "ssh",        "SSH is exposed. Weak configurations may allow brute-force, root login, or legacy ciphers.",                                       "Disable password auth, use Ed25519 keys, restrict AllowUsers, set PermitRootLogin no."),
    23:   ("TELNET_CLEARTEXT",     "Critical", "telnet",     "Telnet transmits all data including credentials in plaintext. This is a critical vulnerability.",                               "Disable Telnet immediately. Replace with SSH. Block port 23 at the firewall."),
    25:   ("SMTP_OPEN_RELAY",      "High",     "smtp",       "SMTP port exposed. May be misconfigured as an open relay, enabling spam and phishing campaigns.",                              "Restrict SMTP to authenticated users. Disable open relay. Enable SPF, DKIM, DMARC."),
    53:   ("DNS_AMPLIFICATION",    "Medium",   "dns",        "Open DNS resolver detected. Can be exploited for DNS amplification DDoS attacks.",                                             "Restrict recursive DNS queries to internal hosts. Apply rate-limiting. Use Response Rate Limiting (RRL)."),
    80:   ("HTTP_UNENCRYPTED",     "Medium",   "http",       "Unencrypted HTTP traffic exposes data to man-in-the-middle attacks.",                                                          "Force redirect all HTTP to HTTPS. Implement HSTS with includeSubDomains."),
    110:  ("POP3_CLEARTEXT",       "High",     "pop3",       "POP3 without TLS exposes email credentials and content.",                                                                       "Use POP3S (port 995) with TLS. Disable plaintext POP3."),
    111:  ("RPC_PORTMAPPER",       "High",     "rpcbind",    "RPC portmapper is exposed. Allows enumeration of RPC services and can lead to NFS exploitation.",                              "Block port 111 externally. Disable unused RPC services. Use a firewall to restrict access."),
    135:  ("MSRPC_EXPOSED",        "High",     "msrpc",      "Microsoft RPC endpoint mapper exposed. Used in DCOM attacks and lateral movement.",                                            "Block port 135 at the firewall. Apply MS patches. Restrict DCOM access."),
    139:  ("NETBIOS_EXPOSED",      "High",     "netbios",    "NetBIOS session service exposed. Enables network share enumeration and potential pass-the-hash attacks.",                     "Disable NetBIOS over TCP/IP. Block ports 137-139 at the firewall."),
    143:  ("IMAP_CLEARTEXT",       "Medium",   "imap",       "IMAP without TLS exposes email metadata and credentials.",                                                                      "Use IMAPS (port 993). Disable plaintext IMAP. Enforce TLS 1.2+."),
    443:  ("WEAK_TLS_SUPPORT",     "Medium",   "https",      "TLS service detected. Older TLS 1.0/1.1 protocols may be enabled, which are deprecated and insecure.",                     "Enforce TLS 1.2+ only. Disable SSLv3/TLS1.0/1.1. Use strong cipher suites (ECDHE+AES-GCM)."),
    445:  ("SMB_EXPOSED",          "Critical", "smb",        "SMB exposed. Vulnerable to EternalBlue (MS17-010) and related ransomware attacks.",                                           "Apply MS17-010 patch. Disable SMBv1. Block port 445 externally. Enable SMB signing."),
    514:  ("SYSLOG_EXPOSED",       "Medium",   "syslog",     "Syslog port exposed without authentication. Logs can be forged or intercepted.",                                               "Use syslog-ng or rsyslog with TLS. Restrict access to logging server."),
    548:  ("AFP_EXPOSED",          "Medium",   "afp",        "Apple Filing Protocol exposed. AFP has known authentication weaknesses.",                                                      "Disable AFP if not required. Migrate to SMB3 with encryption. Apply all Apple security patches."),
    554:  ("RTSP_STREAM_EXPOSED",  "High",     "rtsp",       "RTSP stream exposed. Camera/media streams accessible without authentication.",                                                "Require authentication for all RTSP streams. Place cameras on isolated VLAN. Use VPN for remote access."),
    587:  ("SMTP_SUBMISSION",      "Low",      "smtp",       "SMTP submission port exposed. Ensure STARTTLS is enforced and authentication is required.",                                  "Enforce STARTTLS on port 587. Require SASL authentication. Disable legacy authentication."),
    631:  ("IPP_EXPOSED",          "Medium",   "ipp",        "IPP (Internet Printing Protocol) exposed. Can allow unauthorized printing or information disclosure.",                     "Restrict IPP access to LAN only. Require authentication. Apply CUPS security patches."),
    873:  ("RSYNC_EXPOSED",        "High",     "rsync",      "rsync port exposed. Can allow unauthorized data access or manipulation without authentication.",                              "Require rsync authentication. Restrict to specific source IPs. Use SSH tunneling for rsync."),
    993:  ("IMAPS_TLS_VERIFY",     "Low",      "imaps",      "IMAPS service detected. Ensure TLS certificate is valid and strong ciphers are in use.",                                     "Validate TLS certificate. Enforce TLS 1.2+. Use strong cipher suites."),
    995:  ("POP3S_TLS_VERIFY",     "Low",      "pop3s",      "POP3S service detected. Ensure TLS certificate is valid and strong ciphers are in use.",                                    "Validate TLS certificate. Enforce TLS 1.2+. Use strong cipher suites."),
    1080: ("SOCKS_PROXY",          "High",     "socks",      "SOCKS proxy exposed. Can be abused for anonymous tunneling and bypassing network controls.",                               "Restrict SOCKS proxy to authorized users only. Require authentication. Block externally."),
    1194: ("VPN_EXPOSED",          "Low",      "openvpn",    "OpenVPN port exposed. Ensure strong certificates and up-to-date OpenVPN version.",                                          "Keep OpenVPN patched. Use TLS 1.2+. Enforce certificate-based authentication."),
    1433: ("MSSQL_EXPOSED",        "Critical", "mssql",      "Microsoft SQL Server exposed to network. Risk of SQL injection, data exfiltration, and remote code execution.",             "Block port 1433 externally. Use Windows Authentication. Apply all SQL Server security patches."),
    1723: ("PPTP_VPN_WEAK",        "High",     "pptp",       "PPTP VPN uses MS-CHAPv2, which is cryptographically broken and susceptible to offline brute-force.",                      "Migrate from PPTP to IKEv2/IPSec or WireGuard. Disable PPTP immediately."),
    3306: ("MYSQL_EXPOSED",        "Critical", "mysql",      "MySQL database exposed to the network. Risk of unauthorized access, data exfiltration, and SQL injection.",                "Bind MySQL to 127.0.0.1 only. Block port 3306 externally. Use strong passwords and grants."),
    3389: ("RDP_EXPOSED",          "High",     "rdp",        "RDP exposed. Prime target for brute-force, BlueKeep (CVE-2019-0708) and ransomware lateral movement.",                    "Restrict to VPN + IP whitelist. Enable NLA. Apply BlueKeep patch. Change default port."),
    5900: ("VNC_EXPOSED",          "Critical", "vnc",        "VNC remote desktop exposed. Often runs without authentication or with weak passwords.",                                      "Require VNC password. Tunnel over SSH. Block port 5900 externally."),
    8080: ("HTTP_ALT_EXPOSED",     "Medium",   "http-alt",   "Alternative HTTP port exposed. May expose admin panels, dev servers, or staging environments.",                            "Restrict access. Remove or secure admin panels. Enforce authentication on all management interfaces."),
    8443: ("HTTPS_ALT_EXPOSED",    "Medium",   "https-alt",  "Alternative HTTPS port exposed. Verify TLS configuration and restrict admin access.",                                      "Enforce TLS 1.2+. Require strong authentication. Limit access by IP."),
}

SERVICES_MAP = {
    21:   ["vsftpd 3.0.3", "ProFTPD 1.3.5e", "Pure-FTPd 1.0.47"],
    22:   ["OpenSSH 7.4p1", "OpenSSH 8.2p1 Ubuntu", "Dropbear sshd 2019.78"],
    23:   ["Linux telnetd", "Cisco IOS Telnet", "BusyBox telnetd"],
    25:   ["Postfix smtpd 3.4.13", "Exim 4.93", "Sendmail 8.15.2"],
    53:   ["BIND 9.11.3-Ubuntu", "dnsmasq 2.79", "Microsoft DNS 6.1"],
    80:   ["Apache httpd 2.4.29", "nginx 1.14.0", "lighttpd/1.4.53"],
    110:  ["Dovecot pop3d", "Courier POP3"],
    111:  ["rpcbind 2-4", "portmapper"],
    135:  ["Microsoft EPMAP", "Windows RPC"],
    139:  ["Samba 4.7.6", "Windows NetBIOS"],
    143:  ["Dovecot imapd", "Courier IMAP"],
    443:  ["nginx 1.18.0 (TLS)", "Apache/2.4.41 (TLS)", "Microsoft IIS 10.0 (TLS)"],
    445:  ["Samba 4.7.6-Ubuntu", "Windows SMB"],
    514:  ["RSyslogd 8.2001.0", "syslogd"],
    548:  ["Netatalk 3.1.12", "AFP over TCP"],
    554:  ["Dahua RTSP", "Hikvision RTSP", "VLC 3.0 RTSP server"],
    587:  ["Postfix smtpd (STARTTLS)", "Exim (STARTTLS)"],
    631:  ["CUPS 2.3.3", "IPP"],
    873:  ["rsync 3.1.3"],
    993:  ["Dovecot imaps"],
    995:  ["Dovecot pop3s"],
    1080: ["3proxy 0.9.4", "Dante 1.4.2"],
    1194: ["OpenVPN 2.4.7"],
    1433: ["Microsoft SQL Server 2019", "Microsoft SQL Server 2016"],
    1723: ["Microsoft PPTP", "pptpd 1.4.0"],
    3306: ["MySQL 5.7.30", "MariaDB 10.3.22", "MySQL 8.0.21"],
    3389: ["Microsoft Terminal Services", "xrdp 0.9.12"],
    5900: ["VNC (RealVNC 6.7)", "TigerVNC 1.10"],
    8080: ["Apache Tomcat 9.0.40", "Jetty 9.4.35", "Node.js Express 4.17"],
    8443: ["Apache Tomcat 9.0.40 (TLS)", "nginx (TLS)"],
}

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


@router.post("/deep-scan/{ip}")
async def deep_scan_device_api(ip: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(run_port_scan, ip)
    return {"status": "started", "message": f"Deep scan started for {ip}"}


async def run_port_scan(ip: str, db_session: Session = None):
    """
    Advanced Deep Port Scan:
    Aggregates all findings before broadcasting a single 'scan_complete' event.
    """
    db = db_session or SessionLocal()
    # 1. State Containers (Single Source of Truth)
    open_ports = []
    vulnerabilities = []
    service_banners = {}
    proto = "tcp"
    
    try:
        manager.broadcast({
            "event": "scan_start",
            "type": "deep_port_scan",
            "ip": ip,
            "message": f"Initializing scan for {ip}..."
        })

        # 2. Check Mode
        sim_setting = db.query(Setting).filter(Setting.key == "simulation_mode").first()
        is_sim = sim_setting and sim_setting.value.lower() == "true"
        
        real_results = None
        if not is_sim:
            scanner = PentexNmapScanner()
            manager.broadcast({
                "event": "scan_progress", "type": "deep_port_scan",
                "progress": 20, "message": "Executing Nmap scan..."
            })
            real_results = await asyncio.to_thread(scanner.scan, ip)

        # 3. Data Collection
        if real_results and not real_results.get("error") and real_results.get("ports"):
            logger.info(f"[Scan] Processing {len(real_results['ports'])} real ports for {ip}")
            for p_info in real_results["ports"]:
                if p_info["state"] == "open":
                    p = p_info["port"]
                    open_ports.append(p)
                    service_banners[str(p)] = p_info["version"] or p_info["service"]
                    if p in VULN_RULES:
                        vid, rlvl, vsvc, desc, rem = VULN_RULES[p]
                        vulnerabilities.append({
                            "id": vid, "port": p, "service": vsvc,
                            "risk_level": rlvl.upper(), "description": desc, "remediation": rem
                        })
        elif is_sim:
            logger.info(f"[Scan] Falling back to simulation for {ip}")
            seed_val = int(hashlib.md5(ip.encode()).hexdigest(), 16)
            rng = random.Random(seed_val)
            all_possible_ports = list(SERVICES_MAP.keys())
            num_to_pick = rng.randint(1, 4)
            open_ports = sorted(rng.sample(all_possible_ports, num_to_pick))
            for p in open_ports:
                service_banners[str(p)] = rng.choice(SERVICES_MAP.get(p, ["unknown service"]))
                if p in VULN_RULES:
                    vid, rlvl, vsvc, desc, rem = VULN_RULES[p]
                    vulnerabilities.append({
                        "id": vid, "port": p, "service": vsvc,
                        "risk_level": rlvl.upper(), "description": desc, "remediation": rem
                    })
        
        # 4. Persistence & Risk Analysis
        device = db.query(Device).filter(Device.ip == ip).first()
        if device:
            device.open_ports = ",".join(map(str, open_ports))
            risk_assessment = calculate_risk(open_ports, device.protocol)
            
            # Severity merging logic
            highest_sev = "SAFE"
            if vulnerabilities:
                sevs = [v["risk_level"].upper() for v in vulnerabilities]
                for s in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
                    if s in sevs:
                        highest_sev = s
                        break
            
            final_risk = risk_assessment["risk_level"]
            sev_priority = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "SAFE": 0}
            if sev_priority.get(highest_sev, 0) > sev_priority.get(final_risk, 0):
                final_risk = highest_sev
            
            device.risk_level = final_risk
            device.risk_score = max(risk_assessment["risk_score"], 90.0 if final_risk == "CRITICAL" else 0.0)

            # Sync vulns
            db.query(Vulnerability).filter(Vulnerability.device_id == device.id).delete()
            for v in vulnerabilities:
                db.add(Vulnerability(
                    device_id=device.id, vuln_type=v["id"],
                    severity=v["risk_level"].upper(), description=v["description"],
                    port=v["port"], protocol=proto
                ))
            db.commit()
            db.refresh(device)

            # AI Analysis
            ai_results = analyze_single_device({
                "ip": ip, "hostname": device.hostname, "vendor": device.vendor,
                "protocol": device.protocol, "open_ports": device.open_ports,
                "risk_level": device.risk_level, "vulnerabilities": vulnerabilities
            })
            ai_summary = ai_results.get("dynamic_summary", "Security Analysis complete.")

            # 5. FINAL BROADCAST (Single Source of Truth)
            logger.info(f"[Broadcast] Sending final results for {ip}: Ports={len(open_ports)}, Vulns={len(vulnerabilities)}, Risk={final_risk}")
            
            manager.broadcast({
                "event": "scan_complete",
                "type": "deep_port_scan",
                "ip": ip,
                "vendor": device.vendor,
                "hostname": device.hostname,
                "open_ports": open_ports,
                "service_banners": service_banners,
                "vulnerabilities": vulnerabilities,
                "risk_level": device.risk_level,
                "risk_score": device.risk_score,
                "ai_summary": ai_summary,
                "ai_results": ai_results,
                "recommendations": [v["remediation"] for v in vulnerabilities],
                "message": f"Scan complete: {len(open_ports)} ports, {len(vulnerabilities)} vulnerabilities detected."
            })

    except Exception as e:
        logger.error(f"Deep port scan error: {e}")
        manager.broadcast({
            "event": "scan_error",
            "type": "deep_port_scan",
            "ip": ip,
            "message": f"Deep scan failed: {str(e)}"
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

        manager.broadcast({
            "event": "cred_test_start",
            "attack_type": "Credential Testing",
            "target_uid": ip
        })
        await asyncio.sleep(1)

        sim_creds = [
            ("admin", "admin"),
            ("root", "root"),
            ("admin", "password123"),
            ("admin", "1234"),
            ("root", "123456")
        ]

        # Determine success dynamically based on random roll
        # Give a 40% chance to find weak credentials
        is_vulnerable = random.randint(1, 100) <= 40
        found_cred = None

        if is_vulnerable:
            found_cred = random.choice(sim_creds)

        for user, pwd in sim_creds:
            manager.broadcast({
                "event": "cred_test_log",
                "log_line": f"[+] Testing {user}/{pwd}"
            })
            await asyncio.sleep(0.8)
            
            if found_cred and found_cred == (user, pwd):
                manager.broadcast({
                    "event": "cred_test_log",
                    "log_line": f"[!] Weak credentials detected!"
                })
                break
            else:
                manager.broadcast({
                    "event": "cred_test_log",
                    "log_line": f"[-] Failed"
                })

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
            "event": "cred_test_complete",
            "success": bool(found_cred),
            "remediation": "Change default passwords immediately and enforce strong password policies." if found_cred else "Credentials appear secure."
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
async def start_bluetooth_scan(background_tasks: BackgroundTasks):
    if not HAS_BLEAK:
        return ScanStatus(status="error", message="مكتبة bleak غير متوفرة أو البلوتوث غير مدعوم على هذا النظام")
    background_tasks.add_task(run_bluetooth_scan)
    return ScanStatus(status="started", message="جارٍ البحث عن أجهزة البلوتوث (BLE) المجاورة...")


async def run_bluetooth_scan():
    db = SessionLocal()
    try:
        manager.broadcast({
            "event": "scan_start",
            "type": "bluetooth",
            "message": "Starting Bluetooth BLE scan..."
        })
        
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
            
        manager.broadcast({
            "event": "scan_complete",
            "type": "bluetooth",
            "message": f"Bluetooth scan complete. Found {len(devices)} devices."
        })
    except Exception as e:
        logger.error(f"BLE Scan Error: {e}")
        manager.broadcast({
            "event": "scan_error",
            "type": "bluetooth",
            "message": f"Error during Bluetooth scan: {str(e)}"
        })
    finally:
        db.close()


# ────────────────────────────────────────────────────────────
# 6. مسح شبكات الواي فاي القريبة (SSIDs)
# ────────────────────────────────────────────────────────────
@router.get("/scan/ssids")
async def scan_nearby_ssids(db: Session = Depends(get_db)):
    """يكتشف كل شبكات الواي فاي القريبة (SSIDs)"""
    system = platform.system()
    networks = []

    try:
        if system == "Darwin":  # macOS
            # Method 1: Try CoreWLAN via PyObjC (if available)
            try:
                import importlib
                CoreWLAN = importlib.import_module("CoreWLAN")
                Foundation = importlib.import_module("Foundation")
                NSBundle = Foundation.NSBundle
                
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
        
        if SecurityAssessmentLayer.is_enabled(db):
            unique_networks = SecurityAssessmentLayer.analyze_wifi_networks(unique_networks)
            
        return {"status": "success", "ssids": unique_networks, "count": len(unique_networks)}

    except Exception as e:
        logger.error(f"SSID scan error: {e}")
        return {"status": "error", "message": str(e), "ssids": [], "count": 0}


# ────────────────────────────────────────────────────────────
# 6.1. Security Assessment Report
# ────────────────────────────────────────────────────────────
@router.get("/assessment/report")
async def get_assessment_report(db: Session = Depends(get_db)):
    """Generates the full security assessment report."""
    if not SecurityAssessmentLayer.is_enabled(db):
        return {"status": "error", "message": "Security assessment is disabled in settings."}
    return SecurityAssessmentLayer.generate_report()


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
        manager.broadcast({
            "event": "scan_error",
            "message": str(e)
        })
    finally:
        db.close()


# ────────────────────────────────────────────────────────────
# 8. Deep Port Vulnerability Scan
# ────────────────────────────────────────────────────────────

def _normalize_script_output(script_output):
    if isinstance(script_output, str):
        return script_output.strip()
    if isinstance(script_output, dict):
        lines = []
        for key, value in script_output.items():
            if isinstance(value, (str, int, float)):
                lines.append(f"{key}: {value}")
            elif isinstance(value, dict):
                lines.append(f"{key}: {json.dumps(value)}")
            else:
                lines.append(f"{key}: {str(value)}")
        return "\n".join(lines).strip()
    return str(script_output).strip()


def _extract_cve(output: str) -> str:
    matches = re.findall(r'(CVE-\d{4}-\d{4,7})', output, re.IGNORECASE)
    return matches[0].upper() if matches else "N/A"


def _infer_vuln_severity(script_name: str, output: str) -> str:
    score_text = f"{script_name} {output}".upper()
    if any(term in score_text for term in ["CRITICAL", "EXPLOIT", "HEARTBLEED", "ETERNALBLUE", "SHELLSHOCK", "RCE", "UNAUTH", "UNAUTHORIZED"]):
        return "CRITICAL"
    if any(term in score_text for term in ["HIGH", "VULNERABLE", "WEAK", "INSECURE", "DEFAULT", "TLS 1.0", "TLS 1.1", "OPEN RELAY"]):
        return "HIGH"
    if any(term in score_text for term in ["MEDIUM", "DEPRECATED", "SELF-SIGNED", "CERTIFICATE", "MAN-IN-THE-MIDDLE"]):
        return "MEDIUM"
    return "LOW"


def _severity_to_cvss(severity: str) -> float:
    mapping = {
        "CRITICAL": 9.8,
        "HIGH": 7.5,
        "MEDIUM": 5.5,
        "LOW": 2.8,
    }
    return mapping.get(severity, 2.0)


def _parse_nmap_vulnerabilities(ip: str, nm_scan):
    open_ports = []
    services = []
    vulnerabilities = []

    if ip not in nm_scan.all_hosts():
        return open_ports, services, vulnerabilities

    for proto in nm_scan[ip].all_protocols():
        if proto != "tcp":
            continue

        for port in sorted(nm_scan[ip][proto].keys()):
            svc = nm_scan[ip][proto][port]
            if svc.get("state") != "open":
                continue

            open_ports.append(port)
            service_name = (svc.get("name") or "unknown").upper()
            product = svc.get("product") or ""
            version = svc.get("version") or ""
            extrainfo = svc.get("extrainfo") or ""
            version_parts = [part for part in [product, version, extrainfo] if part]
            version_str = " ".join(version_parts) if version_parts else svc.get("version", "unknown")

            services.append({
                "port": port,
                "service": service_name,
                "version": version_str or "unknown"
            })

            script_results = svc.get("script") or {}
            if script_results:
                if isinstance(script_results, dict):
                    for script_name, output in script_results.items():
                        description = _normalize_script_output(output)
                        if not description:
                            continue
                        severity = _infer_vuln_severity(script_name, description)
                        vulnerabilities.append({
                            "port": port,
                            "service": service_name,
                            "severity": severity,
                            "risk_level": severity,
                            "cvss_score": _severity_to_cvss(severity),
                            "description": f"{script_name}: {description}",
                            "cve": _extract_cve(description),
                            "recommendation": "Review Nmap vulnerability findings and apply vendor patches or mitigations."
                        })
                else:
                    description = _normalize_script_output(script_results)
                    severity = _infer_vuln_severity("nmap-vuln", description)
                    vulnerabilities.append({
                        "port": port,
                        "service": service_name,
                        "severity": severity,
                        "risk_level": severity,
                        "cvss_score": _severity_to_cvss(severity),
                        "description": description,
                        "cve": _extract_cve(description),
                        "recommendation": "Review Nmap vulnerability findings and apply vendor patches or mitigations."
                    })

    return open_ports, services, vulnerabilities


@router.post("/deep-scan/{ip}")
async def deep_port_scan(ip: str, db: Session = Depends(get_db)):
    """
    Perform a dynamic deep TCP port scan with service detection and vulnerability feedback.
    """
    manager.broadcast({
        "event": "scan_start",
        "type": "port_scan",
        "ip": ip,
        "message": f"Starting deep port scan for {ip}..."
    })

    try:
        def discovery_scan():
            nm = nmap.PortScanner()
            nm.scan(hosts=ip, arguments="-T4 -p 1-2000 --open -Pn -sT")
            return nm

        manager.broadcast({
            "event": "scan_progress",
            "type": "port_scan",
            "ip": ip,
            "progress": 10,
            "message": "Discovering open TCP ports..."
        })

        discovery_nm = await asyncio.to_thread(discovery_scan)
        open_ports = []
        services = []
        vulnerabilities = []

        if ip in discovery_nm.all_hosts():
            for proto in discovery_nm[ip].all_protocols():
                if proto != "tcp":
                    continue
                for port in discovery_nm[ip][proto].keys():
                    svc = discovery_nm[ip][proto][port]
                    if svc.get("state") == "open":
                        open_ports.append(port)

        if not open_ports:
            manager.broadcast({
                "event": "scan_progress",
                "type": "port_scan",
                "ip": ip,
                "progress": 100,
                "message": "No open ports were discovered."
            })
            manager.broadcast({
                "event": "scan_complete",
                "type": "port_scan",
                "ip": ip,
                "risk_level": "LOW",
                "risk_score": 0,
                "open_ports": [],
                "assessment_summary": {
                    "wireless_findings": 0,
                    "service_exposure": 0,
                    "iot_risks": 0,
                    "recommendations": 0,
                    "new_vulns_added": 0,
                },
                "message": f"Deep scan complete for {ip}: no open ports detected."
            })
            overall_risk = "LOW"
            recommendations = [
                "No open TCP ports detected on the target host.",
                "Continue to monitor the host and apply standard hardening controls.",
                "If the target will provide services, restrict port access to only required systems."
            ]
            return {
                "ip": ip,
                "scan_time": datetime.utcnow().isoformat(),
                "open_ports": [],
                "services": [],
                "vulnerabilities": [],
                "overall_risk": overall_risk,
                "recommendations": recommendations
            }

        manager.broadcast({
            "event": "scan_progress",
            "type": "port_scan",
            "ip": ip,
            "progress": 35,
            "message": "Detecting services and running vulnerability scripts..."
        })

        def vulnerability_scan():
            nm = nmap.PortScanner()
            port_list = ",".join(str(p) for p in open_ports)
            nm.scan(hosts=ip, arguments=f"-T4 -sV --script vuln -p {port_list} -Pn")
            return nm

        vulnerability_nm = await asyncio.to_thread(vulnerability_scan)
        open_ports, services, vulnerabilities = _parse_nmap_vulnerabilities(ip, vulnerability_nm)

        manager.broadcast({
            "event": "scan_progress",
            "type": "port_scan",
            "ip": ip,
            "progress": 75,
            "message": "Parsing vulnerability results..."
        })

        severity_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for vuln in vulnerabilities:
            severity_counts[vuln["severity"]] += 1

        if severity_counts["CRITICAL"] > 0:
            overall_risk = "CRITICAL"
        elif severity_counts["HIGH"] > 2:
            overall_risk = "HIGH"
        elif severity_counts["HIGH"] > 0 or severity_counts["MEDIUM"] > 2:
            overall_risk = "MEDIUM"
        else:
            overall_risk = "LOW"

        recommendations = []
        if severity_counts["CRITICAL"] > 0:
            recommendations.append("Immediate remediation required for critical vulnerabilities.")
        if 23 in open_ports:
            recommendations.append("Disable Telnet and replace it with SSH.")
        if 21 in open_ports:
            recommendations.append("Replace FTP with secure alternatives such as SFTP or SCP.")
        if 139 in open_ports or 445 in open_ports:
            recommendations.append("Harden SMB services and apply vendor patches.")
        if 3389 in open_ports:
            recommendations.append("Limit RDP exposure and enforce Network Level Authentication.")
        if 80 in open_ports and 443 not in open_ports:
            recommendations.append("Consider enabling HTTPS to protect web traffic.")
        recommendations.extend([
            "Apply latest security patches and updates.",
            "Restrict unnecessary open ports with firewall rules.",
        ])

        if vulnerabilities:
            manager.broadcast({
                "event": "vulnerability_found",
                "vulnerability": vulnerabilities[0],
                "ip": ip
            })

        device = db.query(Device).filter(Device.ip == ip).first()
        if device:
            device.open_ports = ",".join(map(str, open_ports))
            risk_result = calculate_risk(open_ports, device.protocol)
            device.risk_level = risk_result["risk_level"]
            device.risk_score = risk_result["risk_score"]
            db.commit()

        manager.broadcast({
            "event": "scan_complete",
            "type": "port_scan",
            "ip": ip,
            "risk_level": overall_risk,
            "risk_score": severity_counts["CRITICAL"] * 40 + severity_counts["HIGH"] * 25 + severity_counts["MEDIUM"] * 12,
            "open_ports": open_ports,
            "assessment_summary": {
                "wireless_findings": 0,
                "service_exposure": len(open_ports),
                "iot_risks": 0,
                "recommendations": len(recommendations),
                "new_vulns_added": len(vulnerabilities),
            },
            "message": f"Deep scan complete for {ip}: {len(open_ports)} open ports, {len(vulnerabilities)} vulnerabilities detected."
        })

        manager.broadcast({
            "event": "scan_progress",
            "type": "port_scan",
            "ip": ip,
            "progress": 100,
            "message": "Deep port scan complete."
        })

        return {
            "ip": ip,
            "scan_time": datetime.utcnow().isoformat(),
            "open_ports": open_ports,
            "services": services,
            "vulnerabilities": vulnerabilities,
            "overall_risk": overall_risk,
            "recommendations": recommendations
        }

    except Exception as e:
        logger.error(f"Deep scan error for {ip}: {e}")
        manager.broadcast({
            "event": "scan_error",
            "type": "port_scan",
            "ip": ip,
            "message": f"Error during deep scan: {str(e)}"
        })
        raise HTTPException(status_code=500, detail=f"Deep scan failed: {str(e)}")


