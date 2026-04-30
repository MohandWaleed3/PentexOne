# Access Control API

<cite>
**Referenced Files in This Document**
- [main.py](file://backend/main.py)
- [access_control.py](file://backend/routers/access_control.py)
- [models.py](file://backend/models.py)
- [database.py](file://backend/database.py)
- [security_engine.py](file://backend/security_engine.py)
- [reports.py](file://backend/routers/reports.py)
- [websocket_manager.py](file://backend/websocket_manager.py)
- [index.html](file://backend/static/index.html)
</cite>

## Update Summary
**Changes Made**
- Updated authentication system section to reflect removal of experimental authentication system
- Added CORS configuration details for production-ready setup
- Updated middleware section to reflect disabled authentication middleware
- Revised security considerations to reflect public API endpoints
- Updated deployment configuration for production environments

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
10. [Appendices](#appendices)

## Introduction
This document provides comprehensive API documentation for the PentexOne RFID/NFC access control scanning and analysis endpoints. It covers RFID card scanning operations, NFC tag analysis, access control system auditing, and security risk assessment for credential-based systems. The documentation includes endpoint definitions, request/response schemas, integration patterns, and practical workflows for security analysis and reporting.

**Updated**: The authentication system has been removed as part of the production-ready configuration. All endpoints are now publicly accessible without authentication requirements.

## Project Structure
The backend is organized around a FastAPI application with modular routers. The access control module resides under the routers package and integrates with the database and security engine to evaluate risk and persist results.

```mermaid
graph TB
A["main.py<br/>Application entrypoint"] --> B["routers/access_control.py<br/>RFID endpoints"]
A --> C["database.py<br/>SQLAlchemy models"]
A --> D["security_engine.py<br/>Risk calculation"]
A --> E["routers/reports.py<br/>Audit report generation"]
A --> F["websocket_manager.py<br/>WebSocket broadcast"]
A --> G["static/index.html<br/>Dashboard UI"]
B --> C
B --> D
E --> C
```

**Diagram sources**
- [main.py:1-145](file://backend/main.py#L1-L145)
- [access_control.py:1-95](file://backend/routers/access_control.py#L1-L95)
- [database.py:1-80](file://backend/database.py#L1-L80)
- [security_engine.py:1-425](file://backend/security_engine.py#L1-L425)
- [reports.py:1-158](file://backend/routers/reports.py#L1-L158)
- [websocket_manager.py:1-56](file://backend/websocket_manager.py#L1-L56)
- [index.html:1-716](file://backend/static/index.html#L1-L716)

**Section sources**
- [main.py:14-48](file://backend/main.py#L14-L48)

## Core Components
- Access Control Router: Implements RFID scanning, card listing, and cleanup endpoints.
- Database Layer: Defines RFIDCard model and settings storage.
- Security Engine: Computes risk scores and flags for RFID/NFC vulnerabilities.
- Reports Router: Generates PDF audit reports including RFID/NFC findings.
- Frontend Integration: Dashboard UI triggers RFID scans and displays results.
- CORS Middleware: Implements production-ready CORS configuration with configurable origins.

**Updated**: Authentication system has been removed. All endpoints are now publicly accessible.

**Section sources**
- [access_control.py:13-95](file://backend/routers/access_control.py#L13-L95)
- [database.py:44-55](file://backend/database.py#L44-L55)
- [security_engine.py:156-163](file://backend/security_engine.py#L156-L163)
- [reports.py:138-154](file://backend/routers/reports.py#L138-L154)
- [index.html:318-344](file://backend/static/index.html#L318-L344)

## Architecture Overview
The RFID access control flow integrates hardware or simulated input, risk evaluation, persistence, and reporting with a production-ready CORS configuration.

```mermaid
sequenceDiagram
participant Client as "Dashboard UI"
participant API as "FastAPI App"
participant AC as "Access Control Router"
participant DB as "Database"
participant SE as "Security Engine"
participant WS as "WebSocket Manager"
Client->>API : POST /rfid/scan
API->>AC : route handler
alt Simulation Mode Enabled
AC->>AC : simulate_rfid_read()
AC-->>API : {uid, card_type, risk_flags}
else Real Hardware Available
AC->>AC : real_rfid_read()
AC-->>API : {uid, card_type, risk_flags}
else No Hardware Found
AC-->>API : error response
end
API->>SE : calculate_risk(..., "RFID", risk_flags)
SE-->>API : {risk_level, risk_score, vulnerabilities}
API->>DB : save RFIDCard record
DB-->>API : success
API-->>Client : {status, message}
API->>WS : broadcast heartbeat
```

**Diagram sources**
- [access_control.py:47-84](file://backend/routers/access_control.py#L47-L84)
- [security_engine.py:202-339](file://backend/security_engine.py#L202-L339)
- [database.py:44-55](file://backend/database.py#L44-L55)
- [main.py:127-144](file://backend/main.py#L127-L144)

## Detailed Component Analysis

### RFID Scanning Endpoint
- Path: POST /rfid/scan
- Purpose: Trigger RFID/NFC card scanning and evaluate security risk.
- Behavior:
  - Reads simulation mode setting from the database.
  - If simulation mode is true, generates mock card data with risk flags.
  - Otherwise attempts to read from a real serial RFID reader.
  - Calculates risk using the security engine with protocol "RFID".
  - Persists the card record with computed risk metrics.
  - Returns a success or error message.

```mermaid
flowchart TD
Start(["POST /rfid/scan"]) --> CheckSim["Check simulation_mode setting"]
CheckSim --> SimEnabled{"Simulation Enabled?"}
SimEnabled --> |Yes| Simulate["simulate_rfid_read()<br/>Generate mock UID, type, flags"]
SimEnabled --> |No| RealRead["real_rfid_read()<br/>Serial port read"]
RealRead --> HasData{"Data Available?"}
HasData --> |No| ReturnError["Return error: enable simulation or connect hardware"]
HasData --> |Yes| Flags["risk_flags from reader"]
Simulate --> Flags
Flags --> CalcRisk["calculate_risk(..., 'RFID', flags)"]
CalcRisk --> Persist["Save RFIDCard to DB"]
Persist --> Done(["Return success message"])
ReturnError --> Done
```

**Diagram sources**
- [access_control.py:47-84](file://backend/routers/access_control.py#L47-L84)
- [access_control.py:15-27](file://backend/routers/access_control.py#L15-L27)
- [access_control.py:29-45](file://backend/routers/access_control.py#L29-L45)
- [security_engine.py:268-273](file://backend/security_engine.py#L268-L273)
- [database.py:44-55](file://backend/database.py#L44-L55)

**Section sources**
- [access_control.py:47-84](file://backend/routers/access_control.py#L47-L84)

### Card Listing Endpoint
- Path: GET /rfid/cards
- Purpose: Retrieve all scanned RFID cards ordered by last seen time.
- Response: Array of RFIDCardOut objects.

```mermaid
sequenceDiagram
participant Client as "Dashboard UI"
participant API as "FastAPI App"
participant AC as "Access Control Router"
participant DB as "Database"
Client->>API : GET /rfid/cards
API->>AC : route handler
AC->>DB : query RFIDCard order_by(last_seen.desc())
DB-->>AC : list of records
AC-->>API : list[RFIDCardOut]
API-->>Client : JSON array
```

**Diagram sources**
- [access_control.py:86-88](file://backend/routers/access_control.py#L86-L88)
- [models.py:55-66](file://backend/models.py#L55-L66)
- [database.py:44-55](file://backend/database.py#L44-L55)

**Section sources**
- [access_control.py:86-88](file://backend/routers/access_control.py#L86-L88)
- [models.py:55-66](file://backend/models.py#L55-L66)

### Card Cleanup Endpoint
- Path: DELETE /rfid/cards
- Purpose: Remove all stored RFID card records.
- Response: Standard success message.

**Section sources**
- [access_control.py:90-94](file://backend/routers/access_control.py#L90-L94)

### RFID Data Model and Risk Schema
- RFIDCardOut: Defines the serialized representation of RFID card records for API responses.
- RFIDCard: SQLAlchemy model persisted to the database with fields for UID, card type, SAK, raw data, risk level, risk score, and timestamps.

```mermaid
erDiagram
RFID_CARD {
int id PK
string uid UK
string card_type
string sak
string data
string risk_level
float risk_score
datetime last_seen
}
```

**Diagram sources**
- [database.py:44-55](file://backend/database.py#L44-L55)
- [models.py:55-66](file://backend/models.py#L55-L66)

**Section sources**
- [database.py:44-55](file://backend/database.py#L44-L55)
- [models.py:55-66](file://backend/models.py#L55-L66)

### Security Risk Assessment for RFID/NFC
- Risk calculation considers RFID-specific vulnerability flags such as default keys, cloneability, legacy crypto, and mutual authentication.
- Risk level is derived from aggregated score thresholds.

```mermaid
flowchart TD
Start(["calculate_risk(open_ports, 'RFID', extra_flags)"]) --> IterateFlags["Iterate RFID flags"]
IterateFlags --> ApplyWeight["Apply weights by severity"]
ApplyWeight --> SumScore["Sum total score"]
SumScore --> Clamp["Clamp to 0-100"]
Clamp --> Classify{"Score <= 40?"}
Classify --> |Yes| Medium["risk_level = MEDIUM"]
Classify --> |No| Risk["risk_level = RISK"]
Medium --> Output(["Return {risk_level, risk_score, vulnerabilities}"])
Risk --> Output
```

**Diagram sources**
- [security_engine.py:268-273](file://backend/security_engine.py#L268-L273)
- [security_engine.py:325-339](file://backend/security_engine.py#L325-L339)

**Section sources**
- [security_engine.py:156-163](file://backend/security_engine.py#L156-L163)
- [security_engine.py:202-339](file://backend/security_engine.py#L202-L339)

### Access Control System Integration
- The dashboard UI triggers RFID scans and displays results, enabling operators to review risk levels and take remediation actions.
- The WebSocket endpoint maintains persistent connections for heartbeat messages.

```mermaid
sequenceDiagram
participant UI as "Dashboard UI"
participant WS as "WebSocket /ws"
participant API as "FastAPI App"
UI->>API : Connect to /ws
API->>WS : accept connection
loop Heartbeat
API->>UI : {"event" : "heartbeat","status" : "active"}
UI-->>API : ping
end
```

**Diagram sources**
- [main.py:114-125](file://backend/main.py#L114-L125)
- [websocket_manager.py:7-47](file://backend/websocket_manager.py#L7-L47)

**Section sources**
- [index.html:318-344](file://backend/static/index.html#L318-L344)
- [main.py:114-125](file://backend/main.py#L114-L125)
- [websocket_manager.py:7-47](file://backend/websocket_manager.py#L7-L47)

### CORS Configuration and Production Deployment
**New Section**: The application now implements a production-ready CORS configuration with configurable origins.

- CORS Origins: Configurable via environment variable `PENTEX_CORS_ORIGINS`
- Default Origins: Allows localhost and LAN access for development
- Production Usage: Set to specific domains for production deployments
- Security: Restricts cross-origin requests to configured origins only

**Section sources**
- [main.py:48-66](file://backend/main.py#L48-L66)

### Authentication System Removal
**Updated**: The experimental authentication system has been completely removed from the application.

- Removed Login Endpoint: No longer available
- Removed Login Page: No longer exists
- Removed Authentication Middleware: Disabled for development
- Public Endpoints: All API endpoints are now publicly accessible
- Security Implications: Requires external security measures for production deployments

**Section sources**
- [main.py:39-44](file://backend/main.py#L39-L44)
- [main.py:74-76](file://backend/main.py#L74-L76)
- [main.py:108-112](file://backend/main.py#L108-L112)

## Dependency Analysis
- Access Control Router depends on:
  - Database session for CRUD operations.
  - Security Engine for risk computation.
  - Settings model to toggle simulation mode.
- Reports Router depends on RFIDCard model for inclusion in PDF reports.
- Frontend depends on API endpoints for data and actions.

```mermaid
graph LR
AC["access_control.py"] --> DB["database.py"]
AC --> SE["security_engine.py"]
AC --> Models["models.py"]
Reports["reports.py"] --> DB
Reports --> Models
UI["index.html"] --> API["main.py"]
API --> AC
API --> Reports
```

**Diagram sources**
- [access_control.py:9-11](file://backend/routers/access_control.py#L9-L11)
- [database.py:1-80](file://backend/database.py#L1-L80)
- [security_engine.py:1-425](file://backend/security_engine.py#L1-L425)
- [models.py:1-71](file://backend/models.py#L1-L71)
- [reports.py:12-13](file://backend/routers/reports.py#L12-L13)
- [index.html:1-716](file://backend/static/index.html#L1-L716)
- [main.py:14-48](file://backend/main.py#L14-L48)

**Section sources**
- [access_control.py:9-11](file://backend/routers/access_control.py#L9-L11)
- [reports.py:138-154](file://backend/routers/reports.py#L138-L154)

## Performance Considerations
- Simulation mode reduces hardware dependencies and latency for development/testing.
- Risk calculation is lightweight and suitable for real-time feedback.
- Database writes are minimal per scan; batching operations can reduce overhead if scaling.
- CORS middleware adds minimal overhead for cross-origin request handling.
- WebSocket connections maintained for real-time monitoring.

## Troubleshooting Guide
- RFID scan returns error indicating no hardware found:
  - Enable simulation mode in settings or connect a compatible RFID reader.
- Serial communication failures:
  - Verify permissions and port availability; ensure the reader is compatible and powered.
- Risk assessment appears inconsistent:
  - Confirm the presence of RFID-specific flags and adjust simulation/test data accordingly.
- CORS errors in browser console:
  - Configure `PENTEX_CORS_ORIGINS` environment variable with your frontend domain(s).
- Authentication errors:
  - Authentication system has been removed; all endpoints are now public.

**Section sources**
- [access_control.py:57-64](file://backend/routers/access_control.py#L57-L64)
- [access_control.py:29-45](file://backend/routers/access_control.py#L29-L45)
- [main.py:48-66](file://backend/main.py#L48-L66)

## Conclusion
The Access Control API provides a focused set of endpoints for RFID/NFC scanning, risk evaluation, and auditing. It integrates seamlessly with the broader PentexOne platform, enabling operators to assess credential-based access systems, track card inventories, and generate comprehensive security reports. The removal of the authentication system simplifies deployment while requiring external security measures for production environments.

## Appendices

### API Definitions

- POST /rfid/scan
  - Description: Initiates RFID/NFC card scanning.
  - Request: None (uses settings to determine simulation vs. real hardware).
  - Response: JSON object with status and message; on success includes card identifier.
  - Example response:
    - {"status":"success","message":"Card scanned: AA:BB:CC:DD:EE:FF"}

- GET /rfid/cards
  - Description: Lists all scanned RFID cards.
  - Response: Array of RFIDCardOut objects.
  - Example response:
    - [{"id":1,"uid":"AA:BB:CC:DD:EE:FF","card_type":"Mifare Classic 1K","sak":"","data":"","risk_level":"RISK","risk_score":85.0,"last_seen":"2025-01-01T12:00:00Z"}]

- DELETE /rfid/cards
  - Description: Clears all stored RFID card records.
  - Response: JSON object with status and message.

- GET /settings
  - Description: Retrieves system settings (including simulation_mode).
  - Response: JSON object mapping setting keys to values.

- PUT /settings
  - Description: Updates system settings.
  - Request: SettingUpdate with optional fields simulation_mode and nmap_timeout.
  - Response: {"status":"success"}

- GET /reports/generate/pdf
  - Description: Generates a PDF security audit report including RFID/NFC findings.
  - Response: File download (application/pdf).

- WebSocket /ws
  - Description: Maintains persistent connection for heartbeat messages.
  - Messages: {"event":"heartbeat","status":"active"}

**Updated**: Authentication endpoints (login, logout) are no longer available.

**Section sources**
- [access_control.py:47-94](file://backend/routers/access_control.py#L47-L94)
- [models.py:55-66](file://backend/models.py#L55-L66)
- [main.py:78-92](file://backend/main.py#L78-L92)
- [reports.py:37-157](file://backend/routers/reports.py#L37-L157)
- [main.py:114-125](file://backend/main.py#L114-L125)

### Request/Response Schemas

- RFIDCardOut
  - Fields: id, uid, card_type, sak, data, risk_level, risk_score, last_seen
  - Used by GET /rfid/cards

- SettingUpdate
  - Fields: simulation_mode (optional), nmap_timeout (optional)
  - Used by PUT /settings

**Section sources**
- [models.py:55-66](file://backend/models.py#L55-L66)
- [models.py:68-71](file://backend/models.py#L68-L71)

### Access Control Analysis Workflows

- RFID Card Emulation Detection
  - Use risk flags such as RFID_EASILY_CLONABLE to identify cards relying solely on UID without encryption.
  - Combine with card type classification to prioritize remediation.

- Access Pattern Analysis
  - Track last_seen timestamps to identify frequent access patterns.
  - Integrate with broader device analytics for correlation.

- Security Recommendation Generation
  - Leverage security engine's vulnerability mapping to suggest remediation steps.
  - Use AI engine recommendations for protocol-specific improvements.

- Integration with Physical Security Systems
  - Export RFID/NFC findings via PDF reports for compliance and audits.
  - Use dashboard UI to monitor and act on high-risk cards.

**Section sources**
- [security_engine.py:156-163](file://backend/security_engine.py#L156-L163)
- [reports.py:138-154](file://backend/routers/reports.py#L138-L154)
- [index.html:318-344](file://backend/static/index.html#L318-L344)

### Production Deployment Configuration

**New Section**: Environment variables for production deployment.

- PENTEX_CORS_ORIGINS: Comma-separated list of allowed origins (e.g., "https://yourdomain.com,http://192.168.1.100:8000")
- PENTEX_RELOAD: Enable/disable hot reload (default: false)
- PENTEX_WORKERS: Number of worker processes (default: 1 for Raspberry Pi 5)
- Database: SQLite by default, can be configured for production databases

**Section sources**
- [main.py:48-66](file://backend/main.py#L48-L66)
- [main.py:127-144](file://backend/main.py#L127-L144)