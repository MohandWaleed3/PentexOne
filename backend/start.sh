#!/bin/bash
# Quick start script for PentexOne
# Use this for manual testing or development

cd "$(dirname "$0")"

echo "🚀 Starting PentexOne..."
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "   Please run setup.sh first"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found, creating with defaults..."
    echo "PENTEX_USERNAME=admin" > .env
    echo "PENTEX_PASSWORD=pentex2024" >> .env
    echo "🔴 Remember to change the password!"
    echo ""
fi

# Start the server
echo "📡 Server starting on http://0.0.0.0:8000"
echo "📊 Dashboard: http://localhost:8000/dashboard"
echo "📚 API Docs:  http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop"
echo ""

python3 main.py
