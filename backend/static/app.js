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
        this.fetchRfidReports();
        
        // Add auto-refresh every 5 seconds as backup
        this.startAutoRefresh();
        console.log('[Init] App initialized with auto-refresh enabled');
    },
    
    startAutoRefresh() {
        // Refresh devices and summary every 2 seconds for faster display
        const isLightweight = document.body.classList.contains('lightweight-mode');
        const interval = isLightweight ? 5000 : 2000;
        
        this.refreshInterval = setInterval(() => {
            // Only refresh if no scan is currently running
            this.fetchDevices();
            this.fetchSummary();
        }, interval);
        
        // Refresh hardware status every 2 seconds to quickly detect plugged dongles
        this.hwRefreshInterval = setInterval(() => {
            this.fetchHardwareStatus();
        }, 2000);
        
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
            'settings': ['System Settings', 'Configure scanner behaviors and options']
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

    async deepScanDevice() {
        if (!this.selectedDevice) return;
        
        const ip = this.selectedDevice.ip;
        if (ip.startsWith('ZW:') || ip.startsWith('BLE_') || ip.startsWith('ZB:')) {
            alert(`Deep scanning is not available for ${this.selectedDevice.protocol} devices.\nThis feature requires an IP-based device.`);
            return;
        }

        const resultsContainer = document.getElementById("deepScanResults");
        const progress = document.getElementById("deepScanProgress");
        const content = document.getElementById("deepScanContent");
        
        if (resultsContainer && progress && content) {
            resultsContainer.classList.remove("hidden");
            progress.classList.remove("hidden");
            content.innerHTML = "";
        }
        
        try {
            const res = await authFetch(`${API_BASE}/wireless/deep-scan/${ip}`, { method: "POST" });
            let data;
            try {
                data = await res.json();
            } catch (err) {
                console.error("Failed to parse JSON response:", err);
                data = { status: 'error', message: 'Invalid server response' };
            }
            
            if (data.status === 'success') {
                this.renderDeepScanResults(data);
                setTimeout(() => this.fetchDevices(), 2000);
            } else {
                const errorMsg = data.message || "Failed to perform deep scan";
                if (progress) progress.innerHTML = `<span style="color:var(--status-risk)">Error: ${errorMsg}</span>`;
            }
        } catch (e) {
            console.error("Deep scan failed:", e);
            if (progress) progress.innerHTML = `<span style="color:var(--status-risk)">Error starting deep scan</span>`;
        }
    },

    renderDeepScanResults(data) {
        const progress = document.getElementById("deepScanProgress");
        const content = document.getElementById("deepScanContent");
        
        if (progress) progress.classList.add("hidden");
        
        let html = `
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 15px;">
                <strong>Deep Scan complete for ${data.ip}</strong>
                <span class="badge ${data.overall_risk.toLowerCase()}">${data.overall_risk}</span>
            </div>
            
            <h5 style="font-size: 11px; color: var(--text-muted); margin-bottom: 5px;">Open Services (${data.open_ports.length})</h5>
            <div style="display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 15px;">
        `;
        
        data.services.forEach(s => {
            html += `<span style="background: rgba(255,255,255,0.1); padding: 4px 8px; border-radius: 4px; font-size: 11px; font-family: monospace;">${s}</span>`;
        });
        
        html += `</div>
            <h5 style="font-size: 11px; color: var(--text-muted); margin-bottom: 5px;">Vulnerabilities Detected</h5>
        `;
        
        if (data.vulnerabilities.length === 0) {
            html += `<div style="padding: 10px; background: rgba(34, 197, 94, 0.1); border-left: 3px solid var(--status-safe); border-radius: 4px; font-size: 11px; margin-bottom: 15px;">No critical vulnerabilities detected.</div>`;
        } else {
            data.vulnerabilities.forEach(v => {
                html += `
                    <div style="padding: 10px; background: rgba(239, 68, 68, 0.1); border-left: 3px solid var(--status-risk); border-radius: 4px; font-size: 11px; margin-bottom: 8px;">
                        <strong>Port ${v.port} (${v.service})</strong><br>
                        ${v.description}
                    </div>
                `;
            });
        }
        
        html += `
            <h5 style="font-size: 11px; color: var(--text-muted); margin-bottom: 5px; margin-top: 15px;">Recommendations</h5>
            <ul style="font-size: 11px; padding-left: 20px; margin-bottom: 0;">
        `;
        
        data.recommendations.forEach(r => {
            html += `<li>${r}</li>`;
        });
        
        html += `</ul>`;
        
        if (content) content.innerHTML = html;
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
            tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color:var(--text-muted); padding: 30px;">
                <i class="fa-solid fa-id-card" style="font-size: 24px; display: block; margin-bottom: 8px; opacity: 0.4;"></i>
                No cards scanned yet. Click "Scan RFID Card" to begin.
            </td></tr>`;
            return;
        }

        this.rfidCards.forEach(c => {
            const tr = document.createElement("tr");
            let vulns = "None";
            try {
                let v = JSON.parse(c.vulnerabilities_json);
                if (Array.isArray(v) && v.length > 0) {
                    vulns = v.map(item => `<span style="display:inline-block; background:rgba(239,68,68,0.1); color:var(--status-risk); padding:2px 6px; border-radius:4px; font-size:10px; margin:1px;">${item}</span>`).join(' ');
                } else {
                    vulns = `<span style="color:var(--status-safe); font-size:11px;"><i class="fa-solid fa-shield-check"></i> Secure</span>`;
                }
            } catch(e) {}
            
            const integrityColor = c.tag_integrity === 'Valid' ? 'var(--status-safe)' : 'var(--status-risk)';
            
            tr.innerHTML = `
                <td style="font-family:monospace; font-weight:bold; font-size:11px;">${c.uid}</td>
                <td>${c.card_type}</td>
                <td><span style="font-size:11px; padding:2px 6px; background:rgba(139,92,246,0.1); color:var(--accent-purple); border-radius:4px;">${c.encryption_type}</span></td>
                <td style="font-size:12px;">${c.auth_mode}</td>
                <td style="font-size:12px;">${c.replay_protection}</td>
                <td style="font-size:12px; color:${integrityColor};">${c.tag_integrity}</td>
                <td><span class="badge ${c.risk_level.toLowerCase()}">${c.risk_level}</span></td>
                <td style="font-size: 11px; max-width: 200px;">${vulns}</td>
            `;
            tbody.appendChild(tr);
        });
    },

    async scanRfid() {
        const status = document.getElementById("rfidStatus");
        const scanBtn = document.getElementById("rfidScanBtn");
        
        // Show scanning state
        status.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin" style="color: var(--accent-blue);"></i> Scanning for RFID card...';
        if (scanBtn) {
            scanBtn.disabled = true;
            scanBtn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Scanning...';
        }
        
        try {
            const res = await authFetch(`${API_BASE}/rfid/scan`, { method: "POST" });
            let data;
            try {
                data = await res.json();
            } catch (err) {
                data = { status: 'error', message: 'Invalid server response' };
            }
            
            if (data.status === 'error') {
                const errorMsg = data.message || "Scan failed";
                status.innerHTML = `<i class="fa-solid fa-circle" style="color: var(--status-risk); font-size: 8px;"></i> ${errorMsg}`;
            } else {
                const successMsg = data.message || "Scan successful";
                status.innerHTML = `<i class="fa-solid fa-circle" style="color: var(--status-safe); font-size: 8px;"></i> ${successMsg}`;
                
                // Show last scan info card
                if (data.data) {
                    this.showLastScanCard(data.data);
                }
            }
            
            this.fetchCards();
            this.fetchRfidReports();
        } catch(e) {
            console.error("RFID scan failed:", e);
            status.innerHTML = '<i class="fa-solid fa-circle" style="color: var(--status-risk); font-size: 8px;"></i> Error scanning card.';
        } finally {
            if (scanBtn) {
                scanBtn.disabled = false;
                scanBtn.innerHTML = '<i class="fa-solid fa-satellite-dish"></i> Scan RFID Card';
            }
        }
    },

    showLastScanCard(cardData) {
        const container = document.getElementById("rfidLastScanCard");
        const info = document.getElementById("rfidLastScanInfo");
        if (!container || !info) return;
        
        container.classList.remove("hidden");
        
        const riskColor = cardData.risk_level === 'RISK' ? 'var(--status-risk)' : 'var(--status-safe)';
        const vulnCount = cardData.vulnerabilities ? cardData.vulnerabilities.length : 0;
        
        info.innerHTML = `
            <div style="background:rgba(0,0,0,0.2); padding:10px 14px; border-radius:8px;">
                <div style="font-size:10px; color:var(--text-muted); margin-bottom:4px;">UID</div>
                <div style="font-family:monospace; font-weight:bold; font-size:12px;">${cardData.uid}</div>
            </div>
            <div style="background:rgba(0,0,0,0.2); padding:10px 14px; border-radius:8px;">
                <div style="font-size:10px; color:var(--text-muted); margin-bottom:4px;">Card Type</div>
                <div style="font-size:13px; font-weight:500;">${cardData.card_type}</div>
            </div>
            <div style="background:rgba(0,0,0,0.2); padding:10px 14px; border-radius:8px;">
                <div style="font-size:10px; color:var(--text-muted); margin-bottom:4px;">Encryption</div>
                <div style="font-size:13px; color:var(--accent-purple);">${cardData.encryption_type}</div>
            </div>
            <div style="background:rgba(0,0,0,0.2); padding:10px 14px; border-radius:8px;">
                <div style="font-size:10px; color:var(--text-muted); margin-bottom:4px;">Auth Mode</div>
                <div style="font-size:13px;">${cardData.auth_mode}</div>
            </div>
            <div style="background:rgba(0,0,0,0.2); padding:10px 14px; border-radius:8px;">
                <div style="font-size:10px; color:var(--text-muted); margin-bottom:4px;">Risk Level</div>
                <div><span class="badge ${cardData.risk_level.toLowerCase()}">${cardData.risk_level}</span></div>
            </div>
            <div style="background:rgba(0,0,0,0.2); padding:10px 14px; border-radius:8px;">
                <div style="font-size:10px; color:var(--text-muted); margin-bottom:4px;">Vulnerabilities</div>
                <div style="font-size:13px; color:${vulnCount > 0 ? 'var(--status-risk)' : 'var(--status-safe)'};">${vulnCount > 0 ? vulnCount + ' found' : 'None'}</div>
            </div>
        `;
    },

    async simulateAttack(attackType) {
        const console_el = document.getElementById("attackConsole");
        const logs_el = document.getElementById("attackConsoleLogs");
        const title_el = document.getElementById("attackConsoleTitle");
        const summary_el = document.getElementById("attackResultSummary");
        
        // Show console, clear previous
        if (console_el) console_el.classList.remove("hidden");
        if (logs_el) logs_el.innerHTML = "";
        if (title_el) title_el.textContent = `RFID ${attackType} Attack — Running...`;
        if (summary_el) summary_el.classList.add("hidden");
        
        // Disable all attack buttons
        document.querySelectorAll('.quick-action-buttons .btn').forEach(b => b.disabled = true);
        
        this.showToast(`Launching ${attackType} Attack Simulation...`, 'info');
        
        try {
            let targetUid = null;
            if (this.rfidCards && this.rfidCards.length > 0) {
                targetUid = this.rfidCards[0].uid;
            }
            
            const reqBody = { attack_type: attackType };
            if (targetUid) reqBody.target_uid = targetUid;
            
            const res = await authFetch(`${API_BASE}/rfid/attack/simulate`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(reqBody)
            });
            
            const data = await res.json();
            
            if (data.status === 'success' && data.logs) {
                // Animate logs line-by-line
                await this.animateAttackLogs(data.logs, logs_el, data.risk_level);
                
                // Update console title
                if (title_el) {
                    title_el.textContent = `RFID ${attackType} Attack — Complete`;
                }
                
                // Show result summary card
                this.showAttackResultSummary(data);
                
                // Refresh reports
                this.fetchRfidReports();
            }
        } catch(e) {
            console.error("Attack simulation failed", e);
            if (logs_el) logs_el.innerHTML += `<div style="color:#ef4444;">ERROR: Attack simulation failed. Check console.</div>`;
            this.showToast("Failed to run attack simulation", 'risk');
        } finally {
            // Re-enable buttons
            document.querySelectorAll('.quick-action-buttons .btn').forEach(b => b.disabled = false);
        }
    },

    async animateAttackLogs(logs, container, riskLevel) {
        for (let i = 0; i < logs.length; i++) {
            await new Promise(resolve => setTimeout(resolve, 200 + Math.random() * 300));
            
            const line = logs[i];
            const div = document.createElement("div");
            div.style.opacity = "0";
            div.style.transform = "translateX(-10px)";
            div.style.transition = "all 0.3s ease";
            
            const isLastLine = i === logs.length - 1;
            const isWarning = line.includes("⚠") || line.includes("VULNERABLE") || line.includes("SUCCESS");
            const isSecure = line.includes("✓") || line.includes("SECURE") || line.includes("FAILED");
            
            if (isLastLine && isWarning) {
                div.style.color = "#ef4444";
                div.style.fontWeight = "bold";
                div.style.fontSize = "13px";
                div.style.padding = "6px 0";
                div.style.borderTop = "1px solid rgba(239,68,68,0.3)";
                div.style.marginTop = "4px";
            } else if (isLastLine && isSecure) {
                div.style.color = "#22c55e";
                div.style.fontWeight = "bold";
                div.style.fontSize = "13px";
                div.style.padding = "6px 0";
                div.style.borderTop = "1px solid rgba(34,197,94,0.3)";
                div.style.marginTop = "4px";
            } else if (line.includes("KEY CRACKED") || line.includes("CAPTURED")) {
                div.style.color = "#f59e0b";
            } else {
                div.style.color = "#22c55e";
            }
            
            // Add prompt prefix
            const prefix = isLastLine ? "└─ " : "├─ ";
            div.innerHTML = `<span style="color:var(--accent-blue);">$</span> ${prefix}${line}`;
            
            container.appendChild(div);
            container.scrollTop = container.scrollHeight;
            
            // Animate in
            requestAnimationFrame(() => {
                div.style.opacity = "1";
                div.style.transform = "translateX(0)";
            });
        }
    },

    showAttackResultSummary(data) {
        const el = document.getElementById("attackResultSummary");
        if (!el) return;
        
        const isVuln = data.risk_level === 'RISK';
        const bgColor = isVuln ? 'rgba(239,68,68,0.1)' : 'rgba(34,197,94,0.1)';
        const borderColor = isVuln ? 'var(--status-risk)' : 'var(--status-safe)';
        const icon = isVuln ? 'fa-shield-virus' : 'fa-shield-check';
        const iconColor = isVuln ? 'var(--status-risk)' : 'var(--status-safe)';
        
        el.style.background = bgColor;
        el.style.borderLeft = `3px solid ${borderColor}`;
        el.classList.remove("hidden");
        
        el.innerHTML = `
            <div style="display:flex; align-items:center; gap: 12px; margin-bottom: 12px;">
                <i class="fa-solid ${icon}" style="font-size: 24px; color: ${iconColor};"></i>
                <div>
                    <div style="font-weight:600; font-size:14px;">${data.attack_type} Attack — ${data.attack_result}</div>
                    <div style="font-size:11px; color:var(--text-muted);">Target: ${data.target_uid} (${data.card_type})</div>
                </div>
                <span class="badge ${data.risk_level.toLowerCase()}" style="margin-left:auto;">${data.risk_level}</span>
            </div>
            <div style="display:grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 12px;">
                <div><span style="color:var(--text-muted);">Encryption:</span> ${data.encryption_type}</div>
                <div><span style="color:var(--text-muted);">Auth Mode:</span> ${data.auth_mode}</div>
                <div><span style="color:var(--text-muted);">Replay Protection:</span> ${data.replay_protection}</div>
                <div><span style="color:var(--text-muted);">Tag Integrity:</span> ${data.tag_integrity}</div>
            </div>
            <div style="margin-top: 12px; padding: 10px; background:rgba(0,0,0,0.2); border-radius: 6px;">
                <div style="font-size:11px; color:var(--text-muted); margin-bottom:4px;"><i class="fa-solid fa-lightbulb" style="color:var(--status-medium);"></i> Remediation</div>
                <div style="font-size:12px;">${data.remediation}</div>
            </div>
        `;
    },

    async fetchRfidReports() {
        try {
            const res = await authFetch(`${API_BASE}/rfid/reports`);
            if (res.ok) {
                const reports = await res.json();
                this.renderRfidReportsTable(reports);
            }
        } catch(e) {
            console.error("Failed to load RFID reports");
        }
    },

    renderRfidReportsTable(reports) {
        const tbody = document.getElementById("rfidReportsTableBody");
        if (!tbody) return;
        tbody.innerHTML = "";
        
        if (reports.length === 0) {
            tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color:var(--text-muted); padding: 30px;">
                <i class="fa-solid fa-clipboard-list" style="font-size: 24px; display: block; margin-bottom: 8px; opacity: 0.4;"></i>
                No reports yet. Scan a card or run an attack simulation.
            </td></tr>`;
            return;
        }

        reports.forEach(r => {
            const tr = document.createElement("tr");
            const timeStr = new Date(r.timestamp).toLocaleString();
            
            let eventType, details;
            if (r.attack_type) {
                const attackIcons = {
                    'Clone': 'fa-clone', 'Replay': 'fa-rotate-left',
                    'Impersonation': 'fa-user-secret', 'Eavesdropping': 'fa-ear-listen',
                    'Tampering': 'fa-pen-to-square'
                };
                const icon = attackIcons[r.attack_type] || 'fa-bolt';
                eventType = `<i class="fa-solid ${icon}" style="color:var(--status-medium);"></i> ${r.attack_type}`;
                details = r.attack_result || 'N/A';
            } else {
                eventType = `<i class="fa-solid fa-satellite-dish" style="color:var(--accent-blue);"></i> Scan`;
                details = `Encryption: ${r.encryption_type}`;
            }
            
            tr.innerHTML = `
                <td style="font-size: 11px; white-space:nowrap;">${timeStr}</td>
                <td style="font-family:monospace; font-weight:bold; font-size:11px;">${r.uid}</td>
                <td style="font-size:12px;">${r.card_type}</td>
                <td>${eventType}</td>
                <td style="font-size:12px;">${details}</td>
                <td style="font-size:11px; color:var(--text-muted); max-width:180px;">${r.remediation || '—'}</td>
                <td><span class="badge ${r.risk_level.toLowerCase()}">${r.risk_level}</span></td>
                <td style="font-size:11px;"><span style="padding:2px 6px; border-radius:4px; background:rgba(139,92,246,0.1); color:var(--accent-purple);">${r.simulation_status}</span></td>
            `;
            tbody.appendChild(tr);
        });
    },

    async clearCards() {
        try {
            await authFetch(`${API_BASE}/rfid/cards`, { method: "DELETE" });
            this.fetchCards();
            this.fetchRfidReports();
            // Hide last scan card
            const lastScanCard = document.getElementById("rfidLastScanCard");
            if (lastScanCard) lastScanCard.classList.add("hidden");
            // Hide attack console
            const console_el = document.getElementById("attackConsole");
            if (console_el) console_el.classList.add("hidden");
            const summary_el = document.getElementById("attackResultSummary");
            if (summary_el) summary_el.classList.add("hidden");
            this.showToast("All RFID data cleared", "success");
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

};

// Start App
document.addEventListener("DOMContentLoaded", () => {
    app.init();
});
