# PentexOne - Deployment Checklist

Use this checklist to ensure everything is properly set up before deploying PentexOne.

---

## 📋 Pre-Installation Checklist

### Hardware
- [ ] Raspberry Pi 3 Model B+ or newer (Pi 4 recommended)
- [ ] MicroSD card (32GB+ Class 10)
- [ ] Power supply (5V 3A for Pi 4, 5V 2.5A for Pi 3)
- [ ] Ethernet cable (for initial setup)
- [ ] Case with cooling (recommended for Pi 4/5)

### Optional Hardware (for additional protocols)
- [ ] Sonoff Zigbee 3.0 USB Dongle (CC2652P)
- [ ] Nordic nRF52840 Dongle (Thread/Matter)
- [ ] Aeotec Z-Stick 7 (Z-Wave)
- [ ] Powered USB hub (if using 3+ dongles)

### Software
- [ ] Raspberry Pi OS (64-bit) flashed to SD card
- [ ] SSH enabled
- [ ] Wi-Fi configured (optional, Ethernet preferred)
- [ ] System updated (`sudo apt-get update && sudo apt-get upgrade`)

---

## 🛠️ Installation Checklist

### Basic Installation
- [ ] PentexOne files transferred to Raspberry Pi
- [ ] Running `./setup.sh` or `sudo ./rpi_setup.sh`
- [ ] Virtual environment created (`venv/` folder exists)
- [ ] All Python packages installed successfully
- [ ] No errors in installation output

### Configuration
- [ ] `.env` file exists
- [ ] Username changed from default (optional)
- [ ] Password changed from default (REQUIRED!)
- [ ] Database file created (`pentex.db`)
- [ ] Directories created (`generated_reports/`, `static/`)

### Raspberry Pi Service Setup
- [ ] Service file copied to `/etc/systemd/system/pentexone.service`
- [ ] Service file paths are correct for your setup
- [ ] `sudo systemctl daemon-reload` executed
- [ ] `sudo systemctl enable pentexone` executed
- [ ] Service user is correct (usually `pi`)

---

## ✅ Post-Installation Verification

### Service Status
```bash
sudo systemctl status pentexone
```
- [ ] Service is active (running)
- [ ] No errors in status output
- [ ] Started recently (not crashed)

### Port Listening
```bash
sudo netstat -tlnp | grep 8000
```
- [ ] Port 8000 is listening
- [ ] Bound to 0.0.0.0 (not just 127.0.0.1)

### Web Access
```bash
curl http://localhost:8000
```
- [ ] Returns HTML or redirect response
- [ ] No connection errors

### Dashboard Access
- [ ] Open browser: `http://<raspberry-pi-ip>:8000/dashboard`
- [ ] Login page appears
- [ ] Can login with credentials from `.env`
- [ ] Dashboard loads successfully
- [ ] No JavaScript errors in browser console (F12)

### Hardware Detection
- [ ] Navigate to Dashboard
- [ ] Hardware Status section shows connected dongles
- [ ] Built-in Wi-Fi detected
- [ ] Built-in Bluetooth detected
- [ ] USB dongles detected (if connected)

### Protocol Testing
- [ ] Wi-Fi scan works (Discover networks)
- [ ] Bluetooth scan works
- [ ] Zigbee scan works (if dongle connected)
- [ ] Thread scan works (if dongle connected)
- [ ] No error messages during scans

### AI Features
- [ ] AI Security Score displays
- [ ] AI Recommendations appear
- [ ] Device AI Analysis works
- [ ] Score updates after scans

### Reports
- [ ] Navigate to Reports tab
- [ ] PDF Report generates
- [ ] JSON Export downloads
- [ ] CSV Export downloads
- [ ] Files open correctly

---

## 🔐 Security Checklist

### Credentials
- [ ] Default password changed in `.env`
- [ ] Strong password used (12+ characters, mixed case, numbers, symbols)
- [ ] Password not shared or committed to git

### Network Security
- [ ] Firewall enabled (`sudo ufw enable`)
- [ ] Only necessary ports open (22, 8000)
- [ ] SSH using key-based authentication (recommended)
- [ ] SSH password authentication disabled (if using keys)

### System Security
- [ ] System is up to date
- [ ] Automatic security updates enabled (optional)
- [ ] Unused services disabled
- [ ] Strong SSH password or key-based auth

### Application Security
- [ ] `.env` file not accessible from web
- [ ] Database file permissions are restrictive
- [ ] Regular backups scheduled

---

## 📊 Performance Checklist

### System Resources
```bash
htop
df -h
free -h
vcgencmd measure_temp
```
- [ ] CPU usage < 20% when idle
- [ ] Memory usage < 50% when idle
- [ ] Disk space > 5GB free
- [ ] Temperature < 60°C (idle)

### Network Performance
- [ ] Ethernet connection stable (if using)
- [ ] Wi-Fi signal strength good (if using)
- [ ] No packet loss to gateway
- [ ] Reasonable scan times (< 5 min for /24 network)

---

## 🔄 Backup Checklist

### Initial Backup
- [ ] Database backed up (`pentex.db`)
- [ ] `.env` file backed up (securely!)
- [ ] Generated reports backed up
- [ ] Backup stored in separate location

### Backup Automation (Optional)
- [ ] Cron job or systemd timer created for regular backups
- [ ] Backup rotation configured (keep last 7/30/90 days)
- [ ] Backup tested (restore procedure verified)

---

## 📝 Documentation Checklist

### For Your Records
- [ ] Raspberry Pi IP address recorded
- [ ] Admin credentials stored securely
- [ ] Network configuration documented
- [ ] Hardware inventory listed (which dongles, where connected)
- [ ] Custom configurations noted

### For Your Team
- [ ] QUICK_REFERENCE.md shared with team
- [ ] Access instructions documented
- [ ] Troubleshooting guide available
- [ ] Contact information for support

---

## 🧪 Functional Testing

### Complete Test Scan
1. [ ] Connect at least one IoT device to network
2. [ ] Run Wi-Fi scan
3. [ ] Device appears in device list
4. [ ] Click device to see details
5. [ ] Vulnerabilities displayed (if any)
6. [ ] Risk level calculated correctly
7. [ ] AI Analysis provides insights
8. [ ] Export report with scan results

### Multi-Protocol Test (if hardware available)
- [ ] Bluetooth device detected
- [ ] Zigbee devices detected (if dongle)
- [ ] Thread devices detected (if dongle)
- [ ] Z-Wave devices detected (if dongle)
- [ ] Protocol distribution chart accurate

### Stress Test
- [ ] Run multiple scans simultaneously
- [ ] Dashboard remains responsive
- [ ] No crashes or errors
- [ ] Memory usage stable
- [ ] All scans complete successfully

---

## 🚀 Production Readiness

### Before Going Live
- [ ] All checklist items above completed
- [ ] Tested on staging environment (if possible)
- [ ] User acceptance testing completed
- [ ] Performance acceptable for your use case
- [ ] Backup strategy in place
- [ ] Monitoring configured (logs, alerts)
- [ ] Update strategy defined
- [ ] Support plan established

### Monitoring
- [ ] Log rotation configured
- [ ] Disk space monitoring
- [ ] Service health monitoring
- [ ] Alert notifications set up
- [ ] Regular review schedule established

### Maintenance Plan
- [ ] Weekly: Check logs for errors
- [ ] Monthly: Update system packages
- [ ] Monthly: Update PentexOne (if new version)
- [ ] Quarterly: Review and update passwords
- [ ] Quarterly: Test backup restoration
- [ ] Annually: Hardware inspection and cleaning

---

## 📞 Support Information

### Resources
- [ ] GitHub repository bookmarked
- [ ] Documentation downloaded or bookmarked
- [ ] Issue tracker URL saved
- [ ] Community forums joined (if applicable)

### Emergency Contacts
- [ ] System administrator contact information
- [ ] Network administrator contact information
- [ ] Hardware vendor support contacts
- [ ] Security team contact (if applicable)

---

## ✨ Final Verification

### The "Does It Work?" Test
- [ ] Power on Raspberry Pi
- [ ] Wait 2 minutes
- [ ] Open browser from another device
- [ ] Navigate to `http://<pi-ip>:8000`
- [ ] Login successfully
- [ ] Run a quick scan
- [ ] See results
- [ ] Export a report
- [ ] Everything works! 🎉

---

## 📸 Before/After Photos (Optional)

- [ ] Photo of hardware setup
- [ ] Screenshot of dashboard
- [ ] Sample report saved
- [ ] Network diagram updated

---

## ✅ Sign-Off

- [ ] Installation completed by: _______________
- [ ] Date: _______________
- [ ] Tested by: _______________
- [ ] Approved by: _______________
- [ ] Notes: _______________

---

**Congratulations!** If you've checked all applicable items, your PentexOne deployment is ready for production use! 🎊

Remember to:
- 🔐 Keep your credentials secure
- 💾 Maintain regular backups
- 🔄 Keep the system updated
- 📊 Monitor performance and logs
- 📚 Review documentation regularly

**Happy (secure) scanning!** 🔍✨
