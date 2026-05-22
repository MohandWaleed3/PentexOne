#!/usr/bin/env python3
"""
Corporate NAS Simulation (Synology-style) — Corporate Network

Vulnerabilities:
  - Default admin credentials (admin/admin123)
  - SMBv1 enabled (legacy, vulnerable to EternalBlue-style attacks)
  - Anonymous FTP enabled
  - /etc/shadow backup file accessible
  - DSM admin panel exposed without HTTPS
  - Verbose API responses (information disclosure)
"""
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
import json
import socket
import threading
import base64

NAS = {
    "hostname": "CORP-NAS-01",
    "model": "DS920+",
    "vendor": "Synology",
    "dsm_version": "DSM 6.2.4-25556",  # Outdated
    "firmware_date": "2020-08-15",
    "serial": "1810LWN123456",
    "mac": "00:11:32:AA:BB:CC",
    "total_capacity_tb": 16,
    "used_capacity_tb": 8.3,
    "shares": ["public", "backup", "finance", "hr_data", "engineering"],
    "smb_version": "v1+v2+v3",   # VULNERABILITY: SMBv1 enabled
    "ftp_anonymous": True,        # VULNERABILITY
    "https_enabled": False,       # VULNERABILITY
}

VALID_CREDS = {"admin": "admin123", "guest": "guest"}

# ============================================================================
# DSM Web Interface (port 80)
# ============================================================================
DSM_LOGIN = """<!DOCTYPE html>
<html><head><title>Synology DSM</title>
<style>
body { font-family: Arial; background: #2c3e50; color: #fff; margin: 0; padding: 0; }
.container { max-width: 400px; margin: 80px auto; background: #fff; color: #000; padding: 30px; border-radius: 4px; }
h2 { color: #2c3e50; }
input { width: 100%; padding: 10px; margin: 8px 0; box-sizing: border-box; }
button { background: #16a085; color: #fff; padding: 12px; width: 100%; border: 0; cursor: pointer; }
.logo { text-align: center; color: #16a085; font-size: 28px; font-weight: bold; margin-bottom: 20px; }
.warn { background: #fff8e1; border-left: 3px solid #f39c12; padding: 10px; font-size: 11px; margin-top: 15px; }
</style></head>
<body>
<div class="container">
<div class="logo">Synology</div>
<h2>DSM Login</h2>
<form method="POST" action="/login">
<input type="text" name="username" placeholder="Username" required>
<input type="password" name="password" placeholder="Password" required>
<button type="submit">Sign In</button>
</form>
<div class="warn">
<strong>[LAB]</strong> Corporate NAS — DSM {dsm_version}<br>
Default admin: admin/admin123
</div>
</div></body></html>
""".replace("{dsm_version}", NAS["dsm_version"])

DSM_ADMIN = """<!DOCTYPE html>
<html><head><title>Synology DSM - Control Panel</title>
<style>
body { font-family: Arial; background: #ecf0f1; padding: 20px; }
.panel { background: #fff; padding: 20px; max-width: 900px; margin: 0 auto; }
h1 { color: #2c3e50; }
.row { padding: 8px; border-bottom: 1px solid #eee; }
.danger { color: #c0392b; font-weight: bold; }
.warn { background: #fef5e7; border-left: 3px solid #f39c12; padding: 10px; }
</style></head>
<body>
<div class="panel">
<h1>Synology DSM - Control Panel</h1>
<div class="row">User: <strong>admin</strong> (full privileges)</div>
<div class="row">Hostname: {hostname}</div>
<div class="row">Model: {model}</div>
<div class="row">DSM Version: <span class="danger">{dsm_version}</span> (CRITICAL UPDATE AVAILABLE)</div>
<div class="row">Capacity: {used_capacity_tb} TB / {total_capacity_tb} TB used</div>
<div class="row">Shares: {shares}</div>
<div class="row">SMB: <span class="danger">{smb_version} (SMBv1 ENABLED — EternalBlue vulnerable)</span></div>
<div class="row">FTP Anonymous: <span class="danger">ENABLED</span></div>
<div class="row">HTTPS: <span class="danger">DISABLED (HTTP only)</span></div>
<div class="warn">
<strong>Backup Files Accessible:</strong><br>
- /shared/backup/etc-shadow.bak (passwords hash backup)<br>
- /shared/backup/dsm-config.tar.gz (system config)
</div>
<p style="font-size:11px; color:#999;">[LAB] PentexOne Virtual Lab — Corporate NAS Simulation</p>
</div></body></html>
""".replace("{hostname}", NAS["hostname"]).replace("{model}", NAS["model"]) \
   .replace("{dsm_version}", NAS["dsm_version"]) \
   .replace("{used_capacity_tb}", str(NAS["used_capacity_tb"])) \
   .replace("{total_capacity_tb}", str(NAS["total_capacity_tb"])) \
   .replace("{shares}", ", ".join(NAS["shares"])) \
   .replace("{smb_version}", NAS["smb_version"])

class DSMHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self._send(200, DSM_LOGIN)
        elif self.path == "/webman/index.cgi" or self.path == "/admin":
            # VULNERABILITY: Check via cookie (very weak)
            cookie = self.headers.get("Cookie", "")
            if "id=admin_session" in cookie:
                self._send(200, DSM_ADMIN)
            else:
                self.send_response(302)
                self.send_header("Location", "/")
                self.end_headers()
        elif self.path == "/webapi/query.cgi":
            # VULNERABILITY: API info disclosure
            self._send(200, json.dumps({
                "data": {
                    "model": NAS["model"],
                    "serial": NAS["serial"],
                    "version": NAS["dsm_version"],
                    "build_number": "25556",
                    "shares": NAS["shares"],
                    "smb_enabled": True,
                    "smb_versions": ["v1", "v2", "v3"],
                    "ftp_enabled": True,
                    "ftp_anonymous": True,
                },
                "success": True
            }, indent=2), "application/json")
        elif self.path == "/shared/backup/etc-shadow.bak":
            # VULNERABILITY: Password hash backup file exposed
            self._send(200,
                "root:$6$rounds=5000$saltysalt$abcdefghijklmnopqrstuvwxyz1234567890:18000:0:99999:7:::\n"
                "admin:$6$rounds=5000$saltysalt$ZYXWVUTSRQPONMLKJIHGFEDCBA0987654321:18000:0:99999:7:::\n"
                "backup:$6$rounds=5000$saltysalt$qwertyuiopasdfghjklzxcvbnm0987654321:18000:0:99999:7:::\n",
                "text/plain"
            )
        elif self.path == "/shared/backup/dsm-config.tar.gz":
            self._send(200, "[binary] DSM configuration archive — 4.2MB", "application/gzip")
        else:
            self._send(404, "404 Not Found - DSM/" + NAS["dsm_version"])

    def do_POST(self):
        if self.path == "/login":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode()
            params = dict(p.split("=", 1) for p in body.split("&") if "=" in p)
            u = params.get("username", "")
            p = params.get("password", "")
            if VALID_CREDS.get(u) == p:
                self.send_response(302)
                self.send_header("Set-Cookie", "id=admin_session; Path=/")
                self.send_header("Location", "/webman/index.cgi")
                self.end_headers()
            else:
                self._send(401, f"Login failed for user: {u}")
        else:
            self._send(404, "Not Found")

    def _send(self, code, body, ctype="text/html"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Server", "nginx/1.18.0")
        body_bytes = body.encode() if isinstance(body, str) else body
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def log_message(self, *args):
        pass

# ============================================================================
# Fake SMB Service (port 445)
# ============================================================================
def smb_service():
    """Listens on 445 and returns SMBv1 negotiation banner — flagging EternalBlue exposure"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", 445))
    s.listen(5)
    print("[NAS] SMB listening on 445")
    while True:
        try:
            conn, addr = s.accept()
            # SMBv1 negotiate response (vulnerable to EternalBlue scanning)
            smb_banner = bytes.fromhex(
                "00000054ff534d4272000000009853c80000000000000000000000000000fffe"
                "00000000003100020250432050494e4b53472050524f4752414d20312e3000020c"
                "4c414e4d414e312e3000024c414e4d414e322e3100024e54204c4d20302e313200"
            )
            conn.sendall(smb_banner)
            conn.close()
        except Exception:
            pass

# ============================================================================
# Fake FTP Service (port 21) — Anonymous enabled
# ============================================================================
def ftp_service():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", 21))
    s.listen(5)
    print("[NAS] FTP listening on 21 (anonymous enabled)")
    while True:
        try:
            conn, addr = s.accept()
            conn.sendall(b"220 ProFTPD 1.3.5e Server (corporate-nas) [::ffff:172.30.30.50]\r\n")
            conn.sendall(b"220-Anonymous logins permitted.\r\n")
            data = conn.recv(1024)
            if data:
                conn.sendall(b"230 Anonymous user logged in.\r\n")
                conn.sendall(b"250 Files: backup/, finance/, hr_data/, public/\r\n")
            conn.close()
        except Exception:
            pass

class ThreadedHTTP(ThreadingMixIn, HTTPServer):
    daemon_threads = True

if __name__ == "__main__":
    threading.Thread(target=smb_service, daemon=True).start()
    threading.Thread(target=ftp_service, daemon=True).start()
    # DSM HTTPS-style (real cert would be self-signed)
    threading.Thread(
        target=lambda: ThreadedHTTP(("0.0.0.0", 5000), DSMHandler).serve_forever(),
        daemon=True
    ).start()
    print("[NAS] DSM Web on :80, alt :5000, SMB :445, FTP :21")
    ThreadedHTTP(("0.0.0.0", 80), DSMHandler).serve_forever()
