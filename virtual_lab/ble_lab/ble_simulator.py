#!/usr/bin/env python3
"""
PentexOne BLE Lab — Virtual Peripheral Simulator
==================================================

Runs 5 simulated BLE devices using the bumble library.
Each device advertises over the host machine's real Bluetooth adapter so
PentexOne's bleak scanner can discover them as real BLE peripherals.

Devices:
  🔒 August-Lock-A4B2     — No pairing / unauthenticated lock/unlock
  ⌚ Fitbit-Charge-5      — Health data exposed without bonding
  💡 LIFX-A19-3F88        — Hardcoded auth token + Wi-Fi creds in BLE
  🩺 Accu-Chek-Guide      — Medical data in plaintext
  🎧 JBL-Tune-510BT       — Pairing key + device history exposed

Usage:
  python3 ble_simulator.py                        # all devices, auto adapter
  python3 ble_simulator.py --device lock          # single device
  python3 ble_simulator.py --adapter hci1         # specific adapter

Requirements:
  pip install bumble
  Linux: BlueZ must be running (systemctl start bluetooth)
  macOS: bumble uses virtual HCI — no root needed for simulation
"""

import asyncio
import argparse
import logging
import signal
import sys

try:
    from bumble.device import Device, DeviceConfiguration
    from bumble.host import Host
    from bumble.transport import open_transport_or_link
    from bumble.hci import (
        HCI_LE_Set_Advertising_Parameters_Command,
        HCI_LE_Set_Advertising_Data_Command,
        HCI_LE_Set_Scan_Response_Data_Command,
        HCI_LE_Set_Advertise_Enable_Command,
    )
    from bumble.core import AdvertisingData
    BUMBLE_AVAILABLE = True
except ImportError:
    BUMBLE_AVAILABLE = False

from devices import ALL_DEVICES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("ble_lab")

# ─── Fallback simulator (no bumble) ──────────────────────────────────────────

class FallbackSimulator:
    """
    Minimal BLE presence emulator used when bumble is unavailable.
    Logs device advertisement data so PentexOne REST API can still reflect
    'detected' BLE devices via the /lab/ble-devices endpoint.
    """

    def __init__(self):
        self.running = False

    async def run(self, devices):
        self.running = True
        logger.warning("=" * 60)
        logger.warning("bumble not installed — running in FALLBACK mode")
        logger.warning("BLE devices are NOT advertising over air.")
        logger.warning("Use  pip install bumble  for real BLE advertising.")
        logger.warning("=" * 60)

        logger.info("Simulated BLE device registry (in-memory only):")
        for cfg, _ in devices:
            logger.info(
                f"  {cfg['name']:25s}  {cfg['address']}  "
                f"vulns={len(cfg['vulnerabilities'])}"
            )

        logger.info("\nFallback mode active — press Ctrl+C to stop.")
        try:
            while self.running:
                await asyncio.sleep(5)
                for cfg, _ in devices:
                    logger.debug(f"[ADV] {cfg['name']} @ {cfg['address']}")
        except asyncio.CancelledError:
            pass

    def stop(self):
        self.running = False


# ─── Real bumble peripheral ──────────────────────────────────────────────────

async def run_ble_device(config: dict, build_services_fn, transport_spec: str):
    """Start one BLE peripheral using bumble."""
    async with await open_transport_or_link(transport_spec) as (hci_source, hci_sink):
        device = Device(
            name=config["name"],
            address=config["address"],
            host=Host(hci_source, hci_sink),
        )

        # Register GATT services
        for service in build_services_fn():
            device.add_service(service)

        await device.power_on()

        # Build advertising data
        adv_data = AdvertisingData([
            (AdvertisingData.COMPLETE_LOCAL_NAME, config["name"].encode()),
            (AdvertisingData.APPEARANCE, bytes([
                config.get("appearance", 0x0000) & 0xFF,
                (config.get("appearance", 0x0000) >> 8) & 0xFF,
            ])),
            (AdvertisingData.FLAGS, bytes([0x06])),  # LE General Discoverable, BR/EDR not supported
        ])

        await device.start_advertising(advertising_data=adv_data, auto_restart=True)

        logger.info(
            f"[ADV] {config['name']:25s} {config['address']}  "
            f"vulnerabilities={config['vulnerabilities']}"
        )

        # Keep running
        await asyncio.Event().wait()


# ─── Orchestrator ─────────────────────────────────────────────────────────────

async def run_all(devices, transport_spec: str):
    """Start all BLE peripherals concurrently."""
    if not BUMBLE_AVAILABLE:
        sim = FallbackSimulator()
        await sim.run(devices)
        return

    logger.info(f"Starting {len(devices)} BLE peripheral(s) on {transport_spec}")
    tasks = [
        asyncio.create_task(
            run_ble_device(cfg, build_fn, transport_spec),
            name=cfg["name"],
        )
        for cfg, build_fn in devices
    ]

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


# ─── Entry point ─────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="PentexOne BLE Lab simulator")
    p.add_argument(
        "--device",
        choices=["lock", "fitbit", "lifx", "glucose", "jbl", "all"],
        default="all",
        help="Which device(s) to simulate (default: all)",
    )
    p.add_argument(
        "--adapter",
        default="hci0",
        help="HCI adapter to use on Linux (default: hci0). Ignored on macOS fallback.",
    )
    p.add_argument(
        "--transport",
        default=None,
        help="bumble transport string (overrides --adapter). E.g. 'usb:0' or 'serial:/dev/ttyACM0'",
    )
    p.add_argument("--verbose", action="store_true", help="Enable DEBUG logging")
    return p.parse_args()


NAME_MAP = {
    "lock":    0,
    "fitbit":  1,
    "lifx":    2,
    "glucose": 3,
    "jbl":     4,
}


def main():
    args = parse_args()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Select devices
    if args.device == "all":
        selected = ALL_DEVICES
    else:
        idx = NAME_MAP[args.device]
        selected = [ALL_DEVICES[idx]]

    # Determine transport
    if args.transport:
        transport = args.transport
    else:
        transport = f"pyusb:0" if sys.platform == "linux" else "tcp-client:127.0.0.1:6402"
        # Most common Linux case: use the system HCI
        if sys.platform == "linux" and BUMBLE_AVAILABLE:
            transport = f"hci-socket:{args.adapter}"

    print("=" * 62)
    print("  PentexOne BLE Lab — Virtual Peripheral Simulator")
    print("=" * 62)
    print(f"  Transport : {transport}")
    print(f"  Devices   : {len(selected)}")
    print()
    for cfg, _ in selected:
        vuln_count = len(cfg["vulnerabilities"])
        print(f"  {'[BLE]':6s} {cfg['name']:25s} {cfg['address']}  ({vuln_count} vulns)")
    print()
    print("  Press Ctrl+C to stop all peripherals.")
    print("=" * 62)

    loop = asyncio.get_event_loop()

    def _shutdown(sig, frame):
        logger.info("Shutdown signal received — stopping BLE lab...")
        for task in asyncio.all_tasks(loop):
            task.cancel()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        loop.run_until_complete(run_all(selected, transport))
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        loop.close()
        print("\nBLE lab stopped.")


if __name__ == "__main__":
    main()
