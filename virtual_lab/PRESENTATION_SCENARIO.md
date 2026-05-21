# PentexOne — Presentation Scenario: "The Smart Home Heist"

A focused 5–7 minute live scenario that tells one coherent attack story instead of
running through every device. Designed for a graduation committee, a sponsor demo,
or any short technical pitch where you need narrative + impact, not exhaustive coverage.

> Story angle: a single attacker in a parked car across the street compromises a
> smart home and pivots into the homeowner's corporate NAS. PentexOne audits every
> step. Three devices, one continuous attack chain, full kill-chain coverage.

---

## The Story (one paragraph — read this before you present)

A homeowner installs three "smart" devices: a Hikvision IP camera at the front
door, a Nest thermostat in the living room, and a Synology NAS in the home office
holding work backups. The attacker never touches the house. From the curb they
join the home Wi-Fi (extracted from the thermostat's debug interface), log into
the camera with factory credentials, then pivot to the NAS and walk away with the
corporate password database. PentexOne reproduces this chain end-to-end against
the virtual lab in under three minutes of attack runtime.

---

## Pre-Demo State (60 seconds before you start talking)

```bash
cd virtual_lab/ && ./start_lab.sh
curl -X POST http://localhost:8000/lab/quick-scan
```

Open: http://localhost:8000/dashboard/index.html → click **Virtual Lab**.
Confirm: Wi-Fi Lab status = RUNNING, 7 devices in the device table.

---

## Act 1 — Reconnaissance (60 seconds)

**Say:**
> "The attacker starts with one assumption only: there are IoT devices on this
> network. PentexOne mirrors what a real attacker does — passive discovery first."

**Show:** Dashboard → devices table sorted by risk score.

**Point at the three CRITICAL rows:**
- Hikvision Camera — `172.30.10.50` — risk 92
- Nest Thermostat — `172.30.10.54` — risk 95
- Synology NAS    — `172.30.30.50` — risk 88

**Say:**
> "Three red rows. Each one is a separate subnet — IoT, IoT, and corporate.
> The attacker doesn't pick a random target; they pick the chain that leads
> from the easiest device to the most valuable data."

---

## Act 2 — Initial Foothold via the Thermostat (90 seconds)

**Why this device first:** the Nest debug interface leaks the home Wi-Fi password.
Without that, the attacker can't reach anything.

Click **Run** next to `wifi-05` (Nest Thermostat — Debug Credential Dump).

**Show evidence (read the JSON aloud):**
- `GET /debug` → debug interface confirmed in production firmware
- `GET /debug/dump` → response body contains:
  - `wifi_password: HomeNet2024!`
  - `oauth_token: ya29.a0AfH6...`
  - `admin_pin: 4421`

**Say:**
> "One HTTP request. No authentication. The thermostat hands over the home
> Wi-Fi password, a Google OAuth token, and the admin PIN. The attacker is now
> on the home network as a trusted device — every firewall rule based on
> 'only allow internal traffic' just stopped protecting anything."

**CVSS context:** 9.1 — CWE-489 (Active Debug Code).

---

## Act 3 — Lateral Movement to the Camera (60 seconds)

**Why this device next:** the camera gives the attacker eyes inside the home
*and* a stable foothold on the IoT subnet — quieter than the thermostat which
might be patched.

Click **Run** next to `wifi-01` (Hikvision Camera — Default Credentials).

**Show evidence:**
- `GET /` → HTTP 200, login page detected
- `GET /admin/` with `admin:admin` → HTTP 200, ACCESS GRANTED
- `GET /ISAPI/System/deviceInfo` → firmware `V5.4.5 build 170124`

**Say:**
> "Factory password, never changed. Same vulnerability Mirai used to build a
> 600,000-camera botnet in 2016. The ISAPI response gives us the exact firmware
> version — that's the input to a targeted CVE search. From the attacker's car,
> they now have a live RTSP feed of the front door."

---

## Act 4 — The Real Prize: Corporate NAS (90 seconds)

**Why this device last:** the homeowner connects their work laptop to the home
Wi-Fi. The corporate NAS is on a separate subnet but reachable from inside.

Click **Run** next to `wifi-07` (Synology NAS — Shadow File Download).

**Show evidence in three beats:**

1. `GET /webapi/query.cgi` → reveals SMBv1 enabled, FTP anonymous, DSM 6.2.4
2. `GET /shared/backup/etc-shadow.bak` → file downloaded — SHA-512 hashes for
   every system account
3. Hashcat simulation → `admin` hash cracked → password `admin123`

**Say:**
> "Three issues in one device. SMBv1 — vulnerable to EternalBlue. Anonymous FTP.
> And the killer: a backup of `/etc/shadow` sitting in a web-accessible folder.
> No authentication, no exploit chain, just an HTTP GET. The attacker now has
> the homeowner's corporate admin password. The smart home was the entry point,
> but the data exfiltration happens on the corporate side."

---

## Act 5 — What PentexOne Captured (45 seconds)

Scroll to the **Activity Log**.

**Show the timeline** — 3 ATTACK_SIMULATED entries with timestamps, source IPs,
target devices, and protocol tags.

**Say:**
> "Every action is logged with timestamps, target device, protocol, and outcome.
> This is the audit artifact a security consultant hands to the homeowner —
> or in a corporate engagement, what goes into the penetration testing report.
> The chain of evidence is reproducible: same lab, same commands, same result."

Click the **score breakdown** for `wifi-05`:
- Base 200 × Hard difficulty multiplier 2.0
- –10 (1 hint used) — –4 (45s elapsed)
- **Final: 386 / 400 — Grade A**

**Say:**
> "And because PentexOne grades each attack, the same platform doubles as a
> training environment. A student who learns this chain has touched three CVE
> classes — default credentials, debug code exposure, and information disclosure
> — in under three minutes."

---

## The Closing Line (10 seconds)

> "Three devices. Three CVE classes. One coherent attack chain from the curb to
> the corporate password file. That's PentexOne — not just a scanner, an
> end-to-end IoT security audit platform running on a Raspberry Pi."

---

## Timing Guide

| Act | Content | Target |
|---|---|---|
| 1 | Reconnaissance | 1:00 |
| 2 | Nest debug leak (initial foothold) | 1:30 |
| 3 | Hikvision default creds (lateral) | 1:00 |
| 4 | Synology shadow file (exfiltration) | 1:30 |
| 5 | Activity log + scoring | 0:45 |
| Closing | — | 0:10 |
| **Total** | | **~6:00** |

---

## If You Get Cut Short (3-minute version)

Skip Act 3 entirely. The chain still reads as: "leak the Wi-Fi password →
walk straight into the NAS." Hikvision is the most visually obvious attack
but the *least surprising* one for a technical committee — drop it first.

---

## If a Committee Member Pushes Back

**"This is just three default passwords stacked together."**
> Correct — and that is the finding. The 2016 Mirai botnet, the 2021 Verkada
> camera breach, and the 2023 Anker Eufy disclosure all started with the same
> primitive. Real attack chains are not exotic; they are boring vulnerabilities
> composed in order. PentexOne's job is to find that composition before an
> attacker does.

**"Why not show all 12 scenarios?"**
> A full sweep would take 25 minutes and demonstrate breadth but not impact.
> This scenario shows the *integration* — discovery, exploitation, lateral
> movement, exfiltration, and reporting in one continuous flow. Breadth is
> covered in the device registry; what matters in a demo is the chain.

**"What about BLE?"**
> The same engine handles BLE. Run `ble-01` (August Lock) as a 30-second
> appendix if asked — same evidence format, same scoring, just a different
> radio.

---

## Reset Between Runs

```bash
curl -X POST http://localhost:8000/lab/reset       # clear [LAB] devices from DB
curl -X POST http://localhost:8000/lab/quick-scan  # re-inject fresh
# (no need to restart Docker — the containers are stateless for HTTP probes)
```
