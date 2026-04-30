/* ═══════════════════════════════════════════════════
   ARCADE AI — Frontend SSE Client
   Cinematic Dark AI UI
   ═══════════════════════════════════════════════════ */

// ─── Global state ───
let eventSource = null;
let completedAgents = 0;
let currentGameBasename = null;
let timerInterval = null;
let timerStart = null;

const PHASE_ORDER = ['SUPPORT', 'PHASE1', 'PHASE2', 'PHASE3', 'PHASE4', 'PHASE5', 'COORDINATEUR'];
const ESTIMATED_TOTAL = 24;

// phase → { label, status, agents: { name → { status, score, description } } }
const phases = {};

// Phase display labels
const PHASE_LABELS = {
  PHASE1: 'Intelligence',
  PHASE2: 'Design',
  PHASE3: 'Generation',
  PHASE4: 'Evaluation',
  PHASE5: 'Iteration',
  SUPPORT: 'Support',
  COORDINATEUR: 'Coordinator',
};

// ─── Init ───
document.addEventListener('DOMContentLoaded', () => {
  const input = document.getElementById('prompt');
  if (input) {
    input.addEventListener('input', () => {
      document.getElementById('char-count').textContent = input.value.length;
    });
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) startGeneration();
    });
  }
});

// ─── Game type chip selector ───
function setGameType(type, btn) {
  const sel = document.getElementById('game-type');
  if (sel) sel.value = type;
  document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
  if (btn) btn.classList.add('active');
}

// ─── Start generation ───
function startGeneration(quickMode = false) {
  const prompt = (document.getElementById('prompt')?.value || '').trim();
  const gameType = document.getElementById('game-type')?.value || 'tout type';

  if (!prompt) {
    const textarea = document.getElementById('prompt');
    if (textarea) {
      textarea.style.animation = 'none';
      textarea.offsetHeight; // force reflow
      textarea.style.animation = 'shake 0.4s ease';
      textarea.style.borderColor = 'rgba(220,80,80,0.4)';
      setTimeout(() => { textarea.style.animation = ''; textarea.style.borderColor = ''; }, 600);
    }
    return;
  }

  // Reset state
  completedAgents = 0;
  currentGameBasename = null;
  Object.keys(phases).forEach(k => delete phases[k]);
  _stopTimer();

  // Update UI
  setSection('progress');
  updateProgress(0);
  document.getElementById('current-phase-title').textContent = 'Connecting to pipeline...';
  document.getElementById('phases-container').innerHTML = '';
  document.getElementById('log-tail').innerHTML = '';
  document.getElementById('global-score-badge').classList.add('hidden');
  document.getElementById('iteration-badge').classList.add('hidden');

  const btn = document.getElementById('generate-btn');
  const qBtn = document.getElementById('quick-btn');
  if (btn) btn.disabled = true;
  if (qBtn) qBtn.disabled = true;

  const graphicStyle = document.getElementById('graphic-style')?.value || '';
  const apiEndpoint = quickMode ? '/api/quick-generate' : '/api/generate';

  fetch(apiEndpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt, game_type: gameType, graphic_style: graphicStyle }),
  })
    .then(r => r.json())
    .then(data => {
      if (data.error) { showFatalError(data.error); return; }
      connectSSE(data.session_id);
    })
    .catch(err => showFatalError(err.message));
}

// ─── SSE connection ───
function connectSSE(sessionId) {
  _previewSessionId = sessionId;
  if (eventSource) eventSource.close();
  eventSource = new EventSource(`/api/stream/${sessionId}`);

  eventSource.onmessage = (e) => {
    try {
      const event = JSON.parse(e.data);
      handleEvent(event);
    } catch (err) {
      console.error('SSE parse error:', err);
    }
  };

  eventSource.onerror = () => {
    addLog('err', 'SSE connection interrupted.');
    eventSource.close();
  };
}

// ─── Live preview ───
let _previewSessionId = null;

function showLivePreview(sessionId) {
  _previewSessionId = sessionId;
  const bar = document.getElementById('preview-bar');
  if (bar) bar.classList.remove('hidden');
}

function openPreview() {
  if (_previewSessionId) {
    window.open(`/api/preview/${_previewSessionId}`, '_blank');
  }
}

// ─── Event handler ───
function handleEvent(event) {
  switch (event.type) {
    case 'connected':
      addLog('ok', 'Pipeline connected — waiting for agents...');
      break;
    case 'timer_start':
      _startTimer();
      break;
    case 'code_ready':
      addLog('ok', `Code generated (${event.data?.size ? Math.round(event.data.size/1024)+'KB' : '?'}) — preview available`);
      if (_previewSessionId) showLivePreview(_previewSessionId);
      break;
    case 'phase_start':
      onPhaseStart(event.data);
      break;
    case 'agent_start':
      onAgentStart(event.data);
      break;
    case 'agent_done':
      onAgentDone(event.data);
      break;
    case 'score':
      onScore(event.data);
      break;
    case 'success':
      addLog('ok', event.data.message);
      break;
    case 'warning':
      addLog('warn', '! ' + event.data.message);
      break;
    case 'error':
      addLog('err', 'x ' + (event.data.message || 'Unknown error'));
      break;
    case 'complete':
      _stopTimer();
      onComplete(event.data);
      if (eventSource) { eventSource.close(); eventSource = null; }
      break;
    case 'timeout':
      _stopTimer();
      addLog('warn', 'Timeout — generation took too long.');
      if (eventSource) { eventSource.close(); eventSource = null; }
      break;
    case 'end':
      _stopTimer();
      if (eventSource) { eventSource.close(); eventSource = null; }
      break;
    default:
      if (event.data?.message) addLog('', event.data.message);
  }
}

// ─── Phase start ───
function onPhaseStart(data) {
  const { phase, title } = data;
  document.getElementById('current-phase-title').textContent = title || PHASE_LABELS[phase] || phase;

  if (title && title.match(/it[eé]ration/i)) {
    const m = title.match(/\d+/);
    const num = m ? m[0] : '1';
    document.getElementById('iteration-num').textContent = num;
    document.getElementById('iteration-badge').classList.remove('hidden');
  }

  if (phase && !phases[phase]) {
    phases[phase] = { label: PHASE_LABELS[phase] || title || phase, status: 'active', agents: {} };
    renderPhaseBlock(phase);
  }
}

// ─── Agent start ───
function onAgentStart(data) {
  const { agent, phase, description } = data;
  const p = ensurePhase(phase);
  p.agents[agent] = { status: 'running', score: null, description };
  renderAgentItem(phase, agent, 'running', null);
  markPhaseDot(phase, 'active');
  addLog('', `${agent}${description ? ' — ' + description.slice(0, 60) : ''}`);
}

// ─── Agent done ───
function onAgentDone(data) {
  const { agent, phase, result } = data;
  const p = ensurePhase(phase);
  if (p.agents[agent]) p.agents[agent].status = 'done';
  completedAgents++;
  const pct = Math.min(97, Math.round((completedAgents / ESTIMATED_TOTAL) * 100));
  updateProgress(pct);
  renderAgentItem(phase, agent, 'done', p.agents[agent]?.score);
  addLog('ok', `${agent}${result ? ' — ' + result.slice(0, 60) : ''}`);
}

// ─── Score ───
function onScore(data) {
  const { label, value, phase } = data;

  if (phase && phases[phase]) {
    const p = phases[phase];
    for (const [name, info] of Object.entries(p.agents)) {
      if (name.toLowerCase().includes(label.toLowerCase()) ||
          label.toLowerCase().includes(name.toLowerCase())) {
        info.score = value;
        renderAgentItem(phase, name, info.status, value);
        break;
      }
    }
  }

  if (label.toLowerCase().includes('global') || label.toLowerCase().includes('total')) {
    updateGlobalScore(value);
  }
}

// ─── Complete ───
function onComplete(data) {
  updateProgress(100);

  const btn = document.getElementById('generate-btn');
  const qBtn = document.getElementById('quick-btn');
  if (btn) btn.disabled = false;
  if (qBtn) qBtn.disabled = false;

  if (data.erreur) {
    setSection('result');
    document.getElementById('result-error').classList.remove('hidden');
    document.getElementById('error-msg').textContent = data.erreur;
    return;
  }

  setSection('result');

  if (data.approuve && data.html_basename) {
    currentGameBasename = data.html_basename;
    document.getElementById('result-approved').classList.remove('hidden');
    document.getElementById('game-title-result').textContent = data.titre || 'Game generated';
    const scoreEl = document.getElementById('result-score-num');
    if (scoreEl) scoreEl.textContent = (data.score || 0).toFixed(1);
    const durEl = document.getElementById('result-duration');
    if (durEl && data.duree) durEl.textContent = _formatDuration(data.duree);

    loadFinalScores();

    if (data.recommandations && data.recommandations.length) {
      renderApprovedRecs(data.recommandations);
    }
  } else {
    document.getElementById('result-rejected').classList.remove('hidden');
    document.getElementById('game-title-rejected').textContent = data.titre || 'Not saved';
    const rejScore = document.getElementById('result-score-rejected');
    if (rejScore) rejScore.textContent = (data.score || 0).toFixed(1);

    if (data.scores_detail) renderDiagScores(data.scores_detail);
    if (data.issues && data.issues.length) renderDiagIssues(data.issues);
    if (data.recommandations && data.recommandations.length) renderDiagRecs(data.recommandations);
  }
}

// ─── Load final scores from history ───
function loadFinalScores() {
  fetch('/api/history')
    .then(r => r.json())
    .then(games => {
      if (!currentGameBasename) return;
      const game = games.find(g => g.html_basename === currentGameBasename);
      if (!game) return;

      const s = game.scores || {};
      const scoreLabels = {
        technique: 'Technique',
        gameplay: 'Gameplay',
        visuel: 'Visual',
        execution: 'Execution',
        playtester: 'Playtester',
        anti_pattern: 'Anti-pattern',
        benchmark: 'Benchmark',
      };

      const grid = document.getElementById('scores-grid');
      let html = '';
      for (const [key, label] of Object.entries(scoreLabels)) {
        const val = s[key];
        if (val === undefined) continue;
        const cls = val >= 8 ? 'good' : val >= 6 ? 'mid' : 'bad';
        const pct = (val / 10 * 100).toFixed(0);
        const fillColor = val >= 8 ? 'rgba(100,220,100,0.85)' : val >= 6 ? 'rgba(220,180,50,0.85)' : 'rgba(220,80,80,0.85)';
        html += `<div class="score-card">
          <div class="score-card-label">${label}</div>
          <div class="score-card-value ${cls}">${val.toFixed(1)}</div>
          <div class="score-card-bar">
            <div class="score-card-bar-fill" style="width:${pct}%;background:${fillColor}"></div>
          </div>
        </div>`;
      }
      if (grid) grid.innerHTML = html;
    })
    .catch(() => {});
}

// ─── Play game ───
function playGame() {
  if (currentGameBasename) {
    window.open(`/play/${currentGameBasename}`, '_blank');
  }
}

// ─── Reset generator ───
function resetGenerator() {
  if (eventSource) { eventSource.close(); eventSource = null; }
  completedAgents = 0;
  currentGameBasename = null;
  Object.keys(phases).forEach(k => delete phases[k]);

  const input = document.getElementById('prompt');
  if (input) input.value = '';
  const charCount = document.getElementById('char-count');
  if (charCount) charCount.textContent = '0';
  const styleSelect = document.getElementById('graphic-style');
  if (styleSelect) styleSelect.value = '';

  const btn = document.getElementById('generate-btn');
  const qBtn2 = document.getElementById('quick-btn');
  if (btn) btn.disabled = false;
  if (qBtn2) qBtn2.disabled = false;

  ['result-approved', 'result-rejected', 'result-error'].forEach(id => {
    document.getElementById(id)?.classList.add('hidden');
  });
  document.getElementById('preview-bar')?.classList.add('hidden');

  setSection('hero');
}

// ─── Section management ───
function setSection(name) {
  const hero = document.getElementById('view-hero');
  const progress = document.getElementById('progress-section');
  const result = document.getElementById('result-section');
  [hero, progress, result].forEach(el => { if (el) el.classList.add('hidden'); });
  if (name === 'hero' || name === 'idle') {
    if (hero) hero.classList.remove('hidden');
  } else if (name === 'progress') {
    if (progress) progress.classList.remove('hidden');
  } else if (name === 'result') {
    if (result) result.classList.remove('hidden');
  }
}

// ─── Progress ───
function updateProgress(pct) {
  const bar = document.getElementById('progress-bar');
  const pctEl = document.getElementById('progress-pct');
  if (bar) bar.style.width = pct + '%';
  if (pctEl) pctEl.textContent = pct + '%';
}

function updateGlobalScore(value) {
  const badge = document.getElementById('global-score-badge');
  const scoreEl = document.getElementById('score-value');
  if (badge && scoreEl) {
    scoreEl.textContent = typeof value === 'number' ? value.toFixed(1) : value;
    badge.classList.remove('hidden');
  }
}

// ─── Log ───
function addLog(type, message) {
  const tail = document.getElementById('log-tail');
  if (!tail) return;
  const line = document.createElement('div');
  line.style.cssText = 'margin-bottom:2px;';
  if (type === 'ok') line.style.color = 'rgba(100,220,100,0.85)';
  else if (type === 'warn') line.style.color = 'rgba(220,180,50,0.85)';
  else if (type === 'err') line.style.color = 'rgba(220,80,80,0.85)';
  line.textContent = message;
  tail.appendChild(line);
  tail.scrollTop = tail.scrollHeight;
  while (tail.children.length > 30) tail.removeChild(tail.firstChild);
}

function showFatalError(msg) {
  setSection('result');
  document.getElementById('result-error').classList.remove('hidden');
  document.getElementById('error-msg').textContent = msg;
  const btn = document.getElementById('generate-btn');
  if (btn) btn.disabled = false;
}

// ─── Phase rendering ───
function ensurePhase(phase) {
  if (!phases[phase]) {
    phases[phase] = { label: PHASE_LABELS[phase] || phase, status: 'active', agents: {} };
    renderPhaseBlock(phase);
  }
  return phases[phase];
}

function renderPhaseBlock(phase) {
  const container = document.getElementById('phases-container');
  if (!container) return;
  if (document.getElementById(`phase-block-${phase}`)) return;

  const label = PHASE_LABELS[phase] || phase;

  const block = document.createElement('div');
  block.className = 'phase-item';
  block.id = `phase-block-${phase}`;
  block.innerHTML = `
    <div class="phase-header" onclick="togglePhase('${phase}')">
      <div class="phase-dot active" id="phase-dot-${phase}"></div>
      <span class="phase-label active" id="phase-label-${phase}">${label}</span>
      <span class="phase-chevron open" id="phase-chevron-${phase}">›</span>
    </div>
    <div class="agents-list" id="agents-list-${phase}"></div>
  `;
  container.appendChild(block);
}

function togglePhase(phase) {
  const list = document.getElementById(`agents-list-${phase}`);
  const chevron = document.getElementById(`phase-chevron-${phase}`);
  if (!list) return;
  const isOpen = !list.classList.contains('hidden');
  if (isOpen) {
    list.classList.add('hidden');
    if (chevron) chevron.classList.remove('open');
  } else {
    list.classList.remove('hidden');
    if (chevron) chevron.classList.add('open');
  }
}

function markPhaseDot(phase, status) {
  const dot = document.getElementById(`phase-dot-${phase}`);
  const label = document.getElementById(`phase-label-${phase}`);
  if (dot) {
    dot.className = 'phase-dot';
    if (status === 'active') dot.classList.add('active');
    else if (status === 'done') dot.classList.add('done');
  }
  if (label) {
    label.className = 'phase-label';
    if (status === 'active') label.classList.add('active');
    else if (status === 'done') label.classList.add('done');
  }
}

function renderAgentItem(phase, agent, status, score) {
  const listId = `agents-list-${phase}`;
  let list = document.getElementById(listId);
  if (!list) {
    ensurePhase(phase);
    list = document.getElementById(listId);
    if (!list) return;
  }

  const itemId = `agent-item-${phase}-${agent.replace(/\s+/g, '-')}`;
  let item = document.getElementById(itemId);

  const statusChar = status === 'running' ? '◌' : status === 'done' ? '✓' : status === 'warn' ? '!' : '·';
  const statusClass = status === 'running' ? 'running' : status === 'done' ? 'done' : status === 'warn' ? 'warn' : 'pending';

  let scoreBadge = '';
  if (score !== null && score !== undefined) {
    const cls = score >= 8 ? 'good' : score >= 6 ? 'mid' : 'bad';
    scoreBadge = `<span class="agent-score-badge ${cls}">${score.toFixed(1)}</span>`;
  }

  const html = `
    <span class="agent-status ${statusClass}">${statusChar}</span>
    <span class="agent-name${status === 'running' ? ' running' : ''}">${agent}</span>
    ${scoreBadge}
  `;

  if (item) {
    item.innerHTML = html;
  } else {
    item = document.createElement('div');
    item.id = itemId;
    item.className = 'agent-item';
    item.innerHTML = html;
    list.appendChild(item);
  }

  // Mark phase as done once all visible agents are done
  if (status === 'done') {
    const p = phases[phase];
    if (p) {
      const allDone = Object.values(p.agents).every(a => a.status === 'done');
      if (allDone) markPhaseDot(phase, 'done');
    }
  }
}

// ─── Diagnostic: detailed scores ───
function renderDiagScores(scores) {
  const grid = document.getElementById('diag-scores-grid');
  if (!grid) return;
  const labels = {
    technique: 'Technique', gameplay: 'Gameplay', visuel: 'Visual',
    execution: 'Execution', playtester: 'Playtester',
    anti_pattern: 'Anti-pattern', benchmark: 'Benchmark',
  };
  let html = '';
  for (const [key, label] of Object.entries(labels)) {
    const val = scores[key];
    if (val === undefined) continue;
    const cls = val >= 7 ? 'ok' : val >= 5 ? 'warn' : 'bad';
    html += `<div class="diag-score-item">
      <div class="diag-score-name">${label}</div>
      <div class="diag-score-val ${cls}">${val.toFixed(1)}</div>
    </div>`;
  }
  grid.innerHTML = html;
}

// ─── Diagnostic: issues ───
function renderDiagIssues(issues) {
  const list = document.getElementById('diag-issues-list');
  const section = document.getElementById('diag-issues-section');
  if (!list || !section) return;
  let html = '';
  for (const issue of issues.slice(0, 4)) {
    const sev = issue.severite || 'mineur';
    const sevLabel = sev === 'critique' ? 'CRITICAL' : sev === 'majeur' ? 'MAJOR' : 'MINOR';
    html += `<li class="issue-item">
      <span class="issue-badge ${sev}">${sevLabel}</span>
      <span class="issue-text">${escHtml(issue.description || '')}</span>
    </li>`;
  }
  list.innerHTML = html;
  section.classList.remove('hidden');
}

// ─── Diagnostic: recs (rejected) ───
function renderDiagRecs(recs) {
  const grid = document.getElementById('diag-recs-grid');
  const section = document.getElementById('diag-recs-section');
  if (!grid || !section) return;
  grid.innerHTML = recs.map(r => recCardHtml(r)).join('');
  section.classList.remove('hidden');
}

// ─── Recs (approved) ───
function renderApprovedRecs(recs) {
  const grid = document.getElementById('approved-recs-grid');
  const section = document.getElementById('approved-tips');
  if (!grid || !section) return;
  grid.innerHTML = recs.map(r => recCardHtml(r)).join('');
  section.classList.remove('hidden');
}

function recCardHtml(r) {
  const texte = (r.texte || '').replace(/'/g, "\\'");
  const displayText = r.label ? `<strong style="color:#fff;font-size:12px;display:block;margin-bottom:2px">${escHtml(r.label)}</strong>` : '';
  return `<div class="rec-card" onclick="applyRec('${texte}')">
    <div class="rec-text">${displayText}${escHtml(r.texte || '')}</div>
    <span class="rec-action">Use →</span>
  </div>`;
}

// ─── Apply recommendation to input ───
function applyRec(texte) {
  const input = document.getElementById('prompt');
  if (!input) return;
  input.value = texte;
  const charCount = document.getElementById('char-count');
  if (charCount) charCount.textContent = texte.length;
  resetGenerator();
  input.focus();
}

// ─── Timer ───
function _startTimer() {
  timerStart = Date.now();
  _renderTimer(0);
  if (timerInterval) clearInterval(timerInterval);
  timerInterval = setInterval(() => {
    const elapsed = Math.floor((Date.now() - timerStart) / 1000);
    _renderTimer(elapsed);
  }, 1000);
}

function _stopTimer() {
  if (timerInterval) { clearInterval(timerInterval); timerInterval = null; }
}

function _renderTimer(seconds) {
  const el = document.getElementById('elapsed-timer');
  if (!el) return;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  el.textContent = m > 0 ? `${m}m ${String(s).padStart(2,'0')}s` : `${s}s`;
}

function _formatDuration(seconds) {
  if (!seconds) return '';
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m > 0 ? `${m}m ${String(s).padStart(2,'0')}s` : `${s}s`;
}

function escHtml(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
