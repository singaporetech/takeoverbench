// ── State ──
let isRecording = false;
let isRunning = false;        // exposed for setup-link guard in dashboard.html
let currentRunId = null;
let pollTimer = null;
let torShown = false;
let allPresets = [];
let allScenarioSets = [];     // BUG-02 fix: was implicit global (ReferenceError risk)
let queuedIds = [];
let isCarlaConnected = false;
let activePresetIndex = 0;
let sessionRunCount = 0;
let activeSetId = null;
let activeSetName = null;
let runHadSet = false;   // was a scenario set active when this run started?

function updateCarlaStatus(connected) {
  isCarlaConnected = connected;
  const label = connected ? 'CARLA CONNECTED' : 'CARLA DISCONNECTED';
  document.getElementById('lbl-carla').textContent = label;
  document.getElementById('lbl-carla').className = 'badge ' + (connected ? 'badge-green' : 'badge-gray');
  // Hidden stub for backward compat
  var dc = document.getElementById('dot-carla');
  if (dc) dc.className = connected ? 'dot ok' : 'dot';
  const startBtn = document.getElementById('btn-start');
  if (startBtn) startBtn.disabled = !(connected && queuedIds.length > 0) || isRecording;
}

// ── HMI (topbar status only) ──
async function pollHMIStatus() {
  try {
    const res = await fetch('/api/hmi-status');
    const data = await res.json();
    const el = document.getElementById('lbl-hmi');
    if (data.connected) {
      el.textContent = 'HMI Connected';
      el.className = 'badge badge-green';
    } else {
      el.textContent = 'HMI Offline';
      el.className = 'badge badge-gray';
    }
  } catch(e) { /* ignore */ }
}

// ── Presets ──
async function loadPresets() {
  try {
    const res = await fetch('/presets');
    allPresets = await res.json();
  } catch(e) { addLog('Could not load presets', 'error'); }
}

async function loadScenarioSets() {
  try {
    const res = await fetch('/scenario-sets');
    allScenarioSets = await res.json();
    renderScenarioSets();
  } catch(e) { addLog('Could not load scenario sets', 'error'); }
}

async function loadScenarioSet(setId) {
  const res = await fetch('/load-scenario-set', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({set_id: setId})
  });
  const data = await res.json();
  if (!res.ok) { addLog('Error: ' + (data.error || ''), 'error'); return; }
  queuedIds = data.queue;
  activePresetIndex = 0;
  activeSetId = data.set_id || null;
  activeSetName = data.name || null;
  renderQueue();
  addLog('Loaded set: ' + data.name + ' (' + data.queue.length + ' runs)', 'ok');
}

async function clearQueue() {
  await fetch('/clear-queue', {method:'POST'});
  queuedIds = []; activePresetIndex = 0;
  activeSetId = null; activeSetName = null;
  renderQueue();
}

// ── Scenario controls ──
function syncScenarioState(data) {
  if (!data.scenario_running) return;

  currentRunId = data.run_id;
  isRecording = data.recording || false;
  isRunning = true;
  torShown = data.tor_triggered || false;

  document.getElementById('run-id-display').textContent = data.run_id;
  document.getElementById('lbl-runid').textContent = 'RUN: ' + data.run_id;
  document.getElementById('btn-start').disabled = true;
  document.getElementById('btn-start').textContent = 'RUNNING...';

  document.getElementById('dot-rec').className = 'dot recording';
  document.getElementById('lbl-rec').textContent = 'RECORDING';

  showVideoFeed();
  setRunStatus('');
  startPolling();
  addLog('Reconnected to running run: ' + data.run_id, 'ok');
}

async function startScenario() {
  // Prevent starting while already running (defence in depth — button should
  // also be disabled via updateCarlaStatus, but this catches edge cases)
  if (isRunning) return;

  const startBtn = document.getElementById('btn-start');
  startBtn.disabled = true;
  startBtn.textContent = 'STARTING...';
  document.getElementById('next-card').classList.remove('visible');
  setRunStatus('');
  runHadSet = (activeSetId !== null) || (queuedIds.length > 0);
  torShown = false;

  // BUG-03 fix: wrap in try/catch so network errors don't permanently disable the button
  try {
    const res  = await fetch('/start-scenario', {method:'POST'});
    const data = await res.json();

    if (!res.ok) {
      addLog('Error: ' + (data.error || ''), 'error');
      startBtn.disabled = false;
      startBtn.textContent = 'START SCENARIO';
      return;
    }

    isRecording = true;
    isRunning = true;
    // Update text to reflect running state (not 'STARTING...' which implies
    // the button can be clicked again)
    startBtn.textContent = 'RUNNING...';
    if (data.active_preset) updateActiveScenarioInfo(data.active_preset);
    renderQueue();
    showVideoFeed();
    startPolling();
    document.getElementById('dot-rec').className = 'dot recording';
    document.getElementById('lbl-rec').textContent = 'RECORDING';
    document.getElementById('run-id-display').textContent = data.run_id;
    document.getElementById('lbl-runid').textContent = 'RUN: ' + data.run_id;
    addLog('Run started: ' + data.run_id, 'ok');
  } catch(e) {
    addLog('Network error starting scenario: ' + e, 'error');
    startBtn.disabled = false;
    startBtn.textContent = 'START SCENARIO';
  }
}

function downloadReport() {
  const btn = document.getElementById('btn-pdf');
  btn.disabled = true; btn.textContent = 'GENERATING...';
  fetch('/download-report')
    .then(function(r) { if (!r.ok) throw new Error(); return r.blob(); })
    .then(function(blob) {
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = 'takeoverbench_session_report.pdf';
      document.body.appendChild(a); a.click();
      document.body.removeChild(a); URL.revokeObjectURL(url);
      btn.disabled = false;
      btn.textContent = 'SESSION REPORT (' + sessionRunCount + ' run' + (sessionRunCount > 1 ? 's' : '') + ')';
      addLog('PDF downloaded', 'ok');
    })
    .catch(function() {
      addLog('PDF error', 'error');
      btn.disabled = false;
      btn.textContent = 'SESSION REPORT';
    });
}

// ── Results link (report QR target) ──
async function saveQrUrl() {
  const el = document.getElementById('qr-url-input');
  const url = el ? el.value.trim() : '';
  try {
    const res = await fetch('/set-qr-url', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({url: url})
    });
    const data = await res.json();
    if (el) el.value = data.results_url || '';
    setRunStatus('Results link saved · ' + (data.results_url || ''), 'ok');
  } catch (e) {
    setRunStatus('Could not save results link', '');
  }
}

// ── Polling ──
function startPolling() {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(pollStatus, 500);
}
function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
}

async function pollStatus() {
  try {
    const res  = await fetch('/status');
    const data = await res.json();

    if (data.preset_queue) {
      queuedIds = data.preset_queue;
      activePresetIndex = data.active_preset_index || 0;
    }

    if (data.connected) {
      updateCarlaStatus(true);
    } else {
      updateCarlaStatus(false);
    }

    renderQueue();

    // Auto-show video feed if scenario is running
    // BUG-08 fix: removed the inner startPolling() call — it was resetting the interval every tick
    if (data.scenario_running) {
      const img = document.getElementById('video-feed');
      if (img && img.style.display !== 'block') {
        showVideoFeed();
      }
    }

    // Detect scenario end — was recording, but server says no longer running
    if (isRecording && !data.scenario_running) {
      isRecording = false;
      isRunning = false;

      // Re-enable start button (gated by CARLA + queue via updateCarlaStatus)
      document.getElementById('btn-start').textContent = 'START SCENARIO';

      // Reset recording indicator
      document.getElementById('dot-rec').className = 'dot';
      document.getElementById('lbl-rec').textContent = 'IDLE';

      // Reset run ID display
      document.getElementById('run-id-display').textContent = '--';
      document.getElementById('lbl-runid').textContent = 'NO RUN';

      // Reset autopilot badge
      setControlMode('idle');

      // Evaluator-facing status (the participant is cued inside CARLA).
      if (data.next_preset && data.next_preset.name) {
        setRunStatus('Run complete · next: ' + data.next_preset.name, 'ok');
      } else if (runHadSet) {
        setRunStatus('Set complete · Session Report ready', 'ok');
      } else {
        setRunStatus('Run complete', 'ok');
      }

      addLog('Scenario ended', 'ok');
    }

    // BUG-04 fix: populate and show the "next in queue" card from server state
    if (data.next_preset) {
      const nc = document.getElementById('next-card');
      document.getElementById('next-card-name').textContent = data.next_preset.name || '--';
      document.getElementById('next-card-meta').textContent =
        (data.next_preset.speed_kmh ? data.next_preset.speed_kmh + ' km/h' : '')
        + (data.next_preset.weather ? ' · ' + data.next_preset.weather : '');
      nc.classList.add('visible');
    } else {
      document.getElementById('next-card').classList.remove('visible');
    }

    renderParticipantID(data.participant_id);
    renderPhaseBadge(data.experiment_phase);

    // Sync active set from server
    if (data.active_set_id !== undefined) {
      activeSetId = data.active_set_id || null;
      activeSetName = data.active_set_name || null;
    }

    // Update session run count & PDF button
    // PDF is only downloadable at the end of a set, or after the first run
    // when no set is loaded (free mode)
    if (data.session_run_count !== undefined) {
      sessionRunCount = data.session_run_count;
      const btn = document.getElementById('btn-pdf');
      if (sessionRunCount > 0 && !isRecording) {
        const isSetComplete = activeSetId !== null && queuedIds.length > 0 && activePresetIndex >= queuedIds.length;
        const canEnablePdf = !activeSetId || isSetComplete;
        btn.disabled = !canEnablePdf;
        btn.textContent = 'SESSION REPORT (' + sessionRunCount + ' run' + (sessionRunCount > 1 ? 's' : '') + ')';
      } else if (sessionRunCount === 0) {
        btn.disabled = true;
        btn.textContent = 'SESSION REPORT';
      }
    }

    // TOR banner — guard with scenario_running to prevent stale tor_triggered
    // from the previous scenario showing during the gap between runs (0→1)
    if (data.scenario_running && data.tor_triggered && !torShown) {
      showTORBanner();
      addLog('TOR auto-triggered', 'warn');
    }

    renderCountdown(data);

    // Autopilot badge
    if (isRecording) {
      if (data.autopilot_engaged) {
        setControlMode('auto');
      } else {
        setControlMode('human');
      }
    }

    renderHardwareScores(data.hardware_config || {});
    renderTelemetry(data.telemetry);
  } catch(e) {}
}

// ── Init ──
async function initDashboard() {
  loadPresets();
  loadScenarioSets();
  addLog('Dashboard ready.', '');
  setInterval(pollHMIStatus, 5000);

  try {
    const res  = await fetch('/status');
    const data = await res.json();

    if (data.connected) {
      updateCarlaStatus(true);
      addLog('CARLA connected.', 'ok');
    } else {
      document.getElementById('btn-start').disabled = true;
    }

    syncScenarioState(data);

    if (data.preset_queue) {
      queuedIds = data.preset_queue;
      activePresetIndex = data.active_preset_index || 0;
    }

    sessionRunCount = data.session_run_count || 0;

    renderParticipantID(data.participant_id);
    renderPhaseBadge(data.experiment_phase);

    const qrInput = document.getElementById('qr-url-input');
    if (qrInput && data.results_url) qrInput.value = data.results_url;

    if (data.active_set_id !== undefined) {
      activeSetId = data.active_set_id || null;
      activeSetName = data.active_set_name || null;
    }

    renderHardwareScores(data.hardware_config || {});
    if (data.hardware_config && data.hardware_config.visual_score !== undefined) {
      addLog('Hardware config loaded from server.', 'ok');
    } else {
      addLog('No hardware config found -- visit Setup page.', 'warn');
    }

    if (sessionRunCount > 0) {
      const btn = document.getElementById('btn-pdf');
      // Only enable if no set is loaded, or the current set is complete
      const isSetComplete = activeSetId !== null && queuedIds.length > 0 && activePresetIndex >= queuedIds.length;
      btn.disabled = activeSetId !== null && !isSetComplete;
      btn.textContent = 'SESSION REPORT (' + sessionRunCount + ' run' + (sessionRunCount > 1 ? 's' : '') + ')';
    }

  } catch(e) {
    addLog('Server not reachable yet.', 'error');
  }
}

initDashboard();
