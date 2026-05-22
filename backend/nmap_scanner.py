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

    # Curated common-services + IoT-heavy port list. Covers ~95% of what we
    # care about and is ~5× faster than scanning Nmap's top-1000 default.
    DEFAULT_PORTS = (
        "21,22,23,25,53,67,68,80,81,82,83,88,110,111,123,135,137,139,143,"
        "161,179,389,443,445,465,500,502,514,515,520,548,554,587,593,623,"
        "631,636,664,853,873,902,993,995,1080,1194,1433,1521,1723,1883,"
        "1900,2049,2082,2083,2222,2375,2379,3000,3128,3260,3306,3389,3478,"
        "3689,3702,4369,4505,4506,4567,4664,4840,5000,5001,5060,5061,5222,"
        "5353,5432,5555,5601,5672,5683,5800,5900,5901,5984,6000,6379,6443,"
        "6633,6666,6667,7000,7547,7657,7777,8000,8008,8009,8010,8020,8080,"
        "8081,8083,8086,8088,8089,8090,8181,8200,8222,8333,8443,8500,8530,"
        "8531,8649,8883,8888,9000,9001,9042,9090,9091,9100,9200,9300,9418,"
        "9443,9999,10000,11211,15672,25565,27017,28015,32400,49152"
    )

    def scan(self, target: str, version_detection: bool = True,
             port_range: str = None, host_discovery: bool = False) -> dict:
        """
        Performs a real Nmap scan and returns structured JSON.

        Args:
            target: IP or hostname
            version_detection: run -sV (slower, ~+20s) for CPE extraction
            port_range: explicit Nmap -p value; if None uses DEFAULT_PORTS
            host_discovery: if False (default) we pass -Pn — skips ping and
                            saves ~3s when caller already knows host is up
                            (which is our common case after a network sweep).
        """
        if not self.nmap_path:
            return {"error": "Nmap not installed", "target": target, "ports": []}

        if not self.is_valid_target(target):
            return {"error": "Invalid target IP or hostname", "target": target, "ports": []}

        # Speed flags:
        #   -T4              aggressive timing template
        #   --min-rate       push packets out without waiting for slow replies
        #                    (override via PENTEX_NMAP_MIN_RATE env var: lower
        #                    on Pi 3 / weak adapters, raise on wired LANs)
        #   --max-retries 1  one retransmit instead of nmap's default ~10
        #   --host-timeout   give up after 90s per host (defensive)
        #   --open           only emit open ports → smaller XML, faster parse
        #   -Pn              skip ping (caller usually knows host is up)
        min_rate = os.environ.get("PENTEX_NMAP_MIN_RATE", "1000")
        args = [
            self.nmap_path, "-oX", "-",
            "-T4", "--min-rate", min_rate, "--max-retries", "1",
            "--host-timeout", "90s", "--open",
        ]
        if not host_discovery:
            args.append("-Pn")
        args.extend(["-p", port_range or self.DEFAULT_PORTS])
        if version_detection:
            # --version-intensity 5 (default is 7) trims ~10s on noisy services
            args.extend(["-sV", "--version-intensity", "5"])
        args.append(target)

        try:
            logger.info(f"Running Nmap: {' '.join(args)}")
            # Cap subprocess runtime as a hard backstop in case --host-timeout
            # isn't honored (rare, but worth being defensive).
            result = subprocess.run(args, capture_output=True, text=True,
                                    check=True, timeout=180)
            return self._parse_xml(result.stdout, target)

        except subprocess.TimeoutExpired:
            logger.warning(f"Nmap scan exceeded 180s for {target}")
            return {"error": "Nmap scan timed out", "target": target, "ports": []}
        except subprocess.CalledProcessError as e:
            logger.error(f"Nmap execution failed: {e.stderr}")
            if "requires root privileges" in e.stderr:
                # Fallback to TCP Connect scan if SYN scan needs root
                if "-sS" in args:
                    logger.info("Retrying with TCP Connect scan (-sT)...")
                    args = [a for a in args if a != "-sS"] + ["-sT"]
                    try:
                        result = subprocess.run(args, capture_output=True, text=True,
                                                check=True, timeout=180)
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
                        product = ""
                        version_num = ""
                        cpes = []

                        if service_elem is not None:
                            service_name = service_elem.get('name', 'unknown')
                            product = service_elem.get('product', '')
                            version_num = service_elem.get('version', '')
                            extrainfo = service_elem.get('extrainfo', '')
                            version = f"{product} {version_num} {extrainfo}".strip()
                            cpes = [c.text for c in service_elem.findall('cpe') if c.text]

                        scan_results["ports"].append({
                            "port": port_id,
                            "state": state,
                            "service": service_name,
                            "product": product,
                            "version_num": version_num,
                            "version": version,
                            "cpes": cpes
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
