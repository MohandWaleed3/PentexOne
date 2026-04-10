# Contributing & Development

<cite>
**Referenced Files in This Document**
- [backend/README.md](file://backend/README.md)
- [backend/main.py](file://backend/main.py)
- [backend/models.py](file://backend/models.py)
- [backend/requirements.txt](file://backend/requirements.txt)
- [backend/DEPLOYMENT_CHECKLIST.md](file://backend/DEPLOYMENT_CHECKLIST.md)
- [backend/database.py](file://backend/database.py)
- [backend/websocket_manager.py](file://backend/websocket_manager.py)
- [backend/security_engine.py](file://backend/security_engine.py)
- [backend/ai_engine.py](file://backend/ai_engine.py)
- [backend/routers/iot.py](file://backend/routers/iot.py)
- [backend/routers/wifi_bt.py](file://backend/routers/wifi_bt.py)
- [backend/routers/access_control.py](file://backend/routers/access_control.py)
- [backend/routers/reports.py](file://backend/routers/reports.py)
- [backend/routers/ai.py](file://backend/routers/ai.py)
- [backend/static/index.html](file://backend/static/index.html)
- [backend/static/app.js](file://backend/static/app.js)
- [backend/test_dongles.py](file://backend/test_dongles.py)
- [backend/test_all.py](file://backend/test_all.py)
- [backend/setup.sh](file://backend/setup.sh)
- [backend/start.sh](file://backend/start.sh)
- [backend/rpi_setup.sh](file://backend/rpi_setup.sh)
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
9. [Development Workflow](#development-workflow)
10. [Testing Framework](#testing-framework)
11. [Adding New Protocol Support](#adding-new-protocol-support)
12. [Extending Security Analysis](#extending-security-analysis)
13. [Contributing to the Frontend](#contributing-to-the-frontend)
14. [Development Environment Setup](#development-environment-setup)
15. [Documentation Contributions](#documentation-contributions)
16. [Bug Reporting and Feature Requests](#bug-reporting-and-feature-requests)
17. [Code Review Standards](#code-review-standards)
18. [Quality Assurance Practices](#quality-assurance-practices)
19. [Release Procedures](#release-procedures)
20. [Conclusion](#conclusion)

## Introduction
This document provides comprehensive contributing and development guidance for PentexOne, a professional-grade IoT security auditing platform. It covers development workflow, codebase structure, architectural patterns, coding conventions, testing strategies, and contribution procedures for protocols, security analysis, and the frontend interface. It also includes environment setup, dependency management, build processes, documentation contributions, bug reporting, feature requests, code review standards, quality assurance practices, and release procedures.

## Project Structure
PentexOne follows a modular backend architecture with a FastAPI application, organized routers for distinct functional domains, a shared AI and security engines, a SQL-based persistence layer, and a modern web dashboard.

```mermaid
graph TB
subgraph "Backend"
MAIN["main.py<br/>FastAPI app entry"]
WS["websocket_manager.py<br/>WebSocket connections"]
DB["database.py<br/>SQLAlchemy models & DB init"]
MODELS["models.py<br/>Pydantic models"]
ROUTERS_IOT["routers/iot.py<br/>IoT scanning & discovery"]
ROUTERS_WIFI_BT["routers/wifi_bt.py<br/>WiFi & BLE utilities"]
ROUTERS_RFID["routers/access_control.py<br/>RFID/NFC"]
ROUTERS_AI["routers/ai.py<br/>AI analysis endpoints"]
ROUTERS_REPORTS["routers/reports.py<br/>Reports & exports"]
SEC_ENGINE["security_engine.py<br/>Risk calculation"]
AI_ENGINE["ai_engine.py<br/>AI analysis"]
end
subgraph "Frontend"
HTML["static/index.html<br/>Dashboard layout"]
JS["static/app.js<br/>Dashboard logic & UI"]
end
subgraph "Development Scripts"
SETUP["setup.sh<br/>Environment setup"]
START["start.sh<br/>Quick start script"]
RPI_SETUP["rpi_setup.sh<br/>Raspberry Pi installer"]
TEST_ALL["test_all.py<br/>Comprehensive test suite"]
TEST_DONGLES["test_dongles.py<br/>Hardware detection"]
end
MAIN --> ROUTERS_IOT
MAIN --> ROUTERS_WIFI_BT
MAIN --> ROUTERS_RFID
MAIN --> ROUTERS_AI
MAIN --> ROUTERS_REPORTS
MAIN --> WS
MAIN --> DB
MAIN --> MODELS
ROUTERS_IOT --> SEC_ENGINE
ROUTERS_WIFI_BT --> SEC_ENGINE
ROUTERS_AI --> AI_ENGINE
ROUTERS_REPORTS --> DB
HTML --> JS
JS --> MAIN
SETUP --> START
START --> MAIN
RPI_SETUP --> SETUP
TEST_ALL --> MAIN
TEST_DONGLES --> ROUTERS_IOT
```

**Diagram sources**
- [backend/main.py:1-106](file://backend/main.py#L1-L106)
- [backend/websocket_manager.py:1-48](file://backend/websocket_manager.py#L1-L48)
- [backend/database.py:1-80](file://backend/database.py#L1-L80)
- [backend/models.py:1-71](file://backend/models.py#L1-L71)
- [backend/routers/iot.py:1-880](file://backend/routers/iot.py#L1-L880)
- [backend/routers/wifi_bt.py:1-766](file://backend/routers/wifi_bt.py#L1-L766)
- [backend/routers/access_control.py:1-95](file://backend/routers/access_control.py#L1-L95)
- [backend/routers/ai.py:1-330](file://backend/routers/ai.py#L1-L330)
- [backend/routers/reports.py:1-158](file://backend/routers/reports.py#L1-L158)
- [backend/security_engine.py:1-425](file://backend/security_engine.py#L1-L425)
- [backend/ai_engine.py:1-766](file://backend/ai_engine.py#L1-L766)
- [backend/static/index.html:1-413](file://backend/static/index.html#L1-L413)
- [backend/static/app.js:1-1099](file://backend/static/app.js#L1-L1099)
- [backend/start.sh:1-38](file://backend/start.sh#L1-L38)
- [backend/rpi_setup.sh:1-163](file://backend/rpi_setup.sh#L1-L163)
- [backend/test_all.py:1-484](file://backend/test_all.py#L1-L484)
- [backend/test_dongles.py:1-152](file://backend/test_dongles.py#L1-L152)

**Section sources**
- [backend/README.md:273-306](file://backend/README.md#L273-L306)
- [backend/main.py:14-48](file://backend/main.py#L14-L48)

## Core Components
- FastAPI Application: Central entrypoint initializes CORS, routes, database, authentication, and WebSocket manager.
- Routers: Feature-based API groups for IoT scanning, WiFi/Bluetooth utilities, RFID/NFC, AI analysis, and reports.
- Engines: Security engine computes risk scores and vulnerability flags; AI engine performs pattern analysis and recommendations.
- Database: SQLAlchemy models define Device, Vulnerability, RFIDCard, and Setting tables with initialization and defaults.
- WebSocket Manager: Broadcasts scan progress, device discoveries, and errors to the dashboard in real-time.
- Frontend: Single-page dashboard with charts, device tables, and interactive controls.
- **Development Scripts**: Comprehensive setup, startup, and testing automation for streamlined development workflow.

**Section sources**
- [backend/main.py:14-106](file://backend/main.py#L14-L106)
- [backend/database.py:12-80](file://backend/database.py#L12-L80)
- [backend/websocket_manager.py:7-48](file://backend/websocket_manager.py#L7-L48)
- [backend/security_engine.py:202-340](file://backend/security_engine.py#L202-L340)
- [backend/ai_engine.py:236-766](file://backend/ai_engine.py#L236-L766)

## Architecture Overview
PentexOne uses a layered architecture:
- Presentation Layer: FastAPI routes and WebSocket endpoints serve the dashboard and API clients.
- Business Logic Layer: Routers orchestrate scans, integrate engines, and persist results.
- Data Access Layer: SQLAlchemy models and session management.
- External Integrations: Nmap, Scapy, BLEAK, KillerBee, ReportLab, cryptography.
- **Development Layer**: Automated setup, testing, and deployment scripts for comprehensive quality assurance.

```mermaid
graph TB
CLIENT["Browser/CLI Client"]
API["FastAPI App<br/>main.py"]
WS["WebSocket Manager"]
IOT["IoT Router<br/>routers/iot.py"]
WIFI["WiFi/Bluetooth Router<br/>routers/wifi_bt.py"]
RFID["RFID Router<br/>routers/access_control.py"]
AI["AI Router<br/>routers/ai.py"]
REPORTS["Reports Router<br/>routers/reports.py"]
SEC["Security Engine<br/>security_engine.py"]
AIENG["AI Engine<br/>ai_engine.py"]
DB["Database<br/>database.py"]
DEV_SCRIPTS["Development Scripts<br/>setup.sh, start.sh, test_all.py"]
CLIENT --> API
API --> IOT
API --> WIFI
API --> RFID
API --> AI
API --> REPORTS
API --> WS
IOT --> SEC
WIFI --> SEC
RFID --> SEC
AI --> AIENG
REPORTS --> DB
IOT --> DB
WIFI --> DB
RFID --> DB
AI --> DB
WS --> CLIENT
DEV_SCRIPTS --> API
```

**Diagram sources**
- [backend/main.py:14-106](file://backend/main.py#L14-L106)
- [backend/routers/iot.py:24-620](file://backend/routers/iot.py#L24-L620)
- [backend/routers/wifi_bt.py:27-766](file://backend/routers/wifi_bt.py#L27-L766)
- [backend/routers/access_control.py:13-95](file://backend/routers/access_control.py#L13-L95)
- [backend/routers/ai.py:20-330](file://backend/routers/ai.py#L20-L330)
- [backend/routers/reports.py:15-158](file://backend/routers/reports.py#L15-L158)
- [backend/security_engine.py:202-425](file://backend/security_engine.py#L202-L425)
- [backend/ai_engine.py:236-766](file://backend/ai_engine.py#L236-L766)
- [backend/database.py:12-80](file://backend/database.py#L12-L80)

## Detailed Component Analysis

### Backend Entry Point and Routing
- Initializes database, middleware, static files, and WebSocket manager.
- Exposes authentication, settings, and routing for all feature routers.

```mermaid
sequenceDiagram
participant Client as "Client"
participant API as "FastAPI App"
participant Router as "Router"
participant Engine as "Engine"
participant DB as "Database"
Client->>API : HTTP Request
API->>Router : Route dispatch
Router->>Engine : Invoke analysis/scanner
Engine->>DB : Query/Write records
DB-->>Engine : Results
Engine-->>Router : Structured response
Router-->>API : Response model
API-->>Client : JSON/WebSocket events
```

**Diagram sources**
- [backend/main.py:14-106](file://backend/main.py#L14-L106)
- [backend/routers/iot.py:291-413](file://backend/routers/iot.py#L291-L413)
- [backend/security_engine.py:202-340](file://backend/security_engine.py#L202-L340)
- [backend/database.py:62-80](file://backend/database.py#L62-L80)

**Section sources**
- [backend/main.py:14-106](file://backend/main.py#L14-L106)

### IoT Scanning and Hardware Detection
- Implements Wi-Fi, Matter, Zigbee, Thread, Z-Wave, LoRaWAN, and Bluetooth scanning.
- Uses background tasks and WebSocket broadcasts for progress and results.
- Detects hardware dongles and toggles simulation vs. real scans.

```mermaid
flowchart TD
Start([Start Scan]) --> Detect["Detect Hardware & Mode"]
Detect --> Choice{"Hardware Available?"}
Choice --> |Yes| Real["Real Scan (external libs)"]
Choice --> |No| Sim["Simulated Scan"]
Real --> Background["Background Task"]
Sim --> Background
Background --> Risk["Calculate Risk & Persist"]
Risk --> Broadcast["Broadcast Results"]
Broadcast --> End([End])
```

**Diagram sources**
- [backend/routers/iot.py:27-156](file://backend/routers/iot.py#L27-L156)
- [backend/routers/iot.py:483-586](file://backend/routers/iot.py#L483-L586)
- [backend/security_engine.py:202-340](file://backend/security_engine.py#L202-L340)
- [backend/websocket_manager.py:21-46](file://backend/websocket_manager.py#L21-L46)

**Section sources**
- [backend/routers/iot.py:291-413](file://backend/routers/iot.py#L291-L413)
- [backend/routers/iot.py:483-586](file://backend/routers/iot.py#L483-L586)

### Security Engine
- Computes risk scores from open ports, protocol-specific flags, default credentials, firmware CVEs, TLS issues, and protocol weaknesses.
- Provides remediation guidance per vulnerability type.

```mermaid
flowchart TD
Input["Open Ports + Protocol + Flags"] --> Ports["Port-based Risks"]
Input --> Defaults["Default Credentials"]
Input --> Firmware["Firmware CVEs"]
Input --> TLS["TLS/SSL Issues"]
Ports --> Combine["Aggregate Score"]
Defaults --> Combine
Firmware --> Combine
TLS --> Combine
Combine --> Level["Assign Risk Level"]
Level --> Vulns["Build Vulnerability List"]
Vulns --> Output["Risk Score + Vulns"]
```

**Diagram sources**
- [backend/security_engine.py:202-340](file://backend/security_engine.py#L202-L340)

**Section sources**
- [backend/security_engine.py:202-425](file://backend/security_engine.py#L202-L425)

### AI Engine
- Performs device classification, anomaly detection, network pattern analysis, and recommendation generation.
- Provides dashboard suggestions and remediation guides.

```mermaid
classDiagram
class AISecurityEngine {
+analyze_device(device) Dict
+analyze_network(devices) Dict
+get_smart_dashboard_suggestions(devices, analysis) List
+predict_future_risks(historical_scans) Dict
-_identify_device_type(device) str
-_predict_vulnerabilities(device, type) List
-_calculate_anomaly_score(device) float
-_generate_device_recommendations(device, predictions) List
-_calculate_network_security_score(devices, risk_levels) Dict
}
class REMEDIATION_DATABASE {
+Dict of remediation steps
}
AISecurityEngine --> REMEDIATION_DATABASE : "uses"
```

**Diagram sources**
- [backend/ai_engine.py:236-766](file://backend/ai_engine.py#L236-L766)

**Section sources**
- [backend/ai_engine.py:236-766](file://backend/ai_engine.py#L236-L766)

### Database Schema
- Device, Vulnerability, RFIDCard, and Setting tables with relationships and defaults.

```mermaid
erDiagram
DEVICE {
int id PK
string ip UK
string mac
string hostname
string vendor
string protocol
string os_guess
string risk_level
float risk_score
string open_ports
timestamp last_seen
}
VULNERABILITY {
int id PK
int device_id FK
string vuln_type
string severity
string description
int port
string protocol
}
RFID_CARD {
int id PK
string uid UK
string card_type
string sak
string data
string risk_level
float risk_score
timestamp last_seen
}
SETTING {
string key PK
string value
}
DEVICE ||--o{ VULNERABILITY : "has"
```

**Diagram sources**
- [backend/database.py:12-61](file://backend/database.py#L12-L61)

**Section sources**
- [backend/database.py:12-80](file://backend/database.py#L12-L80)

### Frontend Dashboard
- Single-page application with charts, device tables, and real-time updates via WebSocket.
- Controls for quick scans, advanced options, hardware status, AI suggestions, and report exports.

```mermaid
sequenceDiagram
participant Browser as "Browser"
participant WS as "WebSocket"
participant API as "FastAPI"
participant Router as "Router"
participant Engine as "Engine"
Browser->>WS : Connect /ws
API->>WS : Accept & register
Router->>Engine : Start scan (background)
Engine-->>API : Results
API->>WS : Broadcast progress/results
WS-->>Browser : Update UI (charts, tables)
```

**Diagram sources**
- [backend/static/index.html:1-413](file://backend/static/index.html#L1-L413)
- [backend/static/app.js:113-155](file://backend/static/app.js#L113-L155)
- [backend/websocket_manager.py:7-48](file://backend/websocket_manager.py#L7-L48)
- [backend/routers/iot.py:291-413](file://backend/routers/iot.py#L291-L413)

**Section sources**
- [backend/static/index.html:52-316](file://backend/static/index.html#L52-L316)
- [backend/static/app.js:113-155](file://backend/static/app.js#L113-L155)

### Development Scripts and Testing Framework
- **rpi_setup.sh**: Comprehensive Raspberry Pi installation with system dependencies, virtual environment setup, Bluetooth configuration, and systemd service installation.
- **start.sh**: Quick start script for manual testing and development with automatic virtual environment activation and default credential setup.
- **test_all.py**: Comprehensive test suite validating all endpoints, authentication, hardware detection, scanning functionality, AI analysis, reports, and error handling.
- **test_dongles.py**: Hardware detection script for identifying connected USB dongles (Zigbee, Thread/Matter, Z-Wave, Bluetooth).

```mermaid
flowchart TD
DevScripts["Development Scripts"] --> RPISetup["rpi_setup.sh<br/>Raspberry Pi Installation"]
DevScripts --> StartScript["start.sh<br/>Quick Start"]
DevScripts --> TestAll["test_all.py<br/>Comprehensive Testing"]
DevScripts --> TestDongles["test_dongles.py<br/>Hardware Detection"]
RPISetup --> SystemDeps["System Dependencies<br/>Python, BlueZ, USB, etc."]
RPISetup --> VEnv["Virtual Environment<br/>Requirements Installation"]
RPISetup --> Service["Systemd Service<br/>Auto-start Configuration"]
StartScript --> VEnv
StartScript --> Server["FastAPI Server<br/>Local Development"]
TestAll --> Endpoints["All API Endpoints<br/>Health, Auth, IoT, Wireless, AI, Reports"]
TestAll --> Scanning["Scan Functionality<br/>Wi-Fi, Bluetooth, Zigbee, Thread"]
TestAll --> WebSocket["WebSocket Connection<br/>Real-time Updates"]
TestAll --> ErrorHandling["Error Handling<br/>404, Authentication, etc."]
TestDongles --> DongleDetection["USB Dongle Detection<br/>Zigbee, Thread, Z-Wave, Bluetooth"]
TestDongles --> HardwareValidation["Hardware Validation<br/>KillerBee Integration"]
```

**Diagram sources**
- [backend/rpi_setup.sh:1-163](file://backend/rpi_setup.sh#L1-L163)
- [backend/start.sh:1-38](file://backend/start.sh#L1-L38)
- [backend/test_all.py:1-484](file://backend/test_all.py#L1-L484)
- [backend/test_dongles.py:1-152](file://backend/test_dongles.py#L1-L152)

**Section sources**
- [backend/rpi_setup.sh:1-163](file://backend/rpi_setup.sh#L1-L163)
- [backend/start.sh:1-38](file://backend/start.sh#L1-L38)
- [backend/test_all.py:1-484](file://backend/test_all.py#L1-L484)
- [backend/test_dongles.py:1-152](file://backend/test_dongles.py#L1-L152)

## Dependency Analysis
- Python dependencies managed via requirements.txt; includes FastAPI, Uvicorn, Nmap, Scapy, Zeroconf, ReportLab, SQLAlchemy, BLEAK, PySerial, and optional KillerBee and cryptography.
- Optional hardware support is gated by runtime checks in routers and engines.
- **Development dependencies**: requests, pytest (for comprehensive testing framework).

```mermaid
graph LR
A["FastAPI"] --> B["Uvicorn"]
A --> C["SQLAlchemy"]
A --> D["WebSockets"]
E["Nmap"] --> F["Port Scanning"]
G["Scapy"] --> H["Packet Analysis"]
I["Zeroconf"] --> J["mDNS Discovery"]
K["BLEAK"] --> L["BLE Scanning"]
M["PySerial"] --> N["RFID/Serial"]
O["ReportLab"] --> P["PDF Reports"]
Q["Cryptography"] --> R["TLS Validation"]
S["KillerBee"] --> T["Zigbee Sniffing"]
U["Requests"] --> V["HTTP Testing"]
W["Pytest"] --> X["Unit Testing"]
```

**Diagram sources**
- [backend/requirements.txt:1-21](file://backend/requirements.txt#L1-L21)

**Section sources**
- [backend/requirements.txt:1-21](file://backend/requirements.txt#L1-L21)

## Performance Considerations
- Scans use background tasks and WebSocket broadcasts to avoid blocking the API.
- SQLite is used for simplicity; consider migration to PostgreSQL for high-volume deployments.
- Recommendations include headless mode, powered USB hubs, and Ethernet for stability.
- **RPi 5 Optimization**: CPU governor performance mode during scans for improved hardware detection performance.

## Troubleshooting Guide
Common issues and resolutions:
- Dashboard not accessible: verify service status, port binding, and firewall rules.
- USB dongles not detected: check permissions and reboot after adding user to dialout group.
- Bluetooth not working: restart Bluetooth service and unblock via rfkill.
- **Raspberry Pi specific**: Use rpi_setup.sh for complete system configuration and hardware optimization.

**Section sources**
- [backend/README.md:349-381](file://backend/README.md#L349-L381)

## Development Workflow
Recommended Git workflow:
- Fork the repository.
- Create a feature branch: git checkout -b feature/your-feature-name.
- Commit with clear messages: git commit -m "feat: add new protocol support".
- Push to origin: git push origin feature/your-feature-name.
- Open a Pull Request with a clear description and related issue number.

**Section sources**
- [backend/README.md:404-413](file://backend/README.md#L404-L413)

## Testing Framework
- **Comprehensive Test Suite**: test_all.py validates all endpoints, authentication, hardware detection, scanning functionality, AI analysis, reports, and error handling with detailed progress reporting.
- **Hardware Detection**: test_dongles.py quickly identifies connected USB dongles (Zigbee, Thread/Matter, Z-Wave, Bluetooth) with detailed device information.
- **Unit Tests**: Use pytest to test routers, engines, and models.
- **Integration Tests**: Validate end-to-end flows for scans, WebSocket updates, and report generation.
- **Automated Testing**: Development scripts provide standardized testing environments and validation workflows.

**Updated** Enhanced with comprehensive test_all.py framework and improved hardware validation capabilities.

**Section sources**
- [backend/test_all.py:1-484](file://backend/test_all.py#L1-L484)
- [backend/test_dongles.py:1-152](file://backend/test_dongles.py#L1-L152)

## Adding New Protocol Support
Steps to add a new protocol:
1. Create or extend a scanner in routers/iot.py with hardware detection and background scan logic.
2. Add protocol icon and chart updates in static/index.html and static/app.js.
3. Integrate risk calculations in security_engine.py and update vulnerability flags.
4. Test with test_dongles.py and verify WebSocket broadcasts.
5. **Validate with comprehensive test suite**: Use test_all.py to ensure new endpoints work correctly in the full application context.

```mermaid
flowchart TD
Plan["Plan Scanner & UI Changes"] --> Router["Add Router Endpoint"]
Router --> HW["Detect Hardware/Mode"]
HW --> Scan["Run Scan (Real/Sim)"]
Scan --> Risk["Risk Calculation"]
Risk --> Persist["Persist & Broadcast"]
Persist --> UI["Update Charts/Table"]
UI --> Test["Test with test_all.py"]
Test --> Validate["Validate with test_dongles.py"]
Validate --> Complete["Complete"]
```

**Diagram sources**
- [backend/routers/iot.py:27-156](file://backend/routers/iot.py#L27-L156)
- [backend/security_engine.py:202-340](file://backend/security_engine.py#L202-L340)
- [backend/static/index.html:52-118](file://backend/static/index.html#L52-L118)
- [backend/static/app.js:296-329](file://backend/static/app.js#L296-L329)

**Section sources**
- [backend/README.md:299-306](file://backend/README.md#L299-L306)

## Extending Security Analysis
Enhance risk scoring and vulnerability detection:
- Add new port mappings or protocol-specific flags in security_engine.py.
- Extend remediation database in ai_engine.py for new vulnerability types.
- Update WebSocket events to surface new analysis results.
- **Validate with comprehensive testing**: Use test_all.py to ensure AI endpoints and security scoring work correctly.

**Section sources**
- [backend/security_engine.py:16-340](file://backend/security_engine.py#L16-L340)
- [backend/ai_engine.py:99-233](file://backend/ai_engine.py#L99-L233)

## Contributing to the Frontend
Frontend improvements:
- Update static/index.html for new UI elements and icons.
- Modify static/app.js for new scan flows, charts, and WebSocket handlers.
- Ensure responsive design and accessibility.
- **Test with comprehensive validation**: Use test_all.py to validate frontend interactions and WebSocket communications.

**Section sources**
- [backend/static/index.html:1-413](file://backend/static/index.html#L1-L413)
- [backend/static/app.js:1-1099](file://backend/static/app.js#L1-L1099)

## Development Environment Setup
- **Raspberry Pi Setup**: Use rpi_setup.sh for complete system configuration with RPi 5 optimization, Bluetooth setup, and systemd service installation.
- **Manual Setup**: Run setup.sh to create virtual environment, install dependencies, and initialize directories.
- **Quick Start**: Use start.sh for manual testing or development with automatic virtual environment activation and default credential setup.
- **Environment Configuration**: Configure .env with secure credentials.
- **Service Management**: Use systemctl commands for service lifecycle management.

**Updated** Enhanced with comprehensive rpi_setup.sh automation and improved development workflow.

**Section sources**
- [backend/README.md:69-110](file://backend/README.md#L69-L110)
- [backend/README.md:120-150](file://backend/README.md#L120-L150)
- [backend/setup.sh:1-142](file://backend/setup.sh#L1-L142)
- [backend/start.sh:1-38](file://backend/start.sh#L1-L38)
- [backend/rpi_setup.sh:1-163](file://backend/rpi_setup.sh#L1-L163)

## Documentation Contributions
- Improve backend/README.md for new features or workflows.
- Update inline comments and docstrings for clarity.
- Add usage examples and troubleshooting notes.
- **Include development script documentation**: Document new rpi_setup.sh, start.sh, and test_all.py usage patterns.

**Section sources**
- [backend/README.md:162-179](file://backend/README.md#L162-L179)

## Bug Reporting and Feature Requests
- Use GitHub Issues for bugs and feature requests.
- Include environment details, reproduction steps, and expected vs. actual behavior.
- **Provide test results**: Include output from test_all.py and test_dongles.py when reporting issues.

**Section sources**
- [backend/README.md:435-438](file://backend/README.md#L435-L438)

## Code Review Standards
- Ensure new routers follow consistent patterns (response models, background tasks, WebSocket events).
- Validate database migrations and relationships.
- Confirm security-related changes (authentication, TLS, permissions) are reviewed.
- Verify frontend changes are responsive and accessible.
- **Review development scripts**: Ensure rpi_setup.sh, start.sh, and test_all.py follow best practices and security standards.

**Section sources**
- [backend/main.py:24-32](file://backend/main.py#L24-L32)
- [backend/database.py:62-80](file://backend/database.py#L62-L80)

## Quality Assurance Practices
- **Comprehensive Testing**: Use test_all.py for end-to-end validation of all application features and endpoints.
- **Hardware Validation**: Use test_dongles.py to verify USB dongle detection and hardware compatibility.
- **Automated Testing**: Leverage development scripts for consistent testing environments across different platforms.
- **Linting and formatting**: Use black and flake8.
- **Type hints**: Maintain pydantic models and router signatures.
- **Logging**: Add structured logs for scans and errors.
- **Tests**: Cover critical paths in routers, engines, and WebSocket flows.

**Updated** Enhanced with comprehensive test_all.py framework and improved hardware validation processes.

**Section sources**
- [backend/models.py:1-71](file://backend/models.py#L1-L71)
- [backend/routers/iot.py:17-18](file://backend/routers/iot.py#L17-L18)
- [backend/test_all.py:1-484](file://backend/test_all.py#L1-L484)
- [backend/test_dongles.py:1-152](file://backend/test_dongles.py#L1-L152)

## Release Procedures
- Update version in badges and changelog.
- Run deployment checklist for production readiness.
- Verify service startup, dashboard access, and hardware detection.
- Document breaking changes and migration steps.
- **Validate with comprehensive testing**: Ensure test_all.py passes all tests before release.

**Section sources**
- [backend/DEPLOYMENT_CHECKLIST.md:1-312](file://backend/DEPLOYMENT_CHECKLIST.md#L1-L312)

## Conclusion
This guide consolidates PentexOne's development practices, architecture, and contribution workflows. The addition of comprehensive development scripts (rpi_setup.sh, start.sh, test_all.py) significantly enhances the development experience with automated setup, streamlined testing, and robust quality assurance. By following the outlined procedures—feature branching, commit standards, comprehensive testing with test_all.py, code review, and release practices—you can confidently extend protocol support, enhance security analysis, and improve the frontend while maintaining high-quality, secure, and reliable code.

The new testing framework provides complete coverage of all application features, ensuring that new contributions maintain backward compatibility and meet quality standards. The development scripts simplify environment setup and validation, making it easier for contributors to participate in the project development process.