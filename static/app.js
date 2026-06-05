/**
 * AgentForge Web GUI — Frontend Logic
 */

const API = '/api';
let currentTab = 'output';
let currentSessionId = null;
let pollTimer = null;

// ── Init ──

document.addEventListener('DOMContentLoaded', () => {
  checkHealth();
  loadAgents();
  loadPipelines();
  loadSessions();
  loadConfig();
});

// ── Health check ──

async function checkHealth() {
  const dot = document.getElementById('status-dot');
  const text = document.getElementById('status-text');
  const apiStatus = document.getElementById('api-status');

  try {
    const resp = await fetch(`${API}/health`);
    const data = await resp.json();
    dot.className = 'status-dot online';
    text.textContent = `Connected (v${data.version})`;
    apiStatus.textContent = `API: v${data.version}`;
  } catch (e) {
    dot.className = 'status-dot offline';
    text.textContent = 'Disconnected';
    apiStatus.textContent = 'API: offline';
  }
}

// ── Agents ──

async function loadAgents() {
  try {
    const resp = await fetch(`${API}/agents`);
    const agents = await resp.json();
    const container = document.getElementById('agents-list');

    const icons = {
      coder: '🔧', reviewer: '🔍', bugfixer: '🐛', tester: '🧪',
    };

    container.innerHTML = Object.entries(agents).map(([name, info]) => `
      <div class="agent-item">
        <div class="agent-icon ${name}">${icons[name] || '🤖'}</div>
        <div>
          <div class="agent-name">${name}</div>
          <div class="agent-model">${info.model} via ${info.provider}</div>
        </div>
      </div>
    `).join('');
  } catch (e) {
    document.getElementById('agents-list').innerHTML =
      '<span class="muted">Failed to load agents</span>';
  }
}

// ── Pipelines ──

async function loadPipelines() {
  try {
    const resp = await fetch(`${API}/pipelines`);
    const pipelines = await resp.json();
    const select = document.getElementById('pipeline-select');
    select.innerHTML = Object.entries(pipelines).map(([name, info]) =>
      `<option value="${name}">${name} — ${info.description}</option>`
    ).join('');
  } catch (e) {
    // Keep default option
  }
}

// ── Run Pipeline ──

async function runPipeline() {
  const task = document.getElementById('task-input').value.trim();
  const pipeline = document.getElementById('pipeline-select').value;
  const mock = document.getElementById('mock-checkbox').checked;

  if (!task) {
    alert('Please enter a task description.');
    return;
  }

  const btn = document.getElementById('run-btn');
  btn.disabled = true;
  btn.textContent = '⏳ Running...';

  const dot = document.getElementById('status-dot');
  dot.className = 'status-dot busy';

  // Reset progress
  document.getElementById('progress-stages').innerHTML =
    '<span class="muted">Starting pipeline...</span>';
  document.getElementById('progress-bar-wrapper').classList.remove('hidden');
  document.getElementById('progress-bar').style.width = '0%';
  document.getElementById('output-view').textContent = 'Running...';

  try {
    const resp = await fetch(`${API}/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task, pipeline, mock }),
    });

    const data = await resp.json();
    if (data.error) {
      showError(data.error);
      return;
    }

    currentSessionId = data.session_id;
    document.getElementById('output-view').textContent =
      `Session: ${data.session_id}\nPipeline started — polling for results...\n`;

    // Start polling for results
    startPolling(data.session_id);

  } catch (e) {
    showError(`Failed to run pipeline: ${e.message}`);
  } finally {
    btn.disabled = false;
    btn.textContent = '▶ Run Pipeline';
    document.getElementById('status-dot').className = 'status-dot online';
  }
}

function startPolling(sessionId) {
  if (pollTimer) clearInterval(pollTimer);

  let dots = 0;
  pollTimer = setInterval(async () => {
    try {
      const resp = await fetch(`${API}/status/${sessionId}`);
      const data = await resp.json();

      if (data.error) {
        clearInterval(pollTimer);
        document.getElementById('output-view').textContent +=
          `\n[ERROR] Session not found: ${data.error}`;
        return;
      }

      // Update progress
      updateProgress(data);

      // Update output
      if (data.stages && Object.keys(data.stages).length > 0) {
        let output = `Session: ${sessionId}\nStatus: ${data.status}\n\n`;
        for (const [id, stage] of Object.entries(data.stages)) {
          const status = stage.success ? '✓' : '✗';
          output += `[${status}] ${id} (${stage.agent}, ${stage.duration_ms}ms)\n`;
          if (stage.stdout_preview) {
            output += `${stage.stdout_preview}\n\n`;
          }
        }
        document.getElementById('output-view').textContent = output;

        // Load files if completed
        if (data.status === 'completed' || data.status === 'failed') {
          loadSessionFiles(sessionId);
        }
      } else {
        // Still running — show spinner dots
        dots = (dots + 1) % 4;
        const spinner = '⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'[dots * 3] || '⏳';
        document.getElementById('output-view').textContent =
          `Session: ${sessionId}\nStatus: ${data.status} ${spinner}\n`;
      }

      // Stop polling when done
      if (data.status === 'completed' || data.status === 'failed') {
        clearInterval(pollTimer);
        pollTimer = null;
        document.getElementById('status-dot').className =
          data.status === 'completed' ? 'status-dot online' : 'status-dot offline';
        document.getElementById('run-btn').disabled = false;
        document.getElementById('run-btn').textContent = '▶ Run Pipeline';

        // Reload sessions list
        loadSessions();
      }

    } catch (e) {
      // Keep polling
    }
  }, 1500);
}

function updateProgress(data) {
  const container = document.getElementById('progress-stages');
  const bar = document.getElementById('progress-bar');

  if (!data.stages || Object.keys(data.stages).length === 0) {
    container.innerHTML = `<span class="muted">Pipeline running...</span>`;
    bar.style.width = '10%';
    return;
  }

  const stages = data.stages;
  const stageNames = ['coding', 'review', 'bugfix', 'testing'];
  const displayNames = { coding: 'Code', review: 'Review', bugfix: 'Fix', testing: 'Test' };

  container.innerHTML = stageNames.map(name => {
    const stage = stages[name];
    let cls = 'stage-badge';
    if (!stage) return '';

    if (stage.success) cls += ' completed';
    else if (data.status === 'running') {
      // Check if this is the current stage
      const stageOrder = Object.keys(stages);
      const lastStage = stageOrder[stageOrder.length - 1];
      if (name === lastStage) cls += ' running';
    } else cls += ' failed';

    return `<span class="${cls}">${displayNames[name] || name}</span>`;
  }).filter(Boolean).join('');

  // Progress bar
  const total = stageNames.length;
  const completed = stageNames.filter(n => stages[n] && stages[n].success).length;
  const percent = Math.round((completed / total) * 100);
  bar.style.width = `${percent}%`;
}

function showError(msg) {
  document.getElementById('output-view').textContent = `[ERROR] ${msg}`;
  document.getElementById('run-btn').disabled = false;
  document.getElementById('run-btn').textContent = '▶ Run Pipeline';
  document.getElementById('status-dot').className = 'status-dot offline';
}

// ── Tabs ──

function switchTab(tabName) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

  document.querySelector(`.tab:nth-child(${
    ['output', 'files', 'sessions', 'config'].indexOf(tabName) + 1
  })`).classList.add('active');
  document.getElementById(`tab-${tabName}`).classList.add('active');
  currentTab = tabName;

  // Refresh content
  if (tabName === 'sessions') loadSessions();
  if (tabName === 'config') loadConfig();
  if (tabName === 'files' && currentSessionId) loadSessionFiles(currentSessionId);
}

// ── Files ──

async function loadSessionFiles(sessionId) {
  try {
    const resp = await fetch(`${API}/files/${sessionId}`);
    const files = await resp.json();

    if (files.error) {
      document.getElementById('files-view').innerHTML =
        `<span class="muted">${files.error}</span>`;
      return;
    }

    if (files.length === 0) {
      document.getElementById('files-view').innerHTML =
        '<span class="muted">No files produced yet.</span>';
      return;
    }

    const icons = {
      '.py': '🐍', '.js': '📜', '.ts': '📘', '.html': '🌐',
      '.css': '🎨', '.json': '📋', '.md': '📝', '.yaml': '⚙️',
      '.yml': '⚙️', '.txt': '📄',
    };

    document.getElementById('files-view').innerHTML = files.map(f => {
      const ext = '.' + f.path.split('.').pop();
      const icon = icons[ext] || '📄';
      return `
        <div class="file-entry" onclick="viewFile('${sessionId}', '${f.path}')">
          <span class="file-icon">${icon}</span>
          <span class="file-path">${f.path}</span>
          <span class="file-size">${formatSize(f.size)}</span>
        </div>
        <div id="file-content-${sanitizeId(f.path)}" class="file-content"></div>
      `;
    }).join('');
  } catch (e) {
    document.getElementById('files-view').innerHTML =
      '<span class="muted">Failed to load files.</span>';
  }
}

async function viewFile(sessionId, path) {
  const contentDiv = document.getElementById(`file-content-${sanitizeId(path)}`);

  // Toggle if already loaded
  if (contentDiv.classList.contains('open')) {
    contentDiv.classList.remove('open');
    return;
  }

  // Load content
  try {
    const resp = await fetch(`${API}/file/${sessionId}/${encodeURIComponent(path)}`);
    const data = await resp.json();

    if (data.error) {
      contentDiv.textContent = `Error: ${data.error}`;
    } else {
      contentDiv.textContent = data.content;
    }
    contentDiv.classList.add('open');
  } catch (e) {
    contentDiv.textContent = `Failed to load: ${e.message}`;
    contentDiv.classList.add('open');
  }
}

// ── Sessions ──

async function loadSessions() {
  try {
    const resp = await fetch(`${API}/sessions`);
    const sessions = await resp.json();

    if (sessions.length === 0) {
      document.getElementById('sessions-view').innerHTML =
        '<span class="muted">No sessions yet. Run a pipeline first!</span>';
      return;
    }

    document.getElementById('sessions-view').innerHTML = sessions.map(s => `
      <div class="session-entry" onclick="viewSession('${s.id}')">
        <div class="session-id">${s.id}</div>
        ${s.original_task ? `<div class="session-task">${escapeHtml(s.original_task)}</div>` : ''}
        <div class="session-meta">
          ${s.pipeline || '?'} |
          ${s.stages_success || 0}/${s.stages_count || 0} stages |
          ${s.timestamp || ''}
          ${s.has_summary ? '<span class="session-status completed">done</span>' : ''}
        </div>
      </div>
    `).join('');
  } catch (e) {
    document.getElementById('sessions-view').innerHTML =
      '<span class="muted">Failed to load sessions.</span>';
  }
}

async function viewSession(sessionId) {
  currentSessionId = sessionId;
  switchTab('output');

  try {
    const resp = await fetch(`${API}/status/${sessionId}`);
    const data = await resp.json();
    updateProgress(data);

    if (data.stages) {
      let output = `Session: ${sessionId}\n\n`;
      for (const [id, stage] of Object.entries(data.stages)) {
        const status = stage.success ? '✓' : '✗';
        output += `[${status}] ${id} (${stage.agent}, ${stage.duration_ms}ms)\n`;
        if (stage.stdout_preview) {
          output += `${stage.stdout_preview}\n\n`;
        }
      }
      document.getElementById('output-view').textContent = output;
    }

    loadSessionFiles(sessionId);
  } catch (e) {
    document.getElementById('output-view').textContent =
      `Failed to load session: ${e.message}`;
  }
}

// ── Config ──

async function loadConfig() {
  try {
    const resp = await fetch(`${API}/config`);
    const config = await resp.json();
    document.getElementById('config-view').textContent =
      JSON.stringify(config, null, 2);
  } catch (e) {
    document.getElementById('config-view').textContent =
      'Failed to load configuration.';
  }
}

// ── Quick actions ──

async function quickAction(action) {
  switch (action) {
    case 'doctor':
      try {
        const resp = await fetch(`${API}/health`);
        const data = await resp.json();
        alert(`AgentForge v${data.version}\nStatus: ${data.status}\nTimestamp: ${data.timestamp}`);
      } catch (e) {
        alert('API server is not reachable. Check if forge --gui is running.');
      }
      break;
    case 'review':
      document.getElementById('task-input').value = 'Review the code in the workspace for bugs, security issues, and style problems.';
      document.getElementById('pipeline-select').value = 'full_dev_cycle';
      break;
    case 'test':
      document.getElementById('task-input').value = 'Write and run comprehensive tests for the code in the workspace.';
      document.getElementById('pipeline-select').value = 'full_dev_cycle';
      break;
    case 'git-status':
      try {
        // This would need a git endpoint — just show a message for now
        alert('Git status: Use the CLI (/git status) or run "git status" in your workspace.');
      } catch (e) {}
      break;
  }
}

// ── Helpers ──

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}

function sanitizeId(str) {
  return str.replace(/[^a-zA-Z0-9-_.]/g, '_');
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
