# Security Engine

<cite>
**Referenced Files in This Document**
- [security_engine.py](file://backend/security_engine.py)
- [ai_engine.py](file://backend/ai_engine.py)
- [database.py](file://backend/database.py)
- [models.py](file://backend/models.py)
- [main.py](file://backend/main.py)
- [routers/iot.py](file://backend/routers/iot.py)
- [routers/ai.py](file://backend/routers/ai.py)
- [websocket_manager.py](file://backend/websocket_manager.py)
- [test_dongles.py](file://backend/test_dongles.py)
- [requirements.txt](file://backend/requirements.txt)
</cite>

## Update Summary
**Changes Made**
- Enhanced AI security engine with new vulnerability prediction algorithms
- Improved risk assessment scoring with expanded device analysis capabilities
- Added advanced pattern recognition and anomaly detection features
- Expanded protocol-specific vulnerability prediction logic
- Enhanced confidence scoring mechanisms for AI-driven insights

## Table of Contents
1. [Introduction](#introduction)
2. [Project Structure](#project-structure)
3. [Core Components](#core-components)
4. [Architecture Overview](#architecture-overview)
5. [Detailed Component Analysis](#detailed-component-analysis)
6. [Enhanced AI Security Engine](#enhanced-ai-security-engine)
7. [Dependency Analysis](#dependency-analysis)
8. [Performance Considerations](#performance-considerations)
9. [Troubleshooting Guide](#troubleshooting-guide)
10. [Conclusion](#conclusion)
11. [Appendices](#appendices)

## Introduction
This document explains PentexOne's security analysis engines, focusing on:
- The security_engine.py implementation: risk calculation algorithms, vulnerability mapping across 8+ IoT protocols, and protocol-specific security assessment logic
- The AI security engine in ai_engine.py: enhanced pattern recognition, improved anomaly detection, predictive analysis, and recommendation generation
- Integration between security analysis and AI-powered insights
- Vulnerability database integration, default credential testing mechanisms, TLS/SSL validation processes, and firmware vulnerability checking
- Performance considerations, accuracy metrics, and confidence scoring
- Examples of security assessment workflows and threat modeling integration

## Project Structure
The backend is organized around modular routers and engines:
- Security engine: risk scoring and protocol-specific vulnerability mapping
- AI engine: enhanced pattern recognition, anomaly detection, and recommendations
- Database models and SQLAlchemy ORM for persistence
- Routers for IoT scanning, AI analysis, and reporting
- WebSocket manager for real-time progress and events
- Hardware detection utilities for dongle verification

```mermaid
graph TB
subgraph "Backend"
SE["security_engine.py"]
AE["ai_engine.py"]
DB["database.py"]
MD["models.py"]
MAIN["main.py"]
ROUT_IOT["routers/iot.py"]
ROUT_AI["routers/ai.py"]
WS["websocket_manager.py"]
TEST["test_dongles.py"]
REQ["requirements.txt"]
end
MAIN --> ROUT_IOT
MAIN --> ROUT_AI
ROUT_IOT --> SE
ROUT_AI --> AE
ROUT_IOT --> DB
ROUT_AI --> DB
ROUT_IOT --> WS
AE --> DB
SE --> DB
TEST --> ROUT_IOT
REQ --> SE
REQ --> AE
```

**Diagram sources**
- [main.py:14-48](file://backend/main.py#L14-L48)
- [routers/iot.py:20-24](file://backend/routers/iot.py#L20-L24)
- [routers/ai.py:10-18](file://backend/routers/ai.py#L10-L18)
- [security_engine.py:12-15](file://backend/security_engine.py#L12-L15)
- [ai_engine.py:15-21](file://backend/ai_engine.py#L15-L21)
- [database.py:1-9](file://backend/database.py#L1-L9)
- [websocket_manager.py:7-47](file://backend/websocket_manager.py#L7-L47)
- [test_dongles.py:14-132](file://backend/test_dongles.py#L14-L132)
- [requirements.txt:1-21](file://backend/requirements.txt#L1-L21)

**Section sources**
- [main.py:14-48](file://backend/main.py#L14-L48)
- [requirements.txt:1-21](file://backend/requirements.txt#L1-L21)

## Core Components
- Security Engine (security_engine.py)
  - Risk calculation from open ports, default credentials, firmware CVEs, TLS/SSL issues, and protocol-specific vulnerabilities
  - Protocol-specific vulnerability sets for Zigbee, Matter, Bluetooth, RFID, Z-Wave, LoRaWAN, and Thread
  - TLS/SSL validation logic for protocol version, certificate expiration, self-signed certs, and cipher suite checks
  - Remediation mapping for actionable fixes
- AI Engine (ai_engine.py)
  - Enhanced device pattern recognition across IoT categories (cameras, routers, smart home, industrial, medical)
  - Advanced anomaly detection and confidence scoring with improved algorithms
  - Network-wide analysis, risk trend prediction, and dashboard suggestions
  - Expanded remediation knowledge base with prioritized steps
  - Protocol-based risk multipliers for comprehensive analysis
- Database and Models (database.py, models.py)
  - ORM models for devices, vulnerabilities, RFID cards, and settings
  - SQLite-backed persistence with initialization and default settings
- Routers (routers/iot.py, routers/ai.py)
  - IoT scanning across Wi-Fi, Matter, Zigbee, Thread, Z-Wave, LoRaWAN with real/hardware fallback
  - AI analysis endpoints for single device, network-wide analysis, remediation guides, and security score
  - WebSocket broadcasting for scan progress and events
- Websocket Manager (websocket_manager.py)
  - Thread-safe broadcast for real-time UI updates
- Hardware Detection (test_dongles.py)
  - Utility to detect and report connected dongles for Zigbee, Thread/Matter, Z-Wave, and Bluetooth

**Section sources**
- [security_engine.py:16-424](file://backend/security_engine.py#L16-L424)
- [ai_engine.py:236-766](file://backend/ai_engine.py#L236-L766)
- [database.py:12-79](file://backend/database.py#L12-L79)
- [models.py:6-71](file://backend/models.py#L6-L71)
- [routers/iot.py:20-880](file://backend/routers/iot.py#L20-L880)
- [routers/ai.py:10-330](file://backend/routers/ai.py#L10-L330)
- [websocket_manager.py:7-47](file://backend/websocket_manager.py#L7-L47)
- [test_dongles.py:14-132](file://backend/test_dongles.py#L14-L132)

## Architecture Overview
The system integrates passive and active scanning with AI-driven insights:
- IoT routers orchestrate scans across protocols, persist results, and trigger security engine calculations
- AI router consumes persisted device data to classify, predict, and recommend remediation
- WebSocket manager broadcasts live scan progress and device discoveries
- Database stores devices, vulnerabilities, RFID cards, and settings

```mermaid
sequenceDiagram
participant Client as "Dashboard/UI"
participant IOT as "IoT Router"
participant SE as "Security Engine"
participant DB as "Database"
participant WS as "WebSocket Manager"
participant AI as "AI Router"
participant AE as "AI Engine"
Client->>IOT : "POST /iot/scan/{protocol}"
IOT->>WS : "Broadcast scan_progress"
IOT->>SE : "calculate_risk(open_ports, protocol, flags)"
SE-->>IOT : "risk_level, risk_score, vulnerabilities"
IOT->>DB : "Upsert Device + Vulnerabilities"
IOT->>WS : "Broadcast device_found, scan_finished"
Client->>AI : "GET /ai/analyze/device/{id}"
AI->>DB : "Load Device + Vulnerabilities"
AI->>AE : "analyze_device(device_dict)"
AE-->>AI : "device_type, predicted_vulnerabilities, recommendations, confidence"
AI-->>Client : "Analysis results"
```

**Diagram sources**
- [routers/iot.py:291-413](file://backend/routers/iot.py#L291-L413)
- [security_engine.py:202-339](file://backend/security_engine.py#L202-L339)
- [database.py:12-42](file://backend/database.py#L12-L42)
- [websocket_manager.py:21-45](file://backend/websocket_manager.py#L21-L45)
- [routers/ai.py:26-64](file://backend/routers/ai.py#L26-L64)
- [ai_engine.py:247-275](file://backend/ai_engine.py#L247-L275)

## Detailed Component Analysis

### Security Engine: Risk Calculation and Protocol Mapping
- Risk calculation algorithm
  - Aggregates weighted scores from critical/medium ports, default credentials, protocol-specific vulnerabilities, TLS/SSL issues, and firmware CVEs
  - Caps risk score at 100 and maps to SAFE/MEDIUM/RISK
- Vulnerability mapping across 8+ IoT protocols
  - TCP port mappings for critical/medium/high severity
  - Default credentials list for common IoT vendors and device families
  - Protocol-specific vulnerability sets:
    - Zigbee: default keys, no encryption, replay attacks
    - Matter: open commissioning, expired DAC, missing passcode
    - Bluetooth: no pairing, weak auth, exposed characteristics
    - RFID: default keys, cloneability, legacy crypto, no mutual auth, Desweet attack
    - Z-Wave: no encryption, inclusion vulnerability, replay, network key exposure
    - LoRaWAN: ABF confirmation, weak DevNonce, no ADR limits, join-request flood
    - Thread: no commissioner auth, active commissioner, weak network key, border router exposure
- TLS/SSL validation
  - Protocol version checks (SSLv3, TLS 1.0, TLS 1.1)
  - Certificate checks (expiration, self-signed)
  - Remediation mapping for each vulnerability type
- Firmware vulnerability checking
  - Device-type-to-version mapping with associated CVEs and severities
- Remediation mapping
  - Actionable steps for each vulnerability type

```mermaid
flowchart TD
Start(["calculate_risk"]) --> Init["Initialize score=0, vulns=[]"]
Init --> CheckPorts["Check open_ports vs CRITICAL_PORTS/MEDIUM_PORTS"]
CheckPorts --> PortsFound{"Any matches?"}
PortsFound --> |Yes| AddPortScore["Add weighted score<br/>and append vulnerability"]
PortsFound --> |No| CheckCreds["Check default_creds flag"]
AddPortScore --> CheckCreds
CheckCreds --> CredsFound{"Default creds?"}
CredsFound --> |Yes| AddCreds["Add DEFAULT_CREDENTIALS +50"]
CredsFound --> |No| CheckProtocol["Check protocol-specific flags"]
AddCreds --> CheckProtocol
CheckProtocol --> Zigbee{"Protocol Zigbee?"}
Zigbee --> |Yes| AddZigbee["Add Zigbee vulns"]
Zigbee --> |No| Matter{"Protocol Matter?"}
Matter --> |Yes| AddMatter["Add Matter vulns"]
Matter --> |No| Bluetooth{"Protocol Bluetooth?"}
Bluetooth --> |Yes| AddBT["Add Bluetooth vulns"]
Bluetooth --> |No| RFID{"Protocol RFID?"}
RFID --> |Yes| AddRFID["Add RFID vulns"]
RFID --> |No| ZWave{"Protocol Z-Wave?"}
ZWave --> |Yes| AddZW["Add Z-Wave vulns"]
ZWave --> |No| LoRa{"Protocol LoRaWAN?"}
LoRa --> |Yes| AddLora["Add LoRaWAN vulns"]
LoRa --> |No| Thread{"Protocol Thread?"}
Thread --> |Yes| AddThread["Add Thread vulns"]
Thread --> |No| TLS["Check tls_issues"]
TLS --> TLSFound{"TLS issues?"}
TLSFound --> |Yes| AddTLS["Add TLS/SSL vulns"]
TLSFound --> |No| FW["Check firmware_info"]
AddTLS --> FW
FW --> FWFound{"Firmware in VULNERABLE_FIRMWARE?"}
FWFound --> |Yes| AddFW["Add CVE vulnerability"]
FWFound --> |No| CapScore["Cap score at 100"]
AddFW --> CapScore
CapScore --> CalcLevel["Map score to SAFE/MEDIUM/RISK"]
CalcLevel --> Return(["Return {risk_level, risk_score, vulnerabilities}"])
```

**Diagram sources**
- [security_engine.py:202-339](file://backend/security_engine.py#L202-L339)

**Section sources**
- [security_engine.py:16-424](file://backend/security_engine.py#L16-L424)

### TLS/SSL Validation Logic
- Validates protocol versions and certificates
- Detects SSLv3, TLS 1.0, TLS 1.1 deprecations
- Identifies expired or self-signed certificates
- Returns a list of vulnerability identifiers for downstream risk calculation

```mermaid
sequenceDiagram
participant Caller as "Caller"
participant SE as "Security Engine"
participant SSL as "TLS Library"
Caller->>SE : "assess_tls_security(hostname, port)"
SE->>SSL : "Create context and wrap_socket"
SSL-->>SE : "Protocol version and peer cert"
SE->>SE : "Check version and cert fields"
SE-->>Caller : "List of TLS vulnerability identifiers"
```

**Diagram sources**
- [security_engine.py:342-389](file://backend/security_engine.py#L342-L389)

**Section sources**
- [security_engine.py:342-389](file://backend/security_engine.py#L342-L389)

## Enhanced AI Security Engine

### Advanced Pattern Recognition and Anomaly Detection
The AI security engine has been significantly enhanced with improved algorithms for device classification and anomaly detection:

- **Enhanced Device Classification**
  - Keyword-based and port-based pattern matching for cameras, routers, smart home, industrial, and medical devices
  - Risk factor weights per pattern guide predictions with improved accuracy
  - Protocol-based risk multipliers for comprehensive analysis across Wi-Fi, Bluetooth, Zigbee, Thread, Z-Wave, and LoRaWAN
- **Advanced Anomaly Detection**
  - Enhanced anomaly scoring with improved threshold detection (0.85 threshold)
  - Multi-factor analysis including unusual open ports, unknown vendors, and high-risk scores
  - Dynamic confidence adjustment based on device characteristics
- **Expanded Vulnerability Prediction**
  - Vendor-specific predictions for known vulnerable devices (Hikvision, Dahua, Foscam)
  - Protocol-based vulnerability prediction with confidence scoring
  - Typical vulnerability patterns extracted from device type patterns
- **Improved Confidence Scoring**
  - Enhanced confidence calculation considering device type, vendor, open ports, and protocol presence
  - Minimum confidence threshold of 0.5 with progressive increases
  - Context-aware confidence adjustments for different device characteristics

```mermaid
classDiagram
class AISecurityEngine {
+analyze_device(device) Dict
+analyze_network_patterns(devices) Dict
+predict_future_risks(historical_scans) Dict
+get_smart_dashboard_suggestions(devices, analysis) List
+_identify_device_type(device) str
+_predict_vulnerabilities(device, device_type) List
+_calculate_anomaly_score(device) float
+_generate_device_recommendations(device, predicted_vulns) List
+_calculate_confidence(device, device_type) float
+_detect_network_anomalies(devices, device_types, protocols) List
+_generate_network_recommendations(devices, device_types, risk_levels, anomalies) List
+_calculate_network_security_score(devices, risk_levels) Dict
}
```

**Diagram sources**
- [ai_engine.py:236-740](file://backend/ai_engine.py#L236-L740)

**Section sources**
- [ai_engine.py:236-766](file://backend/ai_engine.py#L236-L766)

### Network-Wide Analysis and Risk Prediction
The AI engine now provides comprehensive network analysis capabilities:

- **Pattern Analysis**
  - Device type distribution analysis with minimum device threshold (3 devices)
  - Protocol distribution across Wi-Fi, Bluetooth, Zigbee, Thread, Z-Wave, and LoRaWAN
  - Risk level distribution (SAFE, MEDIUM, RISK) with vendor composition analysis
- **Anomaly Detection**
  - High-risk device ratio detection (>30% high-risk devices)
  - Unencrypted protocol monitoring (Wi-Fi, Bluetooth)
  - Unknown device type identification (>20% unknown devices)
- **Risk Trend Prediction**
  - Historical scan analysis for risk escalation prediction
  - Trend direction analysis (increasing, decreasing, stable)
  - Predictive risk device counting with confidence intervals
- **Security Score Calculation**
  - Weighted network security score (0-100 scale)
  - Letter-grade assignment (A-F) with descriptive analysis
  - Breakdown of device classifications for improvement planning

```mermaid
sequenceDiagram
participant Client as "Dashboard/UI"
participant AI as "AI Router"
participant DB as "Database"
participant AE as "AI Engine"
Client->>AI : "GET /ai/analyze/network"
AI->>DB : "SELECT * FROM devices"
AI->>AE : "analyze_network_patterns(devices_dict)"
AE-->>AI : "distributions, anomalies, recommendations, score"
AI-->>Client : "Analysis results"
```

**Diagram sources**
- [routers/ai.py:70-100](file://backend/routers/ai.py#L70-L100)
- [ai_engine.py:464-513](file://backend/ai_engine.py#L464-L513)

**Section sources**
- [routers/ai.py:26-330](file://backend/routers/ai.py#L26-L330)
- [ai_engine.py:236-766](file://backend/ai_engine.py#L236-L766)

### IoT Scanning and Integration with Security Engine
- Wi-Fi scanning with nmap
  - Discovers hosts, open ports, OS guess, and persists results
  - Calls security engine to compute risk and vulnerabilities
- Protocol-specific scans
  - Matter: mDNS discovery via Zeroconf
  - Zigbee: real sniffing with KillerBee or simulated discovery
  - Thread/Matter: real hardware via nRF52840 or simulated discovery
  - Z-Wave: simulated discovery with serial probing
  - LoRaWAN: simulated discovery with protocol-specific flags
- Real-time updates
  - WebSocket broadcasts device_found and scan_progress events
- Hardware detection
  - Utility to detect dongles and verify KillerBee availability

```mermaid
sequenceDiagram
participant Client as "Dashboard/UI"
participant IOT as "IoT Router"
participant NM as "nmap"
participant SE as "Security Engine"
participant DB as "Database"
participant WS as "WebSocket Manager"
Client->>IOT : "POST /iot/scan/wifi"
IOT->>WS : "Broadcast scan_progress"
IOT->>NM : "Scan hosts with targeted ports"
NM-->>IOT : "Hosts, open ports, OS guess"
IOT->>SE : "calculate_risk(open_ports, 'Wi-Fi')"
SE-->>IOT : "risk_level, risk_score, vulnerabilities"
IOT->>DB : "Upsert Device + Vulnerabilities"
IOT->>WS : "Broadcast device_found, scan_finished"
```

**Diagram sources**
- [routers/iot.py:291-413](file://backend/routers/iot.py#L291-L413)
- [security_engine.py:202-339](file://backend/security_engine.py#L202-L339)
- [websocket_manager.py:21-45](file://backend/websocket_manager.py#L21-L45)

**Section sources**
- [routers/iot.py:291-880](file://backend/routers/iot.py#L291-L880)
- [test_dongles.py:14-132](file://backend/test_dongles.py#L14-L132)

### AI Analysis Endpoints and Integration
- Single device analysis
  - Loads device and vulnerabilities from DB, runs AI analysis, returns predictions and recommendations
- Network-wide analysis
  - Counts distributions, detects anomalies, generates recommendations, and computes network security score
- Remediation guides
  - Returns detailed steps for a specific vulnerability type
- Security score endpoint
  - Computes weighted score across risk levels and suggests improvements

```mermaid
sequenceDiagram
participant Client as "Dashboard/UI"
participant AI as "AI Router"
participant DB as "Database"
participant AE as "AI Engine"
Client->>AI : "GET /ai/analyze/network"
AI->>DB : "SELECT * FROM devices"
AI->>AE : "analyze_network_patterns(devices_dict)"
AE-->>AI : "distributions, anomalies, recommendations, score"
AI-->>Client : "Analysis results"
```

**Diagram sources**
- [routers/ai.py:70-100](file://backend/routers/ai.py#L70-L100)
- [ai_engine.py:464-513](file://backend/ai_engine.py#L464-L513)

**Section sources**
- [routers/ai.py:26-330](file://backend/routers/ai.py#L26-L330)
- [ai_engine.py:236-766](file://backend/ai_engine.py#L236-L766)

## Dependency Analysis
- External libraries
  - FastAPI, Uvicorn, WebSockets for API and real-time
  - python-nmap for Wi-Fi scanning
  - zeroconf for Matter discovery
  - bleak for Bluetooth scanning
  - pyserial for dongle communication
  - cryptography for TLS certificate parsing
  - SQLAlchemy for ORM and SQLite
  - Optional KillerBee for Zigbee sniffing
- Internal dependencies
  - IoT router depends on security_engine.calculate_risk
  - AI router depends on ai_engine.AISecurityEngine and database models
  - WebSocket manager is shared across routers for broadcast events

```mermaid
graph LR
IOT["routers/iot.py"] --> SE["security_engine.py"]
IOT --> DB["database.py"]
IOT --> WS["websocket_manager.py"]
AI["routers/ai.py"] --> AE["ai_engine.py"]
AI --> DB
AE --> DB
SE --> DB
REQ["requirements.txt"] --> IOT
REQ --> AI
```

**Diagram sources**
- [requirements.txt:1-21](file://backend/requirements.txt#L1-L21)
- [routers/iot.py:20-24](file://backend/routers/iot.py#L20-L24)
- [routers/ai.py:10-18](file://backend/routers/ai.py#L10-L18)
- [security_engine.py:12-15](file://backend/security_engine.py#L12-L15)
- [ai_engine.py:15-21](file://backend/ai_engine.py#L15-L21)

**Section sources**
- [requirements.txt:1-21](file://backend/requirements.txt#L1-L21)
- [routers/iot.py:20-24](file://backend/routers/iot.py#L20-L24)
- [routers/ai.py:10-18](file://backend/routers/ai.py#L10-L18)

## Performance Considerations
- Scanning performance
  - Wi-Fi scan uses targeted ports and service version detection to balance speed and insight
  - Background tasks prevent blocking the main event loop; WebSocket broadcasts provide progress updates
- Risk calculation
  - O(n) over open ports and protocol-specific checks; bounded by small fixed-size maps
  - Early exits for missing flags reduce overhead
- AI analysis
  - Enhanced pattern matching and anomaly detection with improved computational efficiency
  - Network-wide analysis scales linearly with device count with optimized algorithms
- Database writes
  - Batched upserts and deletions of vulnerabilities per device minimize transaction overhead
- TLS validation
  - Short timeouts and minimal socket operations; exceptions are handled gracefully

## Troubleshooting Guide
- Hardware detection
  - Use the dongle test utility to verify connected dongles and KillerBee availability
- Scanning issues
  - Ensure nmap and protocol-specific tools are installed; verify permissions for serial/dongle access
  - Check WebSocket connectivity for real-time progress
- TLS validation failures
  - Confirm target host exposes a TLS endpoint; verify DNS resolution and firewall rules
- Database initialization
  - On startup, tables are created and default settings initialized if missing

**Section sources**
- [test_dongles.py:134-152](file://backend/test_dongles.py#L134-L152)
- [routers/iot.py:291-413](file://backend/routers/iot.py#L291-L413)
- [websocket_manager.py:21-45](file://backend/websocket_manager.py#L21-L45)
- [security_engine.py:342-389](file://backend/security_engine.py#L342-L389)
- [database.py:69-80](file://backend/database.py#L69-L80)

## Conclusion
PentexOne's enhanced security engines combine deterministic risk scoring with AI-driven pattern recognition and advanced anomaly detection. The security engine provides robust protocol-specific assessments and remediation guidance, while the AI engine offers scalable classification, prediction, and recommendations with improved accuracy and confidence scoring. Together with real-time scanning and database persistence, the system delivers comprehensive actionable insights for IoT security postures.

## Appendices

### Example Workflows and Threat Modeling Integration
- Wi-Fi security assessment
  - Start Wi-Fi scan; receive device discoveries and vulnerabilities; review remediation steps; monitor with AI predictions
- Protocol-specific assessment
  - Run Zigbee/Thread/Z-Wave/LoRaWAN scans; address protocol-specific vulnerabilities; validate TLS for exposed services
- Threat modeling integration
  - Use AI-generated device classifications to model attack surfaces; leverage enhanced anomaly detection to identify outliers; apply remediation priorities aligned with risk trends