/**
 * PentexOne — Virtual Lab UI Controller
 * Handles all interactions for the Virtual Lab view:
 *   - Lab start/stop control
 *   - Network architecture display
 *   - Attack scenario execution
 *   - Tutorial
 *   - Activity log
 */

const lab = (function () {

  const API = '';   // same origin
  let _statusTimer  = null;
  let _activityTimer = null;
  let _activeScenarioId = null;
  let _allScenarios = [];
  let _protocolFilter = 'all';
  let _difficultyFilter = 'all';

  // ─── Helpers ────────────────────────────────────────────────────────────────

  async function api(method, path, body) {
    const opts = { method, headers: {} };
    if (body) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    }
    const r = await fetch(API + path, opts);
    return r.json();
  }

  function el(id) { return document.getElementById(id); }

  function setDot(dotId, status) {
    const d = el(dotId);
    if (!d) return;
    d.className = 'lab-status-dot ' + (status || 'stopped');
    d.title = status || 'stopped';
  }

  function formatUptime(secs) {
    if (!secs) return '—';
    if (secs < 60) return secs + 's';
    if (secs < 3600) return Math.floor(secs / 60) + 'm ' + (secs % 60) + 's';
    return Math.floor(secs / 3600) + 'h ' + Math.floor((secs % 3600) / 60) + 'm';
  }

  function difficultyBadge(d) {
    const cls = { easy: 'badge-easy', medium: 'badge-medium', hard: 'badge-hard' };
    return `<span class="difficulty-badge ${cls[d] || ''}">${(d||'').toUpperCase()}</span>`;
  }

  function protocolIcon(p) {
    if (!p) return '<i class="fa-solid fa-question"></i>';
    const l = p.toLowerCase();
    if (l.includes('ble'))   return '<i class="fa-brands fa-bluetooth-b" style="color:#60a5fa;"></i>';
    if (l.includes('http'))  return '<i class="fa-solid fa-globe" style="color:#34d399;"></i>';
    if (l.includes('tcp'))   return '<i class="fa-solid fa-network-wired" style="color:#f59e0b;"></i>';
    return '<i class="fa-solid fa-wifi"></i>';
  }

  function confirmDialog({title, message, confirmText, cancelText, danger}) {
    return new Promise(resolve => {
      const overlay = el('confirmDialog');
      const titleEl   = el('confirmDialogTitle');
      const msgEl     = el('confirmDialogMessage');
      const confirmBtn = el('confirmDialogConfirm');
      const cancelBtn  = el('confirmDialogCancel');
      const iconEl     = el('confirmDialogIcon');
      if (!overlay) { resolve(window.confirm(message || title || 'Confirm?')); return; }

      titleEl.textContent   = title || 'Are you sure?';
      msgEl.textContent     = message || 'This action cannot be undone.';
      confirmBtn.textContent = confirmText || 'Confirm';
      cancelBtn.textContent  = cancelText  || 'Cancel';
      confirmBtn.className   = 'btn btn-sm ' + (danger ? 'btn-danger' : 'btn-primary');
      iconEl.className       = 'confirm-dialog-icon ' + (danger ? 'danger' : 'warn');

      const cleanup = (result) => {
        overlay.classList.add('hidden');
        confirmBtn.onclick = null;
        cancelBtn.onclick = null;
        overlay.onclick = null;
        resolve(result);
      };
      confirmBtn.onclick = () => cleanup(true);
      cancelBtn.onclick  = () => cleanup(false);
      overlay.onclick = (e) => { if (e.target === overlay) cleanup(false); };
      overlay.classList.remove('hidden');
      confirmBtn.focus();
    });
  }

  function toast(msg, type) {
    if (window.app && app.showToast) { app.showToast(msg, type); return; }
    const t = document.createElement('div');
    t.style.cssText = 'background:#1e293b;color:#e2e8f0;padding:10px 16px;border-radius:8px;font-size:13px;border-left:3px solid '+(type==='error'?'#ef4444':'#22c55e');
    t.textContent = msg;
    el('toastContainer').appendChild(t);
    setTimeout(() => t.remove(), 3000);
  }

  // ─── Lab Status ─────────────────────────────────────────────────────────────

  async function fetchStatus() {
    try {
      const d = await api('GET', '/lab/status');
      const wifi = d.wifi_lab || {};
      const ble  = d.ble_lab  || {};

      setDot('wifiLabDot', wifi.status);
      setDot('bleLabDot',  ble.status);

      const wifiBtn = el('wifiStatusLabel');
      const bleBtn  = el('bleStatusLabel');
      if (wifiBtn) wifiBtn.textContent = (wifi.status || 'stopped').toUpperCase();
      if (bleBtn)  bleBtn.textContent  = (ble.status  || 'stopped').toUpperCase();

      const wifiUp = el('wifiUptime');
      const bleUp  = el('bleUptime');
      if (wifiUp) wifiUp.textContent = wifi.status === 'running' ? formatUptime(wifi.uptime_seconds) : '—';
      if (bleUp)  bleUp.textContent  = ble.status  === 'running' ? formatUptime(ble.uptime_seconds)  : '—';

      const overall = el('overallLabStatus');
      if (overall) {
        const icons = { running:'fa-circle-check', stopped:'fa-circle-xmark', error:'fa-circle-exclamation', starting:'fa-spinner fa-spin', stopping:'fa-spinner fa-spin' };
        const colors = { running:'#22c55e', stopped:'#6b7280', error:'#ef4444', starting:'#f59e0b', stopping:'#f59e0b' };
        const s = d.overall || 'stopped';
        overall.innerHTML = `<i class="fa-solid ${icons[s]||'fa-circle'}" style="color:${colors[s]||'#6b7280'};"></i> ${s.toUpperCase()}`;
      }
    } catch (_) {}
  }

  // ─── Start / Stop ────────────────────────────────────────────────────────────

  async function startAll() {
    toast('Starting Wi-Fi + BLE lab…', 'info');
    const r = await api('POST', '/lab/start');
    toast(r.wifi_lab?.message || r.message || 'Started', 'success');
    fetchStatus();
    fetchStats();
  }

  async function stopAll() {
    const ok = await confirmDialog({
      title: 'Stop the lab?',
      message: 'This will shut down all Wi-Fi containers and the BLE simulator. Running attacks will no longer reach their targets.',
      confirmText: 'Stop Lab',
      cancelText: 'Keep Running',
      danger: true,
    });
    if (!ok) return;
    toast('Stopping lab…', 'info');
    await api('POST', '/lab/stop');
    toast('Lab stopped', 'success');
    fetchStatus();
    fetchStats();
  }

  async function startComponent(c) {
    toast(`Starting ${c.toUpperCase()} lab…`, 'info');
    const r = await api('POST', `/lab/start?component=${c}`);
    toast(r.message || 'Started', 'success');
    fetchStatus();
    fetchStats();
  }

  async function stopComponent(c) {
    toast(`Stopping ${c.toUpperCase()} lab…`, 'info');
    await api('POST', `/lab/stop?component=${c}`);
    toast('Stopped', 'success');
    fetchStatus();
    fetchStats();
  }

  // ─── Quick Inject ────────────────────────────────────────────────────────────

  function refreshAppDashboard() {
    if (!window.app) return;
    if (app.fetchDevices)          app.fetchDevices();
    if (app.fetchSummary)          app.fetchSummary();
    if (app.fetchAISecurityScore)  app.fetchAISecurityScore();
  }

  async function quickScan() {
    toast('Discovering Wi-Fi lab devices…', 'info');
    const r = await api('POST', '/lab/quick-scan');
    toast(r.message || 'Done', r.ok === false ? 'error' : 'success');
    fetchStats();
    refreshAppDashboard();
  }

  async function bleInject() {
    toast('Discovering BLE lab devices…', 'info');
    const r = await api('POST', '/lab/ble-inject');
    toast(r.message || 'Done', r.ok === false ? 'error' : 'success');
    fetchStats();
    refreshAppDashboard();
  }

  async function resetLab() {
    const ok = await confirmDialog({
      title: 'Clear all lab devices?',
      message: 'This removes every [LAB] device and its vulnerabilities from the database. You can re-add them with "Quick Discovery".',
      confirmText: 'Clear Devices',
      cancelText: 'Keep Devices',
      danger: true,
    });
    if (!ok) return;
    const r = await api('POST', '/lab/reset');
    toast(r.message || 'Reset done', 'success');
    fetchStats();
    refreshAppDashboard();
  }

  // ─── Network Architecture ────────────────────────────────────────────────────

  async function fetchArchitecture() {
    const grid = el('subnetGrid');
    if (!grid) return;
    try {
      const d = await api('GET', '/lab/info');
      if (!d.ok) return;
      const subnets = d.lab.subnets;
      const subnetMeta = {
        iot:       { icon: '🔵', label: 'IoT Subnet',    color: '#00B4D8' },
        guest:     { icon: '🟡', label: 'Guest Network',  color: '#FFC24D' },
        corporate: { icon: '🔴', label: 'Corporate LAN',  color: '#FF5C5C' },
      };
      grid.innerHTML = Object.entries(subnets).map(([key, subnet]) => {
        const m = subnetMeta[key] || {};
        const devRows = (subnet.devices || []).map(dev =>
          `<div class="subnet-device-row">
            <span class="subnet-device-name">${dev.hostname}</span>
            <span class="subnet-device-ip">${dev.ip || ''}</span>
            <span class="subnet-vuln-count">${dev.vuln_count} vulns</span>
           </div>`
        ).join('');
        return `
          <div class="subnet-card" style="border-top:3px solid ${m.color||'#444'}">
            <div class="subnet-card-header">
              <span class="subnet-icon">${m.icon||'⚪'}</span>
              <div>
                <div class="subnet-card-title">${subnet.name || key}</div>
                <div class="subnet-card-cidr">${subnet.cidr || ''}</div>
              </div>
              <span class="subnet-device-count">${subnet.device_count} devices</span>
            </div>
            <div class="subnet-devices">${devRows}</div>
          </div>`;
      }).join('');
    } catch (_) {
      grid.innerHTML = emptyState({
        icon: 'fa-plug-circle-xmark', iconColor: '#ef4444',
        title: 'Network architecture unavailable',
        message: 'Could not reach the backend to load the subnet map.',
        actionLabel: 'Retry', actionFn: 'lab.fetchArchitecture()',
      });
    }
  }

  // ─── BLE Devices ────────────────────────────────────────────────────────────

  async function fetchBleDevices() {
    const grid = el('bleDeviceGrid');
    if (!grid) return;
    try {
      const d = await api('GET', '/lab/ble-devices');
      if (!d.ok || !d.devices) return;
      const riskColor = { CRITICAL:'#ef4444', HIGH:'#f97316', MEDIUM:'#f59e0b', SAFE:'#22c55e' };
      grid.innerHTML = d.devices.map(dev => `
        <div class="ble-device-card">
          <div class="ble-device-header">
            <i class="fa-brands fa-bluetooth-b" style="color:#60a5fa;font-size:18px;"></i>
            <div class="ble-device-info">
              <div class="ble-device-name">${dev.name}</div>
              <div class="ble-device-addr">${dev.address}</div>
            </div>
            <span class="risk-pill" style="background:${riskColor[dev.risk_level]||'#6b7280'}22;color:${riskColor[dev.risk_level]||'#9ca3af'};border:1px solid ${riskColor[dev.risk_level]||'#6b7280'}44">
              ${dev.risk_level}
            </span>
          </div>
          <div class="ble-device-desc">${dev.description}</div>
          <div class="ble-device-vulns">
            ${(dev.vulnerabilities||[]).map(v=>`<span class="vuln-tag">${v}</span>`).join('')}
          </div>
        </div>`
      ).join('');
    } catch (_) {}
  }

  // ─── Attack Scenarios ────────────────────────────────────────────────────────

  async function fetchScenarios() {
    const list = el('scenarioList');
    try {
      const d = await api('GET', '/attacks/');
      if (!d.ok) {
        if (list) list.innerHTML = emptyState({
          icon: 'fa-circle-xmark', iconColor: '#ef4444',
          title: 'Could not load attack scenarios',
          message: d.detail || 'The backend returned an unexpected response.',
          actionLabel: 'Retry', actionFn: 'lab.fetchScenarios()',
        });
        return;
      }
      _allScenarios = d.scenarios || [];
      renderScenarioList();
    } catch (e) {
      if (list) list.innerHTML = emptyState({
        icon: 'fa-plug-circle-xmark', iconColor: '#ef4444',
        title: 'Cannot reach the backend',
        message: 'Make sure the PentexOne backend is running on port 8000.',
        actionLabel: 'Retry', actionFn: 'lab.fetchScenarios()',
      });
    }
  }

  function emptyState({icon, iconColor, title, message, actionLabel, actionFn, secondaryLabel, secondaryFn}) {
    return `
      <div class="empty-state">
        <div class="empty-state-icon" style="color:${iconColor||'#60a5fa'};">
          <i class="fa-solid ${icon||'fa-circle-info'}"></i>
        </div>
        <div class="empty-state-title">${escHtml(title||'')}</div>
        <div class="empty-state-message">${escHtml(message||'')}</div>
        <div class="empty-state-actions">
          ${actionLabel ? `<button class="btn btn-primary btn-sm" onclick="${actionFn}"><i class="fa-solid fa-arrow-right"></i> ${escHtml(actionLabel)}</button>` : ''}
          ${secondaryLabel ? `<button class="btn btn-text btn-sm" onclick="${secondaryFn}">${escHtml(secondaryLabel)}</button>` : ''}
        </div>
      </div>`;
  }

  function filterScenarios(group, value) {
    if (group === 'protocol')        _protocolFilter   = value;
    else if (group === 'difficulty') _difficultyFilter = value;

    const bar = document.querySelector(`.scenario-filter-bar[data-group="${group}"]`);
    if (bar) {
      bar.querySelectorAll('.scenario-filter-btn').forEach(b => b.classList.remove('active'));
      const btn = bar.querySelector(`.scenario-filter-btn[data-filter="${value}"]`);
      if (btn) btn.classList.add('active');
    }
    renderScenarioList();
  }

  function renderScenarioList() {
    const list = el('scenarioList');
    if (!list) return;
    let filtered = _allScenarios;

    if (_protocolFilter === 'wifi') {
      filtered = filtered.filter(s => s.id.startsWith('wifi'));
    } else if (_protocolFilter === 'ble') {
      filtered = filtered.filter(s => s.id.startsWith('ble'));
    }
    if (['easy','medium','hard'].includes(_difficultyFilter)) {
      filtered = filtered.filter(s => s.difficulty === _difficultyFilter);
    }

    list.innerHTML = filtered.map(s => {
      return `
        <div class="scenario-card" id="scenario-card-${s.id}">
          <div class="scenario-card-left">
            <div class="scenario-card-title">${s.title}</div>
            <div class="scenario-card-meta">
              ${difficultyBadge(s.difficulty)}
              <span class="scenario-protocol">${protocolIcon(s.protocol)} ${s.protocol}</span>
              <span class="scenario-target"><i class="fa-solid fa-crosshairs"></i> ${s.target_device || s.target_address || ''}</span>
            </div>
            <div class="scenario-owasp">${s.owasp_category || ''}</div>
          </div>
          <div class="scenario-card-actions">
            <button class="btn btn-outline-blue btn-sm" onclick="lab.openTutorial('${s.id}')" title="Read tutorial">
              <i class="fa-solid fa-book"></i>
            </button>
            <button class="btn btn-primary btn-sm" onclick="lab.runScenario('${s.id}')">
              <i class="fa-solid fa-crosshairs"></i> Exploit
            </button>
          </div>
        </div>`;
    }).join('') || emptyState({
      icon: 'fa-filter-circle-xmark', iconColor: '#a78bfa',
      title: 'No scenarios match these filters',
      message: 'Try a different protocol or difficulty combination.',
      actionLabel: 'Reset Filters',
      actionFn: `lab.filterScenarios('protocol','all');lab.filterScenarios('difficulty','all')`,
    });
  }

  async function runScenario(id) {
    _activeScenarioId = id;

    const panel = el('scenarioResultPanel');
    const resultEl = el('scenarioResultContent');
    if (!panel || !resultEl) return;

    panel.classList.remove('hidden');
    panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

    resultEl.innerHTML = `
      <div class="attack-running">
        <i class="fa-solid fa-circle-notch fa-spin" style="color:#60a5fa;"></i>
        Launching <strong>${id}</strong>… establishing connection to target
      </div>`;

    try {
      const r = await api('POST', `/attacks/${id}/run`);
      await renderScenarioResultLive(r);
      fetchStats();
    } catch (e) {
      resultEl.innerHTML = `<div class="attack-error"><i class="fa-solid fa-circle-xmark"></i> Error: ${e.message}</div>`;
    }
  }

  function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

  async function renderScenarioResultLive(r) {
    const resultEl = el('scenarioResultContent');
    if (!resultEl) return;

    const successColor = r.success ? '#22c55e' : '#ef4444';
    const successIcon  = r.success ? 'fa-circle-check' : 'fa-circle-xmark';
    const evidence = r.evidence || [];

    const containerDown = !r.success && /unreachable|start the wi-fi lab|start the wifi lab|connection failed/i.test(r.summary || '');

    resultEl.innerHTML = `
      <div class="attack-result-header" style="border-left:3px solid ${successColor}">
        <i class="fa-solid ${successIcon}" style="color:${successColor};font-size:20px;"></i>
        <div>
          <div class="attack-result-title">${escHtml(r.title || r.scenario_id)}</div>
          <div class="attack-result-summary">${escHtml(r.summary || '')}</div>
        </div>
        <span class="attack-elapsed" id="liveElapsed">0.0s</span>
      </div>
      <div class="evidence-list" id="liveEvidenceList"></div>
      <div id="liveActionsRow"></div>`;

    const liveList = el('liveEvidenceList');
    const elapsedEl = el('liveElapsed');
    const startTime = Date.now();

    for (let i = 0; i < evidence.length; i++) {
      const ev = evidence[i];
      const pendingId = `pending-step-${i}`;
      liveList.insertAdjacentHTML('beforeend', `
        <div class="evidence-step step-pending" id="${pendingId}">
          <div class="evidence-step-num">Step ${ev.step}</div>
          <div class="evidence-step-body">
            <div class="evidence-action"><i class="fa-solid fa-terminal"></i> ${escHtml(ev.action)}</div>
            <div class="evidence-result"><i class="fa-solid fa-circle-notch fa-spin"></i> executing…</div>
          </div>
          <i class="fa-solid fa-spinner fa-pulse evidence-step-icon" style="color:#60a5fa;"></i>
        </div>`);
      const node = el(pendingId);
      if (node) node.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

      await sleep(450 + Math.random() * 300);
      if (elapsedEl) elapsedEl.textContent = ((Date.now() - startTime) / 1000).toFixed(1) + 's';

      if (node) {
        node.classList.remove('step-pending');
        node.classList.add(ev.success ? 'step-success' : 'step-fail');
        const resEl = node.querySelector('.evidence-result');
        const iconEl = node.querySelector('.evidence-step-icon');
        if (resEl)  resEl.innerHTML = escHtml(ev.result);
        if (iconEl) {
          iconEl.className = `fa-solid ${ev.success ? 'fa-check' : 'fa-xmark'} evidence-step-icon`;
          iconEl.style.color = ev.success ? '#22c55e' : '#ef4444';
        }
      }
      await sleep(180);
    }

    if (elapsedEl) elapsedEl.textContent = ((Date.now() - startTime) / 1000).toFixed(1) + 's';

    const actionsRow = el('liveActionsRow');
    if (actionsRow) {
      actionsRow.innerHTML = (containerDown ? `
        <div class="container-down-banner">
          <div class="container-down-icon"><i class="fa-solid fa-triangle-exclamation"></i></div>
          <div class="container-down-body">
            <div class="container-down-title">Wi-Fi Lab Containers Are Not Running</div>
            <div class="container-down-desc">
              This exploit sends real HTTP requests to a Docker container — but no container is responding on the expected port.
              Start the Wi-Fi lab, then click <strong>Re-run Exploit</strong>.
            </div>
            <div class="container-down-steps">
              <div class="container-down-step"><span class="container-down-step-num">1</span><span>Open a terminal in the project root</span></div>
              <div class="container-down-step"><span class="container-down-step-num">2</span><code>cd virtual_lab &amp;&amp; ./start_lab.sh</code></div>
              <div class="container-down-step"><span class="container-down-step-num">3</span><span>Wait ~15 seconds, then re-run</span></div>
            </div>
            <div class="container-down-actions">
              <button class="btn btn-primary btn-sm" onclick="lab.startComponent('wifi')"><i class="fa-solid fa-play"></i> Start Wi-Fi Lab Now</button>
              <button class="btn btn-outline-blue btn-sm" onclick="lab.runScenario('${r.scenario_id}')"><i class="fa-solid fa-rotate-right"></i> Retry Exploit</button>
            </div>
          </div>
        </div>` : '') + `
        <div class="scenario-actions-row">
          <button class="btn btn-primary btn-sm" onclick="lab.runScenario('${r.scenario_id}')">
            <i class="fa-solid fa-rotate-right"></i> Re-run Exploit
          </button>
          <button class="btn btn-text btn-sm" onclick="lab.openTutorial('${r.scenario_id}')">
            <i class="fa-solid fa-book"></i> Read Tutorial
          </button>
        </div>`;
    }
  }

  // ─── Tutorial ────────────────────────────────────────────────────────────────

  async function openTutorial(id) {
    const modal = el('tutorialModal');
    const body  = el('tutorialBody');
    if (!modal || !body) return;

    body.innerHTML = '<div class="loading-text"><i class="fa-solid fa-spinner fa-spin"></i> Loading…</div>';
    modal.classList.remove('hidden');

    try {
      const d = await api('GET', `/attacks/${id}/tutorial`);
      if (!d.ok) { body.innerHTML = 'Tutorial not found.'; return; }
      const t = d.tutorial;
      body.innerHTML = `
        <div class="tutorial-header">
          <h2>${escHtml(t.title)}</h2>
          <div class="tutorial-meta">
            ${difficultyBadge(t.difficulty)}
            <span class="text-muted"><i class="fa-solid fa-clock"></i> ~${t.reading_time_min} min read</span>
          </div>
        </div>

        <h4><i class="fa-solid fa-lightbulb" style="color:#f59e0b;"></i> Concept</h4>
        <p>${escHtml(t.concept)}</p>

        <h4><i class="fa-solid fa-globe" style="color:#60a5fa;"></i> Real-World Incident</h4>
        <p>${escHtml(t.real_world)}</p>

        <h4><i class="fa-solid fa-bug" style="color:#ef4444;"></i> Vulnerability Details</h4>
        <div class="vuln-details-grid">
          <div><strong>Type:</strong> ${t.vulnerability_details?.type || ''}</div>
          <div><strong>CVSS:</strong> <span style="color:#ef4444;font-weight:600;">${t.vulnerability_details?.cvss_score || ''}</span></div>
          <div><strong>CWE:</strong> ${t.vulnerability_details?.cwe || ''}</div>
          <div><strong>Vector:</strong> <code style="font-size:11px;">${t.vulnerability_details?.cvss_vector || ''}</code></div>
        </div>

        <h4><i class="fa-solid fa-magnifying-glass" style="color:#a78bfa;"></i> What to Look For</h4>
        <ul>${(t.what_to_look_for||[]).map(x=>`<li>${escHtml(x)}</li>`).join('')}</ul>

        <h4><i class="fa-solid fa-graduation-cap" style="color:#34d399;"></i> Learning Objectives</h4>
        <ul>${(t.learning_objectives||[]).map(x=>`<li>${escHtml(x)}</li>`).join('')}</ul>

        <h4><i class="fa-solid fa-shield-halved" style="color:#22c55e;"></i> Remediation</h4>
        <pre class="remediation-pre">${escHtml(t.remediation_deep_dive||'')}</pre>`;
    } catch (e) {
      body.innerHTML = `Error loading tutorial: ${e.message}`;
    }
  }

  function closeTutorial() {
    const modal = el('tutorialModal');
    if (modal) modal.classList.add('hidden');
  }

  // ─── Stats Bar ───────────────────────────────────────────────────────────────

  // Clock skew between server and browser (server_time_ms - browser_time_ms),
  // refreshed every fetchStats() so relative times match server reality.
  let _serverSkewMs = 0;

  function formatRelativeTime(iso) {
    if (!iso) return '—';
    const then = new Date(iso.replace(' ', 'T') + (iso.endsWith('Z') ? '' : 'Z'));
    let diff = Math.floor((Date.now() + _serverSkewMs - then.getTime()) / 1000);
    if (isNaN(diff)) return '—';
    if (diff < 0)    diff = 0;
    if (diff < 5)    return 'just now';
    if (diff < 60)   return `${diff}s ago`;
    if (diff < 3600) return `${Math.floor(diff/60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff/3600)}h ago`;
    return `${Math.floor(diff/86400)}d ago`;
  }

  let _lastActivityTs = null;

  async function fetchStats() {
    try {
      const [devicesResp, activityResp] = await Promise.all([
        api('GET', '/iot/devices').catch(() => null),
        api('GET', '/lab/activity?limit=1').catch(() => null),
      ]);

      const devices = Array.isArray(devicesResp) ? devicesResp
                    : (devicesResp && devicesResp.devices) || [];

      const critical = devices.reduce((acc, d) => {
        const vulns = d.vulnerabilities || [];
        return acc + vulns.filter(v => (v.severity || '').toUpperCase() === 'CRITICAL').length;
      }, 0);

      const lastTs = activityResp && activityResp.entries && activityResp.entries[0]
                     ? activityResp.entries[0].timestamp : null;
      _lastActivityTs = lastTs;

      // Re-sync clock skew with server (handles browser/server clock mismatch)
      if (activityResp && activityResp.server_time) {
        const serverNow = new Date(activityResp.server_time).getTime();
        if (!isNaN(serverNow)) _serverSkewMs = serverNow - Date.now();
      }

      const dEl = el('statDeviceCount');
      const cEl = el('statCriticalCount');
      const lEl = el('statLastActivity');
      if (dEl) dEl.textContent = devices.length;
      if (cEl) cEl.textContent = critical;
      if (lEl) lEl.textContent = formatRelativeTime(lastTs);
    } catch (_) {}
  }

  // Update the "Last Activity" label every second using the cached timestamp,
  // so the user sees "1s ago → 2s ago → …" without re-hitting the API.
  function tickRelativeTimes() {
    const lEl = el('statLastActivity');
    if (lEl && _lastActivityTs) lEl.textContent = formatRelativeTime(_lastActivityTs);
  }

  // ─── Activity Log ────────────────────────────────────────────────────────────

  async function fetchActivity() {
    const logEl = el('labActivityLog');
    if (!logEl) return;
    try {
      const d = await api('GET', '/lab/activity?limit=30');
      if (!d.ok || !d.entries) return;

      const eventColors = {
        LAB_START:           '#22c55e',
        LAB_STOP:            '#6b7280',
        SCAN_STARTED:        '#60a5fa',
        DEVICE_DISCOVERED:   '#34d399',
        VULNERABILITY_FOUND: '#ef4444',
        QUICK_SCAN:          '#a78bfa',
        BLE_INJECT:          '#60a5fa',
        LAB_RESET:           '#f59e0b',
        ATTACK_SIMULATED:    '#f97316',
      };

      if (!d.entries.length) {
        logEl.innerHTML = emptyState({
          icon: 'fa-clock-rotate-left', iconColor: '#a78bfa',
          title: 'No activity yet',
          message: 'Start the lab, run a discovery, or execute an exploit to see events here.',
          actionLabel: 'Quick Discovery (Wi-Fi)', actionFn: 'lab.quickScan()',
          secondaryLabel: 'Start Lab', secondaryFn: 'lab.startAll()',
        });
        return;
      }

      logEl.innerHTML = d.entries.map(ev => {
        const color = eventColors[ev.event] || '#9ca3af';
        const ts = (ev.timestamp || '').replace('T', ' ').replace('Z', '');
        return `
          <div class="activity-event">
            <span class="activity-dot" style="background:${color};"></span>
            <span class="activity-event-type" style="color:${color};">${ev.event}</span>
            <span class="activity-message">${escHtml(ev.message)}</span>
            ${ev.device ? `<span class="activity-device"><i class="fa-solid fa-microchip"></i> ${escHtml(ev.device)}</span>` : ''}
            ${ev.protocol ? `<span class="activity-proto">${escHtml(ev.protocol)}</span>` : ''}
            <span class="activity-time">${ts}</span>
          </div>`;
      }).join('');
    } catch (_) {}
  }

  // ─── Learning Path ───────────────────────────────────────────────────────────

  async function fetchLearningPath() {
    const el2 = el('learningPath');
    if (!el2) return;
    try {
      // Use the full /attacks/ endpoint so we get target_device, vulnerability_class, etc.
      const d = await api('GET', '/attacks/');
      if (!d.ok) return;

      const scenarios = d.scenarios || [];
      const sections = [
        { label: 'Easy',   key: 'easy',   color: '#22c55e', icon: 'fa-seedling' },
        { label: 'Medium', key: 'medium', color: '#f59e0b', icon: 'fa-fire-flame-simple' },
        { label: 'Hard',   key: 'hard',   color: '#ef4444', icon: 'fa-skull' },
      ];

      const protoIcon = (s) => {
        if (s.id.startsWith('ble')) return '<i class="fa-brands fa-bluetooth-b" style="color:#60a5fa;"></i>';
        return '<i class="fa-solid fa-wifi" style="color:#34d399;"></i>';
      };

      const prettyVulnClass = (v) => (v || '').replace(/_/g, ' ').toLowerCase()
        .replace(/\b\w/g, c => c.toUpperCase());

      el2.innerHTML = `
        <div class="learning-path-tracks">
          ${sections.map(s => {
            const items = scenarios.filter(x => x.difficulty === s.key);
            return `
              <div class="learning-track">
                <div class="learning-track-header" style="color:${s.color};">
                  <i class="fa-solid ${s.icon}"></i> ${s.label}
                  <span class="learning-track-count">${items.length}</span>
                </div>
                <div class="catalog-card-grid">
                  ${items.map(sc => `
                    <div class="catalog-card" onclick="lab.runScenario('${sc.id}')" title="Click to launch this exploit">
                      <div class="catalog-card-top">
                        <span class="catalog-card-id">${sc.id}</span>
                        ${protoIcon(sc)}
                      </div>
                      <div class="catalog-card-title">${escHtml(sc.title || sc.target_device || '—')}</div>
                      <div class="catalog-card-meta">
                        ${difficultyBadge(sc.difficulty)}
                        <span class="catalog-card-proto">${protocolIcon(sc.protocol)} ${escHtml(sc.protocol || '')}</span>
                        <span class="catalog-card-tgt"><i class="fa-solid fa-crosshairs"></i> ${escHtml(sc.target_device || sc.target_address || '')}</span>
                      </div>
                      <div class="catalog-card-owasp">${escHtml(sc.owasp_category || prettyVulnClass(sc.vulnerability_class))}</div>
                      <div class="catalog-card-launch">
                        <i class="fa-solid fa-play"></i> Launch
                      </div>
                    </div>`
                  ).join('') || '<div class="catalog-empty">No scenarios at this level</div>'}
                </div>
              </div>`;
          }).join('')}
        </div>`;
    } catch (_) {}
  }

  // ─── Auto-refresh ────────────────────────────────────────────────────────────

  let _tickTimer = null;
  function startAutoRefresh() {
    if (_statusTimer)   clearInterval(_statusTimer);
    if (_activityTimer) clearInterval(_activityTimer);
    if (_tickTimer)     clearInterval(_tickTimer);
    _statusTimer   = setInterval(fetchStatus,   10000);
    _activityTimer = setInterval(() => { fetchActivity(); fetchStats(); }, 5000);
    _tickTimer     = setInterval(tickRelativeTimes, 1000);
  }

  function stopAutoRefresh() {
    clearInterval(_statusTimer);
    clearInterval(_activityTimer);
  }

  // ─── Init ────────────────────────────────────────────────────────────────────

  function init() {
    fetchStatus();
    fetchArchitecture();
    fetchBleDevices();
    fetchActivity();
    fetchStats();
    fetchLearningPath();
    startAutoRefresh();
  }

  // ─── Utility ────────────────────────────────────────────────────────────────

  function escHtml(s) {
    if (!s) return '';
    return String(s)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;')
      .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  // Public API
  return {
    init,
    startAll, stopAll, startComponent, stopComponent,
    quickScan, bleInject, resetLab,
    fetchStatus, fetchArchitecture, fetchBleDevices, fetchActivity, fetchStats, fetchLearningPath,
    filterScenarios, runScenario,
    openTutorial, closeTutorial,
  };
})();

window.lab = lab;
