#!/usr/bin/env python3
"""
Pre-download CVEs for common IoT/network services via NVD API 2.0.
Run this ONCE at home while connected to the internet.
Results saved to nvd_offline/common_iot_cves.json — field scans work offline.

Usage:
    python3 scripts/cache_nvd_online.py
    NVD_API_KEY=your_key python3 scripts/cache_nvd_online.py
"""

import json
import os
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("Run inside the venv: source venv/bin/activate")

NVD_API = "https://services.nvd.nist.gov/rest/json/cves/2.0"
OUT_DIR = Path(__file__).parent.parent / "nvd_offline"
OUT_DIR.mkdir(exist_ok=True)

API_KEY = os.environ.get("NVD_API_KEY", "")
RATE    = 0.7 if API_KEY else 6.5          # seconds between requests
HEADERS = {"User-Agent": "PentexOne-Scanner/1.0"}
if API_KEY:
    HEADERS["apiKey"] = API_KEY
    print(f"[+] Using NVD API key — rate: {RATE}s/req")
else:
    print(f"[!] No API key — rate: {RATE}s/req (slower). Set NVD_API_KEY to speed up.")

# Common services that nmap detects and reports CPEs for
PRODUCTS = [
    # (vendor, product) — must match NVD CPE naming exactly
    ("openbsd",     "openssh"),
    ("apache",      "http_server"),
    ("nginx",       "nginx"),
    ("vsftpd",      "vsftpd"),
    ("proftpd",     "proftpd"),
    ("samba",       "samba"),
    ("mysql",       "mysql"),
    ("postgresql",  "postgresql"),
    ("redis",       "redis"),
    ("mongodb",     "mongodb"),
    ("lighttpd",    "lighttpd"),
    ("eclipse",     "mosquitto"),          # MQTT broker
    ("matt_johnston","dropbear_ssh"),       # common on routers/cameras
    ("busybox",     "busybox"),
    ("hikvision",   "ip_camera_firmware"),
    ("tp-link",     "archer_firmware"),
    ("dlink",       "dir-600_firmware"),
    ("netgear",     "r6700_firmware"),
    ("mikrotik",    "routeros"),
    ("cisco",       "ios"),
    ("telnetd",     "telnetd"),
    ("isc",         "bind"),               # DNS
    ("isc",         "dhcp"),
    ("exim",        "exim"),
    ("postfix",     "postfix"),
    ("dovecot",     "dovecot"),
    ("openssl",     "openssl"),
    ("php",         "php"),
    ("python",      "python"),
]


def fetch_cves(vendor: str, product: str) -> list:
    # virtualMatchString does prefix matching across all CPEs — wildcards
    # in vendor/product are NOT allowed by cpeName, but virtualMatchString
    # finds any CVE referencing a CPE that starts with this string.
    match_str = f"cpe:2.3:a:{vendor}:{product}"
    all_items = []
    start = 0

    while True:
        params = {"virtualMatchString": match_str, "resultsPerPage": 2000, "startIndex": start}
        try:
            resp = requests.get(NVD_API, params=params, headers=HEADERS, timeout=30)
        except requests.RequestException as e:
            print(f"    ✗ Network error: {e}")
            break

        if resp.status_code == 403:
            print("    ✗ Rate limited — sleeping 35s")
            time.sleep(35)
            continue
        if resp.status_code != 200:
            print(f"    ✗ HTTP {resp.status_code}")
            break

        data = resp.json()
        items = data.get("vulnerabilities", [])
        all_items.extend(items)

        total = data.get("totalResults", 0)
        start += len(items)
        if start >= total or not items:
            break
        time.sleep(RATE)

    return all_items


def main():
    all_vulns = []
    failed = []

    for vendor, product in PRODUCTS:
        print(f"[*] {vendor}/{product} ...", end=" ", flush=True)
        items = fetch_cves(vendor, product)
        print(f"{len(items)} CVEs")
        all_vulns.extend(items)
        time.sleep(RATE)

    # Deduplicate by CVE ID
    seen = set()
    unique = []
    for v in all_vulns:
        cve_id = v.get("cve", {}).get("id") or v.get("id", "")
        if cve_id and cve_id not in seen:
            seen.add(cve_id)
            unique.append(v)

    out_file = OUT_DIR / "common_iot_cves.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({"vulnerabilities": unique}, f)

    size_mb = out_file.stat().st_size / 1_000_000
    print(f"\n✓ {len(unique)} unique CVEs → {out_file} ({size_mb:.1f} MB)")
    print("Restart the backend to load the offline index:")
    print("  pkill -f uvicorn && uvicorn main:app --host 0.0.0.0 --port 8000 --reload")


if __name__ == "__main__":
    main()
