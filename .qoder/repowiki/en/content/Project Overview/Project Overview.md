# Project Overview

<cite>
**Referenced Files in This Document**
- [backend/README.md](file://backend/README.md)
- [backend/main.py](file://backend/main.py)
- [backend/models.py](file://backend/models.py)
- [backend/ai_engine.py](file://backend/ai_engine.py)
- [backend/security_engine.py](file://backend/security_engine.py)
- [backend/database.py](file://backend/database.py)
- [backend/websocket_manager.py](file://backend/websocket_manager.py)
- [backend/requirements.txt](file://backend/requirements.txt)
- [backend/static/index.html](file://backend/static/index.html)
- [backend/static/app.js](file://backend/static/app.js)
- [backend/static/style.css](file://backend/static/style.css)
- [backend/routers/iot.py](file://backend/routers/iot.py)
- [backend/routers/wifi_bt.py](file://backend/routers/wifi_bt.py)
- [backend/routers/ai.py](file://backend/routers/ai.py)
- [backend/routers/reports.py](file://backend/routers/reports.py)
</cite>

## Table of Contents
1. [Introduction](#introduction)
2. [Project Structure](#project-structure)
3. [Core Components](#core-components)
4. [Architecture Overview](#architecture-overview)
5. [Detailed Component Analysis](#detailed-component-analysis)
6. [Dependency Analysis](#dependency-analysis)
7. [Performance Considerations](#performance-considerations)
8. [Troubleshooting Guide](#troubleshooting-guide)
9. [Conclusion](#conclusion)

## Introduction
PentexOne is a professional-grade IoT Security Auditor designed to discover, analyze, and assess security vulnerabilities across multiple wireless protocols. It provides a modern web interface powered by AI-driven analysis, enabling security professionals, IoT developers, and smart home enthusiasts to evaluate and improve the security posture of connected environments. Its mission is to simplify multi-protocol vulnerability discovery, deliver actionable insights, and produce professional-grade security reports.

Key value propositions:
- Multi-protocol scanning across Wi-Fi, Bluetooth, Zigbee, Thread/Matter, Z-Wave, LoRaWAN, and RFID/NFC
- AI-powered analysis for device classification, anomaly detection, vulnerability prediction, and remediation recommendations
- Real-time dashboard with live updates via WebSocket and interactive analytics
- Professional reporting in PDF, JSON, and CSV formats
- Raspberry Pi optimized deployment for portable and embedded use

Target audience:
- Security professionals conducting assessments and audits
- IoT developers validating device security during development and post-release
- Smart home enthusiasts securing personal networks and devices

Positioning in the cybersecurity ecosystem:
- Complements traditional network scanners (e.g., nmap) with IoT-specific protocol coverage and AI-driven insights
- Bridges the gap between raw vulnerability data and practical remediation guidance
- Supports continuous monitoring and trend analysis for evolving IoT ecosystems

**Section sources**
- [backend/README.md:18-30](file://backend/README.md#L18-L30)
- [backend/README.md:33-64](file://backend/README.md#L33-L64)
- [backend/README.md:215-241](file://backend/README.md#L215-L241)

## Project Structure
The project follows a modular backend-frontend separation:
- Backend: FastAPI application with modular routers for IoT scanning, Wi-Fi/Bluetooth, AI analysis, and reporting; WebSocket manager for real-time updates; SQLAlchemy models and SQLite storage
- Frontend: Static HTML/CSS/JavaScript dashboard with Chart.js for visualizations and WebSocket integration for live updates

```mermaid
graph TB
subgraph "Backend"
A["FastAPI App<br/>main.py"]
B["Routers<br/>iot.py / wifi_bt.py / ai.py / reports.py"]
C["AI Engine<br/>ai_engine.py"]
D["Security Engine<br/>security_engine.py"]
E["Database<br/>models.py + database.py"]
F["WebSocket Manager<br/>websocket_manager.py"]
G["Static Assets<br/>index.html / app.js / style.css"]
end
subgraph "External Tools"
H["nmap"]
I["scapy"]
J["zeroconf"]
K["reportlab"]
L["bleak"]
M["killerbee (optional)"]
end
A --> B
B --> D
B --> E
B --> F
A --> G
B --> H
B --> I
B --> J
B --> K
B --> L
B --> M
A --> C
C --> D
```

**Diagram sources**
- [backend/main.py:14-48](file://backend/main.py#L14-L48)
- [backend/routers/iot.py:24](file://backend/routers/iot.py#L24)
- [backend/routers/wifi_bt.py:27](file://backend/routers/wifi_bt.py#L27)
- [backend/routers/ai.py:20](file://backend/routers/ai.py#L20)
- [backend/routers/reports.py:15](file://backend/routers/reports.py#L15)
- [backend/ai_engine.py:1](file://backend/ai_engine.py#L1)
- [backend/security_engine.py:1](file://backend/security_engine.py#L1)
- [backend/database.py:12-61](file://backend/database.py#L12-L61)
- [backend/websocket_manager.py:7-47](file://backend/websocket_manager.py#L7-L47)
- [backend/static/index.html:1-413](file://backend/static/index.html#L1-L413)
- [backend/static/app.js:1-200](file://backend/static/app.js#L1-L200)
- [backend/static/style.css:1-200](file://backend/static/style.css#L1-L200)
- [backend/requirements.txt:1-21](file://backend/requirements.txt#L1-L21)

**Section sources**
- [backend/README.md:273-297](file://backend/README.md#L273-L297)
- [backend/main.py:14-48](file://backend/main.py#L14-L48)
- [backend/database.py:12-61](file://backend/database.py#L12-L61)
- [backend/websocket_manager.py:7-47](file://backend/websocket_manager.py#L7-L47)
- [backend/static/index.html:1-413](file://backend/static/index.html#L1-L413)
- [backend/static/app.js:1-200](file://backend/static/app.js#L1-L200)
- [backend/static/style.css:1-200](file://backend/static/style.css#L1-L200)

## Core Components
- FastAPI Application: Central orchestration, routing, authentication, and WebSocket endpoint
- IoT Routers: Protocol-specific scanning and discovery for Wi-Fi, Bluetooth, Zigbee, Thread/Matter, Z-Wave, LoRaWAN, and RFID/NFC
- Security Engine: Risk calculation, vulnerability mapping, and TLS/SSL assessment
- AI Engine: Pattern matching, anomaly detection, vulnerability prediction, and remediation recommendations
- Database: ORM models for devices, vulnerabilities, RFID cards, and settings backed by SQLite
- WebSocket Manager: Broadcasts live scan events to the dashboard
- Frontend Dashboard: Real-time charts, device tables, AI suggestions, and reporting controls

Key capabilities:
- Multi-protocol scanning with hardware detection and fallback simulation modes
- Risk scoring and vulnerability categorization per device and network
- AI-driven device classification, anomaly detection, and security score computation
- Live dashboards with WebSocket updates and interactive visualizations
- Professional report generation in multiple formats

**Section sources**
- [backend/README.md:22-29](file://backend/README.md#L22-L29)
- [backend/README.md:33-64](file://backend/README.md#L33-L64)
- [backend/README.md:215-269](file://backend/README.md#L215-L269)
- [backend/models.py:6-71](file://backend/models.py#L6-L71)
- [backend/database.py:12-61](file://backend/database.py#L12-L61)
- [backend/websocket_manager.py:7-47](file://backend/websocket_manager.py#L7-L47)
- [backend/ai_engine.py:236-766](file://backend/ai_engine.py#L236-L766)
- [backend/security_engine.py:202-340](file://backend/security_engine.py#L202-L340)

## Architecture Overview
PentexOne employs a layered architecture:
- Presentation Layer: Static HTML/CSS/JS dashboard with Chart.js and WebSocket connectivity
- API Layer: FastAPI routes organized by domain (IoT, Wireless, AI, Reports)
- Business Logic Layer: Security and AI engines encapsulating protocol-specific logic and intelligence
- Data Layer: SQLite via SQLAlchemy with models for devices, vulnerabilities, RFID cards, and settings

```mermaid
graph TB
UI["Dashboard UI<br/>index.html + app.js + style.css"]
WS["WebSocket Endpoint<br/>/ws"]
API["FastAPI Routes<br/>main.py"]
IOT["IoT Router<br/>routers/iot.py"]
WIFI["Wireless Router<br/>routers/wifi_bt.py"]
AI["AI Router<br/>routers/ai.py"]
REP["Reports Router<br/>routers/reports.py"]
SEC["Security Engine<br/>security_engine.py"]
AIE["AI Engine<br/>ai_engine.py"]
DB["Database<br/>database.py + pentex.db"]
UI --> WS
UI --> API
API --> IOT
API --> WIFI
API --> AI
API --> REP
IOT --> SEC
IOT --> DB
WIFI --> SEC
WIFI --> DB
AI --> AIE
AI --> DB
REP --> DB
API --> DB
```

**Diagram sources**
- [backend/main.py:14-106](file://backend/main.py#L14-L106)
- [backend/routers/iot.py:24](file://backend/routers/iot.py#L24)
- [backend/routers/wifi_bt.py:27](file://backend/routers/wifi_bt.py#L27)
- [backend/routers/ai.py:20](file://backend/routers/ai.py#L20)
- [backend/routers/reports.py:15](file://backend/routers/reports.py#L15)
- [backend/ai_engine.py:236-766](file://backend/ai_engine.py#L236-L766)
- [backend/security_engine.py:202-340](file://backend/security_engine.py#L202-L340)
- [backend/database.py:12-80](file://backend/database.py#L12-L80)
- [backend/static/index.html:1-413](file://backend/static/index.html#L1-L413)
- [backend/static/app.js:1-200](file://backend/static/app.js#L1-L200)
- [backend/static/style.css:1-200](file://backend/static/style.css#L1-L200)

## Detailed Component Analysis

### Security Engine: Risk Calculation and Vulnerability Mapping
The Security Engine evaluates device risk based on:
- Open ports mapped to known vulnerability categories
- Default credential checks
- Protocol-specific vulnerability patterns
- TLS/SSL certificate validation
- Firmware/CVE matching

Processing logic:
- Risk score aggregation weighted by severity
- Categorization into SAFE, MEDIUM, RISK
- Detailed vulnerability records with severity and description

```mermaid
flowchart TD
Start(["Start Risk Calculation"]) --> Ports["Collect Open Ports"]
Ports --> Defaults["Check Default Credentials"]
Defaults --> Protocols["Apply Protocol-Specific Checks"]
Protocols --> TLS["Assess TLS/SSL"]
TLS --> Firmware["Match Firmware to CVEs"]
Firmware --> Aggregate["Aggregate Scores by Severity"]
Aggregate --> Categorize{"Categorize Risk"}
Categorize --> |0| Safe["SAFE"]
Categorize --> |<=40| Medium["MEDIUM"]
Categorize --> |>40| Risk["RISK"]
Safe --> End(["Return Risk Level + Vulnerabilities"])
Medium --> End
Risk --> End
```

**Diagram sources**
- [backend/security_engine.py:202-340](file://backend/security_engine.py#L202-L340)

**Section sources**
- [backend/security_engine.py:18-187](file://backend/security_engine.py#L18-L187)
- [backend/security_engine.py:202-340](file://backend/security_engine.py#L202-L340)

### AI Engine: Pattern Matching, Anomaly Detection, and Recommendations
The AI Engine performs:
- Device type identification via pattern matching and port heuristics
- Vulnerability prediction with confidence scores
- Anomaly detection and network-wide risk scoring
- Remediation recommendations drawn from a knowledge base
- Trend analysis and dashboard suggestions

```mermaid
flowchart TD
AStart(["AI Analysis Request"]) --> Identify["Identify Device Type"]
Identify --> Predict["Predict Vulnerabilities"]
Predict --> Anomaly["Calculate Anomaly Score"]
Anomaly --> Recom["Generate Recommendations"]
Recom --> Score["Compute Confidence"]
Score --> Net["Network Analysis (Optional)"]
Net --> Output(["Return AI Results"])
Output --> End(["Done"])
```

**Diagram sources**
- [backend/ai_engine.py:236-766](file://backend/ai_engine.py#L236-L766)

**Section sources**
- [backend/ai_engine.py:236-766](file://backend/ai_engine.py#L236-L766)

### IoT Scanning Pipeline: Wi-Fi, Bluetooth, Zigbee, Thread/Matter, Z-Wave, LoRaWAN
The IoT routers coordinate scanning workflows:
- Wi-Fi: nmap-based discovery and port scanning
- Bluetooth: BLE device discovery and risk flags
- Zigbee/Thread/Z-Wave/LoRaWAN: hardware detection with simulated fallbacks
- Real-time updates via WebSocket broadcasts

```mermaid
sequenceDiagram
participant UI as "Dashboard UI"
participant API as "IoT Router"
participant SEC as "Security Engine"
participant DB as "Database"
participant WS as "WebSocket Manager"
UI->>API : "POST /iot/scan/<protocol>"
API->>API : "Background Task Start"
API->>SEC : "calculate_risk(...)"
SEC-->>API : "Risk Result + Vulnerabilities"
API->>DB : "Upsert Device + Vulnerabilities"
API->>WS : "Broadcast device_found / scan_progress"
API-->>UI : "ScanStatus"
WS-->>UI : "Live Updates"
```

**Diagram sources**
- [backend/routers/iot.py:291-413](file://backend/routers/iot.py#L291-L413)
- [backend/security_engine.py:202-340](file://backend/security_engine.py#L202-L340)
- [backend/websocket_manager.py:21-45](file://backend/websocket_manager.py#L21-L45)

**Section sources**
- [backend/routers/iot.py:291-413](file://backend/routers/iot.py#L291-L413)
- [backend/routers/iot.py:483-586](file://backend/routers/iot.py#L483-L586)
- [backend/routers/iot.py:625-722](file://backend/routers/iot.py#L625-L722)
- [backend/routers/iot.py:783-800](file://backend/routers/iot.py#L783-L800)

### Wireless and TLS Utilities: Port Scanning, Credential Testing, TLS Validation
The Wireless router supports:
- Deep port scanning per device
- Default credential testing across HTTP and Telnet
- TLS/SSL certificate validation and risk updates
- Wi-Fi SSID discovery and network quick discovery

```mermaid
sequenceDiagram
participant UI as "Dashboard UI"
participant API as "Wireless Router"
participant SEC as "Security Engine"
participant DB as "Database"
UI->>API : "POST /wireless/test/ports/{ip}"
API->>API : "Run nmap scan"
API->>SEC : "calculate_risk(open_ports, protocol)"
SEC-->>API : "Risk + Vulns"
API->>DB : "Update Device + Vulnerabilities"
API-->>UI : "Started"
```

**Diagram sources**
- [backend/routers/wifi_bt.py:59-96](file://backend/routers/wifi_bt.py#L59-L96)
- [backend/security_engine.py:202-340](file://backend/security_engine.py#L202-L340)

**Section sources**
- [backend/routers/wifi_bt.py:59-96](file://backend/routers/wifi_bt.py#L59-L96)
- [backend/routers/wifi_bt.py:101-167](file://backend/routers/wifi_bt.py#L101-L167)
- [backend/routers/wifi_bt.py:447-549](file://backend/routers/wifi_bt.py#L447-L549)
- [backend/routers/wifi_bt.py:636-766](file://backend/routers/wifi_bt.py#L636-L766)

### Reporting: PDF, JSON, CSV Exports
The Reports router generates comprehensive security reports:
- Executive summary and device inventory
- Vulnerability listings with remediation guidance
- Optional RFID/NFC audit section

```mermaid
sequenceDiagram
participant UI as "Dashboard UI"
participant API as "Reports Router"
participant DB as "Database"
participant FS as "File System"
UI->>API : "GET /reports/generate/pdf"
API->>DB : "Query Devices + Vulnerabilities"
API->>FS : "Write PDF to generated_reports/"
API-->>UI : "FileResponse(pdf)"
```

**Diagram sources**
- [backend/routers/reports.py:37-158](file://backend/routers/reports.py#L37-L158)

**Section sources**
- [backend/routers/reports.py:18-34](file://backend/routers/reports.py#L18-L34)
- [backend/routers/reports.py:37-158](file://backend/routers/reports.py#L37-L158)

### Real-Time Dashboard and WebSocket Integration
The dashboard provides:
- Live scan progress and device discovery notifications
- Interactive charts for risk and protocol distributions
- AI security score and recommendations
- Device selection for detailed analysis and AI insights

```mermaid
sequenceDiagram
participant WS as "WebSocket Client"
participant API as "WebSocket Endpoint"
participant WM as "WebSocket Manager"
participant UI as "Dashboard UI"
WS->>API : "Connect /ws"
API->>WM : "Register Connection"
WM-->>UI : "Broadcast Events"
UI->>UI : "Render Charts + Alerts"
```

**Diagram sources**
- [backend/main.py:90-102](file://backend/main.py#L90-L102)
- [backend/websocket_manager.py:7-47](file://backend/websocket_manager.py#L7-L47)
- [backend/static/app.js:113-155](file://backend/static/app.js#L113-L155)

**Section sources**
- [backend/main.py:90-102](file://backend/main.py#L90-L102)
- [backend/websocket_manager.py:7-47](file://backend/websocket_manager.py#L7-L47)
- [backend/static/app.js:113-155](file://backend/static/app.js#L113-L155)
- [backend/static/index.html:52-316](file://backend/static/index.html#L52-L316)

## Dependency Analysis
Technology stack and integration:
- Web framework: FastAPI with Uvicorn ASGI server
- Networking and scanning: python-nmap, scapy, zeroconf
- Bluetooth: bleak
- Hardware sniffing: killerbee (optional)
- TLS validation: cryptography
- Reporting: ReportLab
- Database: SQLAlchemy with SQLite
- Frontend: Chart.js for analytics, Font Awesome for icons

```mermaid
graph LR
FastAPI["FastAPI"] --> Uvicorn["Uvicorn"]
FastAPI --> Routers["Routers"]
Routers --> Nmap["python-nmap"]
Routers --> Scapy["scapy"]
Routers --> Zeroconf["zeroconf"]
Routers --> Bleak["bleak"]
Routers --> Killerbee["killerbee (opt)"]
Routers --> Crypto["cryptography"]
Routers --> ReportLab["reportlab"]
Routers --> SQLA["SQLAlchemy"]
UI["Static UI"] --> ChartJS["Chart.js"]
UI --> FA["Font Awesome"]
```

**Diagram sources**
- [backend/requirements.txt:1-21](file://backend/requirements.txt#L1-L21)
- [backend/main.py:1-106](file://backend/main.py#L1-L106)
- [backend/routers/iot.py:1-16](file://backend/routers/iot.py#L1-L16)
- [backend/routers/wifi_bt.py:1-12](file://backend/routers/wifi_bt.py#L1-L12)
- [backend/routers/ai.py:1-18](file://backend/routers/ai.py#L1-L18)
- [backend/routers/reports.py:1-15](file://backend/routers/reports.py#L1-L15)
- [backend/static/index.html:8-14](file://backend/static/index.html#L8-L14)
- [backend/static/style.css:1-200](file://backend/static/style.css#L1-L200)

**Section sources**
- [backend/requirements.txt:1-21](file://backend/requirements.txt#L1-L21)

## Performance Considerations
- Resource usage varies by scanning intensity; idle vs. scanning vs. AI analysis states impact CPU and memory
- Recommendations include using wired Ethernet, headless operation, and powered USB hubs for multiple dongles
- Background tasks ensure non-blocking UI interactions; WebSocket broadcasting is thread-safe

[No sources needed since this section provides general guidance]

## Troubleshooting Guide
Common operational issues and resolutions:
- Dashboard accessibility: verify service status, logs, and port binding
- Hardware detection: confirm USB dongle presence, permissions, and driver availability
- Bluetooth connectivity: restart services and unblock interfaces
- Protocol-specific errors: validate optional dependencies (killerbee, bleak) and system capabilities

**Section sources**
- [backend/README.md:349-382](file://backend/README.md#L349-L382)

## Conclusion
PentexOne delivers a comprehensive, professional-grade solution for IoT security auditing. Its multi-protocol scanning, AI-powered insights, real-time dashboard, and professional reporting capabilities position it as a practical tool for security teams and IoT developers alike. Built with modularity, extensibility, and usability in mind, it supports both hands-on assessments and continuous monitoring of evolving IoT environments.

[No sources needed since this section summarizes without analyzing specific files]