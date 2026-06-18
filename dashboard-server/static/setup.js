// ── Step Machine ─────────────────────────────────────────────
let currentStep = 1;

function showStep(n) {
  document.querySelectorAll('.step-content').forEach(function(el) {
    el.style.display = 'none';
  });
  document.getElementById('step-' + n).style.display = '';

  document.querySelectorAll('.step-item').forEach(function(el, i) {
    el.classList.toggle('active', i + 1 === n);
  });

  currentStep = n;
}

// Wire Next buttons (existing listener pattern used throughout this file)
document.addEventListener('DOMContentLoaded', function() {
  var btn1 = document.getElementById('btn-step1-next');
  if (btn1) {
    btn1.addEventListener('click', function() { showStep(2); });
  }

  var btn2 = document.getElementById('btn-step2-next');
  if (btn2) {
    btn2.addEventListener('click', function() { showStep(3); });
  }

  // Wire Back buttons
  document.querySelectorAll('.btn-back').forEach(function(btn) {
    btn.addEventListener('click', function() {
      if (currentStep > 1) showStep(currentStep - 1);
    });
  });
});

// ── Hardware Config State ────────────────────────────────────
const hwConfig = {
  visual: 'single_screen',
  motion: 'none',
  physical: 'wheel_pedals_seat',
};

// Defaults used before /fidelity-rules fetch completes
var scoreMap = {
  visual:   {single_screen:1, large_single:2, multi_screen_180:3, multi_screen_270:4, projector_270:5},
  motion:   {none:1, partial:3, full_6dof:5},
  physical: {keyboard:1, wheel_only:2, wheel_pedals_seat:3, partial_cab:4, full_cab:5},
};
var warningRules = [];
var tiers = {low_max: 7, medium_max: 11};

// Fetch authoritative rules from server — overrides defaults when loaded
fetch('/fidelity-rules').then(function(r) { return r.json(); }).then(function(data) {
  scoreMap = data.score_maps;
  warningRules = data.warning_rules;
  tiers = data.tiers;
  updateScores();
});

var hmiConnected = false;
var carlaConnected = false;
var carlaConnecting = false;
var carlaAbortController = null;
var hmiAbortController = null;

// ── Hardware Option Click Handler (supports both old .hw-option and new .radio-pill) ──
document.querySelectorAll('.hw-option, .radio-pill').forEach(function(opt) {
  opt.addEventListener('click', function() {
    const g = this.dataset.group;
    document.querySelectorAll('.hw-option[data-group="' + g + '"], .radio-pill[data-group="' + g + '"]')
            .forEach(function(o) { o.classList.remove('selected'); });
    this.classList.add('selected');
    hwConfig[g] = this.dataset.val;
    updateScores();
  });
});

// ── Update Scores + Step 3 Breakdown ─────────────────────────
function updateScores() {
  const vs = scoreMap.visual[hwConfig.visual]   || 1;
  const ms = scoreMap.motion[hwConfig.motion]   || 1;
  const ps = scoreMap.physical[hwConfig.physical] || 1;

  // Apply green/amber/red per-score colors
  function scoreSpan(val) {
    var cls = val <= 2 ? 'score-low' : val <= 3 ? 'score-mid' : 'score-high';
    return '<span class="' + cls + '">' + val + '</span>';
  }

  document.getElementById('sv').innerHTML = scoreSpan(vs) + '<span class="score-max">/5</span>';
  document.getElementById('sm').innerHTML = scoreSpan(ms) + '<span class="score-max">/5</span>';
  document.getElementById('sp').innerHTML = scoreSpan(ps) + '<span class="score-max">/5</span>';

  // ── Fidelity Level (Step 3 summary box) ──
  const total = vs + ms + ps;
  const badge = document.getElementById('fidelity-badge');
  var cls, label;
  if (total <= tiers.low_max) { cls = 'low';    label = 'LOW'; }
  else if (total <= tiers.medium_max) { cls = 'medium'; label = 'MEDIUM'; }
  else                         { cls = 'high';   label = 'HIGH'; }
  badge.className = 'score-summary-box ' + cls;
  badge.innerHTML = '<div class="score-total-label">TOTAL SCORE</div>'
    + '<div class="score-total-number">' + total + '<span class="score-total-max">/15</span></div>'
    + '<div class="score-total-level">' + label + '</div>';

  // ── Step 3 breakdown: option labels ──
  var catLabels = {
    visual:   {single_screen:"Single PC Screen", large_single:"Single Projector / Screen (>25\")", multi_screen_180:"Multi-Screen (<180° FOV)", multi_screen_270:"Multi-Screen (180°–270° FOV)", projector_270:"Projector Screens (>270° FOV)"},
    motion:   {none:"No Motion Base", partial:"Partial Motion / Vibration Platform (<6 DOF)", full_6dof:"Full 6-DOF Motion Platform"},
    physical: {keyboard:"Keyboard or Joystick", wheel_only:"Steering Wheel Only (no pedals)", wheel_pedals_seat:"Steering Wheel + Pedals + Racing Seat", partial_cab:"Vehicular Controls — Partial Cab", full_cab:"Full Vehicular Cab with Controls"},
  };
  ['visual', 'motion', 'physical'].forEach(function(key) {
    var labelEl = document.getElementById(key + '-option-label');
    if (labelEl) {
      labelEl.textContent = catLabels[key][hwConfig[key]] || hwConfig[key];
    }
  });

  // ── Per-category inline warnings (Step 2 checklist) ──
  const warnsByCat = {visual: [], motion: [], physical: []};
  for (var i = 0; i < warningRules.length; i++) {
    const rule = warningRules[i];
    const val = hwConfig[rule.key];
    if (val && rule.values.indexOf(val) !== -1) {
      warnsByCat[rule.key].push(rule.message_short || rule.message);
    }
  }

  ['visual', 'motion', 'physical'].forEach(function(key) {
    // Step 2: checklist warning container
    var warnEl = document.getElementById('warnings-' + key);
    if (warnEl) {
      const warns = warnsByCat[key];
      if (warns.length > 0) {
        warnEl.innerHTML = warns.map(function(w) {
          return '<div class="checklist-warn-item">'
            + '<span class="checklist-warn-text">' + w + '</span></div>';
        }).join('');
      } else {
        warnEl.innerHTML = '';
      }
    }
    // Step 3: breakdown remarks
    var remarkEl = document.getElementById(key + '-remarks');
    if (remarkEl) {
      const warns = warnsByCat[key];
      remarkEl.textContent = warns.length > 0 ? warns.join('; ') : '';
    }
  });

  // ── Flat warn-list (backward compat, hidden in Step 3) ──
  const warnsFlat = [];
  for (var i = 0; i < warningRules.length; i++) {
    const rule = warningRules[i];
    const val = hwConfig[rule.key];
    if (val && rule.values.indexOf(val) !== -1) {
      warnsFlat.push({level: rule.level, aspect: rule.aspect, msg: rule.message});
    }
  }

  var warnList = document.getElementById('warn-list');
  if (warnList) {
    warnList.innerHTML = warnsFlat.map(function(w) {
      return '<div class="warn-item ' + w.level + '">'
        + '<span class="warn-aspect">' + w.aspect.toUpperCase() + '</span>'
        + w.msg + '</div>';
    }).join('');
  }
}

// ── Step 1: Next button validation ───────────────────────────
function updateStep1NextButton() {
  var btn = document.getElementById('btn-step1-next');
  if (!btn) return;
  var pid = document.getElementById('participant-id').value.trim();
  btn.disabled = !(pid && carlaConnected && hmiConnected);
  // Keep Step 3 confirm button in sync
  updateConfirmButton();
}

// ── CARLA ────────────────────────────────────────────────────
async function connectCarlaSetup() {
  if (carlaConnected) return;

  // Cancel in-flight connection attempt
  if (carlaConnecting) {
    if (carlaAbortController) carlaAbortController.abort();
    return;
  }

  carlaConnecting = true;

  const btn = document.getElementById('btn-carla-setup');
  btn.textContent = 'Cancel';
  btn.disabled = false;
  btn.className = 'btn-connect cancelling';
  setCarlaStatus('connecting', 'Connecting to CARLA...');

  carlaAbortController = new AbortController();

  try {
    const res = await fetch('/connect-carla', {
      method: 'POST',
      signal: carlaAbortController.signal
    });
    const data = await res.json();

    if (data.status === 'ok') {
      carlaConnected = true;
      showCarlaConnectedUI();
    } else {
      carlaConnected = false;
      showDisconnectedUI('carla', data.error || 'Connection failed');
    }
  } catch(e) {
    if (e.name === 'AbortError') {
      carlaConnecting = false;
      showDisconnectedUI('carla', 'Connection cancelled');
      return;
    }
    carlaConnected = false;
    showDisconnectedUI('carla', 'Network error: ' + e);
  }

  carlaConnecting = false;
  updateStep1NextButton();
}

function setCarlaStatus(status, text) {
  var el = document.getElementById('carla-status-setup');
  if (!el) return;
  el.className = 'conn-status';
  if (status === 'connected') {
    el.className = 'conn-status connected';
    el.textContent = text || 'Carla Connected';
  } else if (status === 'connecting') {
    el.className = 'conn-status connecting';
    el.textContent = text || 'Connecting...';
  } else {
    el.className = 'conn-status disconnected';
    el.textContent = text || 'Not connected';
  }
}

function showCarlaConnectedUI() {
  var btn = document.getElementById('btn-carla-setup');
  btn.disabled = true;
  btn.className = 'btn-connect';
  btn.textContent = 'Connect';
  setCarlaStatus('connected', 'Carla Connected');
  updateStep1NextButton();
}

function showHMIConnectedUI() {
  var btn = document.getElementById('btn-hmi-setup');
  btn.disabled = true;
  btn.className = 'btn-connect';
  btn.textContent = 'Connect';
  setHMIStatus('connected', 'HMI Connected');
  updateStep1NextButton();
}

function showDisconnectedUI(type, detail) {
  var btn, statusId;
  if (type === 'carla') {
    carlaConnected = false;
    carlaConnecting = false;
    btn = document.getElementById('btn-carla-setup');
    statusId = 'carla-status-setup';
  } else {
    hmiConnected = false;
    btn = document.getElementById('btn-hmi-setup');
    statusId = 'hmi-status-setup';
  }
  btn.disabled = false;
  btn.className = 'btn-connect';
  btn.textContent = 'Connect';
  var el = document.getElementById(statusId);
  if (el) {
    el.className = 'conn-status disconnected';
    el.textContent = detail || 'Not connected';
  }
  updateStep1NextButton();
}

async function disconnectCarla() {
  try {
    await fetch('/disconnect-carla', { method: 'POST' });
  } catch(e) { /* server may be unreachable */ }
  showDisconnectedUI('carla');
}

async function disconnectHMI() {
  try {
    await fetch('/disconnect-hmi', { method: 'POST' });
  } catch(e) { /* server may be unreachable */ }
  showDisconnectedUI('hmi');
}

// ── Background status poll ───────────────────────────────────
function startStatusPoll() {
  setInterval(async function() {
    try {
      const res = await fetch('/status');
      const data = await res.json();

      if (!carlaConnected && !carlaConnecting && data.connected) {
        carlaConnected = true;
        showCarlaConnectedUI();
      }

      if (!hmiConnected && data.hmi_connected) {
        hmiConnected = true;
        showHMIConnectedUI();
      }
    } catch(e) { /* server not ready yet */ }
  }, 3000);
}

async function restoreHMIOnLoad() {
  try {
    const res = await fetch('/api/hmi-status');
    const data = await res.json();
    if (data.connected && !hmiConnected) {
      hmiConnected = true;
      showHMIConnectedUI();
    }
  } catch(e) { /* server may not be ready */ }
}

// ── HMI ──────────────────────────────────────────────────────
async function testHMISetup() {
  const btn = document.getElementById('btn-hmi-setup');

  if (hmiAbortController) {
    hmiAbortController.abort();
    return;
  }

  btn.textContent = 'Cancel';
  btn.disabled = false;
  btn.className = 'btn-connect cancelling';
  setHMIStatus('connecting', 'Connecting to HMI...');

  hmiAbortController = new AbortController();

  try {
    const res = await fetch('/api/hmi-test', {
      method: 'POST',
      signal: hmiAbortController.signal
    });
    const data = await res.json();

    if (data.status === 'ok') {
      hmiConnected = true;
      showHMIConnectedUI();
    } else {
      hmiConnected = false;
      var detail = '';
      if (data.results && data.results.ping) {
        detail = 'Partial: ping OK, TOR test failed';
      } else {
        detail = data.error || 'Connection failed';
      }
      showDisconnectedUI('hmi', detail);
    }
  } catch(e) {
    if (e.name === 'AbortError') {
      hmiConnected = false;
      showDisconnectedUI('hmi');
      hmiAbortController = null;
      return;
    }
    hmiConnected = false;
    showDisconnectedUI('hmi', 'Network error: ' + e);
  }
  hmiAbortController = null;
  updateStep1NextButton();
}

function setHMIStatus(status, text) {
  var el = document.getElementById('hmi-status-setup');
  if (!el) return;
  el.className = 'conn-status';
  if (status === 'connected') {
    el.className = 'conn-status connected';
    el.textContent = text || 'HMI Connected';
  } else if (status === 'connecting') {
    el.className = 'conn-status connecting';
    el.textContent = text || 'Connecting...';
  } else {
    el.className = 'conn-status disconnected';
    el.textContent = text || 'Not connected';
  }
}

// ── Confirm Button (Step 3) ───────────────────────────────────
function updateConfirmButton() {
  const btn = document.getElementById('confirm-btn');
  const note = document.getElementById('skip-note');
  var pid = document.getElementById('participant-id').value.trim();
  var reasons = [];

  if (!pid) reasons.push('Participant ID is required');
  if (!carlaConnected) reasons.push('CARLA not connected');
  if (!hmiConnected) reasons.push('HMI not connected (or skipped)');

  if (reasons.length > 0) {
    btn.disabled = true;
    if (note) {
      note.style.display = '';
      note.innerHTML = '<strong style="color:var(--warn)">Complete to proceed:</strong> '
        + reasons.join(' · ');
    }
  } else {
    btn.disabled = false;
    if (note) {
      note.style.display = 'none';
    }
  }
}

// ── Handle Confirm ───────────────────────────────────────────
async function handleConfirm() {
  var pid = document.getElementById('participant-id').value.trim();
  if (!pid) { alert('Please enter a Participant ID.'); return; }
  if (!carlaConnected) { alert('CARLA is not connected. Please connect CARLA first.'); return; }
  if (!hmiConnected) { alert('HMI is not connected. Please test the HMI connection first.'); return; }

  const btn = document.getElementById('confirm-btn');
  btn.disabled = true;
  btn.textContent = 'SAVING...';

  const payload = {};
  for (var k in hwConfig) payload[k] = hwConfig[k];
  payload.participant_id = pid;

  try {
    const res = await fetch('/configure-hardware', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
    });

    if (res.ok) {
      window.location.href = '/';
    } else {
      btn.disabled = false;
      btn.textContent = 'Confirm Hardware & Enter Dashboard';
      alert('Server error saving config. Check terminal.');
    }
  } catch(e) {
    btn.disabled = false;
    btn.textContent = 'Confirm Hardware & Enter Dashboard';
    alert('Network error: ' + e);
  }
}

// ── Init ──────────────────────────────────────────────────────
updateScores();
updateStep1NextButton();
updateConfirmButton();
restoreHMIOnLoad();
startStatusPoll();

document.getElementById('participant-id').addEventListener('input', function() {
  updateStep1NextButton();
  updateConfirmButton();
});
