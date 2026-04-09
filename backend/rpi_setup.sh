#!/bin/bash
# PentexOne - Raspberry Pi Setup Script
# This script installs and configures PentexOne for Raspberry Pi

set -e

echo "=========================================="
echo "  PentexOne - Raspberry Pi Installer"
echo "=========================================="
echo ""

# Check if running on Raspberry Pi (supports RPi 5)
if [ -f /proc/cpuinfo ]; then
    if grep -q "Raspberry Pi" /proc/cpuinfo || grep -q "BCM2712" /proc/cpuinfo || grep -q "BCM2711" /proc/cpuinfo; then
        echo "🍓 Raspberry Pi detected!"
    else
        echo "⚠️  Warning: This doesn't appear to be a Raspberry Pi"
        echo "   The script will continue, but some hardware features may not work."
        echo ""
        read -p "Continue anyway? (y/n) " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
fi

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Please run as root (use sudo)"
    exit 1
fi

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}📦 Step 1: Updating system...${NC}"
apt-get update
apt-get upgrade -y
echo ""

echo -e "${GREEN}📦 Step 2: Installing system dependencies...${NC}"
apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    nmap \
    bluez \
    bluez-tools \
    bluetooth \
    libbluetooth-dev \
    libglib2.0-dev \
    libusb-1.0-0-dev \
    libpcap-dev \
    libssl-dev \
    libffi-dev \
    build-essential \
    git \
    curl \
    wget \
    usbutils \
    screen \
    arp-scan \
    netdiscover \
    i2c-tools \
    wireless-tools \
    rfkill \
    iw
# Note: Removed 'systemctl' - it's not a package, it's a systemd utility
# Added: i2c-tools, wireless-tools, rfkill, iw for RPi 5 hardware support
echo ""

echo -e "${GREEN}📦 Step 3: Installing Python dependencies...${NC}"
cd "$(dirname "$0")"

# Create virtual environment
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi

# Activate and install requirements
source venv/bin/activate
pip3 install --upgrade pip
pip3 install -r requirements.txt
echo ""

echo -e "${GREEN}📦 Step 4: Configuring Bluetooth...${NC}"
systemctl enable bluetooth 2>/dev/null || true
systemctl start bluetooth 2>/dev/null || true
# RPi 5: Also unblock Bluetooth via rfkill
rfkill unblock bluetooth 2>/dev/null || true
rfkill unblock all 2>/dev/null || true
echo "✅ Bluetooth service enabled and unblocked"
echo ""

echo -e "${GREEN}📦 Step 5: Setting up environment...${NC}"
if [ ! -f .env ]; then
    echo "PENTEX_USERNAME=admin" > .env
    echo "PENTEX_PASSWORD=pentex2024" >> .env
    echo -e "${YELLOW}⚠️  Created .env file with default credentials${NC}"
    echo -e "${RED}🔴 IMPORTANT: Change the password in .env file!${NC}"
else
    echo "✅ .env file already exists"
fi
echo ""

echo -e "${GREEN}📦 Step 6: Setting up auto-start service...${NC}"
if [ -f pentexone.service ]; then
    cp pentexone.service /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable pentexone.service
    echo "✅ PentexOne service installed and enabled"
else
    echo "⚠️  pentexone.service not found, skipping service setup"
fi
echo ""

echo -e "${GREEN}📦 Step 7: Setting permissions and optimizing for RPi 5...${NC}"
chmod +x setup.sh 2>/dev/null || true
chmod +x start.sh
chown -R $SUDO_USER:$SUDO_USER "$(pwd)"

# RPi 5 optimization: Set CPU governor to performance during scans
echo "# PentexOne RPi 5 Optimizations" > /tmp/pentex_rpi_opt.sh
echo "echo performance | tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor 2>/dev/null" >> /tmp/pentex_rpi_opt.sh
echo "echo 'RPi 5 CPU governor set to performance'" >> /tmp/pentex_rpi_opt.sh
chmod +x /tmp/pentex_rpi_opt.sh
echo "✅ Permissions set and RPi 5 optimizations configured"
echo ""

echo "=========================================="
echo -e "${GREEN}✅ Installation Complete!${NC}"
echo "=========================================="
echo ""
echo "📋 Next Steps:"
echo "   1. Edit .env file to change default password:"
echo "      nano .env"
echo ""
echo "   2. Start the service:"
echo "      sudo systemctl start pentexone"
echo ""
echo "   3. Check status:"
echo "      sudo systemctl status pentexone"
echo ""
echo "   4. View logs:"
echo "      sudo journalctl -u pentexone -f"
echo ""
echo "   5. Access dashboard:"
echo "      http://<raspberry-pi-ip>:8000"
echo ""
echo "📚 Documentation:"
echo "   - Hardware Guide: HARDWARE_GUIDE.md"
echo "   - Raspberry Pi Guide: RASPBERRY_PI_GUIDE.md"
echo ""
echo -e "${YELLOW}🔴 REMEMBER TO CHANGE DEFAULT PASSWORD!${NC}"
echo "=========================================="
