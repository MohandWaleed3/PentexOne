import logging
from typing import List, Dict, Any, Optional
from database import Device, SessionLocal, Vulnerability, Setting
from datetime import datetime

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────
# Risk scoring weights (passive, read-only analysis only)
# ──────────────────────────────────────────────────────────
SEVERITY_SCORES = {
    "CRITICAL": 40.0,
    "HIGH":     25.0,
    "MEDIUM":   12.0,
    "LOW":       5.0,
}

# ──────────────────────────────────────────────────────────
# Service banner patterns for SSH weakness detection
# ──────────────────────────────────────────────────────────
WEAK_SSH_BANNERS = [
    "dropbear",         # Common in low-end IoT firmware
    "openssh_3",
    "openssh_4",
    "openssh_5",
    "libssh_0.5",
    "libssh_0.6",
]

# ──────────────────────────────────────────────────────────
# Known risky IoT vendor/hostname fingerprints
# ──────────────────────────────────────────────────────────
RISKY_IOT_VENDORS = [
    "hikvision", "dahua", "hanwha", "reolink",   # IP cameras
    "foscam", "amcrest", "uniview",
    "tp-link", "d-link", "netgear", "zyxel",     # Consumer routers
    "mikrotik", "ubiquiti",
    "shelly", "tuya", "sonoff", "espressif",      # Smart home
    "axis",                                        # Industrial cameras
]

# Vendor/hostname patterns that indicate default-cred risk
DEFAULT_CRED_HOSTNAME_PATTERNS = [
    "admin", "router", "gateway", "modem",
    "camera", "ipcam", "nvr", "dvr",
    "default", "setup",
]

# Passive firmware fingerprint indicators for IoT and wireless vendors
FIRMWARE_FINGERPRINT_PATTERNS = {
    "hikvision": "Hikvision",
    "dahua": "Dahua",
    "tp-link": "TP-Link",
    "xiaomi": "Xiaomi",
    "ubiquiti": "Ubiquiti",
    "esp": "Espressif",
    "sonoff": "Sonoff",
    "shelly": "Shelly",
}

# Wireless handshake weakness indicators
WEAK_WIFI_HANDSHAKES = ["TKIP", "WEP", "WPA", "WPA1", "WPA2", "CCMP", "TKIP/AES"]

# Display mapping for consistent risk labels
RISK_LABEL_MAP = {
    "SAFE":     "LOW",
    "LOW":      "LOW",
    "MEDIUM":   "MEDIUM",
    "RISK":     "HIGH",
    "HIGH":     "HIGH",
    "CRITICAL": "CRITICAL",
}


def format_risk_label(level: str) -> str:
    return RISK_LABEL_MAP.get((level or "").upper(), level or "UNKNOWN")

# ──────────────────────────────────────────────────────────
# Per-finding remediation database
# ──────────────────────────────────────────────────────────
REMEDIATION_MAP = {
    # Wireless
    "WIRELESS_WEP_ENCRYPTION":        "Replace WEP with WPA3 or WPA2-AES immediately. WEP can be cracked in minutes.",
    "WIRELESS_WPA1_ENCRYPTION":       "Upgrade to WPA2-AES or WPA3. WPA1 is deprecated and vulnerable to TKIP attacks.",
    "WIRELESS_OPEN_NETWORK":          "Enable WPA2/WPA3 encryption. Open networks expose all traffic to eavesdropping.",
    "WIRELESS_DEAUTH_VULN":           "Enable 802.11w (Management Frame Protection) on the AP to resist deauth attacks.",
    "WIRELESS_ROGUE_AP_INDICATOR":    "Verify all APs match your managed inventory. Investigate unexpected SSIDs.",
    "WIRELESS_DEFAULT_SSID":          "Change the SSID and default credentials. Default SSIDs suggest factory settings.",
    # Service Exposure
    "SERVICE_TELNET_OPEN":            "Disable Telnet (port 23) and replace with SSH. Telnet transmits credentials in cleartext.",
    "SERVICE_FTP_OPEN":               "Disable FTP (port 21). Use SFTP or SCP for secure file transfers.",
    "SERVICE_TFTP_OPEN":              "Disable TFTP (port 69) or restrict it with ACLs. It has no authentication.",
    "SERVICE_UNENCRYPTED_WEB_ADMIN":  "Enable HTTPS and redirect HTTP to HTTPS. Unencrypted admin panels expose credentials.",
    "SERVICE_WEAK_SSH_BANNER":        "Update firmware/SSH server to a current OpenSSH release. Old versions have known CVEs.",
    "SERVICE_CAPTIVE_PORTAL_MISC":    "Secure captive portal with HTTPS and short session timeouts.",
    "SERVICE_ALT_HTTP_NO_HTTPS":      "Ensure alternative HTTP port (8080) redirects to HTTPS or is firewall-restricted.",
    # IoT Risks
    "IOT_UPNP_EXPOSED":               "Disable UPnP (port 1900/SSDP). It allows automatic firewall hole-punching by any device.",
    "IOT_MDNS_EXPOSED":               "Restrict mDNS (port 5353) to local subnet only. It leaks device/service info.",
    "IOT_SSDP_LEAKAGE":               "Disable SSDP on internet-facing interfaces. Responses can amplify DDoS attacks.",
    "IOT_RISKY_VENDOR_FINGERPRINT":   "Check vendor security advisories for this device. Apply the latest firmware update.",
    "IOT_DEFAULT_CRED_INDICATOR":     "Change default credentials immediately. Default username/password patterns are well-known.",
    "IOT_TELNET_BOTNET_RISK":         "Disable Telnet on IoT devices. Mirai and similar botnets actively target open Telnet ports.",
    "IOT_UNENCRYPTED_ADMIN":          "Enable HTTPS on the admin interface. Unencrypted HTTP exposes login credentials.",
    "IOT_MQTT_UNAUTHENTICATED":       "Enable MQTT authentication and TLS. Unauthenticated MQTT brokers expose all IoT data.",
    "IOT_COAP_UNSECURED":             "Implement DTLS for CoAP to prevent eavesdropping and tampering.",
}


class SecurityAssessmentLayer:
    """
    Modular and optional Security Assessment Layer for IoT and Wi-Fi passive analysis.
    All analysis is strictly passive (read-only). No exploitation is performed.
    """

    @staticmethod
    def is_enabled(db) -> bool:
        setting = db.query(Setting).filter(Setting.key == "security_assessment_enabled").first()
        return setting and setting.value.lower() == "true"

    # ──────────────────────────────────────────────────────
    # 1. Wi-Fi SSID network analysis
    # ──────────────────────────────────────────────────────
    @staticmethod
    def analyze_wifi_networks(ssids: List[Dict]) -> List[Dict]:
        """
        Passive analysis of Wi-Fi networks for weak encryption and insecure defaults.
        """
        for network in ssids:
            security = network.get("security", "").upper()
            ssid = network.get("ssid", "")
            risk_flags = []

            # 1. Weak Encryption
            if "WEP" in security:
                risk_flags.append({
                    "type": "WEAK_ENCRYPTION",
                    "severity": "CRITICAL",
                    "desc": "WEP is highly insecure and can be cracked in minutes."
                })
            elif "WPA " in security or security == "WPA":
                risk_flags.append({
                    "type": "OUTDATED_ENCRYPTION",
                    "severity": "HIGH",
                    "desc": "WPA1 is outdated and vulnerable to various attacks."
                })
            elif security in ("OPEN", "NONE", ""):
                risk_flags.append({
                    "type": "OPEN_NETWORK",
                    "severity": "HIGH",
                    "desc": "Network is open, allowing eavesdropping."
                })

            # 2. Insecure SSIDs
            if not ssid or ssid.lower() == "hidden" or ssid == "<redacted>":
                risk_flags.append({
                    "type": "HIDDEN_SSID",
                    "severity": "LOW",
                    "desc": "Hidden SSIDs do not provide security and can sometimes leak information."
                })
            elif any(vendor in ssid.lower() for vendor in ["linksys", "netgear", "dlink", "tp-link", "default"]):
                risk_flags.append({
                    "type": "DEFAULT_SSID",
                    "severity": "MEDIUM",
                    "desc": "Default SSID detected, might indicate default credentials are also in use."
                })

            network["assessment_risks"] = risk_flags

        return ssids

    # ──────────────────────────────────────────────────────
    # 2. Comprehensive per-device deep assessment
    # ──────────────────────────────────────────────────────
    @staticmethod
    def analyze_device_detailed(device_id: int, nmap_data: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Comprehensive passive security assessment for Wi-Fi and IoT devices.

        Performs:
          • Wireless security findings (encryption, deauth vuln, rogue AP indicators)
          • Service exposure checks (Telnet, FTP, TFTP, HTTP admin, SSH banners)
          • IoT risk checks (UPnP, mDNS, SSDP, vendor fingerprints, default creds indicators)
          • Per-device remediation recommendations

        Returns a categorised findings dict and persists Vulnerability records to DB.
        No exploits, no active probing beyond passive banner/port analysis.
        """
        db = SessionLocal()
        findings = {
            "wireless_security": [],
            "service_exposure":  [],
            "iot_risks":         [],
            "recommendations":   [],
        }

        try:
            db_device = db.query(Device).filter(Device.id == device_id).first()
            if not db_device:
                return {"status": "error", "message": "Device not found"}

            open_ports = (
                [int(p.strip()) for p in db_device.open_ports.split(",") if p.strip().isdigit()]
                if db_device.open_ports else []
            )

            hostname  = (db_device.hostname  or "").lower()
            vendor    = (db_device.vendor    or "").lower()
            nmap_data = nmap_data or {}
            service_fingerprints = [p.lower() for p in nmap_data.get("service_fingerprints", []) if p]
            banner_text = (nmap_data.get("banner_text", "") or "").lower()

            new_vulns: List[Dict] = []

            # ── A. Wireless Security Findings ─────────────────────
            wifi_security = nmap_data.get("wifi_security", "").upper()
            if wifi_security:
                if "WEP" in wifi_security:
                    findings["wireless_security"].append({
                        "vuln_type":   "WIRELESS_WEP_ENCRYPTION",
                        "severity":    "CRITICAL",
                        "description": "WEP encryption detected — can be cracked in minutes using passive capture.",
                        "category":    "Wireless Security",
                    })
                    new_vulns.append(findings["wireless_security"][-1])

                elif "WPA1" in wifi_security or ("WPA" in wifi_security and "WPA2" not in wifi_security and "WPA3" not in wifi_security):
                    findings["wireless_security"].append({
                        "vuln_type":   "WIRELESS_WPA1_ENCRYPTION",
                        "severity":    "HIGH",
                        "description": "WPA1/TKIP encryption detected — deprecated and vulnerable to dictionary and TKIP attacks.",
                        "category":    "Wireless Security",
                    })
                    new_vulns.append(findings["wireless_security"][-1])

                elif any(token in wifi_security for token in ["OPEN", "NONE"]):
                    findings["wireless_security"].append({
                        "vuln_type":   "WIRELESS_OPEN_NETWORK",
                        "severity":    "HIGH",
                        "description": "Device is on an open or weak Wi-Fi network, exposing all traffic.",
                        "category":    "Wireless Security",
                    })
                    new_vulns.append(findings["wireless_security"][-1])

                for weak_marker in WEAK_WIFI_HANDSHAKES:
                    if weak_marker in wifi_security and weak_marker not in ["WPA", "WPA2"]:
                        findings["wireless_security"].append({
                            "vuln_type":   "WIRELESS_WEAK_HANDSHAKE",
                            "severity":    "MEDIUM",
                            "description": f"Weak Wi-Fi handshake/configuration detected ({wifi_security}). Upgrade to WPA2-AES or WPA3.",
                            "category":    "Wireless Security",
                        })
                        new_vulns.append(findings["wireless_security"][-1])
                        break

            # A2. Deauthentication vulnerability indicator (lack of 802.11w)
            if nmap_data.get("no_pmf", False) or (wifi_security and "PMF" not in wifi_security.upper()):
                if wifi_security or nmap_data.get("ssid"):
                    findings["wireless_security"].append({
                        "vuln_type":   "WIRELESS_DEAUTH_VULN",
                        "severity":    "MEDIUM",
                        "description": "No 802.11w/PMF (Protected Management Frames) detected — device may be vulnerable to deauthentication attacks.",
                        "category":    "Wireless Security",
                    })
                    new_vulns.append(findings["wireless_security"][-1])

            ssid_name = (nmap_data.get("ssid", "") or "").lower()
            if ssid_name and any(v in ssid_name for v in ["corp", "office", "guest", "free", "open", "public"]):
                findings["wireless_security"].append({
                    "vuln_type":   "WIRELESS_ROGUE_AP_INDICATOR",
                    "severity":    "HIGH",
                    "description": f"SSID '{ssid_name}' matches common rogue AP/evil twin patterns. Verify this AP is authorised.",
                    "category":    "Wireless Security",
                })
                new_vulns.append(findings["wireless_security"][-1])

            if any(pattern in hostname for pattern in ["guest", "free", "open", "public"]):
                findings["wireless_security"].append({
                    "vuln_type":   "WIRELESS_ROGUE_AP_INDICATOR",
                    "severity":    "MEDIUM",
                    "description": "Hostname suggests the device may be part of an untrusted or rogue wireless service.",
                    "category":    "Wireless Security",
                })
                new_vulns.append(findings["wireless_security"][-1])

            if any(v in ssid_name for v in ["linksys", "netgear", "dlink", "tp-link", "default"]):
                findings["wireless_security"].append({
                    "vuln_type":   "WIRELESS_DEFAULT_SSID",
                    "severity":    "MEDIUM",
                    "description": f"SSID '{ssid_name}' appears to use a default or vendor factory SSID.",
                    "category":    "Wireless Security",
                })
                new_vulns.append(findings["wireless_security"][-1])

            # ── B. Service Exposure ────────────────────────────────
            if 23 in open_ports:
                findings["service_exposure"].append({
                    "vuln_type":   "SERVICE_TELNET_OPEN",
                    "severity":    "CRITICAL",
                    "description": "Telnet (port 23) is open — transmits all data including credentials in plaintext.",
                    "category":    "Service Exposure",
                    "port":        23,
                    "protocol":    "TCP",
                })
                new_vulns.append(findings["service_exposure"][-1])

            if 21 in open_ports:
                findings["service_exposure"].append({
                    "vuln_type":   "SERVICE_FTP_OPEN",
                    "severity":    "CRITICAL",
                    "description": "FTP (port 21) is open — insecure file transfer, credentials sent in cleartext.",
                    "category":    "Service Exposure",
                    "port":        21,
                    "protocol":    "TCP",
                })
                new_vulns.append(findings["service_exposure"][-1])

            # B3. TFTP (port 69)
            if 69 in open_ports:
                findings["service_exposure"].append({
                    "vuln_type":   "SERVICE_TFTP_OPEN",
                    "severity":    "HIGH",
                    "description": "TFTP (port 69) is open — trivial file transfer with zero authentication.",
                    "category":    "Service Exposure",
                    "port":        69,
                    "protocol":    "UDP",
                })
                new_vulns.append(findings["service_exposure"][-1])

            # B4. Insecure Web Admin: HTTP (80 or 8080) without HTTPS (443 or 8443)
            has_http     = 80   in open_ports or 8080 in open_ports
            has_https    = 443  in open_ports or 8443 in open_ports
            if has_http and not has_https:
                primary_port = 80 if 80 in open_ports else 8080
                vuln_type    = "SERVICE_UNENCRYPTED_WEB_ADMIN" if primary_port == 80 else "SERVICE_ALT_HTTP_NO_HTTPS"
                findings["service_exposure"].append({
                    "vuln_type":   vuln_type,
                    "severity":    "HIGH",
                    "description": f"Web admin panel accessible over unencrypted HTTP (port {primary_port}) with no HTTPS equivalent detected.",
                    "category":    "Service Exposure",
                    "port":        primary_port,
                    "protocol":    "TCP",
                })
                new_vulns.append(findings["service_exposure"][-1])

            # B5. Weak SSH banner analysis (passive — from nmap service scan data)
            ssh_banner = nmap_data.get("ssh_banner", "").lower()
            if ssh_banner and any(pattern in ssh_banner for pattern in WEAK_SSH_BANNERS):
                findings["service_exposure"].append({
                    "vuln_type":   "SERVICE_WEAK_SSH_BANNER",
                    "severity":    "HIGH",
                    "description": f"Weak/outdated SSH server detected (banner: {ssh_banner[:80]}). Update to current OpenSSH.",
                    "category":    "Service Exposure",
                    "port":        22,
                    "protocol":    "TCP",
                })
                new_vulns.append(findings["service_exposure"][-1])

            # B6. Captive portal misconfiguration indicator
            if 8080 in open_ports and 80 in open_ports and not has_https:
                findings["service_exposure"].append({
                    "vuln_type":   "SERVICE_CAPTIVE_PORTAL_MISC",
                    "severity":    "MEDIUM",
                    "description": "Both port 80 and 8080 open without HTTPS — possible insecure captive portal misconfiguration.",
                    "category":    "Service Exposure",
                    "port":        8080,
                    "protocol":    "TCP",
                })
                new_vulns.append(findings["service_exposure"][-1])

            # ── C. IoT Risks ───────────────────────────────────────
            # C1. UPnP / SSDP (port 1900)
            if 1900 in open_ports:
                findings["iot_risks"].append({
                    "vuln_type":   "IOT_UPNP_EXPOSED",
                    "severity":    "HIGH",
                    "description": "UPnP/SSDP (port 1900) is exposed — can allow malicious devices to modify NAT rules and expose internal services.",
                    "category":    "IoT Risk",
                    "port":        1900,
                    "protocol":    "UDP",
                })
                new_vulns.append(findings["iot_risks"][-1])

            # C2. mDNS (port 5353)
            if 5353 in open_ports:
                findings["iot_risks"].append({
                    "vuln_type":   "IOT_MDNS_EXPOSED",
                    "severity":    "LOW",
                    "description": "mDNS (port 5353) is exposed — leaks device names, service types, and network topology.",
                    "category":    "IoT Risk",
                    "port":        5353,
                    "protocol":    "UDP",
                })
                new_vulns.append(findings["iot_risks"][-1])

            # C3. MQTT (port 1883 — unencrypted IoT broker)
            if 1883 in open_ports:
                findings["iot_risks"].append({
                    "vuln_type":   "IOT_MQTT_UNAUTHENTICATED",
                    "severity":    "HIGH",
                    "description": "MQTT broker (port 1883) open without TLS — IoT data transmitted in cleartext.",
                    "category":    "IoT Risk",
                    "port":        1883,
                    "protocol":    "TCP",
                })
                new_vulns.append(findings["iot_risks"][-1])

            # C4. CoAP (port 5683)
            if 5683 in open_ports:
                findings["iot_risks"].append({
                    "vuln_type":   "IOT_COAP_UNSECURED",
                    "severity":    "MEDIUM",
                    "description": "CoAP (port 5683) is open without DTLS — IoT protocol data is unencrypted.",
                    "category":    "IoT Risk",
                    "port":        5683,
                    "protocol":    "UDP",
                })
                new_vulns.append(findings["iot_risks"][-1])

            # C5. Known risky IoT vendor fingerprint
            if any(risky_v in vendor for risky_v in RISKY_IOT_VENDORS):
                findings["iot_risks"].append({
                    "vuln_type":   "IOT_RISKY_VENDOR_FINGERPRINT",
                    "severity":    "MEDIUM",
                    "description": f"Vendor '{db_device.vendor}' has a history of security vulnerabilities. Check for firmware updates and security advisories.",
                    "category":    "IoT Risk",
                    "port":        None,
                    "protocol":    "IoT-Passive",
                })
                new_vulns.append(findings["iot_risks"][-1])

            # C6. Default credentials indicator (hostname/banner patterns)
            if any(pattern in hostname for pattern in DEFAULT_CRED_HOSTNAME_PATTERNS):
                findings["iot_risks"].append({
                    "vuln_type":   "IOT_DEFAULT_CRED_INDICATOR",
                    "severity":    "HIGH",
                    "description": f"Hostname '{db_device.hostname}' matches default device naming patterns, strongly indicating factory-default credentials may still be in use.",
                    "category":    "IoT Risk",
                    "port":        None,
                    "protocol":    "IoT-Passive",
                })
                new_vulns.append(findings["iot_risks"][-1])

            # C7. Telnet + IoT = botnet magnet
            if 23 in open_ports and (
                any(risky_v in vendor for risky_v in RISKY_IOT_VENDORS) or
                "camera" in hostname or "cam" in hostname or "dvr" in hostname
            ):
                findings["iot_risks"].append({
                    "vuln_type":   "IOT_TELNET_BOTNET_RISK",
                    "severity":    "CRITICAL",
                    "description": "Telnet open on an IoT/camera device — this profile exactly matches Mirai botnet infection targets.",
                    "category":    "IoT Risk",
                    "port":        23,
                    "protocol":    "TCP",
                })
                new_vulns.append(findings["iot_risks"][-1])

            # ── D. Persist vulnerabilities to DB ──────────────────
            score_increase = 0.0
            for v in new_vulns:
                # Avoid duplicate vuln entries
                existing = db.query(Vulnerability).filter(
                    Vulnerability.device_id == db_device.id,
                    Vulnerability.vuln_type == v["vuln_type"]
                ).first()

                if not existing:
                    db.add(Vulnerability(
                        device_id=db_device.id,
                        vuln_type=v["vuln_type"],
                        severity=v["severity"],
                        description=v["description"],
                        port=v.get("port"),
                        protocol=v.get("protocol", "IoT-Passive"),
                    ))
                    score_increase += SEVERITY_SCORES.get(v["severity"], 5.0)

            # Update device risk score and level
            if score_increase > 0:
                db_device.risk_score = min(100.0, db_device.risk_score + score_increase)
                _update_risk_level(db_device)

            # ── E. Per-device recommendations ──────────────────────
            seen_recs = set()
            for v in new_vulns:
                rec = REMEDIATION_MAP.get(v["vuln_type"])
                if rec and rec not in seen_recs:
                    findings["recommendations"].append({
                        "vuln_type": v["vuln_type"],
                        "severity":  v["severity"],
                        "action":    rec,
                    })
                    seen_recs.add(rec)

            db.commit()

            return {
                "status":   "success",
                "device_id": device_id,
                "findings":  findings,
                "total_new_vulns": len(new_vulns),
            }

        except Exception as e:
            logger.error(f"Error in analyze_device_detailed for device {device_id}: {e}")
            db.rollback()
            return {"status": "error", "message": str(e)}
        finally:
            db.close()

    # ──────────────────────────────────────────────────────
    # 3. Legacy: basic IoT port-only analysis (kept for compat)
    # ──────────────────────────────────────────────────────
    @staticmethod
    def analyze_iot_devices(device_id: int) -> None:
        """
        Passive analysis of an IoT device for risky protocols and patterns.
        Updates the device's vulnerabilities in the database.
        """
        db = SessionLocal()
        try:
            db_device = db.query(Device).filter(Device.id == device_id).first()
            if not db_device:
                return

            open_ports = (
                [int(p) for p in db_device.open_ports.split(",") if p.strip().isdigit()]
                if db_device.open_ports else []
            )
            new_vulns = []

            if 1900 in open_ports:
                new_vulns.append({"vuln_type": "IOT_UPNP_EXPOSED",      "severity": "MEDIUM", "desc": "UPnP is exposed, which might allow malicious network reconfiguration."})
            if 5353 in open_ports:
                new_vulns.append({"vuln_type": "IOT_MDNS_EXPOSED",      "severity": "LOW",    "desc": "mDNS exposed, potentially leaking device information."})
            if 23 in open_ports:
                new_vulns.append({"vuln_type": "IOT_TELNET_ENABLED",    "severity": "CRITICAL","desc": "Telnet is enabled on an IoT device, highly vulnerable to botnets."})
            if 80 in open_ports and 443 not in open_ports:
                new_vulns.append({"vuln_type": "IOT_UNENCRYPTED_ADMIN", "severity": "HIGH",   "desc": "Unencrypted HTTP admin panel exposed."})

            for v in new_vulns:
                existing = db.query(Vulnerability).filter(
                    Vulnerability.device_id == db_device.id,
                    Vulnerability.vuln_type == v["vuln_type"]
                ).first()

                if not existing:
                    db.add(Vulnerability(
                        device_id=db_device.id,
                        vuln_type=v["vuln_type"],
                        severity=v["severity"],
                        description=v["desc"],
                        protocol="IoT-Passive"
                    ))
                    db_device.risk_score = min(100.0, db_device.risk_score + SEVERITY_SCORES.get(v["severity"], 5.0))
                    _update_risk_level(db_device)

            db.commit()
        except Exception as e:
            logger.error(f"Error in analyze_iot_devices: {e}")
        finally:
            db.close()

    # ──────────────────────────────────────────────────────
    # 4. Assessment report generator
    # ──────────────────────────────────────────────────────
    @staticmethod
    def generate_report() -> Dict[str, Any]:
        """
        Generates a structured security assessment report.
        """
        db = SessionLocal()
        try:
            devices = db.query(Device).all()
            total_devices   = len(devices)
            critical_devices = [d for d in devices if d.risk_level in ("RISK", "CRITICAL")]
            high_devices     = [d for d in devices if d.risk_level == "HIGH"]
            medium_devices   = [d for d in devices if d.risk_level in ("MEDIUM",)]
            safe_devices     = [d for d in devices if d.risk_level == "SAFE"]

            report = {
                "timestamp": datetime.utcnow().isoformat(),
                "summary": {
                    "total_devices":    total_devices,
                    "critical_devices": len(critical_devices),
                    "high_devices":     len(high_devices),
                    "medium_devices":   len(medium_devices),
                    "safe_devices":     len(safe_devices),
                },
                "high_risk_details": [],
                "recommendations":   [],
            }

            for d in critical_devices + high_devices:
                vulns = db.query(Vulnerability).filter(Vulnerability.device_id == d.id).all()
                report["high_risk_details"].append({
                    "ip":       d.ip,
                    "mac":      d.mac,
                    "hostname": d.hostname,
                    "vendor":   d.vendor,
                    "score":    d.risk_score,
                    "level":    d.risk_level,
                    "issues":   [{"type": v.vuln_type, "severity": v.severity, "desc": v.description} for v in vulns],
                })

            if len(critical_devices) > 0 or len(high_devices) > 0:
                report["recommendations"] += [
                    "Isolate high-risk IoT devices on a separate guest network immediately.",
                    "Disable Telnet, UPnP, and unencrypted HTTP admin panels where possible.",
                    "Change all default credentials immediately on flagged devices.",
                    "Apply available firmware updates to all IoT devices.",
                    "Enable 802.11w (PMF) on your Wi-Fi access point to resist deauth attacks.",
                ]
            else:
                report["recommendations"].append("Continue monitoring the network periodically.")

            return {"status": "success", "report": report}
        except Exception as e:
            logger.error(f"Error generating assessment report: {e}")
            return {"status": "error", "message": str(e)}
        finally:
            db.close()


# ──────────────────────────────────────────────────────────
# Helper: update risk level from score
# ──────────────────────────────────────────────────────────
def _update_risk_level(device) -> None:
    """Map numeric risk_score to a 4-tier risk_level label."""
    score = device.risk_score
    if score >= 70.0:
        device.risk_level = "CRITICAL"
    elif score >= 40.0:
        device.risk_level = "RISK"
    elif score > 0.0:
        device.risk_level = "MEDIUM"
    else:
        device.risk_level = "SAFE"
