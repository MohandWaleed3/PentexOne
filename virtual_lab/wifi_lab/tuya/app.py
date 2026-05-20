#!/usr/bin/env python3
"""
Tuya Smart Plug Simulation (Intentionally Vulnerable)

Vulnerabilities:
  - UPnP service exposed without authentication
  - Local API on port 6668 without auth
  - Device info disclosure
  - Remote control without authorization
  - Hardcoded device ID
"""
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
import json
import socket
import threading
import time

DEVICE_ID = "bf3f7e6c8d9a2b1c4e5f"
LOCAL_KEY = "1234567890abcdef"  # VULNERABILITY: Hardcoded key

DEVICE_STATE = {
    "device_id": DEVICE_ID,
    "name": "Living Room Plug",
    "model": "WP1-EU",
    "firmware": "1.0.7",
    "online": True,
    "switch": False,
    "power_w": 0.0,
    "voltage_v": 230.0,
    "current_a": 0.0,
    "energy_kwh": 12.45,
    "local_key": LOCAL_KEY,  # VULNERABILITY: Exposed in JSON
    "wifi_ssid": "Home-Network",
    "wifi_signal": -42,
    "mac": "BC:DD:C2:11:22:33",
}

# ============================================================================
# HTTP Web Interface (Port 80)
# ============================================================================
WEB_PAGE = """<!DOCTYPE html>
<html><head><title>Tuya Smart Plug</title>
<style>
body { font-family: 'Segoe UI', Arial; background: #fff; color: #333; padding: 0; margin: 0; }
.header { background: linear-gradient(135deg, #ff6600, #ff9933); color: #fff; padding: 30px; text-align: center; }
.container { max-width: 600px; margin: 20px auto; padding: 20px; background: #f8f8f8; border-radius: 8px; }
.status { font-size: 60px; color: #ff6600; }
.btn { background: #ff6600; color: #fff; padding: 15px 30px; border: 0; border-radius: 30px; cursor: pointer; margin: 10px; }
.row { padding: 8px; border-bottom: 1px solid #eee; }
.warn { background: #fff3cd; border-left: 3px solid #ff6600; padding: 10px; font-size: 11px; margin-top: 20px; }
</style></head>
<body>
<div class="header">
<h1>Tuya Smart Plug</h1>
<p>Living Room • WP1-EU</p>
</div>
<div class="container">
<div style="text-align:center;">
<div class="status">⚡</div>
<h2 id="state">{state}</h2>
<button class="btn" onclick="fetch('/api/toggle').then(()=>location.reload())">Toggle Power</button>
</div>
<h3>Device Info</h3>
<div class="row">Device ID: {device_id}</div>
<div class="row">Firmware: {firmware}</div>
<div class="row">Power: {power_w} W</div>
<div class="row">Energy: {energy_kwh} kWh</div>
<div class="row">Wi-Fi: {wifi_ssid} ({wifi_signal} dBm)</div>
<div class="row">MAC: {mac}</div>
<div class="warn">
<strong>[LAB DEVICE]</strong> This Tuya plug exposes:<br>
- Unauthenticated local API at port 6668<br>
- UPnP service advertising the device<br>
- Local key exposed via /api/info endpoint
</div>
</div></body></html>
"""

class TuyaHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            page = WEB_PAGE.format(
                state="ON" if DEVICE_STATE["switch"] else "OFF",
                device_id=DEVICE_STATE["device_id"],
                firmware=DEVICE_STATE["firmware"],
                power_w=DEVICE_STATE["power_w"],
                energy_kwh=DEVICE_STATE["energy_kwh"],
                wifi_ssid=DEVICE_STATE["wifi_ssid"],
                wifi_signal=DEVICE_STATE["wifi_signal"],
                mac=DEVICE_STATE["mac"],
            )
            self._send(200, page)

        elif self.path == "/api/info":
            # VULNERABILITY: Unauthenticated endpoint exposes local key
            self._send(200, json.dumps(DEVICE_STATE, indent=2), "application/json")

        elif self.path == "/api/toggle":
            # VULNERABILITY: No authentication on control endpoint
            DEVICE_STATE["switch"] = not DEVICE_STATE["switch"]
            DEVICE_STATE["power_w"] = 75.3 if DEVICE_STATE["switch"] else 0.0
            DEVICE_STATE["current_a"] = round(DEVICE_STATE["power_w"] / 230.0, 2)
            self._send(200, json.dumps({"ok": True, "switch": DEVICE_STATE["switch"]}), "application/json")

        elif self.path == "/upnp/desc.xml":
            # VULNERABILITY: UPnP description exposed
            upnp = f"""<?xml version="1.0"?>
<root xmlns="urn:schemas-upnp-org:device-1-0">
<device>
<deviceType>urn:tuya-com:device:smartplug:1</deviceType>
<friendlyName>Tuya Smart Plug</friendlyName>
<manufacturer>Tuya Inc.</manufacturer>
<modelName>WP1-EU</modelName>
<UDN>uuid:{DEVICE_ID}</UDN>
<serialNumber>{DEVICE_STATE['mac']}</serialNumber>
</device>
</root>"""
            self._send(200, upnp, "application/xml")

        else:
            self._send(404, "Not Found")

    def _send(self, code, body, ctype="text/html"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Server", "TuyaSmartPlug/1.0.7")
        body_bytes = body.encode() if isinstance(body, str) else body
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def log_message(self, *args):
        pass

class ThreadedHTTP(ThreadingMixIn, HTTPServer):
    daemon_threads = True

# ============================================================================
# Tuya Local API Server (Port 6668) - Raw TCP
# ============================================================================
def tuya_local_api():
    """VULNERABILITY: Raw TCP listening with no authentication"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", 6668))
    s.listen(5)
    print("[Tuya] Local API listening on 6668")
    while True:
        try:
            conn, addr = s.accept()
            threading.Thread(target=handle_client, args=(conn,), daemon=True).start()
        except Exception:
            pass

def handle_client(conn):
    try:
        # VULNERABILITY: Sends device state to anyone who connects
        banner = f"TUYA-DEV/{DEVICE_STATE['firmware']}\n"
        banner += json.dumps(DEVICE_STATE) + "\n"
        conn.sendall(banner.encode())
        data = conn.recv(1024)
        if data:
            conn.sendall(b'{"ok":true,"echo":' + data + b'}\n')
    except Exception:
        pass
    finally:
        conn.close()

if __name__ == "__main__":
    threading.Thread(target=tuya_local_api, daemon=True).start()
    print("[Tuya] HTTP listening on :80")
    ThreadedHTTP(("0.0.0.0", 80), TuyaHandler).serve_forever()
