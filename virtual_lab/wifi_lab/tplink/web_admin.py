#!/usr/bin/env python3
"""
TP-Link Router Web Admin (intentionally vulnerable)
Vulnerabilities:
  - Default credentials (admin/admin)
  - Information disclosure
  - CSRF (no token)
  - Verbose error messages
"""
from http.server import BaseHTTPRequestHandler, HTTPServer
import base64

HOST = "0.0.0.0"
PORT = 80

VALID_CREDS = {"admin": "admin", "root": "root"}

LOGIN_PAGE = """<!DOCTYPE html>
<html><head><title>TP-Link Router WR940N</title>
<style>
body { font-family: Arial; background: #003366; color: #fff; padding: 0; margin: 0; }
.header { background: #00264d; padding: 20px; text-align: center; border-bottom: 3px solid #00ccff; }
.container { max-width: 500px; margin: 50px auto; background: #fff; color: #000; padding: 30px; border-radius: 4px; }
h2 { color: #003366; }
input { width: 100%; padding: 10px; margin: 10px 0; box-sizing: border-box; }
button { background: #00ccff; color: #fff; padding: 12px; width: 100%; border: 0; cursor: pointer; }
.info { background: #ffe; border-left: 3px solid #c00; padding: 10px; font-size: 11px; margin-top: 20px; }
</style></head>
<body>
<div class="header"><h1>TP-Link WR940N Wireless Router</h1></div>
<div class="container">
<h2>Login Required</h2>
<form method="POST" action="/login">
<input type="text" name="username" placeholder="Username" required>
<input type="password" name="password" placeholder="Password" required>
<button type="submit">Login</button>
</form>
<div class="info">
<strong>Firmware:</strong> 3.16.9 Build 150311 Rel.46680n<br>
<strong>Hardware:</strong> WR940N v4<br>
<strong>MAC:</strong> 00:AA:BB:CC:DD:EE<br>
<strong>[LAB]</strong> Default credentials are documented
</div>
</div></body></html>
"""

ADMIN_PAGE = """<!DOCTYPE html>
<html><head><title>TP-Link Admin Panel</title>
<style>
body { font-family: Arial; background: #f0f0f0; padding: 20px; }
.panel { background: #fff; padding: 20px; max-width: 800px; margin: 0 auto; }
h1 { color: #003366; }
.row { padding: 10px; border-bottom: 1px solid #eee; }
.danger { color: #c00; font-weight: bold; }
</style></head>
<body>
<div class="panel">
<h1>TP-Link Router - Admin Panel</h1>
<div class="row">Authenticated: <strong>admin</strong></div>
<div class="row">WAN IP: 203.0.113.45</div>
<div class="row">LAN IP: 192.168.0.1</div>
<div class="row">DHCP Range: 192.168.0.100 - 192.168.0.200</div>
<div class="row">Connected Clients: 12</div>
<div class="row">Wi-Fi SSID: TP-Link_C0FFEE</div>
<div class="row">Security: <span class="danger">WPS Enabled (vulnerable to brute force)</span></div>
<div class="row">Telnet: <span class="danger">ENABLED on port 23 (root/root)</span></div>
<div class="row">UPnP: <span class="danger">ENABLED</span></div>
<div class="row">Remote Management: <span class="danger">ENABLED on port 80</span></div>
<p style="font-size:11px; color:#888;">[LAB] PentexOne Virtual Lab — TP-Link Router Simulation</p>
</div></body></html>
"""

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # VULNERABILITY: Server header information disclosure
        self.protocol_version = "HTTP/1.1"
        if self.path == "/":
            self._send(200, LOGIN_PAGE)
        elif self.path == "/admin":
            # VULNERABILITY: No proper session check — just basic auth header
            auth = self.headers.get("Authorization", "")
            if auth.startswith("Basic "):
                try:
                    decoded = base64.b64decode(auth[6:]).decode()
                    u, p = decoded.split(":", 1)
                    if VALID_CREDS.get(u) == p:
                        self._send(200, ADMIN_PAGE)
                        return
                except Exception:
                    pass
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="TP-Link Admin"')
            self.end_headers()
        elif self.path == "/info":
            # VULNERABILITY: Unauthenticated info endpoint
            info = '{"device":"WR940N","firmware":"3.16.9","mac":"00:AA:BB:CC:DD:EE","telnet":true,"admin_path":"/admin"}'
            self._send(200, info, "application/json")
        else:
            # VULNERABILITY: Verbose 404 reveals server info
            self._send(404, f"Not Found: {self.path}\nServer: TP-Link httpd/1.0")

    def do_POST(self):
        if self.path == "/login":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode()
            params = dict(p.split("=", 1) for p in body.split("&") if "=" in p)
            u = params.get("username", "")
            p = params.get("password", "")
            if VALID_CREDS.get(u) == p:
                self.send_response(302)
                # VULNERABILITY: Weak session — just base64
                token = base64.b64encode(f"{u}:{p}".encode()).decode()
                self.send_header("Set-Cookie", f"session={token}")
                self.send_header("Location", "/admin")
                self.end_headers()
            else:
                # VULNERABILITY: Reveals which field is wrong
                self._send(401, f"Login failed for user '{u}': invalid password")
        else:
            self._send(404, "Not Found")

    def _send(self, code, body, ctype="text/html"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Server", "Apache/2.4.29 (Ubuntu)")
        self.send_header("X-Firmware", "3.16.9 Build 150311")
        body_bytes = body.encode() if isinstance(body, str) else body
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def log_message(self, *args):
        pass

if __name__ == "__main__":
    print(f"[TP-Link] Web admin listening on {HOST}:{PORT}")
    HTTPServer((HOST, PORT), Handler).serve_forever()
