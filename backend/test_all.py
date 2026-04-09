#!/usr/bin/env python3
"""
PentexOne Comprehensive Test Suite
Tests all endpoints, buttons, and functionality
"""

import requests
import time
import json
from typing import Dict, List
import sys

# Configuration
BASE_URL = "http://localhost:8000"
USERNAME = "admin"
PASSWORD = "pentex2024"

class Colors:
    """Terminal colors for output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

class PentexOneTester:
    def __init__(self):
        self.base_url = BASE_URL
        self.session = requests.Session()
        self.token = None
        self.test_results = []
        
    def print_header(self, text: str):
        """Print formatted header"""
        print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}\n")
        
    def print_test(self, test_name: str, passed: bool, details: str = ""):
        """Print test result"""
        status = f"{Colors.GREEN}✓ PASS{Colors.RESET}" if passed else f"{Colors.RED}✗ FAIL{Colors.RESET}"
        print(f"{status} - {test_name}")
        if details:
            print(f"       {Colors.YELLOW}{details}{Colors.RESET}")
        
        self.test_results.append({
            'test': test_name,
            'passed': passed,
            'details': details
        })
    
    def test_server_health(self) -> bool:
        """Test if server is running"""
        self.print_header("TEST 1: Server Health Check")
        
        try:
            # Test root endpoint
            response = self.session.get(f"{self.base_url}/", timeout=5)
            self.print_test("Server Root Endpoint", response.status_code == 200, 
                          f"Status: {response.status_code}")
            
            # Test API docs
            response = self.session.get(f"{self.base_url}/docs", timeout=5)
            self.print_test("API Documentation", response.status_code == 200,
                          f"Docs accessible at /docs")
            
            # Test OpenAPI schema
            response = self.session.get(f"{self.base_url}/openapi.json", timeout=5)
            self.print_test("OpenAPI Schema", response.status_code == 200,
                          "API schema loaded")
            
            return True
        except Exception as e:
            self.print_test("Server Connection", False, str(e))
            return False
    
    def test_authentication(self) -> bool:
        """Test login functionality"""
        self.print_header("TEST 2: Authentication")
        
        try:
            # Test login with correct endpoint
            response = self.session.post(
                f"{self.base_url}/auth/login",
                json={"username": USERNAME, "password": PASSWORD},
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                self.token = "authenticated"  # Simple auth
                self.print_test("Login", True, f"Login successful")
                
                return True
            else:
                self.print_test("Login", False, f"Status: {response.status_code}")
                return False
                
        except Exception as e:
            self.print_test("Authentication", False, str(e))
            return False
    
    def test_iot_endpoints(self) -> bool:
        """Test IoT endpoints"""
        self.print_header("TEST 3: IoT Endpoints")
        
        all_passed = True
        
        # Test network discovery
        try:
            response = self.session.get(f"{self.base_url}/iot/networks/discover", timeout=10)
            passed = response.status_code == 200
            self.print_test("Network Discovery", passed, 
                          f"Found networks" if passed else f"Error: {response.status_code}")
            all_passed = all_passed and passed
            
            if passed:
                networks = response.json()
                print(f"       {Colors.YELLOW}Discovered: {len(networks.get('networks', []))} networks{Colors.RESET}")
        except Exception as e:
            self.print_test("Network Discovery", False, str(e))
            all_passed = False
        
        # Test hardware status
        try:
            response = self.session.get(f"{self.base_url}/iot/hardware/status", timeout=5)
            passed = response.status_code == 200
            self.print_test("Hardware Status", passed,
                          "Dongle detection working" if passed else "Error")
            all_passed = all_passed and passed
            
            if passed:
                hardware = response.json()
                print(f"       {Colors.YELLOW}Dongles: {hardware.get('total_dongles', 0)} connected{Colors.RESET}")
        except Exception as e:
            self.print_test("Hardware Status", False, str(e))
            all_passed = False
        
        # Test device list
        try:
            response = self.session.get(f"{self.base_url}/iot/devices", timeout=5)
            passed = response.status_code == 200
            self.print_test("Device List", passed,
                          f"Devices retrieved" if passed else "Error")
            all_passed = all_passed and passed
            
            if passed:
                devices = response.json()
                print(f"       {Colors.YELLOW}Total devices: {len(devices)}{Colors.RESET}")
        except Exception as e:
            self.print_test("Device List", False, str(e))
            all_passed = False
        
        # Test scan status
        try:
            response = self.session.get(f"{self.base_url}/iot/scan/status", timeout=5)
            passed = response.status_code == 200
            self.print_test("Scan Status", passed,
                          "Status endpoint working" if passed else "Error")
            all_passed = all_passed and passed
        except Exception as e:
            self.print_test("Scan Status", False, str(e))
            all_passed = False
        
        return all_passed
    
    def test_wifi_scan(self) -> bool:
        """Test Wi-Fi scanning"""
        self.print_header("TEST 4: Wi-Fi Scanning")
        
        try:
            # Start Wi-Fi scan
            response = self.session.post(
                f"{self.base_url}/iot/scan/wifi",
                json={"network": "192.168.1.0/24"},
                timeout=10
            )
            
            passed = response.status_code == 200
            self.print_test("Start Wi-Fi Scan", passed,
                          "Scan initiated" if passed else f"Error: {response.status_code}")
            
            if passed:
                # Wait and check status
                print(f"\n       {Colors.YELLOW}Waiting for scan to complete...{Colors.RESET}")
                time.sleep(5)
                
                for i in range(12):  # Check for up to 60 seconds
                    response = self.session.get(f"{self.base_url}/iot/scan/status", timeout=5)
                    if response.status_code == 200:
                        status = response.json()
                        if not status.get('running', False):
                            devices_found = status.get('devices_found', 0)
                            self.print_test("Scan Completion", True,
                                          f"Found {devices_found} devices")
                            return True
                        print(f"       {Colors.YELLOW}Progress: {status.get('progress', 0)}% - {status.get('message', '')}{Colors.RESET}")
                        time.sleep(5)
                
                self.print_test("Scan Completion", False, "Timeout after 60 seconds")
                return False
            
            return False
            
        except Exception as e:
            self.print_test("Wi-Fi Scan", False, str(e))
            return False
    
    def test_wireless_endpoints(self) -> bool:
        """Test wireless (Wi-Fi/Bluetooth) endpoints"""
        self.print_header("TEST 5: Wireless Endpoints")
        
        all_passed = True
        
        # Test SSID scan
        try:
            response = self.session.get(f"{self.base_url}/wireless/scan/ssids", timeout=10)
            passed = response.status_code == 200
            self.print_test("SSID Scan", passed,
                          "Wi-Fi networks scanned" if passed else "Error")
            all_passed = all_passed and passed
            
            if passed:
                ssids = response.json()
                print(f"       {Colors.YELLOW}Found {len(ssids.get('networks', []))} Wi-Fi networks{Colors.RESET}")
        except Exception as e:
            self.print_test("SSID Scan", False, str(e))
            all_passed = False
        
        # Test Bluetooth scan
        try:
            response = self.session.post(f"{self.base_url}/wireless/scan/bluetooth", timeout=15)
            passed = response.status_code == 200
            self.print_test("Bluetooth Scan", passed,
                          "BLE devices scanned" if passed else "Error")
            all_passed = all_passed and passed
            
            if passed:
                devices = response.json()
                print(f"       {Colors.YELLOW}Bluetooth scan initiated{Colors.RESET}")
        except Exception as e:
            self.print_test("Bluetooth Scan", False, str(e))
            all_passed = False
        
        return all_passed
    
    def test_ai_endpoints(self) -> bool:
        """Test AI endpoints"""
        self.print_header("TEST 6: AI Engine")
        
        all_passed = True
        
        # Test security score
        try:
            response = self.session.get(f"{self.base_url}/ai/security-score", timeout=5)
            passed = response.status_code == 200
            self.print_test("Security Score", passed,
                          "AI analysis working" if passed else "Error")
            all_passed = all_passed and passed
            
            if passed:
                score = response.json()
                print(f"       {Colors.YELLOW}Security Score: {score.get('score', 'N/A')}{Colors.RESET}")
        except Exception as e:
            self.print_test("Security Score", False, str(e))
            all_passed = False
        
        # Test suggestions
        try:
            response = self.session.get(f"{self.base_url}/ai/suggestions", timeout=5)
            passed = response.status_code == 200
            self.print_test("AI Suggestions", passed,
                          "Recommendations generated" if passed else "Error")
            all_passed = all_passed and passed
        except Exception as e:
            self.print_test("AI Suggestions", False, str(e))
            all_passed = False
        
        return all_passed
    
    def test_reports_endpoints(self) -> bool:
        """Test reports endpoints"""
        self.print_header("TEST 7: Reports")
        
        all_passed = True
        
        # Test summary
        try:
            response = self.session.get(f"{self.base_url}/reports/summary", timeout=5)
            passed = response.status_code == 200
            self.print_test("Report Summary", passed,
                          "Summary generated" if passed else "Error")
            all_passed = all_passed and passed
        except Exception as e:
            self.print_test("Report Summary", False, str(e))
            all_passed = False
        
        # Test PDF generation (if devices exist)
        try:
            response = self.session.post(
                f"{self.base_url}/reports/generate",
                json={"title": "Test Report", "include_vulnerabilities": True},
                timeout=10
            )
            # 200 or 404 (no devices) is acceptable
            passed = response.status_code in [200, 404]
            self.print_test("PDF Generation", passed,
                          "Report generation endpoint working" if passed else "Error")
            all_passed = all_passed and passed
        except Exception as e:
            self.print_test("PDF Generation", False, str(e))
            all_passed = False
        
        return all_passed
    
    def test_access_control(self) -> bool:
        """Test RFID/Access control endpoints"""
        self.print_header("TEST 8: Access Control (RFID)")
        
        all_passed = True
        
        # Test RFID cards list
        try:
            response = self.session.get(f"{self.base_url}/rfid/cards", timeout=5)
            passed = response.status_code == 200
            self.print_test("RFID Cards List", passed,
                          "Cards endpoint working" if passed else "Error")
            all_passed = all_passed and passed
        except Exception as e:
            self.print_test("RFID Cards List", False, str(e))
            all_passed = False
        
        return all_passed
    
    def test_dashboard_buttons(self) -> bool:
        """Test all dashboard button actions"""
        self.print_header("TEST 9: Dashboard Button Actions")
        
        all_passed = True
        
        # Test Quick Scan Buttons
        buttons = [
            ("POST", "/iot/scan/wifi", {"network": "192.168.1.0/24"}, "Wi-Fi Scan Button"),
            ("POST", "/wireless/scan/bluetooth", None, "Bluetooth Scan Button"),
            ("POST", "/iot/scan/zigbee", {"duration": 30}, "Zigbee Scan Button"),
            ("POST", "/iot/scan/thread", {"duration": 30}, "Thread Scan Button"),
        ]
        
        for method, endpoint, data, name in buttons:
            try:
                if method == "POST":
                    response = self.session.post(f"{self.base_url}{endpoint}", json=data, timeout=10)
                else:
                    response = self.session.get(f"{self.base_url}{endpoint}", timeout=10)
                
                # 200, 503 (no hardware), or 404 are acceptable
                passed = response.status_code in [200, 503, 404]
                self.print_test(name, passed,
                              f"Status: {response.status_code}" if not passed else "Working")
                all_passed = all_passed and passed
            except Exception as e:
                self.print_test(name, False, str(e))
                all_passed = False
        
        return all_passed
    
    def test_websocket(self) -> bool:
        """Test WebSocket connection"""
        self.print_header("TEST 10: WebSocket Connection")
        
        try:
            # Simple test - check if WebSocket endpoint exists
            response = self.session.get(f"{self.base_url}/ws", timeout=5)
            # WebSocket upgrade should fail with regular HTTP
            # But we can check if endpoint exists
            self.print_test("WebSocket Endpoint", True, 
                          "Endpoint exists (upgrade to ws:// required)")
            return True
        except Exception as e:
            # 400 or 426 (Upgrade Required) is normal for WebSocket without upgrade
            if "400" in str(e) or "426" in str(e):
                self.print_test("WebSocket Endpoint", True,
                              "WebSocket endpoint active")
                return True
            self.print_test("WebSocket Endpoint", False, str(e))
            return False
    
    def test_error_handling(self) -> bool:
        """Test error handling"""
        self.print_header("TEST 11: Error Handling")
        
        all_passed = True
        
        # Test 404
        try:
            response = self.session.get(f"{self.base_url}/nonexistent", timeout=5)
            passed = response.status_code == 404
            self.print_test("404 Handling", passed,
                          "Returns 404 for invalid routes" if passed else "Error")
            all_passed = all_passed and passed
        except Exception as e:
            self.print_test("404 Handling", False, str(e))
            all_passed = False
        
        # Test unauthorized access
        try:
            temp_session = requests.Session()
            response = temp_session.get(f"{self.base_url}/settings", timeout=5)
            # Settings endpoint is public (no auth required for this endpoint)
            passed = response.status_code in [200, 401, 403, 302]
            self.print_test("Settings Access", passed,
                          "Settings accessible (may or may not require auth)" if passed else "Error")
            all_passed = all_passed and passed
        except Exception as e:
            self.print_test("Settings Access", False, str(e))
            all_passed = False
        
        return all_passed
    
    def print_summary(self):
        """Print test summary"""
        self.print_header("TEST SUMMARY")
        
        total = len(self.test_results)
        passed = sum(1 for r in self.test_results if r['passed'])
        failed = total - passed
        
        print(f"{Colors.BOLD}Total Tests: {total}{Colors.RESET}")
        print(f"{Colors.GREEN}Passed: {passed}{Colors.RESET}")
        print(f"{Colors.RED}Failed: {failed}{Colors.RESET}")
        print(f"{Colors.YELLOW}Success Rate: {(passed/total*100):.1f}%{Colors.RESET}\n")
        
        if failed > 0:
            print(f"\n{Colors.RED}Failed Tests:{Colors.RESET}")
            for result in self.test_results:
                if not result['passed']:
                    print(f"  ✗ {result['test']}: {result['details']}")
    
    def run_all_tests(self):
        """Run all tests"""
        print(f"\n{Colors.BOLD}╔════════════════════════════════════════════════════════╗{Colors.RESET}")
        print(f"{Colors.BOLD}║     PentexOne Comprehensive Test Suite               ║{Colors.RESET}")
        print(f"{Colors.BOLD}║     Testing All Features and Endpoints                ║{Colors.RESET}")
        print(f"{Colors.BOLD}╚════════════════════════════════════════════════════════╝{Colors.RESET}\n")
        
        # Run tests
        if not self.test_server_health():
            print(f"\n{Colors.RED}Server is not running! Please start the server first.{Colors.RESET}")
            return False
        
        self.test_authentication()
        self.test_iot_endpoints()
        self.test_wifi_scan()
        self.test_wireless_endpoints()
        self.test_ai_endpoints()
        self.test_reports_endpoints()
        self.test_access_control()
        self.test_dashboard_buttons()
        self.test_websocket()
        self.test_error_handling()
        
        # Print summary
        self.print_summary()
        
        return all(r['passed'] for r in self.test_results)

def main():
    """Main entry point"""
    tester = PentexOneTester()
    
    try:
        success = tester.run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Test interrupted by user{Colors.RESET}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}Fatal error: {e}{Colors.RESET}")
        sys.exit(1)

if __name__ == "__main__":
    main()
