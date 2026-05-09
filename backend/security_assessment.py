import logging
from typing import List, Dict, Any
from database import Device, SessionLocal, Vulnerability, Setting
from datetime import datetime

logger = logging.getLogger(__name__)

class SecurityAssessmentLayer:
    """
    Modular and optional Security Assessment Layer for IoT and Wi-Fi passive analysis.
    """
    
    @staticmethod
    def is_enabled(db) -> bool:
        setting = db.query(Setting).filter(Setting.key == "security_assessment_enabled").first()
        return setting and setting.value.lower() == "true"
        
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
                risk_flags.append({"type": "WEAK_ENCRYPTION", "severity": "CRITICAL", "desc": "WEP is highly insecure and can be cracked in minutes."})
            elif "WPA " in security or security == "WPA":
                risk_flags.append({"type": "OUTDATED_ENCRYPTION", "severity": "HIGH", "desc": "WPA1 is outdated and vulnerable to various attacks."})
            elif security == "OPEN" or security == "NONE" or not security:
                risk_flags.append({"type": "OPEN_NETWORK", "severity": "HIGH", "desc": "Network is open, allowing eavesdropping."})
                
            # 2. Insecure SSIDs (Hidden or Default Vendor)
            if not ssid or ssid.lower() == "hidden" or ssid == "<redacted>":
                risk_flags.append({"type": "HIDDEN_SSID", "severity": "LOW", "desc": "Hidden SSIDs do not provide security and can sometimes leak information."})
            elif any(vendor in ssid.lower() for vendor in ["linksys", "netgear", "dlink", "tp-link", "default"]):
                risk_flags.append({"type": "DEFAULT_SSID", "severity": "MEDIUM", "desc": "Default SSID detected, might indicate default credentials are also in use."})
                
            network["assessment_risks"] = risk_flags
            
        return ssids

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
                
            open_ports = [int(p) for p in db_device.open_ports.split(",")] if db_device.open_ports else []
            new_vulns = []
            
            # 1. Risky Protocols in IoT
            if 1900 in open_ports:
                new_vulns.append({"vuln_type": "IOT_UPNP_EXPOSED", "severity": "MEDIUM", "desc": "UPnP is exposed, which might allow malicious network reconfiguration."})
            if 5353 in open_ports:
                new_vulns.append({"vuln_type": "IOT_MDNS_EXPOSED", "severity": "LOW", "desc": "mDNS exposed, potentially leaking device information."})
            if 23 in open_ports:
                new_vulns.append({"vuln_type": "IOT_TELNET_ENABLED", "severity": "CRITICAL", "desc": "Telnet is enabled on an IoT device, highly vulnerable to botnets."})
            if 80 in open_ports and not 443 in open_ports:
                new_vulns.append({"vuln_type": "IOT_UNENCRYPTED_ADMIN", "severity": "HIGH", "desc": "Unencrypted HTTP admin panel exposed."})
                
            # 2. Add to existing vulnerabilities
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
                    
                    score_increase = 30.0 if v["severity"] == "CRITICAL" else (20.0 if v["severity"] == "HIGH" else (10.0 if v["severity"] == "MEDIUM" else 5.0))
                    db_device.risk_score = min(100.0, db_device.risk_score + score_increase)
                    
                    if db_device.risk_score > 40.0:
                        db_device.risk_level = "RISK"
                    elif db_device.risk_score > 0.0 and db_device.risk_level == "SAFE":
                        db_device.risk_level = "MEDIUM"

            db.commit()
        except Exception as e:
            logger.error(f"Error in analyze_iot_devices: {e}")
        finally:
            db.close()

    @staticmethod
    def analyze_device_detailed(device_id: int, nm_data: Any) -> None:
        """
        Comprehensive passive security assessment for a device using nmap data.
        Categories to detect:
        - SERVICE_EXPOSURE -> 'Service Fingerprint' / 'IoT Risk'
        - IOT_RISK -> 'IoT Risk'
        - WIRELESS_SECURITY -> 'Wireless Security Finding'
        - RECOMMENDATIONS -> 'Recommendation'
        """
        db = SessionLocal()
        try:
            if not SecurityAssessmentLayer.is_enabled(db):
                return
                
            device = db.query(Device).filter(Device.id == device_id).first()
            if not device:
                return
                
            ip = device.ip
            new_vulns = []
            
            if ip in nm_data.all_hosts():
                host_data = nm_data[ip]
                
                for proto in host_data.all_protocols():
                    ports = host_data[proto].keys()
                    for port in ports:
                        state = host_data[proto][port]["state"]
                        if state != "open":
                            continue
                            
                        svc_name = host_data[proto][port].get("name", "")
                        svc_product = host_data[proto][port].get("product", "")
                        svc_version = host_data[proto][port].get("version", "")
                        
                        if svc_product or svc_version or svc_name:
                            # Service Fingerprints
                            new_vulns.append({
                                "vuln_type": f"SVC_{svc_name.upper()}",
                                "severity": "INFO",
                                "desc": f"Fingerprint: {svc_name} {svc_product} {svc_version}".strip(),
                                "port": port,
                                "protocol": "Service Fingerprint"
                            })
                        
                        # 1. IoT Risks and Service Exposure Checks
                        if port in [21, 69]:
                            new_vulns.append({"vuln_type": "INSECURE_FILE_TRANSFER", "severity": "HIGH", "desc": "FTP/TFTP exposed. Data is transferred unencrypted.", "port": port, "protocol": "IoT Risk"})
                        if port in [23, 2323]:
                            new_vulns.append({"vuln_type": "TELNET_EXPOSED", "severity": "CRITICAL", "desc": "Telnet exposed. Vulnerable to interception and brute-force.", "port": port, "protocol": "IoT Risk"})
                        if port in [80, 8080, 8888] and not 443 in ports:
                            new_vulns.append({"vuln_type": "INSECURE_WEB_ADMIN", "severity": "HIGH", "desc": "Unencrypted web interface. Credentials may be intercepted.", "port": port, "protocol": "IoT Risk"})
                        if port == 22:
                            new_vulns.append({"vuln_type": "SSH_EXPOSED", "severity": "LOW", "desc": "SSH is open. Ensure strong keys/passwords and disable root login.", "port": port, "protocol": "IoT Risk"})
                            
                        if port == 1900 or svc_name == "upnp":
                            new_vulns.append({"vuln_type": "UPNP_EXPOSURE", "severity": "MEDIUM", "desc": "UPnP exposed. May allow malicious network reconfiguration.", "port": port, "protocol": "IoT Risk"})
                        if port == 5353 or svc_name == "mdns":
                            new_vulns.append({"vuln_type": "MDNS_LEAKAGE", "severity": "LOW", "desc": "mDNS exposed. Leaks local network topology.", "port": port, "protocol": "IoT Risk"})
                        if "camera" in svc_product.lower() or "dahua" in svc_product.lower() or "hikvision" in svc_product.lower():
                            new_vulns.append({"vuln_type": "RISKY_IOT_CAMERA", "severity": "HIGH", "desc": f"IP Camera interface detected ({svc_product}). Often target for botnets.", "port": port, "protocol": "IoT Risk"})
                            
                        # Default Credentials Indicators
                        if "admin" in str(svc_product).lower() or "default" in str(svc_product).lower():
                            new_vulns.append({"vuln_type": "DEFAULT_CREDS_INDICATOR", "severity": "MEDIUM", "desc": f"Service banner indicates possible default configuration.", "port": port, "protocol": "IoT Risk"})
                            
            # 2. Wireless Security Findings (Inferred from device metadata)
            if device.os_guess and ("router" in device.os_guess.lower() or "access point" in device.os_guess.lower()):
                new_vulns.append({"vuln_type": "ROUTER_EXPOSURE", "severity": "MEDIUM", "desc": "Device appears to be a router/AP. Verify management interface is not public.", "port": None, "protocol": "Wireless Security Finding"})
            
            # Additional captive portal check
            if 80 in [p.port for p in new_vulns if p.get('port')]:
                new_vulns.append({"vuln_type": "CAPTIVE_PORTAL_CHECK", "severity": "LOW", "desc": "Open HTTP port could indicate a captive portal or unencrypted admin panel.", "port": 80, "protocol": "Wireless Security Finding"})

            # Recommendations
            recs = []
            has_critical = any(v["severity"] == "CRITICAL" for v in new_vulns)
            has_high = any(v["severity"] == "HIGH" for v in new_vulns)
            
            if has_critical:
                recs.append("Immediately isolate this device from the internet and disable legacy protocols (Telnet, FTP).")
            if has_high:
                recs.append("Review open web interfaces and enforce HTTPS. Change default credentials.")
            if any("UPNP" in v["vuln_type"] for v in new_vulns):
                recs.append("Disable UPnP on your router to prevent unauthorized port forwarding.")
            if not recs:
                recs.append("Device appears relatively secure, continue monitoring.")
                
            for rec in recs:
                new_vulns.append({
                    "vuln_type": "RECOMMENDATION",
                    "severity": "INFO",
                    "desc": rec,
                    "port": None,
                    "protocol": "Recommendation"
                })

            # Save to database
            for v in new_vulns:
                existing = db.query(Vulnerability).filter(
                    Vulnerability.device_id == device.id,
                    Vulnerability.vuln_type == v["vuln_type"],
                    Vulnerability.port == v["port"]
                ).first()
                
                if not existing:
                    db.add(Vulnerability(
                        device_id=device.id,
                        vuln_type=v["vuln_type"],
                        severity=v["severity"],
                        description=v["desc"],
                        port=v["port"],
                        protocol=v["protocol"]
                    ))
            db.commit()
            
        except Exception as e:
            logger.error(f"Error in analyze_device_detailed: {e}")
        finally:
            db.close()

    @staticmethod
    def generate_report() -> Dict[str, Any]:
        """
        Generates a structured security assessment report.
        """
        db = SessionLocal()
        try:
            devices = db.query(Device).all()
            total_devices = len(devices)
            high_risk_devices = [d for d in devices if d.risk_level == "RISK"]
            
            report = {
                "timestamp": datetime.utcnow().isoformat(),
                "summary": {
                    "total_devices": total_devices,
                    "high_risk_devices": len(high_risk_devices),
                    "medium_risk_devices": len([d for d in devices if d.risk_level == "MEDIUM"]),
                    "safe_devices": len([d for d in devices if d.risk_level == "SAFE"])
                },
                "high_risk_details": [],
                "recommendations": []
            }
            
            for d in high_risk_devices:
                vulns = db.query(Vulnerability).filter(Vulnerability.device_id == d.id).all()
                report["high_risk_details"].append({
                    "ip": d.ip,
                    "mac": d.mac,
                    "hostname": d.hostname,
                    "vendor": d.vendor,
                    "score": d.risk_score,
                    "issues": [v.description for v in vulns]
                })
                
            if report["summary"]["high_risk_devices"] > 0:
                report["recommendations"].append("Isolate high-risk IoT devices on a separate guest network.")
                report["recommendations"].append("Disable Telnet, UPnP, and unencrypted HTTP panels where possible.")
                report["recommendations"].append("Change all default credentials immediately.")
            else:
                report["recommendations"].append("Continue monitoring the network periodically.")
                
            return {"status": "success", "report": report}
        except Exception as e:
            logger.error(f"Error generating assessment report: {e}")
            return {"status": "error", "message": str(e)}
        finally:
            db.close()
