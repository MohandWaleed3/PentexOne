"""
AI Router — Endpoints for AI-powered security analysis
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from database import get_db, Device, Vulnerability
from ai_engine import (
    ai_engine,
    analyze_single_device,
    analyze_network,
    get_dashboard_suggestions,
    get_remediation,
    REMEDIATION_DATABASE
)
from action_planner import generate_action_plan
from anomaly_detector import analyze_network as detect_anomalies

router = APIRouter(prefix="/ai", tags=["AI Analysis"])


# ────────────────────────────────────────────────────────────
# 1. Analyze Single Device
# ────────────────────────────────────────────────────────────
@router.get("/analyze/device/{device_id}")
async def ai_analyze_device(device_id: int, db: Session = Depends(get_db)):
    """
    Performs AI-powered analysis on a single device.
    Returns device type prediction, vulnerability predictions, and recommendations.
    """
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        return {"status": "error", "message": "Device not found"}

    # Convert to dict for analysis
    device_dict = {
        "id": device.id,
        "ip": device.ip,
        "mac": device.mac,
        "hostname": device.hostname,
        "vendor": device.vendor,
        "protocol": device.protocol,
        "os_guess": device.os_guess,
        "risk_level": device.risk_level,
        "risk_score": device.risk_score,
        "open_ports": device.open_ports,
        "vulnerabilities": [
            {
                "vuln_type": v.vuln_type,
                "severity": v.severity,
                "description": v.description
            }
            for v in device.vulnerabilities
        ]
    }

    analysis = analyze_single_device(device_dict)

    return {
        "status": "success",
        "device_id": device_id,
        "analysis": analysis
    }


# ────────────────────────────────────────────────────────────
# 2. Network-Wide Analysis
# ────────────────────────────────────────────────────────────
@router.get("/analyze/network")
async def ai_analyze_network(db: Session = Depends(get_db)):
    """
    Performs AI-powered analysis on the entire network.
    Returns pattern analysis, anomalies, and network-wide recommendations.
    """
    devices = db.query(Device).all()

    devices_dict = [
        {
            "id": d.id,
            "ip": d.ip,
            "mac": d.mac,
            "hostname": d.hostname,
            "vendor": d.vendor,
            "protocol": d.protocol,
            "os_guess": d.os_guess,
            "risk_level": d.risk_level,
            "risk_score": d.risk_score,
            "open_ports": d.open_ports
        }
        for d in devices
    ]

    analysis = analyze_network(devices_dict)

    return {
        "status": "success",
        "device_count": len(devices),
        "analysis": analysis
    }


# ────────────────────────────────────────────────────────────
# 2b. Network Anomaly Detection (real statistics, not heuristics)
# ────────────────────────────────────────────────────────────
@router.get("/anomalies")
async def ai_detect_anomalies(db: Session = Depends(get_db)):
    """
    Runs unsupervised anomaly detection (z-score + IQR + Jaccard
    similarity) over all devices. Returns ranked anomalies with
    transparent reasoning — no black box, no fake ML.
    """
    devices = db.query(Device).all()
    payload = [
        {
            "ip": d.ip,
            "hostname": d.hostname,
            "vendor": d.vendor,
            "protocol": d.protocol,
            "risk_level": d.risk_level,
            "risk_score": d.risk_score,
            "open_ports": d.open_ports,
        }
        for d in devices
    ]
    result = detect_anomalies(payload)
    return {
        "status": "success",
        "device_count": len(devices),
        **result,
    }


# ────────────────────────────────────────────────────────────
# 3. Dashboard Suggestions
# ────────────────────────────────────────────────────────────
@router.get("/suggestions")
async def ai_get_suggestions(db: Session = Depends(get_db)):
    """
    Returns AI-powered suggestions for the dashboard.
    Includes recommended scans, alerts, and actions.
    """
    devices = db.query(Device).all()

    devices_dict = [
        {
            "id": d.id,
            "ip": d.ip,
            "protocol": d.protocol,
            "risk_level": d.risk_level,
            "hostname": d.hostname
        }
        for d in devices
    ]

    suggestions = get_dashboard_suggestions(devices_dict)

    # Get network analysis for additional context
    network_analysis = analyze_network([
        {"protocol": d.protocol, "risk_level": d.risk_level}
        for d in devices
    ])

    return {
        "status": "success",
        "suggestions": suggestions,
        "network_score": network_analysis.get("security_score", {}),
        "timestamp": datetime.utcnow().isoformat()
    }


# ────────────────────────────────────────────────────────────
# 4. Remediation Guide
# ────────────────────────────────────────────────────────────
@router.get("/remediation/{vuln_type}")
async def ai_get_remediation(vuln_type: str):
    """
    Returns detailed remediation steps for a specific vulnerability type.
    """
    remediation = get_remediation(vuln_type)

    return {
        "status": "success",
        "vulnerability": vuln_type,
        "remediation": remediation
    }


# ────────────────────────────────────────────────────────────
# 5. Get All Remediations
# ────────────────────────────────────────────────────────────
@router.get("/remediations")
async def ai_get_all_remediations():
    """
    Returns all available remediation guides.
    """
    return {
        "status": "success",
        "remediations": REMEDIATION_DATABASE
    }


# ────────────────────────────────────────────────────────────
# 6. Risk Prediction
# ────────────────────────────────────────────────────────────
@router.get("/predict/risks")
async def ai_predict_risks(db: Session = Depends(get_db)):
    """
    Predicts future risks based on current device state.
    """
    devices = db.query(Device).all()

    # Get current state
    current_risk_count = sum(1 for d in devices if d.risk_level == "RISK")
    current_medium_count = sum(1 for d in devices if d.risk_level == "MEDIUM")
    current_safe_count = sum(1 for d in devices if d.risk_level == "SAFE")

    # Analyze devices for potential future risks
    potential_new_risks = []
    for device in devices:
        if device.risk_level == "MEDIUM":
            # Medium devices have potential to become high risk
            analysis = analyze_single_device({
                "ip": device.ip,
                "hostname": device.hostname,
                "vendor": device.vendor,
                "protocol": device.protocol,
                "open_ports": device.open_ports,
                "risk_score": device.risk_score
            })

            if analysis.get("predicted_vulnerabilities"):
                potential_new_risks.append({
                    "device_id": device.id,
                    "hostname": device.hostname,
                    "current_risk": device.risk_level,
                    "predicted_vulnerabilities": analysis["predicted_vulnerabilities"][:3]
                })

    return {
        "status": "success",
        "current_state": {
            "risk": current_risk_count,
            "medium": current_medium_count,
            "safe": current_safe_count,
            "total": len(devices)
        },
        "potential_escalations": potential_new_risks[:5],
        "recommendation": "Monitor medium-risk devices for escalation" if potential_new_risks
        else "No immediate risks predicted"
    }


# ────────────────────────────────────────────────────────────
# 7. Device Classification
# ────────────────────────────────────────────────────────────
@router.get("/classify/devices")
async def ai_classify_devices(db: Session = Depends(get_db)):
    """
    Classifies all devices by type using AI pattern matching.
    """
    devices = db.query(Device).all()

    classifications = []
    for device in devices:
        analysis = analyze_single_device({
            "hostname": device.hostname,
            "vendor": device.vendor,
            "protocol": device.protocol,
            "open_ports": device.open_ports
        })

        classifications.append({
            "device_id": device.id,
            "ip": device.ip,
            "hostname": device.hostname,
            "classified_type": analysis["device_type"],
            "confidence": analysis["confidence"],
            "is_anomaly": analysis["is_anomaly"]
        })

    # Group by device type
    type_groups = {}
    for c in classifications:
        dtype = c["classified_type"]
        if dtype not in type_groups:
            type_groups[dtype] = []
        type_groups[dtype].append(c)

    return {
        "status": "success",
        "total_devices": len(devices),
        "device_types": type_groups,
        "classifications": classifications
    }


# ────────────────────────────────────────────────────────────
# 8. Prioritized Action Plan
# ────────────────────────────────────────────────────────────
@router.get("/action-plan")
async def ai_action_plan(max_actions: int = 8, db: Session = Depends(get_db)):
    """
    Returns an AI-prioritized list of remediation actions across all devices,
    ranked by (exploitability * impact) / effort, with clustered findings
    and risk-reduction estimates.
    """
    devices = db.query(Device).all()

    devices_payload = []
    for d in devices:
        devices_payload.append({
            "id": d.id,
            "ip": d.ip,
            "hostname": d.hostname,
            "vendor": d.vendor,
            "protocol": d.protocol,
            "risk_level": d.risk_level,
            "risk_score": d.risk_score,
            "vulnerabilities": [
                {
                    "vuln_type": v.vuln_type,
                    "severity": v.severity,
                    "description": v.description,
                    "port": v.port,
                }
                for v in d.vulnerabilities
            ],
        })

    plan = generate_action_plan(devices_payload, max_actions=max_actions)
    plan["status"] = "success"
    plan["timestamp"] = datetime.utcnow().isoformat()
    return plan


# ────────────────────────────────────────────────────────────
# 9. Security Score
# ────────────────────────────────────────────────────────────
@router.get("/security-score")
async def ai_get_security_score(db: Session = Depends(get_db)):
    """
    Returns AI-calculated security score for the network.
    """
    devices = db.query(Device).all()

    if not devices:
        return {
            "status": "success",
            "score": {"score": 100, "grade": "A", "description": "No devices to analyze"}
        }

    # Count risk levels — normalize CRITICAL/HIGH into the unified scale
    LEVEL_SCORE = {"SAFE": 100, "LOW": 80, "MEDIUM": 50,
                   "RISK": 10, "HIGH": 10, "CRITICAL": 0, "UNKNOWN": 30}
    risk_counts: dict = {}
    for d in devices:
        lvl = d.risk_level or "UNKNOWN"
        risk_counts[lvl] = risk_counts.get(lvl, 0) + 1

    # Calculate score (weighted average of per-device scores)
    total = len(devices)
    score = sum(LEVEL_SCORE.get(lvl, 30) * cnt for lvl, cnt in risk_counts.items()) / total
    score = round(score, 1)

    # Grade
    if score >= 80:
        grade, description = "A", "Excellent security posture"
    elif score >= 60:
        grade, description = "B", "Good security with some concerns"
    elif score >= 40:
        grade, description = "C", "Moderate security risks present"
    elif score >= 20:
        grade, description = "D", "Significant security issues"
    else:
        grade, description = "F", "Critical security state"

    # Improvement suggestions
    critical_n = risk_counts.get("CRITICAL", 0)
    high_n = risk_counts.get("HIGH", 0) + risk_counts.get("RISK", 0)
    medium_n = risk_counts.get("MEDIUM", 0)
    suggestions = []
    if critical_n > 0:
        suggestions.append({
            "impact": 30,
            "action": f"Remediate {critical_n} critical device(s) immediately"
        })
    if high_n > 0:
        suggestions.append({
            "impact": 20,
            "action": f"Address {high_n} high-risk device(s)"
        })
    if medium_n > 0:
        suggestions.append({
            "impact": 10,
            "action": f"Review {medium_n} medium-risk device(s)"
        })

    return {
        "status": "success",
        "score": {
            "score": score,
            "grade": grade,
            "description": description
        },
        "breakdown": risk_counts,
        "improvement_suggestions": suggestions,
        "max_possible_score": 100,
        "potential_improvement": sum(s["impact"] for s in suggestions)
    }
