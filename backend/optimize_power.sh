#!/bin/bash
# PentexOne - Power & Performance Optimization Script for Raspberry Pi 5
# This script tunes the Pi for maximum speed and power efficiency on battery.

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}==============================================${NC}"
echo -e "${GREEN}   PentexOne - RPi 5 Power Optimizer          ${NC}"
echo -e "${GREEN}==============================================${NC}"

# Check for root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}❌ Please run as root (use sudo)${NC}"
    exit 1
fi

# 1. CPU Governor Selection
echo -e "${YELLOW}⚙️  CPU Power Management:${NC}"
echo " 1) Performance (Stabilize at max factory speed - Best response)"
echo " 2) On-demand (Scales speed based on load - Best for battery/cooling)"
read -p "Choose option (1/2): " GOV_OPT

if [ "$GOV_OPT" == "1" ]; then
    echo -e "${YELLOW}🚀 Setting CPU Governor to Performance...${NC}"
    for i in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
        echo "performance" > "$i"
    done
    echo "✅ CPU set to maximum speed."
else
    echo -e "${YELLOW}🍃 Setting CPU Governor to On-demand...${NC}"
    for i in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
        echo "ondemand" > "$i" || echo "powersave" > "$i"
    done
    echo "✅ CPU will now scale speed to save energy."
fi

# 2. Disable HDMI (Headless Optimization)
echo ""
read -p "❓ Disable HDMI output to save power & heat? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}📺 Disabling HDMI output...${NC}"
    if command -v vcgencmd &> /dev/null; then
        vcgencmd display_power 0 &> /dev/null || true
    fi
    echo "✅ HDMI output disabled."
fi

# 3. Disable Onboard LEDs (Stealth Mode)
echo ""
read -p "❓ Disable onboard LEDs (Stealth/Power saving)? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}💡 Disabling Onboard LEDs...${NC}"
    # Power LED
    if [ -d "/sys/class/leds/PWR" ]; then
        echo 0 > /sys/class/leds/PWR/brightness
        echo "none" > /sys/class/leds/PWR/trigger || true
    fi
    # Activity LED
    if [ -d "/sys/class/leds/ACT" ]; then
        echo 0 > /sys/class/leds/ACT/brightness
        echo "none" > /sys/class/leds/ACT/trigger || true
    fi
    echo "✅ LEDs disabled."
fi

# 4. USB Current Limit (Optional Override)
echo ""
read -p "❓ Override USB current limit for 3A power banks? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    CONFIG_FILE="/boot/firmware/config.txt"
    if [ ! -f "$CONFIG_FILE" ]; then
        CONFIG_FILE="/boot/config.txt"
    fi
    
    if grep -q "usb_max_current_enable=1" "$CONFIG_FILE"; then
        echo "✅ USB limit already overridden."
    else
        echo "usb_max_current_enable=1" >> "$CONFIG_FILE"
        echo -e "${GREEN}✅ USB limit override added to $CONFIG_FILE${NC}"
        echo -e "${YELLOW}⚠️  A reboot is required for this change to take effect.${NC}"
    fi
fi

echo ""
echo -e "${GREEN}==============================================${NC}"
echo -e "${GREEN}✅ Optimization Complete!${NC}"
echo -e "Your Raspberry Pi 5 is now optimized for:"
echo -e " - Maximum Processing Speed"
echo -e " - Lower Power Draw (No HDMI/LEDs)"
echo -e " - Portable Battery Stability"
echo -e "${GREEN}==============================================${NC}"
