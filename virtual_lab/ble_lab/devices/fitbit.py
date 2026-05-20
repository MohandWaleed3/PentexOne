"""
Fitbit Charge 5 — BLE Simulation
Vulnerability: Health characteristics readable without bonding
BLE Name: Fitbit-Charge-5
"""

import logging
import struct
from bumble.device import Device
from bumble.gatt import (
    Service, Characteristic, CharacteristicValue,
    GATT_DEVICE_INFORMATION_SERVICE,
    GATT_MANUFACTURER_NAME_STRING_CHARACTERISTIC,
    GATT_MODEL_NUMBER_STRING_CHARACTERISTIC,
    GATT_HEART_RATE_SERVICE,
    GATT_HEART_RATE_MEASUREMENT_CHARACTERISTIC,
)
from bumble.core import UUID

logger = logging.getLogger("ble_lab.fitbit")

# Standard health service UUIDs
HEALTH_THERMOMETER_SERVICE   = UUID("00001809-0000-1000-8000-00805F9B34FB")
TEMPERATURE_MEASUREMENT_UUID = UUID("00002A1C-0000-1000-8000-00805F9B34FB")

# Custom Fitbit profile service (simulated)
FITBIT_SERVICE_UUID   = UUID("ADABFB00-6E7D-4601-BDA2-BFFAA68956BA")
STEPS_UUID            = UUID("ADABFB01-6E7D-4601-BDA2-BFFAA68956BA")
SLEEP_DATA_UUID       = UUID("ADABFB02-6E7D-4601-BDA2-BFFAA68956BA")
USER_PROFILE_UUID     = UUID("ADABFB03-6E7D-4601-BDA2-BFFAA68956BA")
GPS_HISTORY_UUID      = UUID("ADABFB04-6E7D-4601-BDA2-BFFAA68956BA")

_heart_rate = 78  # bpm


def _read_heart_rate(connection):
    # HR measurement: flags(1) + value(1)
    logger.warning(f"[FITBIT] Heart rate read without bonding by {connection.peer_address}")
    return struct.pack("BB", 0x00, _heart_rate)


def _read_temperature(connection):
    # IEEE 11073 float: 36.7°C
    logger.warning(f"[FITBIT] Body temperature read without bonding by {connection.peer_address}")
    return struct.pack("<BHB", 0x00, 367, 0xFE)  # 36.7 in fixed notation


def _read_steps(connection):
    logger.warning(f"[FITBIT] Step count read without bonding by {connection.peer_address}")
    return struct.pack("<I", 9843)  # 9843 steps today


def _read_sleep_data(connection):
    # VULNERABILITY: detailed sleep + location data in plaintext
    data = (
        "date=2024-03-02\n"
        "sleep_start=23:14\nsleep_end=07:02\n"
        "deep_sleep_min=87\nrem_min=112\nawake_min=23\n"
        "sleep_score=81\n"
        "resting_hr=58\nspO2_avg=97.2\n"
    )
    logger.warning(f"[FITBIT] Sleep data (detailed) read by {connection.peer_address}")
    return data.encode()


def _read_user_profile(connection):
    # VULNERABILITY: PII readable without authentication
    profile = (
        "name=John Doe\nage=34\ngender=M\n"
        "weight_kg=78.5\nheight_cm=178\n"
        "email=john.doe@company.com\n"
        "account_id=FB-7824619\n"
    )
    logger.warning(f"[FITBIT] *** PII profile read without auth by {connection.peer_address} ***")
    return profile.encode()


def _read_gps_history(connection):
    # VULNERABILITY: GPS location history readable
    gps = (
        "2024-03-02 07:15 37.7749,-122.4194 (San Francisco, CA)\n"
        "2024-03-02 12:30 37.7751,-122.4182 (work)\n"
        "2024-03-02 18:45 37.7749,-122.4194 (home)\n"
    )
    logger.warning(f"[FITBIT] GPS history read by {connection.peer_address}")
    return gps.encode()


def build_services():
    return [
        Service(
            GATT_DEVICE_INFORMATION_SERVICE,
            [
                Characteristic(
                    GATT_MANUFACTURER_NAME_STRING_CHARACTERISTIC,
                    Characteristic.READ,
                    CharacteristicValue(read=lambda conn: b"Fitbit Inc."),
                ),
                Characteristic(
                    GATT_MODEL_NUMBER_STRING_CHARACTERISTIC,
                    Characteristic.READ,
                    CharacteristicValue(read=lambda conn: b"FB421"),
                ),
            ],
        ),
        Service(
            GATT_HEART_RATE_SERVICE,
            [
                Characteristic(
                    GATT_HEART_RATE_MEASUREMENT_CHARACTERISTIC,
                    # VULNERABILITY: no ENCRYPTED_READ requirement
                    Characteristic.READ | Characteristic.NOTIFY,
                    CharacteristicValue(read=_read_heart_rate),
                ),
            ],
        ),
        Service(
            HEALTH_THERMOMETER_SERVICE,
            [
                Characteristic(
                    TEMPERATURE_MEASUREMENT_UUID,
                    Characteristic.READ | Characteristic.INDICATE,
                    CharacteristicValue(read=_read_temperature),
                ),
            ],
        ),
        Service(
            FITBIT_SERVICE_UUID,
            [
                Characteristic(STEPS_UUID, Characteristic.READ,
                    CharacteristicValue(read=_read_steps)),
                Characteristic(SLEEP_DATA_UUID, Characteristic.READ,
                    CharacteristicValue(read=_read_sleep_data)),
                Characteristic(USER_PROFILE_UUID, Characteristic.READ,
                    CharacteristicValue(read=_read_user_profile)),
                Characteristic(GPS_HISTORY_UUID, Characteristic.READ,
                    CharacteristicValue(read=_read_gps_history)),
            ],
        ),
    ]


DEVICE_CONFIG = {
    "name": "Fitbit-Charge-5",
    "address": "C5:FB:00:01:02:04",
    "appearance": 0x0180,
    "vulnerabilities": ["EXPOSED_HEALTH_CHARACTERISTICS", "INFORMATION_DISCLOSURE", "NO_PAIRING_REQUIRED"],
    "description": "Fitness tracker exposing heart rate, sleep, GPS, and PII without bonding",
}
