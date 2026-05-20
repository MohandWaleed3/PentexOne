"""
PentexOne Virtual Lab — Device Registry
========================================

In-memory registry of known Virtual Lab devices, their subnets, and metadata.
Used by the backend to:
  - Detect when a scanned device belongs to the lab
  - Tag lab devices with [LAB] prefix
  - Classify devices by subnet zone (IoT / Guest / Corporate)
  - Provide quick-lab-scan injection without slow nmap sweeps
"""

from typing import Optional, Dict, List, Tuple
import ipaddress


# ===========================================================================
# Lab Subnets — must match docker-compose.yml
# ===========================================================================
LAB_SUBNETS: Dict[str, Dict] = {
    "iot": {
        "cidr": "172.30.10.0/24",
        "name": "IoT Subnet",
        "icon": "🔵",
        "color": "#00B4D8",
        "description": "Smart-home IoT devices (cameras, plugs, thermostats)",
        "difficulty_mix": ["easy", "medium", "hard"],
    },
    "guest": {
        "cidr": "172.30.20.0/24",
        "name": "Guest Network",
        "icon": "🟡",
        "color": "#FFC24D",
        "description": "Visitor-facing devices with limited trust",
        "difficulty_mix": ["easy"],
    },
    "corporate": {
        "cidr": "172.30.30.0/24",
        "name": "Corporate LAN",
        "icon": "🔴",
        "color": "#FF5C5C",
        "description": "Internal business infrastructure (NAS, workstations)",
        "difficulty_mix": ["hard"],
    },
}


# ===========================================================================
# Known Lab Devices — must match docker-compose.yml IP allocations
# ===========================================================================
LAB_DEVICES: List[Dict] = [
    # ───────────── IoT Subnet ─────────────
    {
        "ip": "172.30.10.50",
        "hostname": "HIKVISION-CAMERA",
        "vendor": "Hikvision",
        "device_type": "ip_camera",
        "subnet": "iot",
        "difficulty": "easy",
        "container": "lab-hikvision-camera",
        "exposed_ports": [80],
        "host_port_map": {"80": 8050},
        "vulnerabilities": [
            "DEFAULT_CREDENTIALS",
            "OUTDATED_FIRMWARE",
            "DIRECTORY_LISTING",
            "INFORMATION_DISCLOSURE",
        ],
        "credentials": {"admin": "admin"},
        "description": "IP camera with weak factory configuration",
    },
    {
        "ip": "172.30.10.51",
        "hostname": "MQTT-BROKER",
        "vendor": "Eclipse Mosquitto",
        "device_type": "mqtt_broker",
        "subnet": "iot",
        "difficulty": "easy",
        "container": "lab-mqtt-broker",
        "exposed_ports": [1883, 9001],
        "host_port_map": {"1883": 8051, "9001": 8061},
        "vulnerabilities": [
            "NO_AUTHENTICATION",
            "UNENCRYPTED_PROTOCOL",
            "EXPOSED_TOPICS",
            "WEBSOCKET_OPEN",
        ],
        "credentials": None,
        "description": "Unsecured MQTT broker — anonymous access enabled",
    },
    {
        "ip": "172.30.10.52",
        "hostname": "TPLINK-ROUTER",
        "vendor": "TP-Link",
        "device_type": "router",
        "subnet": "iot",
        "difficulty": "medium",
        "container": "lab-tplink-router",
        "exposed_ports": [23, 80],
        "host_port_map": {"23": 8052, "80": 8062},
        "vulnerabilities": [
            "TELNET_ENABLED",
            "DEFAULT_CREDENTIALS",
            "NO_RATE_LIMITING",
            "WEAK_SESSION",
        ],
        "credentials": {"root": "root", "admin": "admin"},
        "description": "Legacy router with Telnet backdoor",
    },
    {
        "ip": "172.30.10.53",
        "hostname": "TUYA-SMART-PLUG",
        "vendor": "Tuya",
        "device_type": "smart_plug",
        "subnet": "iot",
        "difficulty": "medium",
        "container": "lab-tuya-plug",
        "exposed_ports": [80, 6668],
        "host_port_map": {"80": 8053, "6668": 8063},
        "vulnerabilities": [
            "UPNP_EXPOSED",
            "NO_LOCAL_AUTH",
            "DEVICE_INFO_DISCLOSURE",
            "HARDCODED_KEY",
        ],
        "credentials": None,
        "description": "Smart plug with unauthenticated local API",
    },
    {
        "ip": "172.30.10.54",
        "hostname": "NEST-THERMOSTAT",
        "vendor": "Google Nest",
        "device_type": "thermostat",
        "subnet": "iot",
        "difficulty": "hard",
        "container": "lab-nest-thermostat",
        "exposed_ports": [80, 8080],
        "host_port_map": {"80": 8054, "8080": 8064},
        "vulnerabilities": [
            "OUTDATED_FIRMWARE",
            "DEBUG_INTERFACE_EXPOSED",
            "WEAK_SESSION_TOKENS",
            "CREDENTIAL_LEAK",
        ],
        "credentials": {"admin": "1234"},
        "description": "Thermostat with exposed debug interface leaking credentials",
    },
    # ───────────── Guest Subnet ─────────────
    {
        "ip": "172.30.20.50",
        "hostname": "SAMSUNG-SMARTTV",
        "vendor": "Samsung",
        "device_type": "smart_tv",
        "subnet": "guest",
        "difficulty": "easy",
        "container": "lab-smart-tv",
        "exposed_ports": [80, 8001, 9197],
        "host_port_map": {"80": 8070, "8001": 8071, "9197": 8072},
        "vulnerabilities": [
            "DIAL_EXPOSED",
            "VOICE_API_OPEN",
            "NO_PAIRING_REQUIRED",
            "MIC_REMOTE_CONTROL",
        ],
        "credentials": None,
        "description": "Smart TV with exposed cast/voice services",
    },
    # ───────────── Corporate Subnet ─────────────
    {
        "ip": "172.30.30.50",
        "hostname": "CORP-NAS-01",
        "vendor": "Synology",
        "device_type": "nas",
        "subnet": "corporate",
        "difficulty": "hard",
        "container": "lab-corporate-nas",
        "exposed_ports": [80, 5000, 445, 21],
        "host_port_map": {"80": 8080, "5000": 8081, "445": 8082, "21": 8083},
        "vulnerabilities": [
            "DEFAULT_CREDENTIALS",
            "SMBv1_ENABLED",
            "ANONYMOUS_FTP",
            "SHADOW_BACKUP_EXPOSED",
            "OUTDATED_DSM",
        ],
        "credentials": {"admin": "admin123", "guest": "guest"},
        "description": "Corporate NAS with SMBv1 and exposed credential backups",
    },
]


# ===========================================================================
# BLE Lab Devices (simulated via bumble on host machine)
# ===========================================================================
BLE_DEVICES: List[Dict] = [
    {
        "name": "August-Lock-A4B2",
        "address": "A4:B2:00:01:02:03",
        "device_type": "smart_lock",
        "vendor": "August Home Inc.",
        "difficulty": "easy",
        "vulnerabilities": ["NO_PAIRING_REQUIRED", "CREDENTIAL_LEAK", "INFORMATION_DISCLOSURE"],
        "description": "Smart lock accepting lock/unlock commands without pairing or authentication",
        "exposed_characteristics": ["Lock State (R/W)", "Lock Command (W-no-auth)", "Access Log with PINs (R)"],
    },
    {
        "name": "Fitbit-Charge-5",
        "address": "C5:FB:00:01:02:04",
        "device_type": "fitness_tracker",
        "vendor": "Fitbit Inc.",
        "difficulty": "easy",
        "vulnerabilities": ["EXPOSED_HEALTH_CHARACTERISTICS", "INFORMATION_DISCLOSURE", "NO_PAIRING_REQUIRED"],
        "description": "Fitness tracker exposing heart rate, sleep, GPS, and PII without bonding",
        "exposed_characteristics": ["Heart Rate (R)", "Sleep Data (R)", "User PII (R)", "GPS History (R)"],
    },
    {
        "name": "LIFX-A19-3F88",
        "address": "3F:88:00:01:02:05",
        "device_type": "smart_bulb",
        "vendor": "LIFX Inc.",
        "difficulty": "medium",
        "vulnerabilities": ["HARDCODED_KEY", "UNENCRYPTED_PROTOCOL", "CREDENTIAL_LEAK"],
        "description": "Smart bulb with static auth token and Wi-Fi credentials readable over BLE",
        "exposed_characteristics": ["Color/Power (R/W)", "Auth Token (R)", "Wi-Fi Credentials (R)"],
    },
    {
        "name": "Accu-Chek-Guide",
        "address": "AC:CE:00:01:02:06",
        "device_type": "glucose_meter",
        "vendor": "Roche Diagnostics",
        "difficulty": "medium",
        "vulnerabilities": ["UNENCRYPTED_PROTOCOL", "NO_PAIRING_REQUIRED", "INFORMATION_DISCLOSURE"],
        "description": "Medical glucose meter transmitting patient data and history in plaintext BLE",
        "exposed_characteristics": ["Blood Glucose (R)", "Patient PII (R)", "Medical History (R)", "Insulin Log (R)"],
    },
    {
        "name": "JBL-Tune-510BT",
        "address": "5B:10:00:01:02:07",
        "device_type": "headphones",
        "vendor": "JBL (Harman)",
        "difficulty": "easy",
        "vulnerabilities": ["NO_PAIRING_REQUIRED", "HARDCODED_KEY", "INFORMATION_DISCLOSURE"],
        "description": "Bluetooth headphones with exposed pairing key and paired device history",
        "exposed_characteristics": ["Volume/EQ/ANC (R/W)", "Pairing Key (R)", "Device History (R)"],
    },
]


def get_ble_device_by_name(name: str) -> Optional[Dict]:
    """Return a BLE device record by its advertising name, or None."""
    for dev in BLE_DEVICES:
        if dev["name"] == name:
            return dev
    return None


def get_ble_device_by_address(address: str) -> Optional[Dict]:
    """Return a BLE device record by MAC address, or None."""
    addr_norm = address.upper()
    for dev in BLE_DEVICES:
        if dev["address"].upper() == addr_norm:
            return dev
    return None


def is_lab_ble_address(address: str) -> bool:
    """Return True if the BLE address belongs to a registered lab BLE device."""
    return get_ble_device_by_address(address) is not None


# ===========================================================================
# Lab MAC Address Prefix (Docker default)
# ===========================================================================
# Docker containers typically get MAC addresses with the OUI 02:42:xx:xx:xx:xx
# This is one signal we use to detect lab devices.
LAB_MAC_PREFIX = "02:42:"


# ===========================================================================
# Helper functions
# ===========================================================================

def get_device_by_ip(ip: str) -> Optional[Dict]:
    """Return the lab device record for a given IP, or None."""
    for dev in LAB_DEVICES:
        if dev["ip"] == ip:
            return dev
    return None


def get_subnet_for_ip(ip: str) -> Optional[Tuple[str, Dict]]:
    """Return (subnet_key, subnet_info) for the subnet containing the IP."""
    try:
        ip_obj = ipaddress.ip_address(ip)
    except ValueError:
        return None

    for key, info in LAB_SUBNETS.items():
        try:
            if ip_obj in ipaddress.ip_network(info["cidr"]):
                return key, info
        except ValueError:
            continue
    return None


def is_lab_ip(ip: str) -> bool:
    """Return True if the IP falls inside any of the lab subnets."""
    return get_subnet_for_ip(ip) is not None


def is_lab_mac(mac: str) -> bool:
    """Return True if the MAC matches the Docker container prefix."""
    if not mac:
        return False
    return mac.lower().startswith(LAB_MAC_PREFIX)


def tag_hostname(hostname: str, subnet: Optional[str] = None) -> str:
    """Prefix a hostname with [LAB] (and optionally subnet tag)."""
    if not hostname:
        hostname = "Unknown"
    if hostname.startswith("[LAB"):
        return hostname  # already tagged

    if subnet:
        prefix = f"[LAB:{subnet.upper()}]"
    else:
        prefix = "[LAB]"
    return f"{prefix} {hostname}"


def get_lab_summary() -> Dict:
    """Return a summary of the lab — subnets, devices, vuln counts."""
    by_subnet: Dict[str, List[Dict]] = {k: [] for k in LAB_SUBNETS}
    total_vulns = 0

    for dev in LAB_DEVICES:
        by_subnet[dev["subnet"]].append({
            "ip": dev["ip"],
            "hostname": dev["hostname"],
            "vendor": dev["vendor"],
            "type": dev["device_type"],
            "difficulty": dev["difficulty"],
            "vuln_count": len(dev["vulnerabilities"]),
        })
        total_vulns += len(dev["vulnerabilities"])

    return {
        "total_devices": len(LAB_DEVICES),
        "total_vulnerabilities": total_vulns,
        "total_subnets": len(LAB_SUBNETS),
        "subnets": {
            key: {
                **info,
                "device_count": len(by_subnet[key]),
                "devices": by_subnet[key],
            }
            for key, info in LAB_SUBNETS.items()
        },
    }
