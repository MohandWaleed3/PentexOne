"""
Realistic Simulation Profiles
=============================

Replaces the hardcoded `{"ZIGBEE_DEFAULT_KEY": True}` style flags
with vendor-aware probabilistic findings. Different vendors and
device types now produce different, plausible vulnerability sets —
matching the public reputation of those products.

This file is consulted by `routers/iot.py` and any other simulator
to ensure the demo data looks like the real world:

- High-end vendors (Apple, Yale, Ecobee) → mostly clean.
- Mid-tier (Philips Hue, IKEA)            → 0–1 minor finding.
- Budget / no-name (Tuya, Generic ESP)    → 2–3 findings, often critical.
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional

# ─── Vendor → security tier ─────────────────────────────────────────────
#
#   excellent : enterprise-grade, frequent patches
#   good      : known-security focus, encrypts by default
#   average   : ships secure defaults but slow to patch
#   poor      : ships insecure defaults, slow / no patches
#
VENDOR_TIERS: Dict[str, str] = {
    # Excellent
    "Apple":         "excellent",
    "Google":        "excellent",
    "Yale":          "excellent",
    "August":        "excellent",
    "Schlage":       "excellent",

    # Good
    "Philips":       "good",
    "Philips Hue":   "good",
    "Ecobee":        "good",
    "Nest":          "good",
    "Ring":          "good",
    "Eero":          "good",

    # Average
    "IKEA":          "average",
    "Aqara":         "average",
    "Sonoff":        "average",
    "Bosch":         "average",
    "Dragino":       "average",
    "Heltec":        "average",
    "Sengled":       "average",

    # Poor
    "TP-Link":       "poor",
    "Xiaomi":        "poor",
    "Tuya":          "poor",
    "Wyze":          "poor",
    "Reolink":       "poor",
    "Hikvision":     "poor",
    "Dahua":         "poor",
    "TTGO":          "poor",
    "Generic":       "poor",
    "Unknown":       "poor",
}

# ─── Tier index for probability tables (excellent, good, average, poor) ──
TIER_INDEX = {"excellent": 0, "good": 1, "average": 2, "poor": 3}


# ─── Per-protocol probability tables ────────────────────────────────────
#
# Each entry:  (flag_name, [p_excellent, p_good, p_average, p_poor])
#
# Probabilities chosen to reflect real-world incident frequency:
#  - ZIGBEE_DEFAULT_KEY is the #1 issue in cheap Zigbee devices
#  - LORA_WEAK_DEVNONCE is fairly common across cheap LoRaWAN sensors
#  - MATTER_OPEN_COMMISS only happens during commissioning windows
#
PROTOCOL_FLAGS: Dict[str, List] = {
    "Zigbee": [
        ("ZIGBEE_DEFAULT_KEY",  [0.00, 0.05, 0.30, 0.70]),
        ("ZIGBEE_NO_ENCRYPT",   [0.00, 0.00, 0.10, 0.30]),
        ("ZIGBEE_REPLAY",       [0.05, 0.15, 0.30, 0.50]),
    ],
    "Z-Wave": [
        ("ZWAVE_NO_ENCRYPTION",         [0.00, 0.05, 0.25, 0.60]),
        ("ZWAVE_INCLUSION_VULN",        [0.10, 0.20, 0.35, 0.55]),
        ("ZWAVE_REPLAY_ATTACK",         [0.05, 0.10, 0.25, 0.50]),
        ("ZWAVE_NETWORK_KEY_EXPOSURE",  [0.00, 0.05, 0.15, 0.40]),
    ],
    "Thread": [
        ("THREAD_NO_COMMISSIONER_AUTH", [0.00, 0.00, 0.10, 0.35]),
        ("THREAD_ACTIVE_COMMISSIONER",  [0.05, 0.15, 0.30, 0.55]),
        ("THREAD_NETWORK_KEY_WEAK",     [0.00, 0.05, 0.15, 0.40]),
        ("THREAD_BORDER_ROUTER_EXPOSED",[0.10, 0.15, 0.25, 0.45]),
    ],
    "Matter": [
        ("MATTER_OPEN_COMMISS",  [0.05, 0.10, 0.20, 0.40]),
        ("MATTER_EXPIRED_CERT",  [0.00, 0.05, 0.15, 0.30]),
        ("MATTER_NO_PASSCODE",   [0.00, 0.00, 0.05, 0.20]),
    ],
    "LoRaWAN": [
        ("LORA_ABF_CONFIRMATION",   [0.10, 0.20, 0.40, 0.65]),
        ("LORA_WEAK_DEVNONCE",      [0.05, 0.15, 0.35, 0.60]),
        ("LORA_NO_ADR_LIMITS",      [0.15, 0.25, 0.40, 0.55]),
        ("LORA_JOIN_REQUEST_FLOOD", [0.05, 0.15, 0.30, 0.50]),
    ],
}


def _vendor_tier(vendor: Optional[str]) -> str:
    """Map a raw vendor string to its security tier (default 'average')."""
    if not vendor:
        return "average"
    # exact match first
    if vendor in VENDOR_TIERS:
        return VENDOR_TIERS[vendor]
    # case-insensitive contains
    vlow = vendor.lower()
    for key, tier in VENDOR_TIERS.items():
        if key.lower() in vlow:
            return tier
    return "average"


def realistic_flags(protocol: str,
                    vendor: Optional[str],
                    hostname: Optional[str] = None,
                    seed: Optional[int] = None) -> Dict[str, bool]:
    """
    Return a dict of flags appropriate for a single simulated device.

    Uses the vendor's tier to vary findings: high-tier vendors usually
    return {} (no issues), poor vendors typically return 1–3 flags.

    Pass `seed` for deterministic output (useful in tests).
    """
    rng = random.Random(seed) if seed is not None else random
    tier = _vendor_tier(vendor)
    idx = TIER_INDEX[tier]

    flags: Dict[str, bool] = {}
    for flag_name, probs in PROTOCOL_FLAGS.get(protocol, []):
        if rng.random() < probs[idx]:
            flags[flag_name] = True

    # Hostname-based extra signals (cheap, still realistic)
    hl = (hostname or "").lower()
    if protocol == "Zigbee" and any(k in hl for k in ("test", "dev", "lab")):
        # Test/dev fixtures often left with default keys
        flags.setdefault("ZIGBEE_DEFAULT_KEY", True)
    if protocol == "Matter" and "commission" in hl:
        flags["MATTER_OPEN_COMMISS"] = True

    return flags


def describe_tier(vendor: Optional[str]) -> str:
    """Human-readable tier label, used in the UI/logs."""
    return _vendor_tier(vendor).upper()
