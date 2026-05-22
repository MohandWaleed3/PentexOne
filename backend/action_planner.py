"""
AI Prioritized Action Plan
==========================

Turns a flat list of vulnerabilities across many devices into a small,
ordered playbook the user can actually execute.

Each action is scored on three axes:

    priority  =  (exploitability  *  impact)  /  effort

- exploitability : how easy to weaponise (0–10)
- impact         : blast radius if exploited (0–10)
- effort         : minutes to fully remediate (1–60)

The planner also clusters identical findings across devices into a single
"do once, fix many" action and estimates how much each step reduces the
network's overall risk score.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional, Tuple


# ─── Domain knowledge: vuln class → (exploitability, impact, effort_min, fix) ──
#
# Effort is the realistic time for a non-expert user to apply the fix.
# Exploitability/impact are 0–10 ratings drawn from MITRE ATT&CK + OWASP
# weighting for the common IoT/home-network threat model.
#
ACTION_TEMPLATES: Dict[str, Dict] = {
    # ── Critical authentication / RCE ──────────────────────────────────
    "OPEN_TELNET": {
        "title": "Disable Telnet on {device}",
        "category": "Authentication",
        "exploitability": 10, "impact": 10, "effort": 5,
        "steps": [
            "Log into the device's admin panel",
            "Locate the service / remote-access menu",
            "Disable Telnet completely",
            "If a firmware update is available, install it",
        ],
        "why": "Telnet sends credentials in plaintext and is the #1 vector for Mirai-style botnets.",
    },
    "OPEN_FTP": {
        "title": "Disable FTP on {device}",
        "category": "Authentication",
        "exploitability": 9, "impact": 8, "effort": 5,
        "steps": [
            "Disable FTP in the device's services menu",
            "If file sharing is needed, use SFTP / SMB v3 with auth",
        ],
        "why": "FTP credentials and file contents travel in cleartext.",
    },
    "SMB_OPEN": {
        "title": "Patch / firewall SMB on {device}",
        "category": "Authentication",
        "exploitability": 10, "impact": 10, "effort": 15,
        "steps": [
            "Apply the latest OS patches (EternalBlue is fixed in MS17-010)",
            "Block port 445 at the router for WAN traffic",
            "Disable SMBv1 if still enabled",
        ],
        "why": "SMB is the EternalBlue / WannaCry vector — patched but still widely abused.",
    },
    "RDP_OPEN": {
        "title": "Lock down RDP on {device}",
        "category": "Authentication",
        "exploitability": 8, "impact": 9, "effort": 10,
        "steps": [
            "Restrict RDP to specific IPs via firewall",
            "Enforce Network Level Authentication (NLA)",
            "Use a strong unique password + MFA if possible",
        ],
        "why": "RDP brute-force and BlueKeep remain top ransomware entry points.",
    },
    "DEFAULT_CREDENTIALS": {
        "title": "Change default credentials on {device}",
        "category": "Authentication",
        "exploitability": 10, "impact": 9, "effort": 3,
        "steps": [
            "Open the device's web interface",
            "Set a unique password (16+ characters, manager-stored)",
            "Disable any guest / debug accounts",
        ],
        "why": "Default creds are the single highest-ROI attack — fixing one device prevents most amateur intrusions.",
    },
    "IOT_TELNET_BOTNET_RISK": {
        "title": "Disable Telnet immediately on {device}",
        "category": "Authentication",
        "exploitability": 10, "impact": 10, "effort": 5,
        "steps": [
            "Disable Telnet (admin panel → services)",
            "Reset the device to factory defaults if unsure of integrity",
            "Update firmware before reconnecting to network",
        ],
        "why": "This device matches the Mirai botnet infection profile — assume compromise possible.",
    },

    # ── High-risk wireless ─────────────────────────────────────────────
    "WIRELESS_WEP_ENCRYPTION": {
        "title": "Upgrade Wi-Fi encryption from WEP to WPA3",
        "category": "Wireless",
        "exploitability": 10, "impact": 9, "effort": 10,
        "steps": [
            "Open the router admin page",
            "Wireless settings → Security mode → WPA3 (or WPA2-AES if WPA3 unavailable)",
            "Set a 16+ character passphrase",
        ],
        "why": "WEP can be cracked in minutes using passive capture — anyone within range is on your LAN.",
    },
    "WIRELESS_WPA1_ENCRYPTION": {
        "title": "Upgrade Wi-Fi from WPA1/TKIP to WPA2/WPA3",
        "category": "Wireless",
        "exploitability": 7, "impact": 8, "effort": 10,
        "steps": [
            "Router admin → Wireless security → WPA2-AES or WPA3",
            "Re-connect all devices with the new password",
        ],
        "why": "WPA1/TKIP is deprecated and vulnerable to dictionary attacks.",
    },
    "WIRELESS_OPEN_NETWORK": {
        "title": "Set a passphrase on the open Wi-Fi network",
        "category": "Wireless",
        "exploitability": 10, "impact": 9, "effort": 5,
        "steps": [
            "Router admin → Wireless → enable WPA2/WPA3",
            "Apply a strong unique passphrase",
        ],
        "why": "Anyone nearby is on your LAN — they see your traffic and can pivot.",
    },

    # ── IoT exposure ───────────────────────────────────────────────────
    "IOT_MQTT_UNAUTHENTICATED": {
        "title": "Enable authentication + TLS on MQTT broker",
        "category": "IoT",
        "exploitability": 8, "impact": 8, "effort": 15,
        "steps": [
            "Edit mosquitto.conf / broker config: set `allow_anonymous false`",
            "Add user/password file (`mosquitto_passwd`)",
            "Configure TLS certificates for port 8883",
        ],
        "why": "Open MQTT is the #1 IoT data leak — sensor data + commands exposed.",
    },
    "IOT_UPNP_EXPOSED": {
        "title": "Disable UPnP on the router",
        "category": "Network",
        "exploitability": 7, "impact": 7, "effort": 5,
        "steps": [
            "Router admin → Advanced → UPnP → Disable",
            "Manually port-forward only what's truly required",
        ],
        "why": "UPnP lets any LAN device punch holes in your firewall to the internet.",
    },
    "IOT_DEFAULT_CRED_INDICATOR": {
        "title": "Verify and rotate credentials on {device}",
        "category": "Authentication",
        "exploitability": 9, "impact": 8, "effort": 5,
        "steps": [
            "Hostname suggests factory defaults — log in and change immediately",
            "Disable remote access if not needed",
        ],
        "why": "Device naming pattern indicates factory defaults are likely active.",
    },

    # ── Medium ─────────────────────────────────────────────────────────
    "HTTP_OPEN": {
        "title": "Disable HTTP admin / force HTTPS on {device}",
        "category": "Web",
        "exploitability": 5, "impact": 6, "effort": 10,
        "steps": [
            "Router/device admin → enable HTTPS only",
            "Install a valid certificate if available",
        ],
        "why": "Plaintext HTTP exposes session cookies and admin credentials over the LAN.",
    },
    "MQTT_OPEN": {
        "title": "Authenticate the MQTT broker",
        "category": "IoT",
        "exploitability": 7, "impact": 7, "effort": 15,
        "steps": [
            "Set `allow_anonymous false`",
            "Create user/password",
            "Restart broker",
        ],
        "why": "Open MQTT leaks IoT telemetry and accepts attacker commands.",
    },
    "ALT_HTTP": {
        "title": "Restrict alternative HTTP admin port on {device}",
        "category": "Web",
        "exploitability": 4, "impact": 5, "effort": 5,
        "steps": [
            "Disable the alternate admin port if unused",
            "Or restrict it to LAN-only via firewall rules",
        ],
        "why": "Admin panels on non-standard ports are often overlooked but still exploitable.",
    },

    # ── Low ────────────────────────────────────────────────────────────
    "SSH_OPEN": {
        "title": "Harden SSH on {device}",
        "category": "Authentication",
        "exploitability": 3, "impact": 6, "effort": 10,
        "steps": [
            "Disable password authentication, use keys",
            "Disable root login over SSH",
            "Change to a non-default port for casual scanners",
        ],
        "why": "SSH is generally safe — but only with strong keys and no root login.",
    },
    "MDNS_OPEN": {
        "title": "Disable mDNS broadcast on {device}",
        "category": "Network",
        "exploitability": 2, "impact": 3, "effort": 5,
        "steps": [
            "Disable mDNS/Bonjour if not actively used",
            "Or segment IoT devices on a separate VLAN",
        ],
        "why": "mDNS leaks device names and services — reconnaissance value, low direct risk.",
    },
}

# Generic fallbacks per CVSS severity for unknown vuln types (incl. CVEs)
SEVERITY_DEFAULTS = {
    "CRITICAL": {"exploitability": 9, "impact": 9, "effort": 20,
                 "category": "Patch", "why": "CVSS critical — actively exploited in the wild."},
    "HIGH":     {"exploitability": 7, "impact": 7, "effort": 15,
                 "category": "Patch", "why": "CVSS high — exploits are publicly available."},
    "MEDIUM":   {"exploitability": 4, "impact": 5, "effort": 10,
                 "category": "Patch", "why": "CVSS medium — exploit requires conditions but should still be patched."},
    "LOW":      {"exploitability": 2, "impact": 3, "effort": 5,
                 "category": "Hygiene", "why": "Low severity — fix during routine maintenance."},
    "SAFE":     {"exploitability": 1, "impact": 1, "effort": 5,
                 "category": "Hygiene", "why": "Informational."},
}


def _template_for(vuln_type: str, severity: str) -> Tuple[Dict, bool]:
    """Return (template_dict, is_specific). is_specific=False means generic fallback."""
    if vuln_type in ACTION_TEMPLATES:
        return ACTION_TEMPLATES[vuln_type], True
    sev = (severity or "MEDIUM").upper()
    base = SEVERITY_DEFAULTS.get(sev, SEVERITY_DEFAULTS["MEDIUM"]).copy()
    base["title"] = f"Mitigate {vuln_type} on {{device}}"
    base["steps"] = [
        "Identify the affected service / component",
        "Apply vendor patches or firmware updates",
        "Verify the fix with a re-scan",
    ]
    return base, False


def _device_label(d: Dict) -> str:
    name = d.get("hostname") or d.get("vendor") or "device"
    ip = d.get("ip") or ""
    if ip and not ip.startswith(("ZB:", "ZW:", "BLE_", "TH:")):
        return f"{name} ({ip})"
    return name


def _bucket(score: float) -> str:
    if score >= 8:  return "CRITICAL"
    if score >= 5:  return "HIGH"
    if score >= 2.5: return "MEDIUM"
    return "LOW"


def generate_action_plan(
    devices: List[Dict],
    max_actions: int = 8,
) -> Dict:
    """
    devices: list of dicts shaped like
        {
          "id":..., "ip":..., "hostname":..., "vendor":...,
          "risk_level":..., "risk_score":...,
          "vulnerabilities": [{"vuln_type":..., "severity":..., "description":..., "port":...}]
        }

    Returns a dict ready for the API:
        {
          "actions": [...],
          "summary": {...},
        }
    """
    # 1.  Cluster vulnerabilities by type across devices
    clusters: Dict[str, Dict] = defaultdict(
        lambda: {"vuln_type": "", "severity": "MEDIUM", "max_epss": 0.0,
                 "actively_exploited": False,
                 "devices": [], "ports": set(), "descriptions": []}
    )

    total_devices = len(devices)
    total_vulns = 0

    for dev in devices:
        for v in dev.get("vulnerabilities") or []:
            vt = v.get("vuln_type") or v.get("id") or "UNKNOWN"
            sev = (v.get("severity") or v.get("risk_level") or "MEDIUM").upper()
            c = clusters[vt]
            c["vuln_type"] = vt
            # Track the worst observed severity for this cluster
            sev_rank = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "SAFE": 0}
            if sev_rank.get(sev, 2) > sev_rank.get(c["severity"], 2):
                c["severity"] = sev
            # Track the highest EPSS score for this cluster (active exploitation signal)
            epss = v.get("epss_score") or 0.0
            if epss > c["max_epss"]:
                c["max_epss"] = epss
            if v.get("actively_exploited"):
                c["actively_exploited"] = True
            c["devices"].append(_device_label(dev))
            if v.get("port"):
                c["ports"].add(v["port"])
            if v.get("description"):
                c["descriptions"].append(v["description"])
            total_vulns += 1

    # 2.  Score each cluster
    actions: List[Dict] = []
    for vt, cluster in clusters.items():
        template, is_specific = _template_for(vt, cluster["severity"])

        # Multi-device clusters get an impact bonus
        affected = len(cluster["devices"])
        breadth_multiplier = 1.0 + min(0.5, 0.1 * (affected - 1))

        exploitability = template["exploitability"]
        impact = template["impact"] * breadth_multiplier
        effort = max(1, template["effort"])

        priority_score = (exploitability * impact) / effort
        # Boost critical severity into priority even if effort is high
        if cluster["severity"] == "CRITICAL":
            priority_score += 3
        elif cluster["severity"] == "HIGH":
            priority_score += 1

        # EPSS boost: actively-exploited threats jump to the top of the queue.
        # epss=0.7 → +3.5  ;  epss=0.95 → +4.75 (puts it ahead of dormant CRITICALs)
        if cluster["max_epss"] >= 0.70:
            priority_score += 5 * cluster["max_epss"]
        elif cluster["max_epss"] >= 0.30:
            priority_score += 2 * cluster["max_epss"]

        # Friendly title: collapse to "N devices" when many affected
        device_phrase = (
            cluster["devices"][0]
            if affected == 1
            else f"{affected} devices"
        )
        title = template["title"].replace("{device}", device_phrase)

        actions.append({
            "id": vt,
            "title": title,
            "category": template["category"],
            "severity": cluster["severity"],
            "priority_score": round(priority_score, 2),
            "priority_bucket": _bucket(priority_score),
            "estimated_minutes": template["effort"],
            "affected_devices": cluster["devices"][:10],
            "affected_count": affected,
            "ports": sorted(cluster["ports"]),
            "steps": template["steps"],
            "why_it_matters": template["why"],
            "is_specific": is_specific,
            "max_epss": round(cluster["max_epss"], 4),
            "actively_exploited": cluster["actively_exploited"],
        })

    # 3.  Sort and rank
    actions.sort(key=lambda a: a["priority_score"], reverse=True)

    # 4.  Compute "fix this and reduce risk by X%" estimates
    total_severity_weight = sum(
        {"CRITICAL": 10, "HIGH": 7, "MEDIUM": 4, "LOW": 2, "SAFE": 0}.get(a["severity"], 4)
        * a["affected_count"]
        for a in actions
    ) or 1

    cumulative = 0
    for i, a in enumerate(actions):
        weight = {"CRITICAL": 10, "HIGH": 7, "MEDIUM": 4, "LOW": 2, "SAFE": 0}.get(a["severity"], 4)
        a["risk_reduction_pct"] = round(100 * weight * a["affected_count"] / total_severity_weight, 1)
        cumulative += a["risk_reduction_pct"]
        a["cumulative_reduction_pct"] = round(min(cumulative, 100.0), 1)
        a["rank"] = i + 1

    top_actions = actions[:max_actions]
    total_minutes = sum(a["estimated_minutes"] for a in top_actions)

    # 5.  Summary
    crit_actions = sum(1 for a in actions if a["priority_bucket"] == "CRITICAL")
    quick_wins = [
        a for a in actions
        if a["estimated_minutes"] <= 5 and a["severity"] in ("CRITICAL", "HIGH")
    ][:3]

    return {
        "actions": top_actions,
        "total_actions_available": len(actions),
        "summary": {
            "total_devices_scanned": total_devices,
            "total_vulnerabilities": total_vulns,
            "critical_actions": crit_actions,
            "estimated_total_minutes": total_minutes,
            "estimated_total_label": _format_minutes(total_minutes),
            "first_step_reduction_pct": top_actions[0]["risk_reduction_pct"] if top_actions else 0,
            "quick_wins": [{"title": a["title"], "minutes": a["estimated_minutes"]} for a in quick_wins],
        },
    }


def _format_minutes(m: int) -> str:
    if m < 60:
        return f"{m} min"
    h = m // 60
    rem = m % 60
    return f"{h}h {rem}m" if rem else f"{h}h"
