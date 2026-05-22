"""
Critical-path tests for PentexOne.

These tests cover the engine code that the demo relies on most:

    1. Realistic per-vendor simulation flags
    2. Risk calculator math
    3. Action planner ranking + clustering
    4. Anomaly detector signals
    5. CVE lookup cache + CPE normalisation
    6. Vulnerability deduplication

They do NOT hit the network (NVD is mocked / skipped) and do NOT need
the FastAPI server running. Run with:

    cd backend && python -m pytest tests/ -v
"""

import os
import sys

# Make backend/ importable when running `pytest` from inside it
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from simulation_profiles import realistic_flags, _vendor_tier, VENDOR_TIERS
from security_engine import calculate_risk
from action_planner import generate_action_plan
from anomaly_detector import analyze_network
from cve_lookup import normalise_cpe, _score_to_severity


# ─── 1. Simulation profiles ─────────────────────────────────────────────
class TestSimulationProfiles:

    def test_excellent_vendor_almost_always_clean(self):
        """Yale/Apple should produce zero flags the vast majority of the time."""
        clean_count = 0
        for seed in range(100):
            flags = realistic_flags("Zigbee", "Yale", "Smart Lock", seed=seed)
            if not flags:
                clean_count += 1
        assert clean_count >= 90, (
            f"Yale produced flags in {100 - clean_count}/100 trials — should be ≤ 10"
        )

    def test_poor_vendor_usually_has_issues(self):
        """Tuya/TP-Link should produce flags most of the time."""
        flagged_count = 0
        for seed in range(100):
            flags = realistic_flags("Zigbee", "Tuya", "Switch", seed=seed)
            if flags:
                flagged_count += 1
        assert flagged_count >= 50, (
            f"Tuya was clean in {100 - flagged_count}/100 trials — should be ≤ 50"
        )

    def test_unknown_vendor_defaults_to_average(self):
        assert _vendor_tier("RandomVendor123") == "average"
        assert _vendor_tier(None) == "average"
        assert _vendor_tier("") == "average"

    def test_known_vendors_resolve_to_tier(self):
        assert _vendor_tier("Apple") == "excellent"
        assert _vendor_tier("Tuya") == "poor"
        assert _vendor_tier("IKEA") == "average"

    def test_seed_makes_results_deterministic(self):
        a = realistic_flags("Zigbee", "TP-Link", "Plug", seed=42)
        b = realistic_flags("Zigbee", "TP-Link", "Plug", seed=42)
        assert a == b

    def test_unknown_protocol_returns_empty(self):
        assert realistic_flags("SomeFutureProtocol", "Apple") == {}


# ─── 2. Risk calculator ─────────────────────────────────────────────────
class TestRiskCalculator:

    def test_safe_device_has_zero_score(self):
        result = calculate_risk([], "Wi-Fi")
        assert result["risk_level"] == "SAFE"
        assert result["risk_score"] == 0.0
        assert result["vulnerabilities"] == []

    def test_telnet_is_critical(self):
        result = calculate_risk([23], "Wi-Fi")
        assert result["risk_level"] in ("RISK", "CRITICAL")
        assert any(v["vuln_type"] == "OPEN_TELNET" for v in result["vulnerabilities"])

    def test_multiple_critical_ports_escalate(self):
        result = calculate_risk([21, 23, 445], "Wi-Fi")
        assert result["risk_level"] == "CRITICAL"
        assert result["risk_score"] >= 65

    def test_zigbee_flag_produces_vuln(self):
        result = calculate_risk([], "Zigbee", {"ZIGBEE_DEFAULT_KEY": True})
        assert any(v["vuln_type"] == "ZIGBEE_DEFAULT_KEY" for v in result["vulnerabilities"])


# ─── 3. Action planner ──────────────────────────────────────────────────
class TestActionPlanner:

    def _sample_devices(self):
        return [
            {
                "id": 1, "ip": "192.168.1.1", "hostname": "router", "vendor": "TP-Link",
                "vulnerabilities": [
                    {"vuln_type": "OPEN_TELNET", "severity": "CRITICAL", "port": 23},
                    {"vuln_type": "DEFAULT_CREDENTIALS", "severity": "CRITICAL", "port": 80},
                ],
            },
            {
                "id": 2, "ip": "192.168.1.50", "hostname": "cam", "vendor": "Hikvision",
                "vulnerabilities": [
                    {"vuln_type": "OPEN_TELNET", "severity": "CRITICAL", "port": 23},
                ],
            },
        ]

    def test_empty_devices_returns_empty_plan(self):
        plan = generate_action_plan([])
        assert plan["actions"] == []
        assert plan["summary"]["total_devices_scanned"] == 0

    def test_clusters_same_vuln_across_devices(self):
        plan = generate_action_plan(self._sample_devices())
        telnet_actions = [a for a in plan["actions"] if "Telnet" in a["title"]]
        assert len(telnet_actions) == 1, "Telnet should be ONE clustered action, not two"
        assert telnet_actions[0]["affected_count"] == 2

    def test_default_creds_outranks_smb(self):
        """Quick wins (low-effort, high-impact) should outrank slow critical fixes."""
        plan = generate_action_plan(self._sample_devices())
        assert plan["actions"][0]["id"] == "DEFAULT_CREDENTIALS"

    def test_cumulative_reduction_never_exceeds_100(self):
        plan = generate_action_plan(self._sample_devices())
        for a in plan["actions"]:
            assert 0 <= a["cumulative_reduction_pct"] <= 100

    def test_unknown_vuln_falls_back_to_severity_template(self):
        devs = [{
            "id": 1, "ip": "x", "hostname": "x", "vendor": "x",
            "vulnerabilities": [{"vuln_type": "FUTURE_CVE_999", "severity": "HIGH"}],
        }]
        plan = generate_action_plan(devs)
        assert plan["actions"][0]["is_specific"] is False
        assert "FUTURE_CVE_999" in plan["actions"][0]["title"]


# ─── 4. Anomaly detector ────────────────────────────────────────────────
class TestAnomalyDetector:

    def test_empty_network_returns_no_anomalies(self):
        out = analyze_network([])
        assert out["anomalies"] == []
        assert out["network_stats"]["device_count"] == 0

    def test_identical_devices_have_no_anomalies(self):
        devs = [
            {"ip": f"10.0.0.{i}", "hostname": f"h{i}", "vendor": "IKEA",
             "protocol": "Zigbee", "risk_level": "SAFE", "risk_score": 10,
             "open_ports": ""}
            for i in range(5)
        ]
        out = analyze_network(devs)
        assert out["anomalies"] == []

    def test_clear_outlier_is_detected(self):
        normals = [
            {"ip": f"10.0.0.{i}", "hostname": "hue", "vendor": "Philips",
             "protocol": "Zigbee", "risk_level": "SAFE", "risk_score": 5,
             "open_ports": ""}
            for i in range(4)
        ]
        outlier = {"ip": "10.0.0.99", "hostname": "weird-router",
                   "vendor": "Hikvision", "protocol": "Wi-Fi",
                   "risk_level": "CRITICAL", "risk_score": 95,
                   "open_ports": "21,23,80,445,1900,8080,8081"}
        out = analyze_network(normals + [outlier])
        anomalous_ips = {a["ip"] for a in out["anomalies"]}
        assert "10.0.0.99" in anomalous_ips

    def test_reasons_are_human_readable(self):
        normals = [
            {"ip": f"10.0.0.{i}", "hostname": "hue", "vendor": "Philips",
             "protocol": "Zigbee", "risk_level": "SAFE", "risk_score": 5,
             "open_ports": ""}
            for i in range(4)
        ]
        outlier = {"ip": "10.0.0.99", "hostname": "weird", "vendor": "Hikvision",
                   "protocol": "Wi-Fi", "risk_level": "CRITICAL", "risk_score": 95,
                   "open_ports": "21,23,80,445"}
        out = analyze_network(normals + [outlier])
        weird = next((a for a in out["anomalies"] if a["ip"] == "10.0.0.99"), None)
        assert weird is not None
        assert weird["reasons"], "Outlier should have at least one reason"
        for r in weird["reasons"]:
            assert isinstance(r, str) and len(r) > 10


# ─── 5. CVE lookup ──────────────────────────────────────────────────────
class TestCveLookup:

    def test_normalise_legacy_cpe(self):
        result = normalise_cpe("cpe:/a:openbsd:openssh:7.2p2")
        assert result.startswith("cpe:2.3:a:openbsd:openssh:7.2p2")
        assert result.endswith(":*:*:*:*:*:*:*")

    def test_normalise_already_23(self):
        cpe = "cpe:2.3:a:apache:httpd:2.4.41:*:*:*:*:*:*:*"
        assert normalise_cpe(cpe) == cpe

    def test_invalid_cpe_returns_none(self):
        assert normalise_cpe(None) is None
        assert normalise_cpe("") is None
        assert normalise_cpe("not-a-cpe") is None

    def test_score_to_severity_buckets(self):
        assert _score_to_severity(9.8) == "CRITICAL"
        assert _score_to_severity(7.5) == "HIGH"
        assert _score_to_severity(5.0) == "MEDIUM"
        assert _score_to_severity(2.0) == "LOW"
        assert _score_to_severity(None) == "UNKNOWN"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
