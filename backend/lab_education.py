"""
PentexOne Lab Education System
================================
Tutorial content, progressive hints, and scoring for each attack scenario.

Structure per scenario:
  - tutorial    : background, concept explanation, real-world impact
  - hints       : 3 progressive hints (costs 10 pts each)
  - base_score  : maximum points for completing without hints
  - time_limit  : seconds before time penalty starts
"""

from typing import Dict, List

# ──────────────────────────────────────────────────────────────────────────────
# Tutorial content — one per scenario
# ──────────────────────────────────────────────────────────────────────────────

TUTORIALS: Dict[str, Dict] = {

    "wifi-01": {
        "scenario_id": "wifi-01",
        "title": "Default Credentials — The IoT Achilles' Heel",
        "difficulty": "easy",
        "reading_time_min": 3,
        "concept": (
            "Most IoT devices ship with factory-default credentials (admin/admin, "
            "root/root, admin/password). Manufacturers do this for ease of setup, "
            "but millions of devices are deployed without ever changing them. "
            "This creates a massive attack surface — any attacker who knows the "
            "brand can gain instant admin access."
        ),
        "real_world": (
            "The Mirai botnet (2016) exploited default credentials on 600,000+ cameras "
            "and DVRs to launch the largest DDoS attack in history (1.2 Tbps). "
            "Hikvision cameras were among the most targeted devices."
        ),
        "vulnerability_details": {
            "type": "DEFAULT_CREDENTIALS",
            "cvss_score": 9.8,
            "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
            "cwe": "CWE-1188: Initialization of a Resource with an Insecure Default",
        },
        "what_to_look_for": [
            "HTTP 401 on protected paths — Basic Auth challenge",
            "Server header revealing manufacturer and firmware version",
            "Try: admin/admin, admin/12345, root/root, admin/password",
            "ISAPI endpoint at /ISAPI/System/deviceInfo reveals device model",
        ],
        "learning_objectives": [
            "Understand how HTTP Basic Authentication works",
            "Identify camera web interfaces by their HTTP response headers",
            "Practice credential enumeration against web services",
            "Recognize the impact of unchanged factory passwords",
        ],
        "remediation_deep_dive": (
            "1. Force password change on first login (mandatory, not optional)\n"
            "2. Implement account lockout after 5 failed attempts\n"
            "3. Use a credential management database (Vault, CyberArk)\n"
            "4. Network-segment cameras onto a dedicated VLAN with firewall rules\n"
            "5. Monitor for default credential usage in SIEM"
        ),
    },

    "wifi-02": {
        "scenario_id": "wifi-02",
        "title": "MQTT — The Unsecured IoT Message Bus",
        "difficulty": "easy",
        "reading_time_min": 4,
        "concept": (
            "MQTT (Message Queuing Telemetry Transport) is the de-facto protocol "
            "for IoT device communication. It uses a publish/subscribe model through "
            "a central broker. When anonymous access is enabled, any device on the "
            "network can subscribe to ALL topics and inject messages, completely "
            "compromising the integrity of sensor data and device commands."
        ),
        "real_world": (
            "In 2020, researchers found 200,000+ MQTT brokers publicly exposed with "
            "anonymous access enabled — leaking medical sensor data, industrial control "
            "commands, and home automation signals. One exposed broker served a hospital "
            "ICU ward."
        ),
        "vulnerability_details": {
            "type": "NO_AUTHENTICATION",
            "cvss_score": 9.1,
            "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N",
            "cwe": "CWE-306: Missing Authentication for Critical Function",
        },
        "what_to_look_for": [
            "Open TCP port 1883 (MQTT) or 8883 (MQTT over TLS)",
            "WebSocket MQTT on port 9001",
            "CONNECT packet with empty username/password → CONNACK 0x00",
            "Subscribe to '#' to see all topics",
            "Topics often reveal device types: sensor/, device/, home/, cmd/",
        ],
        "learning_objectives": [
            "Understand the MQTT pub/sub model and packet structure",
            "Use mosquitto_pub/sub or MQTT Explorer to interact with brokers",
            "Demonstrate message injection to falsify sensor readings",
            "Understand the difference between MQTT QoS levels",
        ],
        "remediation_deep_dive": (
            "1. Enable password authentication in mosquitto.conf: allow_anonymous false\n"
            "2. Use TLS (port 8883) with valid certificates\n"
            "3. Configure topic ACLs per client (who can pub/sub to what)\n"
            "4. Use MQTT 5.0 Enhanced Authentication for stronger auth\n"
            "5. Run broker on private VLAN — never expose 1883 to the internet"
        ),
    },

    "wifi-03": {
        "scenario_id": "wifi-03",
        "title": "Telnet — An Ancient Backdoor Still Running",
        "difficulty": "medium",
        "reading_time_min": 3,
        "concept": (
            "Telnet is a 1969 protocol that transmits all data — including passwords — "
            "in cleartext. Many embedded routers and IoT devices still include Telnet "
            "for 'maintenance' with factory credentials that users never change. "
            "A single Telnet shell gives root access to the entire device."
        ),
        "real_world": (
            "The VPNFilter malware (2018) targeted 500,000 routers across 54 countries, "
            "exploiting Telnet and default credentials. TP-Link routers were among the "
            "primary targets. CISA issued an emergency directive to restart all affected devices."
        ),
        "vulnerability_details": {
            "type": "TELNET_ENABLED",
            "cvss_score": 9.8,
            "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
            "cwe": "CWE-319: Cleartext Transmission of Sensitive Information",
        },
        "what_to_look_for": [
            "Open port 23 — banner typically shows: 'BusyBox v...' or 'login:'",
            "Test: root/root, root/admin, root/(empty), admin/admin",
            "After login: run 'id' to confirm root shell",
            "Check 'nvram show' for Wi-Fi passwords and admin credentials",
            "Check 'ps' and 'netstat -an' for running services",
        ],
        "learning_objectives": [
            "Connect to Telnet services manually using netcat or telnet client",
            "Understand why cleartext protocols are dangerous (Wireshark demo)",
            "Navigate a BusyBox embedded Linux environment",
            "Escalate from Telnet access to full network pivot",
        ],
        "remediation_deep_dive": (
            "1. Disable Telnet completely — use SSH with key-based authentication\n"
            "2. If SSH unavailable, at minimum firewall port 23 to loopback only\n"
            "3. Change all factory credentials before deployment\n"
            "4. Enable fail2ban or rate-limit login attempts\n"
            "5. Segment routers on management VLAN inaccessible from user devices"
        ),
    },

    "wifi-04": {
        "scenario_id": "wifi-04",
        "title": "Unauthenticated Local APIs — The Tuya Problem",
        "difficulty": "medium",
        "reading_time_min": 3,
        "concept": (
            "Many smart home devices expose a local HTTP API for LAN control. "
            "Tuya-based devices (used by hundreds of brands) historically exposed "
            "their local API without authentication, and leaked their local_key — "
            "a secret used to authenticate with the Tuya cloud. Anyone on the same "
            "LAN could control the device and impersonate it to the cloud."
        ),
        "real_world": (
            "The Tuya local protocol was reverse-engineered in 2019. Researchers found "
            "that the local_key was transmitted unencrypted, allowing full device control "
            "and account takeover. Millions of devices across brands like Gosund, "
            "BlitzWolf, and Teckin were affected."
        ),
        "vulnerability_details": {
            "type": "NO_LOCAL_AUTH",
            "cvss_score": 8.1,
            "cvss_vector": "CVSS:3.1/AV:A/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N",
            "cwe": "CWE-306: Missing Authentication for Critical Function",
        },
        "what_to_look_for": [
            "HTTP port 80 on smart plug responds with JSON device info",
            "GET /info returns: device_id, local_key, firmware_version",
            "POST /control accepts commands without any auth token",
            "Raw TCP port 6668 for Tuya protocol (encrypted with local_key)",
        ],
        "learning_objectives": [
            "Probe REST APIs with curl and identify unauthenticated endpoints",
            "Understand the risk of credential (local_key) exposure",
            "Use the local_key to authenticate to the real Tuya protocol",
            "Map the attack chain: LAN access → device control → cloud impersonation",
        ],
        "remediation_deep_dive": (
            "1. Require HMAC-signed requests for all local API calls\n"
            "2. Never return local_key in API responses — keep it device-internal\n"
            "3. Rotate local_key periodically (Tuya SDK supports key rotation)\n"
            "4. Bind local API to specific registered MAC addresses only\n"
            "5. Move to Matter protocol — it provides mutual TLS authentication"
        ),
    },

    "wifi-05": {
        "scenario_id": "wifi-05",
        "title": "Debug Interfaces — Left Open in Production",
        "difficulty": "hard",
        "reading_time_min": 4,
        "concept": (
            "IoT firmware often includes debug HTTP endpoints (/debug, /diag, /test) "
            "used during development and QA. When not removed before production, these "
            "endpoints frequently dump the entire device configuration — including "
            "Wi-Fi passwords, API tokens, and user PINs — in plaintext. "
            "This is especially dangerous in network-connected devices like smart thermostats."
        ),
        "real_world": (
            "CVE-2019-9483 affected Nest thermostats — a debug endpoint returned "
            "cleartext Wi-Fi credentials, allowing attackers on the network to pivot "
            "to the home Wi-Fi. Google (who owns Nest) patched it quietly in 2019. "
            "Similar issues have been found in Ring cameras and Philips Hue bridges."
        ),
        "vulnerability_details": {
            "type": "DEBUG_INTERFACE_EXPOSED",
            "cvss_score": 8.8,
            "cvss_vector": "CVSS:3.1/AV:A/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
            "cwe": "CWE-489: Active Debug Code",
        },
        "what_to_look_for": [
            "Scan all ports — devices often run debug on secondary ports (8080, 8888, 9090)",
            "Try paths: /debug, /diag, /diagnostic, /test, /dev, /dump, /config",
            "Look for 'debug=true' or 'X-Debug' headers in normal responses",
            "Debug dumps often include: wifi_password, access_token, device_pin",
        ],
        "learning_objectives": [
            "Perform full port scan with service detection (nmap -sV)",
            "Use directory brute-forcing to discover hidden paths (gobuster/ffuf)",
            "Parse JSON credential dumps and identify sensitive fields",
            "Understand OAuth token scope and what an attacker can do with them",
        ],
        "remediation_deep_dive": (
            "1. Remove all debug endpoints from production firmware builds\n"
            "2. Use build flags (DEBUG=0) to compile out debug code\n"
            "3. Never store credentials in plaintext — use OS keychain or secure enclave\n"
            "4. Implement firmware signing to prevent debug re-enabling\n"
            "5. Run automated secret scanning against firmware images before release"
        ),
    },

    "wifi-06": {
        "scenario_id": "wifi-06",
        "title": "Smart TV Surveillance — Unauthenticated Voice API",
        "difficulty": "easy",
        "reading_time_min": 3,
        "concept": (
            "Modern smart TVs include microphones for voice control and cameras for "
            "gesture recognition. Samsung, LG, and Vizio TVs have all been found to "
            "expose control APIs (DIAL, SmartThings) without authentication. "
            "An attacker on the same network can remotely activate the microphone, "
            "change content, or send arbitrary commands."
        ),
        "real_world": (
            "In 2017, WikiLeaks published CIA documents (Vault 7) showing 'Weeping Angel' "
            "— a tool that put Samsung smart TVs into a fake 'off' mode while recording "
            "audio via the built-in microphone. CVE-2018-3911 allowed unauthenticated "
            "HTTP commands to Samsung TVs on the local network."
        ),
        "vulnerability_details": {
            "type": "MIC_REMOTE_CONTROL",
            "cvss_score": 8.8,
            "cvss_vector": "CVSS:3.1/AV:A/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N",
            "cwe": "CWE-306: Missing Authentication for Critical Function",
        },
        "what_to_look_for": [
            "DIAL protocol on port 8008 or 8001 — identifies device as smart TV",
            "Samsung SmartThings API on port 9197",
            "Endpoints: /api/v1/voice/, /ms/1.0/service/voice/",
            "POST with empty body — no token or session required",
        ],
        "learning_objectives": [
            "Discover IoT services using DIAL/SSDP protocol probing",
            "Use curl to interact with REST APIs on smart home devices",
            "Understand the privacy implications of always-on microphones",
            "Map the attack surface of smart TV APIs",
        ],
        "remediation_deep_dive": (
            "1. Require authentication (OAuth 2.0) for all media control APIs\n"
            "2. Add physical mic/camera indicator lights that cannot be software-overridden\n"
            "3. Implement network-level firewall rules blocking TV API ports from untrusted devices\n"
            "4. Disable voice features if not explicitly enabled by the user\n"
            "5. Apply firmware updates automatically for security patches"
        ),
    },

    "wifi-07": {
        "scenario_id": "wifi-07",
        "title": "NAS Misconfiguration — Shadow Files in Shared Folders",
        "difficulty": "hard",
        "reading_time_min": 5,
        "concept": (
            "Network Attached Storage (NAS) devices are high-value targets: they hold "
            "all backup data, often with domain credentials. When outdated DSM firmware "
            "is combined with SMBv1 (EternalBlue) and world-readable shared folders, "
            "attackers can download password hashes without any authentication, then "
            "crack them offline. Even a single cracked hash gives domain admin access."
        ),
        "real_world": (
            "WannaCry (2017) and NotPetya (2017) both used EternalBlue (MS17-010) to "
            "spread through networks via SMBv1. Synology NAS devices running old DSM "
            "versions were directly impacted. CVE-2021-29086 allowed unauthenticated "
            "file access on Synology DSM < 7.0."
        ),
        "vulnerability_details": {
            "type": "SHADOW_BACKUP_EXPOSED",
            "cvss_score": 9.1,
            "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N",
            "cwe": "CWE-552: Files or Directories Accessible to External Parties",
        },
        "what_to_look_for": [
            "DSM admin panel on port 5000/5001",
            "GET /webapi/query.cgi — unauthenticated API returns firmware version",
            "Look for shared folders: /shared/backup/, /public/, /files/",
            "Files: etc-shadow.bak, passwd.bak, dsm-config.tar.gz",
            "Shadow hash format $6$ = SHA-512 crypt — crackable with hashcat",
        ],
        "learning_objectives": [
            "Identify outdated NAS firmware from HTTP response headers",
            "Traverse shared folder paths via HTTP",
            "Understand /etc/shadow hash format ($6$, $5$, $1$)",
            "Use hashcat with rockyou.txt to crack SHA-512 crypt hashes",
        ],
        "remediation_deep_dive": (
            "1. Update DSM to latest version immediately — enable auto-updates\n"
            "2. Disable SMBv1 (Control Panel → File Services → SMB → disable SMBv1)\n"
            "3. Set shared folder permissions to deny guest/anonymous access\n"
            "4. Never store backup files with sensitive data in web-accessible locations\n"
            "5. Enable 2FA for all DSM admin accounts\n"
            "6. Enable Synology Firewall and block all access except required IPs"
        ),
    },

    "ble-01": {
        "scenario_id": "ble-01",
        "title": "BLE Smart Locks — Physical Security via Software",
        "difficulty": "easy",
        "reading_time_min": 4,
        "concept": (
            "BLE smart locks replace the physical key with a smartphone app. "
            "The security depends entirely on BLE pairing mode. 'Just Works' mode "
            "provides no authentication and is vulnerable to MITM. When a lock "
            "accepts WRITE_WITHOUT_RESPONSE on control characteristics without "
            "requiring pairing, any BLE device in range can unlock it silently."
        ),
        "real_world": (
            "In 2016, researchers found 12 of 16 popular BLE smart locks could be "
            "opened without authentication (DEF CON 24, 'Picking Bluetooth Low Energy "
            "Locks from a Quarter Mile Away'). The August Smart Lock was among the most "
            "studied. CVE-2016-6554 affected multiple BLE lock models."
        ),
        "vulnerability_details": {
            "type": "NO_PAIRING_REQUIRED",
            "cvss_score": 9.3,
            "cvss_vector": "CVSS:3.1/AV:A/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
            "cwe": "CWE-287: Improper Authentication",
        },
        "what_to_look_for": [
            "Advertised name contains 'Lock', 'Door', 'Key', or model number",
            "GATT service with lock state (readable) and command (writable) characteristics",
            "Write to command characteristic without pairing — if accepted, vulnerable",
            "Read access log characteristic — may expose PINs and timestamps",
        ],
        "learning_objectives": [
            "Use bluetoothctl or nRF Connect to discover and enumerate BLE devices",
            "Understand GATT service/characteristic hierarchy",
            "Distinguish between pairing modes (Just Works, Passkey, Numeric Comparison)",
            "Write characteristic values using gatttool or bleak",
        ],
        "remediation_deep_dive": (
            "1. Require Secure Connections with MITM protection (Passkey Entry minimum)\n"
            "2. Lock control characteristics must have ENCRYPTED_WRITE property\n"
            "3. Implement rolling codes or TOTP for unlock commands\n"
            "4. Add tamper detection — alert if BLE unlock is used without app session\n"
            "5. Log all lock/unlock events with timestamps to cloud for audit trail"
        ),
    },

    "ble-02": {
        "scenario_id": "ble-02",
        "title": "Wearable Privacy — Health Data Without Bonding",
        "difficulty": "easy",
        "reading_time_min": 3,
        "concept": (
            "Wearables continuously collect sensitive biometric data: heart rate, "
            "SpO2, sleep patterns, location, and sometimes medical readings. "
            "The Bluetooth SIG health profiles (Heart Rate Service, Glucose) specify "
            "that health characteristics MUST require ENCRYPTED_READ — but many "
            "manufacturers skip this requirement, exposing data to any nearby BLE device."
        ),
        "real_world": (
            "A 2019 study of fitness trackers found that 6 of 10 popular wearables "
            "broadcast identifiable data (MAC + health metrics) without encryption, "
            "enabling passive surveillance and location tracking by monitoring BLE "
            "advertisements. Fitbit, Garmin, and Mi Band were among those studied."
        ),
        "vulnerability_details": {
            "type": "EXPOSED_HEALTH_CHARACTERISTICS",
            "cvss_score": 7.5,
            "cvss_vector": "CVSS:3.1/AV:A/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N",
            "cwe": "CWE-311: Missing Encryption of Sensitive Data",
        },
        "what_to_look_for": [
            "GATT service 0x180D (Heart Rate Service)",
            "GATT service 0x1809 (Health Thermometer)",
            "Custom manufacturer services with health or user data",
            "Read characteristics without pairing first — if data returns, vulnerable",
        ],
        "learning_objectives": [
            "Enumerate all GATT services and characteristics on a wearable",
            "Identify standard Bluetooth SIG health service UUIDs",
            "Read health characteristics and parse the binary measurement format",
            "Understand the regulatory (HIPAA/GDPR) implications of health data exposure",
        ],
        "remediation_deep_dive": (
            "1. Mark all health characteristics with ENCRYPTED_READ or AUTHENTICATED_READ\n"
            "2. Require bonding with MITM protection before any data transfer\n"
            "3. Use Secure Connections (BLE 4.2+) — not legacy pairing\n"
            "4. Implement BLE MAC address randomization to prevent tracking\n"
            "5. Minimize data in BLE advertisements — only advertise device name"
        ),
    },

    "ble-03": {
        "scenario_id": "ble-03",
        "title": "Smart Bulbs — Hidden Secrets in GATT Characteristics",
        "difficulty": "medium",
        "reading_time_min": 3,
        "concept": (
            "Smart bulbs store their Wi-Fi credentials during provisioning. "
            "Some devices (LIFX, early Philips Hue) stored these in GATT "
            "characteristics readable over BLE without encryption. A hardcoded "
            "auth token (never rotated per device lifetime) compounds the problem: "
            "anyone reading it can impersonate the device to the manufacturer's cloud."
        ),
        "real_world": (
            "CVE-2014-8654 affected LIFX bulbs — Wi-Fi credentials were broadcast "
            "in plaintext BLE advertisement packets during provisioning. "
            "CVE-2020-6007 affected Philips Hue — a buffer overflow via ZigBee "
            "allowed attackers to pivot from a bulb to the entire home network."
        ),
        "vulnerability_details": {
            "type": "HARDCODED_KEY",
            "cvss_score": 8.1,
            "cvss_vector": "CVSS:3.1/AV:A/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N",
            "cwe": "CWE-321: Use of Hard-coded Cryptographic Key",
        },
        "what_to_look_for": [
            "Custom manufacturer GATT service with provisioning characteristics",
            "Characteristics labeled 'token', 'key', 'auth', 'wifi', 'ssid', 'password'",
            "Read long-format characteristics (> 20 bytes) — often contain credentials",
            "Look for ASCII strings in characteristic values (printable bytes)",
        ],
        "learning_objectives": [
            "Enumerate custom GATT services by UUID pattern",
            "Read raw characteristic bytes and decode as UTF-8/ASCII",
            "Understand IoT device provisioning flows (BLE → Wi-Fi handoff)",
            "Use the leaked auth token to query the manufacturer's cloud API",
        ],
        "remediation_deep_dive": (
            "1. Never store provisioning credentials in GATT characteristics\n"
            "2. Use per-device unique tokens generated at manufacture (not hardcoded)\n"
            "3. Require bonding with ENCRYPTED_READ for any credential-adjacent characteristic\n"
            "4. Implement token rotation — expire and reissue tokens on each provisioning\n"
            "5. Use Matter's PASE/CASE commissioning — designed to be secure by default"
        ),
    },

    "ble-04": {
        "scenario_id": "ble-04",
        "title": "Medical Devices — When Convenience Beats Security",
        "difficulty": "medium",
        "reading_time_min": 5,
        "concept": (
            "Medical IoT devices (continuous glucose monitors, insulin pumps, "
            "cardiac monitors) transmit health data via BLE for smartphone display. "
            "The Bluetooth SIG Glucose Profile specification requires ENCRYPTED_READ "
            "and bonding — but many manufacturers omit these to simplify setup for "
            "elderly patients. This exposes life-critical health data to passive eavesdropping."
        ),
        "real_world": (
            "In 2019, FDA issued cybersecurity guidance after researchers found that "
            "Medtronic insulin pumps could receive unauthenticated BLE commands — "
            "allowing remote control of insulin dosing (CVE-2019-13224). "
            "Glucose meters from multiple brands were found to broadcast readings "
            "in plaintext, enabling stalking and insurance fraud."
        ),
        "vulnerability_details": {
            "type": "UNENCRYPTED_PROTOCOL",
            "cvss_score": 8.6,
            "cvss_vector": "CVSS:3.1/AV:A/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:H",
            "cwe": "CWE-311: Missing Encryption of Sensitive Data",
        },
        "what_to_look_for": [
            "GATT service 0x1808 (Glucose Service) — standard medical profile",
            "GATT service 0x1809 (Health Thermometer Service)",
            "Custom service with 'patient', 'history', 'log' in characteristic name",
            "RACP characteristic (0x2A52) — controls glucose record retrieval",
        ],
        "learning_objectives": [
            "Understand the Bluetooth SIG Glucose Profile specification",
            "Read and parse IEEE 11073 FLOAT format used in medical measurements",
            "Recognize the regulatory environment (FDA, CE marking) for medical BLE",
            "Understand HIPAA/GDPR implications of patient data in BLE characteristics",
        ],
        "remediation_deep_dive": (
            "1. Follow Bluetooth SIG profile specifications — they mandate encryption\n"
            "2. Implement Secure Connections with MITM protection for all medical data\n"
            "3. Apply FDA pre-market cybersecurity guidance for medical devices\n"
            "4. Conduct threat modeling per IEC 62443 for medical IoT\n"
            "5. Implement remote device management for security patching without recall"
        ),
    },

    "ble-05": {
        "scenario_id": "ble-05",
        "title": "Bluetooth Headphones — Tracking and Impersonation",
        "difficulty": "easy",
        "reading_time_min": 3,
        "concept": (
            "Consumer BLE devices (headphones, earbuds, speakers) typically use "
            "'Just Works' pairing for convenience — no PIN, no confirmation. "
            "This enables silent pairing and MITM attacks. When manufacturers also "
            "store paired device MACs and pairing keys in readable GATT characteristics, "
            "attackers can harvest the user's device inventory and impersonate the headphones."
        ),
        "real_world": (
            "A 2020 study found that AirPods, Galaxy Buds, and Sony WF-1000XM3 all "
            "broadcast unique identifiers enabling passive tracking across locations. "
            "Apple patched this in iOS 14 with MAC randomization for AirPods. "
            "Older Bluetooth headphones remain trackable today."
        ),
        "vulnerability_details": {
            "type": "NO_PAIRING_REQUIRED",
            "cvss_score": 6.5,
            "cvss_vector": "CVSS:3.1/AV:A/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N",
            "cwe": "CWE-287: Improper Authentication",
        },
        "what_to_look_for": [
            "Device advertises with stable, non-randomized MAC address",
            "GATT service with 'pair' or 'config' in custom UUID",
            "Readable characteristic containing pairing key or paired device list",
            "Accept connection without confirmation prompt — Just Works confirmed",
        ],
        "learning_objectives": [
            "Use BLE passive scanning to collect device advertisements over time",
            "Understand Bluetooth MAC randomization and when it is/isn't applied",
            "Enumerate custom manufacturer GATT services on consumer audio devices",
            "Understand how a leaked pairing key enables device impersonation",
        ],
        "remediation_deep_dive": (
            "1. Implement BLE MAC address randomization (resolvable private addresses)\n"
            "2. Use Numeric Comparison pairing — display a 6-digit code on both devices\n"
            "3. Never store pairing keys or device history in readable characteristics\n"
            "4. Rotate pairing credentials after each factory reset\n"
            "5. Follow Bluetooth Core 5.4 privacy features"
        ),
    },
}


# ──────────────────────────────────────────────────────────────────────────────
# Progressive hints — 3 per scenario, increasing specificity
# ──────────────────────────────────────────────────────────────────────────────

HINTS: Dict[str, List[Dict]] = {

    "wifi-01": [
        {"level": 1, "cost_pts": 10, "text": "The camera uses HTTP Basic Authentication. Try connecting to port 80 and observe the 401 response — it tells you the realm and auth type."},
        {"level": 2, "cost_pts": 10, "text": "The vendor is Hikvision. Their factory credentials are admin/admin. The protected path is /admin/ — try it with curl: curl -u admin:admin http://HOST:8050/admin/"},
        {"level": 3, "cost_pts": 10, "text": "After authenticating with admin/admin, access the ISAPI endpoint: GET /ISAPI/System/deviceInfo with the same credentials to extract model and firmware version."},
    ],
    "wifi-02": [
        {"level": 1, "cost_pts": 10, "text": "MQTT runs on TCP port 1883. You can probe it with netcat (nc -v HOST 8051) to confirm it's listening. A real MQTT connection uses a CONNECT packet."},
        {"level": 2, "cost_pts": 10, "text": "Install mosquitto-clients and run: mosquitto_sub -h HOST -p 8051 -t '#' -v. The '#' wildcard subscribes to ALL topics. No password flags needed — that's the vulnerability."},
        {"level": 3, "cost_pts": 10, "text": "Inject a message: mosquitto_pub -h HOST -p 8051 -t sensor/temperature -m '999.9'. Any downstream system reading this topic will receive your spoofed value."},
    ],
    "wifi-03": [
        {"level": 1, "cost_pts": 10, "text": "Port 23 is Telnet. Connect with: telnet HOST 8052 (or: nc HOST 8052). The device will show a login prompt. Look at the banner for clues about the OS."},
        {"level": 2, "cost_pts": 10, "text": "TP-Link routers commonly use root as the username. The password is also root — a factory default. Try it at the login prompt."},
        {"level": 3, "cost_pts": 10, "text": "After getting a shell, run: nvram show | grep -i pass to see all stored passwords. This often reveals the Wi-Fi password and web admin password."},
    ],
    "wifi-04": [
        {"level": 1, "cost_pts": 10, "text": "Start by probing the HTTP API: curl http://HOST:8053/info — look at the JSON response. Notice what sensitive fields are returned without any authentication."},
        {"level": 2, "cost_pts": 10, "text": "The /control endpoint accepts POST requests with JSON. Try: curl -X POST http://HOST:8053/control -H 'Content-Type: application/json' -d '{\"command\":\"toggle\"}'"},
        {"level": 3, "cost_pts": 10, "text": "The local_key from /info is the encryption key used for the raw TCP protocol on port 6668 (host: 8063). With it, you can fully impersonate this device to the Tuya cloud API."},
    ],
    "wifi-05": [
        {"level": 1, "cost_pts": 10, "text": "The thermostat runs on port 80 (host: 8054). But check for other open ports — it also has a secondary service. Try common debug ports: 8080, 8888, 9090. The host port is 8064."},
        {"level": 2, "cost_pts": 10, "text": "Connect to port 8064 and try paths: /debug, /diag, /test. You'll get a confirmation page. Then look for a /dump sub-path."},
        {"level": 3, "cost_pts": 10, "text": "GET http://HOST:8064/debug/dump — this returns a full JSON config. Look for fields: wifi_password, access_token, admin_pin. The Wi-Fi password can be used to join the home network."},
    ],
    "wifi-06": [
        {"level": 1, "cost_pts": 10, "text": "Samsung TVs expose the SmartThings API on port 9197 (host: 8072). Start with: curl http://HOST:8072/ to see the available API paths."},
        {"level": 2, "cost_pts": 10, "text": "The Voice API endpoint is at /api/v1/voice/enable. Try a POST with no body: curl -X POST http://HOST:8072/api/v1/voice/enable — no authentication required."},
        {"level": 3, "cost_pts": 10, "text": "Verify the microphone is enabled: GET /api/v1/voice/status should show mic_enabled: true. Also check /api/v1/voice/disable to confirm you can toggle it both ways."},
    ],
    "wifi-07": [
        {"level": 1, "cost_pts": 10, "text": "Start with the DSM API: curl http://HOST:8080/webapi/query.cgi — it returns firmware version, shares list, and SMB configuration without authentication."},
        {"level": 2, "cost_pts": 10, "text": "The DSM admin panel exposes shared folder paths. Try browsing: /shared/backup/ — look at the admin panel HTML source for hints about what files are available."},
        {"level": 3, "cost_pts": 10, "text": "Download the shadow file: curl http://HOST:8080/shared/backup/etc-shadow.bak. The $6$ prefix means SHA-512 crypt. Crack with: hashcat -m 1800 shadow.bak rockyou.txt"},
    ],
    "ble-01": [
        {"level": 1, "cost_pts": 10, "text": "Scan for the device: bluetoothctl scan on (or use nRF Connect app). Look for 'August-Lock-A4B2'. Note its MAC address for the next steps."},
        {"level": 2, "cost_pts": 10, "text": "Connect and enumerate: gatttool -b A4:B2:00:01:02:03 --interactive → connect → primary. Find the Lock service (UUID FE24). List its characteristics."},
        {"level": 3, "cost_pts": 10, "text": "Write 0x01 to the Lock Command characteristic (UUID 2A57) without pairing: gatttool -b A4:B2:00:01:02:03 --char-write-req -a 0x0015 -n 01. Then read 2A56 to confirm state changed to UNLOCKED."},
    ],
    "ble-02": [
        {"level": 1, "cost_pts": 10, "text": "Connect to Fitbit-Charge-5 (MAC: C5:FB:00:01:02:04). Use 'primary' in gatttool to list all GATT services. Look for standard UUIDs: 0x180D (Heart Rate), 0x1809 (Temperature)."},
        {"level": 2, "cost_pts": 10, "text": "Read the Heart Rate Measurement (0x2A37): char-read-uuid 0x2A37. The first byte is flags, second byte is the heart rate value in BPM. Note: no bonding was required."},
        {"level": 3, "cost_pts": 10, "text": "Find the custom Fitbit service (UUID ADABFB00-...). Characteristics 01-04 hold: steps, sleep data, user profile (with email and name), and GPS history. All readable without bonding."},
    ],
    "ble-03": [
        {"level": 1, "cost_pts": 10, "text": "Connect to LIFX-A19-3F88 (MAC: 3F:88:00:01:02:05). List services with 'primary'. Look for a custom service UUID starting with 0001AAAA — this is the LIFX control service."},
        {"level": 2, "cost_pts": 10, "text": "Read characteristic 0001AAAA-...-0004 (Auth Token). The value is a plaintext string — this static token can be replayed to the LIFX cloud API to control all bulbs in the account."},
        {"level": 3, "cost_pts": 10, "text": "Read characteristic 0001AAAA-...-0005 (Wi-Fi Credentials). It returns ssid= and password= in plaintext. Use these to connect to the home Wi-Fi and pivot to the internal network."},
    ],
    "ble-04": [
        {"level": 1, "cost_pts": 10, "text": "Connect to Accu-Chek-Guide (MAC: AC:CE:00:01:02:06). The standard Glucose Service is UUID 0x1808. Read the Glucose Measurement characteristic (0x2A18) — no pairing needed."},
        {"level": 2, "cost_pts": 10, "text": "Find the custom Patient service (UUID 12345678-...). Characteristic 0001 holds patient PII: name, age, diagnosis, doctor, hospital, and insurance ID — all in readable plaintext."},
        {"level": 3, "cost_pts": 10, "text": "Characteristic 0002 is the glucose history log (7 readings with meal context). Characteristic 0003 is the insulin administration log. Combine all three to build a complete medical profile."},
    ],
    "ble-05": [
        {"level": 1, "cost_pts": 10, "text": "Scan for JBL-Tune-510BT (MAC: 5B:10:00:01:02:07). Connect without pairing — you'll notice no confirmation is shown. That's 'Just Works' mode — the first vulnerability."},
        {"level": 2, "cost_pts": 10, "text": "Find the pairing service (UUID 0000FFFE-...). Read characteristic FFFD — it returns the static pairing key 'JBL-PAIR-1234'. This key is hardcoded in firmware."},
        {"level": 3, "cost_pts": 10, "text": "Read characteristic FFFC (Device History). It returns the MAC addresses and names of all previously paired devices. These can be used to identify and target the owner's other devices."},
    ],
}


# ──────────────────────────────────────────────────────────────────────────────
# Scoring configuration
# ──────────────────────────────────────────────────────────────────────────────

SCORE_CONFIG: Dict[str, Dict] = {
    # base_score: max points for completing with no hints, within time_limit
    # time_limit: seconds — after this, -1 point per 10 seconds
    # difficulty_multiplier: applied to final score
    "wifi-01": {"base_score": 100, "time_limit": 120, "difficulty_multiplier": 1.0},
    "wifi-02": {"base_score": 100, "time_limit": 180, "difficulty_multiplier": 1.0},
    "wifi-03": {"base_score": 150, "time_limit": 180, "difficulty_multiplier": 1.5},
    "wifi-04": {"base_score": 150, "time_limit": 240, "difficulty_multiplier": 1.5},
    "wifi-05": {"base_score": 200, "time_limit": 300, "difficulty_multiplier": 2.0},
    "wifi-06": {"base_score": 100, "time_limit": 120, "difficulty_multiplier": 1.0},
    "wifi-07": {"base_score": 200, "time_limit": 360, "difficulty_multiplier": 2.0},
    "ble-01":  {"base_score": 100, "time_limit": 180, "difficulty_multiplier": 1.0},
    "ble-02":  {"base_score": 100, "time_limit": 180, "difficulty_multiplier": 1.0},
    "ble-03":  {"base_score": 150, "time_limit": 240, "difficulty_multiplier": 1.5},
    "ble-04":  {"base_score": 150, "time_limit": 240, "difficulty_multiplier": 1.5},
    "ble-05":  {"base_score": 100, "time_limit": 180, "difficulty_multiplier": 1.0},
}

HINT_COST = 10   # points deducted per hint used
TIME_PENALTY = 1  # points deducted per 10 seconds over time_limit


def calculate_score(
    scenario_id: str,
    elapsed_seconds: float,
    hints_used: int,
    success: bool,
) -> Dict:
    """Calculate the final score for a completed scenario."""
    if not success:
        return {
            "score": 0,
            "base_score": 0,
            "hint_penalty": 0,
            "time_penalty": 0,
            "grade": "F",
            "message": "Scenario not completed — score is 0",
        }

    cfg = SCORE_CONFIG.get(scenario_id, {"base_score": 100, "time_limit": 180, "difficulty_multiplier": 1.0})
    base = cfg["base_score"]
    multiplier = cfg["difficulty_multiplier"]
    time_limit = cfg["time_limit"]

    hint_penalty = hints_used * HINT_COST
    time_over = max(0, elapsed_seconds - time_limit)
    time_penalty = int(time_over / 10) * TIME_PENALTY

    raw = base - hint_penalty - time_penalty
    final = max(0, int(raw * multiplier))

    if final >= int(base * multiplier * 0.9):
        grade = "A"
    elif final >= int(base * multiplier * 0.75):
        grade = "B"
    elif final >= int(base * multiplier * 0.5):
        grade = "C"
    elif final > 0:
        grade = "D"
    else:
        grade = "F"

    messages = {
        "A": "Excellent! You completed it perfectly with minimal assistance.",
        "B": "Good work! A few tweaks and you'd be flawless.",
        "C": "Completed, but relied on hints or took extra time.",
        "D": "Completed with significant help — review the tutorial and try again.",
        "F": "Score too low — review the tutorial and hints before retrying.",
    }

    return {
        "score": final,
        "base_score": base,
        "difficulty_multiplier": multiplier,
        "hint_penalty": hint_penalty,
        "time_penalty": time_penalty,
        "hints_used": hints_used,
        "elapsed_seconds": round(elapsed_seconds),
        "time_limit_seconds": time_limit,
        "grade": grade,
        "message": messages[grade],
    }


def get_difficulty_path() -> Dict:
    """Returns the recommended learning path ordered by difficulty."""
    easy   = [sid for sid, t in TUTORIALS.items() if t["difficulty"] == "easy"]
    medium = [sid for sid, t in TUTORIALS.items() if t["difficulty"] == "medium"]
    hard   = [sid for sid, t in TUTORIALS.items() if t["difficulty"] == "hard"]
    return {
        "easy":   easy,
        "medium": medium,
        "hard":   hard,
        "recommended_order": easy + medium + hard,
        "total_max_score": sum(
            int(v["base_score"] * v["difficulty_multiplier"])
            for v in SCORE_CONFIG.values()
        ),
    }
