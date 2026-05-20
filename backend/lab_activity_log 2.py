"""
PentexOne Lab Activity Log
===========================
Thread-safe in-memory circular log of lab events.
Events are appended by the virtual_lab router and BLE/Wi-Fi scanners.
The last MAX_ENTRIES events are kept; older entries are discarded.
"""

import time
import threading
from collections import deque
from typing import List, Dict, Optional
from enum import Enum


MAX_ENTRIES = 500


class EventType(str, Enum):
    LAB_START          = "LAB_START"
    LAB_STOP           = "LAB_STOP"
    SCAN_STARTED       = "SCAN_STARTED"
    DEVICE_DISCOVERED  = "DEVICE_DISCOVERED"
    VULNERABILITY_FOUND = "VULNERABILITY_FOUND"
    QUICK_SCAN         = "QUICK_SCAN"
    BLE_INJECT         = "BLE_INJECT"
    LAB_RESET          = "LAB_RESET"
    ATTACK_SIMULATED   = "ATTACK_SIMULATED"


class ActivityLog:
    def __init__(self):
        self._log: deque = deque(maxlen=MAX_ENTRIES)
        self._lock = threading.Lock()
        self._counter = 0

    def _now(self) -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def record(
        self,
        event_type: EventType,
        message: str,
        device: Optional[str] = None,
        protocol: Optional[str] = None,
        severity: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> Dict:
        with self._lock:
            self._counter += 1
            entry = {
                "id":         self._counter,
                "timestamp":  self._now(),
                "event":      event_type,
                "message":    message,
                "device":     device,
                "protocol":   protocol,
                "severity":   severity,
                "metadata":   metadata or {},
            }
            self._log.append(entry)
            return entry

    def get_all(self, limit: int = 100, event_type: Optional[str] = None) -> List[Dict]:
        with self._lock:
            entries = list(self._log)
        if event_type:
            entries = [e for e in entries if e["event"] == event_type]
        return list(reversed(entries))[:limit]

    def get_stats(self) -> Dict:
        with self._lock:
            entries = list(self._log)

        total = len(entries)
        by_event: Dict[str, int] = {}
        by_severity: Dict[str, int] = {}
        devices_seen = set()

        for e in entries:
            by_event[e["event"]] = by_event.get(e["event"], 0) + 1
            if e["severity"]:
                by_severity[e["severity"]] = by_severity.get(e["severity"], 0) + 1
            if e["device"]:
                devices_seen.add(e["device"])

        return {
            "total_events":    total,
            "unique_devices":  len(devices_seen),
            "by_event":        by_event,
            "by_severity":     by_severity,
        }

    def clear(self):
        with self._lock:
            self._log.clear()
            self._counter = 0


# Singleton
activity_log = ActivityLog()
