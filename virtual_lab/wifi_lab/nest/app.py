#!/usr/bin/env python3
"""
Google Nest Thermostat Simulation (Intentionally Vulnerable)

Vulnerabilities:
  - Outdated firmware (CVE-2020-XXXX simulated)
  - Debug interface exposed on port 8080 (no auth)
  - Verbose error messages (information disclosure)
  - Weak session tokens (predictable)
  - Backup of credentials via debug endpoint
"""
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
import json
import threading
import time
import hashlib

DEVICE = {
    "name": "Living Room Thermostat",
    "model": "Nest Learning Thermostat 3rd Gen",
    "serial": "0F00111122223333",
    "firmware": "5.9.3-15",   # VULNERABILITY: Outdated (current is 6.2+)
    "firmware_release_date": "2019-04-12",
    "mac": "18:B4:30:AA:BB:CC",
    "wifi_ssid": "Home-Network",
    "temperature_c": 21.5,
    "target_c": 22.0,
    "humidity": 45,
    "hvac_state": "heating",
    "online": True,
    "eco_mode": False,
}

# VULNERABILITY: Predictable session tokens
SESSIONS = {}

# ============================================================================
# Main interface (port 80)
# ============================================================================
MAIN_PAGE = """<!DOCTYPE html>
<html><head><title>Nest Thermostat</title>
<style>
body { font-family: 'Segoe UI'; background: #1a1a1a; color: #fff; margin: 0; padding: 0; }
.header { background: #00a8e1; padding: 20px; text-align: center; }
.container { max-width: 500px; margin: 30px auto; text-align: center; }
.temp-circle { width: 280px; height: 280px; border: 12px solid #00a8e1; border-radius: 50%; margin: 30px auto; display: flex; flex-direction: column; justify-content: center; }
.temp-current { font-size: 72px; font-weight: 200; }
.temp-target { color: #00a8e1; font-size: 18px; }
.info { background: #2a2a2a; padding: 20px; margin-top: 30px; border-radius: 8px; text-align: left; }
.row { padding: 6px 0; border-bottom: 1px solid #333; }
.warn { background: #3a1a1a; border-left: 3px solid #c00; padding: 10px; font-size: 11px; margin-top: 20px; }
</style></head>
<body>
<div class="header"><h1>Google Nest</h1></div>
<div class="container">
<div class="temp-circle">
<div class="temp-current">{temperature_c}°</div>
<div class="temp-target">Target {target_c}° • {hvac_state}</div>
</div>
<div class="info">
<div class="row">Device: {model}</div>
<div class="row">Serial: {serial}</div>
<div class="row">Firmware: <span style="color:#f80">{firmware}</span> (OUTDATED)</div>
<div class="row">MAC: {mac}</div>
<div class="row">Wi-Fi: {wifi_ssid}</div>
<div class="row">Humidity: {humidity}%</div>
<div class="warn">
<strong>[LAB DEVICE]</strong> Vulnerabilities:<br>
- Debug interface on :8080 (no auth)<br>
- Outdated firmware (release 2019)<br>
- /debug/dump endpoint exposes credentials
</div>
</div></div></body></html>
"""

class NestMainHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            page = MAIN_PAGE.format(**DEVICE)
            self._send(200, page)
        elif self.path == "/api/status":
            self._send(200, json.dumps(DEVICE), "application/json")
        else:
            # VULNERABILITY: Verbose 404 reveals stack trace
            err = f"<h1>404</h1><pre>NotFound at {self.path}\nFile: /var/www/nest/handler.py:127\nThread: main\nDevice: {DEVICE['serial']}</pre>"
            self._send(404, err)

    def _send(self, code, body, ctype="text/html"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Server", "Apache/2.4.29 (Debian)")
        self.send_header("X-Firmware-Date", DEVICE["firmware_release_date"])
        body_bytes = body.encode() if isinstance(body, str) else body
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def log_message(self, *args):
        pass

# ============================================================================
# Debug interface (port 8080) — VULNERABILITY: Should not be exposed
# ============================================================================
DEBUG_PAGE = """<!DOCTYPE html>
<html><head><title>Nest Debug Interface</title>
<style>
body { font-family: monospace; background: #000; color: #0f0; padding: 20px; }
h1 { color: #f00; }
pre { background: #111; padding: 15px; border: 1px solid #0f0; }
a { color: #0ff; }
</style></head>
<body>
<h1>⚠️  NEST INTERNAL DEBUG INTERFACE — DO NOT EXPOSE TO INTERNET</h1>
<p>Firmware build: 5.9.3-15 (debug=true)</p>
<h2>Debug Endpoints:</h2>
<ul>
<li><a href="/debug/dump">/debug/dump</a> — Full memory dump (credentials included)</li>
<li><a href="/debug/logs">/debug/logs</a> — Recent activity logs</li>
<li><a href="/debug/config">/debug/config</a> — System configuration</li>
<li><a href="/debug/exec?cmd=ls">/debug/exec?cmd=&lt;command&gt;</a> — Execute system command</li>
</ul>
<pre>
[LAB] This debug interface contains intentional vulnerabilities
for PentexOne security training purposes.
</pre>
</body></html>
"""

class NestDebugHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self._send(200, DEBUG_PAGE)

        elif self.path == "/debug/dump":
            # VULNERABILITY: Exposes credentials and internal state
            dump = {
                "device": DEVICE,
                "wifi_password": "homewifi2019",   # 🔓 plaintext
                "google_oauth_token": "ya29.A0AfH6SMBxF7gXKf...",  # 🔓 sensitive
                "api_key": "AIzaSyA1B2C3D4E5F6G7H8I9J0K",
                "session_secret": "nest_secret_2019_static",
                "admin_pin": "1234",                # 🔓 weak PIN
                "debug_mode": True,
                "uptime_seconds": 87234,
            }
            self._send(200, json.dumps(dump, indent=2), "application/json")

        elif self.path == "/debug/logs":
            logs = [
                "[2026-05-19 14:23:11] INFO  Wi-Fi connected to Home-Network",
                "[2026-05-19 14:23:15] DEBUG OAuth token refreshed: ya29.A0AfH6SMB...",
                "[2026-05-19 14:25:00] INFO  Temperature set to 22.0°C by user (PIN: 1234)",
                "[2026-05-19 14:30:42] WARN  Session token reused: sess_18b430aabbcc",
                "[2026-05-19 14:45:00] DEBUG Heartbeat to nest-backend.googleapis.com:443",
            ]
            self._send(200, "\n".join(logs), "text/plain")

        elif self.path == "/debug/config":
            # VULNERABILITY: Configuration leak
            self._send(200, json.dumps({
                "wifi_ssid": DEVICE["wifi_ssid"],
                "wifi_psk": "homewifi2019",
                "ntp_server": "time.nist.gov",
                "backend": "nest-backend.googleapis.com",
                "debug_mode": True,
                "telnet_enabled": False,
                "ssh_enabled": True,
                "ssh_user": "nest-debug",
                "ssh_pubkey": "ssh-rsa AAAAB3NzaC1yc2E... nest-factory",
            }, indent=2), "application/json")

        elif self.path.startswith("/debug/exec"):
            # VULNERABILITY: Simulated command execution
            cmd = self.path.split("cmd=", 1)[-1] if "cmd=" in self.path else ""
            fake_output = {
                "ls": "config.json\nfirmware.bin\ncerts/\nlogs/\nuser_data.db",
                "whoami": "nest-debug",
                "uname -a": "Linux nest-thermostat 4.4.27 #1 SMP armv7l GNU/Linux",
                "cat /etc/passwd": "root:x:0:0::/root:/bin/sh\nnest-debug:x:1000:1000::/home/nest:/bin/sh",
            }.get(cmd, f"[simulated] command '{cmd}' executed")
            self._send(200, fake_output, "text/plain")

        else:
            self._send(404, "Debug endpoint not found")

    def _send(self, code, body, ctype="text/html"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Server", "Nest-Debug/5.9.3-15")
        body_bytes = body.encode() if isinstance(body, str) else body
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def log_message(self, *args):
        pass

class ThreadedHTTP(ThreadingMixIn, HTTPServer):
    daemon_threads = True

def run_debug():
    print("[Nest] Debug interface listening on :8080")
    ThreadedHTTP(("0.0.0.0", 8080), NestDebugHandler).serve_forever()

if __name__ == "__main__":
    threading.Thread(target=run_debug, daemon=True).start()
    print("[Nest] Main interface listening on :80")
    ThreadedHTTP(("0.0.0.0", 80), NestMainHandler).serve_forever()
