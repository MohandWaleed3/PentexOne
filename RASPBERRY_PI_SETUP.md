# Pentex One - Raspberry Pi Setup Guide

## المتطلبات

### 1. جهاز Raspberry Pi
- Raspberry Pi 4 (مستحسن) أو Pi 3 B+
- Raspberry Pi OS (64-bit) - Debian Bookworm
- اتصال Ethernet أو Wi-Fi

### 2. Dongles (اختياري حسب الاستخدام)
| البروتوكول | الدونجل المطلوب | السعر التقريبي |
|------------|----------------|---------------|
| Zigbee | Sonoff ZBDongle-E أو ConBee II | $15-25 |
| Z-Wave | Zooz ZST10-700 | $25-35 |
| RFID | PN532 (I2C/SPI) | $10-15 |
| Thread | nRF52840 Dongle | $15-20 |

---

## خطوات التثبيت

### 1. تحديث النظام
```bash
sudo apt update && sudo apt upgrade -y
```

### 2. تثبيت Python والمكتبات الأساسية
```bash
sudo apt install -y python3 python3-pip python3-venv git nmap \
    libusb-1.0-0-dev libbluetooth-dev \
    rfkill wireless-tools net-tools
```

### 3. نسخ المشروع
```bash
cd ~
git clone https://github.com/your-repo/pentexone.git
cd pentexone/backend
```

### 4. إنشاء Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
```

### 5. تثبيت المتطلبات
```bash
pip install --upgrade pip wheel

# التثبيت الأساسي (Wi-Fi, Bluetooth, Network Scanning)
pip install fastapi uvicorn websockets python-nmap scapy \
    zeroconf reportlab aiofiles sqlalchemy python-multipart \
    bleak pyserial cryptography

# اختياري - للـ Zigbee
pip install killerbee

# اختياري - للـ Z-Wave
pip install python-openzwave
```

### 6. إعداد Permissions للـ Hardware

#### Zigbee/RZUSB Stick (KillerBee):
```bash
# إضافة قواعد udev
sudo tee /etc/udev/rules.d/99-killerbee.rules << 'EOF'
# RZUSB Stick (Atmel/Microchip)
SUBSYSTEM=="usb", ATTR{idVendor}=="03eb", ATTR{idProduct}=="210a", MODE="0666", GROUP="dialout"
EOF

sudo udevadm control --reload-rules
sudo udevadm trigger

# إضافة المستخدم لمجموعة dialout
sudo usermod -a -G dialout $USER
```

#### Serial Ports (RFID/Zigbee):
```bash
sudo usermod -a -G tty $USER
sudo chmod 666 /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || true
```

### 7. تمكين Bluetooth
```bash
# التأكد من عدم حظر البلوتوث
sudo rfkill unblock bluetooth
sudo systemctl enable bluetooth
sudo systemctl start bluetooth
```

### 8. إعداد Wi-Fi Interface
```bash
# لعرض قائمة الـ Wi-Fi interfaces
iwconfig

# المفروض يكون wlan0 متاح
```

---

## تشغيل المشروع

### الطريقة 1: للتطوير (مع Auto-reload)
```bash
cd ~/pentexone/backend
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### الطريقة 2: للإنتاج (بدون reload)
```bash
cd ~/pentexone/backend
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2
```

### الطريقة 3: تشغيل كـ Service (مستحسن)
```bash
sudo tee /etc/systemd/system/pentexone.service << 'EOF'
[Unit]
Description=Pentex One IoT Security Scanner
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/pentexone/backend
Environment="PATH=/home/pi/pentexone/backend/venv/bin"
ExecStart=/home/pi/pentexone/backend/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable pentexone
sudo systemctl start pentexone

# للتحقق من حالة الخدمة
sudo systemctl status pentexone

# لعرض الـ logs
sudo journalctl -u pentexone -f
```

---

## الوصول للواجهة

بعد تشغيل السيرفر:
- من Raspberry Pi نفسه: http://localhost:8000
- من جهاز آخر في نفس الشبكة: http://[raspberry-pi-ip]:8000

لمعرفة IP الـ Raspberry Pi:
```bash
hostname -I
```

---

## اختبار الهاردوير

### اختبار Zigbee Dongle
```bash
source ~/pentexone/backend/venv/bin/activate
python3 -c "
import serial.tools.list_ports
ports = serial.tools.list_ports.comports()
for p in ports:
    print(f'{p.device}: {p.description} [{p.vid:04x}:{p.pid:04x}]')
"
```

### اختبار Bluetooth
```bash
hciconfig
# أو
bluetoothctl scan on
```

### اختبار RFID (PN532)
```bash
# تثبيت مكتبة PN532
pip install pyserial pyusb

# التحقق من الاتصال
lsusb | grep -i nxp
```

---

## استكشاف الأخطاء

### مشكلة: Permission denied on serial port
```bash
sudo usermod -a -G dialout,tty $USER
# ثم logout و login مرة أخرى
```

### مشكلة: nmap requires root
```bash
sudo setcap cap_net_raw,cap_net_admin,cap_net_bind_service+eip $(which nmap)
# أو
sudo chmod u+s $(which nmap)
```

### مشكلة: Bluetooth not working
```bash
sudo systemctl restart bluetooth
sudo rfkill unblock bluetooth
```

### مشكلة: KillerBee not detecting RZUSB
```bash
# التحقق من أن الـ stick موصول
lsusb | grep -i "210a\|Atmel\|RZUSB"

# إذا ظهر، تحقق من permissions:
ls -la /dev/bus/usb/*/
```

---

## تحسين الأداء على Raspberry Pi

### 1. زيادة Swap (لو RAM 1GB أو أقل)
```bash
sudo dphys-swapfile swapoff
sudo nano /etc/dphys-swapfile
# غير CONF_SWAPSIZE=1024
sudo dphys-swapfile setup
sudo dphys-swapfile swapon
```

### 2. تعطيل Services غير ضرورية
```bash
sudo systemctl disable bluetooth  # لو مش محتاج BLE
sudo systemctl disable avahi-daemon  # لو مش محتاج mDNS
```

### 3. استخدام SQLite بدل PostgreSQL (افتراضي)
المشروع بيستخدم SQLite افتراضياً - لا تغيير مطلوب.

---

## حماية النظام

### تغيير الـ Default Credentials
```bash
export PENTEX_USERNAME=admin
export PENTEX_PASSWORD=your_secure_password
```

أو عدّل في `main.py`:
```python
VALID_USERNAME = os.getenv("PENTEX_USERNAME", "your_user")
VALID_PASSWORD = os.getenv("PENTEX_PASSWORD", "your_pass")
```

---

## تحديث المشروع

```bash
cd ~/pentexone
git pull origin main
cd backend
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart pentexone  # لو بتستخدم service
```

---

## ملاحظات هامة

1. **Wi-Fi Interface**: على Raspberry Pi، الـ Wi-Fi interface بيكون `wlan0` مش `en0` زي macOS
2. **Zigbee**: KillerBee يحتاج صلاحيات root للـ raw packet capture
3. **Performance**: الـ AI Analysis ممكن يكون بطيء على Pi 3 - Pi 4 مستحسن
4. **Power**: استخدام multiple dongles يحتاج power supply قوي (3A+)

---

## روابط مفيدة

- [KillerBee GitHub](https://github.com/riverloopsec/killerbee)
- [PySerial Documentation](https://pyserial.readthedocs.io/)
- [Raspberry Pi GPIO Pinout](https://pinout.xyz/)
