const API_BASE = window.location.origin;

// Auth removed
function authHeaders(extra = {}) {
    return {'Content-Type': 'application/json', ...extra};
}

function authFetch(url, options = {}) {
    options.headers = options.headers || {};
    // Don't set Content-Type for FormData
    if (options.body && !(options.body instanceof FormData)) {
        options.headers['Content-Type'] = options.headers['Content-Type'] || 'application/json';
    }
    return fetch(url, options);
}

const app = {
    devices: [],
    selectedDevice: null,
    scanInterval: null,
    rfidCards: [],
    ws: null,

    riskChart: null,
    protocolChart: null,
    timelineData: [],

    init() {
        this.fetchSummary();
        this.fetchDevices();
        this.fetchCards();
        this.initNetworkSelect();
        this.initCharts();
        this.initWebSocket();
        this.discoverNetworks(); // لقط الشبكات تلقائي عند البداية
        this.fetchHardwareStatus();
        this.fetchAISuggestions(); // AI suggestions on load
        this.fetchAISecurityScore(); // AI security score
        
        // Add auto-refresh every 5 seconds as backup
        this.startAutoRefresh();
        this.loadAdvancedWifiInterfaces();
        console.log('[Init] App initialized with auto-refresh enabled');
    },
    
    startAutoRefresh() {
        // Refresh devices and summary every 5 seconds (10s if lightweight)
        const isLightweight = document.body.classList.contains('lightweight-mode');
        const interval = isLightweight ? 10000 : 5000;
        
        this.refreshInterval = setInterval(() => {
            // Only refresh if no scan is currently running
            this.fetchDevices();
            this.fetchSummary();
        }, interval);
        
        // Refresh hardware status every 0.1 seconds
        this.hwRefreshInterval = setInterval(() => {
            this.fetchHardwareStatus();
        }, 100);
        
        console.log(`[AutoRefresh] Started - will refresh every ${interval/1000} seconds`);
    },
    
    toggleAdvanced() {
        const advancedOptions = document.getElementById('advancedOptions');
        const advancedIcon = document.getElementById('advancedIcon');
        
        if (advancedOptions.classList.contains('hidden')) {
            advancedOptions.classList.remove('hidden');
            advancedIcon.style.transform = 'rotate(180deg)';
        } else {
            advancedOptions.classList.add('hidden');
            advancedIcon.style.transform = 'rotate(0deg)';
        }
    },

    toggleProtocols() {
        const protocolButtons = document.getElementById('protocolButtons');
        const protocolIcon = document.getElementById('protocolIcon');
        
        if (protocolButtons.classList.contains('hidden')) {
            protocolButtons.classList.remove('hidden');
            protocolIcon.style.transform = 'rotate(180deg)';
        } else {
            protocolButtons.classList.add('hidden');
            protocolIcon.style.transform = 'rotate(0deg)';
        }
    },

    async discoverAndScan() {
        // Quick auto-scan: discover network then scan
        try {
            this.showToast('Discovering network...', 'info');
            
            const response = await authFetch(`${API_BASE}/wireless/discover/devices`, {
                method: 'POST'
            });
            
            const data = await response.json();
            
            if (data.status === 'started') {
                this.showToast(`Scanning ${data.network}...`, 'success');
                document.getElementById('networkInput').value = data.network;
            } else {
                this.showToast(data.message || 'Failed to detect network', 'risk');
            }
        } catch (e) {
            console.error('Auto-scan error:', e);
            this.showToast('Auto-scan failed. Try manual scan.', 'risk');
        }
    },

    initCharts() {
        const isLightweight = document.body.classList.contains('lightweight-mode');
        this.initRiskChart(isLightweight);
        this.initProtocolChart(isLightweight);
    },

    initRiskChart(isLightweight) {
        const ctx = document.getElementById('riskPieChart');
        if (!ctx) return;
        this.riskChart = new Chart(ctx.getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: ['Safe', 'Medium', 'Risk'],
                datasets: [{
                    data: [0, 0, 0],
                    backgroundColor: ['#22c55e', '#f59e0b', '#ef4444'],
                    borderWidth: 0,
                    hoverOffset: isLightweight ? 0 : 4
                }]
            },
            options: {
                cutout: '70%',
                plugins: {
                    legend: { display: false }
                },
                responsive: true,
                maintainAspectRatio: false,
                animation: isLightweight ? false : { duration: 800 }
            }
        });
    },

    initProtocolChart(isLightweight) {
        const ctx = document.getElementById('protocolChart');
        if (!ctx) return;
        this.protocolChart = new Chart(ctx.getContext('2d'), {
            type: 'bar',
            data: {
                labels: ['Wi-Fi', 'Bluetooth', 'Zigbee', 'Thread', 'Z-Wave', 'LoRaWAN', 'RFID'],
                datasets: [{
                    label: 'Devices',
                    data: [0, 0, 0, 0, 0, 0, 0],
                    backgroundColor: [
                        'rgba(59, 130, 246, 0.8)',
                        'rgba(59, 130, 246, 0.8)',
                        'rgba(245, 158, 11, 0.8)',
                        'rgba(139, 92, 246, 0.8)',
                        'rgba(236, 72, 153, 0.8)',
                        'rgba(20, 184, 166, 0.8)',
                        'rgba(239, 68, 68, 0.8)'
                    ],
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: isLightweight ? false : { duration: 800 },
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: { color: '#94a3b8' },
                        grid: { color: 'rgba(148, 163, 184, 0.1)' }
                    },
                    x: {
                        ticks: { color: '#94a3b8' },
                        grid: { display: false }
                    }
                }
            }
        });
    },

    initWebSocket() {
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${wsProtocol}//${window.location.host}/ws`;
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleWebSocketMessage(data);
        };
        
        this.ws.onclose = () => {
            // Reconnect after 5 seconds
            setTimeout(() => this.initWebSocket(), 5000);
        };
    },

    handleWebSocketMessage(data) {
        console.log('[WebSocket] Received event:', data.event, data);
        
        if (data.event === 'heartbeat') return;
        
        if (data.event === 'device_found') {
            console.log('[Device Found] Updating UI with device:', data.device.ip);
            this.showToast(`New device discovered: ${data.device.hostname || data.device.ip}`, 'info');
            this.fetchDevices();
            this.fetchSummary();
            this.fetchAISecurityScore();
        } else if (data.event === 'vulnerability_found') {
            this.showToast(`Vulnerability detected: ${data.vulnerability.vuln_type}`, 'risk');
            this.fetchDevices();
        } else if (data.event === 'scan_progress') {
            console.log('[Scan Progress]', data.progress + '% -', data.message);
            this.updateScanProgress(data.progress, data.message);
        } else if (data.event === 'scan_finished') {
            console.log('[Scan Finished] Count:', data.count);
            this.showToast(`Scan complete: Found ${data.count} devices.`, 'success');
            this.updateScanProgress(100, `Scan finished.`);
            setTimeout(() => {
                document.getElementById("scanProgressContainer").classList.add("hidden");
                this.fetchDevices();
                this.fetchSummary();
                this.fetchAISuggestions();
                this.fetchAISecurityScore();
            }, 2000);
        } else if (data.event === 'scan_error') {
            this.showToast(`Scan Error: ${data.message}`, 'risk');
            this.updateScanProgress(0, `Error: ${data.message}`);
        } else if (data.event === 'wifi_client_found') {
            this.handleWifiClientFound(data);
        } else if (data.event === 'handshake_progress') {
            this.handleHandshakeProgress(data);
        } else if (data.event === 'handshake_captured') {
            this.handleHandshakeCaptured(data);
        } else if (data.event === 'rogue_ap_alert') {
            this.handleRogueApAlert(data);
        } else if (data.event === 'deauth_test_progress') {
            this.handleDeauthTestProgress(data);
        } else if (data.event === 'monitor_mode_changed') {
            this.handleMonitorModeChanged(data);
        } else if (data.event === 'signal_map_update') {
            this.handleSignalMapUpdate(data);
        }
    },

    updateScanProgress(progress, message) {
        const statusText = document.getElementById("scanStatusText");
        const progressBar = document.getElementById("scanProgressBar");
        if (statusText) statusText.textContent = message;
        if (progressBar) progressBar.style.width = `${progress}%`;
    },

    showToast(msg, type = 'info') {
        const container = document.getElementById('toastContainer');
        if (!container) return;
        const toast = document.createElement('div');
        toast.className = `toast-msg ${type}`;
        
        const icons = {
            'info': 'fa-circle-info',
            'success': 'fa-circle-check',
            'warning': 'fa-triangle-exclamation',
            'risk': 'fa-skull-crossbones'
        };

        toast.style.cssText = `
            background: rgba(15, 23, 42, 0.9);
            backdrop-filter: blur(10px);
            border-left: 4px solid ${type === 'risk' ? '#ef4444' : (type === 'success' ? '#22c55e' : '#3b82f6')};
            color: #fff;
            padding: 12px 20px;
            border-radius: 8px;
            box-shadow: 0 10px 15px -3px rgba(0,0,0,0.4);
            display: flex;
            align-items: center;
            gap: 12px;
            animation: slideIn 0.3s ease-out;
            max-width: 350px;
            margin-bottom: 10px;
        `;

        toast.innerHTML = `
            <i class="fa-solid ${icons[type] || icons.info}" style="color: ${type === 'risk' ? '#ef4444' : '#3b82f6'}"></i>
            <span style="font-size: 14px; font-family: 'Inter', sans-serif;">${msg}</span>
        `;

        container.appendChild(toast);
        
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(20px)';
            toast.style.transition = 'all 0.5s ease';
            setTimeout(() => toast.remove(), 500);
        }, 5000);
        
        if (type === 'risk') {
            try {
                const audio = new Audio('https://www.soundjay.com/buttons/beep-01a.mp3');
                audio.play();
            } catch(e){}
        }
    },

    switchView(viewId) {
        // Hide all views
        document.querySelectorAll('.view-section').forEach(el => el.classList.add('hidden'));
        // Show target view
        document.getElementById('view-' + viewId).classList.remove('hidden');
        
        // Update nav active state
        document.querySelectorAll('.nav-links li').forEach(el => el.classList.remove('active'));
        document.getElementById('nav-' + viewId).classList.add('active');

        // Set titles based on view
        const titles = {
            'dashboard': ['IoT Security Auditor', 'Monitor and secure your connected smart home environment'],
            'devices': ['Discovered Devices', 'Detailed list of all scanned networks and devices'],
            'rfid': ['Access Control', 'Scan and manage RFID/NFC cards and key fobs'],
            'reports': ['Security Reports', 'Generate and export security audit results'],
            'settings': ['System Settings', 'Configure scanner behaviors and options'],
            'advanced-wifi': ['Advanced WiFi', 'Monitor Mode, Client Sniffing, Handshake Capture & Security Testing']
        };
        
        if (titles[viewId]) {
            document.getElementById('pageTitle').textContent = titles[viewId][0];
            document.getElementById('pageSubtitle').textContent = titles[viewId][1];
        }
    },

    async fetchSettings() {
        try {
            const res = await authFetch(`${API_BASE}/settings`);
            if (res.ok) {
                const data = await res.json();
                document.getElementById('settingSimMode').checked = data.simulation_mode === 'true';
                document.getElementById('settingTimeout').value = data.nmap_timeout || '60';
            }
        } catch (e) {
            console.error("Failed to fetch settings", e);
        }
    },

    async saveSettings() {
        const simMode = document.getElementById('settingSimMode').checked ? 'true' : 'false';
        const timeout = document.getElementById('settingTimeout').value;
        try {
            await authFetch(`${API_BASE}/settings`, {
                method: 'PUT',
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({simulation_mode: simMode, nmap_timeout: timeout})
            });
        } catch (e) {
            console.error("Failed to save settings", e);
        }
    },

    async fetchSummary() {
        try {
            const res = await authFetch(`${API_BASE}/reports/summary`);
            if (res.ok) {
                const data = await res.json();
                const oldRiskEl = document.getElementById("sRisk");
                const oldRisk = oldRiskEl ? parseInt(oldRiskEl.textContent) || 0 : 0;
                
                if (document.getElementById("sTotal")) document.getElementById("sTotal").textContent = data.total_devices;
                if (document.getElementById("sSafe")) document.getElementById("sSafe").textContent = data.safe_count;
                if (document.getElementById("sMedium")) document.getElementById("sMedium").textContent = data.medium_count;
                if (document.getElementById("sRisk")) document.getElementById("sRisk").textContent = data.risk_count;

                // Update Risk Chart
                if (this.riskChart) {
                    this.riskChart.data.datasets[0].data = [data.safe_count, data.medium_count, data.risk_count];
                    this.riskChart.update();
                }

                // Show alert if new risk found
                if (data.risk_count > oldRisk) {
                    this.showToast(`Critical Risk Detected! Vulnerable device discovered.`, 'risk');
                }
            }
        } catch (e) {
            console.error("Failed to fetch summary", e);
        }
    },

    updateProtocolChart() {
        if (!this.protocolChart) return;
        
        const protocolCounts = {
            'Wi-Fi': 0,
            'Bluetooth': 0,
            'Zigbee': 0,
            'Thread': 0,
            'Matter': 0,
            'Z-Wave': 0,
            'LoRaWAN': 0,
            'RFID': 0
        };
        
        this.devices.forEach(device => {
            if (protocolCounts.hasOwnProperty(device.protocol)) {
                protocolCounts[device.protocol]++;
            }
        });
        
        // Merge Matter into Thread for display
        const displayData = [
            protocolCounts['Wi-Fi'],
            protocolCounts['Bluetooth'],
            protocolCounts['Zigbee'],
            protocolCounts['Thread'] + protocolCounts['Matter'],
            protocolCounts['Z-Wave'],
            protocolCounts['LoRaWAN'],
            protocolCounts['RFID']
        ];
        
        this.protocolChart.data.datasets[0].data = displayData;
        this.protocolChart.update();
    },

    async fetchDevices() {
        try {
            const res = await authFetch(`${API_BASE}/iot/devices`);
            if (res.ok) {
                const newDevices = await res.json();
                const deviceCount = newDevices.length;
                const oldCount = this.devices.length;
                
                // Only update if device count changed or first load
                if (deviceCount !== oldCount || oldCount === 0) {
                    console.log(`[Fetch] Devices changed: ${oldCount} → ${deviceCount}, updating UI`);
                    this.devices = newDevices;
                    this.renderDevicesTable();
                    this.updateProtocolChart();
                    
                    // Show toast if new devices found
                    if (deviceCount > oldCount) {
                        this.showToast(`Found ${deviceCount - oldCount} new device(s)!`, 'success');
                    }
                } else {
                    // Still update but less verbose
                    if (this.devices.length === 0) {
                        console.log('[Fetch] No devices found');
                    }
                }
            } else {
                console.error('[Fetch] Server returned error:', res.status);
            }
        } catch (e) {
            console.error("[Fetch] Failed to fetch devices:", e);
        }
    },

    renderDevicesTable() {
        const tbody = document.getElementById("devicesTableBody");
        if(!tbody) {
            console.error('[Render] devicesTableBody not found in HTML!');
            return;
        }
        
        console.log(`[Render] Rendering ${this.devices.length} devices to table`);
        tbody.innerHTML = "";

        if (this.devices.length === 0) {
            console.log('[Render] No devices to show, showing empty state');
            const tr = document.createElement("tr");
            tr.innerHTML = `<td colspan="4" style="text-align:center; color:var(--text-muted)">No devices discovered yet.</td>`;
            tbody.appendChild(tr);
            return;
        }

        this.devices.forEach((device, index) => {
            const tr = document.createElement("tr");
            tr.className = "device-row";
            if (this.selectedDevice && this.selectedDevice.id === device.id) {
                tr.classList.add("active");
            }
            
            tr.onclick = () => this.selectDevice(device.id);

            let icon = 'fa-laptop';
            if (device.protocol === 'Zigbee') icon = 'fa-brands fa-zigbee';
            else if (device.protocol === 'Matter') icon = 'fa-hubspot';
            else if (device.protocol === 'Bluetooth') icon = 'fa-brands fa-bluetooth';

            tr.innerHTML = `
                <td><i class="fa-solid ${icon}"></i> ${device.protocol}</td>
                <td><div style="font-family:monospace">${device.ip}</div><div style="font-size:11px; color:var(--text-muted)">${device.mac || 'N/A'}</div></td>
                <td><div>${device.hostname || 'Unknown'}</div><div style="font-size:11px; color:var(--text-muted)">${device.vendor || 'Unknown'}</div></td>
                <td><span class="badge ${device.risk_level.toLowerCase()}">${device.risk_level}</span></td>
            `;
            tbody.appendChild(tr);
            
            if (index === 0) {
                console.log('[Render] First device:', device.ip, device.mac, device.hostname);
            }
        });
        
        console.log(`[Render] Successfully rendered ${this.devices.length} devices`);
    },

    selectDevice(id) {
        this.selectedDevice = this.devices.find(d => d.id === id);
        this.renderDevicesTable(); // update active row
        this.renderDeviceDetails();
    },

    renderDeviceDetails() {
        const emptyState = document.getElementById("detailsEmptyState");
        const content = document.getElementById("detailsContent");

        if (!emptyState) return;

        if (!this.selectedDevice) {
            emptyState.classList.remove("hidden");
            content.classList.add("hidden");
            return;
        }

        emptyState.classList.add("hidden");
        content.classList.remove("hidden");

        const dev = this.selectedDevice;

        let icon = 'fa-laptop';
        if (dev.protocol === 'Zigbee') icon = 'fa-brands fa-zigbee';
        else if (dev.protocol === 'Matter') icon = 'fa-hubspot';
        else if (dev.protocol === 'Bluetooth') icon = 'fa-brands fa-bluetooth';

        document.getElementById("detailIcon").innerHTML = `<i class="fa-solid ${icon}"></i>`;
        document.getElementById("detailHostname").textContent = dev.hostname;
        document.getElementById("detailIp").textContent = dev.ip;
        
        const badge = document.getElementById("detailRiskBadge");
        badge.textContent = dev.risk_level;
        badge.className = `risk-badge ${dev.risk_level.toLowerCase()}`;
        
        if (dev.risk_level === 'SAFE') { badge.style.backgroundColor = 'var(--status-safe)'; badge.style.color = '#fff'; }
        else if (dev.risk_level === 'MEDIUM') { badge.style.backgroundColor = 'var(--status-medium)'; badge.style.color = '#fff'; }
        else if (dev.risk_level === 'RISK') { badge.style.backgroundColor = 'var(--status-risk)'; badge.style.color = '#fff'; }

        document.getElementById("detailVendor").textContent = dev.vendor;
        document.getElementById("detailOs").textContent = dev.os_guess;
        document.getElementById("detailPorts").textContent = dev.open_ports || "None";

        const vulnList = document.getElementById("vulnList");
        vulnList.innerHTML = "";

        if (dev.vulnerabilities.length === 0) {
            vulnList.innerHTML = `<div style="text-align:center; color:var(--text-muted); padding: 20px;">No vulnerabilities found. Secure!</div>`;
        } else {
            dev.vulnerabilities.forEach(v => {
                vulnList.innerHTML += `
                    <div class="vuln-item ${v.severity}">
                        <div class="vuln-header">
                            <span class="vuln-type">${v.vuln_type}</span>
                            <span class="vuln-port">${v.protocol} ${v.port ? ':'+v.port : ''}</span>
                        </div>
                        <div class="vuln-desc">${v.description}</div>
                    </div>
                `;
            });
        }
    },

    // Update input field when selection changes
    initNetworkSelect() {
        // Network select dropdown was removed in UI update
        // Network input is now the primary input
    },

    async discoverNetworks() {
        const discoverBtn = document.querySelector('[onclick="app.discoverNetworks()"]');
        
        // Show loading state
        if (discoverBtn) {
            discoverBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Discovering...';
            discoverBtn.disabled = true;
        }
        
        try {
            const res = await authFetch(`${API_BASE}/iot/networks/discover`);
            const data = await res.json();
            
            // Auto-fill the network input with the first discovered network
            if (data.networks && data.networks.length > 0) {
                const networkInput = document.getElementById("networkInput");
                if (networkInput) {
                    networkInput.value = data.networks[0].network;
                }
            }
            
        } catch (e) {
            console.error('Network discovery failed:', e);
        } finally {
            // Reset button
            if (discoverBtn) {
                discoverBtn.innerHTML = '<i class="fa-solid fa-search"></i> Discover';
                discoverBtn.disabled = false;
            }
        }
    },

    async scanSsids() {
        const ssidsList = document.getElementById("ssidsList");
        const container = document.getElementById("nearbySsidsContainer");
        
        container.classList.remove("hidden");
        ssidsList.innerHTML = '<div style="font-size: 11px; color: var(--text-muted);"><i class="fa-solid fa-satellite-dish fa-fade"></i> Scanning airwaves...</div>';
        
        try {
            const res = await authFetch(`${API_BASE}/wireless/scan/ssids`);
            const data = await res.json();
            
            if (data.status === "success" && data.ssids.length > 0) {
                this.renderSsids(data.ssids);
            } else {
                ssidsList.innerHTML = '<div style="font-size: 11px; color: var(--text-muted);">No other SSIDs detected or radio busy.</div>';
            }
        } catch (e) {
            ssidsList.innerHTML = '<div style="font-size: 11px; color: var(--text-muted);">Failed to scan SSIDs.</div>';
        }
    },

    renderSsids(ssids) {
        const ssidsList = document.getElementById("ssidsList");
        ssidsList.innerHTML = "";
        
        ssids.forEach(net => {
            const div = document.createElement("div");
            div.className = "ssid-item";
            div.style.cssText = "display: flex; justify-content: space-between; align-items: center; padding: 4px 8px; background: rgba(255,255,255,0.05); border-radius: 4px; font-size: 11px;";
            
            const signalColor = this.getSignalColor(net.rssi);
            const signalIcon = this.getSignalIcon(net.rssi);
            
            div.innerHTML = `
                <div style="display: flex; align-items: center; gap: 8px;">
                    <i class="fa-solid ${signalIcon}" style="color: ${signalColor}"></i>
                    <span style="font-weight: 500;">${net.ssid}</span>
                </div>
                <div style="color: var(--text-muted); font-size: 10px;">
                    <i class="fa-solid fa-lock" style="font-size: 9px;"></i> ${net.security.split(' ')[0]}
                </div>
            `;
            
            // Clicking SSID copies it to input for advanced scanning if user wants
            div.style.cursor = "pointer";
            div.onclick = () => {
                this.showToast(`Selected SSID: ${net.ssid}`, 'info');
            };
            
            ssidsList.appendChild(div);
        });
    },

    getSignalColor(rssi) {
        if (rssi === "N/A") return "var(--text-muted)";
        const r = parseInt(rssi);
        if (r > -60) return "#22c55e"; // Excellent
        if (r > -75) return "#f59e0b"; // Good
        return "#ef4444"; // Poor
    },

    getSignalIcon(rssi) {
        if (rssi === "N/A") return "fa-wifi";
        const r = parseInt(rssi);
        if (r > -60) return "fa-wifi";
        if (r > -80) return "fa-wifi";
        return "fa-wifi"; // Should find a weak wifi icon if possible, or just use colors
    },

    async startScan(type) {
        const progressContainer = document.getElementById("scanProgressContainer");
        const statusText = document.getElementById("scanStatusText");
        const progressBar = document.getElementById("scanProgressBar");
        
        progressContainer.classList.remove("hidden");
        progressBar.style.width = "0%";
        
        let url = "";
        let body = null;

        if (type === 'wifi') {
            const networkInput = document.getElementById("networkInput");
            const network = networkInput?.value;
            if (!network) {
                statusText.textContent = "Please enter a network range";
                setTimeout(()=> progressContainer.classList.add("hidden"), 3000);
                return;
            }
            
            url = `${API_BASE}/iot/scan/wifi`;
            body = JSON.stringify({ network: network, timeout: 60 });
        } else if (type === 'matter') {
            url = `${API_BASE}/iot/scan/matter`;
        } else if (type === 'zigbee') {
            url = `${API_BASE}/iot/scan/zigbee`;
        } else if (type === 'bluetooth') {
            url = `${API_BASE}/wireless/scan/bluetooth`;
        } else if (type === 'thread') {
            url = `${API_BASE}/iot/scan/thread`;
        } else if (type === 'zwave') {
            url = `${API_BASE}/iot/scan/zwave`;
        } else if (type === 'lora') {
            url = `${API_BASE}/iot/scan/lora`;
        }

        try {
            const reqData = { method: "POST", headers: {"Content-Type": "application/json"} };
            if (body) reqData.body = body;
            
            const res = await authFetch(url, reqData);
            const data = await res.json();
            statusText.textContent = data.message;
            if (data.status === 'error') {
                setTimeout(()=> progressContainer.classList.add("hidden"), 3000);
                return;
            }

            // Start polling status
            if (this.scanInterval) clearInterval(this.scanInterval);
            this.scanInterval = setInterval(() => this.pollScanStatus(), 2000);

            // Simulating progress bar for UI feel
            let p = 0;
            const simInt = setInterval(() => {
                p += Math.random() * 10;
                if (p > 90) clearInterval(simInt);
                else progressBar.style.width = `${p}%`;
            }, 1000);

        } catch (e) {
            console.error(e);
            statusText.textContent = "Error starting scan.";
        }
    },

    async pollScanStatus() {
        try {
            const res = await authFetch(`${API_BASE}/iot/scan/status`);
            const data = await res.json();
            
            console.log('[Polling] Status:', data);
            document.getElementById("scanStatusText").textContent = data.message;
            if (data.progress > 0) {
                document.getElementById("scanProgressBar").style.width = `${data.progress}%`;
            }

            if (!data.running) {
                console.log('[Polling] Scan complete, refreshing in 3 seconds...');
                clearInterval(this.scanInterval);
                document.getElementById("scanProgressBar").style.width = `100%`;
                // Don't refresh here - WebSocket scan_finished will handle it
                // This prevents double-refresh
                setTimeout(() => {
                    document.getElementById("scanProgressContainer").classList.add("hidden");
                    // Only refresh if WebSocket didn't already do it
                    console.log('[Polling] Manual refresh triggered');
                    this.fetchDevices();
                    this.fetchSummary();
                }, 3000);
            }
        } catch (e) {
            console.error("[Polling] Error:", e);
        }
    },

    async testPorts() {
        if (!this.selectedDevice) return;
        
        // Check if device has a valid IP (not Z-Wave, BLE, etc.)
        const ip = this.selectedDevice.ip;
        if (ip.startsWith('ZW:') || ip.startsWith('BLE_') || ip.startsWith('ZB:')) {
            alert(`Port scanning is not available for ${this.selectedDevice.protocol} devices.\nThis feature requires an IP-based device (Wi-Fi/Ethernet).`);
            return;
        }
        
        try {
            await authFetch(`${API_BASE}/wireless/test/ports/${ip}`, { method: "POST" });
            alert(`Started Deep Port Scan on ${ip}`);
            setTimeout(() => this.fetchDevices(), 5000); // Check results after a bit
        } catch (e) {
            alert("Error starting port scan");
        }
    },

    async testCreds() {
        if (!this.selectedDevice) return;
        
        // Check if device has a valid IP (not Z-Wave, BLE, etc.)
        const ip = this.selectedDevice.ip;
        if (ip.startsWith('ZW:') || ip.startsWith('BLE_') || ip.startsWith('ZB:')) {
            alert(`Credential testing is not available for ${this.selectedDevice.protocol} devices.\nThis feature requires an IP-based device (Wi-Fi/Ethernet).`);
            return;
        }
        
        try {
            await authFetch(`${API_BASE}/wireless/test/credentials/${ip}`, { method: "POST" });
            alert(`Started Default Credentials Test on ${ip}`);
            setTimeout(() => this.fetchDevices(), 5000);
        } catch (e) {
            alert("Error starting credentials test");
        }
    },

    // ======== RFID LOGIC ========
    async fetchCards() {
        try {
            const res = await authFetch(`${API_BASE}/rfid/cards`);
            if (res.ok) {
                this.rfidCards = await res.json();
                this.renderCardsTable();
            }
        } catch(e) {
            console.error("Failed to load cards");
        }
    },

    renderCardsTable() {
        const tbody = document.getElementById("cardsTableBody");
        if (!tbody) return;
        tbody.innerHTML = "";
        
        if (this.rfidCards.length === 0) {
            tbody.innerHTML = `<tr><td colspan="3" style="text-align:center; color:var(--text-muted)">No cards scanned yet.</td></tr>`;
            return;
        }

        this.rfidCards.forEach(c => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td style="font-family:monospace; font-weight:bold">${c.uid}</td>
                <td>${c.card_type}</td>
                <td><span class="badge ${c.risk_level.toLowerCase()}">${c.risk_level}</span></td>
            `;
            tbody.appendChild(tr);
        });
    },

    async scanRfid() {
        const status = document.getElementById("rfidStatus");
        status.textContent = "Scanning for card... Please wait.";
        try {
            const res = await authFetch(`${API_BASE}/rfid/scan`, { method: "POST" });
            const data = await res.json();
            status.textContent = data.message;
            if(data.status === 'error') {
                status.style.color = "var(--status-risk)";
            } else {
                status.style.color = "var(--status-safe)";
            }
            this.fetchCards();
        } catch(e) {
            status.textContent = "Error scanning card.";
        }
    },

    async clearCards() {
        try {
            await authFetch(`${API_BASE}/rfid/cards`, { method: "DELETE" });
            this.fetchCards();
        } catch(e) { }
    },
    // ============================

    async downloadReport() {
        window.open(`${API_BASE}/reports/generate/pdf`, "_blank");
    },

    // ======== EXPORT FEATURES ========
    exportJSON() {
        const data = {
            exported_at: new Date().toISOString(),
            devices: this.devices,
            rfid_cards: this.rfidCards,
            summary: {
                total: this.devices.length,
                safe: this.devices.filter(d => d.risk_level === 'SAFE').length,
                medium: this.devices.filter(d => d.risk_level === 'MEDIUM').length,
                risk: this.devices.filter(d => d.risk_level === 'RISK').length
            }
        };
        
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `pentexone_scan_${new Date().toISOString().slice(0,10)}.json`;
        a.click();
        URL.revokeObjectURL(url);
        this.showToast('JSON export downloaded', 'success');
    },

    exportCSV() {
        // Devices CSV
        let csv = 'IP,MAC,Hostname,Vendor,Protocol,OS Guess,Risk Level,Risk Score,Open Ports\n';
        this.devices.forEach(d => {
            csv += `"${d.ip}","${d.mac}","${d.hostname}","${d.vendor}","${d.protocol}","${d.os_guess}","${d.risk_level}",${d.risk_score},"${d.open_ports}"\n`;
        });
        
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `pentexone_devices_${new Date().toISOString().slice(0,10)}.csv`;
        a.click();
        URL.revokeObjectURL(url);
        this.showToast('CSV export downloaded', 'success');
    },

    // ======== HARDWARE STATUS ========
    async fetchHardwareStatus() {
        try {
            const res = await authFetch(`${API_BASE}/iot/hardware/status`);
            if (res.ok) {
                const data = await res.json();
                console.log('[HW Status] API response:', JSON.stringify(data.summary));
                this.updateHardwareStatus(data);
            } else {
                console.warn('[HW Status] API returned non-OK:', res.status);
            }
        } catch (e) {
            console.error("[HW Status] Failed to fetch hardware status", e);
        }
    },

    updateHardwareStatus(data) {
        const container = document.getElementById('hardwareStatus');
        if (!container) {
            console.warn('[HW Status] Container #hardwareStatus not found');
            return;
        }
        
        // Extract data from multiple possible paths
        const summary = data.summary || {};
        const dongles = data.dongles || {};
        
        // Zigbee: try summary first, then dongles
        const zigbeeConnected = summary.zigbee?.connected || (dongles.zigbee !== null && dongles.zigbee !== undefined);
        const zigbeePort = summary.zigbee?.port || dongles.zigbee?.port || '';
        const zigbeeChip = summary.zigbee?.chip || dongles.zigbee?.chip || '';
        const zigbeeReady = summary.zigbee?.ready || false;
        
        // Thread
        const threadConnected = summary.thread?.connected || (dongles.thread !== null && dongles.thread !== undefined);
        const threadPort = summary.thread?.port || dongles.thread?.port || '';
        
        // Z-Wave
        const zwaveConnected = summary.zwave?.connected || (dongles.zwave !== null && dongles.zwave !== undefined);
        const zwavePort = summary.zwave?.port || dongles.zwave?.port || '';
        
        // Bluetooth
        const btConnected = summary.bluetooth?.connected || (dongles.bluetooth !== null && dongles.bluetooth !== undefined);
        
        console.log(`[HW Status] Zigbee: connected=${zigbeeConnected}, port=${zigbeePort}, chip=${zigbeeChip}, ready=${zigbeeReady}`);
        
        let html = '<div style="display: flex; flex-wrap: wrap; gap: 10px;">';
        
        // Zigbee dongle
        html += `<div class="hw-status-item ${zigbeeConnected ? 'connected' : 'disconnected'}">
            <i class="fa-solid fa-usb"></i>
            <span>Zigbee: ${zigbeeConnected ? zigbeePort + ' (' + zigbeeChip + ')' : 'Not Connected'}</span>
        </div>`;
        
        // Thread dongle
        html += `<div class="hw-status-item ${threadConnected ? 'connected' : 'disconnected'}">
            <i class="fa-solid fa-usb"></i>
            <span>Thread: ${threadConnected ? threadPort : 'Not Connected'}</span>
        </div>`;
        
        // Z-Wave dongle
        html += `<div class="hw-status-item ${zwaveConnected ? 'connected' : 'disconnected'}">
            <i class="fa-solid fa-usb"></i>
            <span>Z-Wave: ${zwaveConnected ? zwavePort : 'Not Connected'}</span>
        </div>`;
        
        // Bluetooth
        html += `<div class="hw-status-item connected">
            <i class="fa-brands fa-bluetooth-b"></i>
            <span>Bluetooth: Built-in</span>
        </div>`;
        
        html += '</div>';
        container.innerHTML = html;
    },

    async clearData() {
        if (confirm("Are you sure you want to clear all discovered devices, RFID cards, and vulnerabilities?")) {
            try {
                await authFetch(`${API_BASE}/iot/devices`, { method: "DELETE" });
                await authFetch(`${API_BASE}/rfid/cards`, { method: "DELETE" });
                this.devices = [];
                this.rfidCards = [];
                this.selectedDevice = null;
                this.renderDevicesTable();
                this.renderCardsTable();
                this.renderDeviceDetails();
                this.fetchSummary();
                this.updateProtocolChart();
                this.fetchAISuggestions();
                this.fetchAISecurityScore();
            } catch (e) {
                console.error(e);
                alert("Failed to clear data.");
            }
        }
    },
    
    // ======== AI FUNCTIONS ========
    async fetchAISuggestions() {
        try {
            const res = await authFetch(`${API_BASE}/ai/suggestions`);
            if (res.ok) {
                const data = await res.json();
                this.renderAISuggestions(data.suggestions);
            }
        } catch (e) {
            console.error("Failed to fetch AI suggestions", e);
        }
    },
    
    renderAISuggestions(suggestions) {
        const container = document.getElementById('aiSuggestions');
        if (!container) return;
        
        if (!suggestions || suggestions.length === 0) {
            container.innerHTML = `
                <div style="color: var(--text-muted); font-size: 12px; text-align: center; padding: 20px;">
                    <i class="fa-solid fa-check-circle" style="color: var(--status-safe); font-size: 24px; margin-bottom: 10px;"></i>
                    <p>No critical recommendations at this time</p>
                </div>`;
            return;
        }
        
        container.innerHTML = suggestions.map(s => `
            <div class="ai-suggestion-item" style="
                display: flex;
                align-items: flex-start;
                gap: 12px;
                padding: 12px;
                background: rgba(0,0,0,0.2);
                border-radius: 8px;
                border-left: 3px solid ${s.type === 'alert' ? 'var(--status-risk)' : s.type === 'suggested_scan' ? 'var(--accent-blue)' : 'var(--status-medium)'};">
                <div style="flex-shrink: 0;">
                    <i class="fa-solid ${s.icon}" style="color: ${s.type === 'alert' ? 'var(--status-risk)' : 'var(--accent-blue)'}; font-size: 16px;"></i>
                </div>
                <div style="flex: 1;">
                    <div style="font-weight: 500; font-size: 13px; margin-bottom: 4px;">${s.title}</div>
                    <div style="font-size: 11px; color: var(--text-muted);">${s.description}</div>
                    ${s.action ? `<button class="btn btn-outline-blue" style="margin-top: 8px; font-size: 11px; padding: 4px 10px;" onclick="app.executeSuggestion('${s.action}', ${JSON.stringify(s.device_ids || []).replace(/"/g, "'")})">
                        Take Action
                    </button>` : ''}
                </div>
            </div>
        `).join('');
    },
    
    executeSuggestion(action, deviceIds) {
        if (action.startsWith('startScan')) {
            const scanType = action.match(/'([^']+)'/)?.[1];
            if (scanType) {
                this.startScan(scanType);
            }
        } else if (action === 'view_device' && deviceIds && deviceIds.length > 0) {
            this.selectDevice(deviceIds[0]);
        } else if (action === 'checkHardware') {
            this.fetchHardwareStatus();
        }
    },
    
    async fetchAISecurityScore() {
        try {
            const res = await authFetch(`${API_BASE}/ai/security-score`);
            if (res.ok) {
                const data = await res.json();
                this.renderAISecurityScore(data.score);
            }
        } catch (e) {
            console.error("Failed to fetch AI security score", e);
        }
    },
    
    renderAISecurityScore(score) {
        const scoreValue = document.getElementById('scoreValue');
        const scoreGrade = document.getElementById('scoreGrade');
        const scoreDesc = document.getElementById('scoreDescription');
        const scoreCircle = document.getElementById('securityScoreCircle');
        
        if (!scoreValue) return;
        
        // Determine color based on score
        let color = '#22c55e'; // green
        if (score.score < 60) color = '#f59e0b'; // yellow
        if (score.score < 40) color = '#ef4444'; // red
        
        scoreValue.textContent = Math.round(score.score);
        scoreGrade.textContent = score.grade;
        scoreDesc.textContent = score.description;
        
        // Update circle gradient
        scoreCircle.style.background = `conic-gradient(${color} 0% ${score.score}%, rgba(255,255,255,0.1) ${score.score}% 100%)`;
    },
    
    async analyzeDeviceAI() {
        if (!this.selectedDevice) return;
        
        const analysisDiv = document.getElementById('aiDeviceAnalysis');
        const deviceTypeDiv = document.getElementById('aiDeviceType');
        const predictedVulnsDiv = document.getElementById('aiPredictedVulns');
        
        if (analysisDiv) {
            analysisDiv.classList.remove('hidden');
            deviceTypeDiv.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Analyzing...';
            predictedVulnsDiv.innerHTML = '';
        }
        
        try {
            const res = await authFetch(`${API_BASE}/ai/analyze/device/${this.selectedDevice.id}`);
            if (res.ok) {
                const data = await res.json();
                const analysis = data.analysis;
                
                // Device type
                deviceTypeDiv.innerHTML = `
                    <strong>Device Type:</strong> ${analysis.device_type.replace('_pattern', '').replace('_', ' ').toUpperCase()}
                    <span style="margin-left: 10px; opacity: 0.7;">Confidence: ${Math.round(analysis.confidence * 100)}%</span>
                `;
                
                // Predicted vulnerabilities
                if (analysis.predicted_vulnerabilities && analysis.predicted_vulnerabilities.length > 0) {
                    predictedVulnsDiv.innerHTML = `
                        <strong style="display: block; margin-top: 8px;">Predicted Vulnerabilities:</strong>
                        ${analysis.predicted_vulnerabilities.map(v => `
                            <div style="margin-top: 4px; padding: 4px 8px; background: rgba(239, 68, 68, 0.2); border-radius: 4px; font-size: 10px;">
                                <i class="fa-solid fa-triangle-exclamation" style="color: var(--status-risk);"></i>
                                ${v.vuln_type} (${Math.round(v.confidence * 100)}% confidence)
                            </div>
                        `).join('')}
                    `;
                } else {
                    predictedVulnsDiv.innerHTML = `
                        <span style="color: var(--status-safe); margin-top: 8px; display: block;">
                            <i class="fa-solid fa-check"></i> No predicted vulnerabilities
                        </span>`;
                }
                
                // Show anomaly warning if detected
                if (analysis.is_anomaly) {
                    this.showToast('Anomaly detected! Device behavior is unusual.', 'warning');
                }
            }
        } catch (e) {
            console.error('AI analysis failed', e);
            if (deviceTypeDiv) {
                deviceTypeDiv.innerHTML = '<span style="color: var(--status-risk);">Analysis failed</span>';
            }
        }
    },
    
    async getRemediation(vulnType) {
        try {
            const res = await authFetch(`${API_BASE}/ai/remediation/${vulnType}`);
            if (res.ok) {
                const data = await res.json();
                return data.remediation;
            }
        } catch (e) {
            console.error('Failed to get remediation', e);
        }
        return null;
    },

    // ================================================================
    // ADVANCED WIFI - MONITOR MODE
    // ================================================================
    async enableMonitor() {
        const iface = document.getElementById('monitorInterface')?.value || 'wlan0';
        const btn = document.getElementById('btnMonitorEnable');
        if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Enabling...'; }

        try {
            const res = await authFetch(`${API_BASE}/wireless/monitor/enable`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ interface: iface })
            });
            const data = await res.json();
            if (data.status === 'success') {
                this.showToast('Monitor mode enabled!', 'success');
                this.updateMonitorUI(true, data);
            } else {
                this.showToast(`Failed: ${data.message}`, 'risk');
            }
        } catch (e) {
            this.showToast('Error enabling monitor mode', 'risk');
            console.error('[Monitor] Error:', e);
        } finally {
            if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fa-solid fa-play"></i> Enable Monitor'; }
            this.fetchMonitorStatus();
        }
    },

    async disableMonitor() {
        const btn = document.getElementById('btnMonitorDisable');
        if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Disabling...'; }

        try {
            const res = await authFetch(`${API_BASE}/wireless/monitor/disable`, { method: 'POST' });
            const data = await res.json();
            if (data.status === 'success') {
                this.showToast('Monitor mode disabled. Back to managed mode.', 'success');
                this.updateMonitorUI(false);
            } else {
                this.showToast(`Failed: ${data.message}`, 'risk');
            }
        } catch (e) {
            this.showToast('Error disabling monitor mode', 'risk');
        } finally {
            if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fa-solid fa-stop"></i> Disable'; }
            this.fetchMonitorStatus();
        }
    },

    async setMonitorChannel() {
        const channel = parseInt(document.getElementById('monitorChannel')?.value);
        if (!channel || channel < 1 || channel > 13) {
            this.showToast('Please enter a valid channel (1-13)', 'warning');
            return;
        }
        try {
            const res = await authFetch(`${API_BASE}/wireless/monitor/channel`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ channel: channel })
            });
            const data = await res.json();
            if (data.status === 'success') {
                this.showToast(`Channel set to ${channel}`, 'success');
                this.fetchMonitorStatus();
            } else {
                this.showToast(`Failed: ${data.message}`, 'risk');
            }
        } catch (e) {
            this.showToast('Error setting channel', 'risk');
        }
    },

    async fetchMonitorStatus() {
        try {
            const res = await authFetch(`${API_BASE}/wireless/monitor/status`);
            if (res.ok) {
                const data = await res.json();
                this.updateMonitorUI(data.active, data);
            }
        } catch (e) {
            console.error('[Monitor] Status check failed:', e);
        }
    },

    updateMonitorUI(active, data = {}) {
        const badge = document.getElementById('monitorStatusBadge');
        const btnEnable = document.getElementById('btnMonitorEnable');
        const btnDisable = document.getElementById('btnMonitorDisable');
        const info = document.getElementById('monitorInfo');

        if (badge) {
            badge.textContent = active ? 'Active' : 'Inactive';
            badge.className = `badge ${active ? 'risk' : 'safe'}`;
        }
        if (btnEnable) btnEnable.disabled = active;
        if (btnDisable) btnDisable.disabled = !active;
        if (info) {
            if (active) {
                info.classList.remove('hidden');
                const iface = document.getElementById('monitorIface');
                const mode = document.getElementById('monitorModeVal');
                const ch = document.getElementById('monitorChannelVal');
                const uptime = document.getElementById('monitorUptime');
                if (iface) iface.textContent = data.interface || monitor_state?.interface || '--';
                if (mode) mode.textContent = 'MONITOR';
                if (ch) ch.textContent = data.channel || '--';
                if (uptime) {
                    const started = data.started_at;
                    if (started) {
                        const diff = Math.floor((Date.now() - new Date(started).getTime()) / 1000);
                        uptime.textContent = diff > 60 ? `${Math.floor(diff/60)}m ${diff%60}s` : `${diff}s`;
                    } else {
                        uptime.textContent = '--';
                    }
                }
            } else {
                info.classList.add('hidden');
            }
        }
    },

    handleMonitorModeChanged(data) {
        console.log('[Monitor] Mode changed:', data);
        this.fetchMonitorStatus();
    },

    // ================================================================
    // ADVANCED WIFI - CLIENT SNIFFER
    // ================================================================
    async startSniffer() {
        const duration = parseInt(document.getElementById('snifferDuration')?.value) || 30;
        const btn = document.getElementById('btnSnifferStart');
        if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Starting...'; }

        try {
            const res = await authFetch(`${API_BASE}/wireless/sniffer/start`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ duration: duration })
            });
            const data = await res.json();
            if (data.status === 'success') {
                this.showToast(`Sniffer started for ${duration}s`, 'success');
                this.updateSnifferUI(true, data);
                // Auto-refresh sniffer status periodically
                this._snifferPoll = setInterval(() => this.fetchSnifferStatus(), 3000);
            } else {
                this.showToast(`Failed: ${data.message}`, 'risk');
            }
        } catch (e) {
            this.showToast('Error starting sniffer', 'risk');
        } finally {
            if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fa-solid fa-play"></i> Start Sniffing'; }
        }
    },

    async stopSniffer() {
        const btn = document.getElementById('btnSnifferStop');
        if (btn) { btn.disabled = true; }

        try {
            const res = await authFetch(`${API_BASE}/wireless/sniffer/stop`, { method: 'POST' });
            const data = await res.json();
            if (data.status === 'success') {
                this.showToast('Sniffer stopped', 'success');
            }
        } catch (e) {
            this.showToast('Error stopping sniffer', 'risk');
        } finally {
            if (btn) { btn.disabled = false; }
            if (this._snifferPoll) { clearInterval(this._snifferPoll); this._snifferPoll = null; }
            this.fetchSnifferStatus();
        }
    },

    async fetchSnifferStatus() {
        try {
            const res = await authFetch(`${API_BASE}/wireless/sniffer/status`);
            if (res.ok) {
                const data = await res.json();
                this.updateSnifferUI(data.active, data);
            }
        } catch (e) {
            console.error('[Sniffer] Status check failed:', e);
        }
    },

    async fetchSnifferClients() {
        try {
            const res = await authFetch(`${API_BASE}/wireless/sniffer/clients`);
            if (res.ok) {
                const data = await res.json();
                this.renderSnifferClients(data.clients || []);
            }
        } catch (e) {
            console.error('[Sniffer] Client fetch failed:', e);
        }
    },

    updateSnifferUI(active, data = {}) {
        const badge = document.getElementById('snifferStatusBadge');
        const btnStart = document.getElementById('btnSnifferStart');
        const btnStop = document.getElementById('btnSnifferStop');
        const stats = document.getElementById('snifferStats');

        if (badge) {
            badge.textContent = active ? 'Sniffing' : 'Inactive';
            badge.className = `badge ${active ? 'medium' : 'safe'}`;
        }
        if (btnStart) btnStart.disabled = active;
        if (btnStop) btnStop.disabled = !active;
        if (stats) {
            stats.classList.remove('hidden');
            const clients = document.getElementById('snifferClientCount');
            const probes = document.getElementById('snifferProbeCount');
            const packets = document.getElementById('snifferPacketCount');
            const dur = document.getElementById('snifferDurationVal');
            if (clients) clients.textContent = (data.clients || []).length;
            if (probes) probes.textContent = (data.probe_requests || []).length;
            if (packets) packets.textContent = data.packets_captured || 0;
            if (dur) dur.textContent = active ? 'Running...' : 'Stopped';
        }

        // Show clients table if there are clients
        if (data.clients && data.clients.length > 0) {
            this.renderSnifferClients(data.clients);
        }
    },

    renderSnifferClients(clients) {
        const container = document.getElementById('snifferClientsList');
        const tbody = document.getElementById('snifferClientsBody');
        if (!container || !tbody) return;

        container.classList.remove('hidden');
        tbody.innerHTML = '';

        clients.forEach(c => {
            const tr = document.createElement('tr');
            const signalColor = this.getSignalColor(c.signal_dbm || 'N/A');
            tr.innerHTML = `
                <td style="font-family:monospace;font-size:12px">${c.mac || '--'}</td>
                <td>${c.ssid || (c.probed_ssids ? c.probed_ssids.join(', ') : '--')}</td>
                <td><span style="color:${signalColor}">${c.signal_dbm || 'N/A'} dBm</span></td>
                <td style="font-size:11px;color:var(--text-muted)">${c.last_seen || '--'}</td>
            `;
            tbody.appendChild(tr);
        });
    },

    handleWifiClientFound(data) {
        console.log('[Sniffer] Client found:', data.mac);
        this.fetchSnifferStatus();
        this.fetchSnifferClients();
    },

    // ================================================================
    // ADVANCED WIFI - HANDSHAKE CAPTURE
    // ================================================================
    async startHandshake() {
        const bssid = document.getElementById('handshakeBSSID')?.value;
        const channel = parseInt(document.getElementById('handshakeChannel')?.value);
        const ssid = document.getElementById('handshakeSSID')?.value;
        const timeout = parseInt(document.getElementById('handshakeTimeout')?.value) || 60;

        if (!bssid) {
            this.showToast('Please enter a target BSSID', 'warning');
            return;
        }

        const btn = document.getElementById('btnHandshakeStart');
        if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Capturing...'; }

        try {
            const res = await authFetch(`${API_BASE}/wireless/handshake/start`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ bssid, channel, ssid, timeout })
            });
            const data = await res.json();
            if (data.status === 'success') {
                this.showToast('Handshake capture started. Waiting for EAPOL frames...', 'info');
                this.updateHandshakeUI(true, { target_bssid: bssid, channel, target_ssid: ssid });
                this._handshakePoll = setInterval(() => this.fetchHandshakeStatus(), 3000);
            } else {
                this.showToast(`Failed: ${data.message}`, 'risk');
            }
        } catch (e) {
            this.showToast('Error starting handshake capture', 'risk');
        } finally {
            if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fa-solid fa-play"></i> Capture'; }
        }
    },

    async stopHandshake() {
        const btn = document.getElementById('btnHandshakeStop');
        if (btn) btn.disabled = true;

        try {
            const res = await authFetch(`${API_BASE}/wireless/handshake/stop`, { method: 'POST' });
            const data = await res.json();
            if (data.status === 'success') {
                this.showToast('Handshake capture stopped', 'success');
            }
        } catch (e) {
            this.showToast('Error stopping capture', 'risk');
        } finally {
            if (btn) btn.disabled = false;
            if (this._handshakePoll) { clearInterval(this._handshakePoll); this._handshakePoll = null; }
            this.fetchHandshakeStatus();
        }
    },

    async fetchHandshakeStatus() {
        try {
            const res = await authFetch(`${API_BASE}/wireless/handshake/status`);
            if (res.ok) {
                const data = await res.json();
                this.updateHandshakeUI(data.active, data);
            }
        } catch (e) {
            console.error('[Handshake] Status check failed:', e);
        }
    },

    updateHandshakeUI(active, data = {}) {
        const badge = document.getElementById('handshakeStatusBadge');
        const btnStart = document.getElementById('btnHandshakeStart');
        const btnStop = document.getElementById('btnHandshakeStop');
        const progress = document.getElementById('handshakeProgress');

        if (badge) {
            badge.textContent = active ? 'Capturing' : (data.handshake_captured ? 'Captured!' : 'Inactive');
            badge.className = `badge ${data.handshake_captured ? 'risk' : (active ? 'medium' : 'safe')}`;
        }
        if (btnStart) btnStart.disabled = active;
        if (btnStop) btnStop.disabled = !active;

        if (progress) {
            progress.classList.remove('hidden');
            const target = document.getElementById('handshakeTargetVal');
            const ch = document.getElementById('handshakeChannelVal');
            const eapol = document.getElementById('handshakeEapolCount');
            const status = document.getElementById('handshakeCaptureStatus');

            if (target) target.textContent = data.target_ssid || data.target_bssid || '--';
            if (ch) ch.textContent = data.channel || '--';
            if (eapol) eapol.textContent = data.packets_captured || 0;
            if (status) {
                status.textContent = data.handshake_captured ? 'HANDSHAKE CAPTURED!' : (active ? 'Listening for EAPOL...' : 'Stopped');
                status.style.color = data.handshake_captured ? 'var(--status-safe)' : 'var(--text-main)';
            }
        }

        const alertDiv = document.getElementById('handshakeCapturedAlert');
        if (alertDiv && data.handshake_captured) {
            alertDiv.classList.remove('hidden');
            if (data.capture_file) {
                alertDiv.innerHTML = `<i class="fa-solid fa-check-circle"></i> Handshake captured! Saved to: <code>${data.capture_file}</code>`;
            }
        }
    },

    handleHandshakeProgress(data) {
        console.log('[Handshake] Progress:', data);
        this.fetchHandshakeStatus();
    },

    handleHandshakeCaptured(data) {
        console.log('[Handshake] CAPTURED!', data);
        this.showToast('WPA Handshake Captured! Check the capture file.', 'success');
        this.fetchHandshakeStatus();
        if (this._handshakePoll) { clearInterval(this._handshakePoll); this._handshakePoll = null; }
    },

    // ================================================================
    // ADVANCED WIFI - DEAUTH ATTACK TEST
    // ================================================================
    async startDeauthTest() {
        const target_mac = document.getElementById('deauthTargetMac')?.value;
        const ap_bssid = document.getElementById('deauthApBssid')?.value;
        const channel = parseInt(document.getElementById('deauthChannel')?.value);
        const count = parseInt(document.getElementById('deauthCount')?.value) || 5;

        if (!target_mac || !ap_bssid) {
            this.showToast('Please enter target MAC and AP BSSID', 'warning');
            return;
        }

        const btn = document.getElementById('btnDeauthTest');
        if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Testing...'; }

        try {
            const res = await authFetch(`${API_BASE}/wireless/deauth/test`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ target_mac, ap_bssid, channel, count })
            });
            const data = await res.json();
            if (data.status === 'success') {
                this.showToast('Deauth test started...', 'info');
                this._deauthPoll = setInterval(() => this.fetchDeauthTestStatus(), 2000);
            } else {
                this.showToast(`Failed: ${data.message}`, 'risk');
            }
        } catch (e) {
            this.showToast('Error starting deauth test', 'risk');
        } finally {
            if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fa-solid fa-bolt"></i> Test Resilience'; }
        }
    },

    async fetchDeauthTestStatus() {
        try {
            const res = await authFetch(`${API_BASE}/wireless/deauth/test/status`);
            if (res.ok) {
                const data = await res.json();
                this.updateDeauthTestUI(data);
            }
        } catch (e) {
            console.error('[Deauth] Status check failed:', e);
        }
    },

    updateDeauthTestUI(data = {}) {
        const result = document.getElementById('deauthTestResult');
        const badge = document.getElementById('deauthTestBadge');

        if (badge) {
            badge.textContent = data.active ? 'Testing' : 'Inactive';
            badge.className = `badge ${data.active ? 'medium' : 'safe'}`;
        }

        if (result && (data.packets_sent > 0 || data.active === false)) {
            result.classList.remove('hidden');
            const sent = document.getElementById('deauthPacketsSent');
            const disconnected = document.getElementById('deauthClientDisconnected');
            const mfp = document.getElementById('deauthMfpStatus');
            const verdict = document.getElementById('deauthVerdict');

            if (sent) sent.textContent = data.packets_sent || 0;
            if (disconnected) {
                disconnected.textContent = data.client_disconnected ? 'Yes' : 'No';
                disconnected.style.color = data.client_disconnected ? 'var(--status-risk)' : 'var(--status-safe)';
            }
            if (mfp) {
                mfp.textContent = data.protected ? 'Enabled (Protected)' : 'Disabled (Vulnerable)';
                mfp.style.color = data.protected ? 'var(--status-safe)' : 'var(--status-risk)';
            }
            if (verdict) {
                if (data.client_disconnected && !data.protected) {
                    verdict.textContent = 'VULNERABLE - No MFP';
                    verdict.style.color = 'var(--status-risk)';
                } else if (data.protected) {
                    verdict.textContent = 'PROTECTED - 802.11w Active';
                    verdict.style.color = 'var(--status-safe)';
                } else if (!data.active) {
                    verdict.textContent = 'Test complete';
                    verdict.style.color = 'var(--text-muted)';
                }
            }
        }

        // Stop polling when test is complete
        if (!data.active && this._deauthPoll) {
            clearInterval(this._deauthPoll);
            this._deauthPoll = null;
        }
    },

    handleDeauthTestProgress(data) {
        console.log('[Deauth] Progress:', data);
        this.fetchDeauthTestStatus();
    },

    // ================================================================
    // ADVANCED WIFI - ROGUE AP DETECTION
    // ================================================================
    async startRogueDetection() {
        const duration = parseInt(document.getElementById('rogueDuration')?.value) || 30;
        const btn = document.getElementById('btnRogueStart');
        if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Detecting...'; }

        try {
            const res = await authFetch(`${API_BASE}/wireless/rogue/start`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ duration })
            });
            const data = await res.json();
            if (data.status === 'success') {
                this.showToast('Rogue AP detection started', 'success');
                this.updateRogueUI(true, data);
                this._roguePoll = setInterval(() => this.fetchRogueStatus(), 3000);
            } else {
                this.showToast(`Failed: ${data.message}`, 'risk');
            }
        } catch (e) {
            this.showToast('Error starting rogue detection', 'risk');
        } finally {
            if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fa-solid fa-play"></i> Start Detection'; }
        }
    },

    async stopRogueDetection() {
        const btn = document.getElementById('btnRogueStop');
        if (btn) btn.disabled = true;

        try {
            const res = await authFetch(`${API_BASE}/wireless/rogue/stop`, { method: 'POST' });
            const data = await res.json();
            if (data.status === 'success') {
                this.showToast('Rogue AP detection stopped', 'success');
            }
        } catch (e) {
            this.showToast('Error stopping detection', 'risk');
        } finally {
            if (btn) btn.disabled = false;
            if (this._roguePoll) { clearInterval(this._roguePoll); this._roguePoll = null; }
            this.fetchRogueStatus();
        }
    },

    async fetchRogueStatus() {
        try {
            const res = await authFetch(`${API_BASE}/wireless/rogue/status`);
            if (res.ok) {
                const data = await res.json();
                this.updateRogueUI(data.active, data);
            }
        } catch (e) {
            console.error('[Rogue] Status check failed:', e);
        }
    },

    updateRogueUI(active, data = {}) {
        const badge = document.getElementById('rogueStatusBadge');
        const btnStart = document.getElementById('btnRogueStart');
        const btnStop = document.getElementById('btnRogueStop');

        if (badge) {
            badge.textContent = active ? 'Detecting' : 'Inactive';
            badge.className = `badge ${active ? 'medium' : 'safe'}`;
        }
        if (btnStart) btnStart.disabled = active;
        if (btnStop) btnStop.disabled = !active;

        // Render alerts
        if (data.alerts && data.alerts.length > 0) {
            const alertContainer = document.getElementById('rogueAlerts');
            const alertList = document.getElementById('rogueAlertsList');
            const alertCount = document.getElementById('rogueAlertCount');
            if (alertContainer) alertContainer.classList.remove('hidden');
            if (alertCount) alertCount.textContent = data.alerts.length;
            if (alertList) {
                alertList.innerHTML = data.alerts.map(a => `
                    <div class="adv-wifi-alert ${a.severity || 'warning'}">
                        <i class="fa-solid ${a.severity === 'CRITICAL' ? 'fa-skull-crossbones' : 'fa-triangle-exclamation'}"></i>
                        <div>
                            <strong>${a.severity || 'WARNING'}:</strong> SSID "${a.ssid || ''}" found on multiple BSSIDs
                            <div style="font-size:10px;color:var(--text-muted);margin-top:4px">
                                ${a.bssids ? a.bssids.map(b => `${b.bssid} (Ch:${b.channel}, ${b.signal}dBm, ${b.encryption})`).join(' | ') : ''}
                            </div>
                        </div>
                    </div>
                `).join('');
            }
        }

        // Render known APs
        if (data.known_aps && data.known_aps.length > 0) {
            const apsContainer = document.getElementById('rogueKnownAps');
            const tbody = document.getElementById('rogueApsBody');
            if (apsContainer) apsContainer.classList.remove('hidden');
            if (tbody) {
                tbody.innerHTML = data.known_aps.map(ap => `
                    <tr>
                        <td>${ap.ssid || '<hidden>'}</td>
                        <td style="font-family:monospace;font-size:11px">${ap.bssid}</td>
                        <td>${ap.channel}</td>
                        <td>${ap.signal} dBm</td>
                        <td><span class="badge ${ap.encryption.includes('WPA') ? 'safe' : 'risk'}">${ap.encryption}</span></td>
                    </tr>
                `).join('');
            }
        }
    },

    handleRogueApAlert(data) {
        console.log('[Rogue] Alert:', data);
        this.showToast(`Rogue AP detected! SSID: ${data.ssid || 'Unknown'}`, 'risk');
        this.fetchRogueStatus();
    },

    // ================================================================
    // ADVANCED WIFI - SIGNAL MAPPING
    // ================================================================
    async startSignalMap() {
        const duration = parseInt(document.getElementById('signalDuration')?.value) || 15;
        try {
            const res = await authFetch(`${API_BASE}/wireless/signal/map`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ duration })
            });
            const data = await res.json();
            if (data.status === 'success') {
                this.showToast('Signal mapping started', 'success');
                this.renderSignalMap(data);
            } else {
                this.showToast(`Failed: ${data.message}`, 'risk');
            }
        } catch (e) {
            this.showToast('Error starting signal map', 'risk');
        }
    },

    renderSignalMap(data) {
        const container = document.getElementById('signalMapResults');
        if (!container) return;
        container.classList.remove('hidden');

        // Render channel bars
        const barsContainer = document.getElementById('signalChannelBars');
        if (barsContainer && data.channel_usage) {
            const channels = data.channel_usage;
            const maxNetworks = Math.max(...Object.values(channels).map(c => c.network_count || 0), 1);

            let barsHTML = '<div class="signal-bars">';
            for (let ch = 1; ch <= 13; ch++) {
                const info = channels[ch] || {};
                const count = info.network_count || 0;
                const height = Math.max((count / maxNetworks) * 100, 5);
                const isBest = data.recommended_channel == ch;
                const overlap = info.adjacent_overlap || 0;

                barsHTML += `
                    <div class="signal-bar-col ${isBest ? 'best-channel' : ''}">
                        <div class="signal-bar-value">${count}</div>
                        <div class="signal-bar" style="height:${height}%" title="Ch ${ch}: ${count} networks, overlap: ${overlap}"></div>
                        <div class="signal-bar-label">${ch}</div>
                    </div>
                `;
            }
            barsHTML += '</div>';
            barsContainer.innerHTML = barsHTML;
        }

        // Render recommendation
        const rec = document.getElementById('signalRecommendation');
        const bestCh = document.getElementById('signalBestChannel');
        if (bestCh) bestCh.textContent = data.recommended_channel || '--';
        if (rec && data.best_channels) {
            const chList = data.best_channels.slice(0, 3).map(c => `Ch ${c.channel} (${c.score}pts)`).join(', ');
            rec.innerHTML = `
                <i class="fa-solid fa-star" style="color:var(--status-safe)"></i>
                <span>Recommended: <strong>${data.recommended_channel || '--'}</strong> | Top: ${chList}</span>
            `;
        }
    },

    handleSignalMapUpdate(data) {
        console.log('[Signal] Map update:', data);
        this.renderSignalMap(data);
    },

    // ================================================================
    // LOAD WIFI INTERFACES FOR ADVANCED PANEL
    // ================================================================
    async loadAdvancedWifiInterfaces() {
        try {
            const res = await authFetch(`${API_BASE}/wireless/interfaces`);
            if (res.ok) {
                const data = await res.json();
                const select = document.getElementById('monitorInterface');
                if (select && data.interfaces) {
                    select.innerHTML = '';
                    data.interfaces.forEach(iface => {
                        const option = document.createElement('option');
                        option.value = iface.name || iface;
                        option.textContent = iface.name || iface;
                        if ((iface.name || iface).startsWith('wl')) {
                            option.selected = true;
                        }
                        select.appendChild(option);
                    });
                }
            }
        } catch (e) {
            console.error('[AdvWifi] Failed to load interfaces:', e);
        }
    }
};

// Start App
document.addEventListener("DOMContentLoaded", () => {
    app.init();
});
