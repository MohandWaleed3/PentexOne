#!/bin/bash
# PentexOne - Quick Fix & Setup Script
# Works on macOS, Linux, and Raspberry Pi

echo "🔧 PentexOne Setup & Fix Script"
echo "================================"
echo ""

# Check Python version
echo "📦 Checking Python version..."
python3 --version
if [ $? -ne 0 ]; then
    echo "❌ Python3 not found. Please install Python 3.8+"
    exit 1
fi
echo "✅ Python3 found"
echo ""

# Check if Raspberry Pi
IS_RPI=false
if [ -f /proc/cpuinfo ] && grep -q "Raspberry Pi" /proc/cpuinfo; then
    IS_RPI=true
    echo "🍓 Raspberry Pi detected!"
    echo ""
fi

# Install dependencies
echo "📦 Installing dependencies..."
cd "$(dirname "$0")"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
fi

# Activate virtual environment
if [ "$IS_RPI" = true ]; then
    source venv/bin/activate
else
    source venv/bin/activate
fi

pip3 install --upgrade pip
pip3 install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "❌ Failed to install dependencies"
    exit 1
fi
echo "✅ Dependencies installed"
echo ""

# Verify all Python files
echo "🔍 Verifying Python files..."
python3 -m py_compile main.py security_engine.py ai_engine.py database.py models.py
python3 -m py_compile routers/iot.py routers/ai.py routers/wifi_bt.py routers/access_control.py routers/reports.py
if [ $? -ne 0 ]; then
    echo "❌ Compilation errors found"
    exit 1
fi
echo "✅ All Python files compiled successfully"
echo ""

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p generated_reports
mkdir -p static
echo "✅ Directories created"
echo ""

# Set environment variables
echo "🔐 Setting up environment..."
if [ ! -f .env ]; then
    echo "PENTEX_USERNAME=admin" > .env
    echo "PENTEX_PASSWORD=pentex2024" >> .env
    echo "⚠️  Created .env file with default credentials"
    echo "🔴 IMPORTANT: Change the password in .env file before deploying!"
else
    echo "✅ .env file already exists"
fi
echo ""

# Check optional dependencies
echo "🔍 Checking optional dependencies..."
python3 -c "import killerbee" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✅ KillerBee installed (Real Zigbee scanning available)"
else
    echo "⚠️  KillerBee not installed (Zigbee will use simulation mode)"
fi

python3 -c "import cryptography" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✅ Cryptography installed (TLS validation available)"
else
    echo "⚠️  Cryptography not installed (TLS validation limited)"
fi
echo ""

# Raspberry Pi specific setup
if [ "$IS_RPI" = true ]; then
    echo "🍓 Setting up Raspberry Pi specific configuration..."
    
    # Install system dependencies if running as root
    if [ "$EUID" -eq 0 ]; then
        echo "📦 Installing system packages..."
        apt-get update
        apt-get install -y nmap bluez bluez-tools libbluetooth-dev libglib2.0-dev arp-scan netdiscover
        
        # Enable Bluetooth
        systemctl enable bluetooth
        systemctl start bluetooth
        echo "✅ Bluetooth enabled"
        
        # Verify arp-scan installed
        if command -v arp-scan &> /dev/null; then
            echo "✅ arp-scan installed (better device discovery)"
        else
            echo "⚠️  arp-scan not installed, using nmap fallback"
        fi
    else
        echo "⚠️  Run with sudo to install system packages"
        echo "   sudo ./setup.sh"
    fi
    echo ""
fi

echo "================================"
echo "✅ Setup complete!"
echo ""
echo "🚀 To start the server:"
echo "   Option 1 - Quick start:"
echo "   ./start.sh"
echo ""
echo "   Option 2 - Manual start:"
echo "   source venv/bin/activate"
echo "   python3 main.py"
echo ""
echo "   Option 3 - Service (Raspberry Pi only):"
echo "   sudo ./rpi_setup.sh  # Install service"
echo "   sudo systemctl start pentexone"
echo ""
echo "🌐 Dashboard: http://localhost:8000/dashboard"
echo "📚 API Docs:  http://localhost:8000/docs"
echo ""
echo "🔴 REMEMBER: Change default password in .env file!"
echo "================================"
