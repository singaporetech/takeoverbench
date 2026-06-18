// ── UI rendering helpers (no state, no fetch) ──

function showVideoFeed() {
  const img = document.getElementById('video-feed');
  img.src = '/video_feed?' + Date.now();
  img.style.display = 'block';
  document.getElementById('no-feed').style.display = 'none';
}

function hideVideoFeed() {
  const img = document.getElementById('video-feed');
  img.src = '';
  img.style.display = 'none';
  document.getElementById('no-feed').style.display = 'flex';
}

function addLog(msg, type) {
  // Event log display removed — no-op kept for call-site compat.
}

function setControlMode(mode) {
  const apHud = document.getElementById('hud-ap');
  if (!apHud) return;
  var badge = document.getElementById('autopilot-badge');
  if (mode === 'auto') {
    apHud.textContent = 'AUTO';
    apHud.className = 'hud-badge';
    if (badge) { badge.className = 'autopilot-badge auto'; badge.textContent = '⟳ AUTO'; }
  } else if (mode === 'human') {
    apHud.textContent = 'HUMAN';
    apHud.className = 'hud-badge ok';
    if (badge) { badge.className = 'autopilot-badge human'; badge.textContent = '◉ HUMAN'; }
  } else {
    apHud.textContent = 'IDLE';
    apHud.className = 'hud-badge';
    if (badge) { badge.className = 'autopilot-badge idle'; badge.textContent = '⏸ IDLE'; }
  }
}

function showTORBanner() {
  if (torShown) return;
  torShown = true;
  const b = document.getElementById('tor-banner');
  b.style.display = 'block';
  setTimeout(function() { b.style.display = 'none'; }, 3000);
}

function renderScenarioSets() {
  const el = document.getElementById('sets-list');
  if (!allScenarioSets.length) {
    el.innerHTML = '<div class="queue-empty">No sets available</div>';
    return;
  }
  el.innerHTML = allScenarioSets.map(function(s) {
    const isActive = (s.id === activeSetId);
    return '<div class="set-card' + (isActive ? ' active' : '') + '" onclick="loadScenarioSet(\'' + s.id + '\')">'
      + '<div class="set-card-info">'
      + '<div class="set-name">' + s.name + '</div>'
      + '<div class="set-meta">' + s.preset_ids.length + ' runs · ~' + s.estimated_minutes + ' min · ' + (s.builtin ? 'built-in' : 'custom') + '</div>'
      + '</div>'
      + '<button class="set-load-btn" onclick="event.stopPropagation();loadScenarioSet(\'' + s.id + '\')">'
      + (isActive ? 'LOADED' : 'LOAD') + '</button>'
      + '</div>';
  }).join('');

  // Update active set header in Card 1
  var header = document.getElementById('active-set-header');
  var nameEl = document.getElementById('active-set-name-display');
  if (activeSetId && activeSetName) {
    header.style.display = 'flex';
    nameEl.textContent = activeSetName;
  } else {
    header.style.display = 'none';
  }
}

function renderQueue() {
  const list = document.getElementById('queue-list');
  const countEl = document.getElementById('queue-count');
  const startBtn = document.getElementById('btn-start');

  if (queuedIds.length === 0) {
    list.innerHTML = '<div class="queue-empty">No scenarios queued</div>';
    countEl.textContent = '';
    startBtn.disabled = true;
    return;
  }

  startBtn.disabled = !(queuedIds.length > 0 && isCarlaConnected);
  countEl.textContent = '(' + queuedIds.length + ')';

  list.innerHTML = queuedIds.map(function(pid, i) {
    const p = allPresets.find(function(x) { return x.id === pid; });
    const isCurrent = (i === activePresetIndex && isRecording);
    const isTraining = p && p.is_training;
    var nodeClass = 'timeline-node';
    if (isCurrent) {
      nodeClass += ' current';
    } else if (isTraining) {
      nodeClass += ' orange';
    }
    var nodeContent = isCurrent ? '▶' : (isTraining ? 'T' : (i + 1));

    var html = '<div class="timeline-item' + (isCurrent ? ' current' : '') + '">'
      + '<div class="' + nodeClass + '">' + nodeContent + '</div>'
      + '<div class="timeline-line"></div>'
      + '<div class="timeline-content">'
      + '<div class="timeline-name">' + (p ? p.name : 'Preset ' + pid) + '</div>'
      + '<div class="timeline-meta">'
      + 'TTC: ' + (p ? p.tor_ttc : '--') + ' · Obstacle: ' + (p ? p.obstacle_distance : '--')
      + '</div>'
      + '</div>'
      + '</div>';
    return html;
  }).join('');
}

function updateActiveScenarioInfo(preset) {
  document.getElementById('active-scenario-info').innerHTML =
    'Name: ' + preset.name + '<br>'
    + 'Speed: ' + preset.speed_kmh + ' km/h<br>'
    + 'TTC Threshold: ' + preset.tor_ttc + ' s<br>'
    + 'Obstacle: ' + preset.obstacle_distance + ' m<br>'
    + 'Weather: ' + preset.weather + '<br>'
    + 'SAE Level: ' + preset.sae_level;
}

function renderHardwareScores(hw) {
  // Right panel removed — safety guard
  if (!document.getElementById('hw-visual')) return;
  if (!hw || hw.visual_score === undefined || hw.visual_score === null) return;
  document.getElementById('hw-visual').innerHTML = hw.visual_score + '<span class="fscore-max">/5</span>';
  document.getElementById('hw-motion').innerHTML = hw.motion_score + '<span class="fscore-max">/5</span>';
  document.getElementById('hw-physical').innerHTML = hw.physical_score + '<span class="fscore-max">/5</span>';
  const wList = document.getElementById('hw-warnings');
  if (wList.children.length === 0 && hw.warnings && hw.warnings.length > 0) {
    wList.innerHTML = hw.warnings.map(function(w) {
      return '<div class="warning-item ' + w.level + '">'
        + '<span class="warning-aspect">' + w.aspect.toUpperCase() + '</span>'
        + w.message + '</div>';
    }).join('');
  }
  const fb = document.getElementById('dash-fidelity-badge');
  if (hw.fidelity_level) {
    fb.textContent = hw.fidelity_level + ' -- ' + hw.fidelity_total + '/15';
    fb.style.color = hw.fidelity_level === 'High' ? 'var(--accent)'
                   : hw.fidelity_level === 'Medium' ? 'var(--ok)'
                   : hw.fidelity_level === 'Low' ? 'var(--warn)'
                   : 'var(--text-dim)';
  }
}

function renderPhaseBadge() {
  // Phase badge removed from UI — no-op.
}

function renderParticipantID(pid) {
  var el = document.getElementById('lbl-participant');
  if (el) el.textContent = pid ? 'ID: ' + pid : 'ID: --';
}

function renderCountdown(data) {
  const cd = document.getElementById('lbl-countdown');
  if (!cd) return;
  if (data.tor_phase === 'coasting' && data.tor_countdown_s > 0) {
    cd.textContent = 'Countdown: ' + data.tor_countdown_s.toFixed(1) + 's';
    cd.style.display = '';
  } else if (data.tor_phase === 'auto_ended') {
    cd.textContent = 'Scenario Ended';
    cd.style.display = '';
  } else {
    cd.style.display = 'none';
  }
}

function renderTelemetry(t) {
  if (!t || Object.keys(t).length === 0) return;
  const speed = t.speed_kmh !== undefined && t.speed_kmh !== null ? t.speed_kmh.toFixed(1) : '--';
  const steer = t.steer !== undefined && t.steer !== null ? t.steer.toFixed(3) : '--';
  const ttc   = t.ttc !== undefined ? t.ttc : 999;
  const ttcD  = ttc < 999 ? ttc.toFixed(1) : '--';

  document.getElementById('hud-ttc').textContent = 'TTC ' + ttcD + 's';
  document.getElementById('hud-ttc').className = 'hud-badge' + (ttc < 3 ? ' danger' : ttc < 6 ? ' warn' : '');
  document.getElementById('hud-speed').textContent = speed + ' km/h';
  document.getElementById('hud-steer').textContent = 'STR ' + steer;
}
