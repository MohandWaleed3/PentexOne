# 5.2.4 Virtual Lab Environment

## Overview and Motivation

A critical requirement for comprehensive IoT security testing is the ability to conduct controlled vulnerability scanning without requiring physical hardware dongles, live network deployments, or exposing real production environments to experimental probing techniques. The PentexOne platform integrates a **Docker-based Virtual Lab** comprising three isolated network subnets simulating realistic IoT, guest, and corporate environments. This lab provides a deterministic, reproducible sandbox environment where the security engine can be validated against known vulnerability profiles, protocol implementations, and attack scenarios.

## Virtual Lab Architecture

The Virtual Lab is implemented as a collection of Docker containers managed by the `lab_process_manager.py` module, with logical device registry defined in `lab_registry.py`. The architecture comprises three independent subnets:

**Table 5-4: Virtual Lab Subnets**

| Subnet Name | CIDR Block | Purpose | Simulated Devices |
|---|---|---|---|
| IoT Subnet | 192.168.200.0/24 | Smart home and industrial IoT devices | MQTT broker, Zigbee coordinator, smart hub, thermostats |
| Guest Subnet | 192.168.201.0/24 | Guest network devices (smart speakers, streaming) | Smart speakers, smart displays, media devices |
| Corporate Subnet | 192.168.202.0/24 | Corporate IT systems and NAS | NAS devices, DNS servers, legacy Windows systems |

Each subnet is isolated via Docker network namespaces, preventing cross-subnet communication while allowing the PentexOne scanner (running on the host or orchestrator network) to probe all three subnets via host-mapped ports.

## Device Registry and Vulnerability Profiles

The Virtual Lab maintains a comprehensive device registry in `lab_registry.py::LAB_DEVICES` and `lab_registry.py::BLE_DEVICES`, each device entry defining:

- **Identity**: IP address, MAC address, hostname, vendor, device type
- **Exposure**: Exposed ports, mapped host ports, services
- **Vulnerabilities**: A curated list of vulnerability codes (e.g., `DEFAULT_CREDENTIALS`, `TELNET_ENABLED`, `OUTDATED_FIRMWARE`, `SMBv1_ENABLED`)
- **Container Metadata**: Docker container name, image reference, subnet assignment

Example device entry for an MQTT broker in the IoT subnet:

```python
{
    "ip": "192.168.200.5",
    "hostname": "mqtt-broker",
    "vendor": "Mosquitto",
    "device_type": "MQTT_BROKER",
    "container": "lab-mqtt-broker",
    "subnet": "iot",
    "exposed_ports": [1883],
    "host_port_map": {"1883": 9001},
    "vulnerabilities": ["NO_AUTHENTICATION", "UNENCRYPTED_PROTOCOL", "NO_RATE_LIMITING"]
}
```

## Integration with PentexOne Core Architecture

The Virtual Lab integrates seamlessly with the existing PentexOne scanning and database layers:

### 1. RESTful API Endpoints

A new router (`routers/virtual_lab.py`) exposes dedicated endpoints for lab control and inspection:

- `GET /lab/status` — Current status of Wi-Fi and BLE lab components
- `POST /lab/start` and `POST /lab/stop` — Control lab lifecycle (optionally scoped to specific components)
- `GET /lab/info` and `GET /lab/subnets` — Query lab metadata and network topology
- `GET /lab/devices` and `GET /lab/device/{ip}` — Retrieve device registry and per-device details
- `POST /lab/quick-scan` — Probe live containers and inject discovered devices into the main device database
- `POST /lab/scan` — Execute active nmap scanning on lab subnets with background task support
- `POST /lab/reset` — Clear all lab devices from the database for a clean state

### 2. Database Integration

Lab-discovered devices are persisted in the same SQLite database used for real network scans. Each lab device is tagged with hostname prefixes (e.g., `[LAB:IoT]`, `[LAB:BLE]`) and marked with the lab device type in the `os_guess` field, enabling the security engine and reporting layer to distinguish lab devices from production targets while applying identical vulnerability analysis logic.

### 3. Security Engine Validation

The security engine's risk scoring algorithm is validated against the lab device vulnerability profiles. When a lab device is injected into the database, the system computes a risk level and score by aggregating severity scores from the declared vulnerabilities, using the same port-based and protocol-specific heuristics applied to real scans. This ensures that:

- Default credential detection logic is tested against known vulnerable devices
- Risk scoring thresholds are validated (SAFE < 20, MEDIUM 20-45, HIGH 45-70, CRITICAL ≥ 70)
- Firmware CVE matching is verified against mock device fingerprints
- Protocol-specific vulnerability flags (MQTT unauthenticated, TELNET enabled, etc.) produce expected risk levels

### 4. WebSocket and Real-Time Event Delivery

The lab router integrates with the existing WebSocket manager (`websocket_manager.py`) to broadcast discovery and scan events. When a quick-scan or active scan completes, events are pushed to connected dashboard clients, confirming that real-time notification mechanisms function correctly end-to-end.

## Virtual Lab Operation Modes

The Virtual Lab supports three operational modes:

### 1. Docker-Based Real Container Mode (Primary)

When Docker is available and lab containers are running:

- Devices are instantiated as actual containers running vulnerable services (MQTT without authentication, HTTP servers, legacy protocols)
- The `lab_process_manager.py` module manages container lifecycle via Docker API
- The `quick-scan` endpoint probes containers via host-mapped ports (e.g., `localhost:9001` → container port 1883)
- Only devices responding to probes are injected into the database, ensuring fidelity

### 2. Simulation Mode (Offline)

When Docker is unavailable or containers are not running:

- Lab devices are pre-populated into the database as mock discoveries
- No actual network probing occurs; vulnerability profiles are applied directly
- Useful for dashboard development, report generation testing, and CI/CD environments

### 3. Hybrid Mode (Development)

- Some lab components (e.g., bumble for BLE simulation) run as background processes on the host
- Wi-Fi subnet containers may be running or simulated based on availability
- The system gracefully handles partial hardware/container availability

## Test Scenarios Enabled by Virtual Lab

The Virtual Lab enables the following test scenarios without physical IoT hardware:

**Table 5-5: Virtual Lab Test Scenarios**

| Scenario | Lab Devices | Objective | Validation |
|---|---|---|---|
| Default Credential Detection | MQTT, HTTP admin panels | Verify engine flags known credentials | CRITICAL vulns detected |
| Unencrypted Protocol Scanning | MQTT (no TLS), Telnet | Validate unencrypted protocol detection | HIGH/CRITICAL severity assigned |
| CVE Firmware Matching | Simulated NAS firmware v5.x | Confirm CVE matching logic | CVE-XXXX-XXXXX flagged correctly |
| Risk Score Aggregation | Multi-vulnerability device | Test risk scoring across port/protocol/flag dims | Score falls within expected range |
| Report Generation | Full lab subnet inventory | Validate PDF, JSON, CSV exports | Reports include lab devices with accurate data |
| BLE Vulnerability Profiling | Bumble-simulated BLE peripherals | Test BLE-specific vulnerability detection | BLE_NO_PAIRING, BLE_WEAK_AUTH detected |
| Scan Performance Under Load | All 3 subnets, 30+ devices | Stress-test database and real-time updates | Scan completes within acceptable time |

## Virtual Lab Activity Logging

All lab operations are recorded in an in-memory activity log (`lab_activity_log.py`) capturing:

- Lab lifecycle events (start, stop, reset)
- Scan operations (quick-scan, active-scan) with timestamp and subnet filter
- Device discovery events with injection counts
- Error conditions and offline container warnings

The activity log is queryable via `GET /lab/activity` and provides operational traceability for testing sessions and debugging.

## Why Virtual Lab Was Necessary

Physical hardware-based testing presents several challenges:

1. **Hardware Availability**: Zigbee, Thread, Z-Wave, and RFID dongles are specialized, costly, and may not be available in all lab environments.
2. **Environmental Isolation**: Real network scans risk interfering with live systems; controlled subnets eliminate cross-environment impact.
3. **Reproducibility**: Physical network conditions (interference, timing, device state) vary; virtualized environments provide deterministic, repeatable test runs.
4. **Scalability**: A single physical device can be tested; a virtual lab can instantiate dozens of vulnerable services simultaneously.
5. **Security Testing**: Intentional vulnerabilities (open Telnet, default credentials, SMBv1) can be safely deployed in isolated containers without production risk.
6. **CI/CD Integration**: Continuous testing pipelines require headless, non-interactive testing environments; the virtual lab integrates seamlessly with automated test runners.

## Performance Characteristics

Testing of the Virtual Lab on a standard development workstation (Intel i7, 16 GB RAM) demonstrates:

- **Lab startup time**: 15–25 seconds (Docker image pulls, container initialization)
- **Quick-scan latency**: 2–5 seconds (port probing + database injection of 20–25 devices)
- **Active nmap scan**: 20–40 seconds (full CIDR enumeration across 3 subnets)
- **BLE injection**: <1 second (in-memory registry lookup, database write)
- **Database query performance**: <100 ms for device lookups and vulnerability retrieval

On resource-constrained deployments (Raspberry Pi 4, 4 GB RAM), lab startup times extend to 30–60 seconds due to container I/O, but scan latencies remain acceptable for development workflows.

## Summary

The Virtual Lab component addresses a critical gap in IoT security testing by providing a controlled, deterministic, and reproducible environment for validating the PentexOne platform's scanning, analysis, and reporting capabilities. Through tight integration with the FastAPI backend, database persistence layer, security engine, and WebSocket real-time event system, the lab ensures that all core platform functions can be thoroughly tested and validated without requiring specialized hardware, risking production systems, or sacrificing testing repeatability. The lab's three isolated subnets, comprehensive device registry, and support for both Docker-based and simulated operation modes make it a flexible foundation for both manual security testing and automated CI/CD validation pipelines.

---

**Document Metadata**
- **Section**: 5.2.4
- **Chapter**: 5 - Testing and Validation
- **Project**: PentexOne IoT Security Auditor
- **Date Generated**: 2025-06-04
- **Status**: Final
