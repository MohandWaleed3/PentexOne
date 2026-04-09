# PentexOne - Raspberry Pi Hardware Guide

## 📋 Overview
This guide covers the hardware requirements and setup instructions for running PentexOne IoT Security Auditor on a Raspberry Pi.

---

## 🖥️ Required Hardware

### 1. Raspberry Pi (Choose One)
| Model | Recommendation | Notes |
|-------|---------------|-------|
| **Raspberry Pi 4 (4GB/8GB)** | ⭐⭐⭐⭐⭐ Best | Best performance, USB 3.0 |
| **Raspberry Pi 4 (2GB)** | ⭐⭐⭐⭐ Good | Sufficient for most tasks |
| **Raspberry Pi 5** | ⭐⭐⭐⭐⭐ Excellent | Latest model, best performance, requires 5V 5A for full USB support |
| Raspberry Pi 3 Model B+ | ⭐⭐⭐ OK | Works but slower, USB 2.0 only |

**Minimum Requirements:**
- Raspberry Pi 3 Model B+ or newer
- 2GB RAM minimum (4GB recommended)
- 32GB microSD card (Class 10 or better)
- **Stable Power Supply:**
  - **Pi 5:** 5V 5A (27W) recommended for full USB current.
  - **Pi 4:** 5V 3A (15W).
  - **Pi 3:** 5V 2.5A.

---

## 🔌 Protocol Support & Required Dongles

### Essential Protocols (Built-in)

#### ✅ Wi-Fi (Built-in)
- **Hardware:** Raspberry Pi built-in Wi-Fi
- **Supported:** 802.11 b/g/n/ac (Pi 3/4/5)
- **Range:** ~30 meters indoor
- **No additional hardware required**

#### ✅ Bluetooth/BLE (Built-in)
- **Hardware:** Raspberry Pi built-in Bluetooth 4.2/5.0
- **Supported:** BLE 4.0+, Bluetooth Classic
- **Range:** ~10 meters
- **No additional hardware required**

---

### Optional Protocols (Requires USB Dongles)

#### 🔶 Zigbee (Optional)
**Option 1: Sonoff Zigbee 3.0 USB Dongle Plus (Recommended)**
- **Model:** CC2652P chip
- **Price:** ~$20-25
- **Buy:** [Sonoff Official](https://sonoff.tech/product/gateway-and-sensors/sonoff-zigbee-3-0-usb-dongle-plus-p/)
- **Setup:** Plug and play

**Option 2: CC2531 USB Dongle**
- **Model:** CC2531
- **Price:** ~$10-15
- **Note:** Older, less powerful than CC2652P
- **Setup:** May require firmware flashing

**Installation:**
```bash
# Plug in the dongle to USB port
# Check if detected:
ls -la /dev/ttyUSB*
# Should show: /dev/ttyUSB0

# Test with PentexOne:
cd ~/PentexOne/backend
python3 test_dongles.py
```

---

#### 🔶 Thread/Matter (Optional)
**Recommended: Nordic nRF52840 Dongle**
- **Model:** nRF52840 Dongle
- **Price:** ~$10-15
- **Buy:** [Nordic Semi](https://www.nordicsemi.com/Products/Development-hardware/nrf52840-dongle)
- **Setup:** Plug and play

**Alternative: Home Assistant SkyConnect**
- **Model:** SkyConnect (supports both Zigbee & Thread)
- **Price:** ~$30
- **Buy:** [Home Assistant](https://www.home-assistant.io/skyconnect/)

**Installation:**
```bash
# Plug in the dongle
# Check detection:
ls -la /dev/ttyACM*
# Should show: /dev/ttyACM0
```

---

#### 🔶 Z-Wave (Optional)
**Recommended: Aeotec Z-Stick 7**
- **Model:** Z-Wave Gen5+
- **Price:** ~$40-50
- **Buy:** [Amazon](https://www.amazon.com/Aeotec-Z-Stick-Z-Wave-Plus-Controller/dp/B08X9CW6K7)
- **Setup:** Plug and play

**Alternative: Zooz Z-Wave Plus S2 Stick**
- **Price:** ~$35-40
- **Good alternative to Aeotec**

**Installation:**
```bash
# Plug in the Z-Wave stick
# Check detection:
ls -la /dev/ttyUSB*
# Usually shows as /dev/ttyUSB0 or /dev/ttyUSB1
```

---

#### 🔶 LoRaWAN (Optional - Advanced)
**Recommended: Dragino USB LoRa Adapter**
- **Model:** Dragino Lora USB
- **Price:** ~$30-40
- **Note:** Primarily for listening, not full protocol analysis

**Note:** LoRaWAN support is experimental and requires additional configuration.

---

## 🔧 Complete Hardware Setup

### Scenario 1: Basic Setup (Wi-Fi & Bluetooth Only)
```
Raspberry Pi 4
├── MicroSD Card (32GB+)
├── Power Supply (5V 3A)
└── Ethernet Cable (for initial setup)

Total Cost: ~$55-75 (Pi 4)
Protocols: Wi-Fi, Bluetooth/BLE
```

### Scenario 2: Full Setup (All Protocols)
```
Raspberry Pi 4 (4GB)
├── MicroSD Card (64GB)
├── Power Supply (5V 3A)
├── USB Hub (Powered, 4+ ports)
├── Sonoff Zigbee 3.0 Dongle (CC2652P)
├── Nordic nRF52840 Dongle (Thread/Matter)
├── Aeotec Z-Stick 7 (Z-Wave)
└── Case with Cooling

Total Cost: ~$200-250
Protocols: Wi-Fi, Bluetooth, Zigbee, Thread/Matter, Z-Wave
```

---

## 🛠️ Physical Setup Instructions

### Step 1: Prepare Raspberry Pi
1. Flash Raspberry Pi OS (64-bit) to microSD card
   ```bash
   # Use Raspberry Pi Imager: https://www.raspberrypi.com/software/
   # Select: Raspberry Pi OS (64-bit)
   ```

2. Enable SSH and configure Wi-Fi (optional)
   - Create `ssh` file in boot partition
   - Create `wpa_supplicant.conf` for Wi-Fi

3. Boot the Raspberry Pi and connect via SSH
   ```bash
   ssh pi@<raspberry-pi-ip>
   # Default password: raspberry
   ```

### Step 2: System Configuration
```bash
# Update system
sudo apt-get update
sudo apt-get upgrade -y

# Enable required interfaces
sudo raspi-config
# Navigate to:
# 3 Interface Options
#   - P2 SSH: Enable
#   - P4 SPI: Enable (for some dongles)
#   - P5 I2C: Enable (optional)

# Set GPU memory to minimum (headless mode)
# In raspi-config: Performance Options > GPU Memory: 16

# Reboot
sudo reboot
```

### Step 3: Install PentexOne
```bash
# Clone or copy PentexOne to Raspberry Pi
cd ~
git clone <your-repo-url>  # OR copy via USB/SCP
cd PentexOne/backend

# Run the setup script
chmod +x rpi_setup.sh
sudo ./rpi_setup.sh
```

### Step 4: Connect USB Dongles
```bash
# Plug in all USB dongles
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

### Step 5: Configure and Start
```bash
# Change default password
nano .env
# Update: PENTEX_PASSWORD=your_secure_password

# Start the service
sudo systemctl start pentexone

# Check status
sudo systemctl status pentexone

# View logs
sudo journalctl -u pentexone -f
```

### Step 6: Access Dashboard
Open browser and navigate to:
```
http://<raspberry-pi-ip>:8000
```

Default credentials:
- **Username:** admin
- **Password:** (as set in .env file)

---

## 🔍 Troubleshooting

### Issue: USB Dongle Not Detected
```bash
# Check USB devices
lsusb

# Check dmesg for errors
dmesg | grep -i usb
dmesg | grep -i tty

# Check permissions
sudo usermod -a -G dialout pi
sudo usermod -a -G tty pi

# Reboot
sudo reboot
```

### Issue: Bluetooth Not Working
```bash
# Restart Bluetooth service
sudo systemctl restart bluetooth

# Check Bluetooth status
bluetoothctl
# Should show: [bluetooth]#

# If not working, reinstall BlueZ
sudo apt-get install --reinstall bluez bluez-tools
```

### Issue: Wi-Fi Scanning Fails
```bash
# Ensure you have permission
sudo iwlist wlan0 scan

# If interface is busy, disconnect from network temporarily
sudo nmcli radio wifi off
# Run scan
# Reconnect
sudo nmcli radio wifi on
```

### Issue: Service Won't Start
```bash
# Check logs
sudo journalctl -u pentexone -n 50 --no-pager

# Check if port is in use
sudo netstat -tlnp | grep 8000

# Try manual start
cd ~/PentexOne/backend
source venv/bin/activate
python3 main.py
```

---

## 📊 Performance Optimization

### For Raspberry Pi 3
```bash
# Reduce memory usage
# Edit config.txt
sudo nano /boot/config.txt

# Add:
gpu_mem=16
disable_splash=1
dtparam=audio=off
```

### For All Models
```bash
# Use a powered USB hub for multiple dongles
# Disable unused services
sudo systemctl disable cups
sudo systemctl disable avahi-daemon

# Add swap if needed (for 2GB models)
sudo dphys-swapfile swapoff
sudo nano /etc/dphys-swapfile
# Change: CONF_SWAPSIZE=1024
sudo dphys-swapfile setup
sudo dphys-swapfile swapon
```

---

## 🔋 Portable & Battery Operation
If you are plan to run PentexOne on a battery or power bank:

1. **Check the Portable Guide:** [PORTABLE_POWER_GUIDE_AR.md](PORTABLE_POWER_GUIDE_AR.md)
2. **Use the Optimizer:** Run `./optimize_power.sh` to tune your system for battery life and speed.
3. **Power Bank Note:** For Pi 5, ensure your power bank supports PD 3.0 / 25W+ output.

---

## 🔐 Security Recommendations

1. **Change default credentials**
   ```bash
   nano .env
   # Set strong password
   ```

2. **Enable firewall**
   ```bash
   sudo ufw allow 22/tcp    # SSH
   sudo ufw allow 8000/tcp  # PentexOne
   sudo ufw enable
   ```

3. **Keep system updated**
   ```bash
   sudo apt-get update
   sudo apt-get upgrade
   ```

4. **Use SSH keys instead of passwords**
   ```bash
   ssh-keygen -t ed25519
   ssh-copy-id pi@<raspberry-pi-ip>
   ```

5. **Disable password SSH login**
   ```bash
   sudo nano /etc/ssh/sshd_config
   # Set: PasswordAuthentication no
   sudo systemctl restart ssh
   ```

---

## 📞 Support & Resources

- **GitHub Issues:** Report bugs and feature requests
- **Documentation:** Check README.md and this guide
- **API Docs:** http://<pi-ip>:8000/docs

---

## 📝 Notes

- **Power Requirements:** Use a quality power supply. Multiple USB dongles increase power draw.
- **USB Hub:** If using 3+ dongles, use a powered USB hub.
- **Heat:** Raspberry Pi 4/5 can get hot. Use a case with heatsinks or fan.
- **Network:** For best Wi-Fi scanning, use Ethernet connection and keep Wi-Fi interface free.
- **Range:** External antennas on dongles can improve range significantly.

---

**Last Updated:** April 2026
**Version:** 1.0
