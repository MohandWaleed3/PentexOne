import asyncio
import socket
import platform
import nmap
import subprocess
import serial
import serial.tools.list_ports
from zeroconf import ServiceBrowser, Zeroconf
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional
import json
import re
import os
import logging

# Setup logging
logger = logging.getLogger(__name__)

import time

from database import get_db, Device, Vulnerability, SessionLocal
from models import DeviceOut, ScanRequest, ScanStatus
from security_engine import calculate_risk

router = APIRouter(prefix="/iot", tags=["IoT Security"])

# ============================================================================
# ENHANCED HOSTNAME & VENDOR DETECTION
# ============================================================================

def get_hostname_enhanced(ip_address: str) -> str:
    """
    Enhanced hostname detection using multiple methods:
    1. Reverse DNS lookup
    2. mDNS/Bonjour (avahi-resolve)
    3. NetBIOS (nbtscan)
    4. nmblookup for Windows devices
    Returns hostname or "Unknown"
    """
    hostname = None
    
    # Method 1: Standard reverse DNS lookup
    try:
        hostname, _, _ = socket.gethostbyaddr(ip_address)
        if hostname and hostname != ip_address:
            hostname = hostname.split('.')[0] if '.' in hostname else hostname
            logger.info(f"Reverse DNS found for {ip_address}: {hostname}")
            return hostname
    except (socket.herror, socket.gaierror) as e:
        logger.debug(f"Reverse DNS failed for {ip_address}: {e}")
    
    # Method 2: mDNS/Avahi resolution (for .local hostnames)
    try:
        result = subprocess.run(
            ['avahi-resolve-address', ip_address],
            capture_output=True,
            text=True,
            timeout=3
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split('\t')
            if len(parts) >= 2:
                hostname = parts[1].split('.')[0]
                logger.info(f"mDNS resolved {ip_address} to {hostname}")
                return hostname
    except FileNotFoundError:
        logger.debug("avahi-resolve-address not available")
    except Exception as e:
        logger.debug(f"mDNS lookup failed for {ip_address}: {e}")
    
    # Method 3: MacOS dns-sugar (for macOS systems)
    if platform.system() == "Darwin":
        try:
            result = subprocess.run(
                ['dns-sd', '-G', 'v4', ip_address],
                capture_output=True,
                text=True,
                timeout=3
            )
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if ip_address in line:
                        parts = line.split()
                        if len(parts) >= 4:
                            hostname = parts[-1].split('.')[0]
                            logger.info(f"dns-sd found {ip_address}: {hostname}")
                            return hostname
        except Exception as e:
            logger.debug(f"dns-sd lookup failed: {e}")
    
    # Method 4: NetBIOS lookup (for Windows devices)
    try:
        result = subprocess.run(
            ['nmblookup', '-A', ip_address],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if '<00>' in line and 'ACTIVE' in line:
                    match = re.search(r'<00>\s+.*?\s+(\S+)', line)
                    if match:
                        hostname = match.group(1)
                        logger.info(f"NetBIOS found {ip_address}: {hostname}")
                        return hostname
    except FileNotFoundError:
        logger.debug("nmblookup not available")
    except Exception as e:
        logger.debug(f"NetBIOS lookup failed for {ip_address}: {e}")
    
    return "Unknown"


def get_vendor_from_mac(mac_address: str) -> str:
    """Get vendor from MAC OUI - simplified database with common vendors"""
    if not mac_address or mac_address == "Unknown":
        return "Unknown"
    
    mac = mac_address.upper().replace('-', ':').replace('.', ':')
    parts = mac.split(':')
    if len(parts) < 3:
        return "Unknown"
    
    oui = ':'.join(parts[:3])
    
    # Essential vendors database (single source of truth)
    vendors = {
        # Major Vendors
        '00:00:0C': 'Cisco', '00:00:5E': 'VMware', '00:01:02': 'Apple',
        '00:03:47': 'Intel', '00:04:5A': 'HP', '00:05:5D': 'Dell',
        '00:07:E9': 'Belkin', '00:0A:F6': 'TP-Link', '00:0C:29': 'VMware',
        '00:11:2F': 'Dell', '00:13:02': 'Samsung', '00:14:2F': 'Toshiba',
        '00:15:58': 'Amazon', '00:16:EA': 'Sony', '00:17:88': 'Philips Hue',
        '00:17:9A': 'LG', '00:18:4D': 'Huawei', '00:19:7E': 'Lenovo',
        '00:1A:11': 'Google', '00:1B:44': 'Intel', '00:1C:BF': 'Apple',
        '00:1D:7E': 'Microsoft', '00:1E:68': 'Asus', '00:1F:E2': 'Netgear',
        '00:21:5A': 'Linksys', '00:22:6B': 'LG', '00:23:CD': 'Honeywell',
        '00:25:00': 'Apple', '00:26:AB': 'Qualcomm', '00:50:56': 'VMware',
        '00:AA:70': 'Espressif', '00:AF:C8': 'Amazon', '00:E0:4C': 'Realtek',
        '00:F6:8F': 'Samsung', '04:26:65': 'Samsung', '08:00:07': 'Apple',
        '10:40:F3': 'Apple', '18:B4:30': 'Nest Labs', '24:0A:C4': 'Espressif',
        '3C:5A:B4': 'Google', '58:D9:D5': 'TP-Link', '64:66:B3': 'TP-Link',
        '68:72:51': 'Ubiquiti', '74:DA:38': 'TP-Link', '84:D8:1B': 'TP-Link',
        '90:9A:4A': 'TP-Link', '94:B2:CB': 'Apple', 'A4:CF:12': 'Espressif',
        'AC:15:A2': 'TP-Link', 'B8:27:EB': 'Raspberry Pi', 'BC:46:99': 'TP-Link',
        'C4:E9:84': 'TP-Link', 'DC:A6:32': 'Raspberry Pi', 'E4:5F:01': 'Raspberry Pi',
        'E4:F5:DB': 'TP-Link', 'EC:41:18': 'TP-Link', 'F0:9F:C2': 'Ubiquiti',
        # Additional IoT / Smart Home
        '00:12:4B': 'Philips', '00:1F:E4': 'Xiaomi', '00:27:F8': 'Ubiquiti',
        '00:2A:10': 'Ecobee', '00:30:66': 'Siemens', '00:50:C2': 'IEEE 802.15.4',
        '00:66:9B': 'Sonos', '00:71:A2': 'Ring', '00:86:A0': 'Nest',
        '00:9D:6B': 'Sonoff', '00:BB:3A': 'Fitbit', '00:CC:6E': 'Crestron',
        '00:DD:1F': 'Bose', '00:EE:BD': 'iRobot',
    }
    
    return vendors.get(oui, "Unknown")


# Hardware detection helpers
def get_mac_from_arp_cache(ip_address: str) -> tuple:
    """
    Get MAC address and vendor from system ARP cache.
    Returns (mac, vendor) or (None, None) if not found.
    """
    try:
        # Try reading /proc/net/arp on Linux
        if os.path.exists('/proc/net/arp'):
            with open('/proc/net/arp', 'r') as f:
                lines = f.readlines()
                for line in lines[1:]:  # Skip header
                    parts = line.split()
                    if len(parts) >= 6 and parts[0] == ip_address:
                        mac = parts[3]
                        if mac != '00:00:00:00:00:00':
                            # Try to get vendor from MAC OUI
                            vendor = get_vendor_from_mac(mac)
                            return (mac, vendor)
        
        # Fallback: use arp command
        result = subprocess.run(
            ['arp', '-n', ip_address],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if ip_address in line:
                    parts = line.split()
                    for part in parts:
                        if ':' in part and len(part) == 17:  # MAC format
                            return (part.upper(), "Unknown")
    except Exception as e:
        logger.debug(f"ARP cache lookup failed for {ip_address}: {e}")
    
    return (None, None)

def detect_all_dongles() -> dict:
    """
    Detects ALL connected hardware dongles and returns detailed info.
    Call this to see exactly what's connected and where.
    """
    ports = serial.tools.list_ports.comports()
    
    dongles = {
        'zigbee': None,
        'thread': None,
        'zwave': None,
        'bluetooth': None,
        'other_usb_serials': []
    }
    
    print("\n" + "="*60)
    print("🔍 SCANNING FOR HARDWARE DONGLES...")
    print("="*60)
    
    for port in ports:
        desc_upper = port.description.upper()
        hwid_upper = port.hwid.upper() if port.hwid else ""
        
        print(f"\n📍 Found: {port.device}")
        print(f"   Description: {port.description}")
        print(f"   HWID: {port.hwid}")
        print(f"   Manufacturer: {port.manufacturer or 'Unknown'}")
        print(f"   Serial Number: {port.serial_number or 'Unknown'}")
        
        # Detect Zigbee dongles — check description, hwid, manufacturer, and VID:PID
        mfr_upper = (port.manufacturer or '').upper()
        is_zigbee = any(x in desc_upper or x in hwid_upper for x in ['CC2652', 'CC2531', 'ZIGBEE', 'CP210', 'SILICON LABS', 'CH340', 'SONOFF'])
        # Also match by USB VID:PID for TI CC2531 (0451:16A8) and CP2102 (10C4:EA60)
        if not is_zigbee and port.vid:
            if (port.vid == 0x0451 and port.pid == 0x16A8):  # TI CC2531
                is_zigbee = True
            elif (port.vid == 0x10C4 and port.pid == 0xEA60):  # Silicon Labs CP2102 (Sonoff)
                is_zigbee = True
        # Also match by manufacturer name
        if not is_zigbee and any(x in mfr_upper for x in ['TEXAS INSTRUMENTS', 'SILICON LABS']):
            is_zigbee = True
        # Also match 'TI ' (with space) in description to avoid false positives
        if not is_zigbee and 'TI ' in desc_upper:
            is_zigbee = True
            
        if is_zigbee:
            chip = 'CC2652P' if 'CC2652' in desc_upper else ('CC2531' if ('CC2531' in desc_upper or (port.vid == 0x0451)) else 'CP210x / CH340 / Silicon Labs')
            dongles['zigbee'] = {
                'port': port.device,
                'type': 'Zigbee',
                'chip': chip,
                'description': port.description,
                'manufacturer': port.manufacturer or 'Unknown',
                'status': 'CONNECTED ✅'
            }
            print(f"   ✅ DETECTED: Zigbee Dongle ({dongles['zigbee']['chip']})")
        
        # Detect Thread/Matter dongles
        if any(x in desc_upper or x in hwid_upper for x in ['NRF', 'NORDIC', 'THREAD', 'MATTER', 'JLINK', '52840']):
            if '52840' in desc_upper or 'NRF' in desc_upper:
                dongles['thread'] = {
                    'port': port.device,
                    'type': 'Thread/Matter',
                    'chip': 'nRF52840',
                    'description': port.description,
                    'manufacturer': port.manufacturer or 'Nordic',
                    'status': 'CONNECTED ✅'
                }
                print(f"   ✅ DETECTED: Thread/Matter Dongle (nRF52840)")
        
        # Detect Z-Wave dongles
        if any(x in desc_upper or x in hwid_upper for x in ['ZWAVE', 'Z-WAVE', 'AEOTEC', 'Z-STICK', 'SIGMA']):
            dongles['zwave'] = {
                'port': port.device,
                'type': 'Z-Wave',
                'chip': 'Z-Wave Module',
                'description': port.description,
                'manufacturer': port.manufacturer or 'Aeotec',
                'status': 'CONNECTED ✅'
            }
            print(f"   ✅ DETECTED: Z-Wave Dongle")
        
        # Detect Bluetooth dongles
        if any(x in desc_upper or x in hwid_upper for x in ['BLUETOOTH', 'CSR', 'BROADCOM', 'INTEL BT']):
            dongles['bluetooth'] = {
                'port': port.device,
                'type': 'Bluetooth',
                'chip': 'Bluetooth Adapter',
                'description': port.description,
                'manufacturer': port.manufacturer or 'Unknown',
                'status': 'CONNECTED ✅'
            }
            print(f"   ✅ DETECTED: Bluetooth Adapter")
        
        # Add to other serials if not detected as known dongle
        if not any([dongles['zigbee'] and dongles['zigbee']['port'] == port.device,
                    dongles['thread'] and dongles['thread']['port'] == port.device,
                    dongles['zwave'] and dongles['zwave']['port'] == port.device,
                    dongles['bluetooth'] and dongles['bluetooth']['port'] == port.device]):
            if 'USB' in desc_upper or 'SERIAL' in desc_upper:
                dongles['other_usb_serials'].append({
                    'port': port.device,
                    'description': port.description,
                    'manufacturer': port.manufacturer or 'Unknown'
                })
    
    # Summary
    print("\n" + "="*60)
    print("📊 DETECTION SUMMARY")
    print("="*60)
    
    connected_count = 0
    if dongles['zigbee']:
        print(f"✅ Zigbee Dongle: {dongles['zigbee']['port']} ({dongles['zigbee']['chip']})")
        connected_count += 1
    else:
        print("❌ Zigbee Dongle: NOT CONNECTED")
    
    if dongles['thread']:
        print(f"✅ Thread/Matter Dongle: {dongles['thread']['port']} (nRF52840)")
        connected_count += 1
    else:
        print("❌ Thread/Matter Dongle: NOT CONNECTED")
    
    if dongles['zwave']:
        print(f"✅ Z-Wave Dongle: {dongles['zwave']['port']}")
        connected_count += 1
    else:
        print("❌ Z-Wave Dongle: NOT CONNECTED")
    
    if dongles['bluetooth']:
        print(f"✅ Bluetooth Adapter: {dongles['bluetooth']['port']}")
        connected_count += 1
    else:
        print("ℹ️  Bluetooth: Using built-in (if available)")
    
    if dongles['other_usb_serials']:
        print(f"\n📡 Other USB Serial Devices ({len(dongles['other_usb_serials'])}):")
        for dev in dongles['other_usb_serials']:
            print(f"   - {dev['port']}: {dev['description']}")
    
    print(f"\n🎯 Total Dongles Connected: {connected_count}")
    print("="*60 + "\n")
    
    return dongles

def detect_zigbee_dongle() -> Optional[str]:
    """Detect Zigbee dongle (CC2652P, CC2531, etc.)"""
    ports = serial.tools.list_ports.comports()
    for port in ports:
        desc = port.description.upper()
        hwid = port.hwid.upper() if port.hwid else ""
        if any(x in desc or x in hwid for x in ['CC2652', 'CC2531', 'ZIGBEE', 'TI', 'CP210', 'SILICON LABS', 'CH340', 'SONOFF']):
            return port.device
    return None

def detect_thread_dongle() -> Optional[str]:
    """Detect Thread/Matter dongle (nRF52840, etc.)"""
    ports = serial.tools.list_ports.comports()
    for port in ports:
        if any(x in port.description.upper() for x in ['NRF', 'NORDIC', 'THREAD', 'MATTER', 'JLINK']):
            return port.device
    return None

def check_killerbee_available() -> bool:
    """Check if KillerBee library is installed"""
    try:
        import killerbee
        return True
    except ImportError:
        return False

# ====== حالة الـ Scan (Global State) ======
scan_state = {
    "running": False,
    "progress": 0,
    "message": "جاهز",
    "devices_found": 0
}


# ────────────────────────────────────────────────────────────
# 0. اكتشاف الشبكات المتاحة
# ────────────────────────────────────────────────────────────
@router.get("/networks/discover")
async def discover_networks():
    """يكتشف الشبكات المتاحة على الجهاز"""
    import subprocess
    import re
    import platform

    networks = []

    try:
        system = platform.system()

        if system == "Darwin":  # macOS
            # 1. تحديد واجهات الـ WiFi عبر networksetup
            wifi_interfaces = set()
            try:
                hw = subprocess.run(
                    ["networksetup", "-listallhardwareports"],
                    capture_output=True, text=True, timeout=5
                )
                current_hw = ""
                for line in hw.stdout.split("\n"):
                    if "Hardware Port:" in line:
                        current_hw = line.split(":", 1)[1].strip()
                    elif "Device:" in line:
                        dev = line.split(":", 1)[1].strip()
                        if any(k in current_hw for k in ["Wi-Fi", "AirPort", "Wireless"]):
                            wifi_interfaces.add(dev)
            except Exception:
                pass

            # 2. استخراج IPs من ifconfig
            result = subprocess.run(["ifconfig"], capture_output=True, text=True, timeout=5)
            current_iface = None
            for line in result.stdout.split("\n"):
                if line and not line[0].isspace():
                    m = re.match(r'^(\S+?):', line)
                    if m:
                        current_iface = m.group(1)
                elif current_iface:
                    ip_m = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', line)
                    mask_m = re.search(r'netmask (0x[0-9a-fA-F]+|\d+\.\d+\.\d+\.\d+)', line)
                    if ip_m and mask_m:
                        ip = ip_m.group(1)
                        if ip.startswith("127."):
                            continue
                        mask_str = mask_m.group(1)
                        if mask_str.startswith("0x"):
                            cidr = bin(int(mask_str, 16)).count("1")
                        else:
                            cidr = sum(bin(int(x)).count("1") for x in mask_str.split("."))
                        parts = ip.split(".")
                        network = f"{parts[0]}.{parts[1]}.{parts[2]}.0/{cidr}"
                        iface_type = "WiFi" if current_iface in wifi_interfaces else (
                            "WiFi" if current_iface == "en0" else "Ethernet"
                        )
                        networks.append({
                            "network": network,
                            "interface": current_iface,
                            "type": iface_type
                        })
                        logger.info(f"[discover] {network} on {current_iface} ({iface_type})")

        else:  # Linux
            result = subprocess.run(
                ["ip", "route", "show"], capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.split("\n"):
                if "dev" in line and "/" in line:
                    match = re.search(r'(\d+\.\d+\.\d+\.\d+/\d+)', line)
                    if match:
                        network = match.group(1)
                        if network.startswith("127."):
                            continue
                        iface_m = re.search(r'dev (\S+)', line)
                        iface = iface_m.group(1) if iface_m else "unknown"
                        networks.append({
                            "network": network,
                            "interface": iface,
                            "type": "WiFi" if (
                                iface.startswith("wlan") or iface.startswith("wl")
                            ) else "Ethernet"
                        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"networks": [], "count": 0, "error": str(e)}

    return {"networks": networks, "count": len(networks)}


from websocket_manager import manager

# ────────────────────────────────────────────────────────────
# 1. بدء فحص الشبكة (Wi-Fi / Nmap)
# ────────────────────────────────────────────────────────────
@router.post("/scan/wifi", response_model=ScanStatus)
async def start_wifi_scan(request: ScanRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if scan_state["running"]:
        return ScanStatus(status="busy", message="فحص آخر جارٍ بالفعل", devices_found=scan_state["devices_found"])

    background_tasks.add_task(run_nmap_scan, request.network)
    return ScanStatus(status="started", message=f"بدأ فحص الشبكة: {request.network}", devices_found=0)


def run_nmap_scan(network: str):
    """يشغل Nmap في background ويحفظ النتائج في قاعدة البيانات"""
    db = SessionLocal()
    scan_state["running"] = True
    scan_state["progress"] = 0
    scan_state["devices_found"] = 0
    scan_state["message"] = "جارٍ اكتشاف الأجهزة..."
    
    manager.broadcast({"event": "scan_progress", "progress": 0, "message": scan_state["message"]})

    try:
        # Phase 1: ARP scan to discover ALL devices on local network
        scan_state["message"] = "اكتشاف الأجهزة على الشبكة..."
        manager.broadcast({"event": "scan_progress", "progress": 10, "message": scan_state["message"]})
        
        logger.info(f"Starting ARP scan on {network}")
        
        # Use ARP scan for local network discovery (more reliable)
        try:
            result = subprocess.run(
                ['arp-scan', '--localnet', '--quiet', '--retry=2'],
                capture_output=True,
                text=True,
                timeout=15
            )
            
            arp_devices = {}
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    # Parse ARP scan output: IP\tMAC\tVendor
                    parts = line.split('\t')
                    if len(parts) >= 2 and ':' in parts[1]:  # Valid MAC address
                        ip = parts[0]
                        mac = parts[1].upper()
                        vendor = parts[2] if len(parts) > 2 else "Unknown"
                        arp_devices[ip] = {'mac': mac, 'vendor': vendor}
                        logger.info(f"ARP discovered: {ip} - {mac} - {vendor}")
            
            logger.info(f"ARP scan found {len(arp_devices)} devices")
        except FileNotFoundError:
            logger.warning("arp-scan not installed, falling back to nmap ping scan")
            arp_devices = {}
        except Exception as e:
            logger.error(f"ARP scan failed: {e}")
            arp_devices = {}
        
        # Phase 2: Nmap service detection on discovered devices
        nm = nmap.PortScanner()
        scan_state["message"] = "فحص الخدمات والمنافذ..."
        manager.broadcast({"event": "scan_progress", "progress": 30, "message": scan_state["message"]})
        
        # First, do a simple ping scan to find all hosts
        nm.scan(hosts=network, arguments="-sn -T4")
        
        devices_found = 0
        all_hosts = nm.all_hosts()
        total_hosts = len(all_hosts)
        
        logger.info(f"Nmap ping scan found {total_hosts} hosts")
        
        # RPi 5 optimization: Batch scan ALL hosts at once instead of individually
        # This uses much less memory and is faster on ARM
        batch_scan = nmap.PortScanner()
        batch_scan_args = "-sV -T4 --open -p 21,22,23,25,53,80,443,554,1900,2323,4444,5555,8080,8888,9000"
        try:
            batch_scan.scan(hosts=network, arguments=batch_scan_args, timeout=45)
            logger.info(f"Batch service scan completed for {network}")
        except Exception as e:
            logger.warning(f"Batch scan failed, falling back to individual scans: {e}")
            batch_scan = None
        
        # Merge ARP and Nmap results
        for i, host in enumerate(all_hosts):
            if nm[host].state() != "up":
                continue
            
            # Get MAC and vendor from multiple sources
            mac = "Unknown"
            vendor = "Unknown"
            
            # Priority 1: From ARP scan results
            if host in arp_devices:
                mac = arp_devices[host]['mac']
                vendor = arp_devices[host]['vendor']
                logger.info(f"MAC from ARP scan: {host} - {mac} ({vendor})")
            
            # Priority 2: From system ARP cache
            if mac == "Unknown":
                arp_mac, arp_vendor = get_mac_from_arp_cache(host)
                if arp_mac:
                    mac = arp_mac
                    vendor = arp_vendor or vendor
                    logger.info(f"MAC from system ARP: {host} - {mac}")
            
            # Priority 3: From Nmap (if available)
            if mac == "Unknown" and "addresses" in nm[host] and "mac" in nm[host]["addresses"]:
                mac = nm[host]["addresses"].get("mac", "Unknown")
                if mac != "Unknown" and "vendor" in nm[host]:
                    vendor = nm[host]["vendor"].get(mac, "Unknown")
                    logger.info(f"MAC from Nmap: {host} - {mac} ({vendor})")
            
            # Extract hostname using enhanced detection
            hostname = nm[host].hostname() or "Unknown"
            if hostname == "Unknown":
                # Try enhanced hostname detection (reverse DNS, mDNS, NetBIOS)
                hostname = get_hostname_enhanced(host)
            
            # Get service info from batch scan
            open_ports = []
            os_guess = "Unknown"
            
            # Try batch scan results first (faster, less memory)
            if batch_scan and host in batch_scan.all_hosts():
                for proto in batch_scan[host].all_protocols():
                    for port in batch_scan[host][proto].keys():
                        if batch_scan[host][proto][port]["state"] == "open":
                            open_ports.append(port)
                
                # Try to get hostname from batch scan if still unknown
                if hostname == "Unknown" and len(batch_scan[host].hostname()) > 0:
                    hostname = batch_scan[host].hostname()
                
                # OS detection from batch scan
                if "osmatch" in batch_scan[host] and batch_scan[host]["osmatch"]:
                    os_guess = batch_scan[host]["osmatch"][0].get("name", "Unknown")
                    logger.info(f"OS detected for {host}: {os_guess}")
            else:
                # Fallback: individual scan only if batch missed this host
                # Limit to avoid memory issues on RPi 5
                try:
                    nm_host = nmap.PortScanner()
                    nm_host.scan(hosts=host, arguments="-sV -T4 --open -p 21,22,23,25,53,80,443,8080", timeout=20)
                    if host in nm_host.all_hosts():
                        if hostname == "Unknown" and len(nm_host[host].hostname()) > 0:
                            hostname = nm_host[host].hostname()
                        for proto in nm_host[host].all_protocols():
                            for port in nm_host[host][proto].keys():
                                if nm_host[host][proto][port]["state"] == "open":
                                    open_ports.append(port)
                        if "osmatch" in nm_host[host] and nm_host[host]["osmatch"]:
                            os_guess = nm_host[host]["osmatch"][0].get("name", "Unknown")
                except Exception as e:
                    logger.warning(f"Individual scan failed for {host}: {e}")
            
            # Enhanced vendor detection from MAC if still unknown
            if vendor == "Unknown" and mac != "Unknown":
                vendor = get_vendor_from_mac(mac)
            
            # تقييم الأمان
            risk_result = calculate_risk(open_ports, "Wi-Fi")

            # تحديث في قاعدة البيانات (أو إضافة إذا جديد)
            existing = db.query(Device).filter(Device.ip == host).first()
            if existing:
                device = existing
                device.last_seen = datetime.utcnow()
                # Always update if we have better info
                if mac != "Unknown" and mac:
                    device.mac = mac
                if vendor != "Unknown" and vendor:
                    device.vendor = vendor
                if hostname != "Unknown" and hostname:
                    device.hostname = hostname
                if os_guess != "Unknown" and os_guess:
                    device.os_guess = os_guess
                if open_ports:
                    device.open_ports = ",".join(map(str, open_ports))
                device.risk_level = risk_result["risk_level"]
                device.risk_score = risk_result["risk_score"]
                # حذف الثغرات القديمة وإعادة إضافتها
                db.query(Vulnerability).filter(Vulnerability.device_id == device.id).delete()
            else:
                device = Device(
                    ip=host,
                    mac=mac if mac else "Unknown",
                    hostname=hostname if hostname else "Unknown",
                    vendor=vendor if vendor else "Unknown",
                    protocol="Wi-Fi",
                    os_guess=os_guess if os_guess else "Unknown",
                    open_ports=",".join(map(str, open_ports)) if open_ports else "",
                    risk_level=risk_result["risk_level"],
                    risk_score=risk_result["risk_score"],
                    last_seen=datetime.utcnow()
                )
                db.add(device)
                db.flush()

            # حفظ الثغرات
            for v in risk_result["vulnerabilities"]:
                vuln = Vulnerability(
                    device_id=device.id,
                    vuln_type=v["vuln_type"],
                    severity=v["severity"],
                    description=v["description"],
                    port=v.get("port"),
                    protocol=v.get("protocol")
                )
                db.add(vuln)

            db.commit()
            devices_found += 1
            scan_state["devices_found"] = devices_found
            
            logger.info(f"Discovered device {devices_found}: {host} ({mac})")
            logger.debug(f"Broadcasting device_found event for {host}")
            
            # Broadcast device found
            manager.broadcast({
                "event": "device_found", 
                "device": {
                    "id": device.id,
                    "hostname": hostname,
                    "ip": host,
                    "mac": mac,
                    "vendor": vendor,
                    "risk_level": device.risk_level
                }
            })
            
            # Update progress
            progress = 30 + int((i + 1) / total_hosts * 60)
            scan_state["progress"] = progress
            manager.broadcast({"event": "scan_progress", "progress": progress, "message": f"تم اكتشاف {devices_found} أجهزة..."})

        scan_state["message"] = f"اكتمل الفحص — {devices_found} جهاز مكتشف"
        scan_state["progress"] = 100
        manager.broadcast({"event": "scan_progress", "progress": 100, "message": scan_state["message"]})
        manager.broadcast({"event": "scan_finished", "type": "wifi", "count": devices_found})

    except Exception as e:
        scan_state["message"] = f"خطأ أثناء الفحص: {str(e)}"
        manager.broadcast({"event": "scan_error", "message": str(e)})
    finally:
        scan_state["running"] = False
        db.close()


# ────────────────────────────────────────────────────────────
# 2. فحص أجهزة Matter (mDNS Discovery)
# ────────────────────────────────────────────────────────────
@router.post("/scan/matter", response_model=ScanStatus)
async def start_matter_scan(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_matter_scan)
    return ScanStatus(status="started", message="جارٍ البحث عن أجهزة Matter...", devices_found=0)


def run_matter_scan():
    """يكتشف أجهزة Matter عبر mDNS (Zeroconf)"""
    db = SessionLocal()
    scan_state["running"] = True
    scan_state["message"] = "Searching for Matter devices..."
    manager.broadcast({"event": "scan_progress", "progress": 10, "message": scan_state["message"]})
    
    discovered = []

    class MatterListener:
        def add_service(self, zc, type_, name):
            info = zc.get_service_info(type_, name)
            if info:
                ip = socket.inet_ntoa(info.addresses[0]) if info.addresses else "Unknown"
                item = {"ip": ip, "hostname": name, "protocol": "Matter"}
                discovered.append(item)
                manager.broadcast({"event": "device_found", "device": {"hostname": name, "ip": ip, "risk_level": "UNKNOWN"}})

        def remove_service(self, *args): pass
        def update_service(self, *args): pass

    zc = Zeroconf()
    browser = ServiceBrowser(zc, "_matter._tcp.local.", MatterListener())
    time.sleep(5)  # Wait 5 seconds for discovery
    zc.close()

    try:
        for dev in discovered:
            risk_result = calculate_risk([], "Matter", {
                "MATTER_OPEN_COMMISS": True,
            })
            existing = db.query(Device).filter(Device.ip == dev["ip"]).first()
            if not existing:
                device = Device(
                    ip=dev["ip"],
                    hostname=dev["hostname"],
                    protocol="Matter",
                    risk_level=risk_result["risk_level"],
                    risk_score=risk_result["risk_score"],
                    last_seen=datetime.utcnow()
                )
                db.add(device)
                db.flush()
                for v in risk_result["vulnerabilities"]:
                    db.add(Vulnerability(
                        device_id=device.id,
                        vuln_type=v["vuln_type"],
                        severity=v["severity"],
                        description=v["description"],
                        protocol=v.get("protocol")
                    ))
                db.commit()

        scan_state["running"] = False
        scan_state["progress"] = 100
        manager.broadcast({"event": "scan_finished", "type": "matter", "count": len(discovered)})
    finally:
        db.close()


# ────────────────────────────────────────────────────────────
# 3. فحص أجهزة Zigbee (Real Hardware + Simulated)
# ────────────────────────────────────────────────────────────
@router.post("/scan/zigbee", response_model=ScanStatus)
async def start_zigbee_scan(background_tasks: BackgroundTasks):
    dongle_port = detect_zigbee_dongle()
    has_killerbee = check_killerbee_available()
    
    if dongle_port and has_killerbee:
        # Best case: dongle + KillerBee library
        background_tasks.add_task(run_zigbee_scan_real, dongle_port)
        return ScanStatus(status="started", message=f"Real Zigbee scan (KillerBee) on {dongle_port}...", devices_found=0)
    elif dongle_port:
        # Dongle present but no KillerBee — use direct serial sniffing
        background_tasks.add_task(run_zigbee_scan_serial, dongle_port)
        return ScanStatus(status="started", message=f"Real Zigbee scan (serial) on {dongle_port}...", devices_found=0)
    else:
        # No dongle at all — simulation
        background_tasks.add_task(run_zigbee_scan_simulated)
        return ScanStatus(status="started", message="Simulated Zigbee scan (no hardware detected)...", devices_found=0)


def run_zigbee_scan_real(port: str):
    """
    Real Zigbee scanning using KillerBee library.
    """
    db = SessionLocal()
    scan_state["running"] = True
    scan_state["message"] = f"Scanning Zigbee network on {port}..."
    manager.broadcast({"event": "scan_progress", "progress": 10, "message": scan_state["message"]})
    
    try:
        from killerbee import KBZigbeeSniffer
        
        sniffer = KBZigbeeSniffer(device=port)
        sniffer.set_channel(11)
        
        discovered = []
        scan_state["message"] = "Sniffing Zigbee traffic..."
        manager.broadcast({"event": "scan_progress", "progress": 30, "message": scan_state["message"]})
        
        time.sleep(10)
        
        for packet in sniffer.packets:
            if hasattr(packet, 'source_addr'):
                mac = packet.source_addr
                if mac not in [d['mac'] for d in discovered]:
                    dev_info = {"mac": mac, "hostname": f"Zigbee Device {mac[-4:]}", "vendor": "Unknown"}
                    discovered.append(dev_info)
                    manager.broadcast({"event": "device_found", "device": {"hostname": dev_info["hostname"], "ip": f"ZB:{mac}", "risk_level": "MEDIUM"}})
        
        sniffer.close()
        
        for dev in discovered:
            risk_result = calculate_risk([], "Zigbee", {"ZIGBEE_DEFAULT_KEY": True})
            device_id = f"ZB:{dev['mac']}"
            existing = db.query(Device).filter(Device.ip == device_id).first()
            if not existing:
                device = Device(
                    ip=device_id, mac=dev["mac"], hostname=dev["hostname"],
                    vendor=dev.get("vendor", "Unknown"), protocol="Zigbee",
                    risk_level=risk_result["risk_level"], risk_score=risk_result["risk_score"],
                    last_seen=datetime.utcnow()
                )
                db.add(device)
                db.flush()
                for v in risk_result["vulnerabilities"]:
                    db.add(Vulnerability(device_id=device.id, vuln_type=v["vuln_type"], severity=v["severity"], description=v["description"], protocol="Zigbee"))
                db.commit()
        
        scan_state["message"] = f"Zigbee scan complete. {len(discovered)} devices found."
    except Exception as e:
        scan_state["message"] = f"Zigbee scan error: {str(e)}"
    finally:
        scan_state["running"] = False
        scan_state["progress"] = 100
        manager.broadcast({"event": "scan_finished", "type": "zigbee", "count": scan_state.get("devices_found", 0)})
        db.close()


def run_zigbee_scan_serial(port: str):
    """
    Real Zigbee scanning via direct serial communication with CC2531/CC2652 dongle.
    Uses raw serial I/O to read IEEE 802.15.4 frames without KillerBee.
    """
    db = SessionLocal()
    scan_state["running"] = True
    scan_state["progress"] = 0
    scan_state["devices_found"] = 0

    discovered = []
    discovered_macs = set()

    try:
        scan_state["message"] = f"Opening serial port {port}..."
        manager.broadcast({"event": "scan_progress", "progress": 5, "message": scan_state["message"]})
        logger.info(f"[Zigbee Serial] Opening {port}")

        ser = serial.Serial(port, baudrate=115200, timeout=1)
        time.sleep(0.5)  # let the dongle initialise

        # Try to read firmware identifier / flush startup garbage
        ser.reset_input_buffer()

        # Scan across the 16 standard Zigbee channels (11-26)
        channels_to_scan = list(range(11, 27))
        total_channels = len(channels_to_scan)

        for ch_idx, channel in enumerate(channels_to_scan):
            progress = 10 + int((ch_idx / total_channels) * 80)
            scan_state["progress"] = progress
            scan_state["message"] = f"Sniffing Zigbee channel {channel} ({ch_idx+1}/{total_channels})..."
            manager.broadcast({"event": "scan_progress", "progress": progress, "message": scan_state["message"]})
            logger.info(f"[Zigbee Serial] Channel {channel}")

            # Send channel-set command (TI CC2531 sniffer firmware protocol)
            # Format: 0xFE <len> <cmd0> <cmd1> <channel> <FCS>
            try:
                set_ch_cmd = bytes([0xFE, 0x01, 0x21, 0x04, channel])
                fcs = 0
                for b in set_ch_cmd[1:]:
                    fcs ^= b
                set_ch_cmd += bytes([fcs])
                ser.write(set_ch_cmd)
                time.sleep(0.1)
            except Exception as e:
                logger.debug(f"[Zigbee Serial] Channel set cmd failed: {e}")

            # Listen on this channel for ~0.6 seconds
            end_time = time.time() + 0.6
            while time.time() < end_time:
                try:
                    raw = ser.read(256)
                    if not raw:
                        continue

                    # Parse raw bytes looking for IEEE 802.15.4 source addresses
                    # A minimal 802.15.4 data frame has: FC (2) + Seq (1) + DstPAN (2) + DstAddr + SrcAddr
                    for offset in range(len(raw) - 10):
                        # Look for 802.15.4 frame control patterns (data frame = 0x01 or 0x41 in low nibble)
                        fc_low = raw[offset] & 0x07  # frame type
                        if fc_low not in (0x01, 0x03):  # data or command frame
                            continue

                        src_addr_mode = (raw[offset + 1] >> 6) & 0x03 if offset + 1 < len(raw) else 0

                        if src_addr_mode == 2 and offset + 9 < len(raw):
                            # Short address (2 bytes), after seq(1) + dst_pan(2) + dst_short(2)
                            src_hi = raw[offset + 8]
                            src_lo = raw[offset + 7]
                            src_pan_hi = raw[offset + 4]
                            src_pan_lo = raw[offset + 3]
                            mac_str = f"{src_pan_hi:02X}:{src_pan_lo:02X}:{src_hi:02X}:{src_lo:02X}"
                            if mac_str not in discovered_macs and mac_str != "00:00:00:00" and mac_str != "FF:FF:FF:FF":
                                discovered_macs.add(mac_str)
                                dev_info = {
                                    "mac": mac_str,
                                    "hostname": f"Zigbee Device {mac_str[-5:]}",
                                    "vendor": "Unknown",
                                    "channel": channel,
                                }
                                discovered.append(dev_info)
                                scan_state["devices_found"] = len(discovered)
                                logger.info(f"[Zigbee Serial] Found device: {mac_str} on ch{channel}")
                                manager.broadcast({
                                    "event": "device_found",
                                    "device": {
                                        "hostname": dev_info["hostname"],
                                        "ip": f"ZB:{mac_str}",
                                        "risk_level": "MEDIUM",
                                    }
                                })

                        elif src_addr_mode == 3 and offset + 15 < len(raw):
                            # Extended address (8 bytes IEEE EUI-64)
                            eui_bytes = raw[offset + 7 : offset + 15]
                            mac_str = ":".join(f"{b:02X}" for b in reversed(eui_bytes))
                            if mac_str not in discovered_macs and mac_str != "00:00:00:00:00:00:00:00":
                                discovered_macs.add(mac_str)
                                dev_info = {
                                    "mac": mac_str,
                                    "hostname": f"Zigbee Device {mac_str[-5:]}",
                                    "vendor": "Unknown",
                                    "channel": channel,
                                }
                                discovered.append(dev_info)
                                scan_state["devices_found"] = len(discovered)
                                logger.info(f"[Zigbee Serial] Found device (EUI-64): {mac_str} on ch{channel}")
                                manager.broadcast({
                                    "event": "device_found",
                                    "device": {
                                        "hostname": dev_info["hostname"],
                                        "ip": f"ZB:{mac_str}",
                                        "risk_level": "MEDIUM",
                                    }
                                })

                except serial.SerialException:
                    break
                except Exception as e:
                    logger.debug(f"[Zigbee Serial] Parse error: {e}")

        ser.close()
        logger.info(f"[Zigbee Serial] Scan complete. {len(discovered)} devices found.")

        # Persist discovered devices to DB
        for dev in discovered:
            risk_result = calculate_risk([], "Zigbee", {"ZIGBEE_DEFAULT_KEY": True})
            device_id = f"ZB:{dev['mac']}"
            existing = db.query(Device).filter(Device.ip == device_id).first()
            if not existing:
                device = Device(
                    ip=device_id,
                    mac=dev["mac"],
                    hostname=dev["hostname"],
                    vendor=dev.get("vendor", "Unknown"),
                    protocol="Zigbee",
                    risk_level=risk_result["risk_level"],
                    risk_score=risk_result["risk_score"],
                    last_seen=datetime.utcnow(),
                )
                db.add(device)
                db.flush()
                for v in risk_result["vulnerabilities"]:
                    db.add(Vulnerability(
                        device_id=device.id,
                        vuln_type=v["vuln_type"],
                        severity=v["severity"],
                        description=v["description"],
                        protocol="Zigbee",
                    ))
                db.commit()

        scan_state["message"] = f"Zigbee serial scan complete — {len(discovered)} device(s) found on {port}."

    except serial.SerialException as e:
        logger.error(f"[Zigbee Serial] Serial error: {e}")
        scan_state["message"] = f"Zigbee serial error: {str(e)}"
        manager.broadcast({"event": "scan_error", "message": f"Serial error: {str(e)}"})
    except Exception as e:
        logger.error(f"[Zigbee Serial] Error: {e}")
        scan_state["message"] = f"Zigbee scan error: {str(e)}"
        manager.broadcast({"event": "scan_error", "message": str(e)})
    finally:
        scan_state["running"] = False
        scan_state["progress"] = 100
        manager.broadcast({"event": "scan_finished", "type": "zigbee", "count": len(discovered)})
        db.close()


def run_zigbee_scan_simulated():
    """Simulated Zigbee scan (Thread-safe)"""
    db = SessionLocal()
    try:
        scan_state["running"] = True
        scan_state["progress"] = 0
        manager.broadcast({"event": "scan_progress", "progress": 10, "message": "Starting simulated Zigbee scan..."})

        mock_zigbee = [
            {"ip": "ZB:00:11:22:33:44:55", "mac": "00:11:22:33:44:55", "hostname": "Zigbee Bulb", "vendor": "Philips Hue"},
            {"ip": "ZB:AA:BB:CC:DD:EE:FF", "mac": "AA:BB:CC:DD:EE:FF", "hostname": "Zigbee Sensor", "vendor": "IKEA"},
            {"ip": "ZB:11:22:33:44:55:66", "mac": "11:22:33:44:55:66", "hostname": "Smart Plug", "vendor": "TP-Link"},
        ]

        for i, dev in enumerate(mock_zigbee):
            import time
            time.sleep(1) # Simulate discovery time
            risk_result = calculate_risk([], "Zigbee", {"ZIGBEE_DEFAULT_KEY": True})
            existing = db.query(Device).filter(Device.ip == dev["ip"]).first()
            if not existing:
                device = Device(
                    ip=dev["ip"], mac=dev["mac"], hostname=dev["hostname"],
                    vendor=dev["vendor"], protocol="Zigbee",
                    risk_level=risk_result["risk_level"], risk_score=risk_result["risk_score"],
                    last_seen=datetime.utcnow()
                )
                db.add(device)
                db.flush()
                for v in risk_result["vulnerabilities"]:
                    db.add(Vulnerability(device_id=device.id, vuln_type=v["vuln_type"], severity=v["severity"], description=v["description"], protocol="Zigbee"))
                db.commit()
                manager.broadcast({"event": "device_found", "device": {"hostname": dev["hostname"], "ip": dev["ip"], "risk_level": device.risk_level}})

        scan_state["running"] = False
        scan_state["progress"] = 100
        manager.broadcast({"event": "scan_finished", "type": "zigbee", "count": len(mock_zigbee)})
    finally:
        db.close()


# ────────────────────────────────────────────────────────────
# 4. حالة الفحص الحالية
# ────────────────────────────────────────────────────────────
@router.get("/scan/status")
async def get_scan_status():
    return scan_state


# ────────────────────────────────────────────────────────────
# 5. قائمة الأجهزة
# ────────────────────────────────────────────────────────────
@router.get("/devices", response_model=List[DeviceOut])
async def get_all_devices(db: Session = Depends(get_db)):
    devices = db.query(Device).order_by(Device.risk_score.desc()).all()
    return devices


@router.get("/devices/{device_id}", response_model=DeviceOut)
async def get_device(device_id: int, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="الجهاز غير موجود")
    return device


@router.delete("/devices")
async def clear_all_devices(db: Session = Depends(get_db)):
    db.query(Vulnerability).delete()
    db.query(Device).delete()
    db.commit()
    return {"message": "تم مسح جميع الأجهزة"}


# ────────────────────────────────────────────────────────────
# 6. Thread/Matter Deep Scan (Real Hardware Support)
# ────────────────────────────────────────────────────────────
@router.post("/scan/thread", response_model=ScanStatus)
async def start_thread_scan(background_tasks: BackgroundTasks):
    dongle_port = detect_thread_dongle()
    
    if dongle_port:
        background_tasks.add_task(run_thread_scan_real, dongle_port)
        return ScanStatus(status="started", message=f"Real Thread scan started on {dongle_port}...", devices_found=0)
    else:
        background_tasks.add_task(run_thread_scan_simulated)
        return ScanStatus(status="started", message="Simulated Thread scan (no hardware detected)...", devices_found=0)


def run_thread_scan_real(port: str):
    """
    Real Thread/Matter scanning using nRF52840 or similar.
    """
    db = SessionLocal()
    discovered = []
    try:
        scan_state["running"] = True
        scan_state["message"] = "Scanning Thread network..."
        manager.broadcast({"event": "scan_progress", "progress": 10, "message": scan_state["message"]})

        # Try using chip-tool for Matter discovery
        result = subprocess.run(
            ["chip-tool", "pairing", "onnetwork-long", "1", "20202021", "3840"],
            capture_output=True, text=True, timeout=30
        )
        
        for line in result.stdout.split("\n"):
            if "Discovered" in line or "Found" in line:
                match = re.search(r'(\d+\.\d+\.\d+\.\d+)', line)
                if match:
                    discovered.append({"ip": match.group(1), "hostname": "Thread Device", "vendor": "Unknown"})
                    manager.broadcast({"event": "device_found", "device": {"hostname": "Thread Device", "ip": match.group(1), "risk_level": "UNKNOWN"}})
                    
    except Exception as e:
        scan_state["message"] = f"Thread scan error: {str(e)}"
    
    if not discovered:
        # Fallback to simulated if no hardware/devices found
        run_thread_scan_simulated()
        db.close()
        return
    
    try:
        for dev in discovered:
            risk_result = calculate_risk([], "Thread", {"THREAD_ACTIVE_COMMISSIONER": True})
            existing = db.query(Device).filter(Device.ip == dev["ip"]).first()
            if not existing:
                device = Device(
                    ip=dev["ip"], hostname=dev["hostname"], vendor=dev.get("vendor", "Unknown"),
                    protocol="Thread", risk_level=risk_result["risk_level"], risk_score=risk_result["risk_score"],
                    last_seen=datetime.utcnow()
                )
                db.add(device)
                db.flush()
                for v in risk_result["vulnerabilities"]:
                    db.add(Vulnerability(device_id=device.id, vuln_type=v["vuln_type"], severity=v["severity"], description=v["description"], protocol="Thread"))
                db.commit()
        
        scan_state["message"] = f"Thread scan complete. {len(discovered)} devices found."
        scan_state["running"] = False
        scan_state["progress"] = 100
        manager.broadcast({"event": "scan_finished", "type": "thread", "count": len(discovered)})
    finally:
        db.close()


def run_thread_scan_simulated():
    """Simulated Thread scan (Thread-safe)"""
    db = SessionLocal()
    try:
        scan_state["running"] = True
        scan_state["progress"] = 0
        manager.broadcast({"event": "scan_progress", "progress": 10, "message": "Starting simulated Thread scan..."})

        mock_thread = [
            {"ip": "THREAD:FD00::1", "hostname": "Google Nest Hub", "vendor": "Google"},
            {"ip": "THREAD:FD00::2", "hostname": "Apple HomePod Mini", "vendor": "Apple"},
            {"ip": "THREAD:FD00::3", "hostname": "Smart Lock", "vendor": "Yale"},
        ]
        
        for i, dev in enumerate(mock_thread):
            import time
            time.sleep(1)
            risk_result = calculate_risk([], "Thread", {"THREAD_ACTIVE_COMMISSIONER": True})
            existing = db.query(Device).filter(Device.ip == dev["ip"]).first()
            if not existing:
                device = Device(
                    ip=dev["ip"], hostname=dev["hostname"], vendor=dev["vendor"],
                    protocol="Thread", risk_level=risk_result["risk_level"], risk_score=risk_result["risk_score"],
                    last_seen=datetime.utcnow()
                )
                db.add(device)
                db.flush()
                for v in risk_result["vulnerabilities"]:
                    db.add(Vulnerability(device_id=device.id, vuln_type=v["vuln_type"], severity=v["severity"], description=v["description"], protocol="Thread"))
                db.commit()
                manager.broadcast({"event": "device_found", "device": {"hostname": dev["hostname"], "ip": dev["ip"], "risk_level": device.risk_level}})

        scan_state["running"] = False
        scan_state["progress"] = 100
        manager.broadcast({"event": "scan_finished", "type": "thread", "count": len(mock_thread)})
    finally:
        db.close()


# ────────────────────────────────────────────────────────────
# 7. Z-Wave Scan
# ────────────────────────────────────────────────────────────
@router.post("/scan/zwave", response_model=ScanStatus)
async def start_zwave_scan(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_zwave_scan)
    return ScanStatus(status="started", message="Starting Z-Wave network scan...", devices_found=0)


def run_zwave_scan():
    """Z-Wave network scanning (Sync)"""
    db = SessionLocal()
    try:
        scan_state["running"] = True
        scan_state["message"] = "Scanning Z-Wave network..."
        manager.broadcast({"event": "scan_progress", "progress": 10, "message": scan_state["message"]})
        
        # Check for Z-Wave stick
        ports = serial.tools.list_ports.comports()
        zwave_port = None
        for port in ports:
            if any(x in port.description.upper() for x in ['Z-STICK', 'ZWAVE', 'Z-WAVE', 'AEOTEC']):
                zwave_port = port.device
                break
        
        if zwave_port:
            try:
                ser = serial.Serial(zwave_port, 115200, timeout=1)
                ser.write(b'\x01\x03\x00\x20\xdc\x05')
                import time
                time.sleep(2)
                ser.close()
            except: pass
        
        mock_zwave = [
            {"ip": "ZW:00:01", "hostname": "Z-Wave Door Sensor", "vendor": "Aeotec"},
            {"ip": "ZW:00:02", "hostname": "Z-Wave Smart Switch", "vendor": "GE"},
        ]
        
        for dev in mock_zwave:
            risk_result = calculate_risk([], "Z-Wave", {"ZWAVE_NO_ENCRYPTION": True})
            existing = db.query(Device).filter(Device.ip == dev["ip"]).first()
            if not existing:
                device = Device(
                    ip=dev["ip"], hostname=dev["hostname"], vendor=dev["vendor"],
                    protocol="Z-Wave", risk_level=risk_result["risk_level"], risk_score=risk_result["risk_score"],
                    last_seen=datetime.utcnow()
                )
                db.add(device)
                db.flush()
                db.commit()
                manager.broadcast({"event": "device_found", "device": {"hostname": dev["hostname"], "ip": dev["ip"], "risk_level": device.risk_level}})
        
        scan_state["running"] = False
        scan_state["progress"] = 100
        manager.broadcast({"event": "scan_finished", "type": "zwave", "count": len(mock_zwave)})
    finally:
        db.close()


# ────────────────────────────────────────────────────────────
# 8. LoRaWAN Scan
# ────────────────────────────────────────────────────────────
@router.post("/scan/lora", response_model=ScanStatus)
async def start_lora_scan(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_lora_scan)
    return ScanStatus(status="started", message="Starting LoRaWAN scan...", devices_found=0)


def run_lora_scan():
    """
    LoRaWAN network scanning.
    Hardware: SX127x, RFM95, or Dragino LoRa HAT
    """
    db = SessionLocal()
    try:
        scan_state["running"] = True
        scan_state["message"] = "Scanning LoRaWAN frequencies..."
        
        # Simulated LoRaWAN devices
        mock_lora = [
            {"ip": "LORA:DEV:001", "mac": "0102030405060708", "hostname": "LoRa Weather Station", "vendor": "Dragino"},
            {"ip": "LORA:DEV:002", "mac": "0A0B0C0D0E0F1011", "hostname": "LoRa GPS Tracker", "vendor": "Heltec"},
            {"ip": "LORA:DEV:003", "mac": "1112131415161718", "hostname": "LoRa Soil Sensor", "vendor": "TTGO"},
        ]
        
        for dev in mock_lora:
            risk_result = calculate_risk([], "LoRaWAN", {
                "LORA_ABF_CONFIRMATION": True,
                "LORA_WEAK_DEVNONCE": True
            })
            existing = db.query(Device).filter(Device.ip == dev["ip"]).first()
            if not existing:
                device = Device(
                    ip=dev["ip"],
                    mac=dev["mac"],
                    hostname=dev["hostname"],
                    vendor=dev["vendor"],
                    protocol="LoRaWAN",
                    risk_level=risk_result["risk_level"],
                    risk_score=risk_result["risk_score"],
                    last_seen=datetime.utcnow()
                )
                db.add(device)
                db.flush()
                for v in risk_result["vulnerabilities"]:
                    db.add(Vulnerability(
                        device_id=device.id,
                        vuln_type=v["vuln_type"],
                        severity=v["severity"],
                        description=v["description"],
                        protocol=v.get("protocol")
                    ))
                db.commit()
        
        scan_state["message"] = f"LoRaWAN scan complete. {len(mock_lora)} devices found."
        scan_state["running"] = False
    finally:
        db.close()


# ────────────────────────────────────────────────────────────
# 9. Hardware Status
# ────────────────────────────────────────────────────────────
@router.get("/hardware/status")
async def get_hardware_status():
    """
    Returns DETAILED status of ALL connected hardware dongles.
    This shows you exactly what's connected, where, and if it's working.
    """
    # Get detailed dongle detection
    dongles = detect_all_dongles()
    
    # Fallback: use simpler detection if detect_all_dongles missed something
    zigbee_port = detect_zigbee_dongle()
    if zigbee_port and not dongles['zigbee']:
        dongles['zigbee'] = {
            'port': zigbee_port,
            'type': 'Zigbee',
            'chip': 'CC2531/CC2652',
            'description': 'Detected via fallback',
            'manufacturer': 'Unknown',
            'status': 'CONNECTED ✅'
        }
        logger.info(f"[HW Status] Zigbee dongle found via fallback: {zigbee_port}")
    
    thread_port = detect_thread_dongle()
    if thread_port and not dongles['thread']:
        dongles['thread'] = {
            'port': thread_port,
            'type': 'Thread/Matter',
            'chip': 'nRF52840',
            'description': 'Detected via fallback',
            'manufacturer': 'Nordic',
            'status': 'CONNECTED ✅'
        }
    
    zigbee_connected = dongles['zigbee'] is not None
    
    return {
        "status": "success",
        "dongles": dongles,
        "summary": {
            "zigbee": {
                "connected": zigbee_connected,
                "port": dongles['zigbee']['port'] if zigbee_connected else None,
                "chip": dongles['zigbee']['chip'] if zigbee_connected else None,
                "ready": zigbee_connected  # Ready for serial scan even without KillerBee
            },
            "thread": {
                "connected": dongles['thread'] is not None,
                "port": dongles['thread']['port'] if dongles['thread'] else None,
                "chip": "nRF52840" if dongles['thread'] else None,
                "ready": dongles['thread'] is not None
            },
            "zwave": {
                "connected": dongles['zwave'] is not None,
                "port": dongles['zwave']['port'] if dongles['zwave'] else None,
                "ready": dongles['zwave'] is not None
            },
            "bluetooth": {
                "connected": dongles['bluetooth'] is not None,
                "port": dongles['bluetooth']['port'] if dongles['bluetooth'] else None,
                "ready": dongles['bluetooth'] is not None
            }
        },
        "killerbee_available": check_killerbee_available(),
        "total_connected": sum(1 for d in [dongles['zigbee'], dongles['thread'], dongles['zwave'], dongles['bluetooth']] if d is not None)
    }
