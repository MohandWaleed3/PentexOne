"""
JBL Tune 510BT — BLE Simulation
Vulnerability: No pairing confirmation (Just Works), device info and pairing key exposed
BLE Name: JBL-Tune-510BT
"""

import struct
import logging
from bumble.gatt import (
    Service, Characteristic, CharacteristicValue,
    GATT_DEVICE_INFORMATION_SERVICE,
    GATT_MANUFACTURER_NAME_STRING_CHARACTERISTIC,
    GATT_MODEL_NUMBER_STRING_CHARACTERISTIC,
    GATT_SERIAL_NUMBER_STRING_CHARACTERISTIC,
    GATT_BATTERY_SERVICE,
    GATT_BATTERY_LEVEL_CHARACTERISTIC,
)
from bumble.core import UUID

logger = logging.getLogger("ble_lab.headphones")

# Audio control service (simulated)
AUDIO_SERVICE_UUID     = UUID("00001101-0000-1000-8000-00805F9B34FB")
VOLUME_UUID            = UUID("00002B7D-0000-1000-8000-00805F9B34FB")  # volume R/W
EQ_UUID                = UUID("00002B7E-0000-1000-8000-00805F9B34FB")  # EQ preset R/W
ANC_UUID               = UUID("00002B7F-0000-1000-8000-00805F9B34FB")  # ANC on/off

# Pairing / config service (VULNERABILITY)
PAIR_SERVICE_UUID      = UUID("0000FFFE-0000-1000-8000-00805F9B34FB")
PAIR_KEY_UUID          = UUID("0000FFFD-0000-1000-8000-00805F9B34FB")  # exposed pairing key
DEVICE_HIST_UUID       = UUID("0000FFFC-0000-1000-8000-00805F9B34FB")  # paired device history

_volume = bytearray([0x40])  # 64/100
_eq_preset = bytearray([0x01])  # Bass Boost
_anc_enabled = bytearray([0x00])  # ANC off

# VULNERABILITY: static pairing PIN exposed in a readable characteristic
_PAIRING_KEY = b"JBL-PAIR-1234"


def _read_volume(connection):
    logger.info(f"[JBL] Volume read: {_volume[0]} by {connection.peer_address}")
    return bytes(_volume)


def _write_volume(connection, data):
    global _volume
    if data:
        vol = min(100, max(0, data[0]))
        _volume[0] = vol
        logger.warning(f"[JBL] Volume changed to {vol} by {connection.peer_address} (no confirmation)")


def _read_eq(connection):
    presets = {0: "Flat", 1: "Bass Boost", 2: "Treble Boost", 3: "Vocal"}
    logger.info(f"[JBL] EQ preset: {presets.get(_eq_preset[0], '?')}")
    return bytes(_eq_preset)


def _write_eq(connection, data):
    global _eq_preset
    if data:
        _eq_preset[0] = data[0] & 0x03
        logger.warning(f"[JBL] EQ changed without confirmation by {connection.peer_address}")


def _read_anc(connection):
    state = "ON" if _anc_enabled[0] else "OFF"
    logger.info(f"[JBL] ANC state: {state}")
    return bytes(_anc_enabled)


def _write_anc(connection, data):
    global _anc_enabled
    if data:
        _anc_enabled[0] = 0x01 if data[0] else 0x00
        state = "ON" if _anc_enabled[0] else "OFF"
        logger.warning(f"[JBL] ANC turned {state} by {connection.peer_address} (no auth)")


def _read_pairing_key(connection):
    # VULNERABILITY: pairing key readable — attacker can impersonate this device
    logger.warning(f"[JBL] *** Pairing key exposed to {connection.peer_address} ***")
    return _PAIRING_KEY


def _read_device_history(connection):
    # VULNERABILITY: list of previously paired devices (MAC + name) exposed
    history = (
        "AA:BB:CC:DD:EE:FF Samsung Galaxy S23\n"
        "11:22:33:44:55:66 MacBook Pro 14\n"
        "77:88:99:AA:BB:CC iPad Pro\n"
        "FF:EE:DD:CC:BB:AA Xiaomi 13T\n"
    )
    logger.warning(f"[JBL] Paired device history exposed to {connection.peer_address}")
    return history.encode()


def _read_battery(connection):
    return bytes([82])  # 82% battery


def build_services():
    return [
        Service(
            GATT_DEVICE_INFORMATION_SERVICE,
            [
                Characteristic(GATT_MANUFACTURER_NAME_STRING_CHARACTERISTIC,
                    Characteristic.READ,
                    CharacteristicValue(read=lambda conn: b"JBL (Harman)")),
                Characteristic(GATT_MODEL_NUMBER_STRING_CHARACTERISTIC,
                    Characteristic.READ,
                    CharacteristicValue(read=lambda conn: b"Tune 510BT")),
                Characteristic(GATT_SERIAL_NUMBER_STRING_CHARACTERISTIC,
                    Characteristic.READ,
                    # VULNERABILITY: serial number exposed, can be used for warranty fraud
                    CharacteristicValue(read=lambda conn: b"JBL510BT-2024-098234")),
            ],
        ),
        Service(
            GATT_BATTERY_SERVICE,
            [
                Characteristic(GATT_BATTERY_LEVEL_CHARACTERISTIC,
                    Characteristic.READ | Characteristic.NOTIFY,
                    CharacteristicValue(read=_read_battery)),
            ],
        ),
        Service(
            AUDIO_SERVICE_UUID,
            [
                Characteristic(VOLUME_UUID,
                    Characteristic.READ | Characteristic.WRITE | Characteristic.WRITE_WITHOUT_RESPONSE,
                    CharacteristicValue(read=_read_volume, write=_write_volume)),
                Characteristic(EQ_UUID,
                    Characteristic.READ | Characteristic.WRITE,
                    CharacteristicValue(read=_read_eq, write=_write_eq)),
                Characteristic(ANC_UUID,
                    Characteristic.READ | Characteristic.WRITE,
                    CharacteristicValue(read=_read_anc, write=_write_anc)),
            ],
        ),
        Service(
            PAIR_SERVICE_UUID,
            [
                Characteristic(PAIR_KEY_UUID,
                    # VULNERABILITY: no ENCRYPTED_READ, key is exposed
                    Characteristic.READ,
                    CharacteristicValue(read=_read_pairing_key)),
                Characteristic(DEVICE_HIST_UUID,
                    Characteristic.READ,
                    CharacteristicValue(read=_read_device_history)),
            ],
        ),
    ]


DEVICE_CONFIG = {
    "name": "JBL-Tune-510BT",
    "address": "5B:10:00:01:02:07",
    "appearance": 0x0041,  # Headset
    "vulnerabilities": ["NO_PAIRING_REQUIRED", "HARDCODED_KEY", "INFORMATION_DISCLOSURE"],
    "description": "Bluetooth headphones with exposed pairing key and paired device history",
}
