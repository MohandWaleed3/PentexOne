const API_BASE = window.location.origin;

const app = {
    devices: [],
    selectedDevice: null,
    scanInterval: null,
    rfidCards: [],

    riskChart: null,

    init() {
        this.fetchSummary();
        this.fetchDevices();
        this.fetchCards();
        this.fetchSettings();
        this.initChart();
        
        // Refresh summary every 10 seconds
        setInterval(() => this.fetchSummary(), 10000);
    },

    initChart() {
        const ctx = document.getElementById('riskPieChart').getContext('2d');
        if (!ctx) return;
        this.riskChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Safe', 'Medium', 'Risk'],
                datasets: [{
                    data: [0, 0, 0],
                    backgroundColor: ['#22c55e', '#f59e0b', '#ef4444'],
                    borderWidth: 0,
                    hoverOffset: 4
                }]
            },
            options: {
                cutout: '70%',
                plugins: {
                    legend: { display: false }
                },
                responsive: true,
                maintainAspectRatio: false
            }
        });
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
            const res = await fetch(`${API_BASE}/settings`);
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
            await fetch(`${API_BASE}/settings`, {
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
            const res = await fetch(`${API_BASE}/reports/summary`);
            if (res.ok) {
                const data = await res.json();
                const oldRiskEl = document.getElementById("sRisk");
                const oldRisk = oldRiskEl ? parseInt(oldRiskEl.textContent) || 0 : 0;
                
                if (document.getElementById("sTotal")) document.getElementById("sTotal").textContent = data.total_devices;
                if (document.getElementById("sSafe")) document.getElementById("sSafe").textContent = data.safe_count;
                if (document.getElementById("sMedium")) document.getElementById("sMedium").textContent = data.medium_count;
                if (document.getElementById("sRisk")) document.getElementById("sRisk").textContent = data.risk_count;

                // Update Chart
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

    async fetchDevices() {
        try {
            const res = await fetch(`${API_BASE}/iot/devices`);
            if (res.ok) {
                this.devices = await res.json();
                this.renderDevicesTable();
            }
        } catch (e) {
            console.error("Failed to fetch devices", e);
        }
    },

    renderDevicesTable() {
        const tbody = document.getElementById("devicesTableBody");
        if(!tbody) return;
        tbody.innerHTML = "";

        if (this.devices.length === 0) {
            const tr = document.createElement("tr");
            tr.innerHTML = `<td colspan="4" style="text-align:center; color:var(--text-muted)">No devices discovered yet.</td>`;
            tbody.appendChild(tr);
            return;
        }

        this.devices.forEach(device => {
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
                <td><div style="font-family:monospace">${device.ip}</div><div style="font-size:11px; color:var(--text-muted)">${device.mac}</div></td>
                <td><div>${device.hostname}</div><div style="font-size:11px; color:var(--text-muted)">${device.vendor}</div></td>
                <td><span class="badge ${device.risk_level.toLowerCase()}">${device.risk_level}</span></td>
            `;
            tbody.appendChild(tr);
        });
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

    async startScan(type) {
        const progressContainer = document.getElementById("scanProgressContainer");
        const statusText = document.getElementById("scanStatusText");
        const progressBar = document.getElementById("scanProgressBar");
        
        progressContainer.classList.remove("hidden");
        progressBar.style.width = "0%";
        
        let url = "";
        let body = null;

        if (type === 'wifi') {
            const network = document.getElementById("networkInput").value;
            url = `${API_BASE}/iot/scan/wifi`;
            body = JSON.stringify({ network: network, timeout: 60 });
        } else if (type === 'matter') {
            url = `${API_BASE}/iot/scan/matter`;
        } else if (type === 'zigbee') {
            url = `${API_BASE}/iot/scan/zigbee`;
        } else if (type === 'bluetooth') {
            url = `${API_BASE}/wireless/scan/bluetooth`;
        }

        try {
            const reqData = { method: "POST", headers: {"Content-Type": "application/json"} };
            if (body) reqData.body = body;
            
            const res = await fetch(url, reqData);
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
            const res = await fetch(`${API_BASE}/iot/scan/status`);
            const data = await res.json();
            
            document.getElementById("scanStatusText").textContent = data.message;
            if (data.progress > 0) {
                document.getElementById("scanProgressBar").style.width = `${data.progress}%`;
            }

            if (!data.running) {
                clearInterval(this.scanInterval);
                document.getElementById("scanProgressBar").style.width = `100%`;
                setTimeout(() => {
                    document.getElementById("scanProgressContainer").classList.add("hidden");
                    this.fetchDevices();
                    this.fetchSummary();
                }, 3000);
            }
        } catch (e) {
            console.error("Polling error", e);
        }
    },

    async testPorts() {
        if (!this.selectedDevice) return;
        try {
            await fetch(`${API_BASE}/wireless/test/ports/${this.selectedDevice.ip}`, { method: "POST" });
            alert(`Started Deep Port Scan on ${this.selectedDevice.ip}`);
            setTimeout(() => this.fetchDevices(), 5000); // Check results after a bit
        } catch (e) {
            alert("Error starting port scan");
        }
    },

    async testCreds() {
        if (!this.selectedDevice) return;
        try {
            await fetch(`${API_BASE}/wireless/test/credentials/${this.selectedDevice.ip}`, { method: "POST" });
            alert(`Started Default Credentials Test on ${this.selectedDevice.ip}`);
            setTimeout(() => this.fetchDevices(), 5000);
        } catch (e) {
            alert("Error starting credentials test");
        }
    },

    // ======== RFID LOGIC ========
    async fetchCards() {
        try {
            const res = await fetch(`${API_BASE}/rfid/cards`);
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
            const res = await fetch(`${API_BASE}/rfid/scan`, { method: "POST" });
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
            await fetch(`${API_BASE}/rfid/cards`, { method: "DELETE" });
            this.fetchCards();
        } catch(e) { }
    },
    // ============================

    async downloadReport() {
        window.open(`${API_BASE}/reports/generate/pdf`, "_blank");
    },

    async clearData() {
        if (confirm("Are you sure you want to clear all discovered devices, RFID cards, and vulnerabilities?")) {
            try {
                await fetch(`${API_BASE}/iot/devices`, { method: "DELETE" });
                await fetch(`${API_BASE}/rfid/cards`, { method: "DELETE" });
                this.devices = [];
                this.rfidCards = [];
                this.selectedDevice = null;
                this.renderDevicesTable();
                this.renderCardsTable();
                this.renderDeviceDetails();
                this.fetchSummary();
            } catch (e) {
                console.error(e);
                alert("Failed to clear data.");
            }
        }
    }
};

// Start App
document.addEventListener("DOMContentLoaded", () => {
    app.init();
});
