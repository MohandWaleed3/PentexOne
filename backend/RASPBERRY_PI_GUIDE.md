# PentexOne - Raspberry Pi Deployment Guide

## 📖 Table of Contents
1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Quick Start (5 Minutes)](#quick-start-5-minutes)
4. [Detailed Installation](#detailed-installation)
5. [Running PentexOne](#running-pentexone)
6. [Management Commands](#management-commands)
7. [Updating PentexOne](#updating-pentexone)
8. [Backup & Restore](#backup--restore)
9. [Troubleshooting](#troubleshooting)

---

## Overview

PentexOne is a comprehensive IoT Security Auditor that runs on Raspberry Pi and supports multiple wireless protocols:

- ✅ **Wi-Fi** - Network scanning, device discovery, vulnerability assessment
- ✅ **Bluetooth/BLE** - BLE device scanning and analysis
- ✅ **Zigbee** - Zigbee network sniffing (requires USB dongle)
- ✅ **Thread/Matter** - Thread and Matter device discovery (requires USB dongle)
- ✅ **Z-Wave** - Z-Wave network scanning (requires USB dongle)
- ✅ **AI-Powered Analysis** - Intelligent security scoring and recommendations

---

## Prerequisites

### Hardware
- Raspberry Pi 3 Model B+ or newer (Pi 4 recommended)
- 32GB+ microSD card (Class 10)
- Stable power supply (5V 3A for Pi 4)
- Ethernet connection (recommended for setup)
- Optional: USB security dongles for additional protocols

### Software
- Raspberry Pi OS (64-bit) - Bullseye or Bookworm
- Internet connection for initial setup

---

## Quick Start (5 Minutes)

### 1. Flash Raspberry Pi OS
Download and flash using [Raspberry Pi Imager](https://www.raspberrypi.com/software/)
- Select: **Raspberry Pi OS (64-bit)**
- Enable SSH in settings
- Configure Wi-Fi (optional)

### 2. Boot and Connect
```bash
# SSH into Raspberry Pi
ssh pi@<raspberry-pi-ip>
# Default password: raspberry
```

### 3. Install PentexOne
```bash
# Copy PentexOne folder to Raspberry Pi (from your computer)
scp -r ~/Desktop/PentexOne pi@<raspberry-pi-ip>:~/

# On Raspberry Pi:
cd ~/PentexOne/backend
chmod +x rpi_setup.sh
sudo ./rpi_setup.sh
```

### 4. Configure and Start
```bash
# Change password
nano .env
# Edit: PENTEX_PASSWORD=your_new_password

# Start service
sudo systemctl start pentexone

# Access dashboard
# Open browser: http://<raspberry-pi-ip>:8000
```

**Done!** 🎉

---

## Detailed Installation

### Step 1: Prepare Raspberry Pi OS

#### Flash SD Card
1. Download [Raspberry Pi Imager](https://www.raspberrypi.com/software/)
2. Insert microSD card into computer
3. Select OS: **Raspberry Pi OS (64-bit)**
4. Select storage: Your microSD card
5. Click Settings (gear icon):
   - ✅ Enable SSH
   - Set username/password
   - Configure Wi-Fi (optional)
6. Click Write

#### First Boot
1. Insert SD card into Raspberry Pi
2. Connect Ethernet cable (recommended)
3. Connect power supply
4. Wait 1-2 minutes for boot

### Step 2: Initial System Setup

```bash
# SSH into Pi
ssh pi@<raspberry-pi-ip>

# Update system
sudo apt-get update
sudo apt-get upgrade -y

# Configure locale and timezone
sudo raspi-config
# 5 Localisation Options
#   - L1 Locale: Set to your region
#   - L2 Timezone: Set your timezone
#   - L3 Keyboard: Configure if needed

# Set hostname (optional)
sudo raspi-config
# 1 System Options > S4 Hostname: pentexone

# Reboot
sudo reboot
```

### Step 3: Transfer PentexOne

#### Option A: Using Git (Recommended)
```bash
cd ~
git clone <your-repository-url>
cd PentexOne/backend
```

#### Option B: Using SCP
From your computer:
```bash
scp -r ~/Desktop/PentexOne pi@<raspberry-pi-ip>:~/
```

#### Option C: Using USB Drive
```bash
# Mount USB drive
sudo mkdir /media/usb
sudo mount /dev/sda1 /media/usb

# Copy files
cp -r /media/usb/PentexOne ~/
cd ~/PentexOne/backend
```

### Step 4: Run Installation Script

```bash
cd ~/PentexOne/backend

# Make script executable
chmod +x rpi_setup.sh

# Run installer (requires sudo)
sudo ./rpi_setup.sh
```

The installer will:
1. ✅ Update system packages
2. ✅ Install Python and system dependencies
3. ✅ Create Python virtual environment
4. ✅ Install Python packages
5. ✅ Configure Bluetooth
6. ✅ Set up environment variables
7. ✅ Install systemd service for auto-start
8. ✅ Set proper permissions

### Step 5: Configure Security

```bash
# Edit environment file
nano .env

# Change these:
PENTEX_USERNAME=admin
PENTEX_PASSWORD=your_very_secure_password_here

# Save and exit (Ctrl+X, Y, Enter)
```

### Step 6: Connect USB Dongles (Optional)

```bash
# Plug in your USB dongles
# List connected devices:
lsusb

# Check serial ports:
ls -la /dev/ttyUSB*
ls -la /dev/ttyACM*

# Test dongles:
cd ~/PentexOne/backend
source venv/bin/activate
python3 test_dongles.py
```

See [HARDWARE_GUIDE.md](HARDWARE_GUIDE.md) for detailed hardware setup.

---

## Running PentexOne

### Using systemd Service (Recommended)

```bash
# Start the service
sudo systemctl start pentexone

# Stop the service
sudo systemctl stop pentexone

# Restart the service
sudo systemctl restart pentexone

# Check status
sudo systemctl status pentexone

# Enable auto-start on boot
sudo systemctl enable pentexone

# Disable auto-start
sudo systemctl disable pentexone
```

### Manual Start (For Testing)

```bash
cd ~/PentexOne/backend
source venv/bin/activate
python3 main.py
```

### Access the Dashboard

1. Find your Raspberry Pi's IP address:
   ```bash
   hostname -I
   ```

2. Open browser and navigate to:
   ```
   http://<raspberry-pi-ip>:8000
   ```

3. Login with your credentials:
   - Username: (from .env file)
   - Password: (from .env file)

---

## Management Commands

### View Logs

```bash
# View recent logs
sudo journalctl -u pentexone -n 50

# Follow logs in real-time
sudo journalctl -u pentexone -f

# View logs from today
sudo journalctl -u pentexone --since today

# View logs with timestamps
sudo journalctl -u pentexone -o short-iso
```

### Monitor System Resources

```bash
# Check CPU and memory usage
htop

# Check disk space
df -h

# Check temperature
vcgencmd measure_temp

# Monitor network activity
sudo nethogs
```

### Backup Data

```bash
# Backup database and reports
cd ~
tar -czf pentexone_backup_$(date +%Y%m%d).tar.gz \
    PentexOne/backend/pentex.db \
    PentexOne/backend/generated_reports/

# Copy backup to safe location
scp pentexone_backup_*.tar.gz user@backup-server:/backups/
```

---

## Updating PentexOne

### Update from Git

```bash
cd ~/PentexOne

# Pull latest changes
git pull origin main

# Update dependencies
cd backend
source venv/bin/activate
pip3 install -r requirements.txt --upgrade

# Restart service
sudo systemctl restart pentexone
```

### Manual Update

```bash
# Stop service
sudo systemctl stop pentexone

# Backup current installation
cd ~
cp -r PentexOne PentexOne.backup

# Replace with new version
# (copy new files to ~/PentexOne/backend)

# Update dependencies
cd ~/PentexOne/backend
source venv/bin/activate
pip3 install -r requirements.txt

# Start service
sudo systemctl start pentexone

# Verify everything works
sudo systemctl status pentexone
```

---

## Backup & Restore

### Create Backup

```bash
#!/bin/bash
# save as backup_pentexone.sh

BACKUP_DIR=~/backups
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="pentexone_${TIMESTAMP}"

mkdir -p $BACKUP_DIR

# Create backup
tar -czf $BACKUP_DIR/${BACKUP_NAME}.tar.gz \
    ~/PentexOne/backend/pentex.db \
    ~/PentexOne/backend/generated_reports/ \
    ~/PentexOne/backend/.env

echo "✅ Backup created: $BACKUP_DIR/${BACKUP_NAME}.tar.gz"
```

### Restore from Backup

```bash
# Stop service
sudo systemctl stop pentexone

# Restore backup
cd ~
tar -xzf pentexone_20260403_120000.tar.gz

# Set permissions
sudo chown -R pi:pi ~/PentexOne

# Start service
sudo systemctl start pentexone
```

---

## Troubleshooting

### Service Won't Start

```bash
# Check logs
sudo journalctl -u pentexone -n 100 --no-pager

# Common issues:
# 1. Port already in use
sudo netstat -tlnp | grep 8000
sudo kill -9 <PID>

# 2. Missing dependencies
cd ~/PentexOne/backend
source venv/bin/activate
pip3 install -r requirements.txt

# 3. Permission issues
sudo chown -R pi:pi ~/PentexOne
```

### Can't Access Dashboard

```bash
# Check if service is running
sudo systemctl status pentexone

# Check firewall
sudo ufw status
sudo ufw allow 8000/tcp

# Check if listening on port
sudo netstat -tlnp | grep 8000

# Test locally
curl http://localhost:8000
```

### USB Dongle Not Detected

```bash
# List USB devices
lsusb

# Check kernel messages
dmesg | grep -i usb
dmesg | grep -i tty

# Check permissions
ls -la /dev/ttyUSB*
ls -la /dev/ttyACM*

# Add user to dialout group
sudo usermod -a -G dialout pi
sudo usermod -a -G tty pi

# Reboot
sudo reboot
```

### Bluetooth Issues

```bash
# Restart Bluetooth
sudo systemctl restart bluetooth

# Check status
bluetoothctl show

# Rescan devices
bluetoothctl scan on

# If still not working
sudo systemctl restart bluetooth
sudo rfkill unblock bluetooth
```

### Wi-Fi Scanning Problems

```bash
# Check wireless interface
iwconfig

# Scan for networks
sudo iwlist wlan0 scan

# If interface is busy
sudo nmcli radio wifi off
# Run your scan
sudo nmcli radio wifi on
```

### Database Issues

```bash
# Backup database
cp ~/PentexOne/backend/pentex.db ~/pentex.db.backup

# Reset database (WARNING: Deletes all data)
cd ~/PentexOne/backend
rm pentex.db
python3 -c "from database import init_db; init_db()"
```

### Performance Issues

```bash
# Check resource usage
htop

# If memory is low
free -h

# Add more swap
sudo systemctl stop dphys-swapfile
sudo nano /etc/dphys-swapfile
# Change: CONF_SWAPSIZE=2048
sudo systemctl start dphys-swapfile

# Reduce GPU memory
sudo nano /boot/config.txt
# Add: gpu_mem=16
```

---

## Advanced Configuration

### Change Port

Edit `main.py` and change the port:
```python
# In main.py, add at the bottom:
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)  # Change 8000 to 8080
```

Update systemd service:
```bash
sudo nano /etc/systemd/system/pentexone.service
# No changes needed if using main.py

sudo systemctl daemon-reload
sudo systemctl restart pentexone
```

### Enable HTTPS (SSL/TLS)

```bash
# Install nginx
sudo apt-get install nginx

# Get SSL certificate (Let's Encrypt)
sudo apt-get install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com

# Configure nginx as reverse proxy
sudo nano /etc/nginx/sites-available/pentexone

server {
    listen 443 ssl;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

# Enable site
sudo ln -s /etc/nginx/sites-available/pentexone /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

## Uninstall PentexOne

```bash
# Stop and disable service
sudo systemctl stop pentexone
sudo systemctl disable pentexone

# Remove service file
sudo rm /etc/systemd/system/pentexone.service
sudo systemctl daemon-reload

# Remove installation
cd ~
rm -rf PentexOne

# Remove dependencies (optional)
sudo apt-get remove --purge nmap bluez
sudo apt-get autoremove
```

---

## Getting Help

### Resources
- 📖 **Hardware Guide:** [HARDWARE_GUIDE.md](HARDWARE_GUIDE.md)
- 📚 **API Documentation:** http://<pi-ip>:8000/docs
- 💬 **Issues & Support:** GitHub Issues

### Diagnostic Information
When reporting issues, include:
```bash
# System info
uname -a
cat /proc/cpuinfo | grep "Model"
free -h
df -h

# Python version
python3 --version

# PentexOne logs
sudo journalctl -u pentexone -n 100 --no-pager

# USB devices
lsusb

# Network info
ip addr show
```

---

**Happy Hacking! 🔐🚀**

Last Updated: April 2026
Version: 1.0
