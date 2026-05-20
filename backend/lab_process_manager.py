"""
PentexOne Lab Process Manager
==============================
Controls the lifecycle of the Virtual Lab components:
  - Wi-Fi Lab  : docker compose up/down in virtual_lab/wifi_lab/
  - BLE Lab    : ble_simulator.py subprocess (bumble-based)

Designed to be imported as a singleton — one instance shared across the app.
"""

import asyncio
import logging
import os
import subprocess
import sys
import time
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger("lab_process_manager")

# Resolve paths relative to this file
_BACKEND_DIR   = Path(__file__).parent
_PROJECT_DIR   = _BACKEND_DIR.parent
_WIFI_LAB_DIR  = _PROJECT_DIR / "virtual_lab" / "wifi_lab"
_BLE_SCRIPT    = _PROJECT_DIR / "virtual_lab" / "ble_lab" / "ble_simulator.py"


class LabStatus(str, Enum):
    STOPPED  = "stopped"
    STARTING = "starting"
    RUNNING  = "running"
    STOPPING = "stopping"
    ERROR    = "error"


class LabProcessManager:
    def __init__(self):
        self._wifi_status: LabStatus = LabStatus.STOPPED
        self._ble_status:  LabStatus = LabStatus.STOPPED
        self._ble_proc:    Optional[subprocess.Popen] = None
        self._wifi_start_time: Optional[float] = None
        self._ble_start_time:  Optional[float] = None
        self._last_error: str = ""
        self._wifi_lock = asyncio.Lock()
        self._ble_lock = asyncio.Lock()

    # ─── Status ──────────────────────────────────────────────────────────────

    def status(self) -> dict:
        self._refresh_ble_status()
        uptime_wifi = (
            int(time.time() - self._wifi_start_time)
            if self._wifi_start_time and self._wifi_status == LabStatus.RUNNING
            else 0
        )
        uptime_ble = (
            int(time.time() - self._ble_start_time)
            if self._ble_start_time and self._ble_status == LabStatus.RUNNING
            else 0
        )
        return {
            "wifi_lab":  {"status": self._wifi_status, "uptime_seconds": uptime_wifi},
            "ble_lab":   {"status": self._ble_status,  "uptime_seconds": uptime_ble},
            "overall":   self._overall_status(),
            "last_error": self._last_error,
        }

    def _overall_status(self) -> LabStatus:
        statuses = {self._wifi_status, self._ble_status}
        if LabStatus.ERROR in statuses:
            return LabStatus.ERROR
        if statuses == {LabStatus.RUNNING}:
            return LabStatus.RUNNING
        if LabStatus.STARTING in statuses or LabStatus.STOPPING in statuses:
            return LabStatus.STARTING
        if LabStatus.RUNNING in statuses:
            return LabStatus.RUNNING
        return LabStatus.STOPPED

    def _refresh_ble_status(self):
        """Check if the BLE subprocess is still alive."""
        if self._ble_proc is not None:
            ret = self._ble_proc.poll()
            if ret is not None:
                # Process exited
                if self._ble_status == LabStatus.RUNNING:
                    self._ble_status = LabStatus.ERROR if ret != 0 else LabStatus.STOPPED
                    self._last_error = f"BLE simulator exited with code {ret}"
                    logger.warning(self._last_error)
                self._ble_proc = None

    # ─── Wi-Fi Lab ───────────────────────────────────────────────────────────

    async def start_wifi_lab(self) -> dict:
        async with self._wifi_lock:
            if self._wifi_status in (LabStatus.RUNNING, LabStatus.STARTING):
                return {"ok": True, "message": "Wi-Fi lab already running"}

            if not _WIFI_LAB_DIR.exists():
                self._wifi_status = LabStatus.ERROR
                self._last_error = f"Wi-Fi lab directory not found: {_WIFI_LAB_DIR}"
                return {"ok": False, "error": self._last_error}

            self._wifi_status = LabStatus.STARTING
            self._last_error = ""

            try:
                result = await asyncio.to_thread(
                    subprocess.run,
                    ["docker", "compose", "up", "-d", "--build"],
                    cwd=str(_WIFI_LAB_DIR),
                    capture_output=True,
                    text=True,
                    timeout=180,
                )
                if result.returncode == 0:
                    self._wifi_status = LabStatus.RUNNING
                    self._wifi_start_time = time.time()
                    logger.info("Wi-Fi lab started successfully")
                    return {"ok": True, "message": "Wi-Fi lab started (7 containers)"}
                else:
                    self._wifi_status = LabStatus.ERROR
                    self._last_error = result.stderr[:500] if result.stderr else "docker compose failed"
                    logger.error(f"Wi-Fi lab start failed: {self._last_error}")
                    return {"ok": False, "error": self._last_error}
            except subprocess.TimeoutExpired:
                self._wifi_status = LabStatus.ERROR
                self._last_error = "docker compose timed out (>180s)"
                return {"ok": False, "error": self._last_error}
            except FileNotFoundError:
                self._wifi_status = LabStatus.ERROR
                self._last_error = "docker not found — is Docker installed?"
                return {"ok": False, "error": self._last_error}
            except Exception as e:
                self._wifi_status = LabStatus.ERROR
                self._last_error = str(e)
                return {"ok": False, "error": self._last_error}

    async def stop_wifi_lab(self) -> dict:
        async with self._wifi_lock:
            if self._wifi_status == LabStatus.STOPPED:
                return {"ok": True, "message": "Wi-Fi lab already stopped"}

            self._wifi_status = LabStatus.STOPPING
            try:
                await asyncio.to_thread(
                    subprocess.run,
                    ["docker", "compose", "down"],
                    cwd=str(_WIFI_LAB_DIR),
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                self._wifi_status = LabStatus.STOPPED
                self._wifi_start_time = None
                logger.info("Wi-Fi lab stopped")
                return {"ok": True, "message": "Wi-Fi lab stopped"}
            except Exception as e:
                self._wifi_status = LabStatus.ERROR
                self._last_error = str(e)
                return {"ok": False, "error": self._last_error}

    # ─── BLE Lab ─────────────────────────────────────────────────────────────

    async def start_ble_lab(self) -> dict:
        async with self._ble_lock:
            self._refresh_ble_status()
            if self._ble_status in (LabStatus.RUNNING, LabStatus.STARTING):
                return {"ok": True, "message": "BLE lab already running"}

            if not _BLE_SCRIPT.exists():
                self._ble_status = LabStatus.ERROR
                self._last_error = f"BLE simulator not found: {_BLE_SCRIPT}"
                return {"ok": False, "error": self._last_error}

            self._ble_status = LabStatus.STARTING
            self._last_error = ""

            try:
                # Discard stdout/stderr — keeping pipes open without a reader
                # would deadlock the child once its kernel pipe buffer fills.
                self._ble_proc = subprocess.Popen(
                    [sys.executable, str(_BLE_SCRIPT)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                # Give it 2 seconds to fail fast
                await asyncio.sleep(2)
                self._refresh_ble_status()

                if self._ble_status == LabStatus.ERROR:
                    return {"ok": False, "error": self._last_error}

                self._ble_status = LabStatus.RUNNING
                self._ble_start_time = time.time()
                logger.info(f"BLE lab started (PID {self._ble_proc.pid})")
                return {
                    "ok": True,
                    "message": "BLE lab started (5 virtual peripherals)",
                    "pid": self._ble_proc.pid,
                }
            except Exception as e:
                self._ble_status = LabStatus.ERROR
                self._last_error = str(e)
                return {"ok": False, "error": self._last_error}

    async def stop_ble_lab(self) -> dict:
        async with self._ble_lock:
            self._refresh_ble_status()
            if self._ble_proc is None or self._ble_status == LabStatus.STOPPED:
                self._ble_status = LabStatus.STOPPED
                return {"ok": True, "message": "BLE lab already stopped"}

            self._ble_status = LabStatus.STOPPING
            try:
                self._ble_proc.terminate()
                await asyncio.sleep(1)
                if self._ble_proc.poll() is None:
                    self._ble_proc.kill()
                self._ble_proc = None
                self._ble_status = LabStatus.STOPPED
                self._ble_start_time = None
                logger.info("BLE lab stopped")
                return {"ok": True, "message": "BLE lab stopped"}
            except Exception as e:
                self._ble_status = LabStatus.ERROR
                self._last_error = str(e)
                return {"ok": False, "error": self._last_error}

    # ─── Combined start/stop ──────────────────────────────────────────────────

    async def start_all(self) -> dict:
        wifi_result, ble_result = await asyncio.gather(
            self.start_wifi_lab(),
            self.start_ble_lab(),
            return_exceptions=True,
        )
        return {
            "ok": True,
            "wifi_lab": wifi_result if not isinstance(wifi_result, Exception) else {"ok": False, "error": str(wifi_result)},
            "ble_lab":  ble_result  if not isinstance(ble_result,  Exception) else {"ok": False, "error": str(ble_result)},
        }

    async def stop_all(self) -> dict:
        wifi_result, ble_result = await asyncio.gather(
            self.stop_wifi_lab(),
            self.stop_ble_lab(),
            return_exceptions=True,
        )
        return {
            "ok": True,
            "wifi_lab": wifi_result if not isinstance(wifi_result, Exception) else {"ok": False, "error": str(wifi_result)},
            "ble_lab":  ble_result  if not isinstance(ble_result,  Exception) else {"ok": False, "error": str(ble_result)},
        }


# Singleton instance shared across the app
lab_manager = LabProcessManager()
