"""
Security Engine — Evaluates the security level of each device based on:
- Open ports
- Protocols used
- Discovered vulnerabilities
The result: SAFE | MEDIUM | RISK
"""

from typing import List, Dict, Optional, Any

# ====== Vulnerability Map by Protocol ======

# CRITICAL PORTS
CRITICAL_PORTS = {
    23:   ("OPEN_TELNET",    "CRITICAL", "Telnet is open — Unencrypted data transfer"),
    21:   ("OPEN_FTP",       "CRITICAL", "FTP is open — Allows insecure file upload/download"),
    69:   ("OPEN_TFTP",      "CRITICAL", "TFTP is open — Insecure file transfer protocol"),
    2323: ("ALT_TELNET",     "CRITICAL", "Alternative Telnet is open (2323)"),
    4444: ("BACKDOOR_PORT",  "CRITICAL", "Suspicious backdoor port is open"),
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
}

# Default Passwords commonly found in IoT devices
DEFAULT_CREDENTIALS = [
    ("admin",    "admin"),
    ("admin",    "password"),
    ("admin",    "1234"),
    ("admin",    ""),
    ("root",     "root"),
    ("root",     ""),
    ("root",     "toor"),
    ("user",     "user"),
    ("ubnt",     "ubnt"),
    ("pi",       "raspberry"),
    ("admin",    "admin123"),
]

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
]


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
            score += 40.0
            vulns.append({"vuln_type": name, "severity": sev,
                           "description": desc, "port": port, "protocol": "TCP"})

        elif port in MEDIUM_PORTS:
            name, sev, desc = MEDIUM_PORTS[port]
            score += 20.0
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
                score += 40.0 if sev == "CRITICAL" else 30.0
                vulns.append({"vuln_type": name, "severity": sev,
                               "description": desc, "port": None, "protocol": "RFID"})

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

