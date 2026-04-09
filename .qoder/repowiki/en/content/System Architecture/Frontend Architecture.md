# Frontend Architecture

<cite>
**Referenced Files in This Document**
- [index.html](file://backend/static/index.html)
- [login.html](file://backend/static/login.html)
- [style.css](file://backend/static/style.css)
- [app.js](file://backend/static/app.js)
- [main.py](file://backend/main.py)
- [websocket_manager.py](file://backend/websocket_manager.py)
- [iot.py](file://backend/routers/iot.py)
- [access_control.py](file://backend/routers/access_control.py)
- [ai.py](file://backend/routers/ai.py)
- [models.py](file://backend/models.py)
- [security_engine.py](file://backend/security_engine.py)
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
10. [Appendices](#appendices)

## Introduction
This document describes the frontend architecture of the PentexOne dashboard system. It covers the HTML/CSS/JavaScript implementation of the main dashboard interface, login page, and real-time monitoring components. It explains client-side JavaScript behavior including WebSocket connections, real-time data updates, and Chart.js-based visualizations. It documents static file serving via FastAPI, asset management, and responsive design patterns. It also details user interface components, navigation, interactive elements, WebSocket communication protocols, heartbeat mechanisms, real-time synchronization, styling architecture with CSS organization and theme management, browser compatibility, performance optimization, and user experience considerations.

## Project Structure
The frontend assets are served statically from the backend’s static directory and mounted under the /dashboard route. The main pages are:
- Login page: /login
- Dashboard: /dashboard/index.html
- Static assets: CSS, JS, and HTML files under backend/static/

```mermaid
graph TB
Browser["Browser"]
FastAPI["FastAPI App<br/>main.py"]
StaticMount["StaticFiles('/dashboard')<br/>backend/static/"]
LoginHTML["login.html"]
DashboardHTML["index.html"]
AppJS["app.js"]
StyleCSS["style.css"]
Browser --> FastAPI
FastAPI --> StaticMount
StaticMount --> LoginHTML
StaticMount --> DashboardHTML
DashboardHTML --> AppJS
DashboardHTML --> StyleCSS
```

**Diagram sources**
- [main.py:66-82](file://backend/main.py#L66-L82)
- [index.html:1-413](file://backend/static/index.html#L1-L413)
- [login.html:1-209](file://backend/static/login.html#L1-L209)

**Section sources**
- [main.py:66-82](file://backend/main.py#L66-L82)
- [index.html:1-413](file://backend/static/index.html#L1-L413)
- [login.html:1-209](file://backend/static/login.html#L1-L209)

## Core Components
- HTML pages:
  - Login page: handles authentication and redirects to dashboard upon success.
  - Dashboard page: main UI with navigation, quick actions, charts, device tables, and AI panels.
- CSS:
  - Theme variables in :root define dark theme, glass panels, and status colors.
  - Responsive breakpoints for desktop, tablet, and mobile layouts.
- JavaScript:
  - Application controller (app.js) orchestrates UI, API calls, WebSocket, charts, and notifications.
  - Real-time updates via WebSocket with heartbeat and event-driven UI refresh.
  - Chart.js renders risk distribution and protocol distribution.
- Backend static serving:
  - FastAPI mounts static directory and serves index.html as HTML for SPA-like behavior.

Key responsibilities:
- Authentication and session management (login.html + main.py).
- Real-time monitoring and live updates (app.js + websocket_manager.py + routers).
- Data visualization (Chart.js in app.js).
- Asset delivery and routing (/dashboard, /login, /ws).

**Section sources**
- [login.html:1-209](file://backend/static/login.html#L1-L209)
- [index.html:1-413](file://backend/static/index.html#L1-L413)
- [style.css:1-936](file://backend/static/style.css#L1-L936)
- [app.js:1-1099](file://backend/static/app.js#L1-L1099)
- [main.py:66-102](file://backend/main.py#L66-L102)

## Architecture Overview
The frontend architecture follows a thin client model:
- The browser loads index.html and app.js.
- app.js initializes UI, charts, and WebSocket.
- On user actions (scan, view switch, settings), app.js calls FastAPI endpoints.
- Backend routes (routers) process requests, update state, and broadcast events via WebSocket.
- app.js receives events and updates UI in real time.

```mermaid
sequenceDiagram
participant B as "Browser"
participant A as "app.js"
participant F as "FastAPI main.py"
participant W as "WebSocket Manager"
participant R as "Routers (iot.py, access_control.py, ai.py)"
B->>A : Load index.html
A->>A : init() (fetch summary, devices, charts, WS)
A->>F : GET /reports/summary
A->>F : GET /iot/devices
A->>F : GET /settings
A->>F : GET /ai/security-score
A->>F : GET /ai/suggestions
A->>F : GET /iot/hardware/status
A->>F : GET /wireless/scan/ssids
A->>F : GET /iot/networks/discover
A->>F : WS /ws (initWebSocket)
F->>W : manager.connect()
W-->>A : heartbeat every 10s
Note over R,W : Background scans trigger broadcasts
R->>W : broadcast({event : device_found/scan_progress/scan_finished})
W-->>A : onmessage(handleWebSocketMessage)
A->>A : update UI (tables, charts, toasts)
```

**Diagram sources**
- [app.js:14-25](file://backend/static/app.js#L14-L25)
- [app.js:113-126](file://backend/static/app.js#L113-L126)
- [app.js:128-155](file://backend/static/app.js#L128-L155)
- [main.py:90-101](file://backend/main.py#L90-L101)
- [websocket_manager.py:7-47](file://backend/websocket_manager.py#L7-L47)
- [iot.py:300-413](file://backend/routers/iot.py#L300-L413)

**Section sources**
- [app.js:14-25](file://backend/static/app.js#L14-L25)
- [app.js:113-155](file://backend/static/app.js#L113-L155)
- [main.py:90-101](file://backend/main.py#L90-L101)
- [websocket_manager.py:7-47](file://backend/websocket_manager.py#L7-L47)
- [iot.py:300-413](file://backend/routers/iot.py#L300-L413)

## Detailed Component Analysis

### HTML Pages and Routing
- Login page:
  - Validates credentials via POST /auth/login.
  - Stores session flag in sessionStorage and redirects to /dashboard/.
- Dashboard page:
  - Loads CSS and app.js.
  - Contains navigation, quick actions, charts, device tables, and AI panels.
  - Performs initial auth check and redirects to login if not authenticated.

```mermaid
flowchart TD
Start(["Page Load"]) --> CheckAuth["Check sessionStorage 'pentex_auth'"]
CheckAuth --> |true| RenderDashboard["Render Dashboard"]
CheckAuth --> |false| RedirectLogin["Redirect to /login"]
RedirectLogin --> LoginRoute["GET /login -> login.html"]
RenderDashboard --> InitApp["DOMContentLoaded -> app.init()"]
```

**Diagram sources**
- [index.html:406-410](file://backend/static/index.html#L406-L410)
- [login.html:179-206](file://backend/static/login.html#L179-L206)

**Section sources**
- [index.html:1-413](file://backend/static/index.html#L1-L413)
- [login.html:1-209](file://backend/static/login.html#L1-L209)

### Client-Side JavaScript (app.js)
Responsibilities:
- Initialize UI, charts, WebSocket, and periodic data fetches.
- Handle view switching, scan controls, and device selection.
- Manage toast notifications and progress bars.
- Poll scan status and update UI accordingly.
- Integrate with AI endpoints for suggestions and security score.

WebSocket handling:
- Establishes WS connection using wss:// or ws:// depending on protocol.
- Receives heartbeat messages and ignores them.
- Handles device_found, vulnerability_found, scan_progress, scan_finished, and scan_error events.
- Automatically reconnects on close.

Charts:
- Doughnut chart for risk distribution.
- Bar chart for protocol distribution.

```mermaid
sequenceDiagram
participant App as "app.js"
participant WS as "WebSocket"
participant BE as "Backend Routers"
App->>WS : connect(ws : //host/ws or wss : //host/ws)
WS-->>App : heartbeat (ignore)
BE-->>WS : broadcast({event : device_found})
WS-->>App : onmessage
App->>App : showToast + fetchDevices + fetchSummary
BE-->>WS : broadcast({event : scan_progress})
WS-->>App : onmessage
App->>App : updateScanProgress
BE-->>WS : broadcast({event : scan_finished})
WS-->>App : onmessage
App->>App : showToast + hide progress + fetchDevices + fetchSummary + fetchAISuggestions + fetchAISecurityScore
```

**Diagram sources**
- [app.js:113-155](file://backend/static/app.js#L113-L155)
- [main.py:90-101](file://backend/main.py#L90-L101)
- [websocket_manager.py:21-45](file://backend/websocket_manager.py#L21-L45)

**Section sources**
- [app.js:1-1099](file://backend/static/app.js#L1-L1099)
- [main.py:90-101](file://backend/main.py#L90-L101)
- [websocket_manager.py:7-47](file://backend/websocket_manager.py#L7-L47)

### Real-Time Monitoring and WebSocket Communication
- Heartbeat mechanism:
  - Backend sends periodic heartbeat messages every 10 seconds to keep the connection alive.
- Event-driven UI updates:
  - device_found: adds device to UI and triggers analytics refresh.
  - vulnerability_found: shows risk toast and refreshes devices.
  - scan_progress: updates progress bar and status text.
  - scan_finished: finalizes progress, hides progress UI, and refreshes data.
  - scan_error: displays error toast and resets progress.

```mermaid
flowchart TD
Start(["WS Connected"]) --> Heartbeat["Receive heartbeat"]
Heartbeat --> Wait["Wait for events"]
Wait --> DF{"device_found?"}
DF --> |Yes| UpdateUI["Show toast + fetchDevices + fetchSummary + fetchAISecurityScore"]
DF --> |No| SP{"scan_progress?"}
SP --> |Yes| UpdateProg["updateScanProgress()"]
SP --> |No| SF{"scan_finished?"}
SF --> |Yes| Finish["Show toast + hide progress + fetchDevices + fetchSummary + fetchAISuggestions + fetchAISecurityScore"]
SF --> |No| SE{"scan_error?"}
SE --> |Yes| Err["Show error toast + reset progress"]
SE --> |No| Wait
```

**Diagram sources**
- [main.py:90-101](file://backend/main.py#L90-L101)
- [app.js:128-155](file://backend/static/app.js#L128-L155)

**Section sources**
- [main.py:90-101](file://backend/main.py#L90-L101)
- [app.js:128-155](file://backend/static/app.js#L128-L155)

### Charts and Data Visualization (Chart.js)
- Risk distribution chart:
  - Doughnut chart showing SAFE, MEDIUM, RISK counts.
  - Updated whenever summary data changes.
- Protocol distribution chart:
  - Bar chart showing counts per protocol.
  - Matter merged into Thread for display.
  - Updated whenever devices change.

```mermaid
classDiagram
class App {
+riskChart
+protocolChart
+initRiskChart()
+initProtocolChart()
+updateProtocolChart()
+fetchSummary()
}
class Chart {
+getContext()
+update()
}
App --> Chart : "creates and updates"
```

**Diagram sources**
- [app.js:40-111](file://backend/static/app.js#L40-L111)
- [app.js:296-329](file://backend/static/app.js#L296-L329)

**Section sources**
- [app.js:40-111](file://backend/static/app.js#L40-L111)
- [app.js:296-329](file://backend/static/app.js#L296-L329)

### UI Components, Navigation, and Interactions
- Navigation:
  - Sidebar with links to Dashboard, RFID, Reports, and Settings.
  - Active state managed by app.switchView().
- Dashboard:
  - Quick scan buttons for Wi-Fi, Bluetooth, Zigbee, Thread, Z-Wave, LoRaWAN.
  - Advanced options with network discovery and nearby SSIDs.
  - Progress bar for ongoing scans.
  - Stats grid for total, safe, medium, risk counts.
  - Charts for risk and protocol distribution.
  - Hardware status panel.
  - AI security score and suggestions panels.
  - Device table with details panel.
- RFID:
  - Scan, clear cards, and table of scanned cards.
- Reports:
  - Export to PDF, JSON, CSV.
- Settings:
  - Toggle simulation mode and adjust Nmap timeout.

```mermaid
graph TB
Sidebar["Sidebar Nav"] --> Dashboard["Dashboard View"]
Sidebar --> RFID["RFID View"]
Sidebar --> Reports["Reports View"]
Sidebar --> Settings["Settings View"]
Dashboard --> QuickScan["Quick Scan Controls"]
Dashboard --> Charts["Charts"]
Dashboard --> Devices["Devices Table + Details"]
Dashboard --> AI["AI Score & Suggestions"]
Dashboard --> Hardware["Hardware Status"]
RFID --> ScanCards["Scan & Clear Cards"]
RFID --> CardsTable["Cards Table"]
Reports --> Export["Export Options"]
Settings --> SimMode["Simulation Mode"]
Settings --> Timeout["Nmap Timeout"]
```

**Diagram sources**
- [index.html:18-398](file://backend/static/index.html#L18-L398)
- [app.js:215-238](file://backend/static/app.js#L215-L238)

**Section sources**
- [index.html:18-398](file://backend/static/index.html#L18-L398)
- [app.js:215-238](file://backend/static/app.js#L215-L238)

### Authentication and Authorization
- Login page posts credentials to /auth/login.
- On success, sets sessionStorage flag and redirects to /dashboard/.
- Dashboard checks sessionStorage and redirects to login if missing.

```mermaid
sequenceDiagram
participant U as "User"
participant L as "login.html"
participant F as "main.py"
participant D as "index.html"
U->>L : Enter credentials
L->>F : POST /auth/login
alt Valid
F-->>L : 200 OK
L->>D : Redirect to /dashboard/
D->>D : Auth check (sessionStorage)
else Invalid
F-->>L : 401 Unauthorized
L->>L : Show error message
end
```

**Diagram sources**
- [login.html:179-206](file://backend/static/login.html#L179-L206)
- [main.py:70-74](file://backend/main.py#L70-L74)
- [index.html:406-410](file://backend/static/index.html#L406-L410)

**Section sources**
- [login.html:179-206](file://backend/static/login.html#L179-L206)
- [main.py:70-74](file://backend/main.py#L70-L74)
- [index.html:406-410](file://backend/static/index.html#L406-L410)

### Static File Serving and Asset Management
- FastAPI mounts the static directory under /dashboard with HTML=True so index.html is served as HTML.
- Assets referenced in index.html and login.html include:
  - Chart.js CDN for charts.
  - Font Awesome CDN for icons.
  - Local style.css and app.js.

```mermaid
graph LR
FastAPI["FastAPI"] --> Mount["mount('/dashboard', StaticFiles(..., html=True))"]
Mount --> Index["index.html"]
Mount --> Login["login.html"]
Mount --> CSS["style.css"]
Mount --> JS["app.js"]
```

**Diagram sources**
- [main.py:66-68](file://backend/main.py#L66-L68)
- [index.html:12-14](file://backend/static/index.html#L12-L14)

**Section sources**
- [main.py:66-68](file://backend/main.py#L66-L68)
- [index.html:12-14](file://backend/static/index.html#L12-L14)

### Responsive Design Patterns
- CSS media queries adapt layout for:
  - Desktop: full dashboard layout with sidebar and two-column device details.
  - Tablet: stacked layout for dashboard components.
  - Mobile: compact sidebar with icons-only, stacked charts and panels, and full-width components.

```mermaid
flowchart TD
Desktop[">1400px"] --> FullLayout["Full layout"]
Tablet["<=1400px"] --> StackLayout["Stacked components"]
Mobile["<=768px"] --> CompactSidebar["Compact sidebar"]
CompactSidebar --> MobileLayout["Mobile-first layout"]
```

**Diagram sources**
- [style.css:843-919](file://backend/static/style.css#L843-L919)

**Section sources**
- [style.css:843-919](file://backend/static/style.css#L843-L919)

### Styling Architecture and Theme Management
- CSS custom properties in :root define:
  - Backgrounds, borders, and text colors.
  - Accent colors for blue, purple, orange.
  - Status colors for safe, medium, risk.
  - Glass panel backdrop blur and Inter font family.
- Component styles:
  - Glass panels with backdrop-filter and border.
  - Buttons with multiple variants (primary, outline, danger, etc.).
  - Charts with custom legends and responsive containers.
  - Toast notifications with animations.
  - Device badges and vulnerability items.

```mermaid
classDiagram
class Theme {
--bg-main
--bg-panel
--accent-blue
--accent-purple
--status-safe
--status-medium
--status-risk
}
class Components {
.glass-panel
.btn
.chart-panel
.toast-msg
.badge
}
Theme <.. Components : "uses CSS variables"
```

**Diagram sources**
- [style.css:1-19](file://backend/static/style.css#L1-L19)
- [style.css:164-171](file://backend/static/style.css#L164-L171)
- [style.css:296-357](file://backend/static/style.css#L296-L357)
- [style.css:359-429](file://backend/static/style.css#L359-L429)
- [style.css:933-936](file://backend/static/style.css#L933-L936)

**Section sources**
- [style.css:1-19](file://backend/static/style.css#L1-L19)
- [style.css:164-171](file://backend/static/style.css#L164-L171)
- [style.css:296-357](file://backend/static/style.css#L296-L357)
- [style.css:359-429](file://backend/static/style.css#L359-L429)
- [style.css:933-936](file://backend/static/style.css#L933-L936)

### WebSocket Communication Protocols and Heartbeat
- Connection:
  - Uses ws:// or wss:// based on page protocol.
  - On close, attempts to reconnect after 5 seconds.
- Heartbeat:
  - Backend sends periodic heartbeat messages to keep the connection alive.
- Events:
  - device_found: new device discovered.
  - vulnerability_found: new vulnerability detected.
  - scan_progress: progress updates.
  - scan_finished: scan completion.
  - scan_error: error conditions.

```mermaid
sequenceDiagram
participant App as "app.js"
participant WS as "WebSocket"
participant BE as "main.py"
participant WM as "websocket_manager.py"
App->>WS : new WebSocket(...)
WS-->>App : onopen
BE->>WM : manager.connect()
loop Every 10s
BE->>WS : send_json({"event" : "heartbeat","status" : "active"})
end
WS-->>App : onmessage
App->>App : handleWebSocketMessage()
WS-->>App : onclose
App->>App : setTimeout(initWebSocket, 5000)
```

**Diagram sources**
- [app.js:113-126](file://backend/static/app.js#L113-L126)
- [main.py:90-101](file://backend/main.py#L90-L101)
- [websocket_manager.py:11-19](file://backend/websocket_manager.py#L11-L19)

**Section sources**
- [app.js:113-126](file://backend/static/app.js#L113-L126)
- [main.py:90-101](file://backend/main.py#L90-L101)
- [websocket_manager.py:11-19](file://backend/websocket_manager.py#L11-L19)

### Real-Time Data Synchronization
- Background scans:
  - Wi-Fi scan via nmap, Matter via Zeroconf, Zigbee/Thread/Z-Wave/LoRaWAN via hardware or simulation.
  - Broadcast events for device_found, scan_progress, scan_finished, scan_error.
- Client updates:
  - app.js polls scan status until completion, then refreshes devices and summaries.
  - On WS events, app.js updates UI immediately.

```mermaid
sequenceDiagram
participant App as "app.js"
participant API as "routers/iot.py"
participant WM as "websocket_manager.py"
participant WS as "WebSocket"
App->>API : POST /iot/scan/wifi
API->>API : run_nmap_scan()
API->>WM : broadcast({event : "scan_progress", ...})
WM-->>WS : send_json(...)
WS-->>App : onmessage
App->>App : updateScanProgress()
API->>WM : broadcast({event : "device_found", device})
WM-->>WS : send_json(...)
WS-->>App : onmessage
App->>App : showToast + fetchDevices + fetchSummary
API->>WM : broadcast({event : "scan_finished", count})
WM-->>WS : send_json(...)
WS-->>App : onmessage
App->>App : showToast + hide progress + fetchDevices + fetchSummary + fetchAISuggestions + fetchAISecurityScore
```

**Diagram sources**
- [app.js:568-653](file://backend/static/app.js#L568-L653)
- [iot.py:291-413](file://backend/routers/iot.py#L291-L413)
- [websocket_manager.py:21-45](file://backend/websocket_manager.py#L21-L45)

**Section sources**
- [app.js:568-653](file://backend/static/app.js#L568-L653)
- [iot.py:291-413](file://backend/routers/iot.py#L291-L413)
- [websocket_manager.py:21-45](file://backend/websocket_manager.py#L21-L45)

### Browser Compatibility and User Experience
- Compatibility:
  - Uses modern APIs (fetch, WebSocket, Chart.js, CSS variables).
  - Responsive design ensures usability across screen sizes.
- UX:
  - Toast notifications for scan progress, errors, and critical alerts.
  - Animated progress bars and smooth transitions.
  - Immediate feedback on user actions (scans, settings, exports).
  - Dark theme with glass panels enhances readability and reduces eye strain.

[No sources needed since this section provides general guidance]

## Dependency Analysis
High-level dependencies:
- index.html depends on app.js and style.css.
- app.js depends on Chart.js (CDN), FastAPI endpoints, and WebSocket.
- main.py mounts static files and exposes routes and WebSocket endpoint.
- Routers depend on database sessions and security_engine for risk calculations.

```mermaid
graph TB
Index["index.html"] --> App["app.js"]
Index --> CSS["style.css"]
App --> Chart["Chart.js (CDN)"]
App --> FastAPI["main.py"]
FastAPI --> Routers["iot.py, access_control.py, ai.py"]
FastAPI --> WS["websocket_manager.py"]
Routers --> Security["security_engine.py"]
Routers --> Models["models.py"]
```

**Diagram sources**
- [index.html:1-413](file://backend/static/index.html#L1-L413)
- [app.js:1-1099](file://backend/static/app.js#L1-L1099)
- [main.py:1-106](file://backend/main.py#L1-L106)
- [iot.py:1-880](file://backend/routers/iot.py#L1-L880)
- [access_control.py:1-95](file://backend/routers/access_control.py#L1-L95)
- [ai.py:1-330](file://backend/routers/ai.py#L1-L330)
- [security_engine.py:1-425](file://backend/security_engine.py#L1-L425)
- [models.py:1-71](file://backend/models.py#L1-L71)

**Section sources**
- [index.html:1-413](file://backend/static/index.html#L1-L413)
- [app.js:1-1099](file://backend/static/app.js#L1-L1099)
- [main.py:1-106](file://backend/main.py#L1-L106)
- [iot.py:1-880](file://backend/routers/iot.py#L1-L880)
- [access_control.py:1-95](file://backend/routers/access_control.py#L1-L95)
- [ai.py:1-330](file://backend/routers/ai.py#L1-L330)
- [security_engine.py:1-425](file://backend/security_engine.py#L1-L425)
- [models.py:1-71](file://backend/models.py#L1-L71)

## Performance Considerations
- Minimize DOM updates:
  - Batch UI updates after WebSocket events.
  - Use requestAnimationFrame for smoother animations.
- Efficient chart updates:
  - Update chart datasets instead of recreating charts.
  - Debounce frequent updates (e.g., scan progress).
- Network efficiency:
  - Use polling only when necessary; rely on WebSocket events.
  - Cache frequently accessed data (e.g., settings).
- Rendering:
  - Use CSS transforms for animations.
  - Avoid layout thrashing by batching DOM reads/writes.
- Asset delivery:
  - Serve static assets via CDN or compressed bundles.
  - Lazy-load non-critical resources.

[No sources needed since this section provides general guidance]

## Troubleshooting Guide
Common issues and resolutions:
- Authentication failures:
  - Ensure credentials match configured admin/admin.
  - Check CORS middleware configuration.
- WebSocket disconnections:
  - Verify backend heartbeat loop is running.
  - Confirm browser supports WebSocket; check for mixed content warnings.
- Charts not rendering:
  - Ensure Chart.js CDN is accessible.
  - Check canvas element availability and container sizing.
- Scan progress stuck:
  - Verify router endpoints are reachable.
  - Confirm background tasks are running and broadcasting events.
- Hardware detection:
  - Confirm dongle drivers are installed and accessible.
  - Check permissions for serial devices.

**Section sources**
- [main.py:23-32](file://backend/main.py#L23-L32)
- [main.py:90-101](file://backend/main.py#L90-L101)
- [app.js:113-126](file://backend/static/app.js#L113-L126)
- [iot.py:291-413](file://backend/routers/iot.py#L291-L413)

## Conclusion
The PentexOne frontend employs a clean separation of concerns: FastAPI serves static assets and exposes REST endpoints, while app.js manages the UI, WebSocket, and real-time updates. The architecture emphasizes responsive design, real-time monitoring, and a cohesive dark theme with glass panels. Robust WebSocket heartbeats and event-driven UI updates provide a smooth user experience. With careful attention to performance and accessibility, the system delivers a powerful, real-time dashboard for IoT security auditing.

[No sources needed since this section summarizes without analyzing specific files]

## Appendices

### API Surface Used by app.js
- GET /reports/summary
- GET /iot/devices
- GET /settings
- PUT /settings
- GET /ai/security-score
- GET /ai/suggestions
- GET /iot/hardware/status
- GET /wireless/scan/ssids
- GET /iot/networks/discover
- POST /iot/scan/wifi
- POST /iot/scan/matter
- POST /iot/scan/zigbee
- POST /wireless/scan/bluetooth
- POST /iot/scan/thread
- POST /iot/scan/zwave
- POST /iot/scan/lora
- GET /iot/scan/status
- DELETE /iot/devices
- POST /wireless/test/ports/{ip}
- POST /wireless/test/credentials/{ip}
- POST /rfid/scan
- GET /rfid/cards
- DELETE /rfid/cards
- GET /reports/generate/pdf
- POST /auth/login

**Section sources**
- [app.js:240-265](file://backend/static/app.js#L240-L265)
- [app.js:267-294](file://backend/static/app.js#L267-L294)
- [app.js:331-342](file://backend/static/app.js#L331-L342)
- [app.js:454-497](file://backend/static/app.js#L454-L497)
- [app.js:568-653](file://backend/static/app.js#L568-L653)
- [app.js:727-750](file://backend/static/app.js#L727-L750)
- [app.js:753-756](file://backend/static/app.js#L753-L756)
- [app.js:758-796](file://backend/static/app.js#L758-L796)
- [app.js:908-928](file://backend/static/app.js#L908-L928)
- [app.js:931-941](file://backend/static/app.js#L931-L941)
- [app.js:992-1023](file://backend/static/app.js#L992-L1023)
- [app.js:1025-1079](file://backend/static/app.js#L1025-L1079)