"""
August Smart Lock — BLE Simulation
Vulnerability: No pairing required, lock/unlock without authentication
BLE Name: August-Lock-A4B2
"""

import struct
import logging
from bumble.device import Device
from bumble.gatt import (
    Service, Characteristic, CharacteristicValue,
    GATT_DEVICE_INFORMATION_SERVICE,
    GATT_MANUFACTURER_NAME_STRING_CHARACTERISTIC,
    GATT_MODEL_NUMBER_STRING_CHARACTERISTIC,
    GATT_FIRMWARE_REVISION_STRING_CHARACTERISTIC,
)
from bumble.core import UUID

logger = logging.getLogger("ble_lab.smart_lock")

# Custom UUIDs for August Smart Lock (simulated)
LOCK_SERVICE_UUID      = UUID("0000FE24-0000-1000-8000-00805F9B34FB")
LOCK_STATE_UUID        = UUID("00002A56-0000-1000-8000-00805F9B34FB")  # lock state R/W
LOCK_COMMAND_UUID      = UUID("00002A57-0000-1000-8000-00805F9B34FB")  # command W
LOCK_LOG_UUID          = UUID("00002A58-0000-1000-8000-00805F9B34FB")  # access log R

# State: 0x00=locked, 0x01=unlocked
_lock_state = bytearray([0x00])

# Access log stored in plaintext
_access_log = (
    "2024-03-01 08:22 UNLOCK user=admin pin=1234\n"
    "2024-03-01 22:05 LOCK   auto-lock\n"
    "2024-03-02 07:55 UNLOCK user=guest pin=0000\n"
    "2024-03-02 23:00 LOCK   auto-lock\n"
)


def _read_lock_state(connection):
    state_str = "UNLOCKED" if _lock_state[0] == 0x01 else "LOCKED"
    logger.info(f"[LOCK] State read by {connection.peer_address}: {state_str}")
    return bytes(_lock_state)


def _write_lock_command(connection, data):
    global _lock_state
    cmd = data[0] if data else 0xFF
    if cmd == 0x01:
        _lock_state[0] = 0x01
        logger.warning(f"[LOCK] *** UNLOCKED without auth by {connection.peer_address} ***")
    elif cmd == 0x00:
        _lock_state[0] = 0x00
        logger.info(f"[LOCK] Locked by {connection.peer_address}")
    else:
        logger.info(f"[LOCK] Unknown command 0x{cmd:02X}")


def _read_access_log(connection):
    # VULNERABILITY: full plaintext access log with PINs readable by anyone
    logger.warning(f"[LOCK] Access log (with PINs) read by {connection.peer_address}")
    return _access_log.encode()


def build_services():
    """Return GATT services for the August Smart Lock."""
    return [
        Service(
            GATT_DEVICE_INFORMATION_SERVICE,
            [
                Characteristic(
                    GATT_MANUFACTURER_NAME_STRING_CHARACTERISTIC,
                    Characteristic.READ,
                    CharacteristicValue(read=lambda conn: b"August Home Inc."),
                ),
                Characteristic(
                    GATT_MODEL_NUMBER_STRING_CHARACTERISTIC,
                    Characteristic.READ,
                    CharacteristicValue(read=lambda conn: b"AUG-SL-CON-G03"),
                ),
                Characteristic(
                    GATT_FIRMWARE_REVISION_STRING_CHARACTERISTIC,
                    Characteristic.READ,
                    # VULNERABILITY: outdated firmware version disclosed
                    CharacteristicValue(read=lambda conn: b"1.5.0-vuln"),
                ),
            ],
        ),
        Service(
            LOCK_SERVICE_UUID,
            [
                Characteristic(
                    LOCK_STATE_UUID,
                    Characteristic.READ | Characteristic.NOTIFY,
                    CharacteristicValue(read=_read_lock_state),
                ),
                Characteristic(
                    LOCK_COMMAND_UUID,
                    # VULNERABILITY: WRITE_WITHOUT_RESPONSE — no auth, no pairing
                    Characteristic.WRITE | Characteristic.WRITE_WITHOUT_RESPONSE,
                    CharacteristicValue(write=_write_lock_command),
                ),
                Characteristic(
                    LOCK_LOG_UUID,
                    Characteristic.READ,
                    CharacteristicValue(read=_read_access_log),
                ),
            ],
        ),
    ]


DEVICE_CONFIG = {
    "name": "August-Lock-A4B2",
    "address": "A4:B2:00:01:02:03",
    "appearance": 0x0180,  # Generic Lock
    "vulnerabilities": ["NO_PAIRING_REQUIRED", "CREDENTIAL_LEAK", "INFORMATION_DISCLOSURE"],
    "description": "Smart lock accepting lock/unlock commands without pairing or authentication",
}
