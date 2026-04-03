"""
AI Engine — Intelligent Security Analysis for PentexOne
========================================================

Features:
- Device pattern analysis and anomaly detection
- Vulnerability prediction using ML-based scoring
- Smart remediation suggestions
- Dashboard recommendations
- Risk trend analysis

No external ML libraries required — uses statistical analysis and rule-based AI.
"""

from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
import json
import math
import re


# ====== AI CONFIGURATION ======
AI_CONFIG = {
    "anomaly_threshold": 0.85,  # Threshold for anomaly detection
    "risk_prediction_weight": 0.7,  # Weight for historical data in predictions
    "min_devices_for_pattern": 3,  # Minimum devices to establish patterns
    "recommendation_confidence": 0.6,  # Minimum confidence for recommendations
}


# ====== VULNERABILITY PATTERN DATABASE ======
# Known vulnerability patterns and their risk indicators
VULNERABILITY_PATTERNS = {
    # IoT Device Patterns
    "camera_pattern": {
        "keywords": ["camera", "cam", "ipcam", "webcam", "hikvision", "dahua", "foscam", "amcrest"],
        "common_ports": [80, 443, 554, 8080, 8443, 37777],
        "risk_factors": {
            "default_credentials": 0.9,
            "rtsp_exposed": 0.7,
            "old_firmware": 0.8,
        },
        "typical_vulnerabilities": ["OPEN_RTSP", "DEFAULT_CREDENTIALS", "OUTDATED_FIRMWARE"]
    },
    "router_pattern": {
        "keywords": ["router", "gateway", "ap", "access point", "tp-link", "netgear", "asus", "linksys"],
        "common_ports": [80, 443, 22, 23, 8080],
        "risk_factors": {
            "default_credentials": 0.95,
            "upnp_enabled": 0.6,
            "remote_admin": 0.8,
        },
        "typical_vulnerabilities": ["DEFAULT_CREDENTIALS", "UPNP_OPEN", "REMOTE_ADMIN_EXPOSED"]
    },
    "smart_home_pattern": {
        "keywords": ["smart", "home", "hue", "alexa", "echo", "google", "nest", "ring", "smartthings"],
        "common_ports": [80, 443, 8080, 8883, 5683],
        "risk_factors": {
            "cloud_dependency": 0.5,
            "local_encryption": 0.3,
            "authentication": 0.4,
        },
        "typical_vulnerabilities": ["CLOUD_DEPENDENCY", "WEAK_ENCRYPTION", "NO_LOCAL_AUTH"]
    },
    "industrial_pattern": {
        "keywords": ["plc", "scada", "modbus", "siemens", "allen-bradley", "schneider"],
        "common_ports": [502, 102, 44818, 47808],
        "risk_factors": {
            "no_authentication": 0.95,
            "legacy_protocol": 0.85,
            "firmware_outdated": 0.7,
        },
        "typical_vulnerabilities": ["MODBUS_EXPOSED", "NO_AUTHENTICATION", "LEGACY_PROTOCOL"]
    },
    "medical_pattern": {
        "keywords": ["medical", "health", "patient", "hospital", "infusion", "monitor"],
        "common_ports": [80, 443, 104, 9100],
        "risk_factors": {
            "phi_exposure": 0.95,
            "legacy_systems": 0.8,
            "no_encryption": 0.9,
        },
        "typical_vulnerabilities": ["PHI_EXPOSURE", "LEGACY_SYSTEM", "NO_ENCRYPTION"]
    },
}

# Protocol-based risk multipliers
PROTOCOL_RISK_MULTIPLIERS = {
    "Wi-Fi": {"network_exposure": 1.0, "encryption_variability": 0.8},
    "Bluetooth": {"proximity_risk": 0.9, "pairing_weakness": 0.7},
    "Zigbee": {"mesh_exposure": 0.8, "key_management": 0.9},
    "Thread": {"network_key": 0.7, "commissioner": 0.8},
    "Z-Wave": {"s0_weakness": 0.9, "s2_adoption": 0.4},
    "LoRaWAN": {"lorawan_security": 0.5, "join_procedure": 0.6},
}


# ====== REMEDIATION KNOWLEDGE BASE ======
REMEDIATION_DATABASE = {
    # Port-based remediations
    "OPEN_TELNET": {
        "severity": "CRITICAL",
        "title": "Disable Telnet Service",
        "steps": [
            "Access device administration panel",
            "Navigate to Services/Network settings",
            "Disable Telnet service",
            "Enable SSH as secure alternative",
            "Block port 23 at firewall level"
        ],
        "priority": 1,
        "estimated_time": "15 minutes",
        "impact": "No service disruption if SSH is configured first"
    },
    "OPEN_FTP": {
        "severity": "CRITICAL",
        "title": "Replace FTP with Secure Alternative",
        "steps": [
            "Install and configure SFTP or FTPS server",
            "Migrate user accounts and permissions",
            "Update client configurations",
            "Disable FTP service",
            "Block port 21 at firewall"
        ],
        "priority": 1,
        "estimated_time": "30-60 minutes",
        "impact": "Requires client updates"
    },
    "DEFAULT_CREDENTIALS": {
        "severity": "CRITICAL",
        "title": "Change Default Credentials Immediately",
        "steps": [
            "Access device web interface or console",
            "Navigate to User/Security settings",
            "Change admin password to strong unique password (16+ chars)",
            "Create separate user accounts if possible",
            "Enable account lockout after failed attempts"
        ],
        "priority": 1,
        "estimated_time": "5 minutes",
        "impact": "Immediate security improvement"
    },
    "SMB_OPEN": {
        "severity": "CRITICAL",
        "title": "Secure or Disable SMB Service",
        "steps": [
            "Apply latest security patches (MS17-010)",
            "Disable SMBv1 protocol",
            "Enable SMB signing",
            "Configure firewall to restrict access",
            "Consider disabling if not required"
        ],
        "priority": 1,
        "estimated_time": "20 minutes",
        "impact": "May affect legacy Windows systems"
    },
    "RDP_OPEN": {
        "severity": "HIGH",
        "title": "Secure Remote Desktop Access",
        "steps": [
            "Enable Network Level Authentication (NLA)",
            "Change default port from 3389",
            "Implement strong password policy",
            "Enable account lockout",
            "Use VPN for external access",
            "Apply latest security patches"
        ],
        "priority": 2,
        "estimated_time": "25 minutes",
        "impact": "Improved security, may need client reconfiguration"
    },
    
    # Protocol-specific remediations
    "ZIGBEE_DEFAULT_KEY": {
        "severity": "HIGH",
        "title": "Update Zigbee Network Security",
        "steps": [
            "Access Zigbee coordinator settings",
            "Generate unique network key",
            "Re-pair all devices with new key",
            "Enable APS layer encryption",
            "Document new key securely"
        ],
        "priority": 2,
        "estimated_time": "1-2 hours",
        "impact": "Requires re-pairing all Zigbee devices"
    },
    "BLE_NO_PAIRING": {
        "severity": "HIGH",
        "title": "Enable BLE Pairing Security",
        "steps": [
            "Access device Bluetooth settings",
            "Enable pairing/bonding requirement",
            "Use Secure Connections (LESC)",
            "Disable Just Works pairing",
            "Enable passkey or numeric comparison"
        ],
        "priority": 2,
        "estimated_time": "15 minutes",
        "impact": "Existing connections may need re-pairing"
    },
    "TLSV1_ENABLED": {
        "severity": "HIGH",
        "title": "Upgrade TLS Protocol",
        "steps": [
            "Access web server/SSL configuration",
            "Disable TLS 1.0 and TLS 1.1",
            "Enable TLS 1.2 and TLS 1.3 only",
            "Configure strong cipher suites",
            "Test with SSL Labs SSL Test"
        ],
        "priority": 2,
        "estimated_time": "20 minutes",
        "impact": "May affect very old clients"
    },
    
    # Generic remediation
    "GENERIC": {
        "severity": "MEDIUM",
        "title": "Apply Security Best Practices",
        "steps": [
            "Update device firmware to latest version",
            "Review and close unnecessary open ports",
            "Enable encryption where available",
            "Implement network segmentation",
            "Document all changes made"
        ],
        "priority": 3,
        "estimated_time": "Varies",
        "impact": "General security improvement"
    }
}


class AISecurityEngine:
    """
    AI-powered security analysis engine for PentexOne.
    Provides intelligent vulnerability prediction, pattern analysis, and recommendations.
    """
    
    def __init__(self):
        self.device_history = []  # Historical device data for learning
        self.scan_history = []    # Scan results over time
        self.learned_patterns = {}  # Patterns learned from network
        
    def analyze_device(self, device: Dict[str, Any]) -> Dict[str, Any]:
        """
        Performs comprehensive AI analysis on a single device.
        Returns predicted vulnerabilities, risk assessment, and recommendations.
        """
        # Identify device type
        device_type = self._identify_device_type(device)
        
        # Predict vulnerabilities based on patterns
        predicted_vulns = self._predict_vulnerabilities(device, device_type)
        
        # Calculate anomaly score
        anomaly_score = self._calculate_anomaly_score(device)
        
        # Generate recommendations
        recommendations = self._generate_device_recommendations(device, predicted_vulns)
        
        # Calculate overall AI confidence
        confidence = self._calculate_confidence(device, device_type)
        
        return {
            "device_type": device_type,
            "predicted_vulnerabilities": predicted_vulns,
            "anomaly_score": anomaly_score,
            "is_anomaly": anomaly_score > AI_CONFIG["anomaly_threshold"],
            "recommendations": recommendations,
            "confidence": confidence,
            "analysis_timestamp": datetime.utcnow().isoformat()
        }
    
    def _identify_device_type(self, device: Dict[str, Any]) -> str:
        """
        Uses pattern matching to identify device type.
        """
        hostname = device.get("hostname", "").lower()
        vendor = device.get("vendor", "").lower()
        combined_text = f"{hostname} {vendor}"
        
        for pattern_name, pattern_data in VULNERABILITY_PATTERNS.items():
            for keyword in pattern_data["keywords"]:
                if keyword in combined_text:
                    return pattern_name
        
        # Check port patterns
        open_ports = str(device.get("open_ports", "")).split(",")
        for pattern_name, pattern_data in VULNERABILITY_PATTERNS.items():
            common_ports = set(pattern_data["common_ports"])
            device_ports = set(p.strip() for p in open_ports if p.strip().isdigit())
            if device_ports and len(device_ports & common_ports) >= 2:
                return pattern_name
        
        return "unknown_device"
    
    def _predict_vulnerabilities(self, device: Dict[str, Any], device_type: str) -> List[Dict[str, Any]]:
        """
        Predicts likely vulnerabilities based on device characteristics.
        """
        predictions = []
        
        # Get device pattern if known
        pattern = VULNERABILITY_PATTERNS.get(device_type, {})
        
        # Analyze open ports
        open_ports = [int(p.strip()) for p in str(device.get("open_ports", "")).split(",") 
                      if p.strip().isdigit()]
        
        # Port-based predictions
        risky_ports = {
            23: ("OPEN_TELNET", 0.9),
            21: ("OPEN_FTP", 0.85),
            445: ("SMB_OPEN", 0.8),
            139: ("NETBIOS_OPEN", 0.7),
            3389: ("RDP_OPEN", 0.75),
            554: ("RTSP_OPEN", 0.65),
            1883: ("MQTT_OPEN", 0.6),
        }
        
        for port in open_ports:
            if port in risky_ports:
                vuln_type, confidence = risky_ports[port]
                predictions.append({
                    "vuln_type": vuln_type,
                    "confidence": confidence,
                    "source": "port_analysis",
                    "port": port
                })
        
        # Vendor-specific predictions
        vendor = device.get("vendor", "").lower()
        if any(v in vendor for v in ["hikvision", "dahua", "foscam"]):
            predictions.append({
                "vuln_type": "DEFAULT_CREDENTIALS",
                "confidence": 0.85,
                "source": "vendor_pattern",
                "details": "Camera vendor known for default credentials"
            })
        
        # Protocol-based predictions
        protocol = device.get("protocol", "")
        if protocol == "Zigbee":
            predictions.extend([
                {"vuln_type": "ZIGBEE_DEFAULT_KEY", "confidence": 0.7, "source": "protocol"},
                {"vuln_type": "ZIGBEE_REPLAY", "confidence": 0.5, "source": "protocol"}
            ])
        elif protocol == "Bluetooth":
            predictions.extend([
                {"vuln_type": "BLE_NO_PAIRING", "confidence": 0.6, "source": "protocol"},
                {"vuln_type": "BLE_EXPOSED_CHARACTERISTICS", "confidence": 0.5, "source": "protocol"}
            ])
        
        # Add typical vulnerabilities from pattern
        if pattern:
            for vuln in pattern.get("typical_vulnerabilities", []):
                if not any(p["vuln_type"] == vuln for p in predictions):
                    risk_factors = pattern.get("risk_factors", {})
                    confidence = risk_factors.get(vuln.lower(), 0.5)
                    predictions.append({
                        "vuln_type": vuln,
                        "confidence": confidence,
                        "source": "device_pattern"
                    })
        
        # Sort by confidence
        predictions.sort(key=lambda x: x["confidence"], reverse=True)
        return predictions[:5]  # Return top 5 predictions
    
    def _calculate_anomaly_score(self, device: Dict[str, Any]) -> float:
        """
        Calculates an anomaly score for the device based on deviation from normal patterns.
        """
        score = 0.0
        factors = 0
        
        # Check for unusual open ports
        open_ports = [int(p.strip()) for p in str(device.get("open_ports", "")).split(",")
                      if p.strip().isdigit()]
        common_ports = {80, 443, 22, 8080, 8443}
        unusual_ports = [p for p in open_ports if p not in common_ports]
        if len(unusual_ports) > 3:
            score += 0.3
            factors += 1
        
        # Check for unknown vendor
        vendor = device.get("vendor", "").lower()
        if vendor in ["unknown", "", "generic"]:
            score += 0.2
            factors += 1
        
        # Check for high risk score
        risk_score = device.get("risk_score", 0)
        if risk_score > 60:
            score += min(risk_score / 100, 0.4)
            factors += 1
        
        # Check for multiple protocols
        # Device with multiple protocols could be suspicious
        # (handled elsewhere)
        
        return min(score / max(factors, 1) + 0.1, 1.0)
    
    def _generate_device_recommendations(self, device: Dict[str, Any], 
                                         predicted_vulns: List[Dict]) -> List[Dict[str, Any]]:
        """
        Generates actionable recommendations for the device.
        """
        recommendations = []
        seen_vulns = set()
        
        # Process predicted vulnerabilities
        for pred in predicted_vulns:
            vuln_type = pred["vuln_type"]
            if vuln_type in seen_vulns:
                continue
            seen_vulns.add(vuln_type)
            
            # Get remediation from database
            remediation = REMEDIATION_DATABASE.get(vuln_type, REMEDIATION_DATABASE["GENERIC"])
            
            recommendations.append({
                "priority": remediation["priority"],
                "vulnerability": vuln_type,
                "severity": remediation["severity"],
                "title": remediation["title"],
                "steps": remediation["steps"],
                "estimated_time": remediation["estimated_time"],
                "impact": remediation["impact"],
                "confidence": pred["confidence"]
            })
        
        # Sort by priority and confidence
        recommendations.sort(key=lambda x: (x["priority"], -x["confidence"]))
        return recommendations[:5]  # Return top 5 recommendations
    
    def _calculate_confidence(self, device: Dict[str, Any], device_type: str) -> float:
        """
        Calculates overall confidence in the AI analysis.
        """
        confidence = 0.5
        
        # Higher confidence if device type is known
        if device_type != "unknown_device":
            confidence += 0.2
        
        # Higher confidence if vendor is known
        if device.get("vendor") and device["vendor"] not in ["Unknown", "unknown", ""]:
            confidence += 0.1
        
        # Higher confidence if we have open port data
        if device.get("open_ports"):
            confidence += 0.1
        
        # Higher confidence if we have protocol info
        if device.get("protocol") and device["protocol"] != "Unknown":
            confidence += 0.1
        
        return min(confidence, 1.0)
    
    def analyze_network_patterns(self, devices: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyzes patterns across all devices in the network.
        """
        if len(devices) < AI_CONFIG["min_devices_for_pattern"]:
            return {
                "status": "insufficient_data",
                "message": f"Need at least {AI_CONFIG['min_devices_for_pattern']} devices for pattern analysis"
            }
        
        # Device type distribution
        device_types = defaultdict(int)
        for device in devices:
            device_type = self._identify_device_type(device)
            device_types[device_type] += 1
        
        # Protocol distribution
        protocols = defaultdict(int)
        for device in devices:
            protocols[device.get("protocol", "Unknown")] += 1
        
        # Risk distribution
        risk_levels = defaultdict(int)
        for device in devices:
            risk_levels[device.get("risk_level", "UNKNOWN")] += 1
        
        # Vendor distribution
        vendors = defaultdict(int)
        for device in devices:
            vendor = device.get("vendor", "Unknown")
            vendors[vendor if vendor else "Unknown"] += 1
        
        # Identify network anomalies
        anomalies = self._detect_network_anomalies(devices, device_types, protocols)
        
        # Generate network-wide recommendations
        network_recommendations = self._generate_network_recommendations(
            devices, device_types, risk_levels, anomalies
        )
        
        return {
            "status": "success",
            "device_type_distribution": dict(device_types),
            "protocol_distribution": dict(protocols),
            "risk_distribution": dict(risk_levels),
            "top_vendors": dict(sorted(vendors.items(), key=lambda x: -x[1])[:5]),
            "anomalies": anomalies,
            "recommendations": network_recommendations,
            "security_score": self._calculate_network_security_score(devices, risk_levels)
        }
    
    def _detect_network_anomalies(self, devices: List[Dict], 
                                  device_types: Dict, protocols: Dict) -> List[Dict]:
        """
        Detects anomalies at the network level.
        """
        anomalies = []
        
        # Check for too many high-risk devices
        risk_devices = sum(1 for d in devices if d.get("risk_level") == "RISK")
        if risk_devices > len(devices) * 0.3:
            anomalies.append({
                "type": "high_risk_ratio",
                "message": f"{risk_devices} devices ({risk_devices/len(devices)*100:.0f}%) are high-risk",
                "severity": "HIGH",
                "recommendation": "Prioritize remediation of high-risk devices"
            })
        
        # Check for unencrypted protocols
        unencrypted_protocols = ["Wi-Fi", "Bluetooth"]
        for proto in unencrypted_protocols:
            if protocols.get(proto, 0) > 5:
                anomalies.append({
                    "type": "unencrypted_protocol",
                    "message": f"Multiple {proto} devices may lack encryption",
                    "severity": "MEDIUM",
                    "protocol": proto
                })
        
        # Check for unknown device types
        unknown_count = device_types.get("unknown_device", 0)
        if unknown_count > len(devices) * 0.2:
            anomalies.append({
                "type": "unknown_devices",
                "message": f"{unknown_count} devices could not be identified",
                "severity": "LOW",
                "recommendation": "Manual identification recommended"
            })
        
        return anomalies
    
    def _generate_network_recommendations(self, devices: List[Dict], device_types: Dict,
                                          risk_levels: Dict, anomalies: List) -> List[Dict]:
        """
        Generates network-wide security recommendations.
        """
        recommendations = []
        
        # Based on risk levels
        if risk_levels.get("RISK", 0) > 0:
            recommendations.append({
                "priority": 1,
                "title": "Address Critical Vulnerabilities",
                "description": f"{risk_levels['RISK']} devices have critical vulnerabilities",
                "action": "Review and remediate all RISK-level devices immediately",
                "category": "critical"
            })
        
        # Based on device types
        if device_types.get("camera_pattern", 0) > 2:
            recommendations.append({
                "priority": 2,
                "title": "Review Camera Security",
                "description": "Multiple cameras detected in network",
                "action": "Ensure all cameras have updated firmware and changed credentials",
                "category": "device_specific"
            })
        
        # Based on anomalies
        for anomaly in anomalies:
            if anomaly["type"] == "high_risk_ratio":
                recommendations.append({
                    "priority": 1,
                    "title": "Network Security Posture Critical",
                    "description": anomaly["message"],
                    "action": anomaly["recommendation"],
                    "category": "network"
                })
        
        # General recommendations
        if len(devices) > 10:
            recommendations.append({
                "priority": 3,
                "title": "Implement Network Segmentation",
                "description": "Large IoT network detected",
                "action": "Segment IoT devices on separate VLAN for isolation",
                "category": "best_practice"
            })
        
        return recommendations
    
    def _calculate_network_security_score(self, devices: List[Dict], risk_levels: Dict) -> Dict:
        """
        Calculates an overall network security score (0-100).
        """
        if not devices:
            return {"score": 100, "grade": "A", "description": "No devices to analyze"}
        
        total = len(devices)
        safe = risk_levels.get("SAFE", 0)
        medium = risk_levels.get("MEDIUM", 0)
        risk = risk_levels.get("RISK", 0)
        
        # Weighted score
        score = (safe * 100 + medium * 50 + risk * 0) / total
        score = round(score, 1)
        
        # Grade assignment
        if score >= 80:
            grade = "A"
            description = "Excellent security posture"
        elif score >= 60:
            grade = "B"
            description = "Good security with some concerns"
        elif score >= 40:
            grade = "C"
            description = "Moderate security risks present"
        elif score >= 20:
            grade = "D"
            description = "Significant security issues"
        else:
            grade = "F"
            description = "Critical security state"
        
        return {
            "score": score,
            "grade": grade,
            "description": description,
            "breakdown": {
                "safe_devices": safe,
                "medium_devices": medium,
                "risk_devices": risk,
                "total_devices": total
            }
        }
    
    def predict_future_risks(self, historical_scans: List[Dict]) -> Dict[str, Any]:
        """
        Predicts future security risks based on historical scan data.
        """
        if len(historical_scans) < 2:
            return {
                "status": "insufficient_data",
                "message": "Need at least 2 historical scans for prediction"
            }
        
        # Analyze trends
        risk_trend = []
        for scan in historical_scans[-5:]:  # Last 5 scans
            risk_trend.append(scan.get("risk_count", 0))
        
        # Calculate trend direction
        if len(risk_trend) >= 2:
            trend_direction = "increasing" if risk_trend[-1] > risk_trend[0] else "decreasing"
            trend_rate = abs(risk_trend[-1] - risk_trend[0]) / max(risk_trend[0], 1)
        else:
            trend_direction = "stable"
            trend_rate = 0
        
        # Predict next scan results
        predicted_risk = risk_trend[-1] if risk_trend else 0
        if trend_direction == "increasing":
            predicted_risk = int(risk_trend[-1] * (1 + trend_rate * 0.5))
        elif trend_direction == "decreasing":
            predicted_risk = max(0, int(risk_trend[-1] * (1 - trend_rate * 0.5)))
        
        return {
            "status": "success",
            "trend_direction": trend_direction,
            "trend_rate": round(trend_rate, 2),
            "predicted_risk_devices": predicted_risk,
            "recommendation": "Continue monitoring" if trend_direction == "decreasing" 
                             else "Increase security measures"
        }
    
    def get_smart_dashboard_suggestions(self, devices: List[Dict], 
                                        analysis: Dict) -> List[Dict]:
        """
        Generates smart suggestions for dashboard improvement.
        """
        suggestions = []
        
        # Suggest scans based on missing protocols
        protocols_found = set(d.get("protocol", "") for d in devices)
        all_protocols = {"Wi-Fi", "Bluetooth", "Zigbee", "Thread", "Z-Wave", "LoRaWAN"}
        missing_protocols = all_protocols - protocols_found
        
        for proto in missing_protocols:
            suggestions.append({
                "type": "suggested_scan",
                "icon": "fa-radar",
                "title": f"Scan for {proto} Devices",
                "description": f"No {proto} devices discovered yet",
                "action": f"startScan('{proto.lower()}')",
                "priority": 2
            })
        
        # Suggest remediation for high-risk devices
        risk_devices = [d for d in devices if d.get("risk_level") == "RISK"]
        if risk_devices:
            suggestions.append({
                "type": "alert",
                "icon": "fa-triangle-exclamation",
                "title": f"Address {len(risk_devices)} High-Risk Devices",
                "description": "Devices with critical vulnerabilities detected",
                "action": "view_device",
                "device_ids": [d["id"] for d in risk_devices[:3]],
                "priority": 1
            })
        
        # Suggest hardware check if no IoT devices found
        iot_protocols = {"Zigbee", "Thread", "Z-Wave", "Bluetooth"}
        iot_devices = [d for d in devices if d.get("protocol") in iot_protocols]
        if not iot_devices:
            suggestions.append({
                "type": "hardware_check",
                "icon": "fa-usb",
                "title": "Check IoT Hardware",
                "description": "No IoT devices found - check hardware dongles",
                "action": "checkHardware",
                "priority": 3
            })
        
        # Sort by priority
        suggestions.sort(key=lambda x: x["priority"])
        return suggestions


# Global AI engine instance
ai_engine = AISecurityEngine()


# ====== HELPER FUNCTIONS FOR API ======

def analyze_single_device(device: Dict) -> Dict:
    """Convenience function for single device analysis."""
    return ai_engine.analyze_device(device)


def analyze_network(devices: List[Dict]) -> Dict:
    """Convenience function for network-wide analysis."""
    return ai_engine.analyze_network_patterns(devices)


def get_dashboard_suggestions(devices: List[Dict], analysis: Dict = None) -> List:
    """Convenience function for dashboard suggestions."""
    return ai_engine.get_smart_dashboard_suggestions(devices, analysis or {})


def get_remediation(vuln_type: str) -> Dict:
    """Get remediation steps for a vulnerability type."""
    return REMEDIATION_DATABASE.get(vuln_type, REMEDIATION_DATABASE["GENERIC"])
