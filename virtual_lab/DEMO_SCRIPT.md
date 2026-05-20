# PentexOne — Graduation Defense Demo Script

This script guides you through a 10–15 minute live demonstration of the PentexOne
Virtual Lab during your graduation committee presentation.

Rehearse this at least twice before the defense so every step is muscle memory.

---

## Pre-Demo Checklist (30 minutes before)

- [ ] Backend running: `python3 main.py` (or `uvicorn main:app --port 8000`)
- [ ] Dashboard open in browser: http://localhost:8000/dashboard/index.html
- [ ] Docker running: `docker ps` shows 7 containers OR ready to start
- [ ] Terminal open with `virtual_lab/` as working directory
- [ ] Browser zoom at 100% (committee can see the full layout)
- [ ] Second terminal open for curl commands
- [ ] Network connected (if demo machine and lab are on same Wi-Fi)

---

## Part 1 — Introduction (2 minutes)

**Say:** "PentexOne is an IoT Security Auditor running on Raspberry Pi.
Today I will demonstrate it against a fully simulated IoT network — 7 vulnerable
devices across 3 isolated subnets, plus 5 Bluetooth peripherals.
Everything you will see are real HTTP and TCP requests hitting real containers."

Click the **Virtual Lab** nav item in the sidebar.

**Show:** The Lab Control Panel — two status cards (Wi-Fi Lab, BLE Lab), both STOPPED.

---

## Part 2 — Start the Lab (1 minute)

**In terminal 1:**
```bash
cd virtual_lab/
./start_lab.sh
```

**Say:** "This starts 7 Docker containers — each simulating a real vulnerable
IoT device on its own isolated subnet. The three subnets mirror a real deployment:
an IoT zone, a guest network, and a corporate LAN."

Wait for containers to start (~15 seconds), then click **Refresh** in the Virtual Lab UI.

**Show:** Status dots turn green. Architecture grid shows 3 subnets with their devices.

**Say (pointing to subnet grid):**
"Blue subnet — IoT devices: camera, MQTT broker, router, smart plug, thermostat.
Yellow subnet — guest network: smart TV.
Red subnet — corporate LAN: NAS server with sensitive data."

---

## Part 3 — Device Discovery (1 minute)

Click **Inject Wi-Fi Devices** button.

**Say:** "In quick-scan mode, PentexOne injects all known lab devices instantly
with their vulnerability profiles — useful for demos. In production, it uses nmap
to actively scan the subnet."

Click the **Dashboard** nav item. Show the devices table — 7 devices now appear,
all tagged [LAB:IOT], [LAB:GUEST], [LAB:CORPORATE].

**Say:** "Every device is tagged with its subnet zone. The risk scores are
pre-computed from the vulnerability registry — CRITICAL devices appear in red."

Click back to **Virtual Lab**.

---

## Part 4 — Attack Scenario: Default Credentials (2 minutes)

**Say:** "Let me demonstrate the first attack — default credentials on the Hikvision
IP camera. This is the most common real-world IoT vulnerability."

In the Attack Scenarios panel, click the **Book icon** next to wifi-01.

**Show the Tutorial modal:**
"The tutorial explains the concept — Mirai botnet exploited exactly this vulnerability
across 600,000 cameras. The CVSS score is 9.8 — critical. Hikvision's CVE-2017-7921."

Close the tutorial. Click **Run** next to wifi-01.

**Show step-by-step evidence:**
- Step 1: GET / → HTTP 200 — login page detected
- Step 2: GET /admin/ with admin:admin → HTTP 200 — ACCESS GRANTED
- Step 3: GET /ISAPI/System/deviceInfo → firmware version extracted

**Say:** "PentexOne sent real HTTP requests to the container. Admin access was granted
in under 2 seconds using the factory default password. The ISAPI response reveals
the exact firmware version — enabling targeted exploit selection."

---

## Part 5 — Attack Scenario: Debug Interface (2 minutes)

Click **Run** next to wifi-05 (Nest Thermostat).

**Show the evidence:**
- Step 2: GET /debug → debug interface confirmed
- Step 3: GET /debug/dump → Wi-Fi password, OAuth token, admin PIN in plaintext

**Say:** "This is a hard scenario — difficulty multiplier 2x. The debug interface
was left active in production firmware. One HTTP request returns the home Wi-Fi
password, an OAuth token for the Google API, and the admin PIN.
An attacker with this information can join the home network and control the thermostat remotely."

Click **Get Hint** → show hint 1 to explain the hint system.

Click **Submit Score:**
```
{elapsed_seconds: 45, hints_used: 1, success: true}
```

**Show:** Grade A, score breakdown — hint penalty, difficulty multiplier applied.

**Say:** "The scoring system grades each attack — deducting points for hints used
and time taken. This makes it a complete training environment for security students."

---

## Part 6 — MQTT Injection (1 minute)

Click **Run** next to wifi-02 (MQTT Broker).

**Show:**
- TCP connect to port 8051 — connection accepted
- Anonymous CONNECT → CONNACK 0x00 — accepted without credentials
- Subscribe to '#' — all topics now visible
- Publish spoofed temperature 999.9 to sensor/temperature

**Say:** "The MQTT broker accepts anonymous connections. Any device on the network
can read all sensor data and inject fake commands. This is how attackers manipulate
industrial sensor networks — change a temperature reading, trigger a false alarm,
or send a reboot command to every device subscribed to that topic."

---

## Part 7 — NAS Shadow File (1 minute)

Click **Run** next to wifi-07 (Synology NAS).

**Show:**
- /webapi/query.cgi returns SMBv1 enabled, FTP anonymous, DSM 6.2.4
- /shared/backup/etc-shadow.bak → downloaded, shows SHA-512 password hashes
- Hashcat simulation: admin hash cracked → admin123

**Say:** "The corporate NAS has three critical issues: SMBv1 enabled — vulnerable to
EternalBlue. Anonymous FTP. And a backup of /etc/shadow in a web-accessible folder.
Without any authentication, we downloaded the password hashes for every system account."

---

## Part 8 — BLE Devices (1 minute)

**Say:** "PentexOne also covers Bluetooth Low Energy. The BLE lab simulates 5
real-world vulnerable peripherals."

Scroll to the BLE Peripherals section. Point to the 5 device cards.

Click **Inject BLE Devices**.

Click **Run** next to ble-01 (August Smart Lock).

**Show:** Simulated BLE attack — connect without pairing, write 0x01 to lock command,
state changes to UNLOCKED, access log with PINs readable.

**Say:** "Smart locks that use 'Just Works' BLE pairing accept commands from any
nearby device — no authentication required. This is a physical security bypass
achievable from a smartphone app or a Raspberry Pi."

---

## Part 9 — Activity Log & Scoring (1 minute)

Scroll to the Activity Log.

**Show:** All events logged — LAB_START, QUICK_SCAN, ATTACK_SIMULATED entries.

**Say:** "Every action is logged with timestamps — who did what, which device was
targeted, what protocol was used. This is essential for penetration testing reports."

Scroll to Learning Path.

**Show:** Easy/Medium/Hard progression, completed scenarios marked with grade.

**Say:** "The learning path guides trainees from easy to hard scenarios.
Total possible score is 2,300 points across all 12 attacks.
This makes PentexOne a complete IoT security training platform — not just an auditing tool."

---

## Part 10 — Architecture Summary (1 minute)

Click **Dashboard** → show devices table with all [LAB] devices.

Click on one device (e.g., Hikvision) to open the details panel.

**Show:** Risk score, open ports, vulnerabilities list, Deep Port Scan and Test Default Creds buttons.

**Say:** "The core scanning engine — nmap for Wi-Fi, bleak for BLE — integrates
seamlessly with the lab. Any device discovered by a real scan on the lab subnets
is automatically tagged, risk-scored, and added to the database."

---

## Anticipated Committee Questions

**Q: Why Docker and not real devices?**
A: Docker provides reproducibility, isolation, and zero hardware cost. The same
vulnerabilities exist — the HTTP/TCP services are functionally identical to the real firmware.
For a thesis demonstration, reproducibility is more important than physical authenticity.

**Q: Is the AI engine real?**
A: Yes — it is a rule-based scoring engine with VULNERABILITY_PATTERNS defined in
ai_engine.py. It produces a composite 0–100 risk score using statistical weighting
of vulnerability severity. No external ML libraries are used — it runs entirely on
the Raspberry Pi's CPU without a GPU.

**Q: Does PentexOne work on real networks?**
A: Yes. The Wi-Fi scanner uses python-nmap, the BLE scanner uses bleak — both
work against real devices. The Virtual Lab is an additional mode for training and demos.

**Q: What about false positives in the scanner?**
A: The lab registry cross-references discovered IPs with the known device registry.
Only IPs in the registered lab subnets get [LAB] tags. Real network devices are
treated normally through the main scanning pipeline.

**Q: How does BLE scanning work without the bumble simulator?**
A: PentexOne's existing bleak-based scanner discovers any real BLE device. The
bumble simulator is for the virtual lab only — it advertises over a real Bluetooth
adapter so bleak can find it exactly like a real device. Without bumble, BLE inject
mode populates the database directly from the registry.

**Q: What is the maximum range for BLE scanning?**
A: BLE class 1 adapters reach ~100 meters. The Raspberry Pi's built-in adapter
is class 2 (~10 meters). For longer-range auditing, a USB BLE adapter (e.g.,
ASUS BT500) can be plugged in.

---

## Timing Guide

| Part | Content | Target Time |
|---|---|---|
| 1 | Introduction | 2 min |
| 2 | Start lab | 1 min |
| 3 | Device discovery | 1 min |
| 4 | Default credentials attack | 2 min |
| 5 | Debug interface + scoring | 2 min |
| 6 | MQTT injection | 1 min |
| 7 | NAS shadow file | 1 min |
| 8 | BLE devices | 1 min |
| 9 | Activity log + learning path | 1 min |
| 10 | Architecture wrap-up | 1 min |
| **Total** | | **~13 min** |

If time is short, skip parts 6 and 8. Always end with the Activity Log and Scoring —
it makes the educational angle clear to the committee.

---

## Emergency Fallbacks

**If Docker won't start in time:**
Pre-inject devices via the API before the demo:
```bash
curl -X POST http://localhost:8000/lab/quick-scan
curl -X POST http://localhost:8000/lab/ble-inject
```
The attack scenarios and tutorial system still work without containers —
BLE scenarios are always simulated server-side regardless.

**If the backend crashes:**
```bash
cd backend/
python3 main.py
```
Wait 5 seconds, refresh the browser. All data is persisted in SQLite.

**If the browser crashes:**
Navigate to http://localhost:8000 — it auto-redirects to the dashboard.
The Virtual Lab nav item is always visible.

**If the committee asks to see a raw API call:**
Open a new terminal tab and run:
```bash
curl http://localhost:8000/attacks/wifi-05/tutorial | python3 -m json.tool
curl -X POST http://localhost:8000/attacks/wifi-07/run | python3 -m json.tool
```
This shows the FastAPI backend is real and the responses are structured JSON.
