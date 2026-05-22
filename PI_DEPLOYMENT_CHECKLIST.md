# PentexOne Pi 5 Deployment Checklist

**Status**: Ready for Raspberry Pi 5 deployment  
**Date**: 2026-05-22  
**Target**: Raspberry Pi 5 (4GB RAM)

---

## ✅ What Was Completed

### 1. Code Improvements
- [x] **Offline CVE Lookup** (`backend/cve_lookup.py`)
  - Three-tier lookup: SQLite cache → offline NVD index → online API fallback
  - Semantic version matching for CPE ranges
  - 0ms lookups from offline index vs 6.5s+ from API
  
- [x] **Real Credential Testing** (`backend/routers/wifi_bt.py`)
  - SSH auth via paramiko
  - FTP auth via ftplib  
  - HTTP Basic Auth via requests
  - Parallelized testing (gather all probes concurrently)
  
- [x] **Nmap Performance Tuning** (`backend/nmap_scanner.py`)
  - Curated port list (~130 IoT ports instead of top-1000)
  - Aggressive timing: --min-rate 1000, --max-retries 1, --host-timeout 90s
  - Environment variable override: PENTEX_NMAP_MIN_RATE
  
- [x] **Hardware Detection** (`backend/routers/iot.py`)
  - Fixed Linux Bluetooth detection (proper per-line parsing)
  - Added LoRa dongle detection (DRAGINO, LORAWAN, LORA32, etc.)
  - Added Matter dongle detection (EFR32MGxx, MGM21x/24x chip IDs)

- [x] **Progress Callbacks** (`backend/routers/wifi_bt.py`)
  - Streaming CVE lookup progress (60→90%) during scan
  
- [x] **Dependencies** (`backend/requirements.txt`)
  - Added paramiko>=3.4.0 (SSH testing)
  - Added requests>=2.31.0 (HTTP auth)
  - Added urllib3>=2.0.0 (HTTPS, with unverified context support)

### 2. Pi Setup Infrastructure
- [x] **Enhanced Setup Script** (`backend/rpi_setup.sh`)
  - One-shot setup: apt update/upgrade + pip install + nmap caps + BT perms
  - Nmap capabilities: setcap CAP_NET_RAW,CAP_NET_ADMIN (SYN scans without sudo)
  - Bluetooth group membership: usermod -aG bluetooth $USER
  - Environment variable setup: .env template with PENTEX_NMAP_MIN_RATE, NVD_API_KEY
  - NVD feeds auto-detection and guidance
  
- [x] **NVD Download Script** (`backend/scripts/download_nvd_feeds.sh`)
  - Primary source: NIST official JSON feeds
  - Fallback: GitHub mirror (no Cloudflare)
  - Auto-selects last 6 years or custom range
  - Output: `backend/nvd_offline/` (ready to use)
  
- [x] **Documentation** (`RASPBERRY_PI_SETUP.md`)
  - New section: CVE Database Setup with NVD offline flows
  - New section: Environment Variables (PENTEX_NMAP_MIN_RATE, NVD_API_KEY, etc.)
  - Explains CPE lookup limits (8 without key, 30 with key)

---

## 📋 Deployment Steps (On Pi 5)

### Step 1: Clone and Initial Setup
```bash
cd ~
git clone https://github.com/your-repo/pentexone.git
cd pentexone/backend
sudo ./rpi_setup.sh
```

**What this does**:
- Updates apt packages
- Installs system deps (python3, nmap, bluez, etc.)
- Creates Python venv and installs requirements
- Enables Bluetooth
- Creates .env with template
- Configures Nmap capabilities (no sudo needed for scans)
- Adds user to bluetooth group

**Output**: Prints next steps and system info

### Step 2: Download NVD Feeds (Optional but Recommended)
```bash
cd ~/pentexone/backend
chmod +x scripts/download_nvd_feeds.sh
./scripts/download_nvd_feeds.sh
```

**What this does**:
- Downloads 6 years of CVE data (~500MB)
- Stores in `backend/nvd_offline/` (ready to use)
- Takes 5-10 minutes on Pi 5 with good internet
- Backend auto-falls back to API if feeds unavailable

**Skip if**: You want to start scanning immediately (first scan will use API as fallback)

### Step 3: Configure Credentials & Optimize
Edit `.env`:
```bash
nano .env
```

**At minimum, change**:
```bash
PENTEX_PASSWORD=choose_a_strong_password
```

**Optional tuning** (add/uncomment):
```bash
# For WiFi with packet loss or Pi 3
PENTEX_NMAP_MIN_RATE=500

# For NVD API key (if obtained from nvd.nist.gov)
NVD_API_KEY=your_api_key_here

# To force offline-only (no API fallback)
# PENTEX_NVD_OFFLINE_ONLY=1
```

### Step 4: Log Out and Back In (Bluetooth)
Bluetooth group membership requires new login session:
```bash
exit
# SSH back in or open new terminal
```

Or immediately activate the group:
```bash
newgrp bluetooth
```

### Step 5: Start the Service
```bash
sudo systemctl start pentexone
sudo systemctl status pentexone
```

Check logs:
```bash
sudo journalctl -u pentexone -f
```

Look for: `Application startup complete` message

### Step 6: Access Dashboard
Open browser: `http://[raspberry-pi-ip]:8000`

Find IP:
```bash
hostname -I
```

Default login: `admin` / (password from .env)

---

## 📊 Expected Performance (Pi 5)

### WiFi Scanning
- Network discovery: 5-10s (depends on network size)
- Per-device Nmap scan: 10-15s (curated port list)
- Credential testing: 5-20s (parallel auth probes)
- CVE lookup: 2-5s (offline) or 20-30s (API fallback)
- **Total per device**: 30-60s

### Bluetooth Scanning
- Device discovery: 10-15s
- BLE services enumeration: 5-10s per device
- CVE lookup: 2-5s (offline) or 20-30s (API fallback)
- **Total per device**: 20-50s

### Full Network Report (10 devices)
- ~5-10 minutes (parallel scans)
- Depends on network size, device responsiveness, CVE lookup availability

---

## 🔍 Quick Diagnostics

### Test Nmap (no sudo needed)
```bash
nmap -sS localhost
# Should complete without "requires root" error
```

### Test Offline CVE Index
```bash
cd ~/pentexone/backend
source venv/bin/activate
python3 << 'EOF'
from cve_lookup import get_cve_lookup_service
service = get_cve_lookup_service()
cves = service.lookup_cves_for_cpe("cpe:2.3:a:apache:log4j:*:*:*:*:*:*:*:*")
print(f"Found {len(cves)} CVEs for Log4j")
EOF
```

Expected: `Found N CVEs for Log4j` (should be instant, not 6 seconds)

### Test Bluetooth
```bash
hciconfig
# Should show at least one hci device
```

### Test SSH Auth (against testable host)
```bash
cd ~/pentexone/backend
source venv/bin/activate
python3 << 'EOF'
import asyncio
from routers.wifi_bt import _try_ssh_auth

result = asyncio.run(_try_ssh_auth("192.168.1.1", "admin", "admin"))
print(f"SSH auth result: {result}")
EOF
```

---

## ⚠️ Common Issues & Fixes

### "nmap: you don't have permission to sniff on that device"
**Cause**: Capabilities not set  
**Fix**:
```bash
sudo setcap cap_net_raw,cap_net_admin=eip /usr/bin/nmap
```

### Bluetooth scanning fails
**Cause**: User not in bluetooth group  
**Fix**:
```bash
sudo usermod -aG bluetooth $USER
# Then log out and back in
```

### "Cloudflare check failed" or NVD API times out
**Expected**: Normal after first few requests (API rate-limits)  
**Fix**: Use offline feeds or wait 24h for API key approval

### CVE lookup very slow on first scan
**Cause**: No offline feeds; API fallback is 6.5s/request  
**Fix**: Download feeds with `./scripts/download_nvd_feeds.sh`

### Python dependency conflicts
**Cause**: System Python vs venv conflict  
**Fix**:
```bash
cd ~/pentexone/backend
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 📚 Next Resources

- Full setup guide: `RASPBERRY_PI_SETUP.md`
- Architecture docs: Check `backend/cve_lookup.py` docstrings
- NVD feed format: https://nvd.nist.gov/developers/data-feeds
- Nmap options: `man nmap` on Pi or `nmap -h`

---

## 🚀 Auto-Start on Boot

Already configured by `rpi_setup.sh`:
```bash
sudo systemctl enable pentexone
# PentexOne now starts automatically on reboot
```

Check status anytime:
```bash
sudo systemctl status pentexone
```

View recent logs:
```bash
sudo journalctl -u pentexone --since "10 minutes ago"
```

---

**Ready to deploy! 🍓**
