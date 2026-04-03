"""
Security Engine — Evaluates the security level of each device based on:
- Open ports
- Protocols used
- Discovered vulnerabilities
- Firmware versions
- Known CVEs
- TLS/SSL certificate validation
The result: SAFE | MEDIUM | RISK
"""

from typing import List, Dict, Optional, Any
import re
from datetime import datetime

# ====== Vulnerability Map by Protocol ======

# CRITICAL PORTS
CRITICAL_PORTS = {
    23:   ("OPEN_TELNET",    "CRITICAL", "Telnet is open — Unencrypted data transfer"),
    21:   ("OPEN_FTP",       "CRITICAL", "FTP is open — Allows insecure file upload/download"),
    69:   ("OPEN_TFTP",      "CRITICAL", "TFTP is open — Insecure file transfer protocol"),
    2323: ("ALT_TELNET",     "CRITICAL", "Alternative Telnet is open (2323)"),
    4444: ("BACKDOOR_PORT",  "CRITICAL", "Suspicious backdoor port is open"),
    445:  ("SMB_OPEN",       "CRITICAL", "SMB is open — Vulnerable to exploits (EternalBlue, etc.)"),
    139:  ("NETBIOS_OPEN",   "HIGH",     "NetBIOS is open — May expose system information"),
    3389: ("RDP_OPEN",       "HIGH",     "RDP is open — Target for brute-force and BlueKeep"),
    5900: ("VNC_OPEN",       "HIGH",     "VNC is open — Often unencrypted remote access"),
    5901: ("VNC_OPEN_ALT",   "HIGH",     "VNC alternative port is open"),
}

# MEDIUM PORTS
MEDIUM_PORTS = {
    80:   ("HTTP_OPEN",      "MEDIUM",   "HTTP is open — Unencrypted control panel"),
    8080: ("ALT_HTTP",       "MEDIUM",   "Alternative HTTP port is open"),
    8888: ("ALT_HTTP_8888",  "MEDIUM",   "Administrative HTTP port is open"),
    554:  ("RTSP_OPEN",      "MEDIUM",   "RTSP is open — Potential unencrypted camera stream"),
    1900: ("UPNP_OPEN",      "MEDIUM",   "UPnP is open — May allow network configuration changes"),
    5555: ("ADB_OPEN",       "MEDIUM",   "Android Debug Bridge is open"),
    9000: ("ADMIN_PORT",     "MEDIUM",   "Administrative port is open"),
    22:   ("SSH_OPEN",       "LOW",      "SSH is open — Ensure strong authentication"),
    443:  ("HTTPS_OPEN",     "LOW",      "HTTPS is open — Verify certificate validity"),
    1883: ("MQTT_OPEN",      "MEDIUM",   "MQTT broker is open — Often unauthenticated in IoT"),
    5683: ("COAP_OPEN",      "MEDIUM",   "CoAP is open — UDP-based IoT protocol, often unsecured"),
    8443: ("HTTPS_ALT",      "MEDIUM",   "Alternative HTTPS port is open"),
    5000: ("UPNP_ALT",       "MEDIUM",   "UPnP alternative port or Flask/Dev server"),
}

# Default Passwords commonly found in IoT devices
DEFAULT_CREDENTIALS = [
    # Generic defaults
    ("admin",    "admin"),
    ("admin",    "password"),
    ("admin",    "1234"),
    ("admin",    ""),
    ("root",     "root"),
    ("root",     ""),
    ("root",     "toor"),
    ("user",     "user"),
    # Vendor specific
    ("ubnt",     "ubnt"),           # Ubiquiti
    ("pi",       "raspberry"),      # Raspberry Pi
    ("admin",    "admin123"),
    ("admin",    "12345"),
    ("admin",    "123456"),
    ("admin",    "12345678"),
    ("admin",    "1234567890"),
    ("admin",    "passwd"),
    ("admin",    "pass"),
    ("administrator", "administrator"),
    # Cameras
    ("admin",    "tlJwpbo6"),       # Hikvision backdoor
    ("admin",    "hikvision"),      # Hikvision
    ("admin",    "dahua"),          # Dahua
    ("admin",    "admin12345"),
    # Routers
    ("admin",    "michael"),        # Some Linksys
    ("admin",    "oelinux123"),     # Oracle
    ("admin",    "antslq"),         # Antlabs
    ("admin",    "admin@123"),
    ("admin",    "admin@1234"),
    ("admin",    "admin@12345"),
    ("support",  "support"),
    ("tech",     "tech"),
    ("guest",    "guest"),
    ("test",     "test"),
    # Industrial/IoT
    ("operator",  "operator"),
    ("service",   "service"),
    ("supervisor", "supervisor"),
    ("maint",     "maint"),
    ("engineer",  "engineer"),
    ("manager",   "manager"),
    ("monitor",   "monitor"),
    ("scada",     "scada"),
    # NAS devices
    ("admin",     "netgear1"),
    ("admin",     "netgear"),
]

# Known vulnerable firmware versions (device_type -> vulnerable_versions)
VULNERABLE_FIRMWARE = {
    "hikvision_camera": {
        "versions": ["5.5.0", "5.5.1", "5.5.2"],
        "cve": "CVE-2021-36260",
        "severity": "CRITICAL",
        "description": "Unauthenticated RCE vulnerability in Hikvision cameras"
    },
    "dahua_camera": {
        "versions": ["2.622.0000.0", "2.800.0000.0"],
        "cve": "CVE-2021-33044",
        "severity": "CRITICAL",
        "description": "Authentication bypass in Dahua cameras"
    },
    "tp_link_router": {
        "versions": ["1.0.1", "1.0.2"],
        "cve": "CVE-2020-9374",
        "severity": "HIGH",
        "description": "RCE vulnerability in TP-Link routers"
    },
    "xiaomi_camera": {
        "versions": ["3.0.4"],
        "cve": "CVE-2020-3196",
        "severity": "HIGH",
        "description": "Authentication bypass in Xiaomi cameras"
    }
}

# Common Zigbee Vulnerabilities
ZIGBEE_VULNS = [
    ("ZIGBEE_DEFAULT_KEY", "HIGH",
     "Using default TC Link key (0x00...00) — Easily exploitable"),
    ("ZIGBEE_NO_ENCRYPT",  "CRITICAL",
     "Zigbee network is unencrypted — Packets are visible to everyone"),
    ("ZIGBEE_REPLAY",      "MEDIUM",
     "No protection against Replay attacks on the network"),
]

# Common Matter Vulnerabilities
MATTER_VULNS = [
    ("MATTER_OPEN_COMMISS", "MEDIUM",
     "Matter device in open Commissioning mode — Can be paired by anyone"),
    ("MATTER_EXPIRED_CERT", "HIGH",
     "DAC certificate is invalid or expired"),
    ("MATTER_NO_PASSCODE",  "HIGH",
     "Matter device without a secure Passcode — Probable default code"),
]

# Common Bluetooth Vulnerabilities
BLUETOOTH_VULNS = [
    ("BLE_NO_PAIRING", "HIGH", "Device does not require pairing and allows anyone to connect"),
    ("BLE_WEAK_AUTH", "MEDIUM", "Weak authentication or unencrypted response (Just Works)"),
    ("BLE_EXPOSED_CHARACTERISTICS", "MEDIUM", "Device exposes read/write attributes without protection"),
]

# Common RFID/Access Control Vulnerabilities
RFID_VULNS = [
    ("RFID_MIFARE_DEFAULT_KEY", "CRITICAL", "Card uses default, easily crackable keys (Mifare Classic Default Keys)"),
    ("RFID_EASILY_CLONABLE", "HIGH", "Card relies solely on UID without encryption (Easily clonable)"),
    ("RFID_LEGACY_CRYPTO", "HIGH", "Card uses deprecated crypto (Crypto1) vulnerable to attacks"),
    ("RFID_NO_MUTUAL_AUTH", "MEDIUM", "Card lacks mutual authentication protocol"),
    ("RFID_DESWEET_ATTACK", "HIGH", "Card vulnerable to Desweet attack on DESFire"),
]

# Z-Wave Protocol Vulnerabilities
ZWAVE_VULNS = [
    ("ZWAVE_NO_ENCRYPTION", "CRITICAL", "Z-Wave device using S0 legacy encryption or no encryption"),
    ("ZWAVE_INCLUSION_VULN", "HIGH", "Device vulnerable to forced inclusion attacks"),
    ("ZWAVE_REPLAY_ATTACK", "HIGH", "No replay protection detected"),
    ("ZWAVE_NETWORK_KEY_EXPOSURE", "CRITICAL", "Network key transmitted in plaintext during pairing"),
]

# LoRaWAN Vulnerabilities
LORA_VULNS = [
    ("LORA_ABF_CONFIRMATION", "HIGH", "Device accepts unconfirmed downlinks (potential beacon fraud)"),
    ("LORA_WEAK_DEVNONCE", "MEDIUM", "Device uses predictable DevNonce values"),
    ("LORA_NO_ADR_LIMITS", "LOW", "No ADR limits set (potential DoS vector)"),
    ("LORA_JOIN_REQUEST_FLOOD", "MEDIUM", "Device vulnerable to join-request flooding"),
]

# Thread/Matter Vulnerabilities
THREAD_VULNS = [
    ("THREAD_NO_COMMISSIONER_AUTH", "CRITICAL", "Thread network allows unauthenticated commissioner"),
    ("THREAD_ACTIVE_COMMISSIONER", "MEDIUM", "Active commissioner mode enabled (potential attack vector)"),
    ("THREAD_NETWORK_KEY_WEAK", "HIGH", "Weak or default Thread network key detected"),
    ("THREAD_BORDER_ROUTER_EXPOSED", "HIGH", "Border router exposes internal network services"),
]

# TLS/SSL Vulnerabilities
TLS_VULNS = {
    "SSLV3_ENABLED": ("CRITICAL", "SSLv3 is enabled (POODLE vulnerability)"),
    "TLSV1_ENABLED": ("HIGH", "TLS 1.0 is enabled (deprecated protocol)"),
    "TLSV1_1_ENABLED": ("MEDIUM", "TLS 1.1 is enabled (deprecated protocol)"),
    "SELF_SIGNED_CERT": ("MEDIUM", "Self-signed certificate detected"),
    "EXPIRED_CERT": ("CRITICAL", "Expired SSL/TLS certificate"),
    "WEAK_CIPHER": ("HIGH", "Weak cipher suite supported"),
    "NO_HSTS": ("LOW", "HSTS header not implemented"),
    "CERT_CN_MISMATCH": ("MEDIUM", "Certificate Common Name mismatch"),
}


def calculate_risk(open_ports: List[int], protocol: str, extra_flags: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Calculates risk level and returns:
    {
        "risk_level": "SAFE" | "MEDIUM" | "RISK",
        "risk_score": float (0-100),
        "vulnerabilities": [ {vuln_type, severity, description, port} ]
    }
    """
    score: float = 0.0
    vulns: List[Dict[str, Any]] = []
    
    if extra_flags is None:
        extra_flags = {}

    # --- Check Critical Ports ---
    for port in open_ports:
        if port in CRITICAL_PORTS:
            name, sev, desc = CRITICAL_PORTS[port]
            score += 40.0 if sev == "CRITICAL" else (30.0 if sev == "HIGH" else 20.0)
            vulns.append({"vuln_type": name, "severity": sev,
                           "description": desc, "port": port, "protocol": "TCP"})

        elif port in MEDIUM_PORTS:
            name, sev, desc = MEDIUM_PORTS[port]
            score += 15.0 if sev == "MEDIUM" else 5.0
            vulns.append({"vuln_type": name, "severity": sev,
                           "description": desc, "port": port, "protocol": "TCP"})

    # --- Default Credentials ---
    if extra_flags.get("default_creds"):
        cred = extra_flags["default_creds"]
        score += 50.0
        vulns.append({
            "vuln_type": "DEFAULT_CREDENTIALS",
            "severity": "CRITICAL",
            "description": f"Default credentials '{cred[0]}/{cred[1]}' work on the device!",
            "port": None,
            "protocol": "HTTP/Telnet"
        })

    # --- Zigbee Vulnerabilities ---
    if protocol == "Zigbee":
        for name, sev, desc in ZIGBEE_VULNS:
            if extra_flags.get(name, True):   # By default we add vulnerabilities for simulation
                score += 25.0
                vulns.append({"vuln_type": name, "severity": sev,
                               "description": desc, "port": None, "protocol": "Zigbee"})

    # --- Matter Vulnerabilities ---
    if protocol == "Matter":
        for name, sev, desc in MATTER_VULNS:
            if extra_flags.get(name, False):
                score += 20.0
                vulns.append({"vuln_type": name, "severity": sev,
                               "description": desc, "port": None, "protocol": "Matter"})

    # --- Bluetooth Vulnerabilities ---
    if protocol == "Bluetooth":
        for name, sev, desc in BLUETOOTH_VULNS:
            if extra_flags.get(name, False):
                score += 30.0 if sev == "HIGH" else 15.0
                vulns.append({"vuln_type": name, "severity": sev,
                               "description": desc, "port": None, "protocol": "Bluetooth"})

    # --- RFID Vulnerabilities ---
    if protocol == "RFID":
        for name, sev, desc in RFID_VULNS:
            if extra_flags.get(name, False):
                score += 40.0 if sev == "CRITICAL" else (30.0 if sev == "HIGH" else 15.0)
                vulns.append({"vuln_type": name, "severity": sev,
                               "description": desc, "port": None, "protocol": "RFID"})

    # --- Z-Wave Vulnerabilities ---
    if protocol == "Z-Wave":
        for name, sev, desc in ZWAVE_VULNS:
            if extra_flags.get(name, False):
                score += 40.0 if sev == "CRITICAL" else (30.0 if sev == "HIGH" else 15.0)
                vulns.append({"vuln_type": name, "severity": sev,
                               "description": desc, "port": None, "protocol": "Z-Wave"})

    # --- LoRaWAN Vulnerabilities ---
    if protocol == "LoRaWAN":
        for name, sev, desc in LORA_VULNS:
            if extra_flags.get(name, False):
                score += 35.0 if sev == "HIGH" else (15.0 if sev == "MEDIUM" else 5.0)
                vulns.append({"vuln_type": name, "severity": sev,
                               "description": desc, "port": None, "protocol": "LoRaWAN"})

    # --- Thread Vulnerabilities ---
    if protocol == "Thread":
        for name, sev, desc in THREAD_VULNS:
            if extra_flags.get(name, False):
                score += 40.0 if sev == "CRITICAL" else (30.0 if sev == "HIGH" else 15.0)
                vulns.append({"vuln_type": name, "severity": sev,
                               "description": desc, "port": None, "protocol": "Thread"})

    # --- TLS/SSL Vulnerabilities ---
    if extra_flags.get("tls_issues"):
        for issue in extra_flags["tls_issues"]:
            if issue in TLS_VULNS:
                sev, desc = TLS_VULNS[issue]
                score += 40.0 if sev == "CRITICAL" else (25.0 if sev == "HIGH" else (15.0 if sev == "MEDIUM" else 5.0))
                vulns.append({"vuln_type": issue, "severity": sev,
                               "description": desc, "port": 443, "protocol": "TLS/SSL"})

    # --- Firmware Vulnerabilities (CVE Check) ---
    if extra_flags.get("firmware_info"):
        fw_info = extra_flags["firmware_info"]
        device_type = fw_info.get("type", "")
        version = fw_info.get("version", "")
        if device_type in VULNERABLE_FIRMWARE:
            vuln_fw = VULNERABLE_FIRMWARE[device_type]
            if version in vuln_fw["versions"]:
                score += 50.0
                vulns.append({
                    "vuln_type": f"CVE_{vuln_fw['cve']}",
                    "severity": vuln_fw["severity"],
                    "description": f"{vuln_fw['description']} (Version: {version})",
                    "port": None,
                    "protocol": "Firmware"
                })

    # --- Calculate Security Level ---
    score = min(score, 100.0)  # Max score is 100

    if score == 0.0:
        risk_level = "SAFE"
    elif score <= 40.0:
        risk_level = "MEDIUM"
    else:
        risk_level = "RISK"

    return {
        "risk_level": risk_level,
        "risk_score":  round(score, 1),
        "vulnerabilities": vulns
    }


def assess_tls_security(hostname: str, port: int = 443) -> List[str]:
    """
    Assess TLS/SSL security of a device.
    Returns list of TLS vulnerability identifiers.
    """
    issues = []
    
    try:
        import ssl
        import socket
        from datetime import datetime as dt
        
        context = ssl.create_default_context()
        
        with socket.create_connection((hostname, port), timeout=5) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                # Check protocol versions
                if ssock.version() in ["SSLv3", "TLSv1", "TLSv1.1"]:
                    if ssock.version() == "SSLv3":
                        issues.append("SSLV3_ENABLED")
                    elif ssock.version() == "TLSv1":
                        issues.append("TLSV1_ENABLED")
                    elif ssock.version() == "TLSv1.1":
                        issues.append("TLSV1_1_ENABLED")
                
                # Check certificate
                cert = ssock.getpeercert(binary_form=True)
                if cert:
                    from cryptography import x509
                    from cryptography.hazmat.backends import default_backend
                    
                    cert_obj = x509.load_der_x509_certificate(cert, default_backend())
                    
                    # Check expiration
                    if cert_obj.not_valid_after_utc < dt.utcnow():
                        issues.append("EXPIRED_CERT")
                    
                    # Check self-signed (issuer == subject)
                    if cert_obj.issuer == cert_obj.subject:
                        issues.append("SELF_SIGNED_CERT")
                    
    except ssl.SSLCertVerificationError as e:
        if "self signed" in str(e).lower():
            issues.append("SELF_SIGNED_CERT")
    except Exception as e:
        pass  # Connection failed or other error
    
    return issues


def get_remediation(vuln_type: str) -> str:
    """
    Returns remediation advice for a given vulnerability type.
    """
    remediations = {
        "OPEN_TELNET": "Disable Telnet and use SSH for secure remote access.",
        "OPEN_FTP": "Disable FTP and use SFTP or SCP for secure file transfer.",
        "OPEN_TFTP": "Disable TFTP or implement access control lists.",
        "BACKDOOR_PORT": "Investigate and close suspicious backdoor ports immediately.",
        "SMB_OPEN": "Disable SMB if not needed, or apply latest security patches (MS17-010).",
        "RDP_OPEN": "Enable Network Level Authentication (NLA) and use strong passwords.",
        "VNC_OPEN": "Enable encryption and use strong authentication for VNC.",
        "HTTP_OPEN": "Implement HTTPS and redirect HTTP traffic.",
        "RTSP_OPEN": "Enable authentication and use RTSPS for encrypted streams.",
        "MQTT_OPEN": "Enable MQTT authentication and use TLS encryption.",
        "COAP_OPEN": "Implement DTLS for secure CoAP communication.",
        "DEFAULT_CREDENTIALS": "Change default credentials to strong, unique passwords immediately.",
        "ZIGBEE_DEFAULT_KEY": "Update Zigbee network to use unique, secure link keys.",
        "ZIGBEE_NO_ENCRYPT": "Enable AES-128 encryption on Zigbee network.",
        "MATTER_OPEN_COMMISS": "Disable open commissioning mode after initial setup.",
        "BLE_NO_PAIRING": "Enable pairing/bonding requirements.",
        "RFID_MIFARE_DEFAULT_KEY": "Replace with MIFARE DESFire or change all sector keys.",
        "RFID_EASILY_CLONABLE": "Use cards with cryptographic authentication.",
        "ZWAVE_NO_ENCRYPTION": "Enable S2 security framework on Z-Wave devices.",
        "LORA_ABF_CONFIRMATION": "Require confirmed downlinks for critical commands.",
        "THREAD_NO_COMMISSIONER_AUTH": "Enable commissioner authentication.",
        "SSLV3_ENABLED": "Disable SSLv3 and use TLS 1.2 or higher.",
        "TLSV1_ENABLED": "Disable TLS 1.0 and use TLS 1.2 or higher.",
        "EXPIRED_CERT": "Renew SSL/TLS certificate immediately.",
        "SELF_SIGNED_CERT": "Use certificates from a trusted CA.",
    }
    return remediations.get(vuln_type, "Apply vendor security updates and follow best practices.")

