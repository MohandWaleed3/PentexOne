import subprocess
import json
import xml.etree.ElementTree as ET
import re
import os
import shutil
import logging

logger = logging.getLogger(__name__)

class PentexNmapScanner:
    def __init__(self, nmap_path: str = None):
        self.nmap_path = nmap_path or shutil.which("nmap")
        if not self.nmap_path:
            logger.error("Nmap binary not found in PATH. Please install Nmap.")

    def is_valid_target(self, target: str) -> bool:
        """Simple IP/Hostname validation."""
        ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        hostname_pattern = r'^[a-zA-Z0-9\.-]+$'
        return bool(re.match(ip_pattern, target)) or bool(re.match(hostname_pattern, target))

    def scan(self, target: str, version_detection: bool = True) -> dict:
        """
        Performs a real Nmap scan and returns structured JSON.
        """
        if not self.nmap_path:
            return {"error": "Nmap not installed", "target": target, "ports": []}
        
        if not self.is_valid_target(target):
            return {"error": "Invalid target IP or hostname", "target": target, "ports": []}

        # Build arguments
        # -oX -: Output to XML on stdout
        # -T4: Faster execution
        # -F: Fast scan (top 100 ports) or specific range
        args = [self.nmap_path, "-oX", "-", "-T4", "--open"]
        
        if version_detection:
            args.append("-sV")
        
        args.append(target)

        try:
            # Run Nmap via subprocess
            logger.info(f"Running Nmap: {' '.join(args)}")
            result = subprocess.run(args, capture_output=True, text=True, check=True)
            return self._parse_xml(result.stdout, target)
        
        except subprocess.CalledProcessError as e:
            logger.error(f"Nmap execution failed: {e.stderr}")
            if "requires root privileges" in e.stderr:
                # Fallback to TCP Connect scan if Syn scan fails due to privileges
                if "-sS" in args:
                    logger.info("Retrying with TCP Connect scan (-sT)...")
                    args = [a for a in args if a != "-sS"] + ["-sT"]
                    try:
                        result = subprocess.run(args, capture_output=True, text=True, check=True)
                        return self._parse_xml(result.stdout, target)
                    except Exception as ex:
                        return {"error": f"Nmap retry failed: {str(ex)}", "target": target, "ports": []}
            return {"error": f"Nmap failed: {e.stderr}", "target": target, "ports": []}
        except Exception as e:
            logger.error(f"Unexpected scanner error: {e}")
            return {"error": str(e), "target": target, "ports": []}

    def _parse_xml(self, xml_data: str, target: str) -> dict:
        """Parses Nmap XML output into the required JSON structure."""
        try:
            root = ET.fromstring(xml_data)
            scan_results = {
                "target": target,
                "ports": []
            }

            for host in root.findall('host'):
                for ports in host.findall('ports'):
                    for port in ports.findall('port'):
                        port_id = int(port.get('portid'))
                        state_elem = port.find('state')
                        state = state_elem.get('state') if state_elem is not None else "unknown"
                        
                        service_elem = port.find('service')
                        service_name = "unknown"
                        version = ""
                        
                        if service_elem is not None:
                            service_name = service_elem.get('name', 'unknown')
                            product = service_elem.get('product', '')
                            version_num = service_elem.get('version', '')
                            extrainfo = service_elem.get('extrainfo', '')
                            version = f"{product} {version_num} {extrainfo}".strip()

                        scan_results["ports"].append({
                            "port": port_id,
                            "state": state,
                            "service": service_name,
                            "version": version
                        })

            return scan_results
        except Exception as e:
            logger.error(f"XML Parsing error: {e}")
            return {"error": f"XML Parse error: {str(e)}", "target": target, "ports": []}

# Simple CLI test
if __name__ == "__main__":
    scanner = PentexNmapScanner()
    res = scanner.scan("127.0.0.1")
    print(json.dumps(res, indent=2))
