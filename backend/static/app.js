const API_BASE = window.location.origin;

// Auth removed
function authHeaders(extra = {}) {
    return { 'Content-Type': 'application/json', ...extra };
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

    simulationMode: false,

    init() {
        this.fetchSummary();
        this.fetchDevices();
        this.fetchCards();
        this.fetchRfidReports();
        this.initNetworkSelect();
        this.initCharts();
        this.initWebSocket();
        this.discoverNetworks(); // لقط الشبكات تلقائي عند البداية
        this.fetchHardwareStatus();
        this.fetchAISuggestions(); // AI suggestions on load
        this.fetchAISecurityScore(); // AI security score
        this.fetchSettings(); // Load system settings

        // Add auto-refresh every 5 seconds as backup
        this.startAutoRefresh();
        console.log('[Init] App initialized with auto-refresh enabled');
    },

    async fetchSettings() {
        try {
            const res = await authFetch(`${API_BASE}/settings`);
            if (res.ok) {
                const data = await res.json();
                this.simulationMode = data.simulation_mode === 'true';
            }
        } catch (e) {
            console.warn("Settings endpoint not available, defaulting simulationMode to false", e);
        }

        const toggle = document.getElementById('globalSimulationToggle');
        if (toggle) toggle.checked = this.simulationMode;

        this.updateSimulationUI();
    },

    async toggleSimulationMode() {
        this.simulationMode = !this.simulationMode;
        try {
            await authFetch(`${API_BASE}/settings`, {
                method: 'PUT',
                body: JSON.stringify({ simulation_mode: this.simulationMode ? 'true' : 'false' })
            });
            this.showToast(`Simulation Mode ${this.simulationMode ? 'Enabled' : 'Disabled'}`, 'info');
        } catch (e) {
            console.error("Failed to save simulation mode", e);
        }
        this.updateSimulationUI();
    },

    updateSimulationUI() {
        const toggle = document.getElementById('globalSimulationToggle');
        if (toggle) toggle.checked = this.simulationMode;

        // If simulation mode is OFF, disable simulation buttons.
        const simButtons = document.querySelectorAll('.attack-nav-btn, [onclick="app.testCreds()"], #rfidScanBtn');
        simButtons.forEach(btn => {
            if (this.simulationMode) {
                btn.disabled = false;
                btn.classList.remove('locked');
                btn.title = '';
            } else {
                btn.disabled = true;
                btn.classList.add('locked');
                btn.title = 'Enable Simulation Mode first';
            }
        });

        // If simulation is off, show a locked overlay or message in terminal
        const term = document.getElementById('attackConsoleLogs');
        if (term && !this.simulationMode) {
            term.innerHTML = '<div class="terminal-line" style="color:var(--status-risk)">[SYSTEM] Simulation Mode is currently DISABLED. Enable it from the top bar to run simulated attacks.</div>';
        } else if (term && this.simulationMode && term.innerHTML.includes('DISABLED')) {
            term.innerHTML = '<div class="terminal-line">Pentex One Attack Simulator v2.0</div><div class="terminal-line">Ready for session...</div>';
        }
    },

     startAutoRefresh() {
         // Refresh devices and summary every 2 seconds for faster display
         const isLightweight = document.body.classList.contains('lightweight-mode');
         const interval = isLightweight ? 5000 : 2000;

         this.refreshInterval = setInterval(() => {
             // Only refresh if no scan is currently running
             this.fetchDevices();
             this.fetchSummary();
             this.fetchCards(); // Also refresh RFID cards
         }, interval);

         // Refresh hardware status every 2 seconds to quickly detect plugged dongles
         this.hwRefreshInterval = setInterval(() => {
             this.fetchHardwareStatus();
         }, 2000);

         console.log(`[AutoRefresh] Started - will refresh every ${interval / 1000} seconds`);
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

    typewriterEffect(element, text, delay = 0) {
        return new Promise((resolve) => {
            setTimeout(() => {
                const div = document.createElement('div');
                div.className = 'terminal-line';
                let charIndex = 0;

                // Pre-process text to replace markers with HTML
                const processedText = text
                    .replace(/\n/g, '<br>')
                    .replace(/\[COMPROMISED\]/g, '<span class="status-badge compromised">COMPROMISED</span>')
                    .replace(/\[SAFE\]/g, '<span class="status-badge safe">SAFE</span>');

                const type = () => {
                    if (charIndex < processedText.length) {
                        // If we hit a '<', skip to '>' to avoid typing HTML tags character by character
                        if (processedText[charIndex] === '<') {
                            const endTag = processedText.indexOf('>', charIndex);
                            if (endTag !== -1) {
                                div.innerHTML += processedText.substring(charIndex, endTag + 1);
                                charIndex = endTag + 1;
                            }
                        } else {
                            div.innerHTML += processedText[charIndex];
                            charIndex++;
                        }
                        setTimeout(type, Math.random() * 15 + 5);
                    } else {
                        element.appendChild(div);
                        if (element.parentElement) element.parentElement.scrollTop = element.parentElement.scrollHeight;
                        resolve();
                    }
                };
                type();
            }, delay);
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

        if (data.event === 'settings_updated') {
            console.log('[Sync] Settings updated globally:', data.settings);
            if (data.settings.simulation_mode !== undefined) {
                this.simulationMode = data.settings.simulation_mode === 'true' || data.settings.simulation_mode === true;
                this.updateSimulationUI();
            }
            return;
        }

        if (data.event === 'attack_simulation_start') {
            const logPanel = document.getElementById('attackConsoleLogs');
            if (logPanel) {
                logPanel.innerHTML = '';
                this.typewriterEffect(logPanel, `$ ${data.attack_type} Attack on ${data.target_uid}`, 0);
            }
        } else if (data.event === 'attack_simulation_log') {
            const logPanel = document.getElementById('attackConsoleLogs');
            if (logPanel) {
                this.typewriterEffect(logPanel, `> ${data.log_line}`, 50);
            }
        } else if (data.event === 'attack_simulation_complete') {
            const logPanel = document.getElementById('attackConsoleLogs');
            const remPanel = document.getElementById('attackResultSummary');
            if (logPanel) {
                const resultColor = data.success ? '#ef4444' : '#22c55e';
                const resultText = data.success ? '✗ ATTACK SUCCEEDED' : '✓ ATTACK FAILED';
                const div = document.createElement('div');
                div.innerHTML = `<div style="color: ${resultColor}; margin-top: 12px; font-weight: bold;">${resultText}</div>`;
                logPanel.appendChild(div);
                if (logPanel.parentElement) logPanel.parentElement.scrollTop = logPanel.parentElement.scrollHeight;
            }
            if (remPanel && data.remediation) {
                remPanel.classList.remove('hidden');
                remPanel.innerHTML = `<div style="background: rgba(139, 92, 246, 0.1); padding: 12px; border-radius: 8px; border-left: 3px solid #8b5cf6;">
                    <strong style="color: #8b5cf6;"><i class="fa-solid fa-lightbulb"></i> Remediation:</strong>
                    <div style="margin-top: 6px; font-size: 12px; line-height: 1.6;">${data.remediation}</div>
                </div>`;
            }
            document.querySelectorAll('.attack-action-btn').forEach(btn => btn.classList.remove('active-attack'));
        } else if (data.event === 'attack_simulation_error') {
            const logPanel = document.getElementById('attackConsoleLogs');
            if (logPanel) {
                const div = document.createElement('div');
                div.style.color = '#ef4444';
                div.textContent = `✗ ERROR: ${data.error}`;
                logPanel.appendChild(div);
            }
            document.querySelectorAll('.attack-action-btn').forEach(btn => btn.classList.remove('active-attack'));
        } else if (data.event === 'cred_test_start') {
            const logPanel = document.getElementById('credTestLogs');
            if (logPanel) {
                logPanel.innerHTML = '';
                this.typewriterEffect(logPanel, `$ Starting Credential Simulator on ${data.target_uid}`, 0);
            }
        } else if (data.event === 'cred_test_log') {
            const logPanel = document.getElementById('credTestLogs');
            if (logPanel) {
                this.typewriterEffect(logPanel, `> ${data.log_line}`, 50);
            }
        } else if (data.event === 'cred_test_complete') {
            const logPanel = document.getElementById('credTestLogs');
            const remPanel = document.getElementById('credTestSummary');
            if (logPanel) {
                const resultColor = data.success ? '#ef4444' : '#22c55e';
                const resultText = data.success ? '✗ WEAK CREDENTIALS FOUND' : '✓ SECURE (NO WEAK CREDENTIALS)';
                const div = document.createElement('div');
                div.innerHTML = `<div style="color: ${resultColor}; margin-top: 12px; font-weight: bold;">${resultText}</div>`;
                logPanel.appendChild(div);
                if (logPanel.parentElement) logPanel.parentElement.scrollTop = logPanel.parentElement.scrollHeight;
            }
            if (remPanel && data.remediation) {
                remPanel.classList.remove('hidden');
                remPanel.innerHTML = `<div style="background: rgba(139, 92, 246, 0.1); padding: 12px; border-radius: 8px; border-left: 3px solid #8b5cf6;">
                    <strong style="color: #8b5cf6;"><i class="fa-solid fa-lightbulb"></i> Remediation:</strong>
                    <div style="margin-top: 6px; font-size: 12px; line-height: 1.6;">${data.remediation}</div>
                </div>`;
            }
            this.fetchDevices();
        } else if (data.event === 'device_found') {
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
            if (data.type === 'deep_port_scan') {
                this.updateDeepScanProgress(data.progress, data.message);
            } else {
                this.updateScanProgress(data.progress, data.message);
            }
        } else if (data.event === 'scan_complete' && data.type === 'deep_port_scan') {
            try {
                // SINGLE SOURCE OF TRUTH: All deep scan data is processed here
                console.log('[DeepScan] Received final aggregated results for:', data.ip);
                const riskLevel = data.risk_level || 'UNKNOWN';
                this.showToast(`Deep Scan Complete for ${data.ip}`, 'success');

                // Update Header
                const ipEl = document.getElementById('deepScanIp');
                const vendorEl = document.getElementById('deepScanVendor');
                if (ipEl) ipEl.textContent = data.ip || '---';
                if (vendorEl) vendorEl.textContent = data.vendor || 'Unknown Vendor';

                const statusBadge = document.getElementById('deepScanStatusBadge');
                if (statusBadge) {
                    statusBadge.textContent = riskLevel.toUpperCase();
                    statusBadge.className = `badge status-${riskLevel.toLowerCase()}`;
                }

                // Render technical data
                const vulns = data.vulnerabilities || [];
                const banners = data.service_banners || {};
                const ports = Array.isArray(data.open_ports) ? data.open_ports : [];

                console.log(`[DeepScan] Rendering ${ports.length} ports and ${vulns.length} vulnerabilities`);
                this.renderDeepScanCards(vulns, banners, ports);

                // Render AI analysis
                if (data.ai_results || data.ai_summary) {
                    this.renderAIAnalysis(data.ai_results || { dynamic_summary: data.ai_summary });
                }

                this.fetchDevices();
                this.fetchSummary();
            } catch (e) {
                console.error('[DeepScan] Render error:', e);
            } finally {
                const progress = document.getElementById('deepScanProgress');
                if (progress) progress.classList.add('hidden');
            }

        } else if (data.event === 'scan_finished' && data.type !== 'deep_port_scan') {
            // Ignore generic finished events during deep scans to prevent overwrites
            console.log('[Scan Finished] Type:', data.type, 'Count:', data.count);
            this.showToast(`Scan complete: Found ${data.count} devices.`, 'success');
            this.updateScanProgress(100, `Scan finished.`);
            setTimeout(() => {
                const container = document.getElementById("scanProgressContainer");
                if (container) container.classList.add("hidden");
                this.fetchDevices();
                this.fetchSummary();
                this.fetchAISuggestions();
                this.fetchAISecurityScore();
            }, 2000);
        } else if (data.event === 'scan_error') {
            this.showToast(`Scan Error: ${data.message}`, 'risk');
            if (data.type === 'deep_port_scan') {
                const progress = document.getElementById('deepScanProgress');
                if (progress) progress.classList.add('hidden');
                this.updateDeepScanProgress(0, `Error: ${data.message}`);

                const statusBadge = document.getElementById('deepScanStatusBadge');
                if (statusBadge) {
                    statusBadge.textContent = 'FAILED';
                    statusBadge.className = 'badge status-risk';
                }

                const contentDiv = document.getElementById('deepScanContent');
                if (contentDiv) {
                    contentDiv.innerHTML = `<div style="text-align:center; padding: 40px; color: #ef4444;">
                        <i class="fa-solid fa-circle-exclamation" style="font-size: 24px; margin-bottom: 10px; display: block;"></i>
                        Scan failed: ${data.message}</div>`;
                }
            } else {
                const progress = document.getElementById('scanProgressContainer');
                if (progress) progress.classList.add('hidden');
                this.updateScanProgress(0, `Error: ${data.message}`);
            }
        }
    },

    updateScanProgress(progress, message) {
        const statusText = document.getElementById("scanStatusText");
        const progressBar = document.getElementById("scanProgressBar");
        if (statusText) statusText.textContent = message;
        if (progressBar) progressBar.style.width = `${progress}%`;
    },

    updateDeepScanProgress(progress, message) {
        const statusText = document.getElementById("deepScanPhase");
        const progressBar = document.getElementById("deepScanProgressBar");
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
            } catch (e) { }
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
            'dashboard':    ['IoT Security Auditor', 'Monitor and secure your connected smart home environment'],
            'devices':      ['Discovered Devices', 'Detailed list of all scanned networks and devices'],
            'rfid':         ['Access Control', 'Scan and manage RFID/NFC cards and key fobs'],
            'reports':      ['Security Reports', 'Generate and export security audit results'],
            'virtual-lab':  ['Virtual Lab', 'Simulated vulnerable IoT environment for hands-on penetration testing'],
        };

        if (titles[viewId]) {
            document.getElementById('pageTitle').textContent = titles[viewId][0];
            document.getElementById('pageSubtitle').textContent = titles[viewId][1];
        }

        // Initialize lab UI when switching to virtual-lab view
        if (viewId === 'virtual-lab' && window.lab) {
            lab.init();
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

         // Add RFID card count to RFID protocol
         protocolCounts['RFID'] += this.rfidCards?.length || 0;

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
        if (!tbody) {
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
        const riskColors = {
            'SAFE': 'var(--status-safe)',
            'MEDIUM': 'var(--status-medium)',
            'RISK': 'var(--status-risk)',
            'CRITICAL': '#c026d3',
        };
        badge.style.backgroundColor = riskColors[dev.risk_level] || 'var(--status-risk)';
        badge.style.color = '#fff';

        document.getElementById("detailVendor").textContent = dev.vendor;
        document.getElementById("detailOs").textContent = dev.os_guess;
        document.getElementById("detailPorts").textContent = dev.open_ports || "None";

        // ── Vulnerability grouping ────────────────────────────────
        const vulnList = document.getElementById("vulnList");
        vulnList.innerHTML = "";

        if (!dev.vulnerabilities || dev.vulnerabilities.length === 0) {
            vulnList.innerHTML = `<div style="text-align:center; color:var(--text-muted); padding: 20px;">No vulnerabilities found. Secure!</div>`;
            return;
        }

        // Category definitions — order controls display order
        const CATEGORIES = [
            {
                key: 'wireless',
                label: 'Wireless Security Findings',
                icon: 'fa-wifi',
                color: '#8b5cf6',
                match: v => ['WIRELESS_WEP_ENCRYPTION', 'WIRELESS_WPA1_ENCRYPTION', 'WIRELESS_OPEN_NETWORK',
                    'WIRELESS_DEAUTH_VULN', 'WIRELESS_ROGUE_AP_INDICATOR', 'WIRELESS_DEFAULT_SSID'].includes(v.vuln_type),
            },
            {
                key: 'ports',
                label: 'Open Ports',
                icon: 'fa-ethernet',
                color: '#3b82f6',
                match: v => v.port != null && !['IOT_UPNP_EXPOSED', 'IOT_MDNS_EXPOSED'].includes(v.vuln_type),
            },
            {
                key: 'service',
                label: 'Service Fingerprints',
                icon: 'fa-server',
                color: '#f59e0b',
                match: v => v.vuln_type.startsWith('SERVICE_'),
            },
            {
                key: 'iot',
                label: 'IoT Risks',
                icon: 'fa-microchip',
                color: '#ef4444',
                match: v => v.vuln_type.startsWith('IOT_'),
            },
            {
                key: 'other',
                label: 'Other Findings',
                icon: 'fa-shield-halved',
                color: '#64748b',
                match: () => true,   // catch-all
            },
        ];

        const sevOrder = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 };
        const sevColor = { CRITICAL: '#c026d3', HIGH: '#ef4444', MEDIUM: '#f59e0b', LOW: '#22c55e' };

        // Build recommendations from vuln_type lookup
        const remediationMap = {
            'SERVICE_TELNET_OPEN': 'Disable Telnet (port 23) and replace with SSH.',
            'SERVICE_FTP_OPEN': 'Disable FTP (port 21). Use SFTP/SCP instead.',
            'SERVICE_TFTP_OPEN': 'Disable TFTP (port 69) or restrict with ACLs.',
            'SERVICE_UNENCRYPTED_WEB_ADMIN': 'Enable HTTPS and redirect HTTP to HTTPS.',
            'SERVICE_ALT_HTTP_NO_HTTPS': 'Ensure alt HTTP port is HTTPS-protected.',
            'SERVICE_WEAK_SSH_BANNER': 'Update SSH server to a current OpenSSH release.',
            'SERVICE_CAPTIVE_PORTAL_MISC': 'Secure captive portal with HTTPS and short session timeouts.',
            'WIRELESS_WEP_ENCRYPTION': 'Replace WEP with WPA3 or WPA2-AES immediately.',
            'WIRELESS_WPA1_ENCRYPTION': 'Upgrade to WPA2-AES or WPA3.',
            'WIRELESS_OPEN_NETWORK': 'Enable WPA2/WPA3 encryption on this network.',
            'WIRELESS_DEAUTH_VULN': 'Enable 802.11w (PMF) on the access point.',
            'WIRELESS_ROGUE_AP_INDICATOR': 'Verify this AP is in your managed inventory.',
            'IOT_UPNP_EXPOSED': 'Disable UPnP/SSDP — it allows automatic NAT hole-punching.',
            'IOT_MDNS_EXPOSED': 'Restrict mDNS to local subnet only.',
            'IOT_MQTT_UNAUTHENTICATED': 'Enable MQTT authentication and TLS.',
            'IOT_COAP_UNSECURED': 'Implement DTLS for CoAP.',
            'IOT_DEFAULT_CRED_INDICATOR': 'Change default credentials immediately.',
            'IOT_TELNET_BOTNET_RISK': 'Disable Telnet on this IoT device immediately.',
            'IOT_RISKY_VENDOR_FINGERPRINT': 'Check vendor security advisories, update firmware.',
            'DEFAULT_CREDENTIALS': 'Change default credentials to a strong, unique password.',
            'OPEN_TELNET': 'Disable Telnet and use SSH for remote access.',
            'OPEN_FTP': 'Disable FTP and use SFTP/SCP for file transfers.',
        };

        const assigned = new Set();

        const renderGroup = (cat, vulns) => {
            if (vulns.length === 0) return '';
            const items = vulns
                .sort((a, b) => (sevOrder[a.severity] ?? 4) - (sevOrder[b.severity] ?? 4))
                .map(v => `
                    <div class="vuln-item ${v.severity.toLowerCase()}" style="
                        border-left: 3px solid ${sevColor[v.severity] || '#64748b'};
                        margin-bottom: 6px; padding: 8px 10px;
                        background: rgba(255,255,255,0.04); border-radius: 6px;">
                        <div class="vuln-header" style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                            <span class="vuln-type" style="font-size:11px; font-weight:600; font-family:monospace; color:${sevColor[v.severity] || '#fff'};">${v.vuln_type}</span>
                            <span style="font-size:10px; background:${sevColor[v.severity] || '#64748b'}22; color:${sevColor[v.severity] || '#94a3b8'}; padding:2px 6px; border-radius:4px; font-weight:600;">${v.severity}</span>
                        </div>
                        <div class="vuln-desc" style="font-size:11px; color:var(--text-muted);">${v.description}</div>
                        ${v.port ? `<div style="font-size:10px; color:#475569; margin-top:3px;"><i class="fa-solid fa-plug" style="font-size:9px;"></i> ${v.protocol || 'TCP'}:${v.port}</div>` : ''}
                    </div>`
                ).join('');

            return `
                <div class="vuln-group" style="margin-bottom: 14px;">
                    <div style="
                        display: flex; align-items: center; gap: 6px;
                        font-size: 11px; font-weight: 600; text-transform: uppercase;
                        letter-spacing: 0.08em; color: ${cat.color};
                        margin-bottom: 6px; padding-bottom: 4px;
                        border-bottom: 1px solid ${cat.color}33;">
                        <i class="fa-solid ${cat.icon}"></i> ${cat.label}
                        <span style="margin-left:auto; background:${cat.color}22; padding:1px 7px; border-radius:10px; font-size:10px;">${vulns.length}</span>
                    </div>
                    ${items}
                </div>`;
        };

        let html = '';

        CATEGORIES.forEach(cat => {
            const vulns = dev.vulnerabilities.filter(v => !assigned.has(v.vuln_type) && cat.match(v));
            vulns.forEach(v => assigned.add(v.vuln_type));
            html += renderGroup(cat, vulns);
        });

        // ── Recommendations section ───────────────────────────────
        const recs = dev.vulnerabilities
            .filter(v => remediationMap[v.vuln_type])
            .map(v => ({ type: v.vuln_type, severity: v.severity, action: remediationMap[v.vuln_type] }))
            .filter((r, i, arr) => arr.findIndex(x => x.action === r.action) === i); // deduplicate

        if (recs.length > 0) {
            const recItems = recs
                .sort((a, b) => (sevOrder[a.severity] ?? 4) - (sevOrder[b.severity] ?? 4))
                .map(r => `
                    <div style="display:flex; align-items:flex-start; gap:8px; margin-bottom:7px;
                                padding:7px 10px; background:rgba(34,197,94,0.06);
                                border-left:3px solid #22c55e33; border-radius:6px;">
                        <i class="fa-solid fa-lightbulb" style="color:#22c55e; font-size:12px; margin-top:2px; flex-shrink:0;"></i>
                        <div>
                            <div style="font-size:10px; font-family:monospace; color:#64748b; margin-bottom:2px;">${r.type}</div>
                            <div style="font-size:11px; color:var(--text-muted);">${r.action}</div>
                        </div>
                    </div>`
                ).join('');

            html += `
                <div class="vuln-group" style="margin-bottom:14px;">
                    <div style="
                        display:flex; align-items:center; gap:6px;
                        font-size:11px; font-weight:600; text-transform:uppercase;
                        letter-spacing:0.08em; color:#22c55e;
                        margin-bottom:6px; padding-bottom:4px;
                        border-bottom:1px solid #22c55e33;">
                        <i class="fa-solid fa-shield-check"></i> Recommendations
                        <span style="margin-left:auto; background:#22c55e22; padding:1px 7px; border-radius:10px; font-size:10px;">${recs.length}</span>
                    </div>
                    ${recItems}
                </div>`;
        }

        vulnList.innerHTML = html;
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

            let riskIcon = "";
            if (net.assessment_risks && net.assessment_risks.length > 0) {
                const maxSeverity = net.assessment_risks.some(r => r.severity === 'CRITICAL') ? 'var(--status-risk)' :
                    (net.assessment_risks.some(r => r.severity === 'HIGH') ? 'var(--status-risk)' : 'var(--status-medium)');
                const riskDesc = net.assessment_risks.map(r => r.desc).join(" | ");
                riskIcon = `<i class="fa-solid fa-triangle-exclamation" style="color: ${maxSeverity}; margin-left: 5px;" title="${riskDesc}"></i>`;
            }

            div.innerHTML = `
                <div style="display: flex; align-items: center; gap: 8px;">
                    <i class="fa-solid ${signalIcon}" style="color: ${signalColor}"></i>
                    <span style="font-weight: 500;">${net.ssid}</span>
                    ${riskIcon}
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
                setTimeout(() => progressContainer.classList.add("hidden"), 3000);
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
            const reqData = { method: "POST", headers: { "Content-Type": "application/json" } };
            if (body) reqData.body = body;

            const res = await authFetch(url, reqData);
            const data = await res.json();
            statusText.textContent = data.message;
            if (data.status === 'error') {
                setTimeout(() => progressContainer.classList.add("hidden"), 3000);
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
        try {
            await authFetch(`${API_BASE}/wireless/test/ports/${ip}`, { method: "POST" });
            alert(`Started Deep Port Scan on ${ip}`);
            setTimeout(() => this.fetchDevices(), 5000);
        } catch (e) {
            if (progress) progress.innerHTML = `<span style="color:var(--status-risk)">Error starting deep scan</span>`;
        }
    },

    updateDeepScanProgress(progress, message) {
        const progressBar = document.getElementById('deepScanProgressBar');
        const phaseText = document.getElementById('deepScanPhase');
        if (progressBar) progressBar.style.width = `${progress}%`;
        if (phaseText) phaseText.textContent = message;
    },

    async deepScanDevice() {
        if (!this.selectedDevice) return;
        const ip = this.selectedDevice.ip;
        if (ip.startsWith('ZW:') || ip.startsWith('BLE_') || ip.startsWith('ZB:')) {
            this.showToast(`Deep scan is only available for IP-based devices.`, 'info');
            return;
        }

        const resultsDiv = document.getElementById('deepScanResults');
        const progressDiv = document.getElementById('deepScanProgress');
        const contentDiv = document.getElementById('deepScanContent');
        const phaseText = document.getElementById('deepScanPhase');
        const progressBar = document.getElementById('deepScanProgressBar');

        const credPanel = document.getElementById('credTestPanel');
        if (credPanel) credPanel.classList.add('hidden');

        if (resultsDiv) resultsDiv.classList.remove('hidden');
        if (progressDiv) progressDiv.classList.remove('hidden');
        if (contentDiv) contentDiv.innerHTML = '';
        if (phaseText) phaseText.textContent = 'Initializing deep scan...';
        if (progressBar) progressBar.style.width = '0%';

        // Clear previous AI Analysis results
        const aiAnalysisDiv = document.getElementById('aiDeviceAnalysis');
        if (aiAnalysisDiv) aiAnalysisDiv.classList.add('hidden');
        const summaryText = document.getElementById('aiSummaryText');
        if (summaryText) summaryText.textContent = 'Analyzing scan data...';

        const ipEl = document.getElementById('deepScanIp');
        const vendorEl = document.getElementById('deepScanVendor');
        if (ipEl) ipEl.textContent = ip;
        if (vendorEl) vendorEl.textContent = this.selectedDevice.vendor || 'Detecting...';

        this.showToast(`Starting Deep Port Vulnerability Scan on ${ip}...`, 'info');

        try {
            await authFetch(`${API_BASE}/wireless/deep-scan/${ip}`, { method: 'POST' });
        } catch (e) {
            console.error('Deep scan error:', e);
            this.showToast('Failed to perform deep scan.', 'risk');
            if (progressDiv) progressDiv.classList.add('hidden');
        }
    },

    renderDeepScanCards(vulnerabilities, serviceBanners, openPorts = []) {
        const contentDiv = document.getElementById('deepScanContent');
        if (!contentDiv) return;

        contentDiv.innerHTML = '';

        if (!openPorts || openPorts.length === 0) {
            contentDiv.innerHTML = `
                <div style="text-align:center; padding: 40px; color: var(--text-muted);">
                    <i class="fa-solid fa-shield-check" style="font-size: 24px; color: #22c55e; display: block; margin-bottom: 10px;"></i>
                    No open ports detected. The target appears secure.
                </div>`;
            return;
        }

        // 1. Technical Port Audit Section
        const techSection = document.createElement('div');
        techSection.className = 'tech-audit-section';
        techSection.style.marginBottom = '20px';
        techSection.innerHTML = `
            <h3 style="font-size: 14px; color: var(--text-muted); margin-bottom: 12px; border-bottom: 1px solid var(--border-color); padding-bottom: 8px;">
                <i class="fa-solid fa-list-check"></i> TECHNICAL PORT AUDIT
            </h3>
            <div class="port-technical-table" style="background: rgba(0,0,0,0.2); border-radius: 8px; overflow: hidden;">
                <table style="width: 100%; border-collapse: collapse; font-size: 12px;">
                    <thead>
                        <tr style="background: rgba(255,255,255,0.05); text-align: left;">
                            <th style="padding: 10px; border-bottom: 1px solid var(--border-color);">PORT</th>
                            <th style="padding: 10px; border-bottom: 1px solid var(--border-color);">SERVICE / BANNER</th>
                            <th style="padding: 10px; border-bottom: 1px solid var(--border-color);">STATUS</th>
                            <th style="padding: 10px; border-bottom: 1px solid var(--border-color);">VULN</th>
                        </tr>
                    </thead>
                    <tbody id="techAuditBody"></tbody>
                </table>
            </div>
        `;
        contentDiv.appendChild(techSection);

        const body = techSection.querySelector('#techAuditBody');
        const sortedPorts = [...openPorts].sort((a, b) => a - b);

        sortedPorts.forEach(port => {
            const banner = serviceBanners && serviceBanners[port] ? serviceBanners[port] : 'Unknown Service';
            const vuln = vulnerabilities ? vulnerabilities.find(v => v.port == port) : null;
            const tr = document.createElement('tr');
            tr.style.borderBottom = '1px solid rgba(255,255,255,0.05)';

            tr.innerHTML = `
                <td style="padding: 10px; font-family: monospace; font-weight: bold; color: var(--accent-blue);">${port}/tcp</td>
                <td style="padding: 10px; color: var(--text-color);">${banner}</td>
                <td style="padding: 10px;"><span style="color: #22c55e;"><i class="fa-solid fa-circle-dot" style="font-size: 8px;"></i> OPEN</span></td>
                <td style="padding: 10px;">
                    ${vuln ? `<span style="color: var(--status-risk); font-weight: bold;"><i class="fa-solid fa-triangle-exclamation"></i> ${vuln.severity}</span>` : '<span style="color: #22c55e;">SAFE</span>'}
                </td>
            `;
            body.appendChild(tr);
        });

        // 2. Vulnerability Detail Section
        if (vulnerabilities && vulnerabilities.length > 0) {
            const vulnSection = document.createElement('div');
            vulnSection.innerHTML = `
                <h3 style="font-size: 14px; color: var(--status-risk); margin-top: 20px; margin-bottom: 12px; border-bottom: 1px solid rgba(239, 68, 68, 0.2); padding-bottom: 8px;">
                    <i class="fa-solid fa-bug"></i> DETECTED VULNERABILITIES
                </h3>
            `;
            contentDiv.appendChild(vulnSection);

            vulnerabilities.forEach(v => {
                const card = document.createElement('div');
                card.className = `vuln-item ${v.severity.toUpperCase()}`;

                let icon = 'fa-triangle-exclamation';
                if (v.severity === 'CRITICAL') icon = 'fa-skull-crossbones';
                if (v.severity === 'LOW') icon = 'fa-circle-info';

                card.innerHTML = `
                    <div class="vuln-header">
                        <span class="vuln-type"><i class="fa-solid ${icon}"></i> ${v.vuln_type}</span>
                        <span class="vuln-port badge ${v.severity.toLowerCase()}">${v.severity}</span>
                    </div>
                    <div class="vuln-desc">
                        <p><strong>Port:</strong> ${v.port} (${v.protocol || 'TCP'})</p>
                        <p>${v.description}</p>
                    </div>
                    ${v.remediation ? `<div class="vuln-remediation"><strong>Remediation:</strong> ${v.remediation}</div>` : ''}
                `;
                contentDiv.appendChild(card);
            });
        }
    },

    async testCreds() {
        if (!this.selectedDevice) return;

        // Check if device has a valid IP (not Z-Wave, BLE, etc.)
        const ip = this.selectedDevice.ip;
        if (ip.startsWith('ZW:') || ip.startsWith('BLE_') || ip.startsWith('ZB:')) {
            this.showToast(`Credential testing is not available for ${this.selectedDevice.protocol} devices.`, 'warning');
            return;
        }

        const dscan = document.getElementById('deepScanResults');
        if (dscan) dscan.classList.add('hidden');

        const pnl = document.getElementById('credTestPanel');
        if (pnl) {
            pnl.classList.remove('hidden');
            const logPanel = document.getElementById('credTestLogs');
            if (logPanel) logPanel.innerHTML = '<div class="terminal-line">Pentex One Credential Simulator</div>';
            const sumPanel = document.getElementById('credTestSummary');
            if (sumPanel) sumPanel.classList.add('hidden');
        }

        try {
            await authFetch(`${API_BASE}/wireless/test/credentials/${ip}`, { method: "POST" });
        } catch (e) {
            this.showToast("Error starting credentials test", "error");
        }
    },



    selectedRfidCard: null,

    async fetchCards() {
        try {
            const res = await authFetch(`${API_BASE}/rfid/vulnerability-report`);
            if (res.ok) {
                const data = await res.json();
                this.rfidCards = data.cards;
                this.renderRfidStats(data);
                this.renderCardsTable();
                this.renderVulnMatrix();
            }
        } catch (e) {
            console.error("Failed to load cards report");
        }
    },

    renderRfidStats(data) {
        if (document.getElementById("rfidTotalCards")) document.getElementById("rfidTotalCards").textContent = data.total_cards;
        if (document.getElementById("rfidSecureCards")) document.getElementById("rfidSecureCards").textContent = data.secure_cards;
        if (document.getElementById("rfidVulnCards")) document.getElementById("rfidVulnCards").textContent = data.vulnerable_cards;
        if (document.getElementById("rfidAvgRisk")) document.getElementById("rfidAvgRisk").textContent = data.average_risk_score.toFixed(1);
    },

    renderVulnMatrix() {
        const matrix = {
            'RFID_CLONING_ATTACK': { id: 'cloning', found: false },
            'RFID_UNAUTHORIZED_ACCESS': { id: 'unauth', found: false },
            'RFID_REPLAY_ATTACK': { id: 'replay', found: false },
            'RFID_EAVESDROPPING': { id: 'eavesdrop', found: false },
            'RFID_TAG_TAMPERING': { id: 'tamper', found: false }
        };

        this.rfidCards.forEach(card => {
            if (card.vulnerabilities_json) {
                try {
                    const vulns = JSON.parse(card.vulnerabilities_json);
                    vulns.forEach(v => {
                        if (matrix[v.vuln_type]) {
                            matrix[v.vuln_type].found = true;
                        }
                    });
                } catch (e) { }
            }
        });

        Object.values(matrix).forEach(v => {
            const ind = document.getElementById(`vi-${v.id}`);
            if (ind) {
                ind.className = `vuln-indicator ${v.found ? 'risk' : 'safe'}`;
            }
        });
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
            tr.className = "device-row rfid-card-row";
            if (this.selectedRfidCard && this.selectedRfidCard.id === c.id) {
                tr.classList.add("active");
            }

            tr.onclick = () => this.selectRfidCard(c.id);

            tr.innerHTML = `
                <td>
                    <div style="font-family:monospace; font-weight:bold">${c.uid}</div>
                    <div style="font-size:11px; color:var(--text-muted)">Seen: ${new Date(c.last_seen).toLocaleTimeString()}</div>
                </td>
                <td>
                    <div>${c.card_type}</div>
                    <div style="font-size:11px; color:var(--text-muted)"><i class="fa-solid fa-lock"></i> ${c.encryption_type || 'None'} | <i class="fa-solid fa-key"></i> ${c.auth_mode || 'UID-only'}</div>
                </td>
                <td><span class="badge ${c.risk_level.toLowerCase()}">${c.risk_level}</span></td>
                <td style="font-size: 11px; max-width: 200px;">${vulns}</td>
            `;
            tbody.appendChild(tr);
        });
    },

    selectRfidCard(id) {
        this.selectedRfidCard = this.rfidCards.find(c => c.id === id);
        this.renderCardsTable(); // Update active row
        this.renderRfidCardDetails();
    },

    renderRfidCardDetails() {
        const lastScanCard = document.getElementById("rfidLastScanCard");
        const rfidAttackPanel = document.getElementById("rfidAttackPanel");

        if (!this.selectedRfidCard) {
            if (lastScanCard) lastScanCard.classList.add("hidden");
            if (rfidAttackPanel) rfidAttackPanel.classList.add("hidden");
            return;
        }

        if (lastScanCard) lastScanCard.classList.remove("hidden");
        if (rfidAttackPanel) rfidAttackPanel.classList.remove("hidden");

        const c = this.selectedRfidCard;

        let vulns = [];
        try {
            vulns = JSON.parse(c.vulnerabilities_json || "[]");
        } catch (e) {
            console.error("Failed to parse vulnerabilities JSON", e);
        }

        const lastScanInfo = document.getElementById("rfidLastScanInfo");
        if (lastScanInfo) {
            lastScanInfo.innerHTML = `
                <div style="background: rgba(255,255,255,0.05); padding: 10px; border-radius: 6px;">
                    <span style="font-size: 10px; color: var(--text-muted); text-transform: uppercase;">UID</span><br>
                    <strong style="font-family: monospace; font-size: 14px;">${c.uid}</strong>
                </div>
                <div style="background: rgba(255,255,255,0.05); padding: 10px; border-radius: 6px;">
                    <span style="font-size: 10px; color: var(--text-muted); text-transform: uppercase;">Type</span><br>
                    <strong style="font-size: 14px;">${c.card_type}</strong>
                </div>
                <div style="background: rgba(255,255,255,0.05); padding: 10px; border-radius: 6px;">
                    <span style="font-size: 10px; color: var(--text-muted); text-transform: uppercase;">Encryption</span><br>
                    <strong style="font-size: 14px;">${c.encryption_type || "None"}</strong>
                </div>
                <div style="background: rgba(255,255,255,0.05); padding: 10px; border-radius: 6px;">
                    <span style="font-size: 10px; color: var(--text-muted); text-transform: uppercase;">Status</span><br>
                    <span class="status-badge ${c.risk_level.toLowerCase()}">${c.risk_level}</span>
                </div>
                <div style="background: rgba(255,255,255,0.05); padding: 10px; border-radius: 6px; grid-column: 1 / -1;">
                    <span style="font-size: 10px; color: var(--text-muted); text-transform: uppercase;">Vulnerabilities</span><br>
                    <div style="font-size: 13px; margin-top: 4px; color: ${vulns.length ? 'var(--status-risk)' : 'var(--status-safe)'}">
                        ${vulns.length ? vulns.map(v => `<i class="fa-solid fa-triangle-exclamation"></i> ${v.vuln_type}`).join('<br>') : '<i class="fa-solid fa-shield-check"></i> Secure - No known vulnerabilities'}
                    </div>
                </div>
            `;
        }

        const noAttackMsg = document.getElementById("rfidNoAttackMsg");
        const dynamicNav = document.getElementById("dynamicAttackNav");

        if (vulns.length === 0 || c.risk_level === 'SAFE') {
            if (noAttackMsg) noAttackMsg.classList.remove("hidden");
            if (dynamicNav) dynamicNav.classList.add("hidden");
        } else {
            if (noAttackMsg) noAttackMsg.classList.add("hidden");
            if (dynamicNav) {
                dynamicNav.classList.remove("hidden");
                dynamicNav.innerHTML = '';

                // Restore all 5 attack modules as requested
                const possibleAttacks = new Set();
                possibleAttacks.add('Clone');
                possibleAttacks.add('Replay');
                possibleAttacks.add('Eavesdropping');
                possibleAttacks.add('Tampering');
                possibleAttacks.add('Impersonation');

                // Fallback: if vulnerable but no specific attacks matched, allow Clone/Replay
                if (possibleAttacks.size === 0) {
                    possibleAttacks.add('Clone');
                    possibleAttacks.add('Replay');
                }

                possibleAttacks.forEach(attack => {
                    const btn = document.createElement("button");
                    btn.className = "attack-nav-btn";
                    btn.id = `atk-${attack}`;
                    btn.textContent = attack;
                    btn.onclick = () => this.simulateAttack(attack);
                    dynamicNav.appendChild(btn);
                });

                this.updateSimulationUI(); // Enforce simulation mode toggle states
            }
        }
    },

    async scanRfid() {
        await this._doScan(`${API_BASE}/rfid/scan`);
    },

    async deepScanRfid() {
        await this._doScan(`${API_BASE}/rfid/scan/deep`);
    },

    async _doScan(url) {
        if (!this.simulationMode) {
            this.showToast('Enable Simulation Mode first', 'warning');
            const status = document.getElementById("rfidStatus");
            if (status) {
                status.innerHTML = '<i class="fa-solid fa-lock"></i> Enable Simulation Mode first';
                status.style.color = "var(--status-risk)";
            }
            return;
        }
        const status = document.getElementById("rfidStatus");
        if (status) {
            status.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Scanning...';
            status.style.color = "var(--text-muted)";
        }
        try {
            const res = await authFetch(url, { method: "POST" });
            const data = await res.json();
            if (data.status === 'error') {
                status.innerHTML = `<i class="fa-solid fa-circle-xmark"></i> ${data.message}`;
                status.style.color = "var(--status-risk)";
            } else {
                const simBadge = data.simulated ? ' <span style="background:var(--accent-purple);color:#fff;padding:2px 6px;border-radius:4px;font-size:10px;margin-left:4px;">SIM</span>' : '';
                const msg = data.card ? `Card scanned: ${data.card.uid}` : "Card scanned successfully";
                status.innerHTML = `<i class="fa-solid fa-circle-check"></i> ${msg}${simBadge}`;
                status.style.color = "var(--status-safe)";
            }
            await this.fetchCards();
            await this.fetchRfidReports();
            if (data.status === 'success' && this.rfidCards.length > 0) {
                this.selectRfidCard(this.rfidCards[0].id);
            }
        } catch (e) {
            console.error("Scan error:", e);
            status.innerHTML = '<i class="fa-solid fa-circle-xmark"></i> Error scanning card.';
            status.style.color = "var(--status-risk)";
        }
    },

    async simulateAttack(attackType) {
        if (!this.selectedRfidCard) {
            this.showToast('Please scan a card first', 'warning');
            return;
        }

        const logPanel = document.getElementById('attackConsoleLogs');
        const remPanel = document.getElementById('attackResultSummary');

        if (logPanel) logPanel.innerHTML = '<div class="terminal-line">Initializing Attack: ' + attackType + '...</div>';
        if (remPanel) remPanel.classList.add('hidden');

        // Nav highlighting
        document.querySelectorAll('.attack-nav-btn').forEach(btn => btn.classList.remove('active'));
        const activeBtn = document.getElementById(`atk-${attackType}`);
        if (activeBtn) activeBtn.classList.add('active');

        try {
            const res = await authFetch(`${API_BASE}/rfid/attack/simulate-stream`, {
                method: 'POST',
                body: JSON.stringify({
                    attack_type: attackType,
                    target_uid: this.selectedRfidCard.uid
                })
            });
            const data = await res.json();
            if (data.status === 'started') {
                this.showToast(`${attackType} attack simulation started...`, 'info');
            }
        } catch (e) {
            this.showToast(`Error starting attack: ${e.message}`, 'risk');
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
            this.selectedRfidCard = null;
            this.fetchCards();
            this.renderRfidCardDetails();
        } catch (e) { }
    },

    async fetchRfidReports() {
        try {
            const res = await authFetch(`${API_BASE}/rfid/reports`);
            if (!res.ok) return;
            const data = await res.json();
            const tbody = document.getElementById('rfidReportsTableBody');
            if (!tbody) return;
            tbody.innerHTML = '';
            const reports = Array.isArray(data) ? data : (data.reports || []);
            if (reports.length === 0) {
                tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color:var(--text-muted)">No reports yet.</td></tr>`;
                return;
            }
            const sevColor = { CRITICAL: '#c026d3', HIGH: '#ef4444', MEDIUM: '#f59e0b', LOW: '#22c55e', SAFE: '#22c55e' };
            reports.forEach(r => {
                const eventLabel = r.attack_type ? `${r.attack_type} Attack` : 'RFID Scan';
                const resultText = r.attack_result || (r.vulnerabilities ? `${JSON.parse(r.vulnerabilities).length} findings` : '-');
                const statusText = r.attack_result ? (r.attack_result.includes('Success') ? 'Vulnerable' : 'Secure') : (r.simulation_status || 'Saved');
                const statusColor = r.attack_result ? (r.attack_result.includes('Success') ? '#ef4444' : '#22c55e') : '#3b82f6';

                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td style="font-size:11px; font-family:monospace; color:var(--text-muted)">${new Date(r.timestamp || r.created_at).toLocaleString()}</td>
                    <td style="font-family:monospace; font-weight:600">${r.uid || r.card_uid || '-'}</td>
                    <td>${r.card_type || '-'}</td>
                    <td><span style="padding:2px 8px; border-radius:4px; font-size:11px; background:rgba(59,130,246,0.1); color:#3b82f6">${eventLabel}</span></td>
                    <td style="font-size:12px; color:var(--text-muted)">${resultText}</td>
                    <td style="font-size:11px; color:var(--text-muted)">${r.remediation || '-'}</td>
                    <td><span style="color:${sevColor[r.risk_level] || '#94a3b8'}; font-weight:600">${r.risk_level || '-'}</span></td>
                    <td><span style="font-size:11px; padding:2px 6px; border-radius:4px; background:rgba(255,255,255,0.06); color:${statusColor}">${statusText}</span></td>
                `;
                tbody.appendChild(tr);
            });
        } catch (e) {
            console.error('Failed to load RFID reports', e);
        }
    },

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
        a.download = `pentexone_scan_${new Date().toISOString().slice(0, 10)}.json`;
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
        a.download = `pentexone_devices_${new Date().toISOString().slice(0, 10)}.csv`;
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

                // Clear State
                this.devices = [];
                this.rfidCards = [];
                this.selectedDevice = null;
                this.selectedRfidCard = null;

                // Reset UI
                this.renderDevicesTable();
                this.renderCardsTable();
                this.renderDeviceDetails();
                this.renderRfidCardDetails();
                this.fetchSummary();
                this.updateProtocolChart();
                this.fetchAISuggestions();
                this.fetchAISecurityScore();

                // Hide results panels
                const deepRes = document.getElementById('deepScanResults');
                if (deepRes) deepRes.classList.add('hidden');
                const aiRes = document.getElementById('aiDeviceAnalysis');
                if (aiRes) aiRes.classList.add('hidden');

                this.showToast('All system data cleared successfully', 'success');
            } catch (e) {
                console.error(e);
                this.showToast("Failed to clear data.", 'risk');
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

    renderAIAnalysis(analysis) {
        const analysisDiv = document.getElementById('aiDeviceAnalysis');
        const deviceTypeDiv = document.getElementById('aiDeviceType');
        const summaryDiv = document.getElementById('aiDynamicSummary');
        const predictedVulnsDiv = document.getElementById('aiPredictedVulns');

        if (!analysisDiv) return;

        analysisDiv.classList.remove('hidden');

        // Device type
        if (deviceTypeDiv) {
            deviceTypeDiv.innerHTML = `
                <strong>Device Type:</strong> ${analysis.device_type.replace('_pattern', '').replace('_', ' ').toUpperCase()}
                <span style="margin-left: 10px; opacity: 0.7;">Confidence: ${Math.round(analysis.confidence * 100)}%</span>
            `;
        }

        // Dynamic Summary
        if (summaryDiv && analysis.dynamic_summary) {
            summaryDiv.innerHTML = `<i class="fa-solid fa-quote-left" style="opacity:0.3; margin-right:8px;"></i>${analysis.dynamic_summary}`;
        }

        // Predicted vulnerabilities
        if (predictedVulnsDiv) {
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
        }

        if (analysis.is_anomaly) {
            this.showToast('Anomaly detected! Device behavior is unusual.', 'warning');
        }
    },

    async analyzeDeviceAI() {
        if (!this.selectedDevice) return;

        const btn = document.querySelector('.ai-analysis-btn[onclick="app.analyzeDeviceAI()"]');
        const originalText = btn ? btn.innerHTML : '';
        if (btn) {
            btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Processing AI Analysis...';
            btn.disabled = true;
        }

        try {
            const res = await authFetch(`${API_BASE}/ai/analyze/device/${this.selectedDevice.id}`);
            if (res.ok) {
                const data = await res.json();
                this.renderAIAnalysis(data.analysis);
                this.showToast('AI analysis completed successfully', 'success');
            } else {
                this.showToast('Failed to process AI analysis', 'risk');
            }
        } catch (e) {
            console.error('AI analysis failed', e);
            this.showToast('Failed to process AI analysis', 'risk');
        } finally {
            if (btn) {
                btn.innerHTML = originalText;
                btn.disabled = false;
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

    async analyzeRfidAI() {
        if (!this.selectedRfidCard) {
            this.showToast('Please scan a card first', 'warning');
            return;
        }

        const btn = document.querySelector('.ai-analysis-btn[onclick="app.analyzeRfidAI()"]');
        const originalText = btn ? btn.innerHTML : '';
        if (btn) {
            btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Processing AI Analysis...';
            btn.disabled = true;
        }

        try {
            const res = await authFetch(`${API_BASE}/rfid/analyze/${this.selectedRfidCard.id}`);
            if (res.ok) {
                const data = await res.json();
                const analysis = data.analysis;

                // Show result in a modal or append to the summary
                const remPanel = document.getElementById('attackResultSummary');
                if (remPanel) {
                    remPanel.classList.remove('hidden');

                    let insightsHtml = '';
                    if (analysis.insights && analysis.insights.length > 0) {
                        insightsHtml = `
                            <strong style="color: var(--accent-blue); display: block; margin-top: 10px; margin-bottom: 5px;">
                                <i class="fa-solid fa-microchip"></i> Architectural Insights:
                            </strong>
                            <ul style="margin: 0; padding-left: 20px; font-size: 12px; color: var(--text-muted);">
                                ${analysis.insights.map(i => `<li style="margin-bottom: 4px;">${i}</li>`).join('')}
                            </ul>
                        `;
                    }

                    remPanel.innerHTML = `
                        <div style="background: rgba(124, 58, 237, 0.1); padding: 16px; border-radius: 8px; border-left: 4px solid var(--accent-purple);">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                                <h3 style="margin: 0; color: var(--accent-purple); font-size: 14px;">
                                    <i class="fa-solid fa-brain"></i> AI Security Report
                                </h3>
                                <span class="status-badge ${analysis.risk_level.toLowerCase()}">${analysis.risk_level}</span>
                            </div>
                            
                            <div style="font-size: 13px; line-height: 1.6;">
                                <div style="margin-bottom: 8px;">
                                    <strong style="color: var(--text-muted);">Target Profile:</strong> ${analysis.card_type}
                                </div>
                                
                                ${insightsHtml}

                                <strong style="color: #22c55e; display: block; margin-top: 12px; margin-bottom: 5px;">
                                    <i class="fa-solid fa-shield-halved"></i> Strategic Recommendation:
                                </strong>
                                <div style="font-size: 12px; color: var(--text-muted);">
                                    ${analysis.recommendation}
                                </div>
                            </div>
                        </div>
                    `;
                }
                this.showToast('AI analysis completed successfully', 'success');
            } else {
                this.showToast('Failed to process AI analysis', 'risk');
            }
        } catch (e) {
            console.error('RFID AI analysis failed', e);
            this.showToast('Failed to process AI analysis', 'risk');
        } finally {
            if (btn) {
                btn.innerHTML = originalText;
                btn.disabled = false;
            }
        }
    }
};

// Start App
document.addEventListener("DOMContentLoaded", () => {
    app.init();
});
