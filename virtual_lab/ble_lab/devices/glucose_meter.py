"""
Accu-Chek Guide Glucose Meter — BLE Simulation
Vulnerability: Plaintext health data, no bonding, no encryption
BLE Name: Accu-Chek-Guide
"""

import struct
import logging
from bumble.gatt import (
    Service, Characteristic, CharacteristicValue,
    GATT_DEVICE_INFORMATION_SERVICE,
    GATT_MANUFACTURER_NAME_STRING_CHARACTERISTIC,
    GATT_MODEL_NUMBER_STRING_CHARACTERISTIC,
    GATT_GLUCOSE_SERVICE,
)
from bumble.core import UUID

logger = logging.getLogger("ble_lab.glucose_meter")

# Standard Glucose profile UUIDs (Bluetooth SIG)
GLUCOSE_SERVICE_UUID     = UUID("00001808-0000-1000-8000-00805F9B34FB")
GLUCOSE_MEAS_UUID        = UUID("00002A18-0000-1000-8000-00805F9B34FB")
GLUCOSE_CONTEXT_UUID     = UUID("00002A34-0000-1000-8000-00805F9B34FB")
GLUCOSE_FEATURE_UUID     = UUID("00002A51-0000-1000-8000-00805F9B34FB")
RACP_UUID                = UUID("00002A52-0000-1000-8000-00805F9B34FB")

# Custom extended service — patient profile (simulated vulnerability)
PATIENT_SERVICE_UUID = UUID("12345678-0000-1000-8000-00805F9B34FB")
PATIENT_INFO_UUID    = UUID("12345678-0001-1000-8000-00805F9B34FB")
HISTORY_UUID         = UUID("12345678-0002-1000-8000-00805F9B34FB")
INSULIN_LOG_UUID     = UUID("12345678-0003-1000-8000-00805F9B34FB")

# Blood glucose record (mmol/L x 10 stored as int16)
# Flags: time offset present, mmol/L units
_latest_glucose = struct.pack("<BHH", 0x03, 1440, 65)  # flags, time_offset=1440min, 6.5mmol/L


def _read_glucose(connection):
    logger.warning(f"[GLUCOSE] Blood glucose read without bonding by {connection.peer_address}")
    return _latest_glucose


def _read_feature(connection):
    # Feature flags: low battery, sensor malfunction, general fault detection
    return struct.pack("<H", 0b0000000000001110)


def _read_patient_info(connection):
    # VULNERABILITY: PII + medical data in plaintext
    info = (
        "name=Sarah Al-Rashidi\nage=52\ngender=F\n"
        "diabetes_type=Type2\ndoctor=Dr. Hassan Khalil\n"
        "target_glucose_min=4.0\ntarget_glucose_max=7.0\n"
        "medication=Metformin 1000mg\n"
        "insurance_id=INS-20934871\n"
        "hospital=King Fahad Medical City\n"
    )
    logger.warning(f"[GLUCOSE] *** Medical PII read by {connection.peer_address} ***")
    return info.encode()


def _read_history(connection):
    # VULNERABILITY: full glucose history with timestamps
    records = (
        "2024-03-01 07:00 6.1 mmol/L (fasting)\n"
        "2024-03-01 12:30 9.2 mmol/L (post-lunch)\n"
        "2024-03-01 18:00 7.8 mmol/L (pre-dinner)\n"
        "2024-03-01 22:00 6.5 mmol/L (bedtime)\n"
        "2024-03-02 07:00 5.8 mmol/L (fasting)\n"
        "2024-03-02 12:30 11.4 mmol/L (post-lunch — HIGH)\n"
        "2024-03-02 18:00 8.1 mmol/L (pre-dinner)\n"
    )
    logger.warning(f"[GLUCOSE] Glucose history exposed to {connection.peer_address}")
    return records.encode()


def _read_insulin_log(connection):
    log = (
        "2024-03-01 08:00 Lantus 20U (basal)\n"
        "2024-03-01 12:30 Humalog 8U (bolus)\n"
        "2024-03-02 08:00 Lantus 20U (basal)\n"
        "2024-03-02 12:30 Humalog 10U (bolus — correction)\n"
    )
    logger.warning(f"[GLUCOSE] Insulin log exposed to {connection.peer_address}")
    return log.encode()


def build_services():
    return [
        Service(
            GATT_DEVICE_INFORMATION_SERVICE,
            [
                Characteristic(GATT_MANUFACTURER_NAME_STRING_CHARACTERISTIC,
                    Characteristic.READ,
                    CharacteristicValue(read=lambda conn: b"Roche Diagnostics")),
                Characteristic(GATT_MODEL_NUMBER_STRING_CHARACTERISTIC,
                    Characteristic.READ,
                    CharacteristicValue(read=lambda conn: b"Accu-Chek Guide")),
            ],
        ),
        Service(
            GLUCOSE_SERVICE_UUID,
            [
                Characteristic(GLUCOSE_MEAS_UUID,
                    # VULNERABILITY: should require ENCRYPT_AUTHENTICATED_READ per spec
                    Characteristic.READ | Characteristic.NOTIFY,
                    CharacteristicValue(read=_read_glucose)),
                Characteristic(GLUCOSE_FEATURE_UUID,
                    Characteristic.READ,
                    CharacteristicValue(read=_read_feature)),
            ],
        ),
        Service(
            PATIENT_SERVICE_UUID,
            [
                Characteristic(PATIENT_INFO_UUID,
                    Characteristic.READ,
                    CharacteristicValue(read=_read_patient_info)),
                Characteristic(HISTORY_UUID,
                    Characteristic.READ,
                    CharacteristicValue(read=_read_history)),
                Characteristic(INSULIN_LOG_UUID,
                    Characteristic.READ,
                    CharacteristicValue(read=_read_insulin_log)),
            ],
        ),
    ]


DEVICE_CONFIG = {
    "name": "Accu-Chek-Guide",
    "address": "AC:CE:00:01:02:06",
    "appearance": 0x0300,  # Generic: Glucose Meter
    "vulnerabilities": ["UNENCRYPTED_PROTOCOL", "NO_PAIRING_REQUIRED", "INFORMATION_DISCLOSURE"],
    "description": "Medical glucose meter transmitting patient data and history in plaintext BLE",
}
