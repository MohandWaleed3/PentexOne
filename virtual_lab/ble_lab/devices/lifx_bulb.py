"""
LIFX A19 Smart Bulb — BLE Simulation
Vulnerability: Weak/static authentication token, unencrypted control commands
BLE Name: LIFX-A19-3F88
"""

import struct
import logging
from bumble.gatt import (
    Service, Characteristic, CharacteristicValue,
    GATT_DEVICE_INFORMATION_SERVICE,
    GATT_MANUFACTURER_NAME_STRING_CHARACTERISTIC,
    GATT_MODEL_NUMBER_STRING_CHARACTERISTIC,
    GATT_FIRMWARE_REVISION_STRING_CHARACTERISTIC,
)
from bumble.core import UUID

logger = logging.getLogger("ble_lab.lifx_bulb")

# LIFX BLE service (simulated)
LIFX_SERVICE_UUID   = UUID("0001AAAA-0002-0003-0004-000000000001")
COLOR_UUID          = UUID("0001AAAA-0002-0003-0004-000000000002")  # HSBK R/W
POWER_UUID          = UUID("0001AAAA-0002-0003-0004-000000000003")  # on/off R/W
AUTH_TOKEN_UUID     = UUID("0001AAAA-0002-0003-0004-000000000004")  # auth token R (VULN)
WIFI_CREDS_UUID     = UUID("0001AAAA-0002-0003-0004-000000000005")  # provisioning (VULN)

# HSBK: hue, saturation, brightness, kelvin (each uint16)
_color = bytearray(struct.pack("<HHHH", 43690, 65535, 65535, 3500))  # warm white
_power = bytearray([0x01])  # on

# VULNERABILITY: hardcoded auth token (never rotated)
_STATIC_TOKEN = b"LIFX-TOKEN-8f3a9c2b"


def _read_color(connection):
    h, s, b, k = struct.unpack("<HHHH", _color)
    logger.info(f"[LIFX] Color read: H={h} S={s} B={b} K={k}K by {connection.peer_address}")
    return bytes(_color)


def _write_color(connection, data):
    global _color
    if len(data) >= 8:
        _color = bytearray(data[:8])
        h, s, b, k = struct.unpack("<HHHH", _color)
        logger.info(f"[LIFX] Color changed to H={h} S={s} B={b} K={k}K by {connection.peer_address}")
    else:
        logger.warning(f"[LIFX] Invalid color data from {connection.peer_address}")


def _read_power(connection):
    state = "ON" if _power[0] else "OFF"
    logger.info(f"[LIFX] Power state read: {state} by {connection.peer_address}")
    return bytes(_power)


def _write_power(connection, data):
    global _power
    cmd = data[0] if data else 0
    _power[0] = 0x01 if cmd else 0x00
    state = "ON" if _power[0] else "OFF"
    logger.warning(f"[LIFX] Power turned {state} by {connection.peer_address} (no auth check)")


def _read_auth_token(connection):
    # VULNERABILITY: static token readable by any connected device — can replay to cloud API
    logger.warning(f"[LIFX] *** Auth token leaked to {connection.peer_address} ***")
    return _STATIC_TOKEN


def _read_wifi_creds(connection):
    # VULNERABILITY: provisioned Wi-Fi credentials stored in plaintext on device
    creds = b"ssid=HomeNetwork\npassword=Passw0rd123!\nsecurity=WPA2"
    logger.warning(f"[LIFX] *** Wi-Fi credentials leaked to {connection.peer_address} ***")
    return creds


def build_services():
    return [
        Service(
            GATT_DEVICE_INFORMATION_SERVICE,
            [
                Characteristic(GATT_MANUFACTURER_NAME_STRING_CHARACTERISTIC,
                    Characteristic.READ,
                    CharacteristicValue(read=lambda conn: b"LIFX Inc.")),
                Characteristic(GATT_MODEL_NUMBER_STRING_CHARACTERISTIC,
                    Characteristic.READ,
                    CharacteristicValue(read=lambda conn: b"L1A19")),
                Characteristic(GATT_FIRMWARE_REVISION_STRING_CHARACTERISTIC,
                    Characteristic.READ,
                    CharacteristicValue(read=lambda conn: b"2.80.0")),
            ],
        ),
        Service(
            LIFX_SERVICE_UUID,
            [
                Characteristic(COLOR_UUID,
                    Characteristic.READ | Characteristic.WRITE,
                    CharacteristicValue(read=_read_color, write=_write_color)),
                Characteristic(POWER_UUID,
                    Characteristic.READ | Characteristic.WRITE | Characteristic.WRITE_WITHOUT_RESPONSE,
                    CharacteristicValue(read=_read_power, write=_write_power)),
                Characteristic(AUTH_TOKEN_UUID,
                    # VULNERABILITY: token is readable, should be encrypted
                    Characteristic.READ,
                    CharacteristicValue(read=_read_auth_token)),
                Characteristic(WIFI_CREDS_UUID,
                    # VULNERABILITY: Wi-Fi password readable over BLE
                    Characteristic.READ,
                    CharacteristicValue(read=_read_wifi_creds)),
            ],
        ),
    ]


DEVICE_CONFIG = {
    "name": "LIFX-A19-3F88",
    "address": "3F:88:00:01:02:05",
    "appearance": 0x0140,
    "vulnerabilities": ["HARDCODED_KEY", "UNENCRYPTED_PROTOCOL", "CREDENTIAL_LEAK"],
    "description": "Smart bulb with static auth token and Wi-Fi credentials readable over BLE",
}
