#!/bin/sh
# TP-Link Router startup — runs telnetd + web admin

# Start telnetd in background (vulnerable: no rate limiting, plaintext)
telnetd -l /bin/sh -p 23 &

# Start web admin interface
python3 /web_admin.py &

# Keep container alive
tail -f /dev/null
