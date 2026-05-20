#!/usr/bin/env python3
"""
Samsung Smart TV Simulation (Guest Network)

Vulnerabilities:
  - DIAL protocol exposed without authentication
  - Cast service open to anyone on the network
  - Voice command API accepts unauthenticated requests
  - Microphone state controllable via API
  - Installed apps list exposed
"""
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
import json
import threading

TV_STATE = {
    "model": "UN55MU8000",
    "name": "Samsung Smart TV",
    "firmware": "T-MST14AKUC-1330.4",
    "serial": "0AKM3CKM700123A",
    "mac": "F8:3F:51:11:22:33",
    "current_app": "Netflix",
    "volume": 25,
    "muted": False,
    "input": "HDMI-1",
    "screen_on": True,
    "microphone_active": False,
    "installed_apps": [
        "Netflix", "YouTube", "Disney+", "Spotify",
        "Web Browser", "Samsung TV Plus", "Hulu"
    ],
    "wifi_ssid": "Guest-Network",
    "ip_address": "172.30.20.50",
}

# ============================================================================
# Main interface (port 80)
# ============================================================================
MAIN_PAGE = """<!DOCTYPE html>
<html><head><title>Samsung Smart TV</title>
<style>
body { font-family: 'Segoe UI'; background: #000; color: #fff; margin: 0; padding: 0; }
.header { background: linear-gradient(135deg, #1428a0, #006eb6); padding: 30px; text-align: center; }
.container { max-width: 700px; margin: 30px auto; padding: 20px; }
.tv-screen { background: #1a1a1a; border: 4px solid #333; padding: 60px 20px; text-align: center; border-radius: 8px; }
.app { background: #1428a0; padding: 12px 20px; display: inline-block; border-radius: 4px; margin: 5px; }
.info { background: #1a1a1a; padding: 20px; margin-top: 20px; border-radius: 8px; }
.row { padding: 6px 0; border-bottom: 1px solid #222; }
.warn { background: #2a1a00; border-left: 3px solid #ff8800; padding: 10px; font-size: 11px; margin-top: 20px; }
</style></head>
<body>
<div class="header"><h1>SAMSUNG</h1><p>Smart TV — Guest Mode</p></div>
<div class="container">
<div class="tv-screen">
<h2>{current_app}</h2>
<p>Volume: {volume} • {input} • {wifi_ssid}</p>
</div>
<div class="info">
<div class="row">Model: {model}</div>
<div class="row">Firmware: {firmware}</div>
<div class="row">Serial: {serial}</div>
<div class="row">MAC: {mac}</div>
<div class="row">Network: {wifi_ssid} ({ip_address})</div>
<h3>Installed Apps</h3>
{apps_html}
<div class="warn">
<strong>[LAB DEVICE]</strong> Exposed services:<br>
- DIAL/Cast on :8001 (anyone can launch apps)<br>
- Voice API on :9197 (mic control possible)<br>
- App info endpoint at /api/v2/applications
</div>
</div></div></body></html>
"""

class SmartTVHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            apps_html = " ".join(f'<span class="app">{a}</span>' for a in TV_STATE["installed_apps"])
            page = MAIN_PAGE.format(apps_html=apps_html, **TV_STATE)
            self._send(200, page)
        elif self.path == "/api/v2/applications":
            # VULNERABILITY: Lists installed apps without auth
            self._send(200, json.dumps({"apps": TV_STATE["installed_apps"]}), "application/json")
        elif self.path == "/api/v2/state":
            self._send(200, json.dumps(TV_STATE), "application/json")
        else:
            self._send(404, "Not Found")

    def _send(self, code, body, ctype="text/html"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Server", "Samsung-Tizen/5.5")
        body_bytes = body.encode() if isinstance(body, str) else body
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def log_message(self, *args):
        pass

# ============================================================================
# DIAL Protocol (port 8001) — Cast service
# ============================================================================
class DialHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # VULNERABILITY: DIAL service description, no auth
        if self.path == "/dd.xml":
            xml = f"""<?xml version="1.0"?>
<root xmlns="urn:schemas-upnp-org:device-1-0" xmlns:dial="urn:schemas-org:device-dial-1-0">
<device>
<deviceType>urn:dial-multiscreen-org:device:dial:1</deviceType>
<friendlyName>{TV_STATE['name']}</friendlyName>
<manufacturer>Samsung Electronics</manufacturer>
<modelName>{TV_STATE['model']}</modelName>
<UDN>uuid:{TV_STATE['serial']}</UDN>
<dial:X_DIALEx_DiscoveryURL>http://172.30.20.50:8001/api/v2/applications</dial:X_DIALEx_DiscoveryURL>
</device>
</root>"""
            self._send(200, xml, "application/xml")
        elif self.path.startswith("/apps/"):
            app = self.path.split("/apps/")[-1]
            # VULNERABILITY: Anyone can launch any app
            return_xml = f"<?xml version='1.0'?><service xmlns='urn:dial-multiscreen-org:schemas:dial' dialVer='2.1'><name>{app}</name><state>running</state></service>"
            self._send(200, return_xml, "application/xml")
        else:
            self._send(404, "Not Found")

    def do_POST(self):
        # VULNERABILITY: Launching apps without authentication
        app = self.path.split("/apps/")[-1] if "/apps/" in self.path else "unknown"
        TV_STATE["current_app"] = app
        self.send_response(201)
        self.send_header("LOCATION", f"http://172.30.20.50:8001/apps/{app}/run")
        self.end_headers()

    def _send(self, code, body, ctype="text/html"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Server", "Samsung-DIAL/2.1")
        body_bytes = body.encode() if isinstance(body, str) else body
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def log_message(self, *args):
        pass

# ============================================================================
# Voice Command API (port 9197)
# ============================================================================
class VoiceHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/v1/voice/status":
            # VULNERABILITY: Microphone state exposed
            self._send(200, json.dumps({
                "microphone_active": TV_STATE["microphone_active"],
                "language": "en-US",
                "voice_assistant": "Bixby",
                "wake_word_detection": True,
            }), "application/json")
        elif self.path == "/api/v1/voice/enable":
            # VULNERABILITY: Anyone can enable the microphone remotely!
            TV_STATE["microphone_active"] = True
            self._send(200, json.dumps({"ok": True, "microphone_active": True}), "application/json")
        elif self.path == "/api/v1/voice/disable":
            TV_STATE["microphone_active"] = False
            self._send(200, json.dumps({"ok": True, "microphone_active": False}), "application/json")
        else:
            self._send(404, "Not Found")

    def _send(self, code, body, ctype="text/html"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Server", "Bixby-Voice/2.0")
        body_bytes = body.encode() if isinstance(body, str) else body
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def log_message(self, *args):
        pass

class ThreadedHTTP(ThreadingMixIn, HTTPServer):
    daemon_threads = True

if __name__ == "__main__":
    threading.Thread(
        target=lambda: ThreadedHTTP(("0.0.0.0", 8001), DialHandler).serve_forever(),
        daemon=True
    ).start()
    threading.Thread(
        target=lambda: ThreadedHTTP(("0.0.0.0", 9197), VoiceHandler).serve_forever(),
        daemon=True
    ).start()
    print("[Smart TV] Main: 80 | DIAL: 8001 | Voice API: 9197")
    ThreadedHTTP(("0.0.0.0", 80), SmartTVHandler).serve_forever()
