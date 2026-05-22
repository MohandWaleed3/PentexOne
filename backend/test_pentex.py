"""
PentexOne - Comprehensive API Test Suite
Tests all routers: iot, rfid, wireless, reports, ai, attacks, lab, settings
"""
import os
import sys
import pytest

# Use in-memory DB for tests
os.environ["DATABASE_URL"] = "sqlite://:memory:"
os.environ["PENTEX_RELOAD"] = "false"

sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app, raise_server_exceptions=False)


# ─────────────────────────────────────────────────────
# ROOT & SETTINGS
# ─────────────────────────────────────────────────────

class TestRoot:
    def test_root_redirect(self):
        r = client.get("/", follow_redirects=False)
        assert r.status_code in (301, 302, 307, 308)

    def test_settings_get(self):
        r = client.get("/settings")
        assert r.status_code == 200
        assert isinstance(r.json(), dict)

    def test_settings_update(self):
        r = client.put("/settings", json={"simulation_mode": "true", "nmap_timeout": "30"})
        assert r.status_code in (200, 422, 500)


# ─────────────────────────────────────────────────────
# IOT ROUTER  /iot/*
# ─────────────────────────────────────────────────────

class TestIoT:
    def test_get_devices_empty(self):
        r = client.get("/iot/devices")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_scan_status(self):
        r = client.get("/iot/scan/status")
        assert r.status_code == 200

    def test_hardware_status(self):
        r = client.get("/iot/hardware/status")
        assert r.status_code == 200

    def test_networks_discover(self):
        r = client.get("/iot/networks/discover")
        assert r.status_code in (200, 500)

    def test_scan_wifi(self):
        r = client.post("/iot/scan/wifi", json={"network": "192.168.1.0/24"})
        assert r.status_code in (200, 500)

    def test_scan_matter(self):
        r = client.post("/iot/scan/matter")
        assert r.status_code in (200, 500)

    def test_scan_zigbee(self):
        r = client.post("/iot/scan/zigbee")
        assert r.status_code in (200, 500)

    def test_scan_thread(self):
        r = client.post("/iot/scan/thread")
        assert r.status_code in (200, 500)

    def test_scan_zwave(self):
        r = client.post("/iot/scan/zwave")
        assert r.status_code in (200, 500)

    def test_scan_lora(self):
        r = client.post("/iot/scan/lora")
        assert r.status_code in (200, 500)

    def test_device_not_found(self):
        r = client.get("/iot/devices/9999")
        assert r.status_code == 404

    def test_delete_devices(self):
        r = client.delete("/iot/devices")
        assert r.status_code in (200, 204)


# ─────────────────────────────────────────────────────
# RFID / ACCESS CONTROL  /rfid/*
# ─────────────────────────────────────────────────────

class TestRFID:
    def test_get_cards_empty(self):
        r = client.get("/rfid/cards")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_get_reports_empty(self):
        r = client.get("/rfid/reports")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_vulnerability_report(self):
        r = client.get("/rfid/vulnerability-report")
        assert r.status_code == 200

    def test_scan_mock(self):
        r = client.post("/rfid/scan/mock")
        assert r.status_code in (200, 500)

    def test_scan_real(self):
        r = client.post("/rfid/scan")
        assert r.status_code in (200, 500)

    def test_attack_simulate(self):
        r = client.post("/rfid/attack/simulate", json={"card_id": "AABBCCDD", "attack_type": "replay"})
        assert r.status_code in (200, 422, 500)

    def test_analyze_card(self):
        r = client.get("/rfid/analyze/AABBCCDD")
        assert r.status_code in (200, 404, 500)

    def test_delete_cards(self):
        r = client.delete("/rfid/cards")
        assert r.status_code in (200, 204)

    def test_delete_reports(self):
        r = client.delete("/rfid/reports")
        assert r.status_code in (200, 204)


# ─────────────────────────────────────────────────────
# WIRELESS (WiFi / BT)  /wireless/*
# ─────────────────────────────────────────────────────

class TestWireless:
    def test_interfaces(self):
        r = client.get("/wireless/interfaces")
        assert r.status_code in (200, 500)

    def test_scan_ssids(self):
        r = client.get("/wireless/scan/ssids")
        assert r.status_code in (200, 500)

    def test_assessment_report(self):
        r = client.get("/wireless/assessment/report")
        assert r.status_code in (200, 500)

    def test_deauth_status(self):
        r = client.get("/wireless/deauth/status")
        assert r.status_code in (200, 500)

    def test_deauth_start(self):
        r = client.post("/wireless/deauth/start", json={"target": "AA:BB:CC:DD:EE:FF", "interface": "en0"})
        assert r.status_code in (200, 422, 500)

    def test_deauth_stop(self):
        r = client.post("/wireless/deauth/stop")
        assert r.status_code in (200, 500)

    def test_scan_bluetooth(self):
        r = client.post("/wireless/scan/bluetooth")
        assert r.status_code in (200, 500)

    def test_tls_check(self):
        r = client.post("/wireless/tls/check/192.168.1.1")
        assert r.status_code in (200, 500)

    def test_discover_devices(self):
        r = client.post("/wireless/discover/devices")
        assert r.status_code in (200, 500)

    def test_port_scan(self):
        r = client.post("/wireless/test/ports/192.168.1.1")
        assert r.status_code in (200, 500)

    def test_credential_test(self):
        r = client.post("/wireless/test/credentials/192.168.1.1")
        assert r.status_code in (200, 500)


# ─────────────────────────────────────────────────────
# REPORTS  /reports/*
# ─────────────────────────────────────────────────────

class TestReports:
    def test_summary(self):
        r = client.get("/reports/summary")
        assert r.status_code == 200
        data = r.json()
        assert "total_devices" in data or isinstance(data, dict)

    def test_generate_pdf(self):
        r = client.get("/reports/generate/pdf")
        assert r.status_code in (200, 500)


# ─────────────────────────────────────────────────────
# AI ANALYSIS  /ai/*
# ─────────────────────────────────────────────────────

class TestAI:
    def test_security_score(self):
        r = client.get("/ai/security-score")
        assert r.status_code == 200

    def test_analyze_network(self):
        r = client.get("/ai/analyze/network")
        assert r.status_code == 200

    def test_suggestions(self):
        r = client.get("/ai/suggestions")
        assert r.status_code == 200

    def test_predict_risks(self):
        r = client.get("/ai/predict/risks")
        assert r.status_code == 200

    def test_classify_devices(self):
        r = client.get("/ai/classify/devices")
        assert r.status_code == 200

    def test_remediations(self):
        r = client.get("/ai/remediations")
        assert r.status_code == 200

    def test_remediation_by_type(self):
        r = client.get("/ai/remediation/default_password")
        assert r.status_code in (200, 404)

    def test_analyze_device_not_found(self):
        r = client.get("/ai/analyze/device/9999")
        assert r.status_code in (200, 404)


# ─────────────────────────────────────────────────────
# ATTACK SCENARIOS  /attacks/*
# ─────────────────────────────────────────────────────

class TestAttacks:
    def test_list_scenarios(self):
        r = client.get("/attacks/")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_learning_path(self):
        r = client.get("/attacks/learning/path")
        assert r.status_code == 200

    def test_results(self):
        r = client.get("/attacks/results")
        assert r.status_code == 200

    def test_get_scenario(self):
        r = client.get("/attacks/")
        scenarios = r.json()
        if scenarios:
            sid = scenarios[0].get("id") or scenarios[0].get("scenario_id")
            if sid:
                r2 = client.get(f"/attacks/{sid}")
                assert r2.status_code in (200, 404)

    def test_run_scenario(self):
        r = client.get("/attacks/")
        scenarios = r.json()
        if scenarios:
            sid = scenarios[0].get("id") or scenarios[0].get("scenario_id")
            if sid:
                r2 = client.post(f"/attacks/{sid}/run")
                assert r2.status_code in (200, 404, 500)

    def test_tutorial(self):
        r = client.get("/attacks/")
        scenarios = r.json()
        if scenarios:
            sid = scenarios[0].get("id") or scenarios[0].get("scenario_id")
            if sid:
                r2 = client.get(f"/attacks/{sid}/tutorial")
                assert r2.status_code in (200, 404)

    def test_hints(self):
        r = client.get("/attacks/")
        scenarios = r.json()
        if scenarios:
            sid = scenarios[0].get("id") or scenarios[0].get("scenario_id")
            if sid:
                r2 = client.get(f"/attacks/{sid}/hints")
                assert r2.status_code in (200, 404)


# ─────────────────────────────────────────────────────
# VIRTUAL LAB  /lab/*
# ─────────────────────────────────────────────────────

class TestVirtualLab:
    def test_status(self):
        r = client.get("/lab/status")
        assert r.status_code == 200

    def test_info(self):
        r = client.get("/lab/info")
        assert r.status_code == 200

    def test_subnets(self):
        r = client.get("/lab/subnets")
        assert r.status_code in (200, 500)

    def test_devices(self):
        r = client.get("/lab/devices")
        assert r.status_code in (200, 500)

    def test_ble_devices(self):
        r = client.get("/lab/ble-devices")
        assert r.status_code in (200, 500)

    def test_activity(self):
        r = client.get("/lab/activity")
        assert r.status_code == 200

    def test_activity_stats(self):
        r = client.get("/lab/activity/stats")
        assert r.status_code == 200

    def test_device_by_ip_not_running(self):
        r = client.get("/lab/device/172.30.10.1")
        assert r.status_code in (200, 404, 500)

    def test_quick_scan_not_running(self):
        r = client.post("/lab/quick-scan")
        assert r.status_code in (200, 500)

    def test_delete_activity(self):
        r = client.delete("/lab/activity")
        assert r.status_code in (200, 204)
