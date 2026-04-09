#!/bin/bash
# Fix Wi-Fi scanning issue - Install required tools and fix permissions

echo "🔧 Fixing PentexOne Wi-Fi scanning..."
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Please run as root:"
    echo "   sudo ./fix_wifi_scan.sh"
    exit 1
fi

# Install arp-scan
echo "📦 Installing arp-scan..."
apt-get update
apt-get install -y arp-scan netdiscover

# Set proper permissions
echo "🔐 Setting permissions..."
setcap cap_net_raw,cap_net_admin=eip $(which arp-scan)
setcap cap_net_raw,cap_net_admin=eip $(which nmap)

# Enable promiscuous mode on network interfaces
echo "📡 Enabling network interfaces..."
for iface in $(ls /sys/class/net/ | grep -E 'eth|wlan'); do
    echo "   Interface: $iface"
    ip link set $iface promisc on 2>/dev/null || echo "   ⚠️  Could not enable promiscuous mode"
done

# Test arp-scan
echo ""
echo "🧪 Testing arp-scan..."
if arp-scan --localnet --quiet 2>/dev/null | head -5; then
    echo "✅ arp-scan working!"
else
    echo "⚠️  arp-scan may need additional configuration"
fi

echo ""
echo "=========================================="
echo "✅ Fix applied successfully!"
echo ""
echo "🔄 Restart PentexOne:"
echo "   sudo systemctl restart pentexone"
echo ""
echo "📊 Or if running manually:"
echo "   ./start.sh"
echo ""
echo "🌐 Then test the scan again!"
echo "=========================================="
