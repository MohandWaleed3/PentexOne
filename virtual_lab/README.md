# PentexOne Virtual Lab

A self-contained, Docker-based IoT penetration testing environment built for the PentexOne platform. All vulnerable devices are simulated — no real hardware needed.

---

## Architecture Overview

```
PentexOne (Raspberry Pi / your laptop)
          |
          |  HTTP API
          v
  +------------------------------------------------------------------------+
  |  VIRTUAL LAB (Linux VM or same machine)                                |
  |                                                                        |
  |  [IoT Subnet]  172.30.10.0/24                                          |
  |    Hikvision Camera    172.30.10.50  -> host:8050                      |
  |    MQTT Broker         172.30.10.51  -> host:8051, 8061                |
  |    TP-Link Router      172.30.10.52  -> host:8052, 8062                |
  |    Tuya Smart Plug     172.30.10.53  -> host:8053, 8063                |
  |    Nest Thermostat     172.30.10.54  -> host:8054, 8064                |
  |                                                                        |
  |  [Guest Subnet]  172.30.20.0/24                                        |
  |    Samsung Smart TV    172.30.20.50  -> host:8070, 8071, 8072          |
  |                                                                        |
  |  [Corporate Subnet]  172.30.30.0/24                                    |
  |    Synology NAS        172.30.30.50  -> host:8080, 8081, 8082, 8083    |
  |                                                                        |
  |  [BLE Lab]  (host Bluetooth adapter)                                   |
  |    August Smart Lock   A4:B2:00:01:02:03                               |
  |    Fitbit Charge 5     C5:FB:00:01:02:04                               |
  |    LIFX A19 Bulb       3F:88:00:01:02:05                               |
  |    Accu-Chek Guide     AC:CE:00:01:02:06                               |
  |    JBL Tune 510BT      5B:10:00:01:02:07                               |
  +------------------------------------------------------------------------+
```

---

## Prerequisites

| Component | Requirement |
|---|---|
| Docker | 20.10+ with Docker Compose v2 |
| Python | 3.9+ (for BLE lab) |
| OS | Linux recommended (Ubuntu 22.04 / Raspberry Pi OS) |
| RAM | >= 2 GB free for all 7 containers |
| Disk | >= 500 MB |

> macOS / Windows: Docker containers work fine. BLE advertising requires Linux with BlueZ.
> On Mac/Win, use BLE inject mode (no real Bluetooth needed for demos).

---

## Quick Start

### 1 — Start the Wi-Fi Lab

```bash
cd virtual_lab/
./start_lab.sh
```

Verify containers are up:
```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

### 2 — Test connectivity

```bash
curl http://localhost:8050/              # Hikvision login page
curl http://localhost:8080/             # Synology NAS DSM login
curl http://localhost:8064/debug/dump   # Nest credential dump (CRITICAL vuln)
```

### 3 — Control via PentexOne API

```bash
# Start both Wi-Fi + BLE labs
curl -X POST http://localhost:8000/lab/start

# Check status
curl http://localhost:8000/lab/status

# Inject all devices into the device database (demo mode, no nmap needed)
curl -X POST http://localhost:8000/lab/quick-scan
curl -X POST http://localhost:8000/lab/ble-inject
```

### 4 — Open the Virtual Lab UI

Navigate to:  http://localhost:8000/dashboard/index.html
Click "Virtual Lab" in the left sidebar.

### 5 — Stop the lab

```bash
./stop_lab.sh
# or via API:
curl -X POST http://localhost:8000/lab/stop
```

---

## BLE Lab Setup

### Install bumble

```bash
cd virtual_lab/ble_lab/
pip install -r requirements.txt
```

### Run BLE simulator

```bash
# Linux with BlueZ (real Bluetooth advertising over the air)
python3 ble_simulator.py --adapter hci0

# Single device only
python3 ble_simulator.py --device lock

# macOS / no adapter (in-memory simulation, shows in activity log only)
python3 ble_simulator.py
```

### Scan for BLE devices (Linux)

```bash
bluetoothctl scan on
# Look for: August-Lock-A4B2, Fitbit-Charge-5, LIFX-A19-3F88, Accu-Chek-Guide, JBL-Tune-510BT
```

---

## API Reference

### Lab Control

| Method | Endpoint | Description |
|---|---|---|
| GET | /lab/status | Status of Wi-Fi + BLE labs |
| POST | /lab/start | Start both labs |
| POST | /lab/start?component=wifi | Start Wi-Fi lab only |
| POST | /lab/start?component=ble | Start BLE lab only |
| POST | /lab/stop | Stop both labs |
| POST | /lab/stop?component=wifi | Stop Wi-Fi lab only |

### Device Management

| Method | Endpoint | Description |
|---|---|---|
| GET | /lab/info | Full architecture summary |
| GET | /lab/subnets | List 3 subnets |
| GET | /lab/devices | List all 7 Wi-Fi devices |
| GET | /lab/ble-devices | List all 5 BLE devices |
| POST | /lab/quick-scan | Inject Wi-Fi devices into DB instantly |
| POST | /lab/ble-inject | Inject BLE devices into DB instantly |
| POST | /lab/reset | Remove all [LAB] devices from DB |
| GET | /lab/device/{ip} | Single Wi-Fi device detail |
| GET | /lab/ble-device/{address} | Single BLE device detail |

### Attack Scenarios

| Method | Endpoint | Description |
|---|---|---|
| GET | /attacks/ | List all 12 scenarios |
| GET | /attacks/?difficulty=easy | Filter by difficulty |
| GET | /attacks/?protocol=BLE | Filter by protocol |
| GET | /attacks/{id} | Full scenario with steps |
| POST | /attacks/{id}/run | Execute attack |
| GET | /attacks/{id}/tutorial | Full educational tutorial |
| GET | /attacks/{id}/hints | Hint metadata |
| GET | /attacks/{id}/hints/{1-3} | Reveal a specific hint |
| POST | /attacks/{id}/score | Submit score {elapsed_seconds, hints_used, success} |
| GET | /attacks/results | All past attack results |
| GET | /attacks/learning/path | Difficulty learning path |

### Activity Log

| Method | Endpoint | Description |
|---|---|---|
| GET | /lab/activity | Recent events (newest first) |
| GET | /lab/activity/stats | Event statistics |
| DELETE | /lab/activity | Clear the log |

---

## Device Reference

### Wi-Fi Lab Devices

| Device | IP | Host Port | Default Credentials | Key Vulnerabilities |
|---|---|---|---|---|
| Hikvision Camera | 172.30.10.50 | 8050 | admin / admin | DEFAULT_CREDENTIALS, DIRECTORY_LISTING |
| MQTT Broker | 172.30.10.51 | 8051, 8061 | (none) | NO_AUTHENTICATION, UNENCRYPTED_PROTOCOL |
| TP-Link Router | 172.30.10.52 | 8052, 8062 | root / root | TELNET_ENABLED, DEFAULT_CREDENTIALS |
| Tuya Smart Plug | 172.30.10.53 | 8053, 8063 | (none) | NO_LOCAL_AUTH, HARDCODED_KEY |
| Nest Thermostat | 172.30.10.54 | 8054, 8064 | admin / 1234 | DEBUG_INTERFACE_EXPOSED, CREDENTIAL_LEAK |
| Samsung Smart TV | 172.30.20.50 | 8070, 8071, 8072 | (none) | MIC_REMOTE_CONTROL, VOICE_API_OPEN |
| Synology NAS | 172.30.30.50 | 8080, 8081, 8082, 8083 | admin / admin123 | SHADOW_BACKUP_EXPOSED, SMBv1_ENABLED |

### BLE Lab Devices

| Device | BLE Name | MAC Address | Key Vulnerabilities |
|---|---|---|---|
| August Smart Lock | August-Lock-A4B2 | A4:B2:00:01:02:03 | NO_PAIRING_REQUIRED, CREDENTIAL_LEAK |
| Fitbit Charge 5 | Fitbit-Charge-5 | C5:FB:00:01:02:04 | EXPOSED_HEALTH_CHARACTERISTICS |
| LIFX A19 Bulb | LIFX-A19-3F88 | 3F:88:00:01:02:05 | HARDCODED_KEY, CREDENTIAL_LEAK |
| Accu-Chek Guide | Accu-Chek-Guide | AC:CE:00:01:02:06 | UNENCRYPTED_PROTOCOL, INFORMATION_DISCLOSURE |
| JBL Tune 510BT | JBL-Tune-510BT | 5B:10:00:01:02:07 | NO_PAIRING_REQUIRED, HARDCODED_KEY |

---

## Attack Scenarios & Scoring

| ID | Target | Difficulty | Max Score |
|---|---|---|---|
| wifi-01 | Hikvision Camera — Default Credentials | Easy | 100 |
| wifi-02 | MQTT Broker — Anonymous Takeover | Easy | 100 |
| wifi-03 | TP-Link Router — Telnet Root Shell | Medium | 225 |
| wifi-04 | Tuya Plug — Unauthenticated Control | Medium | 225 |
| wifi-05 | Nest Thermostat — Debug Credential Dump | Hard | 400 |
| wifi-06 | Samsung TV — Remote Mic Activation | Easy | 100 |
| wifi-07 | Synology NAS — Shadow File Download | Hard | 400 |
| ble-01 | August Lock — Unauthenticated Unlock | Easy | 100 |
| ble-02 | Fitbit — Health Data Exfiltration | Easy | 100 |
| ble-03 | LIFX Bulb — Auth Token Leak | Medium | 225 |
| ble-04 | Glucose Meter — Medical PII Extraction | Medium | 225 |
| ble-05 | JBL Headphones — Pairing Key Theft | Easy | 100 |
| **Total** | | | **2,300 pts** |

Scoring formula: `(base_score - hint_penalty - time_penalty) x difficulty_multiplier`
- Hint cost: -10 pts per hint used (max 3 hints per scenario)
- Time penalty: -1 pt per 10 seconds over the time limit

---

## File Structure

```
virtual_lab/
├── start_lab.sh              <- Start all lab components
├── stop_lab.sh               <- Stop all lab components
├── README.md                 <- This file
├── DEMO_SCRIPT.md            <- Step-by-step demo for presentations
│
├── wifi_lab/
│   ├── docker-compose.yml    <- 7 services across 3 bridge networks
│   ├── hikvision/            <- Nginx + Basic Auth camera simulation
│   ├── mosquitto/            <- Eclipse Mosquitto (anonymous=true)
│   ├── tplink/               <- Alpine + telnetd + Python web admin
│   ├── tuya/                 <- Tuya local protocol simulation
│   ├── nest/                 <- Debug interface + credential leak
│   ├── smart_tv/             <- DIAL + Voice API
│   └── corporate_nas/        <- DSM + fake SMB + fake FTP
│
└── ble_lab/
    ├── ble_simulator.py      <- Main bumble simulator (5 peripherals)
    ├── requirements.txt      <- bumble, pyusb
    └── devices/
        ├── smart_lock.py     <- August Smart Lock GATT
        ├── fitbit.py         <- Fitbit health data GATT
        ├── lifx_bulb.py      <- LIFX color/auth/wifi GATT
        ├── glucose_meter.py  <- Medical glucose GATT
        └── headphones.py     <- JBL audio/pairing GATT
```

---

## Troubleshooting

**Containers fail to start:**
```bash
docker compose down -v
docker compose up -d --build
```

**Port already in use:**
```bash
lsof -i :8050       # Find what is using port 8050
# Edit host ports in wifi_lab/docker-compose.yml if needed
```

**BLE simulator: "No adapter":**
```bash
hciconfig                       # List adapters
sudo systemctl start bluetooth
python3 ble_simulator.py --adapter hci1
```

**Devices not appearing in PentexOne dashboard:**
- Go to Virtual Lab view -> click "Inject Wi-Fi Devices"
- Then click Dashboard -> refresh device list

**Lab on separate VM, PentexOne on different machine:**
- Edit `LAB_HOST` in `backend/routers/attack_scenarios.py` to the VM's IP
- Ensure ports 8050-8083 are reachable from PentexOne's machine
