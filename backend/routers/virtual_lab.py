"""
PentexOne Virtual Lab Router
=============================

REST endpoints that integrate the IoT Virtual Lab with the PentexOne core:

  GET  /lab/status            — Current status of Wi-Fi + BLE labs
  POST /lab/start             — Start Wi-Fi lab + BLE lab (or one at a time)
  POST /lab/stop              — Stop Wi-Fi lab + BLE lab (or one at a time)
  GET  /lab/info              — Lab architecture summary (subnets + devices)
  GET  /lab/subnets           — List all lab subnets
  GET  /lab/devices           — List all known lab devices (registry)
  GET  /lab/ble-devices       — List all registered BLE lab devices
  GET  /lab/ble-device/{addr} — Detail for a specific BLE device
  POST /lab/quick-scan        — Inject known lab devices into the DB instantly
  POST /lab/ble-inject        — Inject BLE devices into the DB
  POST /lab/scan              — Active nmap scan on lab subnets (background)
  GET  /lab/device/{ip}       — Detail about a specific lab device
  POST /lab/reset             — Remove all [LAB] devices from the DB
"""

from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, List

from database import get_db, Device, Vulnerability, SessionLocal
from lab_registry import (
    LAB_SUBNETS,
    LAB_DEVICES,
    BLE_DEVICES,
    get_device_by_ip,
    get_subnet_for_ip,
    is_lab_ip,
    get_ble_device_by_address,
    tag_hostname,
    get_lab_summary,
)
from lab_process_manager import lab_manager
from lab_activity_log import activity_log, EventType

router = APIRouter(prefix="/lab", tags=["Virtual Lab"])


# ===========================================================================
# Severity mapping
# ===========================================================================
SEVERITY_MAP = {
    # IoT subnet
    "DEFAULT_CREDENTIALS":       "CRITICAL",
    "OUTDATED_FIRMWARE":         "HIGH",
    "DIRECTORY_LISTING":         "MEDIUM",
    "INFORMATION_DISCLOSURE":    "MEDIUM",
    "NO_AUTHENTICATION":         "CRITICAL",
    "UNENCRYPTED_PROTOCOL":      "HIGH",
    "EXPOSED_TOPICS":            "MEDIUM",
    "WEBSOCKET_OPEN":            "MEDIUM",
    "TELNET_ENABLED":            "CRITICAL",
    "NO_RATE_LIMITING":          "MEDIUM",
    "WEAK_SESSION":              "HIGH",
    "UPNP_EXPOSED":              "HIGH",
    "NO_LOCAL_AUTH":             "CRITICAL",
    "DEVICE_INFO_DISCLOSURE":    "MEDIUM",
    "HARDCODED_KEY":             "CRITICAL",
    "DEBUG_INTERFACE_EXPOSED":   "CRITICAL",
    "WEAK_SESSION_TOKENS":       "HIGH",
    "CREDENTIAL_LEAK":           "CRITICAL",
    # Guest subnet
    "DIAL_EXPOSED":              "MEDIUM",
    "VOICE_API_OPEN":            "HIGH",
    "NO_PAIRING_REQUIRED":       "HIGH",
    "MIC_REMOTE_CONTROL":        "CRITICAL",
    # Corporate subnet
    "SMBv1_ENABLED":             "CRITICAL",
    "ANONYMOUS_FTP":             "HIGH",
    "SHADOW_BACKUP_EXPOSED":     "CRITICAL",
    "OUTDATED_DSM":              "HIGH",
}

SEVERITY_SCORE = {
    "CRITICAL": 25.0,
    "HIGH":     18.0,
    "MEDIUM":   10.0,
    "LOW":      4.0,
}


def _compute_risk(vuln_list: List[str]) -> tuple:
    """Returns (risk_level, risk_score) for a list of vulnerability codes."""
    total = sum(SEVERITY_SCORE.get(SEVERITY_MAP.get(v, "MEDIUM"), 10.0)
                for v in vuln_list)
    total = min(100.0, total)
    if total >= 70:
        return "CRITICAL", total
    elif total >= 45:
        return "HIGH", total
    elif total >= 20:
        return "MEDIUM", total
    return "SAFE", total


# ===========================================================================
# GET /lab/status
# ===========================================================================
@router.get("/status")
async def get_lab_status():
    """Returns the current running status of the Wi-Fi and BLE labs."""
    return {"ok": True, **lab_manager.status()}


# ===========================================================================
# POST /lab/start
# ===========================================================================
@router.post("/start")
async def start_lab(component: Optional[str] = None):
    """
    Start the virtual lab.
    - component=wifi  → start only the Wi-Fi lab (Docker)
    - component=ble   → start only the BLE lab (bumble)
    - omit            → start both
    """
    if component == "wifi":
        result = await lab_manager.start_wifi_lab()
    elif component == "ble":
        result = await lab_manager.start_ble_lab()
    elif component is None:
        result = await lab_manager.start_all()
    else:
        raise HTTPException(status_code=400, detail=f"Unknown component '{component}' (valid: wifi, ble)")
    activity_log.record(
        EventType.LAB_START,
        message=result.get("message", f"Lab start requested (component={component or 'all'})"),
        metadata={"component": component or "all", "ok": result.get("ok")},
    )
    return {"ok": result.get("ok", True), **result}


# ===========================================================================
# POST /lab/stop
# ===========================================================================
@router.post("/stop")
async def stop_lab(component: Optional[str] = None):
    """
    Stop the virtual lab.
    - component=wifi  → stop only the Wi-Fi lab
    - component=ble   → stop only the BLE lab
    - omit            → stop both
    """
    if component == "wifi":
        result = await lab_manager.stop_wifi_lab()
    elif component == "ble":
        result = await lab_manager.stop_ble_lab()
    elif component is None:
        result = await lab_manager.stop_all()
    else:
        raise HTTPException(status_code=400, detail=f"Unknown component '{component}' (valid: wifi, ble)")
    activity_log.record(
        EventType.LAB_STOP,
        message=result.get("message", f"Lab stop requested (component={component or 'all'})"),
        metadata={"component": component or "all", "ok": result.get("ok")},
    )
    return {"ok": result.get("ok", True), **result}


# ===========================================================================
# GET /lab/info
# ===========================================================================
@router.get("/info")
async def lab_info():
    """Returns a complete summary of the lab architecture."""
    return {
        "ok": True,
        "lab": get_lab_summary(),
    }


# ===========================================================================
# GET /lab/subnets
# ===========================================================================
@router.get("/subnets")
async def list_subnets():
    """Returns the 3 isolated subnets with their metadata."""
    return {
        "ok": True,
        "subnets": LAB_SUBNETS,
    }


# ===========================================================================
# GET /lab/devices
# ===========================================================================
@router.get("/devices")
async def list_devices():
    """Returns the registry of all known lab devices."""
    return {
        "ok": True,
        "count": len(LAB_DEVICES),
        "devices": LAB_DEVICES,
    }


# ===========================================================================
# GET /lab/device/{ip}
# ===========================================================================
@router.get("/device/{ip}")
async def get_device(ip: str):
    """Returns details of a single lab device by IP."""
    dev = get_device_by_ip(ip)
    if not dev:
        raise HTTPException(status_code=404, detail=f"No lab device registered at {ip}")
    subnet_info = LAB_SUBNETS.get(dev["subnet"], {})
    risk_lvl, risk_score = _compute_risk(dev["vulnerabilities"])
    return {
        "ok": True,
        "device": {
            **dev,
            "subnet_info": subnet_info,
            "risk_level": risk_lvl,
            "risk_score": risk_score,
        }
    }


# ===========================================================================
# POST /lab/quick-scan
# ===========================================================================
@router.post("/quick-scan")
async def quick_scan(db: Session = Depends(get_db)):
    """
    Zero-wait Quick Scan — directly inject all registered lab devices into the DB.
    Useful for demos and presentations where waiting for nmap is not desirable.
    """
    inserted, updated = 0, 0

    for dev in LAB_DEVICES:
        risk_lvl, risk_score = _compute_risk(dev["vulnerabilities"])
        ports_csv = ",".join(str(p) for p in dev["exposed_ports"])
        tagged_name = tag_hostname(dev["hostname"], dev["subnet"])

        existing = db.query(Device).filter(Device.ip == dev["ip"]).first()

        if existing:
            existing.hostname    = tagged_name
            existing.vendor      = dev["vendor"]
            existing.protocol    = "Wi-Fi"
            existing.os_guess    = f"Lab-{dev['device_type']}"
            existing.risk_level  = risk_lvl
            existing.risk_score  = risk_score
            existing.open_ports  = ports_csv
            existing.last_seen   = datetime.utcnow()
            device_id = existing.id
            # clear old vulnerabilities to avoid duplicates
            db.query(Vulnerability).filter(Vulnerability.device_id == device_id).delete()
            updated += 1
        else:
            ip_parts = [int(x) for x in dev["ip"].split(".")]
            new_dev = Device(
                ip          = dev["ip"],
                mac         = "02:42:{:02x}:{:02x}:{:02x}:{:02x}".format(*ip_parts),
                hostname    = tagged_name,
                vendor      = dev["vendor"],
                protocol    = "Wi-Fi",
                os_guess    = f"Lab-{dev['device_type']}",
                risk_level  = risk_lvl,
                risk_score  = risk_score,
                open_ports  = ports_csv,
                last_seen   = datetime.utcnow(),
            )
            db.add(new_dev)
            db.flush()
            device_id = new_dev.id
            inserted += 1

        # add vulnerabilities
        for vcode in dev["vulnerabilities"]:
            sev = SEVERITY_MAP.get(vcode, "MEDIUM")
            db.add(Vulnerability(
                device_id   = device_id,
                vuln_type   = vcode,
                severity    = sev,
                description = f"[LAB] {dev['device_type'].replace('_', ' ').title()} — {vcode.replace('_', ' ').lower()}",
                port        = dev["exposed_ports"][0] if dev["exposed_ports"] else None,
                protocol    = "Wi-Fi",
            ))

    db.commit()

    activity_log.record(
        EventType.QUICK_SCAN,
        message=f"Quick scan complete — {inserted} new, {updated} updated",
        protocol="Wi-Fi",
        metadata={"inserted": inserted, "updated": updated, "total": len(LAB_DEVICES)},
    )
    return {
        "ok": True,
        "message": f"Quick scan complete — {inserted} new, {updated} updated",
        "inserted": inserted,
        "updated": updated,
        "total_devices": len(LAB_DEVICES),
    }


# ===========================================================================
# POST /lab/scan
# ===========================================================================
@router.post("/scan")
async def active_scan(background_tasks: BackgroundTasks, subnet: Optional[str] = None):
    """
    Active network scan limited to lab subnets.
    If `subnet` is provided (iot|guest|corporate), only that subnet is scanned.
    Otherwise all 3 subnets are scanned in parallel.
    """
    if subnet and subnet not in LAB_SUBNETS:
        raise HTTPException(status_code=400,
            detail=f"Unknown subnet '{subnet}' (valid: {list(LAB_SUBNETS.keys())})")

    targets = [LAB_SUBNETS[subnet]["cidr"]] if subnet else [s["cidr"] for s in LAB_SUBNETS.values()]
    background_tasks.add_task(_active_scan_worker, targets)
    activity_log.record(
        EventType.SCAN_STARTED,
        message=f"Active nmap scan started for {len(targets)} subnet(s)",
        protocol="Wi-Fi",
        metadata={"targets": targets, "subnet_filter": subnet},
    )
    return {
        "ok": True,
        "message": f"Active scan started for {len(targets)} subnet(s)",
        "targets": targets,
    }


def _active_scan_worker(targets: List[str]):
    """Background worker that runs nmap on the requested lab subnets."""
    import nmap
    db = SessionLocal()
    try:
        scanner = nmap.PortScanner()
        for cidr in targets:
            try:
                scanner.scan(hosts=cidr, arguments="-sn -T4 --max-retries=1")
            except Exception:
                continue

            for host in scanner.all_hosts():
                if scanner[host].state() != "up":
                    continue

                # Check if this is a known lab device
                reg = get_device_by_ip(host)
                if not reg:
                    continue  # not registered, skip

                risk_lvl, risk_score = _compute_risk(reg["vulnerabilities"])
                tagged_name = tag_hostname(reg["hostname"], reg["subnet"])
                ports_csv = ",".join(str(p) for p in reg["exposed_ports"])

                existing = db.query(Device).filter(Device.ip == host).first()
                if existing:
                    existing.hostname   = tagged_name
                    existing.vendor     = reg["vendor"]
                    existing.risk_level = risk_lvl
                    existing.risk_score = risk_score
                    existing.open_ports = ports_csv
                    existing.last_seen  = datetime.utcnow()
                    device_id = existing.id
                    db.query(Vulnerability).filter(Vulnerability.device_id == device_id).delete()
                else:
                    ip_parts = [int(x) for x in host.split(".")]
                    new_dev = Device(
                        ip=host,
                        mac="02:42:{:02x}:{:02x}:{:02x}:{:02x}".format(*ip_parts),
                        hostname=tagged_name, vendor=reg["vendor"],
                        protocol="Wi-Fi", os_guess=f"Lab-{reg['device_type']}",
                        risk_level=risk_lvl, risk_score=risk_score,
                        open_ports=ports_csv, last_seen=datetime.utcnow(),
                    )
                    db.add(new_dev)
                    db.flush()
                    device_id = new_dev.id

                for vcode in reg["vulnerabilities"]:
                    db.add(Vulnerability(
                        device_id=device_id, vuln_type=vcode,
                        severity=SEVERITY_MAP.get(vcode, "MEDIUM"),
                        description=f"[LAB] {reg['device_type']} — {vcode}",
                        port=reg["exposed_ports"][0] if reg["exposed_ports"] else None,
                        protocol="Wi-Fi",
                    ))
        db.commit()
    finally:
        db.close()


# ===========================================================================
# POST /lab/reset
# ===========================================================================
@router.post("/reset")
async def reset_lab_devices(db: Session = Depends(get_db)):
    """Removes all lab devices (and their vulnerabilities) from the database."""
    lab_ips = [d["ip"] for d in LAB_DEVICES]
    devices = db.query(Device).filter(Device.ip.in_(lab_ips)).all()
    deleted_count = len(devices)
    for d in devices:
        db.delete(d)
    db.commit()
    activity_log.record(
        EventType.LAB_RESET,
        message=f"Lab reset — {deleted_count} device(s) removed from database",
        metadata={"deleted": deleted_count},
    )
    return {
        "ok": True,
        "deleted": deleted_count,
        "message": f"Removed {deleted_count} lab device(s) from the database",
    }


# ===========================================================================
# GET /lab/ble-devices
# ===========================================================================
@router.get("/ble-devices")
async def list_ble_devices():
    """Returns all registered BLE lab devices with their vulnerability profiles."""
    enriched = []
    for dev in BLE_DEVICES:
        risk_lvl, risk_score = _compute_risk(dev["vulnerabilities"])
        enriched.append({
            **dev,
            "risk_level": risk_lvl,
            "risk_score": risk_score,
            "protocol": "BLE",
            "tag": f"[LAB:BLE] {dev['name']}",
        })
    return {
        "ok": True,
        "count": len(BLE_DEVICES),
        "devices": enriched,
    }


# ===========================================================================
# GET /lab/ble-device/{address}
# ===========================================================================
@router.get("/ble-device/{address}")
async def get_ble_device(address: str):
    """Returns detail for a single BLE lab device by MAC address."""
    dev = get_ble_device_by_address(address)
    if not dev:
        raise HTTPException(
            status_code=404,
            detail=f"No BLE lab device registered with address {address}",
        )
    risk_lvl, risk_score = _compute_risk(dev["vulnerabilities"])
    return {
        "ok": True,
        "device": {
            **dev,
            "risk_level": risk_lvl,
            "risk_score": risk_score,
            "protocol": "BLE",
            "tag": f"[LAB:BLE] {dev['name']}",
        },
    }


# ===========================================================================
# POST /lab/ble-inject
# ===========================================================================
@router.post("/ble-inject")
async def ble_inject(db: Session = Depends(get_db)):
    """
    Inject all registered BLE lab devices into the Device DB as if they were
    discovered by the Bluetooth scanner. Useful for demos when bumble is not running.
    """
    inserted, updated = 0, 0

    for dev in BLE_DEVICES:
        risk_lvl, risk_score = _compute_risk(dev["vulnerabilities"])
        tagged_name = f"[LAB:BLE] {dev['name']}"

        existing = db.query(Device).filter(Device.mac == dev["address"]).first()

        if existing:
            existing.hostname   = tagged_name
            existing.vendor     = dev["vendor"]
            existing.protocol   = "BLE"
            existing.os_guess   = f"Lab-{dev['device_type']}"
            existing.risk_level = risk_lvl
            existing.risk_score = risk_score
            existing.open_ports = ""
            existing.last_seen  = datetime.utcnow()
            device_id = existing.id
            db.query(Vulnerability).filter(Vulnerability.device_id == device_id).delete()
            updated += 1
        else:
            new_dev = Device(
                ip          = f"ble://{dev['address']}",
                mac         = dev["address"],
                hostname    = tagged_name,
                vendor      = dev["vendor"],
                protocol    = "BLE",
                os_guess    = f"Lab-{dev['device_type']}",
                risk_level  = risk_lvl,
                risk_score  = risk_score,
                open_ports  = "",
                last_seen   = datetime.utcnow(),
            )
            db.add(new_dev)
            db.flush()
            device_id = new_dev.id
            inserted += 1

        for vcode in dev["vulnerabilities"]:
            sev = SEVERITY_MAP.get(vcode, "MEDIUM")
            db.add(Vulnerability(
                device_id   = device_id,
                vuln_type   = vcode,
                severity    = sev,
                description = f"[LAB:BLE] {dev['device_type']} — {vcode.replace('_', ' ').lower()}",
                port        = None,
                protocol    = "BLE",
            ))

    db.commit()
    activity_log.record(
        EventType.BLE_INJECT,
        message=f"BLE inject complete — {inserted} new, {updated} updated",
        protocol="BLE",
        metadata={"inserted": inserted, "updated": updated, "total": len(BLE_DEVICES)},
    )
    return {
        "ok": True,
        "message": f"BLE inject complete — {inserted} new, {updated} updated",
        "inserted": inserted,
        "updated": updated,
        "total_ble_devices": len(BLE_DEVICES),
    }


# ===========================================================================
# Helper — annotate a BLE device found by the live scanner
# ===========================================================================
def annotate_lab_ble_device(mac: str) -> dict:
    """
    Called from wifi_bt router when a BLE scan discovers a device whose address
    matches a registered lab BLE peripheral. Returns enriched metadata dict.
    """
    dev = get_ble_device_by_address(mac)
    if not dev:
        return {}
    risk_lvl, risk_score = _compute_risk(dev["vulnerabilities"])
    return {
        "hostname": f"[LAB:BLE] {dev['name']}",
        "vendor": dev["vendor"],
        "risk_level": risk_lvl,
        "risk_score": risk_score,
        "vulnerabilities": dev["vulnerabilities"],
    }


# ===========================================================================
# GET /lab/activity
# ===========================================================================
@router.get("/activity")
async def get_activity(
    limit: int = 50,
    event_type: Optional[str] = None,
):
    """
    Returns the lab activity log (most recent first).
    - limit: max entries to return (default 50, max 500)
    - event_type: filter by event type (LAB_START, SCAN_STARTED, DEVICE_DISCOVERED, etc.)
    """
    limit = min(limit, 500)
    entries = activity_log.get_all(limit=limit, event_type=event_type)
    return {
        "ok": True,
        "server_time": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "count": len(entries),
        "entries": entries,
    }


# ===========================================================================
# GET /lab/activity/stats
# ===========================================================================
@router.get("/activity/stats")
async def get_activity_stats():
    """Returns aggregated statistics from the activity log."""
    return {
        "ok": True,
        "stats": activity_log.get_stats(),
    }


# ===========================================================================
# DELETE /lab/activity
# ===========================================================================
@router.delete("/activity")
async def clear_activity():
    """Clears the activity log."""
    activity_log.clear()
    return {"ok": True, "message": "Activity log cleared"}


# ===========================================================================
# Helper for other routers — annotate a freshly-scanned Wi-Fi device
# ===========================================================================
def annotate_lab_device(device_record: Device) -> Device:
    """
    Called from the main Wi-Fi scanner: if a discovered device belongs to a lab
    subnet, prefix its hostname and enrich its vendor field with the subnet name.
    """
    if device_record is None or not device_record.ip:
        return device_record

    if not is_lab_ip(device_record.ip):
        return device_record

    subnet_match = get_subnet_for_ip(device_record.ip)
    subnet_key = subnet_match[0] if subnet_match else None

    if not device_record.hostname or not device_record.hostname.startswith("[LAB"):
        device_record.hostname = tag_hostname(
            device_record.hostname or "Unknown", subnet_key
        )

    # Add subnet name to vendor for visibility
    if subnet_key and "(Lab" not in (device_record.vendor or ""):
        subnet_name = LAB_SUBNETS[subnet_key]["name"]
        device_record.vendor = f"{device_record.vendor or 'Unknown'} (Lab/{subnet_name})"

    return device_record
