# Getting Started Guide

<cite>
**Referenced Files in This Document**
- [backend/README.md](file://backend/README.md)
- [backend/setup.sh](file://backend/setup.sh)
- [backend/start.sh](file://backend/start.sh)
- [backend/rpi_setup.sh](file://backend/rpi_setup.sh)
- [backend/requirements.txt](file://backend/requirements.txt)
- [backend/main.py](file://backend/main.py)
- [backend/pentexone.service](file://backend/pentexone.service)
- [backend/RASPBERRY_PI_GUIDE.md](file://backend/RASPBERRY_PI_GUIDE.md)
- [backend/HARDWARE_GUIDE.md](file://backend/HARDWARE_GUIDE.md)
- [backend/QUICK_REFERENCE.md](file://backend/QUICK_REFERENCE.md)
- [backend/DEPLOYMENT_CHECKLIST.md](file://backend/DEPLOYMENT_CHECKLIST.md)
- [backend/test_dongles.py](file://backend/test_dongles.py)
</cite>

## Table of Contents
1. [Introduction](#introduction)
2. [Prerequisites](#prerequisites)
3. [Quick Start](#quick-start)
4. [Step-by-Step Installation](#step-by-step-installation)
5. [Environment Configuration](#environment-configuration)
6. [Verification Steps](#verification-steps)
7. [Troubleshooting](#troubleshooting)
8. [Local Development vs Raspberry Pi Deployment](#local-development-vs-raspberry-pi-deployment)
9. [Cost Estimates and Hardware Recommendations](#cost-estimates-and-hardware-recommendations)
10. [Conclusion](#conclusion)

## Introduction
PentexOne is a comprehensive IoT security auditing platform with a modern web interface and AI-powered analysis. It supports multiple wireless protocols (Wi‑Fi, Bluetooth, Zigbee, Thread/Matter, Z‑Wave, Lo‑Ra‑WAN) and provides real-time dashboards, vulnerability assessments, and professional reporting capabilities.

## Prerequisites
Before installing PentexOne, ensure your system meets the following requirements:
- Python 3.8 or higher
- pip (Python package manager)
- nmap (network scanner)
- Optional Raspberry Pi 3+ for deployment

These prerequisites are validated and documented in the project’s documentation and setup scripts.

**Section sources**
- [backend/README.md:69-75](file://backend/README.md#L69-L75)
- [backend/requirements.txt:1-21](file://backend/requirements.txt#L1-L21)

## Quick Start
Follow these steps to quickly get PentexOne running:

1. Clone or download the repository to your target machine.
2. Make the setup scripts executable and run the setup script:
   - chmod +x setup.sh start.sh
   - ./setup.sh
3. Configure credentials by editing the .env file:
   - nano .env
   - Change default credentials:
     - PENTEX_USERNAME=admin
     - PENTEX_PASSWORD=your_secure_password
4. Start the application:
   - ./start.sh
   - Or manually activate the virtual environment and run the main application.
5. Access the dashboard:
   - Open your browser and navigate to http://localhost:8000/dashboard

This workflow is documented in the project’s README and quick reference materials.

**Section sources**
- [backend/README.md:76-117](file://backend/README.md#L76-L117)
- [backend/QUICK_REFERENCE.md:5-18](file://backend/QUICK_REFERENCE.md#L5-L18)

## Step-by-Step Installation
### Option A: Local Development Setup
1. Navigate to the backend directory and make scripts executable:
   - cd backend
   - chmod +x setup.sh start.sh
2. Run the setup script to create a virtual environment and install dependencies:
   - ./setup.sh
3. Verify the virtual environment was created and dependencies installed.
4. Start the application:
   - ./start.sh
   - Or manually:
     - source venv/bin/activate
     - python3 main.py

### Option B: Raspberry Pi Deployment
1. Prepare your Raspberry Pi with Raspberry Pi OS (64-bit) and enable SSH.
2. Transfer the PentexOne folder to your Raspberry Pi (via Git, SCP, or USB).
3. Run the Raspberry Pi installer with elevated privileges:
   - cd backend
   - chmod +x rpi_setup.sh
   - sudo ./rpi_setup.sh
4. Configure credentials:
   - nano .env
   - Update PENTEX_USERNAME and PENTEX_PASSWORD
5. Start the service:
   - sudo systemctl start pentexone
6. Enable auto-start on boot:
   - sudo systemctl enable pentexone

The Raspberry Pi deployment process is fully documented in the dedicated guide and installer script.

**Section sources**
- [backend/README.md:120-159](file://backend/README.md#L120-L159)
- [backend/RASPBERRY_PI_GUIDE.md:44-84](file://backend/RASPBERRY_PI_GUIDE.md#L44-L84)
- [backend/rpi_setup.sh:12-28](file://backend/rpi_setup.sh#L12-L28)
- [backend/rpi_setup.sh:65-80](file://backend/rpi_setup.sh#L65-L80)
- [backend/pentexone.service:6-22](file://backend/pentexone.service#L6-L22)

## Environment Configuration
PentexOne uses environment variables for authentication. The default credentials are set in the .env file and must be changed before deployment.

Key configuration steps:
- Locate or create the .env file in the backend directory.
- Set PENTEX_USERNAME and PENTEX_PASSWORD to secure values.
- The application reads these values at runtime from environment variables.

Security considerations:
- Change the default password immediately.
- Consider enabling a firewall and restricting access to necessary ports.
- For production, consider using HTTPS with a reverse proxy and SSL certificates.

**Section sources**
- [backend/main.py:23-28](file://backend/main.py#L23-L28)
- [backend/README.md:308-334](file://backend/README.md#L308-L334)

## Verification Steps
To ensure a successful installation, perform the following checks:

- Service status:
  - sudo systemctl status pentexone
- Port listening:
  - sudo netstat -tlnp | grep 8000
- Local access test:
  - curl http://localhost:8000
- Dashboard accessibility:
  - Open http://<raspberry-pi-ip>:8000/dashboard in a browser
  - Login with credentials from .env
- Hardware detection:
  - Use the dongle test utility to verify connected USB dongles
  - Navigate to the dashboard and confirm hardware status indicators
- Protocol functionality:
  - Run basic scans (Wi‑Fi, Bluetooth) and verify results
- AI features:
  - Confirm AI security scores and recommendations are displayed
- Reporting:
  - Generate and export reports (PDF, JSON, CSV) to verify functionality

A comprehensive post-installation checklist is available for reference.

**Section sources**
- [backend/DEPLOYMENT_CHECKLIST.md:55-112](file://backend/DEPLOYMENT_CHECKLIST.md#L55-L112)
- [backend/QUICK_REFERENCE.md:63-90](file://backend/QUICK_REFERENCE.md#L63-L90)
- [backend/test_dongles.py:14-132](file://backend/test_dongles.py#L14-L132)

## Troubleshooting
Common issues and resolutions:

- Dashboard not accessible:
  - Check service status and logs
  - Verify port 8000 is listening
  - Test locally with curl
- USB dongle not detected:
  - List USB devices and serial ports
  - Check permissions and reboot if necessary
- Bluetooth not working:
  - Restart the Bluetooth service and unblock Bluetooth
- Wi‑Fi scanning problems:
  - Ensure the wireless interface is free and accessible
- Database issues:
  - Backup and reset the database if needed
- Performance issues:
  - Monitor resource usage and adjust system configuration

Additional troubleshooting tips and diagnostic commands are available in the quick reference and Raspberry Pi guides.

**Section sources**
- [backend/README.md:349-382](file://backend/README.md#L349-L382)
- [backend/RASPBERRY_PI_GUIDE.md:402-526](file://backend/RASPBERRY_PI_GUIDE.md#L402-L526)
- [backend/QUICK_REFERENCE.md:63-90](file://backend/QUICK_REFERENCE.md#L63-L90)

## Local Development vs Raspberry Pi Deployment
- Local development:
  - Use setup.sh to create a virtual environment and install dependencies
  - Start the application with start.sh or manually
  - Ideal for testing and development
- Raspberry Pi deployment:
  - Use rpi_setup.sh for a complete system and service setup
  - Manage the application as a systemd service
  - Enable auto-start and monitor logs via journalctl
  - Suitable for continuous operation and remote access

Both approaches share the same core application and configuration, with the Raspberry Pi setup adding system-level automation and service management.

**Section sources**
- [backend/README.md:120-159](file://backend/README.md#L120-L159)
- [backend/RASPBERRY_PI_GUIDE.md:215-263](file://backend/RASPBERRY_PI_GUIDE.md#L215-L263)
- [backend/pentexone.service:6-22](file://backend/pentexone.service#L6-L22)

## Cost Estimates and Hardware Recommendations
### Minimum Setup (Wi‑Fi & Bluetooth Only)
- Raspberry Pi 3 Model B+ or newer
- 2GB RAM
- 32GB microSD card (Class 10)
- 5V 2.5A power supply
- Estimated cost: ~$55–$75

### Recommended Setup (Full Protocol Support)
- Raspberry Pi 4 (4GB)
- 64GB microSD card (Class 10)
- 5V 3A power supply
- Powered USB hub (4+ ports)
- Optional security dongles:
  - Zigbee: Sonoff Zigbee 3.0 USB (CC2652P) – ~$20
  - Thread: Nordic nRF52840 Dongle – ~$12
  - Z‑Wave: Aeotec Z‑Stick 7 – ~$45
- Estimated cost: ~$200–$250

Dongle compatibility and recommendations are documented in the hardware guide.

**Section sources**
- [backend/README.md:182-212](file://backend/README.md#L182-L212)
- [backend/HARDWARE_GUIDE.md:126-153](file://backend/HARDWARE_GUIDE.md#L126-L153)

## Conclusion
You now have the essential information to install, configure, and verify PentexOne for both local development and Raspberry Pi deployment. Follow the step-by-step instructions, verify each stage, and consult the troubleshooting section if needed. For production deployments, ensure secure credentials, firewall configuration, and regular maintenance procedures.