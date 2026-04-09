# PentexOne - IoT Security Auditor

<div align="center">

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-green.svg)
![License](https://img.shields.io/badge/license-MIT-yellow.svg)
![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi-Ready-red.svg)

**A comprehensive IoT security testing platform with AI-powered analysis**

[Features](#-features) • [Quick Start](#-quick-start) • [Documentation](#-documentation) • [Hardware Guide](#-hardware-requirements)

</div>

---

## 📖 Overview

PentexOne is a professional-grade IoT Security Auditor designed to discover, analyze, and assess security vulnerabilities in IoT devices across multiple wireless protocols. Built with a modern web interface and powered by AI-driven analysis, it's perfect for security professionals, IoT developers, and smart home enthusiasts.

### Key Capabilities

- 🔍 **Multi-Protocol Scanning** - Wi-Fi, Bluetooth, Zigbee, Thread/Matter, Z-Wave, LoRaWAN
- 🤖 **AI-Powered Analysis** - Intelligent vulnerability prediction and security scoring
- 📊 **Real-Time Dashboard** - Beautiful, responsive web interface with live updates
- 📄 **Professional Reports** - Export comprehensive security reports (PDF, JSON, CSV)
- 🍓 **Raspberry Pi Ready** - Optimized for deployment on Raspberry Pi
- 🔐 **RFID/NFC Security** - Scan and analyze RFID cards for vulnerabilities

---

## ✨ Features

### Protocol Support

| Protocol | Status | Hardware Required |
|----------|--------|-------------------|
| **Wi-Fi** | ✅ Built-in | Raspberry Pi Wi-Fi |
| **Bluetooth/BLE** | ✅ Built-in | Raspberry Pi Bluetooth |
| **Zigbee** | ✅ Optional | CC2652P/CC2531 USB Dongle |
| **Thread/Matter** | ✅ Optional | nRF52840 USB Dongle |
| **Z-Wave** | ✅ Optional | Aeotec Z-Stick 7 |
| **LoRaWAN** | 🔶 Experimental | Dragino USB LoRa |
| **RFID/NFC** | ✅ Optional | RC522/PN532 Reader |

### Security Analysis

- **Network Discovery** - Automatic device detection and fingerprinting
- **Port Scanning** - Deep port analysis with service detection
- **Vulnerability Assessment** - Known vulnerability matching (CVE database)
- **Default Credential Testing** - Test for common default passwords
- **TLS/SSL Validation** - Certificate analysis and validation
- **AI Security Scoring** - Machine learning-based risk assessment
- **Smart Recommendations** - Context-aware remediation suggestions

### User Interface

- 🎨 **Modern Dark Theme** - Easy on the eyes during long scanning sessions
- 📱 **Responsive Design** - Works on desktop, tablet, and mobile
- ⚡ **Real-Time Updates** - WebSocket-powered live device discovery
- 📈 **Visual Analytics** - Interactive charts and statistics
- 🔔 **Smart Notifications** - Instant alerts for critical findings

---

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- nmap (network scanner)
- Raspberry Pi 3+ (optional, for deployment)

### Installation

#### 1. Clone or Download
```bash
cd PentexOne/backend
```

#### 2. Run Setup
```bash
# Make scripts executable
chmod +x setup.sh start.sh

# Run setup (creates virtual environment and installs dependencies)
./setup.sh
```

#### 3. Configure
```bash
# Edit environment file
nano .env

# Change default credentials
PENTEX_USERNAME=admin
PENTEX_PASSWORD=your_secure_password
```

#### 4. Start
```bash
# Quick start
./start.sh

# Or manually
source venv/bin/activate
python3 main.py
```

#### 5. Access Dashboard
Open your browser and navigate to:
```
http://localhost:8000/dashboard
```

---

## 🍓 Raspberry Pi Deployment

### One-Command Install
```bash
sudo ./rpi_setup.sh
```

This will:
- ✅ Install all system dependencies
- ✅ Configure Bluetooth and Wi-Fi
- ✅ Set up Python virtual environment
- ✅ Install PentexOne as a systemd service
- ✅ Enable auto-start on boot

### Service Management
```bash
# Start/Stop/Restart
sudo systemctl start pentexone
sudo systemctl stop pentexone
sudo systemctl restart pentexone

# Check status
sudo systemctl status pentexone

# View logs
sudo journalctl -u pentexone -f

# Enable auto-start
sudo systemctl enable pentexone
```

### Access from Network
```bash
# Find your Raspberry Pi's IP
hostname -I

# Access from any device on the network
http://<raspberry-pi-ip>:8000/dashboard
```

---

## 📚 Documentation

### Guides

| Document | Description |
|----------|-------------|
| **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** | Quick commands and tips |
| **[HARDWARE_GUIDE.md](HARDWARE_GUIDE.md)** | Hardware requirements and setup |
| **[RASPBERRY_PI_GUIDE.md](RASPBERRY_PI_GUIDE.md)** | Complete RPi deployment guide |

### API Documentation

Once running, access interactive API docs:
```
http://localhost:8000/docs        # Swagger UI
http://localhost:8000/redoc       # ReDoc
```

---

## 🔧 Hardware Requirements

### Minimum (Wi-Fi & Bluetooth Only)
- Raspberry Pi 3 Model B+ or newer
- 2GB RAM
- 32GB microSD card (Class 10)
- 5V 2.5A power supply
- **Cost:** ~$55-75

### Recommended (Full Protocol Support)
- Raspberry Pi 4 (4GB)
- 64GB microSD card (Class 10/UHS-I)
- 5V 3A power supply
- Powered USB hub (4+ ports)
- **Security Dongles:**
  - Sonoff Zigbee 3.0 USB (CC2652P) - ~$20
  - Nordic nRF52840 Dongle (Thread/Matter) - ~$12
  - Aeotec Z-Stick 7 (Z-Wave) - ~$45
- **Cost:** ~$200-250

### Dongle Compatibility

| Protocol | Recommended Dongle | Price | Status |
|----------|-------------------|-------|--------|
| Zigbee | Sonoff Zigbee 3.0 USB Plus | ~$20 | ✅ Plug & Play |
| Thread | Nordic nRF52840 Dongle | ~$12 | ✅ Plug & Play |
| Z-Wave | Aeotec Z-Stick 7 | ~$45 | ✅ Plug & Play |
| LoRaWAN | Dragino USB LoRa | ~$35 | 🔶 Experimental |

See [HARDWARE_GUIDE.md](HARDWARE_GUIDE.md) for detailed setup instructions.

---

## 🎯 Usage Guide

### Basic Scanning Workflow

1. **Discover Networks**
   - Click "Discover" to auto-detect your network
   - Or manually enter network range (e.g., 192.168.1.0/24)

2. **Start Scanning**
   - Quick Scan buttons for common protocols
   - Advanced Options for additional protocols

3. **Analyze Results**
   - Click any device in the table for details
   - View vulnerabilities and risk level
   - Run AI Analysis for deep insights

4. **Take Action**
   - Test ports with Deep Port Scan
   - Check for default credentials
   - Review AI recommendations

5. **Export Reports**
   - Navigate to Reports tab
   - Export as PDF, JSON, or CSV
   - Share with your team

### Dashboard Layout

```
┌─────────────────────────────────────────────┐
│  QUICK SCAN BAR                             │
│  [Wi-Fi] [Bluetooth] [Zigbee] [Thread]     │
│  └─ Advanced Options ▼                      │
├─────────────────────────────────────────────┤
│  STATS CARDS                                │
│  [Total] [Safe] [Medium] [Risk]            │
├─────────────────────────────────────────────┤
│  CHARTS                                     │
│  [Risk Distribution] [Protocol Distribution]│
├─────────────────────────────────────────────┤
│  HARDWARE STATUS                            │
│  [Zigbee ✓] [Thread ✓] [Z-Wave ✗]          │
├─────────────────────────────────────────────┤
│  AI SECTION                                 │
│  [Security Score] [Recommendations]         │
├──────────────────┬──────────────────────────┤
│  DEVICES TABLE   │  DEVICE DETAILS          │
│  ┌────────────┐  │  ┌──────────────────┐   │
│  │ Device 1   │  │  │ Vulnerabilities  │   │
│  │ Device 2   │  │  │ AI Analysis      │   │
│  │ Device 3   │  │  │ Actions          │   │
│  └────────────┘  │  └──────────────────┘   │
└──────────────────┴──────────────────────────┘
```

---

## 🛠️ Development

### Project Structure
```
PentexOne/backend/
├── main.py                  # FastAPI application entry point
├── models.py                # Pydantic models
├── database.py              # SQLAlchemy database setup
├── security_engine.py       # Security analysis engine
├── ai_engine.py             # AI/ML analysis engine
├── websocket_manager.py     # WebSocket connection manager
├── routers/
│   ├── iot.py               # IoT scanning endpoints
│   ├── ai.py                # AI analysis endpoints
│   ├── wifi_bt.py           # Wi-Fi & Bluetooth endpoints
│   ├── access_control.py    # RFID endpoints
│   └── reports.py           # Report generation endpoints
├── static/
│   ├── index.html           # Dashboard HTML
│   ├── app.js               # Frontend JavaScript
│   ├── style.css            # Styles
│   └── login.html           # Login page
├── generated_reports/       # Exported reports
└── pentex.db                # SQLite database
```

### Adding New Protocols

1. Create scanner in `routers/iot.py`
2. Add protocol icon in `static/index.html`
3. Update protocol chart in `static/app.js`
4. Test with `test_dongles.py`

---

## 🔐 Security Considerations

### Important Notes

1. **Change Default Credentials**
   ```bash
   nano .env
   # Set strong password
   ```

2. **Enable Firewall** (Raspberry Pi)
   ```bash
   sudo ufw allow 22/tcp
   sudo ufw allow 8000/tcp
   sudo ufw enable
   ```

3. **Use HTTPS in Production**
   - Set up reverse proxy (nginx)
   - Obtain SSL certificate (Let's Encrypt)

4. **Regular Updates**
   ```bash
   git pull
   pip install -r requirements.txt --upgrade
   sudo systemctl restart pentexone
   ```

### Legal Disclaimer

**This tool is designed for authorized security testing only.**

- ✅ Use on your own networks and devices
- ✅ Use with explicit written permission
- ❌ Do not use on networks you don't own
- ❌ Do not use without proper authorization

**Unauthorized access to computer networks is illegal.**

---

## 🐛 Troubleshooting

### Common Issues

**Problem:** Can't access dashboard
```bash
# Check if service is running
sudo systemctl status pentexone

# Check logs
sudo journalctl -u pentexone -f

# Verify port is listening
sudo netstat -tlnp | grep 8000
```

**Problem:** USB dongle not detected
```bash
# List USB devices
lsusb

# Check permissions
sudo usermod -a -G dialout pi
sudo reboot
```

**Problem:** Bluetooth not working
```bash
sudo systemctl restart bluetooth
sudo rfkill unblock bluetooth
```

See [QUICK_REFERENCE.md](QUICK_REFERENCE.md) for more troubleshooting tips.

---

## 📊 Performance

### Resource Usage (Raspberry Pi 4)

| State | CPU | Memory | Disk |
|-------|-----|--------|------|
| Idle | 2-5% | ~150MB | ~200MB |
| Scanning | 30-60% | ~250MB | ~250MB |
| With AI | 40-70% | ~300MB | ~300MB |

### Optimization Tips

- Use Ethernet instead of Wi-Fi for stability
- Disable unused desktop services (headless mode)
- Add swap space for 2GB models
- Use powered USB hub for multiple dongles

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## 🙏 Acknowledgments

- **FastAPI** - Modern web framework
- **Nmap** - Network scanner
- **Scapy** - Packet manipulation
- **Chart.js** - Beautiful charts
- **BLEAK** - Bluetooth Low Energy platform Agnostic Klient
- **ReportLab** - PDF generation

---

## 📞 Support

- 📖 **Documentation:** See guides above
- 🐛 **Bug Reports:** GitHub Issues
- 💡 **Feature Requests:** GitHub Issues
- 📧 **Contact:** Check repository

---

<div align="center">

**Made with ❤️ for the IoT security community**

[⬆ Back to Top](#pentexone---iot-security-auditor)

</div>
