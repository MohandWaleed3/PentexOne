# PentexOne - Quick Reference Card

## 🚀 Quick Start

### First Time Setup
```bash
# 1. Install dependencies
./setup.sh

# 2. Change password
nano .env

# 3. Start server
./start.sh

# 4. Open browser
# http://localhost:8000/dashboard
```

### Raspberry Pi Deployment
```bash
# 1. Run Raspberry Pi installer
sudo ./rpi_setup.sh

# 2. Change password
nano .env

# 3. Start service
sudo systemctl start pentexone

# 4. Enable auto-start
sudo systemctl enable pentexone
```

---

## 📡 Common Commands

### Service Management
```bash
sudo systemctl start pentexone      # Start
sudo systemctl stop pentexone       # Stop
sudo systemctl restart pentexone    # Restart
sudo systemctl status pentexone     # Status
sudo systemctl enable pentexone     # Auto-start on boot
```

### View Logs
```bash
sudo journalctl -u pentexone -f         # Follow logs
sudo journalctl -u pentexone -n 50      # Last 50 lines
```

### Manual Start (Testing)
```bash
cd ~/PentexOne/backend
source venv/bin/activate
python3 main.py
```

---

## 🔧 Troubleshooting

### Check if Running
```bash
sudo systemctl status pentexone
curl http://localhost:8000
```

### Port Already in Use
```bash
sudo netstat -tlnp | grep 8000
sudo kill -9 <PID>
```

### USB Dongle Not Detected
```bash
lsusb                    # List USB devices
ls -la /dev/ttyUSB*      # Check serial ports
ls -la /dev/ttyACM*      # Check ACM ports
```

### Test Hardware
```bash
source venv/bin/activate
python3 test_dongles.py
```

---

## 🌐 Access Points

- **Dashboard:** http://<ip>:8000/dashboard
- **API Docs:** http://<ip>:8000/docs
- **Login Page:** http://<ip>:8000/login

---

## 📁 Important Files

```
PentexOne/backend/
├── main.py                  # Main application
├── .env                     # Configuration (passwords)
├── pentex.db                # Database
├── setup.sh                 # Setup script (all platforms)
├── rpi_setup.sh             # Raspberry Pi installer
├── start.sh                 # Quick start script
├── pentexone.service        # Systemd service file
├── HARDWARE_GUIDE.md        # Hardware documentation
├── RASPBERRY_PI_GUIDE.md    # RPi deployment guide
└── generated_reports/       # PDF reports
```

---

## 🔐 Default Credentials

- **Username:** admin
- **Password:** pentex2024
- **⚠️ Change immediately in .env file!**

---

## 📊 Hardware Requirements

### Minimum
- Raspberry Pi 3 Model B+
- 2GB RAM
- 32GB microSD card
- 5V 2.5A power supply

### Recommended
- Raspberry Pi 4 (4GB)
- 64GB microSD card (Class 10)
- 5V 3A power supply
- Powered USB hub (for multiple dongles)

### Optional Dongles
- **Zigbee:** Sonoff Zigbee 3.0 USB (CC2652P)
- **Thread:** Nordic nRF52840 Dongle
- **Z-Wave:** Aeotec Z-Stick 7
- **LoRaWAN:** Dragino USB LoRa

---

## 🎯 UI Tips

### Dashboard Layout
1. **Quick Scan Bar** - One-click scanning for common protocols
2. **Advanced Options** - Network configuration and additional protocols
3. **Stats Cards** - Real-time device counts by risk level
4. **Charts** - Visual risk and protocol distribution
5. **Hardware Status** - Connected dongles status
6. **AI Score** - Security score and recommendations
7. **Device Table** - Click any device for details

### Scanning Workflow
1. Click **Discover** to find networks
2. Select network or enter manually
3. Click **Wi-Fi Scan** (or other protocol)
4. Watch progress bar
5. Click devices in table to see details
6. Use **AI Analysis** for deep insights
7. Export reports from Reports tab

---

## 🆘 Get Help

- **Hardware Guide:** `HARDWARE_GUIDE.md`
- **RPi Guide:** `RASPBERRY_PI_GUIDE.md`
- **API Docs:** http://localhost:8000/docs
- **Logs:** `sudo journalctl -u pentexone -f`

---

**Print this card for quick reference!** 📄
