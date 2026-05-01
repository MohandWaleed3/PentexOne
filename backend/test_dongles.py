#!/usr/bin/env python3
"""
PentexOne - Quick Dongle Detection Test
Run this to see ALL connected hardware dongles instantly!

Usage:
    python3 test_dongles.py
"""

import serial
import serial.tools.list_ports
import sys

def detect_all_dongles():
    """Detects ALL connected hardware dongles"""
    ports = serial.tools.list_ports.comports()
    
    dongles = {
        'zigbee': None,
        'thread': None,
        'zwave': None,
        'bluetooth': None,
        'other_usb_serials': []
    }
    
    print("\n" + "="*70)
    print("🔍 PENTEXONE - HARDWARE DONGLE DETECTION")
    print("="*70)
    print(f"\n📡 Scanning {len(ports)} serial port(s)...\n")
    
    for port in ports:
        desc_upper = port.description.upper()
        hwid_upper = port.hwid.upper() if port.hwid else ""
        
        print(f"📍 Port: {port.device}")
        print(f"   Description: {port.description}")
        print(f"   HWID: {port.hwid}")
        print(f"   Manufacturer: {port.manufacturer or 'Unknown'}")
        print(f"   Serial Number: {port.serial_number or 'Unknown'}")
        
        # Detect Zigbee dongles
        if any(x in desc_upper or x in hwid_upper for x in ['CC2652', 'CC2531', 'ZIGBEE', 'TI', 'CP210', 'SILICON LABS', 'CH340', 'SONOFF']):
            chip = 'CC2652P' if 'CC2652' in desc_upper else ('CC2531' if 'CC2531' in desc_upper else 'CP210x / CH340 / Silicon Labs')
            dongles['zigbee'] = {
                'port': port.device,
                'type': 'Zigbee',
                'chip': chip,
                'description': port.description,
                'manufacturer': port.manufacturer or 'Unknown',
                'status': 'CONNECTED ✅'
            }
            print(f"   ✅ DETECTED: Zigbee Dongle ({chip})")
        
        # Detect Thread/Matter dongles
        elif any(x in desc_upper or x in hwid_upper for x in ['NRF', 'NORDIC', 'THREAD', 'MATTER', 'JLINK', '52840']):
            dongles['thread'] = {
                'port': port.device,
                'chip': 'nRF52840',
                'description': port.description,
                'status': '✅ CONNECTED'
            }
            print(f"   ✅ DETECTED: Thread/Matter Dongle (nRF52840)")
        
        # Detect Z-Wave dongles
        elif any(x in desc_upper or x in hwid_upper for x in ['ZWAVE', 'Z-WAVE', 'AEOTEC', 'Z-STICK', 'SIGMA']):
            dongles['zwave'] = {
                'port': port.device,
                'chip': 'Z-Wave Module',
                'description': port.description,
                'status': '✅ CONNECTED'
            }
            print(f"   ✅ DETECTED: Z-Wave Dongle")
        
        # Detect Bluetooth dongles
        elif any(x in desc_upper or x in hwid_upper for x in ['BLUETOOTH', 'CSR', 'BROADCOM', 'INTEL BT']):
            dongles['bluetooth'] = {
                'port': port.device,
                'chip': 'Bluetooth Adapter',
                'description': port.description,
                'status': '✅ CONNECTED'
            }
            print(f"   ✅ DETECTED: Bluetooth Adapter")
        
        # Add to other serials
        else:
            if 'USB' in desc_upper or 'SERIAL' in desc_upper:
                dongles['other_usb_serials'].append({
                    'port': port.device,
                    'description': port.description,
                    'manufacturer': port.manufacturer or 'Unknown'
                })
        
        print()
    
    # Summary
    print("="*70)
    print("📊 DETECTION SUMMARY")
    print("="*70)
    
    connected_count = 0
    
    if dongles['zigbee']:
        print(f"✅ Zigbee Dongle:    {dongles['zigbee']['port']} ({dongles['zigbee']['chip']})")
        connected_count += 1
    else:
        print("❌ Zigbee Dongle:    NOT CONNECTED")
    
    if dongles['thread']:
        print(f"✅ Thread/Matter:     {dongles['thread']['port']} (nRF52840)")
        connected_count += 1
    else:
        print("❌ Thread/Matter:     NOT CONNECTED")
    
    if dongles['zwave']:
        print(f"✅ Z-Wave Dongle:     {dongles['zwave']['port']}")
        connected_count += 1
    else:
        print("❌ Z-Wave Dongle:     NOT CONNECTED")
    
    if dongles['bluetooth']:
        print(f"✅ Bluetooth:         {dongles['bluetooth']['port']}")
        connected_count += 1
    else:
        print("ℹ️  Bluetooth:         Using built-in (if available)")
    
    if dongles['other_usb_serials']:
        print(f"\n📡 Other USB Serial Devices ({len(dongles['other_usb_serials'])}):")
        for dev in dongles['other_usb_serials']:
            print(f"   - {dev['port']}: {dev['description']}")
    
    print(f"\n🎯 Total Dongles Connected: {connected_count}")
    print("="*70 + "\n")
    
    return dongles

if __name__ == "__main__":
    try:
        dongles = detect_all_dongles()
        
        # Check for KillerBee
        try:
            import killerbee
            print("✅ KillerBee library: INSTALLED (Real Zigbee scanning available)")
        except ImportError:
            print("⚠️  KillerBee library: NOT INSTALLED (Zigbee will use simulation)")
        
        print("\n💡 Tip: Connect your dongles and run this script again to verify!")
        print("🌐 Dashboard: http://localhost:8000/dashboard")
        print("📚 API Docs:  http://localhost:8000/docs\n")
        
    except Exception as e:
        print(f"\n❌ Error: {e}\n")
        sys.exit(1)
