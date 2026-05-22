# PentexOne Feature Audit
## Real vs Stubbed/Fake Features

**Last Updated**: 2026-05-22

---

## ✅ REAL (Fully Implemented & Working)

### Network Scanning
- **WiFi Network Discovery** (`/iot/networks/discover`) ✅
  - Uses system tools: `iwconfig`, `nmcli`, `networksetup`
  - Returns actual SSIDs, encryption types, signal strength
  
- **WiFi Device Scanning** (`/wireless/scan/full/{ip}`) ✅
  - Nmap scanning with version detection
  - Service enumeration
  - Real CVE lookup (offline or API fallback)
  - Actual credential testing (SSH, FTP, HTTP Basic Auth)
  
- **Bluetooth Scanning** (`/wireless/scan/bluetooth`) ✅
  - Uses `hciconfig`, `hcitool`, `bluetoothctl` on Linux
  - Uses `bleak` library for async BLE enumeration
  - Real GATT service enumeration (on capable systems)
  
- **Port Testing** (`/wireless/test/ports/{ip}`) ✅
  - Uses nmap with SYN scans
  - Service banner grabbing
  - Real timeout handling

### Credential Testing
- **SSH Authentication** (`/wireless/test/credentials/{ip}`) ✅
  - Real SSH testing via `paramiko` library
  - Tests actual username/password combos
  - Falls back to key-based auth
  
- **FTP Authentication** ✅
  - Uses `ftplib` for real FTP testing
  - Tests actual login credentials
  
- **HTTP Basic Auth** ✅
  - Uses `requests` library with actual auth testing
  - Tests against real HTTP endpoints
  
- **Combined Credential Test** ✅
  - Parallelizes all auth methods concurrently
  - Reports only actual successful authentications
  - No faking results

### CVE/Vulnerability Detection
- **Offline CVE Lookup** (`cve_lookup.py`) ✅
  - Offline NVD JSON feeds (backend/nvd_offline/)
  - Three-tier: cache → offline index → API fallback
  - Real semantic version matching for CPE ranges
  - 0ms lookups from offline index
  
- **API Fallback** ✅
  - Real NVD API calls when offline feeds unavailable
  - Rate limiting: 6.5s/request without key, 0.7s with key
  - Dynamic lookup cap: 8 CPEs without key, 30 with key
  
- **Cache Layer** ✅
  - SQLite-backed cache with 7-day TTL
  - Reduces repeated API calls

### Hardware Detection
- **WiFi Interface Detection** ✅
  - Real interface enumeration via `iwconfig`/`nmcli`
  
- **Bluetooth Detection** ✅
  - Real Bluetooth device enumeration
  - Proper Linux hciconfig parsing (fixed in this session)
  
- **LoRa Dongle Detection** ✅
  - Real USB device enumeration
  - Keyword matching for DRAGINO, LORAWAN, LORA32, etc.
  
- **Matter Dongle Detection** ✅
  - Real chip ID matching (EFR32MGxx, MGM21x/24x)
  
- **Zigbee/Z-Wave Hardware** ✅
  - Real USB enumeration and permission checking

### Report Generation
- **PDF Report** (`/reports/generate/pdf`) ✅
  - Real PDF generation via `reportlab`
  - Includes scan results, vulnerabilities, risk scores
  - Actual data from database

---

## ⚠️ PARTIALLY IMPLEMENTED (Some Real, Some Fake)

### AI Analysis (`/ai/*`)
- **Anomaly Detection** (`/ai/anomalies`) - PARTIALLY REAL
  - Has actual anomaly detection algorithms (z-score, IQR, Jaccard similarity)
  - Works if database has sufficient scan data
  - **FAKE part**: If no devices scanned yet, returns placeholder anomalies
  
- **Device Analysis** (`/ai/analyze/device/{device_id}`) - PARTIALLY REAL
  - Calls `ai_engine.analyze_single_device()`
  - Has actual device classification and risk prediction
  - **FAKE part**: ML models are trained on hardcoded patterns, not real ML
  
- **Network Analysis** (`/ai/analyze/network`) - PARTIALLY REAL
  - Pattern detection logic exists
  - **FAKE part**: Heavily dependent on collected data; sparse networks get placeholder analysis
  
- **Security Score** (`/ai/security-score`) - PARTIALLY REAL
  - Calculates from actual scan results
  - **FAKE part**: Scoring algorithm is heuristic-based, not ML-based
  
- **Remediation** (`/ai/remediation/{vuln_type}`) - REAL
  - Returns hardcoded remediation steps from `REMEDIATION_DATABASE`
  - Useful but not AI-generated

### Virtual Lab (`/virtual-lab/*`)
- **Lab Status** (`/virtual-lab/status`) - PARTIALLY REAL
  - Returns status of Docker containers (if they exist)
  - **FAKE part**: Doesn't actually run Docker if not installed; returns "not available"
  
- **Lab Devices** (`/virtual-lab/devices`) - PARTIALLY FAKE
  - Returns virtual network device list
  - **FAKE part**: Devices are simulated; no real Docker containers running attacks
  
- **Virtual WiFi Lab** - FAKE (No Docker Setup)
  - UI shows WiFi lab features (isolated subnet, simulated devices)
  - **No Docker containers actually deployed on Pi**
  - Would need docker-compose and significant setup
  
- **Virtual BLE Lab** - FAKE (No Docker Setup)
  - UI shows BLE lab features
  - **No actual BLE device simulation**
  
- **Quick Scan in Virtual Lab** - FAKE
  - Returns simulated scan results
  - Not connected to real devices

### Attack Scenarios (`/attack-scenarios/*`)
- **Scenario List** (`/attack-scenarios/`) - REAL
  - Returns hardcoded learning scenarios (WiFi hacking CTF challenges)
  
- **Run Scenario** (`/attack-scenarios/{scenario_id}/run`) - PARTIALLY REAL
  - Scenarios are interactive learning challenges
  - Uses real HTTP probes against the virtual lab
  - **FAKE part**: Target is a virtual lab service, not real devices; results are scripted
  
- **Hints & Scoring** - PARTIALLY REAL
  - Hints are hardcoded per scenario
  - Scoring is based on task completion, not real exploitation
  
- **Learning Path** - PARTIALLY FAKE
  - Returns learning path structure
  - **FAKE part**: Doesn't actually track user progress persistently

---

## ❌ FAKE/STUBBED (Not Implemented or Non-Functional)

### RFID/Access Control (`/access-control/*`)
- **RFID Scanning** (`/access-control/scan`) - FAKE
  - Returns simulated RFID card data
  - **No real RFID hardware support** (PN532 reader, etc.)
  - Has fallback logic but RFID hardware is not integrated
  - Generates fake card UUIDs, encryption types, vulnerabilities
  
- **RFID Card Analysis** (`/access-control/analyze/{card_id}`) - FAKE
  - Analyzes simulated card data
  - **Real data**: Only if you scanned with real hardware (not implemented)
  
- **RFID Attacks** (`/access-control/attack/simulate`) - FAKE
  - Simulates RFID cloning, replay attacks, etc.
  - **No actual exploitation** (for obvious security reasons)
  - Returns hardcoded attack scenarios

### Deauth Attack Detection (`/wireless/deauth/*`)
- **Deauth Monitoring** (`/wireless/deauth/start`) - PARTIALLY REAL
  - **REAL part**: Uses scapy to sniff actual WiFi frames
  - **REQUIRES**: Monitor mode on wireless interface (not auto-enabled)
  - **FAKE part**: On most systems, monitor mode setup fails silently; endpoint appears to work but captures nothing
  
- **Deauth Status** - RETURNS REAL DATA
  - **But**: Most networks can't capture due to monitor mode not being set up
  - Works in CTF/lab environments; rarely works on real Pi

### Zigbee Scanning (`/iot/scan/zigbee`)
- **FAKE/NON-FUNCTIONAL**
  - Requires killerbee library (disabled for Python 3.13 compatibility)
  - Hardware support mentioned but not fully integrated
  - Returns error or simulation if hardware unavailable

### Z-Wave Scanning (`/iot/scan/zwave`)
- **FAKE/NON-FUNCTIONAL**
  - python-openzwave not included in requirements
  - Hardware not integrated
  - Returns placeholder response

### Thread Scanning (`/iot/scan/thread`)
- **FAKE/NON-FUNCTIONAL**
  - No Thread-specific scanning logic
  - Hardware detection exists but no protocol scanning
  - Returns stub response

### TLS/SSL Checking (`/wireless/tls/check/{host}`)
- **PARTIALLY FAKE/INCOMPLETE**
  - Endpoint exists in router but implementation may be incomplete
  - Real TLS checking libraries (cryptography, ssl) available but usage unclear

---

## 📊 Summary Table

| Feature | Status | Notes |
|---------|--------|-------|
| WiFi scanning | ✅ REAL | Fully functional, real data |
| Bluetooth scanning | ✅ REAL | Works with bleak library |
| Nmap port scanning | ✅ REAL | Real service enumeration |
| CVE lookup (offline) | ✅ REAL | 0ms lookups, three-tier cache |
| Credential testing | ✅ REAL | SSH, FTP, HTTP auth tested |
| PDF reports | ✅ REAL | reportlab generation |
| Anomaly detection | ⚠️ PARTIAL | Real algo but placeholder results if no data |
| Device/Network AI | ⚠️ PARTIAL | Heuristic-based, not ML-based |
| Virtual WiFi lab | ❌ FAKE | No Docker, no simulation |
| Virtual BLE lab | ❌ FAKE | No actual BLE simulation |
| Attack scenarios | ⚠️ PARTIAL | Learning challenges, but CTF-like not real exploitation |
| RFID scanning | ❌ FAKE | Simulated data only |
| Zigbee scanning | ❌ FAKE | Not integrated, lib disabled |
| Z-Wave scanning | ❌ FAKE | Not integrated |
| Thread scanning | ❌ FAKE | Not integrated |
| Deauth monitoring | ⚠️ PARTIAL | Real if monitor mode set up; usually fails silently |
| TLS checking | ❓ UNCLEAR | Endpoint exists, implementation unclear |

---

## 🎯 Recommendation

### For Smart Home/IoT Vulnerability Detection (Your Use Case)
**What you CAN trust and use immediately on Pi 5**:
- ✅ WiFi network discovery and device scanning
- ✅ Port scanning and service enumeration
- ✅ Real credential testing
- ✅ CVE lookup and vulnerability reports
- ✅ Bluetooth enumeration and scanning
- ✅ Hardware detection (LoRa, Matter, etc.)

**What to avoid or understand limitations**:
- ⚠️ AI Analysis — useful heuristic-based insights, not ML predictions
- ⚠️ Anomaly detection — needs baseline data first
- ❌ RFID features — skip unless you install real hardware
- ❌ Virtual lab — would need Docker; not Pi-compatible
- ⚠️ Deauth detection — requires monitor mode setup (advanced)
- ❌ Zigbee/Z-Wave — not functional without extra setup

### Next Steps
If you want to improve detection for your smart home focus:
1. **TLS/SSL scanning** — add comprehensive cert validation for HTTPS devices
2. **Device-specific defaults** — expand credential list for common manufacturers
3. **BLE security** — improve GATT permissions and pairing analysis
4. **Firmware tracking** — flag outdated device versions

Would you like me to implement any of these?
