#!/bin/bash
# PentexOne - Quick Fix & Setup Script

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

# Install dependencies
echo "📦 Installing dependencies..."
cd "$(dirname "$0")"
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

echo "================================"
echo "✅ Setup complete!"
echo ""
echo "🚀 To start the server:"
echo "   python3 main.py"
echo ""
echo "🌐 Dashboard: http://localhost:8000/dashboard"
echo "📚 API Docs:  http://localhost:8000/docs"
echo ""
echo "🔴 REMEMBER: Change default password in .env file!"
echo "================================"
