from .smart_lock   import build_services as lock_services,     DEVICE_CONFIG as LOCK_CONFIG
from .fitbit        import build_services as fitbit_services,   DEVICE_CONFIG as FITBIT_CONFIG
from .lifx_bulb     import build_services as lifx_services,     DEVICE_CONFIG as LIFX_CONFIG
from .glucose_meter import build_services as glucose_services,  DEVICE_CONFIG as GLUCOSE_CONFIG
from .headphones    import build_services as jbl_services,      DEVICE_CONFIG as JBL_CONFIG

ALL_DEVICES = [
    (LOCK_CONFIG,    lock_services),
    (FITBIT_CONFIG,  fitbit_services),
    (LIFX_CONFIG,    lifx_services),
    (GLUCOSE_CONFIG, glucose_services),
    (JBL_CONFIG,     jbl_services),
]
