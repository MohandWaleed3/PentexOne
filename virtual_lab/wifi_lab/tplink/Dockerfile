FROM alpine:3.18

# TP-Link router simulation with vulnerable telnet
# Vulnerabilities: default credentials root/root, telnet enabled, no rate limiting

RUN apk add --no-cache busybox-extras openrc python3 py3-pip bash shadow

# Create a root user with a weak default password
RUN echo "root:root" | chpasswd

# Set hostname
RUN echo "TPLINK-ROUTER" > /etc/hostname

# Create welcome banner (information disclosure vulnerability)
RUN cat > /etc/motd <<'EOF'

╔═══════════════════════════════════════════════════════════╗
║  TP-Link Wireless Router WR940N                           ║
║  Firmware Version: 3.16.9 Build 150311 Rel.46680n         ║
║  Hardware Version: WR940N v4 00000000                     ║
║                                                            ║
║  [LAB] PentexOne Virtual Lab Device                       ║
║  WARNING: This device contains known vulnerabilities      ║
╚═══════════════════════════════════════════════════════════╝

EOF

# Copy startup script and web server
COPY start.sh /start.sh
COPY web_admin.py /web_admin.py
RUN chmod +x /start.sh

EXPOSE 23 80

CMD ["/start.sh"]
