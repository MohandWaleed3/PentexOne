"""
Default Credentials Tester — checks common IoT/router/NAS default passwords.

⚠ AUTHORIZED USE ONLY — run only on devices you own or have written permission to test.

Supports: HTTP Basic Auth, FTP anonymous, Telnet banner check
"""
from __future__ import annotations

import ftplib
import logging
import socket
import time
from typing import Dict, List, Optional
from urllib.request import HTTPBasicAuthHandler, HTTPPasswordMgrWithDefaultRealm, build_opener
from urllib.error import URLError, HTTPError

logger = logging.getLogger(__name__)

# ── Credential dictionary ─────────────────────────────────────────────────────
# (username, password, description)
COMMON_CREDS: List[tuple] = [
    # Generic defaults
    ("admin",    "admin",      "Generic admin/admin"),
    ("admin",    "",           "Admin no password"),
    ("admin",    "password",   "Generic admin/password"),
    ("admin",    "1234",       "Generic admin/1234"),
    ("admin",    "12345",      "Generic admin/12345"),
    ("admin",    "123456",     "Generic admin/123456"),
    ("admin",    "Admin1234",  "Generic admin/Admin1234"),
    ("root",     "root",       "Generic root/root"),
    ("root",     "",           "Root no password"),
    ("root",     "toor",       "Kali default root/toor"),
    ("root",     "1234",       "Generic root/1234"),
    ("user",     "user",       "Generic user/user"),
    ("guest",    "guest",      "Generic guest/guest"),
    ("guest",    "",           "Guest no password"),
    # Hikvision cameras
    ("admin",    "12345",      "Hikvision default"),
    ("admin",    "Admin1234",  "Hikvision newer firmware"),
    # TP-Link routers
    ("admin",    "admin",      "TP-Link default"),
    # D-Link routers
    ("admin",    "",           "D-Link default (no password)"),
    # Netgear
    ("admin",    "password",   "Netgear default"),
    # Asus routers
    ("admin",    "admin",      "Asus default"),
    # Synology NAS
    ("admin",    "admin",      "Synology default"),
    ("admin",    "admin123",   "Synology common"),
    # UBNT/Ubiquiti
    ("ubnt",     "ubnt",       "Ubiquiti default"),
    # Raspberry Pi
    ("pi",       "raspberry",  "Raspberry Pi default"),
    # Cisco
    ("cisco",    "cisco",      "Cisco default"),
    ("admin",    "cisco",      "Cisco admin"),
    # Mikrotik
    ("admin",    "",           "Mikrotik default"),
    # IP cameras (generic Chinese OEM)
    ("admin",    "888888",     "Chinese OEM camera default"),
    ("admin",    "666666",     "Chinese OEM camera default 2"),
    ("888888",   "888888",     "Chinese OEM camera variant"),
    # Industrial / SCADA
    ("operator", "operator",   "Industrial default"),
    ("admin",    "admin1",     "Industrial variant"),
]

# Vendor-specific defaults keyed by hostname/vendor keywords
VENDOR_CREDS: Dict[str, List[tuple]] = {
    "hikvision": [("admin", "12345"), ("admin", "Admin1234")],
    "dahua":     [("admin", "admin"), ("888888", "888888")],
    "tplink":    [("admin", "admin"), ("root", "root")],
    "dlink":     [("admin", ""), ("Admin", "")],
    "netgear":   [("admin", "password"), ("admin", "1234")],
    "synology":  [("admin", "admin"), ("admin", "admin123")],
    "ubiquiti":  [("ubnt", "ubnt")],
    "mikrotik":  [("admin", "")],
    "cisco":     [("admin", "cisco"), ("cisco", "cisco")],
    "nest":      [("admin", "admin"), ("owner", "")],
    "tuya":      [("admin", "admin"), ("admin", "12345")],
}

MAX_ATTEMPTS = 5   # per service, to avoid lockouts
DELAY = 0.8        # seconds between attempts


# ── HTTP Basic Auth ───────────────────────────────────────────────────────────
def _test_http_basic(host: str, port: int, username: str, password: str,
                     timeout: float = 4.0) -> bool:
    url = f"http://{host}:{port}/"
    mgr = HTTPPasswordMgrWithDefaultRealm()
    mgr.add_password(None, url, username, password)
    handler = HTTPBasicAuthHandler(mgr)
    opener = build_opener(handler)
    try:
        resp = opener.open(url, timeout=timeout)
        return resp.status == 200
    except HTTPError as e:
        return e.code == 200
    except (URLError, OSError):
        return False


# ── FTP Anonymous ─────────────────────────────────────────────────────────────
def _test_ftp_anonymous(host: str, port: int, timeout: float = 4.0) -> bool:
    try:
        ftp = ftplib.FTP(timeout=timeout)
        ftp.connect(host, port)
        ftp.login("anonymous", "pentex@test.local")
        ftp.quit()
        return True
    except ftplib.error_perm:
        return False
    except (OSError, ConnectionRefusedError, ftplib.Error):
        return False


# ── Telnet banner check ───────────────────────────────────────────────────────
def _test_telnet_open(host: str, port: int, timeout: float = 3.0) -> bool:
    """Just checks if telnet port accepts a connection and sends data (no login attempt)."""
    try:
        with socket.create_connection((host, port), timeout=timeout) as s:
            s.settimeout(timeout)
            banner = s.recv(256)
            return len(banner) > 0
    except (OSError, ConnectionRefusedError):
        return False


# ── Main tester ───────────────────────────────────────────────────────────────
def test_default_credentials(
    ip: str,
    open_ports: List[int],
    hostname: str = "",
    vendor: str = "",
) -> List[Dict]:
    """
    Attempt default credentials on detected open services.

    Returns a list of finding dicts — empty list if nothing found.
    Each finding has keys: port, service, username, password, severity, description, remediation.
    """
    findings: List[Dict] = []
    label = (hostname or vendor or ip).lower()

    # Build credential list — vendor-specific first, then generic
    vendor_key = next(
        (k for k in VENDOR_CREDS if k in label), None
    )
    creds_to_try = []
    if vendor_key:
        for u, p in VENDOR_CREDS[vendor_key]:
            creds_to_try.append((u, p, f"{vendor_key.title()} default"))
    for u, p, desc in COMMON_CREDS:
        if (u, p, desc) not in creds_to_try and len(creds_to_try) < 40:
            creds_to_try.append((u, p, desc))

    # ── FTP anonymous check ───────────────────────────────────────────────────
    if 21 in open_ports:
        logger.info(f"[DefaultCreds] Testing FTP anonymous on {ip}:21")
        if _test_ftp_anonymous(ip, 21):
            findings.append({
                "port": 21, "service": "ftp",
                "username": "anonymous", "password": "",
                "severity": "CRITICAL",
                "description": "FTP anonymous login accepted — any user can read/write files without credentials.",
                "remediation": "Disable anonymous FTP. Require authenticated access. Use SFTP instead.",
            })

    # ── HTTP Basic Auth check ─────────────────────────────────────────────────
    for port in [p for p in open_ports if p in (80, 8080, 8000, 5000, 8081)]:
        logger.info(f"[DefaultCreds] Testing HTTP Basic Auth on {ip}:{port}")
        attempts = 0
        for username, password, desc in creds_to_try:
            if attempts >= MAX_ATTEMPTS:
                break
            time.sleep(DELAY)
            if _test_http_basic(ip, port, username, password):
                findings.append({
                    "port": port, "service": "http",
                    "username": username, "password": password,
                    "severity": "CRITICAL",
                    "description": f"Default credentials work on HTTP admin interface — {desc}. "
                                   f"Login: {username}/{password or '(empty)'}",
                    "remediation": "Change default credentials immediately. "
                                   "Enforce strong password policy. Disable remote admin if not needed.",
                })
                break  # One confirmed finding per port is enough
            attempts += 1

    # ── Telnet open (no auth check, just exposure) ────────────────────────────
    if 23 in open_ports:
        logger.info(f"[DefaultCreds] Checking Telnet exposure on {ip}:23")
        if _test_telnet_open(ip, 23):
            findings.append({
                "port": 23, "service": "telnet",
                "username": "", "password": "",
                "severity": "CRITICAL",
                "description": "Telnet service is accepting connections. "
                               "Telnet transmits all data (including credentials) in plaintext.",
                "remediation": "Disable Telnet. Replace with SSH. Block port 23 at the firewall.",
            })

    if findings:
        logger.info(f"[DefaultCreds] {len(findings)} finding(s) on {ip}")
    else:
        logger.info(f"[DefaultCreds] No default credential hits on {ip}")

    return findings
