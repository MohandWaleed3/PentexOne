#!/bin/bash
# ==============================================================================
# PentexOne Virtual Lab — Start Script (Multi-Subnet)
# ==============================================================================
# Starts the Wi-Fi Lab with 3 isolated subnets (IoT / Guest / Corporate)
# Designed for Linux/Ubuntu (run inside the lab VM)
# ==============================================================================

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
MAGENTA='\033[0;35m'
NC='\033[0m'

echo -e "${CYAN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║         PentexOne Virtual Lab — Starting Up                ║${NC}"
echo -e "${CYAN}║         Multi-Subnet Network Simulation                    ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# --- Check Docker ---
if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker is not installed${NC}"
    exit 1
fi

if ! docker info &> /dev/null; then
    echo -e "${RED}✗ Docker daemon is not running${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Docker is ready${NC}"

# --- Start Wi-Fi Lab ---
echo ""
echo -e "${YELLOW}▶ Starting 3-subnet network (7 vulnerable devices)...${NC}"
cd wifi_lab
docker compose up -d --build

echo ""
echo -e "${GREEN}✓ All subnets are running${NC}"

# --- Display network architecture ---
echo ""
echo -e "${CYAN}┌────────────────────────────────────────────────────────────────┐${NC}"
echo -e "${CYAN}│  NETWORK ARCHITECTURE                                          │${NC}"
echo -e "${CYAN}├────────────────────────────────────────────────────────────────┤${NC}"
echo ""

echo -e "${MAGENTA}  🔵 IoT SUBNET — 172.30.10.0/24${NC}"
echo -e "  ┌──────────────────────────────────────────────────────────────┐"
echo -e "  │  📷  Hikvision Camera     172.30.10.50  → host:8050          │"
echo -e "  │  📡  Mosquitto MQTT       172.30.10.51  → host:8051,8061     │"
echo -e "  │  📶  TP-Link Router       172.30.10.52  → host:8052,8062     │"
echo -e "  │  🔌  Tuya Smart Plug      172.30.10.53  → host:8053,8063     │"
echo -e "  │  🌡️   Nest Thermostat      172.30.10.54  → host:8054,8064     │"
echo -e "  └──────────────────────────────────────────────────────────────┘"
echo ""

echo -e "${YELLOW}  🟡 GUEST SUBNET — 172.30.20.0/24${NC}"
echo -e "  ┌──────────────────────────────────────────────────────────────┐"
echo -e "  │  📺  Samsung Smart TV     172.30.20.50  → host:8070,8071,8072 │"
echo -e "  └──────────────────────────────────────────────────────────────┘"
echo ""

echo -e "${RED}  🔴 CORPORATE SUBNET — 172.30.30.0/24${NC}"
echo -e "  ┌──────────────────────────────────────────────────────────────┐"
echo -e "  │  💾  Synology NAS         172.30.30.50  → host:8080-8083      │"
echo -e "  └──────────────────────────────────────────────────────────────┘"
echo ""

HOST_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "<lab-host-ip>")

echo -e "${CYAN}┌────────────────────────────────────────────────────────────────┐${NC}"
echo -e "${CYAN}│  REACHABLE FROM PENTEXONE                                      │${NC}"
echo -e "${CYAN}└────────────────────────────────────────────────────────────────┘${NC}"
echo -e "  Lab host IP:  ${YELLOW}${HOST_IP}${NC}"
echo ""
echo -e "${CYAN}Quick tests:${NC}"
echo -e "  curl http://${HOST_IP}:8050/                  # Hikvision login page"
echo -e "  curl http://${HOST_IP}:8064/debug/dump        # 🔓 Nest credentials leak"
echo -e "  curl http://${HOST_IP}:8070/                  # Samsung TV"
echo -e "  curl http://${HOST_IP}:8072/api/v1/voice/enable  # 🔓 Activate TV mic"
echo -e "  curl http://${HOST_IP}:8080/                  # Synology NAS login"
echo -e "  curl http://${HOST_IP}:8080/shared/backup/etc-shadow.bak  # 🔓 Password hashes"
echo ""
echo -e "${GREEN}Total: 7 vulnerable devices across 3 isolated subnets${NC}"
echo -e "${GREEN}Stop the lab with: ./stop_lab.sh${NC}"
