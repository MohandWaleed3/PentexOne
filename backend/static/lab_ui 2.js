/**
 * PentexOne — Virtual Lab UI Controller
 * Handles all interactions for the Virtual Lab view:
 *   - Lab start/stop control
 *   - Network architecture display
 *   - Attack scenario execution
 *   - Tutorial & hint system
 *   - Scoring
 *   - Activity log
 */

const lab = (function () {

  const API = '';   // same origin
  let _statusTimer  = null;
  let _activityTimer = null;
  let _activeScenarioId = null;
  let _scenarioStartTime = null;
  let _hintsUsed = 0;
  let _allScenarios = [];
  let _currentFilter = 'all';
  let _scoreTracker = {};   // scenarioId → {score, grade}

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
  }

  async function stopAll() {
    toast('Stopping lab…', 'info');
    await api('POST', '/lab/stop');
    toast('Lab stopped', 'success');
    fetchStatus();
  }

  async function startComponent(c) {
    toast(`Starting ${c.toUpperCase()} lab…`, 'info');
    const r = await api('POST', `/lab/start?component=${c}`);
    toast(r.message || 'Started', 'success');
    fetchStatus();
  }

  async function stopComponent(c) {
    toast(`Stopping ${c.toUpperCase()} lab…`, 'info');
    await api('POST', `/lab/stop?component=${c}`);
    toast('Stopped', 'success');
    fetchStatus();
  }

  // ─── Quick Inject ────────────────────────────────────────────────────────────

  async function quickScan() {
    toast('Injecting Wi-Fi lab devices into database…', 'info');
    const r = await api('POST', '/lab/quick-scan');
    toast(r.message || 'Done', 'success');
    if (window.app && app.fetchDevices) app.fetchDevices();
  }

  async function bleInject() {
    toast('Injecting BLE lab devices into database…', 'info');
    const r = await api('POST', '/lab/ble-inject');
    toast(r.message || 'Done', 'success');
    if (window.app && app.fetchDevices) app.fetchDevices();
  }

  async function resetLab() {
    if (!confirm('Remove all [LAB] devices from the database?')) return;
    const r = await api('POST', '/lab/reset');
    toast(r.message || 'Reset done', 'success');
    if (window.app && app.fetchDevices) app.fetchDevices();
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
      grid.innerHTML = '<span class="text-muted">Could not load architecture — is the backend running?</span>';
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
    try {
      const d = await api('GET', '/attacks/');
      if (!d.ok) return;
      _allScenarios = d.scenarios || [];
      renderScenarioList();
    } catch (_) {}
  }

  function filterScenarios(f) {
    _currentFilter = f;
    document.querySelectorAll('.scenario-filter-btn').forEach(b => b.classList.remove('active'));
    const btn = document.querySelector(`.scenario-filter-btn[data-filter="${f}"]`);
    if (btn) btn.classList.add('active');
    renderScenarioList();
  }

  function renderScenarioList() {
    const list = el('scenarioList');
    if (!list) return;
    let filtered = _allScenarios;
    if (_currentFilter === 'wifi') filtered = filtered.filter(s => s.protocol && s.protocol.toLowerCase().includes('http') || s.id.startsWith('wifi'));
    else if (_currentFilter === 'ble') filtered = filtered.filter(s => s.id.startsWith('ble'));
    else if (['easy','medium','hard'].includes(_currentFilter)) filtered = filtered.filter(s => s.difficulty === _currentFilter);

    const riskColor = { CRITICAL:'#ef4444', HIGH:'#f97316', MEDIUM:'#f59e0b', SAFE:'#22c55e' };
    const savedScores = _scoreTracker;

    list.innerHTML = filtered.map(s => {
      const scoreInfo = savedScores[s.id];
      const scoreBadge = scoreInfo
        ? `<span class="score-badge grade-${scoreInfo.grade}">${scoreInfo.grade} (${scoreInfo.score}pts)</span>`
        : '';
      return `
        <div class="scenario-card" id="scenario-card-${s.id}">
          <div class="scenario-card-left">
            <div class="scenario-card-title">${s.title}</div>
            <div class="scenario-card-meta">
              ${difficultyBadge(s.difficulty)}
              <span class="scenario-protocol">${protocolIcon(s.protocol)} ${s.protocol}</span>
              <span class="scenario-target"><i class="fa-solid fa-crosshairs"></i> ${s.target_device || s.target_address || ''}</span>
              ${scoreBadge}
            </div>
            <div class="scenario-owasp">${s.owasp_category || ''}</div>
          </div>
          <div class="scenario-card-actions">
            <button class="btn btn-outline-blue btn-sm" onclick="lab.openTutorial('${s.id}')" title="Read tutorial">
              <i class="fa-solid fa-book"></i>
            </button>
            <button class="btn btn-primary btn-sm" onclick="lab.runScenario('${s.id}')">
              <i class="fa-solid fa-play"></i> Run
            </button>
          </div>
        </div>`;
    }).join('') || '<p class="text-muted" style="padding:20px;">No scenarios match this filter.</p>';
  }

  async function runScenario(id) {
    _activeScenarioId = id;
    _scenarioStartTime = Date.now();
    _hintsUsed = 0;

    const panel = el('scenarioResultPanel');
    const resultEl = el('scenarioResultContent');
    if (!panel || !resultEl) return;

    panel.classList.remove('hidden');
    panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

    resultEl.innerHTML = `
      <div class="attack-running">
        <i class="fa-solid fa-circle-notch fa-spin" style="color:#60a5fa;"></i>
        Running <strong>${id}</strong>… sending real requests to lab containers
      </div>`;

    try {
      const r = await api('POST', `/attacks/${id}/run`);
      renderScenarioResult(r);
    } catch (e) {
      resultEl.innerHTML = `<div class="attack-error"><i class="fa-solid fa-circle-xmark"></i> Error: ${e.message}</div>`;
    }
  }

  function renderScenarioResult(r) {
    const resultEl = el('scenarioResultContent');
    if (!resultEl) return;

    const successColor = r.success ? '#22c55e' : '#ef4444';
    const successIcon  = r.success ? 'fa-circle-check' : 'fa-circle-xmark';

    const evidenceHtml = (r.evidence || []).map(ev => `
      <div class="evidence-step ${ev.success ? 'step-success' : 'step-fail'}">
        <div class="evidence-step-num">Step ${ev.step}</div>
        <div class="evidence-step-body">
          <div class="evidence-action"><i class="fa-solid fa-terminal"></i> ${escHtml(ev.action)}</div>
          <div class="evidence-result">${escHtml(ev.result)}</div>
        </div>
        <i class="fa-solid ${ev.success ? 'fa-check' : 'fa-xmark'} evidence-step-icon" style="color:${ev.success?'#22c55e':'#ef4444'};"></i>
      </div>`
    ).join('');

    const elapsed = _scenarioStartTime ? ((Date.now() - _scenarioStartTime) / 1000).toFixed(1) : '?';

    resultEl.innerHTML = `
      <div class="attack-result-header" style="border-left:3px solid ${successColor}">
        <i class="fa-solid ${successIcon}" style="color:${successColor};font-size:20px;"></i>
        <div>
          <div class="attack-result-title">${escHtml(r.title || r.scenario_id)}</div>
          <div class="attack-result-summary">${escHtml(r.summary || '')}</div>
        </div>
        <span class="attack-elapsed">${elapsed}s</span>
      </div>
      <div class="evidence-list">${evidenceHtml}</div>
      <div class="scenario-actions-row">
        <button class="btn btn-outline-blue btn-sm" onclick="lab.showHintPanel('${r.scenario_id}')">
          <i class="fa-solid fa-lightbulb"></i> Get Hint
        </button>
        <button class="btn btn-outline-green btn-sm" onclick="lab.submitScore('${r.scenario_id}', ${elapsed})">
          <i class="fa-solid fa-star"></i> Submit Score
        </button>
        <button class="btn btn-text btn-sm" onclick="lab.openTutorial('${r.scenario_id}')">
          <i class="fa-solid fa-book"></i> Read Tutorial
        </button>
      </div>
      <div id="hintPanel-${r.scenario_id}" class="hint-panel hidden"></div>
      <div id="scorePanel-${r.scenario_id}" class="score-panel hidden"></div>`;
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
        <pre class="remediation-pre">${escHtml(t.remediation_deep_dive||'')}</pre>

        <div class="tutorial-run-row">
          <button class="btn btn-primary" onclick="lab.closeTutorial(); lab.runScenario('${id}')">
            <i class="fa-solid fa-play"></i> Run Attack Now
          </button>
        </div>`;
    } catch (e) {
      body.innerHTML = `Error loading tutorial: ${e.message}`;
    }
  }

  function closeTutorial() {
    const modal = el('tutorialModal');
    if (modal) modal.classList.add('hidden');
  }

  // ─── Hints ───────────────────────────────────────────────────────────────────

  async function showHintPanel(id) {
    const panel = el(`hintPanel-${id}`);
    if (!panel) return;
    panel.classList.remove('hidden');

    const meta = await api('GET', `/attacks/${id}/hints`);
    const available = meta.hint_count || 3;
    const used = _hintsUsed;

    panel.innerHTML = `
      <div class="hint-panel-header">
        <i class="fa-solid fa-lightbulb" style="color:#f59e0b;"></i>
        <strong>Hints</strong>
        <span class="text-muted">(${used} used · -10 pts each)</span>
      </div>
      <div class="hint-buttons">
        ${Array.from({length: available}, (_, i) => i + 1).map(level => `
          <button class="btn btn-outline-orange btn-sm ${used >= level ? 'used' : ''}"
                  onclick="lab.revealHint('${id}', ${level})"
                  ${used >= level ? 'disabled' : ''}>
            Hint ${level}
          </button>`).join('')}
      </div>
      <div id="hintText-${id}" class="hint-text"></div>`;
  }

  async function revealHint(id, level) {
    const d = await api('GET', `/attacks/${id}/hints/${level}`);
    const textEl = el(`hintText-${id}`);
    if (textEl) {
      textEl.innerHTML = `<div class="hint-revealed"><i class="fa-solid fa-lightbulb" style="color:#f59e0b;"></i> <strong>Hint ${level}:</strong> ${escHtml(d.hint || '')}</div>`;
    }
    if (level > _hintsUsed) _hintsUsed = level;
  }

  // ─── Score Submission ────────────────────────────────────────────────────────

  async function submitScore(id, elapsedStr) {
    const elapsed = parseFloat(elapsedStr) || 60;
    const panel = el(`scorePanel-${id}`);
    if (!panel) return;
    panel.classList.remove('hidden');

    const d = await api('POST', `/attacks/${id}/score`, {
      elapsed_seconds: elapsed,
      hints_used: _hintsUsed,
      success: true,
    });

    const gradeColor = { A:'#22c55e', B:'#84cc16', C:'#f59e0b', D:'#f97316', F:'#ef4444' };
    const g = d.grade || 'F';
    const color = gradeColor[g] || '#9ca3af';

    panel.innerHTML = `
      <div class="score-result" style="border-color:${color}44;background:${color}11;">
        <div class="score-grade-big" style="color:${color};">${g}</div>
        <div class="score-pts" style="color:${color};">${d.score} pts</div>
        <div class="score-msg">${escHtml(d.message || '')}</div>
        <div class="score-breakdown">
          <span>Base: ${d.base_score}</span>
          <span>×${d.difficulty_multiplier}</span>
          <span style="color:#ef4444;">−${d.hint_penalty} hints</span>
          <span style="color:#ef4444;">−${d.time_penalty} time</span>
        </div>
      </div>`;

    _scoreTracker[id] = { score: d.score, grade: g };
    renderScenarioList();
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
        logEl.innerHTML = '<p class="text-muted" style="padding:16px;">No activity yet — start the lab or run a scan.</p>';
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
      const d = await api('GET', '/attacks/learning/path');
      if (!d.ok) return;
      const sections = [
        { label: 'Easy', key: 'easy', color: '#22c55e', icon: 'fa-seedling' },
        { label: 'Medium', key: 'medium', color: '#f59e0b', icon: 'fa-fire-flame-simple' },
        { label: 'Hard', key: 'hard', color: '#ef4444', icon: 'fa-skull' },
      ];
      el2.innerHTML = `
        <div class="learning-path-total">
          Total Max Score: <strong style="color:#a78bfa;">${d.total_max_score} pts</strong>
        </div>
        <div class="learning-path-tracks">
          ${sections.map(s => `
            <div class="learning-track">
              <div class="learning-track-header" style="color:${s.color};">
                <i class="fa-solid ${s.icon}"></i> ${s.label}
              </div>
              <div class="learning-track-ids">
                ${(d[s.key]||[]).map(id => {
                  const score = _scoreTracker[id];
                  const done = score ? `✓ ${score.grade}` : '';
                  return `<span class="learning-id ${done?'done':''}" onclick="lab.runScenario('${id}')" title="${id}">${id} ${done}</span>`;
                }).join('')}
              </div>
            </div>`
          ).join('')}
        </div>`;
    } catch (_) {}
  }

  // ─── Auto-refresh ────────────────────────────────────────────────────────────

  function startAutoRefresh() {
    if (_statusTimer)   clearInterval(_statusTimer);
    if (_activityTimer) clearInterval(_activityTimer);
    _statusTimer   = setInterval(fetchStatus,   10000);
    _activityTimer = setInterval(fetchActivity, 15000);
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
    fetchScenarios();
    fetchActivity();
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
    fetchStatus, fetchArchitecture, fetchBleDevices, fetchActivity, fetchLearningPath,
    filterScenarios, runScenario,
    openTutorial, closeTutorial,
    showHintPanel, revealHint,
    submitScore,
  };
})();
