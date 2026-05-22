"""
Default credentials dictionary used by the credential-testing flow in
routers/wifi_bt.py. Only data here — the actual probing logic (SSH/FTP/
HTTP Basic) lives next to the scan code where it's used.

⚠ AUTHORIZED USE ONLY — credential testing must only run against devices
you own or have written permission to test.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

# Common defaults across most consumer IoT — ordered roughly by frequency.
# Format: (username, password, description)
COMMON_CREDS: List[Tuple[str, str, str]] = [
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
    ("admin",    "admin123",   "Synology common"),
    ("ubnt",     "ubnt",       "Ubiquiti default"),
    ("pi",       "raspberry",  "Raspberry Pi default"),
    ("cisco",    "cisco",      "Cisco default"),
    ("admin",    "cisco",      "Cisco admin"),
    ("admin",    "888888",     "Chinese OEM camera default"),
    ("admin",    "666666",     "Chinese OEM camera default 2"),
    ("888888",   "888888",     "Chinese OEM camera variant"),
    ("operator", "operator",   "Industrial default"),
    ("support",  "support",    "Network gear support account"),
]

# Vendor-specific defaults tried first when the device's vendor/hostname matches.
VENDOR_CREDS: Dict[str, List[Tuple[str, str]]] = {
    "hikvision": [("admin", "12345"),     ("admin", "Admin1234")],
    "dahua":     [("admin", "admin"),     ("888888", "888888")],
    "tplink":    [("admin", "admin"),     ("root",   "root")],
    "tp-link":   [("admin", "admin"),     ("root",   "root")],
    "dlink":     [("admin", ""),          ("Admin",  "")],
    "d-link":    [("admin", ""),          ("Admin",  "")],
    "netgear":   [("admin", "password"),  ("admin",  "1234")],
    "synology":  [("admin", "admin"),     ("admin",  "admin123")],
    "ubiquiti":  [("ubnt",  "ubnt")],
    "mikrotik":  [("admin", "")],
    "cisco":     [("admin", "cisco"),     ("cisco",  "cisco")],
    "nest":      [("admin", "admin"),     ("owner",  "")],
    "tuya":      [("admin", "admin"),     ("admin",  "12345")],
    "samsung":   [("admin", "0000"),      ("admin",  "tlbb15")],
}


def creds_for_device(hostname: str = "", vendor: str = "") -> List[Tuple[str, str]]:
    """Return a credential list ordered vendor-first, then common defaults."""
    label = f"{hostname} {vendor}".lower()
    out: List[Tuple[str, str]] = []
    for key, pairs in VENDOR_CREDS.items():
        if key in label:
            out.extend(pairs)
    seen = set(out)
    for u, p, _ in COMMON_CREDS:
        if (u, p) not in seen:
            out.append((u, p))
            seen.add((u, p))
    return out
