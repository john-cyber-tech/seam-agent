"""
SSE message types emitted to the frontend:
  status               { message }
  stage                { stage: parsing|clustering|metrics|agent|complete }
  progress             { current, total }
  log                  { message, highlight? }
  add_node             { id, label, domain, node_type }
  add_edge             { from, to, relationship }
  cluster              { node, community }
  metrics              { node, betweenness, in_degree, out_degree, total_degree }
  highlight_cross_edge { from, to }
  file_parsed          {}
  agent_chunk          { text }
  plan_ready           { default_dir }
  complete             { message }
"""

import json
import queue
import threading
import time
import webbrowser
from pathlib import Path

try:
    from flask import Flask, Response, jsonify, redirect, request, stream_with_context
except ImportError:
    raise SystemExit(
        "Flask is required for live mode.\n"
        "Install it with: pip install flask"
    )

app = Flask(__name__)

# ── SSE pub/sub state ─────────────────────────────────────────────────────────
_subscribers: list[queue.Queue] = []
_lock = threading.Lock()

# ── Setup / config state ──────────────────────────────────────────────────────
_prefill: str = ""
_start_event = threading.Event()
_pending_folder: str = ""
_pending_plan: str = ""

# ── Setup page ────────────────────────────────────────────────────────────────
# __PREFILL__ is replaced server-side with json.dumps(_prefill)
_SETUP_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Seam</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: #0d1f1b; color: #e0e0e0;
  font-family: 'Menlo','Monaco','Consolas',monospace;
  min-height: 100vh; display: flex; align-items: center; justify-content: center;
}
.wrap { width: 100%; display: flex; justify-content: center; padding: 40px 20px; }
.card {
  width: 480px; background: #152e28; border: 1px solid #1e3d36;
  border-radius: 8px; padding: 40px 44px 36px;
}
.icon { font-size: 28px; color: #006B58; margin-bottom: 14px; }
h1 { font-size: 17px; font-weight: 600; color: #fff; margin-bottom: 8px; }
.sub { font-size: 11px; color: #888; line-height: 1.6; margin-bottom: 32px; }
label {
  display: flex; align-items: center; gap: 8px;
  font-size: 10px; color: #999; font-weight: 700; letter-spacing: 0.6px;
  text-transform: uppercase; margin-bottom: 7px;
}
.badge {
  font-size: 9px; font-weight: 700; letter-spacing: 0.4px;
  background: #253525; color: #5aa05a; border: 1px solid #406040;
  padding: 1px 6px; border-radius: 8px; text-transform: uppercase;
}

/* folder row */
.folder-row { display: flex; gap: 8px; margin-bottom: 6px; }
.folder-row input {
  flex: 1; margin: 0; background: #091512; border: 1px solid #1e3d36;
  color: #e0e0e0; font-family: inherit; font-size: 12px;
  padding: 10px 12px; border-radius: 4px; outline: none;
  transition: border-color 0.2s;
}
.folder-row input:focus { border-color: #006B58; }
.folder-row input::placeholder { color: #666; }
.browse-btn {
  flex-shrink: 0; background: #152e28; border: 1px solid #1e3d36;
  color: #aaa; font-family: inherit; font-size: 12px;
  padding: 0 14px; border-radius: 4px; cursor: pointer; white-space: nowrap;
  transition: background 0.15s, color 0.15s, border-color 0.15s;
}
.browse-btn:hover { background: #1a3530; color: #ddd; border-color: #555; }

.hint { font-size: 10px; color: #777; margin-bottom: 24px; line-height: 1.5; }
.start-btn {
  width: 100%; background: #006B58; color: #fff; border: none;
  font-family: inherit; font-size: 13px; font-weight: 600;
  padding: 12px; border-radius: 4px; cursor: pointer; margin-top: 6px;
  transition: background 0.2s;
}
.start-btn:hover:not(:disabled) { background: #007D68; }
.start-btn:disabled { background: #152e28; color: #666; cursor: not-allowed; }
.error { font-size: 11px; color: #cc4444; margin-top: 12px; min-height: 16px; line-height: 1.4; }

/* ── Folder picker modal ────────────────────────────────────────────────────── */
.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center; z-index: 100;
}
.picker-card {
  width: 540px; background: #152e28; border: 1px solid #1e3d36;
  border-radius: 7px; overflow: hidden;
  display: flex; flex-direction: column; max-height: 500px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.4);
}
.picker-header {
  background: #0d1f1b; border-bottom: 1px solid #1e3d36;
  padding: 10px 14px; display: flex; align-items: center; gap: 4px;
  overflow-x: auto; white-space: nowrap; flex-shrink: 0; min-height: 40px;
}
.picker-header::-webkit-scrollbar { height: 3px; }
.picker-header::-webkit-scrollbar-thumb { background: #555; border-radius: 2px; }
.bc-root { font-size: 11px; color: #888; cursor: pointer; padding: 2px 4px; border-radius: 3px; }
.bc-root:hover { color: #ccc; background: #1a3530; }
.bc-sep { font-size: 11px; color: #555; margin: 0 1px; user-select: none; }
.bc-seg {
  font-size: 11px; color: #999; cursor: pointer;
  padding: 2px 5px; border-radius: 3px; transition: background 0.1s, color 0.1s;
}
.bc-seg:hover { background: #1a3530; color: #ccc; }
.bc-seg.bc-current { color: #ccc; cursor: default; font-weight: 600; }
.bc-seg.bc-current:hover { background: transparent; }

.picker-list { flex: 1; overflow-y: auto; min-height: 0; }
.picker-item {
  display: flex; align-items: center; gap: 10px;
  padding: 9px 16px; font-size: 12px; cursor: pointer;
  border-bottom: 1px solid #102018; transition: background 0.1s; color: #ccc;
}
.picker-item:hover { background: #1a3530; }
.picker-item:last-child { border-bottom: none; }
.pi-icon { font-size: 13px; flex-shrink: 0; opacity: 0.8; }
.pi-arrow { font-size: 11px; color: #888; flex-shrink: 0; width: 13px; text-align: center; }
.pi-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.picker-parent .pi-name { color: #888; font-style: italic; }
.picker-empty { padding: 24px 16px; font-size: 11px; color: #777; text-align: center; }
.picker-loading { padding: 24px 16px; font-size: 11px; color: #777; text-align: center; }

.picker-footer {
  background: #0d1f1b; border-top: 1px solid #1e3d36;
  padding: 10px 14px; display: flex; align-items: center;
  justify-content: space-between; flex-shrink: 0; gap: 8px;
}
.picker-info { font-size: 10px; color: #777; flex: 1; }
.picker-btns { display: flex; gap: 8px; }
.btn-cancel {
  background: transparent; border: 1px solid #1e3d36; color: #999;
  font-family: inherit; font-size: 11px; padding: 6px 14px;
  border-radius: 4px; cursor: pointer; transition: border-color 0.15s, color 0.15s;
}
.btn-cancel:hover { border-color: #666; color: #ccc; }
.btn-select {
  background: #006B58; border: none; color: #fff;
  font-family: inherit; font-size: 11px; font-weight: 600;
  padding: 6px 14px; border-radius: 4px; cursor: pointer; transition: background 0.15s;
}
.btn-select:hover { background: #007D68; }

::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #1e3d36; border-radius: 2px; }
</style>
</head>
<body>
<div class="wrap">
  <div class="card">
    <div class="icon">&#x2B21;</div>
    <h1>Seam</h1>
    <p class="sub">
      Parse your Java monolith, detect natural service boundaries via<br>
      community detection, and generate a strangler-fig migration plan.
    </p>

    <label for="folder">Monolith source folder</label>
    <div class="folder-row">
      <input id="folder" type="text"
        placeholder="/path/to/your/java/repo"
        spellcheck="false" autocomplete="off" />
      <button class="browse-btn" onclick="openPicker()">Browse&hellip;</button>
    </div>

    <button class="start-btn" id="btn" onclick="go()">Start Analysis</button>
    <p class="error" id="err"></p>
  </div>
</div>

<!-- Folder picker modal -->
<div id="picker-modal" class="modal-overlay" style="display:none" onclick="overlayClick(event)">
  <div class="picker-card" onclick="event.stopPropagation()">
    <div class="picker-header" id="breadcrumb"></div>
    <div class="picker-list" id="picker-list">
      <div class="picker-loading">Loading&hellip;</div>
    </div>
    <div class="picker-footer">
      <span class="picker-info" id="picker-info"></span>
      <div class="picker-btns">
        <button class="btn-cancel" onclick="closePicker()">Cancel</button>
        <button class="btn-select" onclick="selectCurrent()">Select this folder</button>
      </div>
    </div>
  </div>
</div>

<script>
// __PREFILL__ is replaced server-side with json.dumps(_prefill)
const prefill = __PREFILL__;
if (prefill) {
  document.getElementById('folder').value = prefill;
  document.getElementById('btn').focus();
} else {
  document.getElementById('folder').focus();
}

document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closePicker();
  if (e.key === 'Enter' && document.getElementById('picker-modal').style.display === 'none') go();
});

// ── Form submission ───────────────────────────────────────────────────────────
async function go() {
  const folder = document.getElementById('folder').value.trim();
  const btn    = document.getElementById('btn');
  const err    = document.getElementById('err');

  if (!folder) { err.textContent = 'Please select or enter a folder path.'; return; }

  btn.disabled = true;
  btn.textContent = 'Validating...';
  err.textContent = '';

  try {
    const res  = await fetch('/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ folder }),
    });
    const data = await res.json();
    if (!res.ok) {
      err.textContent = data.error || 'Unknown error.';
      btn.disabled = false;
      btn.textContent = 'Start Analysis';
      return;
    }
    btn.textContent = 'Opening graph...';
    window.location.href = '/graph';
  } catch (_) {
    err.textContent = 'Could not reach the server.';
    btn.disabled = false;
    btn.textContent = 'Start Analysis';
  }
}

// ── Folder picker ─────────────────────────────────────────────────────────────
let pickerPath = '';

function openPicker() {
  document.getElementById('picker-modal').style.display = 'flex';
  const cur = document.getElementById('folder').value.trim();
  loadDir(cur || '');
}

function closePicker() {
  document.getElementById('picker-modal').style.display = 'none';
}

function overlayClick(e) {
  if (e.target === document.getElementById('picker-modal')) closePicker();
}

function selectCurrent() {
  document.getElementById('folder').value = pickerPath;
  closePicker();
  document.getElementById('btn').focus();
}

async function loadDir(path) {
  document.getElementById('picker-list').innerHTML =
    '<div class="picker-loading">Loading...</div>';
  document.getElementById('picker-info').textContent = '';

  // Separate network/parse errors from render errors so we can show the real message.
  let data;
  try {
    const res = await fetch('/browse?path=' + encodeURIComponent(path));
    if (!res.ok) throw new Error('Server error ' + res.status);
    data = await res.json();
  } catch (err) {
    document.getElementById('picker-list').innerHTML =
      '<div class="picker-empty">Could not load directory: ' + err.message + '</div>';
    return;
  }

  pickerPath = data.current;
  renderBreadcrumb(data.current);
  renderList(data.entries, data.parent);
}

function renderBreadcrumb(fullPath) {
  const bc = document.getElementById('breadcrumb');
  bc.innerHTML = '';

  const root = document.createElement('span');
  root.className = 'bc-root';
  root.textContent = '/';
  root.title = 'Filesystem root';
  root.onclick = () => loadDir('/');
  bc.appendChild(root);

  const parts = fullPath.split('/').filter(Boolean);
  let cum = '';
  parts.forEach((seg, i) => {
    cum += '/' + seg;
    const sep = document.createElement('span');
    sep.className = 'bc-sep';
    sep.textContent = '/';
    bc.appendChild(sep);

    const span = document.createElement('span');
    const last = i === parts.length - 1;
    span.className = 'bc-seg' + (last ? ' bc-current' : '');
    span.textContent = seg;
    if (!last) { const p = cum; span.onclick = () => loadDir(p); }
    bc.appendChild(span);
  });

  // Scroll right so the deepest segment is always visible
  bc.scrollLeft = bc.scrollWidth;
}

function renderList(entries, parent) {
  const list = document.getElementById('picker-list');
  list.innerHTML = '';

  if (parent !== null && parent !== undefined) {
    const row = document.createElement('div');
    row.className = 'picker-item picker-parent';
    row.innerHTML = '<span class="pi-arrow">&#x2191;</span>' +
                    '<span class="pi-name">Parent folder</span>';
    row.onclick = () => loadDir(parent);
    list.appendChild(row);
  }

  if (entries.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'picker-empty';
    empty.textContent = 'No subdirectories found';
    list.appendChild(empty);
  } else {
    entries.forEach(e => {
      const row = document.createElement('div');
      row.className = 'picker-item';
      const icon = document.createElement('span');
      icon.className = 'pi-icon';
      icon.textContent = '📁';
      const label = document.createElement('span');
      label.className = 'pi-name';
      label.textContent = e.name;
      row.appendChild(icon);
      row.appendChild(label);
      row.onclick = () => loadDir(e.path);
      list.appendChild(row);
    });
  }

  const n = entries.length;
  document.getElementById('picker-info').textContent =
    n + ' folder' + (n !== 1 ? 's' : '');
}
</script>
</body>
</html>"""

# ── Graph visualisation page ──────────────────────────────────────────────────
_GRAPH_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Seam — Live Analysis</title>
<script src="https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/marked@9.1.6/marked.min.js"></script>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: #0d1f1b; color: #e0e0e0;
  font-family: 'Menlo','Monaco','Consolas',monospace;
  overflow: hidden; height: 100vh; display: flex; flex-direction: column;
}

/* ── Header ── */
#hdr {
  height: 46px; background: #152e28; border-bottom: 1px solid #1e3d36;
  display: flex; align-items: center; padding: 0 18px; gap: 14px; flex-shrink: 0;
}
#hdr h1 { font-size: 14px; font-weight: 600; color: #fff; white-space: nowrap; }
#status {
  font-size: 11px; color: #999; flex: 1;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
#badge {
  padding: 2px 10px; border-radius: 9px; font-size: 10px; font-weight: 700;
  letter-spacing: 0.6px; background: #152e28; color: #888;
  transition: background 0.35s, color 0.35s; white-space: nowrap;
}

/* ── Progress bar ── */
#prog { height: 2px; background: #152e28; flex-shrink: 0; }
#prog-fill { height: 2px; background: #006B58; width: 0%; transition: width 0.3s ease; }

/* ── Main layout ── */
#main { flex: 1; display: flex; min-height: 0; }
#graph-wrap { flex: 1; min-width: 0; }
#graph { width: 100%; height: 100%; }

/* ── Sidebar ── */
#side {
  width: 355px; flex-shrink: 0; display: flex; flex-direction: column;
  border-left: 1px solid #152e28; background: #111c19;
}
#log { flex: 1; overflow-y: auto; padding: 8px 10px; min-height: 0; }
.le { font-size: 10.5px; color: #777; margin-bottom: 2px; line-height: 1.45; }
.le.hl { color: #ccc; }
.le.hl::before { content: '\25B8 '; color: #006B58; }

/* ── Agent panel ── */
#ap {
  flex: 0 0 48%; border-top: 1px solid #152e28;
  display: flex; flex-direction: column; min-height: 0;
}
#ap-hdr {
  padding: 8px 10px 5px; font-size: 10px; font-weight: 700;
  letter-spacing: 0.8px; color: #006B58; text-transform: uppercase; flex-shrink: 0;
}
#ao {
  flex: 1; overflow-y: auto; padding: 0 10px 10px;
  font-size: 11px; line-height: 1.65; color: #aaa; min-height: 0;
}
#ao h1 { font-size: 13px; color: #ddd; margin: 10px 0 5px; }
#ao h2 { font-size: 12px; color: #ccc; margin: 10px 0 5px; }
#ao h3 { font-size: 11px; color: #bbb; margin: 8px 0 4px; }
#ao p { margin-bottom: 5px; color: #aaa; }
#ao strong { color: #e0e0e0; }
#ao em { color: #bbb; }
#ao ul, #ao ol { padding-left: 15px; margin-bottom: 5px; }
#ao li { margin-bottom: 2px; }
#ao table { border-collapse: collapse; font-size: 10px; margin: 6px 0; width: 100%; }
#ao td, #ao th { border: 1px solid #1e3d36; padding: 3px 7px; text-align: left; }
#ao th { background: #132420; color: #999; }
#ao code { background: #132420; padding: 1px 4px; border-radius: 2px; font-size: 10px; color: #8ab4f8; }
#ao pre { background: #132420; padding: 8px; border-radius: 3px; margin: 5px 0; overflow-x: auto; }
#ao pre code { background: none; padding: 0; }
#ao hr { border: none; border-top: 1px solid #1a3530; margin: 8px 0; }
#ao blockquote { border-left: 2px solid #555; padding-left: 8px; color: #999; }

/* ── Stats bar ── */
#stats {
  height: 22px; background: #091512; border-top: 1px solid #152e28;
  display: flex; align-items: center; padding: 0 14px; gap: 18px; flex-shrink: 0;
}
.st { font-size: 10px; color: #666; }
.st b { color: #999; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #1e3d36; border-radius: 2px; }
::-webkit-scrollbar-thumb:hover { background: #555; }

/* ── Save plan modal ── */
.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center; z-index: 100;
}
.save-card {
  width: 420px; background: #152e28; border: 1px solid #1e3d36;
  border-radius: 7px; overflow: hidden;
  box-shadow: 0 20px 60px rgba(0,0,0,0.4);
}
.save-hdr {
  background: #0d1f1b; border-bottom: 1px solid #1e3d36;
  padding: 12px 16px; font-size: 12px; font-weight: 600; color: #ccc;
}
.save-body { padding: 16px; }
.save-lbl {
  display: block; font-size: 10px; color: #888; font-weight: 700;
  letter-spacing: 0.6px; text-transform: uppercase; margin-bottom: 6px;
}
.save-input {
  display: block; width: 100%; background: #091512;
  border: 1px solid #1e3d36; color: #e0e0e0;
  font-family: inherit; font-size: 12px;
  padding: 9px 11px; border-radius: 4px; outline: none;
  transition: border-color 0.2s;
}
.save-input:focus { border-color: #006B58; }
.save-err { font-size: 11px; color: #cc4444; margin-top: 8px; min-height: 16px; }
.save-footer {
  background: #0d1f1b; border-top: 1px solid #1e3d36;
  padding: 10px 14px; display: flex; justify-content: flex-end; gap: 8px;
}
.btn-cancel {
  background: transparent; border: 1px solid #1e3d36; color: #999;
  font-family: inherit; font-size: 11px; padding: 6px 14px;
  border-radius: 4px; cursor: pointer; transition: border-color 0.15s, color 0.15s;
}
.btn-cancel:hover { border-color: #666; color: #ccc; }
.btn-select {
  background: #006B58; border: none; color: #fff;
  font-family: inherit; font-size: 11px; font-weight: 600;
  padding: 6px 14px; border-radius: 4px; cursor: pointer; transition: background 0.15s;
}
.btn-select:hover { background: #007D68; }

/* ── Presentation overlay ── */
#present-overlay {
  position: fixed; inset: 0; background: #091512; z-index: 200;
  display: flex; flex-direction: column; overflow: hidden;
}
#present-hdr {
  height: 56px; background: #0d1f1b; border-bottom: 1px solid #1e3d36;
  display: flex; align-items: center; padding: 0 32px; gap: 16px; flex-shrink: 0;
}
#present-hdr-title {
  font-size: 15px; font-weight: 600; color: #fff; flex: 1;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}
.present-save-btn {
  background: #2a4a2a; border: 1px solid #406040; color: #5aa05a;
  font-family: inherit; font-size: 11px; font-weight: 600; padding: 6px 16px;
  border-radius: 4px; cursor: pointer; transition: background 0.15s, color 0.15s;
  letter-spacing: 0.3px; margin-right: 6px;
}
.present-save-btn:hover { background: #335033; color: #7acc7a; }
.present-close-btn {
  background: transparent; border: 1px solid #1e3d36; color: #aaa;
  font-family: inherit; font-size: 11px; padding: 6px 16px;
  border-radius: 4px; cursor: pointer; transition: border-color 0.15s, color 0.15s;
  letter-spacing: 0.3px;
}
.present-close-btn:hover { border-color: #666; color: #fff; }
#present-scroll {
  flex: 1; overflow-y: auto; display: flex; flex-direction: column; align-items: center;
  padding: 56px 48px 80px;
}
#present-content {
  width: 100%; max-width: 860px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 16px; line-height: 1.75; color: #bbb;
}
#present-content h1 {
  font-size: 30px; color: #fff; margin: 0 0 28px; font-weight: 700; line-height: 1.2;
}
#present-content h2 {
  font-size: 20px; color: #4a9e8e; font-weight: 600;
  margin: 44px 0 14px; padding-bottom: 10px; border-bottom: 1px solid #152e28;
}
#present-content h3 {
  font-size: 16px; color: #ccc; font-weight: 600; margin: 24px 0 8px;
}
#present-content p { margin-bottom: 14px; }
#present-content strong { color: #e0e0e0; }
#present-content em { color: #aaa; }
#present-content ul, #present-content ol { padding-left: 26px; margin-bottom: 14px; }
#present-content li { margin-bottom: 7px; }
#present-content code {
  background: #132420; padding: 2px 7px; border-radius: 3px;
  font-family: 'Menlo','Monaco','Consolas',monospace; font-size: 14px; color: #8ab4f8;
}
#present-content pre {
  background: #091512; padding: 18px 22px; border-radius: 6px;
  margin: 14px 0; overflow-x: auto; border: 1px solid #152e28;
}
#present-content pre code { background: none; padding: 0; font-size: 13px; }
#present-content table { border-collapse: collapse; width: 100%; margin: 18px 0; }
#present-content td, #present-content th { border: 1px solid #152e28; padding: 10px 16px; }
#present-content th {
  background: #0d1f1b; color: #888; font-size: 11px;
  letter-spacing: 0.6px; text-transform: uppercase; font-weight: 700;
}
#present-content hr { border: none; border-top: 1px solid #102018; margin: 36px 0; }
#present-content blockquote {
  border-left: 3px solid #006B58; padding: 2px 0 2px 18px;
  margin: 14px 0; color: #999; font-style: italic;
}

/* Present Plan button in header */
#present-btn {
  display: none; background: #006B58; border: none; color: #fff;
  font-family: inherit; font-size: 11px; font-weight: 600;
  padding: 6px 14px; border-radius: 4px; cursor: pointer;
  letter-spacing: 0.3px; transition: background 0.15s; white-space: nowrap;
}
#present-btn:hover { background: #007D68; }
#present-btn.ready { display: block; }
</style>
</head>
<body>

<div id="hdr">
  <h1>Seam</h1>
  <div id="status">Connecting to analysis server&hellip;</div>
  <div id="badge">IDLE</div>
  <button id="present-btn" onclick="openPresentMode()">&#x2B21; Present Plan</button>
</div>
<div id="prog"><div id="prog-fill"></div></div>

<div id="main">
  <div id="graph-wrap"><div id="graph"></div></div>
  <div id="side">
    <div id="log"></div>
    <div id="ap">
      <div id="ap-hdr">&#x2B21; Agent Analysis</div>
      <div id="ao">Waiting for analysis to complete&hellip;</div>
    </div>
  </div>
</div>

<div id="stats">
  <div class="st">Nodes <b id="sn">0</b></div>
  <div class="st">Edges <b id="se">0</b></div>
  <div class="st">Communities <b id="sc">0</b></div>
  <div class="st">Files <b id="sf">0</b></div>
  <div class="st">Cross-cluster <b id="scc">0</b></div>
</div>

<!-- Save plan modal -->
<div id="save-modal" class="modal-overlay" style="display:none">
  <div class="save-card">
    <div class="save-hdr">Save Migration Plan</div>
    <div class="save-body">
      <label class="save-lbl" for="save-name">Filename</label>
      <input class="save-input" id="save-name" type="text" value="migration_plan.md" spellcheck="false" />
      <label class="save-lbl" for="save-dir" style="margin-top:12px">Directory</label>
      <input class="save-input" id="save-dir" type="text" spellcheck="false" />
      <div class="save-err" id="save-err"></div>
    </div>
    <div class="save-footer">
      <button class="btn-cancel" onclick="closeSaveModal()">Cancel</button>
      <button class="btn-select" id="save-btn" onclick="savePlan()">Save</button>
    </div>
  </div>
</div>

<!-- Presentation overlay -->
<div id="present-overlay" style="display:none">
  <div id="present-hdr">
    <span id="present-hdr-title">&#x2B21; Migration Plan</span>
    <button class="present-save-btn" onclick="openSaveFromPresent()">&#x2193;&nbsp; Save</button>
    <button class="present-close-btn" onclick="closePresentMode()">&#x2715;&nbsp; Close</button>
  </div>
  <div id="present-scroll">
    <div id="present-content"></div>
  </div>
</div>

<script>
marked.setOptions({ breaks: true, gfm: true });

const PALETTE = [
  "#006B58","#D85A30","#0F6E56","#BA7517",
  "#993556","#185FA5","#639922","#A32D2D"
];
const DCLR = {
  user:"#006B58", order:"#D85A30", payment:"#0F6E56", inventory:"#BA7517",
  notification:"#993556", reporting:"#185FA5",
  shared:"#666", database:"#1e3d36", unknown:"#555"
};
const STAGE_CLR = {
  parsing:"#BA7517", clustering:"#993556", metrics:"#185FA5",
  agent:"#006B58", complete:"#0F6E56"
};

// ── vis.js setup ─────────────────────────────────────────────────────────────
const nodesDS = new vis.DataSet();
const edgesDS = new vis.DataSet();

const net = new vis.Network(
  document.getElementById('graph'),
  { nodes: nodesDS, edges: edgesDS },
  {
    physics: {
      stabilization: { enabled: false },
      barnesHut: {
        gravitationalConstant: -7000,
        centralGravity: 0.25,
        springLength: 110,
        springConstant: 0.04,
        damping: 0.09,
      }
    },
    nodes: { borderWidth: 0, font: { size: 11, color: '#ccc' } },
    edges: {
      arrows: { to: { enabled: true, scaleFactor: 0.45 } },
      smooth: { type: 'dynamic' },
      color: { inherit: false },
    },
    interaction: {
      hover: true, tooltipDelay: 80,
      hideEdgesOnDrag: true, navigationButtons: false,
    },
    layout: { improvedLayout: false },
  }
);

// ── State ────────────────────────────────────────────────────────────────────
let nN=0, nE=0, nC=0, nF=0, nCC=0;
const seenEdges = new Set();
const seenComms = new Set();
let agentBuf = '';

// ── SSE connection ───────────────────────────────────────────────────────────
const es = new EventSource('/events');

es.onmessage = ({ data }) => {
  const m = JSON.parse(data);

  switch (m.type) {

    case 'status':
      document.getElementById('status').textContent = m.message; break;

    case 'stage': {
      const b = document.getElementById('badge');
      b.textContent = m.stage.toUpperCase();
      b.style.background = STAGE_CLR[m.stage] || '#091512';
      b.style.color = '#fff';
      break;
    }

    case 'progress':
      document.getElementById('prog-fill').style.width =
        ((m.current / m.total) * 100) + '%';
      break;

    case 'log': {
      const div = document.createElement('div');
      div.className = 'le' + (m.highlight ? ' hl' : '');
      const t = new Date().toLocaleTimeString('en', { hour12: false });
      div.textContent = '[' + t + '] ' + m.message;
      const log = document.getElementById('log');
      log.appendChild(div);
      log.scrollTop = log.scrollHeight;
      break;
    }

    case 'add_node': {
      const c = DCLR[m.domain] || '#132420';
      nodesDS.add({
        id: m.id, label: m.label,
        color: {
          background: c, border: c,
          highlight: { background: c, border: '#e0e0e0' },
          hover:      { background: c, border: '#777' },
        },
        shape: m.node_type === 'table' ? 'diamond' : 'dot',
        size:  m.node_type === 'table' ? 9 : 13,
        title: '<b>' + m.label + '</b><br>Domain: ' + m.domain,
      });
      document.getElementById('sn').textContent = ++nN;
      break;
    }

    case 'add_edge': {
      const key = m.from + '=>' + m.to;
      if (!seenEdges.has(key)) {
        seenEdges.add(key);
        const isTable = m.relationship === 'accesses_table';
        edgesDS.add({
          id: key, from: m.from, to: m.to, title: m.relationship,
          color: {
            color:     isTable ? '#6a2a2a' : '#1e3d36',
            hover:     '#666',
            highlight: '#999',
          },
          width:  m.relationship === 'instantiates' ? 1.5 : 0.8,
          dashes: isTable ? [3, 3] : false,
        });
        document.getElementById('se').textContent = ++nE;
      }
      break;
    }

    case 'cluster': {
      const c = PALETTE[m.community % PALETTE.length];
      try {
        nodesDS.update({
          id: m.node,
          color: {
            background: c, border: c,
            highlight: { background: c, border: '#fff' },
            hover:     { background: c, border: '#ccc' },
          },
        });
      } catch (_) {}
      if (!seenComms.has(m.community)) {
        seenComms.add(m.community);
        document.getElementById('sc').textContent = ++nC;
      }
      break;
    }

    case 'metrics': {
      const sz = 11 + (m.total_degree || 0) * 2.2;
      try {
        nodesDS.update({
          id: m.node, size: sz,
          title: (
            '<b>' + m.node + '</b><br>' +
            'In: ' + m.in_degree + ' | Out: ' + m.out_degree + '<br>' +
            'Betweenness: ' + m.betweenness
          ),
        });
      } catch (_) {}
      break;
    }

    case 'highlight_cross_edge': {
      const key = m.from + '=>' + m.to;
      try {
        edgesDS.update({
          id: key,
          color: { color: '#8e2424', hover: '#c44', highlight: '#f44' },
          width: 1.8, dashes: [5, 4],
        });
      } catch (_) {}
      document.getElementById('scc').textContent = ++nCC;
      break;
    }

    case 'file_parsed':
      document.getElementById('sf').textContent = ++nF; break;

    case 'agent_chunk':
      agentBuf += m.text;
      document.getElementById('ao').innerHTML = marked.parse(agentBuf);
      document.getElementById('ap').scrollTop =
        document.getElementById('ap').scrollHeight;
      document.getElementById('present-btn').classList.add('ready');
      break;

    case 'plan_ready':
      pendingDefaultDir = m.default_dir || '';
      openPresentMode();
      break;

    case 'complete':
      document.getElementById('status').textContent =
        m.message || 'Analysis complete';
      document.getElementById('prog-fill').style.width = '100%';
      document.getElementById('prog-fill').style.background = '#0F6E56';
      break;
  }
};

// ── Save plan modal ──────────────────────────────────────────────────────────
function openSaveModal(defaultDir) {
  document.getElementById('save-dir').value = defaultDir;
  document.getElementById('save-err').textContent = '';
  document.getElementById('save-btn').disabled = false;
  document.getElementById('save-btn').textContent = 'Save';
  document.getElementById('save-modal').style.display = 'flex';
  setTimeout(() => {
    const n = document.getElementById('save-name');
    n.focus(); n.select();
  }, 50);
}

function closeSaveModal() {
  document.getElementById('save-modal').style.display = 'none';
}

document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeSaveModal();
  if (e.key === 'Enter' && document.getElementById('save-modal').style.display !== 'none') savePlan();
});

async function savePlan() {
  const name = document.getElementById('save-name').value.trim();
  const dir  = document.getElementById('save-dir').value.trim();
  const err  = document.getElementById('save-err');
  const btn  = document.getElementById('save-btn');
  if (!name) { err.textContent = 'Filename is required.'; return; }
  if (!dir)  { err.textContent = 'Directory is required.'; return; }

  btn.disabled = true;
  btn.textContent = 'Saving…';
  err.textContent = '';

  try {
    const res  = await fetch('/save_plan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename: name, directory: dir }),
    });
    const data = await res.json();
    if (!res.ok) {
      err.textContent = data.error || 'Save failed.';
      btn.disabled = false;
      btn.textContent = 'Save';
      return;
    }
    closeSaveModal();
    const div = document.createElement('div');
    div.className = 'le hl';
    const t = new Date().toLocaleTimeString('en', { hour12: false });
    div.textContent = '[' + t + '] Migration plan saved → ' + data.path;
    const log = document.getElementById('log');
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
  } catch (_) {
    err.textContent = 'Could not reach the server.';
    btn.disabled = false;
    btn.textContent = 'Save';
  }
}

es.onerror = () => {
  document.getElementById('status').textContent =
    'Connection lost — reload to reconnect';
  const b = document.getElementById('badge');
  b.textContent = 'DISCONNECTED';
  b.style.background = '#4a1414';
  b.style.color = '#ff6b6b';
};

// ── Presentation mode ────────────────────────────────────────────────────────
let pendingDefaultDir = '';

function openPresentMode() {
  if (!agentBuf) return;
  document.getElementById('present-content').innerHTML = marked.parse(agentBuf);
  document.getElementById('present-scroll').scrollTop = 0;
  document.getElementById('present-overlay').style.display = 'flex';
}

function closePresentMode() {
  document.getElementById('present-overlay').style.display = 'none';
}

function openSaveFromPresent() {
  closePresentMode();
  openSaveModal(pendingDefaultDir);
}

document.addEventListener('keydown', e => {
  if (e.key === 'Escape' && document.getElementById('present-overlay').style.display !== 'none') {
    closePresentMode();
  }
  if ((e.key === 'p' || e.key === 'P') &&
      document.getElementById('save-modal').style.display === 'none' &&
      document.getElementById('present-overlay').style.display === 'none' &&
      document.activeElement.tagName !== 'INPUT') {
    openPresentMode();
  }
});
</script>
</body>
</html>"""


# ── SSE helpers ───────────────────────────────────────────────────────────────

def emit(msg: dict):
    """Thread-safe SSE broadcast."""
    data = json.dumps(msg)
    with _lock:
        dead = []
        for q in _subscribers:
            try:
                q.put_nowait(data)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _subscribers.remove(q)


def _sse_stream():
    q = queue.Queue(maxsize=500)
    with _lock:
        _subscribers.append(q)
    try:
        while True:
            try:
                data = q.get(timeout=20)
                yield f"data: {data}\n\n"
            except queue.Empty:
                yield 'data: {"type":"ping"}\n\n'
    except GeneratorExit:
        pass
    finally:
        with _lock:
            if q in _subscribers:
                _subscribers.remove(q)


# ── Flask routes ──────────────────────────────────────────────────────────────

@app.route('/browse')
def browse():
    raw = (request.args.get('path') or '').strip()
    p   = Path(raw).expanduser().resolve() if raw else Path.home()
    if not p.is_dir():
        p = p.parent

    entries = []
    try:
        for item in sorted(p.iterdir(), key=lambda x: x.name.lower()):
            if item.is_dir() and not item.name.startswith('.'):
                entries.append({"name": item.name, "path": str(item)})
    except PermissionError:
        pass

    parent = str(p.parent) if p != p.parent else None
    return jsonify({"current": str(p), "parent": parent, "entries": entries})


@app.route('/')
def index():
    return _SETUP_HTML.replace('__PREFILL__', json.dumps(_prefill))


@app.route('/graph')
def graph():
    if not _start_event.is_set():
        return redirect('/')
    return _GRAPH_HTML


@app.route('/start', methods=['POST'])
def start():
    global _pending_folder

    if _start_event.is_set():
        return jsonify({"error": "Analysis already started."}), 400

    data       = request.get_json(silent=True) or {}
    folder_raw = (data.get('folder') or '').strip()

    if not folder_raw:
        return jsonify({"error": "Folder path is required."}), 400

    p = Path(folder_raw).expanduser().resolve()
    if not p.is_dir():
        return jsonify({"error": f"Directory not found: {folder_raw}"}), 400

    java_files = list(p.rglob("*.java"))
    if not java_files:
        return jsonify({"error": f"No .java files found in: {folder_raw}"}), 400

    _pending_folder = str(p)
    _start_event.set()

    return jsonify({"ok": True, "files": len(java_files)})


@app.route('/save_plan', methods=['POST'])
def save_plan():
    if not _pending_plan:
        return jsonify({"error": "No plan available to save."}), 400

    data      = request.get_json(silent=True) or {}
    filename  = (data.get('filename') or '').strip()
    directory = (data.get('directory') or '').strip()

    if not filename:
        return jsonify({"error": "Filename is required."}), 400
    if not directory:
        return jsonify({"error": "Directory is required."}), 400
    if not filename.endswith('.md'):
        filename += '.md'

    try:
        out_path = Path(directory).expanduser().resolve() / filename
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(_pending_plan)
        return jsonify({"ok": True, "path": str(out_path)})
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500


@app.route('/events')
def events():
    return Response(
        stream_with_context(_sse_stream()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )


# ── Lifecycle ─────────────────────────────────────────────────────────────────

def wait_for_config() -> str:
    _start_event.wait()
    return _pending_folder


def set_pending_plan(text: str):
    global _pending_plan
    _pending_plan = text


def start_server(port: int = 5050, prefill: str = ""):
    global _prefill
    _prefill = prefill

    import logging
    logging.getLogger('werkzeug').setLevel(logging.ERROR)

    t = threading.Thread(
        target=lambda: app.run(port=port, threaded=True, use_reloader=False),
        daemon=True,
    )
    t.start()
    time.sleep(0.8)
    webbrowser.open(f'http://localhost:{port}')
    print(f"  Setup page  →  http://localhost:{port}")
