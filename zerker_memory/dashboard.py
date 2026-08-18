from __future__ import annotations

import argparse
import json
import sqlite3
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .exporter import export_bundle, export_snapshot
from .session_connections import create_session_invitation, detach_session_attachment
from .store import MemoryStore, default_db_path, default_policy_path
from .workspaces import workspace_source_report, workspace_status_for_paths


INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Zerker Memory Console</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #162019;
      --muted: #637065;
      --line: #d9e1da;
      --paper: #f6f7f3;
      --panel: #ffffff;
      --accent: #1f7a5a;
      --warn: #9b4b22;
      --bad: #9f2f37;
      --good: #1f7a5a;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--paper);
      color: var(--ink);
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 20px;
      padding: 22px 28px;
      border-bottom: 1px solid var(--line);
      background: rgba(255,255,255,.86);
      position: sticky;
      top: 0;
      z-index: 3;
      backdrop-filter: blur(12px);
    }
    h1 { margin: 0; font-size: 20px; letter-spacing: 0; }
    main {
      width: 100%;
      min-width: 0;
      padding: 24px 28px 40px;
      display: grid;
      grid-template-columns: minmax(0, 1fr);
      gap: 22px;
    }
    main > *, .grid > *, .status-strip > *, .status-board > *, .hero-grid > *,
    .quick-grid > *, .split-view > *, .proof-grid > *, .story-grid > *,
    .workflow > *, .form-grid > * { min-width: 0; }
    .topline {
      color: var(--muted);
      font-size: 13px;
      margin-top: 4px;
      overflow-wrap: anywhere;
    }
    .grid { display: grid; grid-template-columns: 1.2fr .8fr; gap: 22px; align-items: start; }
    .hero {
      display: grid;
      gap: 18px;
      padding: 22px;
      border-radius: 14px;
      border: 1px solid #d4ddd6;
      background:
        radial-gradient(circle at top left, rgba(31,122,90,.12), transparent 40%),
        linear-gradient(135deg, #ffffff, #f0f4ee);
      box-shadow: 0 10px 30px rgba(22, 32, 25, .05);
    }
    .hero h2 {
      font-size: 24px;
      margin: 0;
      letter-spacing: -.02em;
    }
    .hero p {
      margin: 0;
      color: var(--muted);
      line-height: 1.5;
      max-width: 760px;
    }
    .hero-grid {
      display: grid;
      gap: 14px;
      grid-template-columns: 1.15fr .85fr;
      align-items: start;
    }
    .checklist, .command-list {
      display: grid;
      gap: 10px;
      min-width: 0;
    }
    .check {
      display: flex;
      align-items: flex-start;
      gap: 10px;
      padding: 11px 12px;
      border: 1px solid var(--line);
      border-radius: 10px;
      background: rgba(255,255,255,.82);
    }
    .check strong {
      display: block;
      margin-bottom: 3px;
      font-size: 13px;
    }
    .check span {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.4;
    }
    .dot {
      flex: 0 0 10px;
      width: 10px;
      height: 10px;
      border-radius: 999px;
      margin-top: 4px;
      background: #c6d1c8;
    }
    .dot.ready { background: var(--good); }
    .dot.pending { background: var(--warn); }
    .command-list pre {
      margin: 0;
      font-size: 12px;
      line-height: 1.45;
      max-height: none;
      background: #17211a;
      color: #eef6ef;
      border-color: #17211a;
    }
    .metrics { display: grid; grid-template-columns: repeat(4, minmax(120px, 1fr)); gap: 12px; }
    .status-strip { display: grid; grid-template-columns: 1.05fr .95fr; gap: 12px; align-items: stretch; }
    .status-panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      min-width: 0;
    }
    .status-panel h2 { margin-bottom: 8px; }
    .quick-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin-top: 12px; }
    .quick-card {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfcfa;
      padding: 11px;
      min-width: 0;
    }
    .quick-card strong { display: block; font-size: 13px; margin-bottom: 5px; }
    .quick-card span { display: block; color: var(--muted); font-size: 12px; line-height: 1.35; overflow-wrap: anywhere; }
    .quick-card a { color: var(--accent); font-weight: 700; text-decoration: none; }
    .status-board { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    .cluster-list { display: grid; gap: 10px; margin-top: 12px; }
    .cluster {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfcfa;
      padding: 12px;
    }
    .cluster-head { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
    .cluster-head strong { font-size: 13px; line-height: 1.35; }
    .cluster .topline { overflow-wrap: anywhere; }
    .split-view { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 12px; }
    .zone {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      background: #fbfcfa;
      min-width: 0;
    }
    .zone.proven { border-color: #b8d9ca; }
    .zone.asserted { border-color: #e9c8ad; }
    .zone strong { display: block; font-size: 13px; margin-bottom: 8px; }
    .zone ul { margin: 0; padding-left: 18px; color: var(--muted); font-size: 12px; line-height: 1.45; }
    .benchmark-table { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 13px; }
    .benchmark-table th, .benchmark-table td { border-bottom: 1px solid var(--line); padding: 8px; text-align: left; vertical-align: top; }
    .benchmark-table th { color: var(--muted); font-size: 11px; text-transform: uppercase; }
    .table-scroll { width: 100%; max-width: 100%; overflow-x: auto; }
    .num { text-align: right; white-space: nowrap; }
    .metric, section {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
    }
    .metric { padding: 14px; min-height: 76px; }
    .metric strong { display: block; font-size: 24px; margin-bottom: 4px; }
    .metric span { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }
    section { padding: 16px; }
    h2 { font-size: 15px; margin: 0 0 14px; }
    h3 { font-size: 13px; margin: 0 0 8px; }
    .toolbar { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
    input, select, textarea {
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 9px 10px;
      font: inherit;
      background: #fff;
      color: var(--ink);
    }
    input[type="search"] { min-width: 260px; }
    textarea { width: 100%; min-height: 82px; resize: vertical; }
    button {
      border: 1px solid #b8c8bd;
      background: #fff;
      color: var(--ink);
      border-radius: 6px;
      padding: 9px 11px;
      font: inherit;
      cursor: pointer;
    }
    button.primary { background: var(--accent); color: white; border-color: var(--accent); }
    button.danger { color: var(--bad); border-color: #e4b9bd; }
    button:disabled { cursor: not-allowed; opacity: .48; }
    .list {
      display: grid;
      grid-template-columns: minmax(0, 1fr);
      gap: 10px;
      min-width: 0;
    }
    .item {
      width: 100%;
      min-width: 0;
      max-width: 100%;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      background: #fff;
      overflow-wrap: anywhere;
    }
    .meta { display: flex; flex-wrap: wrap; gap: 7px; margin-bottom: 8px; }
    .pill {
      font-size: 12px;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 3px 7px;
      color: var(--muted);
      background: #fbfcfa;
    }
    .pill.active { color: var(--good); border-color: #b8d9ca; }
    .pill.quarantined, .pill.proposed { color: var(--warn); border-color: #e9c8ad; }
    .pill.revoked, .pill.deprecated { color: var(--bad); border-color: #e5b6bb; }
    .content { line-height: 1.45; margin-bottom: 10px; }
    .actions { display: flex; flex-wrap: wrap; gap: 8px; }
    .session-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      margin-top: 8px;
      padding-top: 8px;
      border-top: 1px solid var(--line);
      color: var(--muted);
      font-size: 12px;
    }
    .session-row span { min-width: 0; overflow-wrap: anywhere; }
    .session-row button { flex: 0 0 auto; padding: 5px 8px; }
    .proof-grid { display: grid; grid-template-columns: repeat(3, minmax(160px, 1fr)); gap: 10px; margin-bottom: 12px; }
    .proof-cell {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      background: #fbfcfa;
      min-width: 0;
    }
    .proof-cell span { display: block; color: var(--muted); font-size: 12px; margin-bottom: 4px; }
    .proof-cell strong {
      display: block;
      font-size: 13px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .proof-status { display: flex; flex-wrap: wrap; gap: 7px; margin-bottom: 12px; }
    .helper {
      margin: 0 0 12px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.5;
    }
    .story-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(160px, 1fr));
      gap: 10px;
      margin-bottom: 12px;
    }
    .story-card {
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 12px;
      background: #fbfcfa;
    }
    .story-card strong {
      display: block;
      margin-bottom: 6px;
      font-size: 13px;
    }
    .story-card p {
      margin: 0;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.45;
    }
    .story-card code {
      display: inline-block;
      max-width: 100%;
      margin-top: 8px;
      padding: 4px 6px;
      border-radius: 6px;
      background: #17211a;
      color: #eef6ef;
      font-size: 11px;
      overflow-wrap: anywhere;
      white-space: normal;
    }
    .workflow {
      display: grid;
      grid-template-columns: repeat(4, minmax(150px, 1fr));
      gap: 10px;
    }
    .flow-step {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      background: #fbfcfa;
      min-height: 116px;
    }
    .flow-step span {
      display: inline-grid;
      place-items: center;
      width: 24px;
      height: 24px;
      margin-bottom: 10px;
      border-radius: 999px;
      background: var(--accent);
      color: #fff;
      font-size: 12px;
      font-weight: 700;
    }
    .flow-step strong {
      display: block;
      margin-bottom: 6px;
      font-size: 13px;
    }
    .flow-step p {
      margin: 0;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.45;
    }
    .form-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(110px, 1fr));
      gap: 8px;
      margin: 10px 0;
    }
    pre {
      min-width: 0;
      max-width: 100%;
      overflow: auto;
      padding: 12px;
      border-radius: 8px;
      border: 1px solid var(--line);
      background: #fbfcfa;
      max-height: 360px;
    }
    pre > code { display: block; width: 100%; }
    .empty { color: var(--muted); padding: 16px 0; }
    @media (max-width: 900px) {
      .grid { grid-template-columns: 1fr; }
      .hero-grid { grid-template-columns: 1fr; }
      .metrics { grid-template-columns: repeat(2, minmax(120px, 1fr)); }
      .status-strip { grid-template-columns: 1fr; }
      .status-board { grid-template-columns: 1fr; }
      .quick-grid { grid-template-columns: 1fr; }
      .split-view { grid-template-columns: 1fr; }
      .proof-grid { grid-template-columns: 1fr; }
      .story-grid { grid-template-columns: 1fr; }
      .workflow { grid-template-columns: 1fr; }
      .form-grid { grid-template-columns: 1fr; }
      header { align-items: flex-start; flex-direction: column; }
      input[type="search"] { min-width: 0; width: 100%; }
    }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>Zerker Memory Console</h1>
      <div class="topline" id="dbPath">Loading local memory state...</div>
    </div>
    <div class="toolbar">
      <button id="refreshBtn">Refresh</button>
      <button class="primary" id="snapshotBtn">Export Snapshot</button>
    </div>
  </header>
  <main>
    <div class="metrics" id="metrics"></div>
    <section class="status-panel">
      <h2>Workspace Profile</h2>
      <p class="helper">Switching projects and agents starts here: the console shows whether this DB is registered, current, or pointed at a different workspace.</p>
      <div id="workspaceProfile" class="empty">Loading workspace profile...</div>
    </section>
    <section class="status-panel">
      <h2>Memory Provenance</h2>
      <p class="helper">Read-only source lineage for recent memory writes: connected agent, chat/session id, source URI, trust status, and proof root.</p>
      <div id="workspaceSources" class="empty">Loading workspace sources...</div>
    </section>
    <section class="status-strip">
      <div class="status-panel">
        <h2>Memory In Use</h2>
        <p class="helper">This console is connected to the local ZMem store. These are the dogfood memories and proof artifacts agents should be able to retrieve.</p>
        <div id="memorySpotlight" class="empty">Loading dogfood memories...</div>
      </div>
      <div class="status-panel">
        <h2>Agent MCP And Benchmarks</h2>
        <p class="helper">Agents use the same memory DB through MCP configs. Benchmark artifacts are generated separately but linked here.</p>
        <div id="agentBenchmarkSpotlight" class="empty">Loading agent and benchmark status...</div>
      </div>
    </section>
    <section class="status-board">
      <div class="status-panel">
        <h2>Memory Status</h2>
        <p class="helper">A cleaner health view for humans and agents: active memories, review queues, stale/revoked memory, and duplicate clusters.</p>
        <div id="memoryStatusPanel" class="empty">Loading memory status...</div>
      </div>
      <div class="status-panel">
        <h2>Benchmark Panel</h2>
        <p class="helper">The latest local matrix is proof-backed engineering evidence, not an official leaderboard claim.</p>
        <div id="benchmarkPanel" class="empty">Loading benchmark evidence...</div>
      </div>
    </section>
    <section>
      <h2>Memory Clusters</h2>
      <p class="helper">Duplicate and near-duplicate memories are grouped so old smoke runs do not drown out the current facts agents should use.</p>
      <div id="memoryClusters" class="empty">Loading memory clusters...</div>
    </section>
    <section id="onboarding" class="hero" hidden></section>
    <section>
      <h2>Use ZMem</h2>
      <div class="workflow">
        <div class="flow-step"><span>1</span><strong>Save memory</strong><p>Add a fact, preference, decision, or policy into the local store.</p></div>
        <div class="flow-step"><span>2</span><strong>Review control</strong><p>Promote trusted memories and reject or revoke anything that should not guide an agent.</p></div>
        <div class="flow-step"><span>3</span><strong>Preview injection</strong><p>See exactly what an agent would receive before a task runs.</p></div>
        <div class="flow-step"><span>4</span><strong>Prove and hand off</strong><p>Export receipts, snapshots, or a handoff for another agent or machine.</p></div>
      </div>
    </section>
    <section>
      <h2>Agent Memory Network</h2>
      <p class="helper">See which frameworks are configured for this exact store, which agents have written memory, and which attached connectors are live recently. Configuration, historical provenance, and live presence stay separate.</p>
      <div class="form-grid">
        <select id="sessionAgent" aria-label="Agent to invite"></select>
        <input id="sessionLabel" value="current chat" maxlength="120" aria-label="Session label">
        <input id="sessionScope" value="project" maxlength="256" aria-label="Memory scope">
        <input id="sessionRoom" maxlength="256" placeholder="Room id (optional)" aria-label="Room id">
      </div>
      <div class="toolbar" style="margin-bottom:12px">
        <button class="primary" id="sessionInviteBtn" data-session-action="invite">Create One-Time Invite</button>
      </div>
      <div id="sessionInviteResult" class="empty">Choose an agent, create an invite, then paste the one copy-ready instruction into that agent chat.</div>
      <div id="continuity" class="empty">Connected-agent state will appear here.</div>
    </section>
    <section>
      <h2>Shared Rooms</h2>
      <p class="helper">Room-shared and member-private memory stay in isolated local stores. Contributors shown here come from memory provenance; Zerker Gateway remains authoritative for membership and access.</p>
      <div id="roomInventory" class="empty">Local Room memory will appear here.</div>
    </section>
    <section>
      <h2>What Does ZMem Know?</h2>
      <p class="helper">Ask before you hand context to an agent. ZMem searches active and queued memory, then shows source, status, trust, and scope in one compact view.</p>
      <div class="toolbar" style="margin-bottom:12px">
        <input id="topicQuery" type="search" placeholder="Ask about a person, project, task, or decision">
        <button class="primary" id="topicSearchBtn">Inspect Topic</button>
        <button id="topicExampleBtn">Use Example</button>
      </div>
      <div id="topicSummary" class="empty">Topic memory will appear here.</div>
    </section>
    <div class="grid">
      <section>
        <h2>Add Memory</h2>
        <p class="helper">Save a local memory in one step. Human-entered semantic and policy memories become active by default; agent or external memories stay reviewable.</p>
        <textarea id="rememberContent" placeholder="Example: The launch positioning is local-first memory for AI agents with verifiable transition receipts."></textarea>
        <div class="form-grid">
          <select id="rememberType" aria-label="Memory type">
            <option value="semantic" selected>Semantic</option>
            <option value="episodic">Episodic</option>
            <option value="procedural">Procedural</option>
            <option value="policy">Policy</option>
          </select>
          <select id="rememberSource" aria-label="Source">
            <option value="human" selected>Human</option>
            <option value="agent">Agent</option>
            <option value="external">External</option>
          </select>
          <input id="rememberScope" value="project" aria-label="Memory scope">
          <input id="rememberLabels" placeholder="labels, comma-separated" aria-label="Memory labels">
        </div>
        <div class="toolbar">
          <button class="primary" id="rememberBtn">Save Memory</button>
          <button id="rememberExampleBtn">Use Example</button>
        </div>
      </section>
      <section>
        <h2>Inject Preview</h2>
        <p class="helper">Preview the governed memory an agent would receive for a real task, then inspect or bundle the resulting receipt.</p>
        <textarea id="task" placeholder="Task an agent is about to perform"></textarea>
        <div class="toolbar" style="margin:10px 0">
          <input id="agent" value="codex" aria-label="Agent">
          <select id="risk"><option>low</option><option selected>medium</option><option>high</option></select>
          <input id="scope" value="project" aria-label="Scope">
          <button id="demoTaskBtn">Load deploy demo</button>
          <button class="primary" id="injectBtn">Preview</button>
        </div>
      </section>
    </div>
    <section>
      <h2>Review Queue</h2>
      <div class="list" id="queue"></div>
    </section>
    <section>
      <h2>Context Transfer</h2>
      <p class="helper">Package verified memory for another agent or machine, preview the exact snapshot and destination without writing, then restore only that reviewed artifact into a new local copy.</p>
      <div class="toolbar" style="margin-bottom:12px">
        <button class="primary" id="handoffBtn">Generate Handoff</button>
        <button id="previewHandoffBtn">Preview Restore</button>
        <button id="restoreHandoffBtn" disabled>Restore To New Copy</button>
      </div>
      <div id="handoffPreview" class="empty">Generate or select a handoff, then preview it before restore.</div>
    </section>
    <section>
      <h2>Release Verification</h2>
      <p class="helper">Optional maintainer tools for release proof, clean-shell verification, and launch assets.</p>
      <div class="toolbar" style="margin-bottom:12px">
        <button class="primary" id="releasePackBtn">Run Release Pack</button>
        <button id="launchProofBtn">Generate Launch Proof</button>
        <button id="verifyLaunchAssetsBtn">Verify Launch Assets</button>
        <button id="verifyReturnPacketBtn">Verify Return Packet</button>
      </div>
      <div id="releaseStatus" class="empty">Launch-proof and handoff readiness will appear here.</div>
    </section>
    <section>
      <h2>Proof Inspector</h2>
      <p class="helper">Treeship boundary framing: hashes, roots, signatures, policy digests, and ordered-log anchors belong in the proven zone. Outcome counts and injected/withheld ids are asserted provider details unless independently committed by a proof.</p>
      <div id="proofSummary" class="empty">Run an injection preview, inspect a receipt, export a bundle, or export a snapshot.</div>
      <pre id="rawOutput">{}</pre>
    </section>
    <section>
      <h2>Memories</h2>
      <div class="toolbar" style="margin-bottom:12px">
        <input id="search" type="search" placeholder="Search active and queued memory">
        <select id="status">
          <option value="">All statuses</option>
          <option value="active">Active</option>
          <option value="quarantined">Quarantined</option>
          <option value="proposed">Proposed</option>
          <option value="deprecated">Deprecated</option>
          <option value="revoked">Revoked</option>
          <option value="forgotten">Forgotten</option>
        </select>
        <button id="searchBtn">Search</button>
      </div>
      <div class="list" id="memories"></div>
    </section>
    <section>
      <h2>Recent Receipts</h2>
      <div class="list" id="receipts"></div>
    </section>
  </main>
  <script>
    const $ = (id) => document.getElementById(id);
    let handoffPreviewId = null;
    let lastSessionInstruction = '';

    async function api(path, options = {}) {
      const response = await fetch(path, {
        headers: {'content-type': 'application/json'},
        ...options,
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || response.statusText);
      return payload;
    }

    function pill(value) {
      const text = String(value);
      return `<span class="pill ${text.replace(/[^a-z0-9_-]/gi, '')}">${escapeHtml(text)}</span>`;
    }

    function memoryItem(memory, controls = true) {
      const labels = (memory.labels || []).map(pill).join('');
      return `<div class="item">
        <div class="meta">
          ${pill(memory.status)}${pill(memory.type)}${pill(memory.authority)}
          ${pill('trust ' + Number(memory.trust).toFixed(2))}${labels}
        </div>
        <div class="content">${escapeHtml(memory.content)}</div>
        <div class="topline">${memory.id} · ${memory.scope} · ${memory.source_kind}</div>
        ${controls ? `<div class="actions" style="margin-top:10px">
          <button data-action="promote" data-id="${memory.id}">Promote</button>
          <button data-action="reject" data-id="${memory.id}">Reject</button>
          <button class="danger" data-action="revoke" data-id="${memory.id}">Revoke</button>
        </div>` : ''}
      </div>`;
    }

    function escapeHtml(value) {
      return String(value).replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
    }

    function shortHash(value) {
      if (!value) return 'none';
      const text = String(value);
      return text.length > 18 ? text.slice(0, 18) + '...' : text;
    }

    function proofCell(label, value) {
      return `<div class="proof-cell"><span>${escapeHtml(label)}</span><strong title="${escapeHtml(value)}">${escapeHtml(value)}</strong></div>`;
    }

    function normalizeMemoryContent(content) {
      return String(content || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').replace(/\s+/g, ' ').trim();
    }

    function groupMemories(memories) {
      const groups = new Map();
      for (const memory of memories || []) {
        const key = memory.content_hash || normalizeMemoryContent(memory.content);
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key).push(memory);
      }
      return Array.from(groups.values()).sort((a, b) => b.length - a.length);
    }

    function renderMemoryStatusPanel(state) {
      const stats = state.stats || {};
      const status = stats.memory_status || {};
      const memories = state.memories || [];
      const duplicateGroups = groupMemories(memories).filter((group) => group.length > 1);
      const staleCount = (status.deprecated || 0) + (status.revoked || 0) + (status.forgotten || 0) + (status.expired || 0);
      $('memoryStatusPanel').innerHTML = `
        <div class="proof-status">
          ${pill(`active ${status.active || 0}`)}
          ${pill(`review ${(status.quarantined || 0) + (status.proposed || 0)}`)}
          ${pill(`stale ${staleCount}`)}
          ${pill(`clusters ${duplicateGroups.length}`)}
        </div>
        <div class="proof-grid">
          ${proofCell('Memory root', shortHash(stats.memory_merkle_root))}
          ${proofCell('Event root', shortHash(stats.merkle_root))}
          ${proofCell('Receipts', String(stats.receipt_count || 0))}
          ${proofCell('Duplicate groups', String(duplicateGroups.length))}
        </div>`;
    }

    function renderMemoryClusters(state) {
      const groups = groupMemories(state.memories || []).filter((group) => group.length > 1).slice(0, 8);
      if (!groups.length) {
        $('memoryClusters').innerHTML = '<div class="empty">No duplicate clusters in the loaded memory window.</div>';
        return;
      }
      $('memoryClusters').innerHTML = `<div class="cluster-list">${groups.map((group) => {
        const active = group.filter((memory) => memory.status === 'active').length;
        const review = group.filter((memory) => memory.status === 'quarantined' || memory.status === 'proposed').length;
        const latest = group[0];
        const ids = group.map((memory) => memory.id).join(', ');
        return `<div class="cluster">
          <div class="cluster-head">
            <strong>${escapeHtml(latest.content)}</strong>
            ${pill(`${group.length} copies`)}
          </div>
          <div class="meta">${pill(`active ${active}`)}${pill(`review ${review}`)}${pill(latest.type || 'memory')}</div>
          <div class="topline">${escapeHtml(ids)}</div>
        </div>`;
      }).join('')}</div>`;
    }

    function renderBenchmarkPanel(state) {
      const benchmark = state.benchmark || {};
      if (!benchmark.ok) {
        $('benchmarkPanel').innerHTML = `<div class="empty">${escapeHtml(benchmark.message || 'No benchmark matrix found yet.')}</div>`;
        return;
      }
      const rows = (benchmark.modes || []).map((mode) => `<tr>
        <td><strong>${escapeHtml(mode.retrieval_mode || mode.run_id)}</strong></td>
        <td class="num">${Number(mode.accuracy || 0).toFixed(3)}</td>
        <td class="num">${escapeHtml(mode.pass || '')}</td>
        <td class="num">${escapeHtml(String(mode.p95_retrieval_latency_ms || 0))}</td>
        <td class="num">${escapeHtml(String(mode.total_tokens || 0))}</td>
      </tr>`).join('');
      $('benchmarkPanel').innerHTML = `
        <div class="proof-status">
          ${pill(benchmark.claim_status || 'local evidence')}
          ${pill(benchmark.verification_status || 'unknown')}
          ${pill(`best ${benchmark.best_mode || 'n/a'}`)}
        </div>
        <div class="proof-grid">
          ${proofCell('Run', benchmark.run_id || 'unknown')}
          ${proofCell('Matrix hash', shortHash(benchmark.matrix_hash))}
          ${proofCell('Comparison hash', shortHash(benchmark.comparison_hash))}
          ${proofCell('Dashboard', benchmark.dashboard_path || 'not generated')}
        </div>
        <div class="table-scroll">
          <table class="benchmark-table">
            <thead><tr><th>Mode</th><th class="num">Accuracy</th><th class="num">Pass</th><th class="num">P95 ms</th><th class="num">Tokens</th></tr></thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
        <p class="helper"><a href="${escapeHtml(benchmark.public_url || 'http://127.0.0.1:8766/benchmarks.html')}" target="_blank" rel="noreferrer">Open public evidence</a></p>`;
    }

    function renderWorkspaceProfile(state) {
      const profile = state.workspace_profile || {};
      const current = profile.current || {};
      const matched = profile.matched || {};
      const match = profile.match_state || 'unknown';
      const tone = match === 'matched-current' ? 'current' : match === 'matched-other' ? 'registered elsewhere' : 'needs registration';
      $('workspaceProfile').innerHTML = `
        <div class="proof-status">
          ${pill(tone)}
          ${pill(current.name || 'no active profile')}
          ${pill(profile.registry_exists ? 'registry found' : 'registry missing')}
        </div>
        <div class="proof-grid">
          ${proofCell('Current workspace', current.name || 'none')}
          ${proofCell('Current id', profile.current_id || 'none')}
          ${proofCell('Matched workspace', matched.name || 'none')}
          ${proofCell('Registry', profile.registry_path || 'unknown')}
        </div>
        <div class="topline">DB ${escapeHtml(profile.db_path || state.stats.db_path || 'unknown')}</div>`;
    }

    function renderWorkspaceSources(state) {
      const report = state.workspace_sources || {};
      const agents = report.connected_agents || [];
      const conflicts = report.claim_conflicts || [];
      const sources = report.sources || [];
      const identityResolutionByKey = new Map(
        agents
          .map((agent) => [agent.identity_anchor?.key, agent.identity_resolution])
          .filter(([key]) => Boolean(key))
      );
      function sourceIdentityText(identity, fallbackWorkspaceId) {
        const sourceIdentity = identity || {};
        const tool = String(sourceIdentity.tool || 'unknown');
        const repo = String(sourceIdentity.repo_name || 'unknown');
        const workspace = String(sourceIdentity.workspace_id || fallbackWorkspaceId || 'unknown');
        return `tool ${tool} · repo ${repo} · workspace ${workspace}`;
      }
      function sourceOriginText(value) {
        const sourceValue = value || {};
        const originSummary = String(sourceValue.latest_origin_summary || sourceValue.origin_summary || 'unknown');
        return `origin ${originSummary}`;
      }
      function identityAnchorText(anchor, resolution) {
        const identityAnchor = anchor || {};
        const identityResolution = resolution || {};
        const key = String(identityAnchor.key || identityResolution.key || 'unknown-anchor');
        const resolutionMethod = String(identityAnchor.resolution_method || identityResolution.resolution_method || 'unknown');
        if (resolution) {
          const sessionCount = Number(identityResolution.session_count || 0);
          return `identity ${key} · via ${resolutionMethod} · cross session ${identityResolution.cross_session ? 'yes' : 'no'} · sessions ${sessionCount}`;
        }
        const resolved = identityResolutionByKey.get(key) || {};
        const crossSession = resolved.cross_session;
        const sessionCount = Number(resolved.session_count || 0);
        const suffix = typeof crossSession === 'boolean'
          ? ` · cross session ${crossSession ? 'yes' : 'no'} · sessions ${sessionCount}`
          : '';
        return `identity ${key} · via ${resolutionMethod}${suffix}`;
      }
      function parentActionText(action, prefix = 'parent action') {
        const parentAction = action || {};
        const actionId = String(parentAction.action_id || 'none');
        if (actionId === 'none') return `${prefix} none`;
        const agent = String(parentAction.agent_id || 'unknown');
        const risk = String(parentAction.risk || 'unknown');
        const receiptState = parentAction.available_local_receipt ? 'local' : 'missing';
        const taskSummary = String(parentAction.task_summary || 'unknown');
        return `${prefix} ${actionId} · agent ${agent} · risk ${risk} · receipt ${receiptState} · task ${taskSummary}`;
      }
      function sourceSchemeText(identity) {
        const sourceIdentity = identity || {};
        const sessionScheme = String(sourceIdentity.session_scheme || 'none');
        const sourceScheme = String(sourceIdentity.source_scheme || 'none');
        return `session scheme ${sessionScheme} · source scheme ${sourceScheme}`;
      }
      function attestationText(lineage) {
        const proofLineage = lineage || {};
        return `attestation ${proofLineage.treeship_attestation_status || 'none'} · artifact ${proofLineage.treeship_artifact_id || 'none'}`;
      }
      function systemText(lineage) {
        const proofLineage = lineage || {};
        return `system ${proofLineage.treeship_system || 'none'}`;
      }
      function subjectText(lineage) {
        const proofLineage = lineage || {};
        return `subject ${proofLineage.treeship_subject_key || 'none'}`;
      }
      function signedAtText(lineage) {
        const proofLineage = lineage || {};
        if (!proofLineage.treeship_signed_at) return null;
        return `signed at ${proofLineage.treeship_signed_at}`;
      }
      function payloadDigestText(lineage) {
        const proofLineage = lineage || {};
        if (!proofLineage.treeship_payload_digest) return null;
        return `payload digest ${shortHash(proofLineage.treeship_payload_digest)}`;
      }
      function eventHashText(lineage) {
        const proofLineage = lineage || {};
        if (!proofLineage.event_hash) return null;
        return `event hash ${shortHash(proofLineage.event_hash)}`;
      }
      function receiptHashText(lineage) {
        const proofLineage = lineage || {};
        if (!proofLineage.receipt_hash) return null;
        return `receipt hash ${shortHash(proofLineage.receipt_hash)}`;
      }
      function importedOriginText(origin) {
        const importedOrigin = origin || {};
        if (!importedOrigin.restore_receipt_id) return null;
        const snapshotHash = importedOrigin.snapshot_hash ? shortHash(importedOrigin.snapshot_hash) : 'unknown';
        const restoreReceiptHash = importedOrigin.restore_receipt_hash ? shortHash(importedOrigin.restore_receipt_hash) : 'unknown';
        const continuityStatus = importedOrigin.continuity_sidecar_ok === true
          ? 'ok'
          : (importedOrigin.continuity_sidecar_ok === false ? 'failed' : 'none');
        const parts = [
          `imported restore ${importedOrigin.restore_receipt_id}`,
          `snapshot ${snapshotHash}`,
          `receipt hash ${restoreReceiptHash}`,
          `continuity ${continuityStatus}`,
        ];
        if (importedOrigin.continuity_error) parts.push(`error ${importedOrigin.continuity_error}`);
        return parts.join(' · ');
      }
      function restoreLineageText(lineage) {
        const restoreLineage = lineage || {};
        if (!restoreLineage.kind) return null;
        const parts = [`restore lineage ${restoreLineage.kind}`];
        if (restoreLineage.basis) parts.push(`basis ${restoreLineage.basis}`);
        if (restoreLineage.restore_created_at) parts.push(`restore at ${restoreLineage.restore_created_at}`);
        if (restoreLineage.source_receipt_created_at) parts.push(`receipt at ${restoreLineage.source_receipt_created_at}`);
        return parts.join(' · ');
      }
      function workspaceContinuityText(continuity) {
        const continuityAnchor = continuity || {};
        if (!continuityAnchor.kind) return null;
        const snapshotHash = continuityAnchor.snapshot_hash ? shortHash(continuityAnchor.snapshot_hash) : 'unknown';
        const actionId = continuityAnchor.action_id || 'none';
        const manifestPath = continuityAnchor.manifest_path || 'none';
        const restoreReceiptId = continuityAnchor.restore_receipt_id || null;
        const continuityError = continuityAnchor.continuity_error || null;
        const continuityStatus = continuityAnchor.continuity_sidecar_ok === true
          ? 'ok'
          : (continuityAnchor.continuity_sidecar_ok === false ? 'failed' : null);
        const continuitySidecarPath = continuityAnchor.continuity_sidecar_path || null;
        const sourcePath = continuityAnchor.snapshot_path || 'none';
        const parts = [
          `workspace continuity ${continuityAnchor.kind}`,
          `snapshot ${snapshotHash}`,
          `action ${actionId}`,
        ];
        if (restoreReceiptId) parts.push(`restore receipt ${restoreReceiptId}`);
        if (manifestPath !== 'none') parts.push(`manifest ${manifestPath}`);
        if (continuityStatus) parts.push(`continuity ${continuityStatus}`);
        if (continuityError) parts.push(`error ${continuityError}`);
        if (continuitySidecarPath) parts.push(`sidecar ${continuitySidecarPath}`);
        parts.push(`source ${sourcePath}`);
        return parts.join(' · ');
      }
      function tieDetailsText(preview) {
        const tieFields = Array.isArray(preview.tie_fields) ? preview.tie_fields : [];
        if (!tieFields.length) return null;
        return `tie fields ${tieFields.join(', ') || 'none'}`;
      }
      function ignoredTieBreakersText(preview) {
        const ignoredTieBreakers = Array.isArray(preview.ignored_tie_breakers) ? preview.ignored_tie_breakers : [];
        if (!ignoredTieBreakers.length) return null;
        return `ignored tie breakers ${ignoredTieBreakers.join(', ') || 'none'}`;
      }
      function resolutionTraceText(preview) {
        const trace = Array.isArray(preview.resolution_trace) ? preview.resolution_trace : [];
        return trace.map((step) => `resolution trace ${step.summary || `${step.field || 'field'} ${step.outcome || 'preview'}`}`);
      }
      function decisiveClaimText(preview) {
        const decisiveClaim = (preview || {}).decisive_claim_lineage || {};
        if (!decisiveClaim.memory_id) return null;
        const proofLineage = decisiveClaim.proof_lineage || {};
        const parts = [
          `decision source ${decisiveClaim.summary || 'read-only merge preview'}`,
          `${decisiveClaim.agent_id || 'unknown agent'} @ ${decisiveClaim.chat_session_id || 'no session'}`,
        ];
        if (decisiveClaim.source_uri) parts.push(`via ${decisiveClaim.source_uri}`);
        parts.push(`receipt ${proofLineage.receipt_id || 'none'}`);
        parts.push(attestationText(proofLineage));
        parts.push(systemText(proofLineage));
        parts.push(subjectText(proofLineage));
        const eventHash = eventHashText(proofLineage);
        if (eventHash) parts.push(eventHash);
        const receiptHash = receiptHashText(proofLineage);
        if (receiptHash) parts.push(receiptHash);
        parts.push(`root ${shortHash(proofLineage.merkle_root)}`);
        return parts.join(' · ');
      }
      function losingClaimContrastText(preview) {
        const losingContrast = (preview || {}).losing_claim_contrast || {};
        if (!(losingContrast.losing_claim_count > 0)) return null;
        return `decision contrast ${losingContrast.summary || 'read-only merge preview'}`;
      }
      function losingClaimParentActionText(preview) {
        const losingAction = (preview || {}).losing_claim_parent_action || {};
        const action = losingAction.parent_action || {};
        if (!action.action_id) return null;
        return `losing action ${losingAction.summary || 'read-only merge preview'} · ${parentActionText(action, 'losing action')}`;
      }
      if (!agents.length && !sources.length && !conflicts.length) {
        $('workspaceSources').innerHTML = '<div class="empty">No source-lineage receipts yet. Agent writes will appear here after memory is saved.</div>';
        return;
      }
      const continuityText = workspaceContinuityText(report.workspace_continuity);
      const agentCards = agents.slice(0, 6).map((agent) => {
        const latestProof = agent.latest_proof_lineage || {};
        const latestImportedOrigin = importedOriginText(agent.latest_imported_origin);
        const latestRestoreLineage = restoreLineageText(agent.latest_restore_lineage);
        const latestSignedAt = signedAtText(latestProof);
        const latestPayloadDigest = payloadDigestText(latestProof);
        const latestEventHash = eventHashText(latestProof);
        const latestReceiptHash = receiptHashText(latestProof);
        const sourceUriPreview = String(agent.source_uri_preview || 'none');
        return `<div class="quick-card">
          <strong>${escapeHtml(agent.agent_id || 'unknown agent')}</strong>
          <span>${escapeHtml(sourceIdentityText(agent, report.workspace_id))}</span>
          <span>${escapeHtml(sourceOriginText(agent))}</span>
          <span>${escapeHtml(identityAnchorText(agent.identity_anchor, agent.identity_resolution))}</span>
          ${latestRestoreLineage ? `<span>${escapeHtml(latestRestoreLineage)}</span>` : ''}
          ${latestImportedOrigin ? `<span>${escapeHtml(latestImportedOrigin)}</span>` : ''}
          <span>${escapeHtml(parentActionText(agent.latest_parent_action, 'latest parent action'))}</span>
          <span>${escapeHtml((agent.chat_session_ids || []).join(', ') || 'no sessions')}</span>
          <span>${escapeHtml(`source URIs ${sourceUriPreview}`)}</span>
          <span>${escapeHtml(`memories ${agent.memory_count || 0} · ${attestationText(latestProof)} · ${systemText(latestProof)} · ${subjectText(latestProof)}${latestSignedAt ? ` · ${latestSignedAt}` : ''}${latestPayloadDigest ? ` · ${latestPayloadDigest}` : ''}`)}</span>
          <span>${escapeHtml(`${latestEventHash || 'event hash none'} · ${latestReceiptHash || 'receipt hash none'} · latest root ${shortHash(latestProof.merkle_root)}`)}</span>
        </div>`;
      }).join('');
      const sourceRows = sources.slice(0, 5).map((source) => {
        const lineage = source.proof_lineage || {};
        const restoreLineage = restoreLineageText(source.restore_lineage);
        const importedOrigin = importedOriginText(source.imported_origin);
        const signedAt = signedAtText(lineage);
        const payloadDigest = payloadDigestText(lineage);
        const eventHash = eventHashText(lineage);
        const receiptHash = receiptHashText(lineage);
        return `<div class="item">
          <div class="meta">
            ${pill(source.agent_id || 'unknown agent')}
            ${pill(source.trust_status || 'unknown')}
            ${pill(source.source_kind || 'unknown source')}
          </div>
          <div class="content">${escapeHtml(source.source_uri || 'no source URI recorded')}</div>
          <div class="topline">${escapeHtml(sourceIdentityText(source.source_identity, source.workspace_id))}</div>
          <div class="topline">${escapeHtml(sourceOriginText(source.source_identity))}</div>
          <div class="topline">${escapeHtml(identityAnchorText(source.identity_anchor, source.identity_resolution))}</div>
          ${restoreLineage ? `<div class="topline">${escapeHtml(restoreLineage)}</div>` : ''}
          ${importedOrigin ? `<div class="topline">${escapeHtml(importedOrigin)}</div>` : ''}
          <div class="topline">${escapeHtml(parentActionText(source.parent_action))}</div>
          <div class="topline">${escapeHtml(sourceSchemeText(source.source_identity))}</div>
          <div class="topline">${escapeHtml(source.chat_session_id || 'no session')} · receipt ${escapeHtml(lineage.receipt_id || 'none')} · ${escapeHtml(attestationText(lineage))} · ${escapeHtml(systemText(lineage))} · ${escapeHtml(subjectText(lineage))}${signedAt ? ` · ${escapeHtml(signedAt)}` : ''}${payloadDigest ? ` · ${escapeHtml(payloadDigest)}` : ''}${eventHash ? ` · ${escapeHtml(eventHash)}` : ''}${receiptHash ? ` · ${escapeHtml(receiptHash)}` : ''} · root ${escapeHtml(shortHash(lineage.merkle_root))}</div>
        </div>`;
      }).join('');
      const conflictRows = conflicts.slice(0, 3).map((conflict) => {
        const preview = conflict.merge_preview || {};
        const resolutionBasis = (preview.resolution_basis || {}).summary || 'read-only merge preview';
        const tieDetails = tieDetailsText(preview);
        const ignoredTieBreakers = ignoredTieBreakersText(preview);
        const resolutionTrace = resolutionTraceText(preview);
        const decisiveClaim = decisiveClaimText(preview);
        const losingContrast = losingClaimContrastText(preview);
        const losingAction = losingClaimParentActionText(preview);
        const claims = (conflict.claims || []).slice(0, 3).map((claim) => {
          const lineage = claim.proof_lineage || {};
          const chosen = preview.chosen_memory_id && preview.chosen_memory_id === claim.memory_id;
          const restoreLineage = restoreLineageText(claim.restore_lineage);
          const importedOrigin = importedOriginText(claim.imported_origin);
          const signedAt = signedAtText(lineage);
          const payloadDigest = payloadDigestText(lineage);
          const eventHash = eventHashText(lineage);
          const receiptHash = receiptHashText(lineage);
          return `<div class="quick-card">
            <strong>${escapeHtml(claim.agent_id || 'unknown agent')} · ${escapeHtml(claim.value || 'unknown claim')}</strong>
            <span>${escapeHtml(claim.chat_session_id || 'no session')}</span>
            <span>${escapeHtml(sourceIdentityText(claim.source_identity, claim.workspace_id))}</span>
            <span>${escapeHtml(sourceOriginText(claim.source_identity))}</span>
            <span>${escapeHtml(identityAnchorText(claim.identity_anchor, claim.identity_resolution))}</span>
            ${restoreLineage ? `<span>${escapeHtml(restoreLineage)}</span>` : ''}
            ${importedOrigin ? `<span>${escapeHtml(importedOrigin)}</span>` : ''}
            <span>${escapeHtml(parentActionText(claim.parent_action))}</span>
            <span>${escapeHtml(sourceSchemeText(claim.source_identity))}</span>
            <span>${escapeHtml(`${claim.trust_status || 'unknown'} · ${claim.authority || 'unknown'} authority`)}</span>
            <span>${escapeHtml(`${attestationText(lineage)} · ${systemText(lineage)} · ${subjectText(lineage)}${signedAt ? ` · ${signedAt}` : ''}${payloadDigest ? ` · ${payloadDigest}` : ''}${eventHash ? ` · ${eventHash}` : ''}${receiptHash ? ` · ${receiptHash}` : ''} · root ${shortHash(lineage.merkle_root)}${chosen ? ' · selected' : ''}`)}</span>
          </div>`;
        }).join('');
        const headline = `${conflict.subject_key || 'unknown entity'} ${conflict.relation || 'is'}`;
        return `<div class="item">
          <div class="meta">
            ${pill(preview.resolution_outcome || 'unknown')}
            ${pill(`agents ${(conflict.connected_agent_ids || []).length}`)}
            ${pill(`sessions ${(conflict.chat_session_ids || []).length}`)}
          </div>
          <div class="content">${escapeHtml(headline)}</div>
          <div class="topline">${escapeHtml(preview.rule_summary || 'read-only merge preview')}</div>
          <div class="topline">${escapeHtml(`resolution basis ${resolutionBasis}`)}</div>
          ${decisiveClaim ? `<div class="topline">${escapeHtml(decisiveClaim)}</div>` : ''}
          ${losingContrast ? `<div class="topline">${escapeHtml(losingContrast)}</div>` : ''}
          ${losingAction ? `<div class="topline">${escapeHtml(losingAction)}</div>` : ''}
          ${tieDetails ? `<div class="topline">${escapeHtml(tieDetails)}</div>` : ''}
          ${ignoredTieBreakers ? `<div class="topline">${escapeHtml(ignoredTieBreakers)}</div>` : ''}
          ${resolutionTrace.map((step) => `<div class="topline">${escapeHtml(step)}</div>`).join('')}
          <div class="quick-grid" style="margin-top:12px">${claims}</div>
        </div>`;
      }).join('');
      $('workspaceSources').innerHTML = `
        <div class="proof-status">
          ${pill(`agents ${report.connected_agent_count || 0}`)}
          ${pill(`sessions ${report.chat_session_count || 0}`)}
          ${pill(`sources ${report.source_count || 0}`)}
          ${pill(`claim conflicts ${report.claim_conflict_count || 0}`)}
          ${pill(report.workspace_id || 'workspace none')}
        </div>
        ${continuityText ? `<div class="topline" style="margin-top:10px">${escapeHtml(continuityText)}</div>` : ''}
        <div class="quick-grid">${agentCards}</div>
        ${conflicts.length ? `<h3 style="margin-top:14px">Claim Conflicts</h3><div class="list" style="margin-top:12px">${conflictRows}</div>` : ''}
        <h3 style="margin-top:14px">Recent Source Lineage</h3>
        <div class="list" style="margin-top:12px">${sourceRows}</div>`;
    }

    function renderBoundaryZones(provenItems, assertedItems) {
      const proven = (provenItems || []).map((item) => `<li>${escapeHtml(item)}</li>`).join('');
      const asserted = (assertedItems || []).map((item) => `<li>${escapeHtml(item)}</li>`).join('');
      return `<div class="split-view">
        <div class="zone proven"><strong>Proven Zone</strong><ul>${proven || '<li>No committed proof fields exposed for this object.</li>'}</ul></div>
        <div class="zone asserted"><strong>Asserted Zone</strong><ul>${asserted || '<li>No provider outcome fields exposed for this object.</li>'}</ul></div>
      </div>`;
    }

    function renderLaunchAssetStoryboard(assets, missingPaths) {
      if (!assets || !assets.length) return `<div class="empty">Launch asset storyboard unavailable.</div>`;
      const missing = new Set((missingPaths || []).map((path) => String(path)));
      return assets.map((asset) => {
        const outputPath = String(asset.output_path || '');
        const ready = outputPath && !missing.has(outputPath);
        return `<div class="story-card">
          <strong>${escapeHtml(String(asset.deliverable || 'unknown'))}</strong>
          <p>${escapeHtml(String(asset.id || 'unknown'))}</p>
          <code>${escapeHtml(outputPath || 'missing output path')}</code>
          <p>${escapeHtml(ready ? 'Captured in the proof pack.' : 'Still missing from the proof pack.')}</p>
        </div>`;
      }).join('');
    }

    function renderCodeList(paths, emptyText) {
      if (!paths || !paths.length) return `<div class="empty">${escapeHtml(emptyText)}</div>`;
      return paths.map((path) => `<code>${escapeHtml(path)}</code>`).join('<br>');
    }

    function renderTopicSummary(query, memories) {
      if (!query) return '<div class="empty">Enter a topic to inspect local memory.</div>';
      if (!memories.length) {
        return `<div class="empty">No local memory matched "${escapeHtml(query)}". That absence is useful: the agent should not pretend it knows.</div>`;
      }
      const active = memories.filter((memory) => memory.status === 'active').length;
      const queued = memories.filter((memory) => memory.status === 'quarantined' || memory.status === 'proposed').length;
      const proofCells = `
        <div class="proof-grid">
          ${proofCell('Topic', query)}
          ${proofCell('Matches', String(memories.length))}
          ${proofCell('Active / queued', `${active} / ${queued}`)}
        </div>`;
      return `${proofCells}<div class="list">${memories.slice(0, 8).map((memory) => memoryItem(memory, false)).join('')}</div>`;
    }

    function setSessionAgentOptions(agents) {
      const select = $('sessionAgent');
      const previous = select.value;
      const available = (agents || []).filter((agent) => agent.agent_id);
      select.innerHTML = available.map((agent) => `<option value="${escapeHtml(agent.agent_id)}">${escapeHtml(agent.label || agent.agent_id)}</option>`).join('');
      if (available.some((agent) => agent.agent_id === previous)) {
        select.value = previous;
        return;
      }
      const preferred = available.find((agent) => agent.live)
        || available.find((agent) => agent.configured)
        || available.find((agent) => agent.observed)
        || available[0];
      if (preferred) select.value = preferred.agent_id;
    }

    function renderSessionInvitation(invitation) {
      const attachArgs = JSON.stringify({activation_code: invitation.activation_code});
      lastSessionInstruction = `Call memory.session_attach with ${attachArgs}\nIf your client exposes its chat/session id, include it as client_session_id.`;
      $('sessionInviteResult').innerHTML = `
        <div class="proof-grid">
          ${proofCell('Agent', invitation.agent_id)}
          ${proofCell('Scope', invitation.scope)}
          ${proofCell('Expires', invitation.expires_at)}
        </div>
        <div class="content"><strong>Paste this into the selected agent chat</strong></div>
        <pre><code>${escapeHtml(lastSessionInstruction)}</code></pre>
        <div class="toolbar">
          <button data-session-action="copy">Copy Instruction</button>
          ${invitation.room_id ? pill(`Room ${invitation.room_id}`) : ''}
          ${pill('one time')}
        </div>
        <p class="helper" style="margin-top:10px">The code is stored only as a hash. It binds the consuming MCP connector; any client session id remains asserted unless the host verifies it.</p>`;
    }

    async function createSessionInvite(agentOverride = null) {
      const agentId = agentOverride || $('sessionAgent').value;
      if (!agentId) throw new Error('Choose an agent first.');
      $('sessionAgent').value = agentId;
      const result = await api('/api/sessions/invitations', {
        method: 'POST',
        body: JSON.stringify({
          agent_id: agentId,
          session_label: $('sessionLabel').value.trim() || null,
          scope: $('sessionScope').value.trim() || 'project',
          room_id: $('sessionRoom').value.trim() || null,
        }),
      });
      renderSessionInvitation(result);
      return result;
    }

    function renderContinuity(state) {
      const continuity = state.agent_continuity || {};
      const agents = continuity.agents || [];
      setSessionAgentOptions(agents);
      const agentCards = agents.map((agent) => {
        const sessions = agent.chat_session_ids || [];
        const attachedSessions = agent.session_attachments || [];
        const connectionLabel = String(agent.connection_state || 'not connected').replaceAll('_', ' ');
        const activity = agent.observed
          ? `${agent.memory_count || 0} memories · ${sessions.length} sessions`
          : 'No writes observed yet';
        const source = agent.latest_origin_summary || agent.source_uri_preview || 'No source provenance yet';
        const attachmentRows = attachedSessions.length
          ? attachedSessions.map((session) => `<div class="session-row">
              <span>${escapeHtml(session.session_label || session.client_session_id || 'unnamed')} · ${escapeHtml(session.presence)} · ${escapeHtml(session.identity_assurance)}</span>
              ${session.state === 'active' ? `<button class="danger" data-session-action="detach" data-id="${escapeHtml(session.attachment_id)}">Detach</button>` : ''}
            </div>`).join('')
          : '<p>No explicit live-session attachment</p>';
        return `<div class="story-card">
          <div class="proof-status">${pill(connectionLabel)}${agent.live ? pill('live now') : ''}${agent.shared_store_match ? pill('shared store') : ''}</div>
          <strong>${escapeHtml(agent.label)}</strong>
          <p>${escapeHtml(activity)}</p>
          ${attachmentRows}
          <p>${escapeHtml(source)}</p>
          <code>${escapeHtml((agent.configured || agent.export_ready) ? (agent.path || 'configured') : agent.setup_command)}</code>
          <div class="actions" style="margin-top:10px"><button data-session-action="invite" data-agent="${escapeHtml(agent.agent_id)}">Invite This Agent</button></div>
        </div>`;
      }).join('');
      const commands = (continuity.commands || []).map((command) => `<code>${escapeHtml(command)}</code>`).join('<br>');
      $('continuity').innerHTML = `
        <div class="proof-status">
          ${pill(`configured ${continuity.configured_count || 0}`)}
          ${pill(`exports ${continuity.export_ready_count || 0}`)}
          ${pill(`observed ${continuity.observed_count || 0}`)}
          ${pill(`active ${continuity.active_count || 0}`)}
          ${pill(`live sessions ${continuity.live_session_count || 0}`)}
          ${pill(continuity.shared_memory_ready ? 'multi-agent ready' : 'connect another agent')}
          ${pill(continuity.handoff_ready ? 'handoff ready' : 'handoff pending')}
        </div>
        <div class="story-grid">${agentCards}</div>
        <div class="proof-grid">
          ${proofCell('Shared memory DB', continuity.db_path || 'unknown')}
          ${proofCell('Policy', continuity.policy_path || 'none')}
          ${proofCell('Transfer package', continuity.handoff_path || '.zerker/handoff')}
        </div>
        <p class="helper">Connect, verify, and transfer:</p>
        <pre>${commands}</pre>`;
    }

    function renderRoomInventory(state) {
      const inventory = state.room_inventory || {};
      const rooms = inventory.rooms || [];
      if (!rooms.length) {
        $('roomInventory').innerHTML = `<div class="empty">No local Rooms have written memory yet. Start the Rooms service with <code>zmem serve</code>; stores will appear after Gateway records or proposes the first memory.</div>`;
        return;
      }
      const cards = rooms.map((room) => {
        if (room.inventory_state === 'unreadable') {
          return `<div class="story-card">
            <div class="proof-status">${pill('unreadable')}</div>
            <strong>${escapeHtml(room.room_id)}</strong>
            <p>The local Room store could not be inspected. Other Rooms remain available.</p>
            <code>${escapeHtml(room.storage_id)}</code>
          </div>`;
        }
        const status = room.status_counts || {};
        const semantic = room.semantic_index || {};
        const contributors = (room.observed_contributor_ids || []).join(', ') || 'none observed';
        return `<div class="story-card">
          <div class="proof-status">${pill(`shared ${room.shared_memory_count || 0}`)}${pill(`private ${room.member_private_memory_count || 0}`)}</div>
          <strong>${escapeHtml(room.room_id)}</strong>
          <p>${escapeHtml(`contributors ${contributors}`)}</p>
          <p>${escapeHtml(`active ${status.active || 0} · review ${Number(status.quarantined || 0) + Number(status.proposed || 0)} · semantic index ${Math.round(Number(semantic.coverage || 0) * 100)}%`)}</p>
          <code>${escapeHtml(shortHash(room.latest_merkle_root) || room.storage_id)}</code>
        </div>`;
      }).join('');
      $('roomInventory').innerHTML = `
        <div class="proof-status">
          ${pill(`rooms ${inventory.room_count || 0}`)}
          ${pill(`memories ${inventory.memory_count || 0}`)}
          ${pill(`contributors ${(inventory.observed_contributor_ids || []).length}`)}
          ${inventory.unreadable_room_count ? pill(`unreadable ${inventory.unreadable_room_count}`) : ''}
          ${pill(`tenant ${inventory.tenant_id || 'local'}`)}
        </div>
        <div class="story-grid">${cards}</div>
        <p class="helper">${escapeHtml(inventory.membership_note || '')}</p>`;
    }

    function renderMemorySpotlight(state) {
      const memories = state.memories || [];
      const focused = memories.filter((memory) => {
        const labels = memory.labels || [];
        return labels.includes('dogfood') || labels.includes('benchmark') || labels.includes('agent-integration') || labels.includes('public-evidence');
      }).slice(0, 5);
      if (!focused.length) {
        $('memorySpotlight').innerHTML = '<div class="empty">No dogfood or benchmark memories are active yet. Use Add Memory or run the agent smoke checks.</div>';
        return;
      }
      $('memorySpotlight').innerHTML = `<div class="quick-grid">${focused.map((memory) => `<div class="quick-card">
        <strong>${escapeHtml(memory.id)}</strong>
        <span>${escapeHtml(memory.content)}</span>
        <span>${(memory.labels || []).map((label) => '#' + escapeHtml(label)).join(' ')}</span>
      </div>`).join('')}</div>`;
    }

    function renderAgentBenchmarkSpotlight(state) {
      const continuity = state.agent_continuity || {};
      const agents = continuity.agents || [];
      const readyAgents = agents.filter((agent) => agent.ready).map((agent) => agent.label);
      const release = state.release_readiness || {};
      const benchmarkPath = 'http://127.0.0.1:8766/benchmarks.html';
      const internalDashboard = '.zerker/bench/internal-synthetic-20260606/benchmark-dashboard.html';
      $('agentBenchmarkSpotlight').innerHTML = `<div class="quick-grid">
        <div class="quick-card">
          <strong>Agents Ready</strong>
          <span>${escapeHtml(readyAgents.join(', ') || 'No agent configs found')}</span>
        </div>
        <div class="quick-card">
          <strong>Benchmark Page</strong>
          <span><a href="${benchmarkPath}" target="_blank" rel="noreferrer">Open public evidence</a></span>
          <span>${escapeHtml(benchmarkPath)}</span>
        </div>
        <div class="quick-card">
          <strong>Internal Dashboard</strong>
          <span>${escapeHtml(internalDashboard)}</span>
        </div>
        <div class="quick-card">
          <strong>Launch Gate</strong>
          <span>${escapeHtml(release.strict_publish_ready ? 'Strict publish ready' : 'Strict publish still blocked on external proof/assets')}</span>
        </div>
        <div class="quick-card">
          <strong>Use Memory</strong>
          <span>Try: What is the ZMem agent integration status for Codex and Claude Code?</span>
        </div>
        <div class="quick-card">
          <strong>Verify Proof</strong>
          <span>Recent receipts appear below. Click Why or Bundle to inspect what memory influenced an action.</span>
        </div>
      </div>`;
    }

    function renderOutput(payload) {
      $('rawOutput').textContent = JSON.stringify(payload, null, 2);
      $('proofSummary').innerHTML = renderSummary(payload);
      $('proofSummary').scrollIntoView({behavior: 'smooth', block: 'start'});
    }

    function renderReleaseStatus(state) {
      const release = state.release_readiness || {};
      if (!release.repo_surface_present) {
        $('releaseStatus').innerHTML = '<div class="empty">Release checks appear in the full repo where README, QUICKSTART, landing, and smoke scripts are present.</div>';
        return;
      }
      if (!release.launch_proof_ready) {
        const nextStep = escapeHtml((release.strict_publish_next_steps || [])[0] || 'zmem release-pack --summary-only');
        $('releaseStatus').innerHTML = `
          <div class="proof-status">
            ${pill('launch proof missing')}
            ${pill(release.handoff_ready ? 'handoff ok' : 'handoff missing')}
            ${pill('release pack needed')}
            ${pill(release.strict_publish_ready ? 'strict publish ok' : 'strict publish blocked')}
          </div>
          <div class="story-grid">
            <div class="story-card">
              <strong>Generate release pack first</strong>
              <p>Run <code>zmem release-pack --summary-only</code> before forwarding the clean-shell handoff or asking another chat to capture launch assets.</p>
              <code>${nextStep}</code>
            </div>
            <div class="story-card">
              <strong>Public verify</strong>
              <p>${escapeHtml(release.public_verify_details || 'Pending')}</p>
              <code>zmem release-pack --summary-only</code>
            </div>
            <div class="story-card">
              <strong>Launch assets</strong>
              <p>${escapeHtml(release.launch_assets_details || 'Pending')}</p>
              <code>zmem release-pack --summary-only</code>
            </div>
            <div class="story-card">
              <strong>Return packet</strong>
              <p>${escapeHtml(release.return_packet_details || 'Pending')}</p>
              <code>zmem release-pack --summary-only</code>
            </div>
          </div>
        `;
        return;
      }
      const blockers = (release.strict_publish_blockers || []).map((item) => pill(item)).join('');
      const warnings = (release.strict_publish_warnings || []).map((item) => pill(item)).join('');
      const nextSteps = (release.strict_publish_next_steps || []).map((step) => `<code>${escapeHtml(step)}</code>`).join('<br>');
      const publicVerifyMissing = renderCodeList(release.public_verify_missing_paths || [], 'Clean-shell logs are complete.');
      const launchAssetMissing = renderCodeList(release.launch_assets_missing_paths || [], 'Launch assets are complete.');
      const launchAssetStoryboard = renderLaunchAssetStoryboard(release.expected_launch_assets || [], release.launch_assets_missing_paths || []);
      const returnPacketMissing = renderCodeList(release.return_packet_missing_paths || [], 'Return packet roots are structurally present.');
      $('releaseStatus').innerHTML = `
        <div class="proof-status">
          ${pill(release.launch_proof_ready ? 'launch proof ok' : 'launch proof missing')}
          ${pill(release.handoff_ready ? 'handoff ok' : 'handoff missing')}
          ${pill(release.operator_packet_ready ? 'operator packet ok' : 'operator packet pending')}
          ${pill(release.public_verify_ready ? 'public verify ok' : 'public verify pending')}
          ${pill(release.launch_assets_ready ? 'launch assets ok' : 'launch assets pending')}
          ${pill(release.return_packet_ready ? 'return packet ok' : 'return packet pending')}
          ${pill(release.local_alpha_ready ? 'local alpha ok' : 'local alpha blocked')}
          ${pill(release.strict_publish_ready ? 'strict publish ok' : 'strict publish blocked')}
        </div>
        <div class="proof-grid">
          ${proofCell('Launch proof dir', release.launch_proof_dir || '.zerker/launch-proof')}
          ${proofCell('Handoff dir', release.handoff_dir || '.zerker/handoff')}
          ${proofCell('Capture checklist', release.capture_checklist_path || '.zerker/launch-proof/CAPTURE_CHECKLIST.md')}
          ${proofCell('Launch asset handoff', release.launch_asset_handoff_path || '.zerker/launch-proof/LAUNCH_ASSET_HANDOFF.md')}
          ${proofCell('Public verify handoff', release.public_verify_handoff_path || '.zerker/launch-proof/PUBLIC_VERIFY_HANDOFF.md')}
          ${proofCell('Receive-side handoff', release.receive_verify_handoff_path || '.zerker/launch-proof/RECEIVE_VERIFY_HANDOFF.md')}
          ${proofCell('Public verify script', release.public_verify_script_path || '.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh')}
          ${proofCell('Operator packet', release.operator_packet_archive_path || '.zerker/launch-proof/public-verify-operator-packet.tar.gz')}
          ${proofCell('Public verify logs', `${release.public_verify_present_count || 0}/${release.public_verify_expected_count || 0}`)}
          ${proofCell('Public verify result', release.public_verify_result_path || '.zerker/launch-proof/public-verify-result.json')}
          ${proofCell('Public verify summary', release.public_verify_summary_path || '.zerker/launch-proof/public-verify-summary.md')}
          ${proofCell('Launch assets', `${release.launch_assets_present_count || 0}/${release.launch_assets_expected_count || 0}`)}
          ${proofCell('Return packet archive', release.return_packet_archive_path || '.zerker/launch-proof/public-verify-return-packet.tar.gz')}
          ${proofCell('Return finalize', release.return_packet_finalize_script_path || '.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh')}
          ${proofCell('Assets dir', release.launch_assets_outputs_dir_path || '.zerker/launch-proof/assets')}
          ${proofCell('Next strict step', (release.strict_publish_next_steps || [])[0] || 'none')}
        </div>
        <div class="story-grid">
          <div class="story-card">
            <strong>Operator packet</strong>
            <p>${escapeHtml(release.operator_packet_details || 'Pending')}</p>
            <code>${escapeHtml(release.operator_packet_archive_path || '.zerker/launch-proof/public-verify-operator-packet.tar.gz')}</code>
          </div>
          <div class="story-card">
            <strong>Public verify</strong>
            <p>${escapeHtml(release.public_verify_details || 'Pending')}</p>
            <code>${escapeHtml(release.public_verify_result_path || '.zerker/launch-proof/public-verify-result.json')}</code>
          </div>
          <div class="story-card">
            <strong>Launch assets</strong>
            <p>${escapeHtml(release.launch_assets_details || 'Pending')}</p>
            <code>${escapeHtml(release.launch_assets_outputs_dir_path || '.zerker/launch-proof/assets')}</code>
          </div>
          <div class="story-card">
            <strong>Return packet</strong>
            <p>${escapeHtml(release.return_packet_details || 'Pending')}</p>
            <code>${escapeHtml(release.return_packet_archive_path || '.zerker/launch-proof/public-verify-return-packet.tar.gz')}</code>
          </div>
        </div>
        <h3>Missing public-verify logs</h3>
        <div class="content">${publicVerifyMissing}</div>
        <h3>Missing launch assets</h3>
        <div class="content">${launchAssetMissing}</div>
        <h3>Launch asset storyboard</h3>
        <div class="story-grid">${launchAssetStoryboard}</div>
        <h3>Return-packet roots</h3>
        <div class="content">${returnPacketMissing}</div>
        ${(blockers || warnings) ? `<div class="proof-status">${blockers}${warnings}</div>` : ''}
        ${nextSteps ? `<div class="content">${nextSteps}</div>` : ''}
      `;
    }

    function renderOnboarding(state) {
      const onboarding = state.onboarding || {};
      if (!onboarding.show) {
        $('onboarding').hidden = true;
        $('onboarding').innerHTML = '';
        return;
      }
      const checks = (onboarding.checks || []).map((check) => `<div class="check">
        <div class="dot ${check.ready ? 'ready' : 'pending'}"></div>
        <div>
          <strong>${escapeHtml(check.label)}</strong>
          <span>${escapeHtml(check.detail)}</span>
        </div>
      </div>`).join('');
      const commands = (onboarding.commands || []).join('\\n');
      $('onboarding').hidden = false;
      $('onboarding').innerHTML = `
        <div>
          <h2>Start with a governed-memory proof run</h2>
          <p>${escapeHtml(onboarding.message || 'Initialize the local workspace, run the proof harness, and reopen the console once receipts exist.')}</p>
        </div>
        <div class="hero-grid">
          <div class="checklist">${checks}</div>
          <div class="command-list">
            <h3>First-run commands</h3>
            <pre>${escapeHtml(commands)}</pre>
          </div>
        </div>
      `;
    }

    function renderSummary(payload) {
      if (!payload || typeof payload !== 'object') return '<div class="empty">No proof selected.</div>';
      if (payload.format === 'bundle' && payload.payload) return renderBundleSummary(payload);
      if (payload.format === 'snapshot' && payload.payload) return renderSnapshotSummary(payload);
      if (payload.schema === 'zerker.release_pack.v1') return renderReleasePackSummary(payload);
      if (payload.schema === 'zerker.launch_proof.v1') return renderLaunchProofSummary(payload);
      if (payload.schema === 'zerker.handoff.v1') return renderHandoffSummary(payload);
      if (payload.schema === 'zerker.restore_preview.v1') return renderHandoffPreviewSummary(payload);
      if (payload.schema === 'zerker.restore_handoff.v1') return renderRestoreSummary(payload);
      if (payload.schema === 'zerker.launch_assets_verify.v1') return renderLaunchAssetsSummary(payload);
      if (payload.schema === 'zerker.return_packet_verify.v1') return renderReturnPacketSummary(payload);
      if (payload.revoked_ids && payload.memory_id) return renderRevokeSummary(payload);
      if (payload.id && payload.content && payload.status) return renderMemorySummary(payload);
      if (payload.receipt_schema || payload.action_id) return renderReceiptSummary(payload);
      if (payload.ok === false) return `<div class="proof-status">${pill('error')}</div><div class="content">${escapeHtml(payload.error || 'Action failed')}</div>`;
      return renderEmptyProofState();
    }

    function renderRevokeSummary(result) {
      const ids = result.revoked_ids || [];
      const descendants = result.descendant_count || 0;
      return `<div class="proof-status">
          ${pill('revoked')}${pill(ids.length + ' affected')}${pill('descendants ' + descendants)}
        </div>
        <div class="proof-grid">
          ${proofCell('Memory', result.memory_id || 'none')}
          ${proofCell('Revoked count', String(ids.length))}
          ${proofCell('Reason', result.reason || 'none')}
        </div>
        <div class="content">Revoked ${escapeHtml(result.memory_id || '')} and ${descendants} descendant(s). This action is recorded in the receipt chain.</div>`;
    }

    function renderMemorySummary(memory) {
      return `<div class="proof-status">
          ${pill('memory saved')}${pill(memory.status)}${pill(memory.type)}${pill(memory.authority)}
        </div>
        <div class="proof-grid">
          ${proofCell('Memory', memory.id || 'none')}
          ${proofCell('Scope', memory.scope || 'global')}
          ${proofCell('Source', memory.source_kind || 'unknown')}
          ${proofCell('Trust', String(memory.trust || 0))}
        </div>
        <div class="content">${escapeHtml(memory.content || '')}</div>`;
    }

    function renderReleasePackSummary(result) {
      const handoff = result.handoff || {};
      const launchProof = result.launch_proof || {};
      const prelaunch = result.prelaunch || {};
      const operatorPacket = result.operator_packet || {};
      const publicVerify = result.public_verify || {};
      const launchAssets = result.launch_assets || {};
      const nextSteps = (result.next_steps || []).map((step) => `<code>${escapeHtml(step)}</code>`).join('<br>');
      const publicVerifyMissing = renderCodeList(publicVerify.missing_paths || [], 'Clean-shell logs are complete.');
      const launchAssetMissing = renderCodeList(launchAssets.missing_paths || [], 'Launch assets are complete.');
      const launchAssetStoryboard = renderLaunchAssetStoryboard(result.expected_launch_assets || [], launchAssets.missing_paths || []);
      const returnPacketMissing = renderCodeList((result.return_packet || {}).missing_paths || [], 'Return packet roots are structurally present.');
      return `<div class="proof-status">
          ${pill('release pack')}${pill(result.ok ? 'ready' : 'blocked')}${pill(operatorPacket.ok ? 'operator packet ok' : 'operator packet pending')}${pill(prelaunch.ok ? 'prelaunch ok' : 'prelaunch blocked')}
        </div>
        <div class="proof-grid">
          ${proofCell('Launch proof report', launchProof.report_path || 'not written')}
          ${proofCell('Launch proof manifest', launchProof.manifest_path || 'not written')}
          ${proofCell('Handoff manifest', handoff.manifest_path || 'not written')}
          ${proofCell('Prelaunch', prelaunch.ok ? 'ok' : 'blocked')}
          ${proofCell('Action', launchProof.action_id || handoff.action_id || 'none')}
          ${proofCell('Handoff dir', handoff.out_dir || 'not written')}
          ${proofCell('Operator packet', result.operator_packet_archive_path || 'not written')}
          ${proofCell('Public verify logs', `${publicVerify.present_count || 0}/${publicVerify.expected_count || 0}`)}
          ${proofCell('Public verify result', publicVerify.result_path || '.zerker/launch-proof/public-verify-result.json')}
          ${proofCell('Public verify summary', result.public_verify_summary_path || '.zerker/launch-proof/public-verify-summary.md')}
          ${proofCell('Launch assets', `${launchAssets.present_count || 0}/${launchAssets.expected_count || 0}`)}
          ${proofCell('Capture checklist', result.capture_checklist_path || 'not written')}
          ${proofCell('Launch asset handoff', result.launch_asset_handoff_path || 'not written')}
          ${proofCell('Receive-side handoff', result.receive_verify_handoff_path || 'not written')}
          ${proofCell('Return packet archive', result.return_packet_archive_path || '.zerker/launch-proof/public-verify-return-packet.tar.gz')}
          ${proofCell('Return finalize', result.return_packet_finalize_script_path || 'not written')}
        </div>
        <div class="story-grid">
          <div class="story-card">
            <strong>Operator packet</strong>
            <p>${escapeHtml(operatorPacket.details || 'Pending')}</p>
            <code>${escapeHtml(result.operator_packet_archive_path || '.zerker/launch-proof/public-verify-operator-packet.tar.gz')}</code>
          </div>
          <div class="story-card">
            <strong>Public verify</strong>
            <p>${escapeHtml(publicVerify.details || 'Pending')}</p>
            <code>${escapeHtml(publicVerify.result_path || '.zerker/launch-proof/public-verify-result.json')}</code>
          </div>
          <div class="story-card">
            <strong>Launch assets</strong>
            <p>${escapeHtml(launchAssets.details || 'Pending')}</p>
            <code>${escapeHtml(result.launch_assets_dir_path || '.zerker/launch-proof/assets')}</code>
          </div>
          <div class="story-card">
            <strong>Return packet</strong>
            <p>${escapeHtml((result.return_packet || {}).details || 'Pending')}</p>
            <code>${escapeHtml(result.return_packet_archive_path || '.zerker/launch-proof/public-verify-return-packet.tar.gz')}</code>
          </div>
        </div>
        <h3>Missing public-verify logs</h3>
        <div class="content">${publicVerifyMissing}</div>
        <h3>Missing launch assets</h3>
        <div class="content">${launchAssetMissing}</div>
        <h3>Launch asset storyboard</h3>
        <div class="story-grid">${launchAssetStoryboard}</div>
        <h3>Return-packet roots</h3>
        <div class="content">${returnPacketMissing}</div>
        ${nextSteps ? `<div class="content">${nextSteps}</div>` : ''}`;
    }

    function renderEmptyProofState() {
      return `<div class="proof-status">
          ${pill('launch proof path')}${pill('console demo')}
        </div>
        <div class="story-grid">
          <div class="story-card">
            <strong>1. Generate governed state</strong>
            <p>Initialize the workspace, run readiness, and create receipts you can review in the console.</p>
            <code>zmem init && zmem doctor && zmem eval</code>
          </div>
          <div class="story-card">
            <strong>2. Preview a high-risk task</strong>
            <p>Use the deploy demo to show authorized policy memory and quarantined memory in one proof view.</p>
            <code>Load deploy demo -> Preview</code>
          </div>
          <div class="story-card">
            <strong>3. Export portable proof</strong>
            <p>Bundle the receipt or export a snapshot so launch screenshots include a verifiable artifact path.</p>
            <code>Bundle receipt or Export Snapshot</code>
          </div>
        </div>`;
    }

    function renderReceiptSummary(receipt) {
      const injected = receipt.injected_memory_ids || [];
      const withheld = receipt.withheld || receipt.withheld_memory_ids || [];
      const proven = [
        `action_id: ${receipt.action_id || 'none'}`,
        `merkle_root: ${receipt.merkle_root || 'none'}`,
        `created_at: ${receipt.created_at || 'unknown'}`,
        `agent_id: ${receipt.agent_id || 'unknown'}`,
      ];
      const asserted = [
        `task: ${receipt.task || 'No task text'}`,
        `risk: ${receipt.risk || 'unknown'}`,
        `injected_memory_ids: ${injected.length}`,
        `withheld_memory_ids: ${withheld.length}`,
      ];
      return `<div class="proof-status">
          ${pill('receipt')}${pill(receipt.risk || 'risk unknown')}${pill(receipt.agent_id || 'agent unknown')}
        </div>
        <div class="proof-grid">
          ${proofCell('Action', receipt.action_id || 'none')}
          ${proofCell('Merkle root', shortHash(receipt.merkle_root))}
          ${proofCell('Injected / withheld', `${injected.length} / ${withheld.length}`)}
        </div>
        <div class="content">${escapeHtml(receipt.task || 'No task text')}</div>
        ${renderBoundaryZones(proven, asserted)}`;
    }

    function renderBundleSummary(result) {
      const bundle = result.payload;
      const proof = bundle.proof || {};
      const proven = [
        `bundle_hash: ${bundle.bundle_hash || 'none'}`,
        `receipt_merkle_root: ${proof.receipt_merkle_root || 'none'}`,
        `computed_merkle_root: ${proof.computed_merkle_root || 'none'}`,
        `verified: ${String(Boolean(proof.verified))}`,
      ];
      const asserted = [
        `action_id: ${bundle.action_id || 'none'}`,
        `supporting_memory_ids: ${(bundle.supporting_memory_ids || []).length}`,
        `format: ${result.format || 'unknown'}`,
        `path: ${result.path || 'not written'}`,
      ];
      const pathBanner = result.path
        ? `<div class="content" style="margin-bottom:10px">Bundle written to <code style="user-select:all">${escapeHtml(result.path)}</code></div>`
        : '';
      return `${pathBanner}<div class="proof-status">
          ${pill('bundle')}${pill(proof.verified ? 'verified' : 'unverified')}${pill(result.format)}
        </div>
        <div class="proof-grid">
          ${proofCell('Path', result.path || 'not written')}
          ${proofCell('Action', bundle.action_id || 'none')}
          ${proofCell('Bundle hash', shortHash(bundle.bundle_hash))}
          ${proofCell('Receipt root', shortHash(proof.receipt_merkle_root))}
          ${proofCell('Computed root', shortHash(proof.computed_merkle_root))}
          ${proofCell('Events / memories', `${proof.event_count || 0} / ${(bundle.supporting_memory_ids || []).length}`)}
        </div>
        ${renderBoundaryZones(proven, asserted)}`;
    }

    function renderSnapshotSummary(result) {
      const snapshot = result.payload;
      return `<div class="proof-status">
          ${pill('snapshot')}${pill(result.format)}
        </div>
        <div class="proof-grid">
          ${proofCell('Path', result.path || 'not written')}
          ${proofCell('Snapshot hash', shortHash(snapshot.snapshot_hash))}
          ${proofCell('Merkle root', shortHash(snapshot.merkle_root))}
          ${proofCell('Memories', String(snapshot.memory_count || 0))}
          ${proofCell('Events', String(snapshot.event_count || 0))}
          ${proofCell('Receipts', String(snapshot.receipt_count || 0))}
        </div>`;
    }

    function renderLaunchProofSummary(result) {
      return `<div class="proof-status">
          ${pill('launch proof')}${pill(result.ok ? 'ready' : 'failed')}
        </div>
        <div class="proof-grid">
          ${proofCell('Manifest', result.manifest_path || 'not written')}
          ${proofCell('Report', result.report_path || 'not written')}
          ${proofCell('Transcript', result.transcript_path || 'not written')}
          ${proofCell('Capture checklist', result.capture_checklist_path || 'not written')}
          ${proofCell('Launch asset handoff', result.launch_asset_handoff_path || 'not written')}
          ${proofCell('Receive-side handoff', result.receive_verify_handoff_path || 'not written')}
          ${proofCell('Public verify script', result.public_verify_script_path || 'not written')}
          ${proofCell('Return finalize', result.return_packet_finalize_script_path || 'not written')}
          ${proofCell('Public verify logs dir', result.public_verify_logs_dir_path || 'not written')}
          ${proofCell('Action', result.action_id || 'none')}
          ${proofCell('Bundle', result.bundle_path || 'not written')}
          ${proofCell('Snapshot', result.snapshot_path || 'not written')}
          ${proofCell('BT XML', result.bt_xml_path || 'not written')}
          ${proofCell('Launch assets dir', result.launch_assets_dir_path || 'not written')}
        </div>`;
    }

    function renderHandoffSummary(result) {
      return `<div class="proof-status">
          ${pill('handoff')}${pill(result.ok ? 'ready' : 'failed')}
        </div>
        <div class="proof-grid">
          ${proofCell('README', result.readme_path || 'not written')}
          ${proofCell('Manifest', result.manifest_path || 'not written')}
          ${proofCell('Snapshot', result.snapshot_path || 'not written')}
          ${proofCell('Action', result.action_id || 'snapshot only')}
          ${proofCell('Bundle', result.bundle_path || 'none')}
          ${proofCell('Treeship', result.treeship_path || 'none')}
        </div>`;
    }

    function renderHandoffPreviewSummary(result) {
      const effects = result.effects || {};
      const blockers = (result.blockers || []).join(', ') || 'none';
      return `<div class="proof-status">
          ${pill('restore preview')}${pill(result.ready_to_restore ? 'ready' : 'blocked')}${pill('no writes')}
        </div>
        <div class="proof-grid">
          ${proofCell('Preview', result.preview_id || 'none')}
          ${proofCell('Target', result.db_path || 'not selected')}
          ${proofCell('Snapshot', shortHash(result.snapshot_hash))}
          ${proofCell('Manifest', shortHash(result.manifest_hash) || 'standalone snapshot')}
          ${proofCell('New / unchanged', `${effects.new_memory_count || 0} / ${effects.unchanged_memory_count || 0}`)}
          ${proofCell('Conflicts', String(effects.conflict_count || 0))}
          ${proofCell('Deletes', effects.deletes_memory ? 'yes' : 'no')}
        </div>
        <div class="content">${escapeHtml(result.ready_to_restore ? 'Verified and bound to a new local import database.' : `Blocked: ${blockers}`)}</div>`;
    }

    function renderRestoreSummary(result) {
      const restore = result.restore || {};
      return `<div class="proof-status">
          ${pill('handoff restore')}${pill(result.ok ? 'ready' : 'failed')}
        </div>
        <div class="proof-grid">
          ${proofCell('Source', result.source || 'not found')}
          ${proofCell('Imported DB', result.db_path || 'not written')}
          ${proofCell('Snapshot', result.snapshot_path || 'not found')}
          ${proofCell('Bundle', result.bundle_path || 'none')}
          ${proofCell('Memories', String(restore.memory_count || 0))}
          ${proofCell('Receipts', String(restore.receipt_count || 0))}
        </div>`;
    }

    function renderReturnPacketSummary(result) {
      const missing = (result.missing_paths || []).map((path) => `<code>${escapeHtml(path)}</code>`).join('<br>');
      const failedSteps = (result.failed_steps || []).join(', ');
      return `<div class="proof-status">
          ${pill('return packet')}${pill(result.ok ? 'ready' : 'failed')}
        </div>
        <div class="proof-grid">
          ${proofCell('Archive', result.archive_path || 'not found')}
          ${proofCell('Manifest', result.manifest_path || 'not found')}
          ${proofCell('Public verify result', result.public_verify_result_path || 'not found')}
          ${proofCell('Public verify', `${result.public_verify_present_count || 0}/${result.public_verify_expected_count || 0} logs`)}
          ${proofCell('Launch assets', `${result.launch_assets_present_count || 0}/${result.launch_assets_expected_count || 0} assets`)}
          ${proofCell('Action', result.action_id || 'none')}
        </div>
        <div class="story-grid">
          <div class="story-card">
            <strong>Archive status</strong>
            <p>${escapeHtml(result.details || 'Unknown')}</p>
            <code>${escapeHtml(result.archive_path || '.zerker/launch-proof/public-verify-return-packet.tar.gz')}</code>
          </div>
          <div class="story-card">
            <strong>Failed steps</strong>
            <p>${escapeHtml(failedSteps || 'None')}</p>
            <code>${escapeHtml(result.public_verify_result_path || '.zerker/launch-proof/public-verify-result.json')}</code>
          </div>
          <div class="story-card">
            <strong>Missing paths</strong>
            <p>${escapeHtml((result.missing_paths || []).length ? 'Return packet is incomplete.' : 'Return packet matches the shipped contract.')}</p>
            <code>${escapeHtml(result.manifest_path || 'launch-proof.json')}</code>
          </div>
        </div>
        ${missing ? `<div class="content">${missing}</div>` : ''}`;
    }

    function renderLaunchAssetsSummary(result) {
      const missing = (result.missing_paths || []).map((path) => `<code>${escapeHtml(path)}</code>`).join('<br>');
      const launchAssetStoryboard = renderLaunchAssetStoryboard(result.expected_launch_assets || [], result.missing_paths || []);
      return `<div class="proof-status">
          ${pill('launch assets')}${pill(result.ok ? 'ready' : 'failed')}
        </div>
        <div class="proof-grid">
          ${proofCell('Outputs dir', result.outputs_dir_path || 'not found')}
          ${proofCell('Checklist', result.checklist_path || 'not found')}
          ${proofCell('Handoff', result.handoff_path || 'not found')}
          ${proofCell('Assets', `${result.present_count || 0}/${result.expected_count || 0}`)}
        </div>
        <div class="story-grid">
          <div class="story-card">
            <strong>Asset status</strong>
            <p>${escapeHtml(result.details || 'Unknown')}</p>
            <code>${escapeHtml(result.outputs_dir_path || '.zerker/launch-proof/assets')}</code>
          </div>
          <div class="story-card">
            <strong>Checklist source</strong>
            <p>${escapeHtml(result.ok ? 'Storyboard is complete.' : 'Use the generated checklist to finish the remaining captures.')}</p>
            <code>${escapeHtml(result.checklist_path || '.zerker/launch-proof/CAPTURE_CHECKLIST.md')}</code>
          </div>
          <div class="story-card">
            <strong>Operator handoff</strong>
            <p>${escapeHtml(result.handoff_path ? 'Forward the generated handoff when another operator is recording the launch assets.' : 'Launch-asset handoff not found.')}</p>
            <code>${escapeHtml(result.handoff_path || '.zerker/launch-proof/LAUNCH_ASSET_HANDOFF.md')}</code>
          </div>
        </div>
        <h3>Launch asset storyboard</h3>
        <div class="story-grid">${launchAssetStoryboard}</div>
        ${missing ? `<div class="content">${missing}</div>` : ''}`;
    }

    async function load() {
      const state = await api('/api/state');
      $('dbPath').textContent = state.stats.db_path;
      renderOnboarding(state);
      renderReleaseStatus(state);
      renderContinuity(state);
      renderRoomInventory(state);
      renderMemorySpotlight(state);
      renderAgentBenchmarkSpotlight(state);
      renderWorkspaceProfile(state);
      renderWorkspaceSources(state);
      renderMemoryStatusPanel(state);
      renderMemoryClusters(state);
      renderBenchmarkPanel(state);
      $('metrics').innerHTML = [
        ['Memories', state.stats.memory_count],
        ['Queued', (state.stats.memory_status.quarantined || 0) + (state.stats.memory_status.proposed || 0)],
        ['Receipts', state.stats.receipt_count],
        ['Events', state.stats.event_count],
      ].map(([label, value]) => `<div class="metric"><strong>${value}</strong><span>${label}</span></div>`).join('');
      $('queue').innerHTML = state.queue.length ? state.queue.map((m) => memoryItem(m)).join('') : '<div class="empty">Nothing waiting for review.</div>';
      $('memories').innerHTML = state.memories.length ? state.memories.map((m) => memoryItem(m)).join('') : '<div class="empty">No memories yet.</div>';
      $('receipts').innerHTML = state.receipts.length ? state.receipts.map((receipt) => `<div class="item">
        <div class="meta">${pill(receipt.risk)}${pill(receipt.agent_id)}</div>
        <div class="content">${escapeHtml(receipt.task)}</div>
        <div class="topline">${receipt.action_id} · ${receipt.created_at}</div>
        <div class="actions" style="margin-top:10px">
          <button data-action="why" data-id="${receipt.action_id}">Why</button>
          <button data-action="bundle" data-id="${receipt.action_id}">Bundle</button>
        </div>
      </div>`).join('') : '<div class="empty">No receipts yet.</div>';
    }

    async function search() {
      const params = new URLSearchParams();
      if ($('search').value) params.set('q', $('search').value);
      if ($('status').value) params.set('status', $('status').value);
      const result = await api('/api/memories?' + params.toString());
      $('memories').innerHTML = result.memories.length ? result.memories.map((m) => memoryItem(m)).join('') : '<div class="empty">No matching memories.</div>';
    }

    async function inspectTopic() {
      const query = $('topicQuery').value.trim();
      const params = new URLSearchParams();
      if (query) params.set('q', query);
      const result = query ? await api('/api/memories?' + params.toString()) : {memories: []};
      $('topicSummary').innerHTML = renderTopicSummary(query, result.memories || []);
    }

    async function act(action, id) {
      const body = action === 'reject' || action === 'revoke' ? {reason: 'dashboard review'} : {};
      const result = await api(`/api/memories/${id}/${action}`, {method: 'POST', body: JSON.stringify(body)});
      renderOutput(result);
      await load();
    }

    function loadDemoTask() {
      $('task').value = 'deploy service to production after approval check';
      $('agent').value = 'codex';
      $('risk').value = 'high';
      $('scope').value = 'project';
      renderOutput({mode: 'demo', hint: 'Preview the launch-ready deploy task to generate a receipt and then bundle it.'});
    }

    function loadMemoryExample() {
      $('rememberContent').value = 'ZMem should be positioned as local-first memory for AI agents with verifiable transition receipts.';
      $('rememberType').value = 'semantic';
      $('rememberSource').value = 'human';
      $('rememberScope').value = 'project';
      $('rememberLabels').value = 'positioning, launch';
    }

    function loadTopicExample() {
      $('topicQuery').value = 'durable memory source';
      inspectTopic().catch((error) => {
        $('topicSummary').innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
      });
    }

    document.body.addEventListener('click', async (event) => {
      const sessionButton = event.target.closest('button[data-session-action]');
      if (sessionButton) {
        const sessionAction = sessionButton.dataset.sessionAction;
        if (sessionAction === 'copy') {
          if (!lastSessionInstruction) return;
          try {
            if (navigator.clipboard?.writeText) {
              await navigator.clipboard.writeText(lastSessionInstruction);
            } else {
              const scratch = document.createElement('textarea');
              scratch.value = lastSessionInstruction;
              scratch.style.position = 'fixed';
              scratch.style.opacity = '0';
              document.body.appendChild(scratch);
              scratch.select();
              document.execCommand('copy');
              scratch.remove();
            }
            const originalText = sessionButton.textContent;
            sessionButton.textContent = 'Copied';
            setTimeout(() => { sessionButton.textContent = originalText; }, 1200);
          } catch (error) {
            $('sessionInviteResult').insertAdjacentHTML('beforeend', `<p class="helper">${escapeHtml(error.message)}</p>`);
          }
          return;
        }
        const originalText = sessionButton.textContent;
        sessionButton.disabled = true;
        sessionButton.textContent = 'Working...';
        try {
          if (sessionAction === 'invite') {
            await createSessionInvite(sessionButton.dataset.agent || null);
          } else if (sessionAction === 'detach') {
            if (!window.confirm('Detach this connector? Stored memory will remain.')) return;
            const result = await api(`/api/sessions/${sessionButton.dataset.id}/detach`, {
              method: 'POST',
              body: JSON.stringify({reason: 'detached from local console'}),
            });
            lastSessionInstruction = '';
            $('sessionInviteResult').innerHTML = `<div class="empty">Detached ${escapeHtml(result.session_label || result.client_session_id || result.attachment_id)}. Stored memory was not deleted.</div>`;
            await load();
          }
        } catch (error) {
          $('sessionInviteResult').innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
        } finally {
          sessionButton.disabled = false;
          sessionButton.textContent = originalText;
        }
        return;
      }
      const button = event.target.closest('button[data-action]');
      if (!button) return;
      const action = button.dataset.action;
      const id = button.dataset.id;
      const originalText = button.textContent;
      button.disabled = true;
      button.textContent = '…';
      try {
        if (action === 'why') renderOutput(await api(`/api/receipts/${id}`));
        else if (action === 'bundle') renderOutput(await api(`/api/receipts/${id}/bundle`, {method: 'POST', body: '{}'}));
        else await act(action, id);
      } catch (error) {
        renderOutput({ok:false, error:error.message});
      } finally {
        button.disabled = false;
        button.textContent = originalText;
      }
    });

    $('refreshBtn').addEventListener('click', load);
    $('searchBtn').addEventListener('click', search);
    $('topicSearchBtn').addEventListener('click', inspectTopic);
    $('topicExampleBtn').addEventListener('click', loadTopicExample);
    $('topicQuery').addEventListener('keydown', (event) => {
      if (event.key === 'Enter') inspectTopic();
    });
    $('demoTaskBtn').addEventListener('click', loadDemoTask);
    $('rememberExampleBtn').addEventListener('click', loadMemoryExample);
    $('rememberBtn').addEventListener('click', async () => {
      const labels = $('rememberLabels').value.split(',').map((label) => label.trim()).filter(Boolean);
      const result = await api('/api/memories', {
        method: 'POST',
        body: JSON.stringify({
          content: $('rememberContent').value,
          memory_type: $('rememberType').value,
          source_kind: $('rememberSource').value,
          scope: $('rememberScope').value || 'project',
          labels,
        }),
      });
      renderOutput(result);
      $('rememberContent').value = '';
      await load();
    });
    $('snapshotBtn').addEventListener('click', async () => {
      renderOutput(await api('/api/snapshot', {method: 'POST', body: '{}'}));
      await load();
    });
    $('releasePackBtn').addEventListener('click', async () => {
      renderOutput(await api('/api/release/release-pack', {method: 'POST', body: '{}'}));
      await load();
    });
    $('launchProofBtn').addEventListener('click', async () => {
      renderOutput(await api('/api/release/launch-proof', {method: 'POST', body: '{}'}));
      await load();
    });
    $('handoffBtn').addEventListener('click', async () => {
      const result = await api('/api/release/handoff', {method: 'POST', body: '{}'});
      handoffPreviewId = null;
      $('restoreHandoffBtn').disabled = true;
      $('handoffPreview').innerHTML = '<div class="empty">Handoff generated. Preview it before restore.</div>';
      renderOutput(result);
      await load();
    });
    $('previewHandoffBtn').addEventListener('click', async () => {
      const result = await api('/api/release/preview-handoff', {method: 'POST', body: '{}'});
      handoffPreviewId = result.ready_to_restore ? result.preview_id : null;
      $('restoreHandoffBtn').disabled = !handoffPreviewId;
      $('handoffPreview').innerHTML = renderHandoffPreviewSummary(result);
      renderOutput(result);
    });
    $('restoreHandoffBtn').addEventListener('click', async () => {
      if (!handoffPreviewId) return;
      const result = await api('/api/release/restore-handoff', {
        method: 'POST',
        body: JSON.stringify({preview_id: handoffPreviewId}),
      });
      handoffPreviewId = null;
      $('restoreHandoffBtn').disabled = true;
      $('handoffPreview').innerHTML = renderRestoreSummary(result);
      renderOutput(result);
      await load();
    });
    $('verifyLaunchAssetsBtn').addEventListener('click', async () => {
      renderOutput(await api('/api/release/verify-launch-assets', {method: 'POST', body: '{}'}));
      await load();
    });
    $('verifyReturnPacketBtn').addEventListener('click', async () => {
      renderOutput(await api('/api/release/verify-return-packet', {method: 'POST', body: '{}'}));
      await load();
    });
    $('injectBtn').addEventListener('click', async () => {
      const result = await api('/api/inject', {
        method: 'POST',
        body: JSON.stringify({task: $('task').value, agent: $('agent').value, risk: $('risk').value, scope: $('scope').value || null}),
      });
      renderOutput(result);
      await load();
    });
    load().catch((error) => $('dbPath').textContent = error.message);
  </script>
</body>
</html>
"""


class DashboardServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address: tuple[str, int],
        store: MemoryStore,
        *,
        rooms_root: Path | None = None,
        tenant_id: str = "local",
    ):
        self.db_path = store.db_path
        self.policy_path = store.policy_path
        self.rooms_root = rooms_root or (store.db_path.parent / "rooms")
        self.tenant_id = tenant_id
        super().__init__(server_address, DashboardHandler)

    def new_store(self) -> MemoryStore:
        return MemoryStore(self.db_path, policy_path=self.policy_path)


class DashboardHandler(BaseHTTPRequestHandler):
    server: DashboardServer

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        try:
            store = self.server.new_store()
            if parsed.path == "/":
                self._send_html(INDEX_HTML)
                return
            if parsed.path == "/api/state":
                workspace_sources = build_workspace_sources_state(store)
                self._send_json(
                    {
                        "stats": store.stats(),
                        "workspace_profile": workspace_status_for_paths(
                            db_path=store.db_path,
                            policy_path=store.policy_path,
                        ),
                        "workspace_sources": workspace_sources,
                        "onboarding": build_onboarding_state(store),
                        "agent_continuity": build_agent_continuity_state(
                            store,
                            source_report=workspace_sources,
                        ),
                        "room_inventory": build_room_inventory_state(
                            storage_root=self.server.rooms_root,
                            tenant_id=self.server.tenant_id,
                        ),
                        "benchmark": build_benchmark_state(),
                        "release_readiness": build_release_readiness_state(store),
                        "queue": [memory.to_dict() for memory in store.queue()],
                        "memories": [memory.to_dict() for memory in store.list_memories(limit=100)],
                        "receipts": store.list_receipts(limit=25),
                    }
                )
                return
            if parsed.path == "/api/memories":
                params = parse_qs(parsed.query)
                query = first(params, "q")
                status = first(params, "status")
                if query:
                    memories = store.search(query, include_quarantined=True)
                    if status:
                        memories = [memory for memory in memories if memory.status == status]
                else:
                    memories = store.list_memories(status=status or None, limit=100)
                self._send_json({"memories": [memory.to_dict() for memory in memories]})
                return
            if parsed.path.startswith("/api/receipts/"):
                if re_receipt_action(parsed.path):
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "use POST for receipt actions")
                    return
                action_id = parsed.path.rsplit("/", 1)[-1]
                self._send_json(store.why(action_id))
                return
            self._send_error(HTTPStatus.NOT_FOUND, "not found")
        except Exception as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            store = self.server.new_store()
            payload = self._read_json()
            if parsed.path == "/api/memories":
                content = required_str(payload, "content").strip()
                if not content:
                    raise ValueError("memory content is required")
                self._send_json(
                    store.remember(
                        content,
                        memory_type=payload.get("memory_type", "semantic"),
                        scope=payload.get("scope") or "project",
                        source_kind=payload.get("source_kind", "human"),
                        labels=payload.get("labels") or [],
                    ).to_dict()
                )
                return
            if parsed.path == "/api/inject":
                self._send_json(
                    store.inject(
                        required_str(payload, "task"),
                        agent_id=required_str(payload, "agent"),
                        risk=payload.get("risk", "medium"),
                        scope=payload.get("scope"),
                    )
                )
                return
            if parsed.path == "/api/sessions/invitations":
                self._send_json(create_dashboard_session_invitation(store, payload))
                return
            if parsed.path == "/api/snapshot":
                out_dir = Path(payload["out_dir"]) if payload.get("out_dir") else None
                self._send_json(export_snapshot(store.snapshot(), out_dir=out_dir))
                return
            if parsed.path == "/api/release/launch-proof":
                self._send_json(create_dashboard_launch_proof(store))
                return
            if parsed.path == "/api/release/release-pack":
                self._send_json(create_dashboard_release_pack(store))
                return
            if parsed.path == "/api/release/handoff":
                self._send_json(create_dashboard_handoff(store))
                return
            if parsed.path == "/api/release/preview-handoff":
                self._send_json(create_dashboard_handoff_preview(store))
                return
            if parsed.path == "/api/release/restore-handoff":
                self._send_json(
                    create_dashboard_handoff_restore(
                        store,
                        confirmed_preview_id=required_str(payload, "preview_id"),
                    )
                )
                return
            if parsed.path == "/api/release/verify-launch-assets":
                self._send_json(create_dashboard_launch_assets_verify(store))
                return
            if parsed.path == "/api/release/verify-return-packet":
                self._send_json(create_dashboard_return_packet_verify(store))
                return
            session_match = re_session_action(parsed.path)
            if session_match:
                attachment_id, action = session_match
                if action == "detach":
                    self._send_json(
                        create_dashboard_session_detach(
                            store,
                            attachment_id=attachment_id,
                            reason=payload.get("reason"),
                        )
                    )
                    return
            receipt_match = re_receipt_action(parsed.path)
            if receipt_match:
                action_id, action = receipt_match
                if action == "bundle":
                    out_dir = Path(payload["out_dir"]) if payload.get("out_dir") else None
                    self._send_json(export_bundle(store.receipt_bundle(action_id), out_dir=out_dir))
                    return
            match = re_memory_action(parsed.path)
            if match:
                memory_id, action = match
                if action == "promote":
                    self._send_json(store.promote(memory_id).to_dict())
                    return
                if action == "reject":
                    self._send_json(store.reject(memory_id, reason=payload.get("reason")).to_dict())
                    return
                if action == "revoke":
                    self._send_json(store.revoke(memory_id, reason=payload.get("reason")))
                    return
            self._send_error(HTTPStatus.NOT_FOUND, "not found")
        except Exception as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("content-length") or 0)
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("content-type", "text/html; charset=utf-8")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, value: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(value, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status: HTTPStatus, message: str) -> None:
        self._send_json({"ok": False, "error": message}, status=status)


def re_memory_action(path: str) -> tuple[str, str] | None:
    parts = path.strip("/").split("/")
    if len(parts) == 4 and parts[0] == "api" and parts[1] == "memories":
        return parts[2], parts[3]
    return None


def re_receipt_action(path: str) -> tuple[str, str] | None:
    parts = path.strip("/").split("/")
    if len(parts) == 4 and parts[0] == "api" and parts[1] == "receipts":
        return parts[2], parts[3]
    return None


def re_session_action(path: str) -> tuple[str, str] | None:
    parts = path.strip("/").split("/")
    if len(parts) == 4 and parts[0] == "api" and parts[1] == "sessions":
        return parts[2], parts[3]
    return None


def create_dashboard_session_invitation(
    store: MemoryStore,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return create_session_invitation(
        store.conn,
        agent_id=required_str(payload, "agent_id"),
        scope=payload.get("scope") or "project",
        room_id=payload.get("room_id") or None,
        session_label=payload.get("session_label") or None,
    )


def create_dashboard_session_detach(
    store: MemoryStore,
    *,
    attachment_id: str,
    reason: str | None = None,
) -> dict[str, Any]:
    return detach_session_attachment(
        store.conn,
        attachment_id=attachment_id,
        detached_by="operator://dashboard",
        reason=reason,
    )


def first(params: dict[str, list[str]], key: str) -> str | None:
    values = params.get(key) or []
    return values[0] if values else None


def build_onboarding_state(store: MemoryStore) -> dict[str, Any]:
    stats = store.stats()
    root = store.db_path.parent
    policy_path = store.policy_path or default_policy_path()
    setup_checks = [
        {
            "label": "Workspace initialized",
            "ready": store.db_path.exists(),
            "detail": f"SQLite memory store at {store.db_path}",
        },
        {
            "label": "Policy file present",
            "ready": policy_path.exists(),
            "detail": f"Policy gate config at {policy_path}",
        },
        {
            "label": "Agent wiring present",
            "ready": (root / "mcp.json").exists() and (root / "AGENT_PROMPT.md").exists(),
            "detail": "MCP config and agent prompt are ready for Codex-style loops",
        },
        {
            "label": "Provider config present",
            "ready": (root / "providers.json").exists(),
            "detail": f"Optional governance overlay config at {root / 'providers.json'}",
        },
    ]
    commands = [
        "zmem init --with-policy --with-agent-prompt --with-mcp-config --with-provider-config",
        "zmem status --summary-only",
        "zmem doctor",
        "zmem eval",
        "zmem demo",
        "zmem ui",
    ]
    empty = stats["memory_count"] == 0 and stats["receipt_count"] == 0
    return {
        "show": empty,
        "message": "This workspace has no memories or receipts yet. Create the local policy files, run the readiness check, generate a proof run, then use the console to capture the governed-memory story.",
        "checks": setup_checks,
        "commands": commands,
    }


def _compact_dashboard_preview(values: list[Any] | None, *, limit: int = 3) -> str | None:
    items = sorted({str(value).strip() for value in values or [] if str(value).strip()})
    if not items:
        return None
    if len(items) <= limit:
        return ",".join(items)
    return ",".join(items[:limit]) + f",+{len(items) - limit} more"


def build_workspace_sources_state(store: MemoryStore, *, limit: int = 25) -> dict[str, Any]:
    report = workspace_source_report(
        store,
        db_path=store.db_path,
        policy_path=store.policy_path,
        limit=limit,
    )
    connected_agents = []
    for agent in report.get("connected_agents") or []:
        enriched_agent = dict(agent)
        enriched_agent["source_uri_preview"] = _compact_dashboard_preview(agent.get("source_uris"))
        connected_agents.append(enriched_agent)
    report["connected_agents"] = connected_agents
    return report


def build_agent_continuity_state(
    store: MemoryStore,
    *,
    root: Path | None = None,
    config_paths: dict[str, Path] | None = None,
    source_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from .cli import agent_default_config_path, agent_display_name, agent_export_config_path, agent_presets
    from .doctor import inspect_agent_connection
    from .session_connections import list_session_attachments

    root = (root or Path.cwd()).resolve(strict=False)
    zerker_dir = store.db_path.parent
    agents_dir = zerker_dir / "agents"
    handoff_dir = root / ".zerker" / "handoff"
    manual_pack_path = agents_dir / "manual-agent-pack.md"
    source_report = source_report or build_workspace_sources_state(store)
    aliases = {"claude": "claude-code", "claude_code": "claude-code"}
    observed: dict[str, dict[str, Any]] = {}
    for item in source_report.get("connected_agents") or []:
        actor_uri = str(item.get("actor_uri") or "")
        if not actor_uri.startswith("agent://"):
            continue
        agent_id = str(item.get("agent_id") or "").strip()
        if agent_id:
            observed[aliases.get(agent_id, agent_id)] = item
    attachment_report = list_session_attachments(store.conn, limit=200)
    attachments_by_agent: dict[str, list[dict[str, Any]]] = {}
    for attachment in attachment_report["attachments"]:
        agent_id = aliases.get(str(attachment["agent_id"]), str(attachment["agent_id"]))
        attachments_by_agent.setdefault(agent_id, []).append(attachment)

    agents: list[dict[str, Any]] = []
    overrides = config_paths or {}
    for preset in agent_presets():
        config_path = overrides.get(preset) or agent_default_config_path(preset) or agent_export_config_path(preset, cwd=root)
        inspection = inspect_agent_connection(
            preset,
            config_path=config_path,
            db_path=store.db_path,
            policy_path=store.policy_path,
            working_dir=root,
        )
        provenance = observed.pop(preset, None)
        session_attachments = attachments_by_agent.pop(preset, [])
        live_session_count = sum(1 for item in session_attachments if item["presence"] == "live")
        idle_session_count = sum(1 for item in session_attachments if item["presence"] == "idle")
        is_live = live_session_count > 0
        inspection_state = str(inspection.get("state") or "not_connected")
        export_ready = inspection_state == "exported_awaiting_import"
        configured = bool(inspection.get("ok")) and not export_ready
        was_observed = provenance is not None
        if is_live:
            connection_state = "live"
        elif configured and was_observed:
            connection_state = "active"
        elif configured:
            connection_state = "configured"
        elif was_observed:
            connection_state = "observed"
        else:
            connection_state = "export_ready" if export_ready else inspection_state
        configured_db_path = inspection.get("configured_db_path")
        shared_store_match = bool(
            configured_db_path
            and Path(str(configured_db_path)).expanduser().resolve(strict=False)
            == store.db_path.expanduser().resolve(strict=False)
        )
        agents.append(
            {
                "agent_id": preset,
                "label": agent_display_name(preset),
                "path": str(config_path),
                "ready": configured,
                "configured": configured,
                "export_ready": export_ready,
                "observed": was_observed,
                "active": configured and was_observed,
                "live": is_live,
                "live_session_count": live_session_count,
                "idle_session_count": idle_session_count,
                "session_attachments": session_attachments,
                "connection_state": connection_state,
                "mode": "Direct config install" if preset in {"codex", "claude-code"} else "Manual MCP import",
                "details": inspection.get("details"),
                "configured_db_path": configured_db_path,
                "shared_store_match": shared_store_match,
                "memory_count": int((provenance or {}).get("memory_count") or 0),
                "chat_session_ids": list((provenance or {}).get("chat_session_ids") or []),
                "source_uri_preview": (provenance or {}).get("source_uri_preview"),
                "latest_origin_summary": (provenance or {}).get("latest_origin_summary"),
                "latest_proof_lineage": (provenance or {}).get("latest_proof_lineage"),
                "ready_text": "Configured for this shared store; observed writes appear after the agent uses ZMem.",
                "next_step": (
                    f"Import {config_path} into {agent_display_name(preset)}."
                    if export_ready
                    else f"Run zmem setup {preset}."
                ),
                "setup_command": f"zmem setup {preset}",
            }
        )

    for agent_id, provenance in sorted(observed.items()):
        session_attachments = attachments_by_agent.pop(agent_id, [])
        live_session_count = sum(1 for item in session_attachments if item["presence"] == "live")
        idle_session_count = sum(1 for item in session_attachments if item["presence"] == "idle")
        is_live = live_session_count > 0
        agents.append(
            {
                "agent_id": agent_id,
                "label": agent_id,
                "path": None,
                "ready": False,
                "configured": False,
                "export_ready": False,
                "observed": True,
                "active": False,
                "connection_state": "live" if is_live else "observed",
                "live": is_live,
                "live_session_count": live_session_count,
                "idle_session_count": idle_session_count,
                "session_attachments": session_attachments,
                "mode": "Observed through memory provenance",
                "details": "This agent wrote memory here, but no local adapter config is registered for it.",
                "configured_db_path": None,
                "shared_store_match": False,
                "memory_count": int(provenance.get("memory_count") or 0),
                "chat_session_ids": list(provenance.get("chat_session_ids") or []),
                "source_uri_preview": provenance.get("source_uri_preview"),
                "latest_origin_summary": provenance.get("latest_origin_summary"),
                "latest_proof_lineage": provenance.get("latest_proof_lineage"),
                "ready_text": "Observed from provenance.",
                "next_step": "Connect this framework with the generic MCP adapter.",
                "setup_command": "zmem setup generic",
            }
        )

    for agent_id, session_attachments in sorted(attachments_by_agent.items()):
        live_session_count = sum(1 for item in session_attachments if item["presence"] == "live")
        idle_session_count = sum(1 for item in session_attachments if item["presence"] == "idle")
        is_live = live_session_count > 0
        agents.append(
            {
                "agent_id": agent_id,
                "label": agent_id,
                "path": None,
                "ready": False,
                "configured": False,
                "export_ready": False,
                "observed": False,
                "active": False,
                "live": is_live,
                "live_session_count": live_session_count,
                "idle_session_count": idle_session_count,
                "session_attachments": session_attachments,
                "connection_state": "live" if is_live else "idle",
                "mode": "Explicit session attachment",
                "details": "This connector attached with a one-time code; no matching local adapter config was found.",
                "configured_db_path": None,
                "shared_store_match": False,
                "memory_count": 0,
                "chat_session_ids": [],
                "source_uri_preview": None,
                "latest_origin_summary": None,
                "latest_proof_lineage": None,
                "ready_text": "Explicit connector attachment observed.",
                "next_step": "Verify this framework's persistent MCP configuration.",
                "setup_command": "zmem setup generic",
            }
        )

    configured_count = sum(1 for agent in agents if agent["configured"])
    export_ready_count = sum(1 for agent in agents if agent["export_ready"])
    observed_count = sum(1 for agent in agents if agent["observed"])
    active_count = sum(1 for agent in agents if agent["active"])
    live_agent_count = sum(1 for agent in agents if agent["live"])
    live_session_count = sum(agent["live_session_count"] for agent in agents)
    return {
        "schema": "zerker.agent_memory_network.v1",
        "db_path": str(store.db_path),
        "policy_path": str(store.policy_path) if store.policy_path is not None else None,
        "mcp_ready": (zerker_dir / "mcp.json").exists(),
        "manual_pack_ready": manual_pack_path.exists(),
        "manual_pack_path": str(manual_pack_path),
        "handoff_ready": (handoff_dir / "handoff.json").exists(),
        "handoff_path": str(handoff_dir),
        "configured_count": configured_count,
        "export_ready_count": export_ready_count,
        "observed_count": observed_count,
        "active_count": active_count,
        "live_agent_count": live_agent_count,
        "live_session_count": live_session_count,
        "shared_memory_ready": configured_count >= 2,
        "agents": agents,
        "commands": [
            "zmem setup codex claude-code hermes",
            "zmem session invite --agent codex --label current-chat --summary-only",
            "zmem session connections --summary-only",
            "zmem agent pack --summary-only",
            "zmem status --summary-only",
            "zmem agent mcp-smoke --agent codex",
            "zmem handoff --summary-only",
            "zmem --db .zerker/imported.sqlite restore --handoff-dir .zerker/handoff --dry-run",
        ],
    }


def build_room_inventory_state(*, storage_root: Path, tenant_id: str) -> dict[str, Any]:
    from .rooms import discover_room_stores

    room_items: list[dict[str, Any]] = []
    observed_agents: set[str] = set()
    for descriptor in discover_room_stores(storage_root, tenant_id=tenant_id):
        db_path = Path(descriptor["db_path"])
        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)
            connection.row_factory = sqlite3.Row
            memory_rows = connection.execute(
                "SELECT id, status, scope, labels_json, updated_at FROM memories ORDER BY updated_at DESC, id"
            ).fetchall()
            latest_receipt = connection.execute(
                "SELECT receipt_id, receipt_hash, merkle_root, created_at FROM memory_write_receipts ORDER BY created_at DESC, receipt_id DESC LIMIT 1"
            ).fetchone()
            indexed_count = 0
            if connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'memory_embeddings'"
            ).fetchone():
                indexed_count = int(
                    connection.execute(
                        "SELECT COUNT(DISTINCT e.memory_id) FROM memory_embeddings e JOIN memories m ON m.id = e.memory_id AND m.content_hash = e.content_hash WHERE m.status IN ('active', 'quarantined', 'proposed')"
                    ).fetchone()[0]
                )
        except sqlite3.Error:
            room_items.append(
                {
                    **descriptor,
                    "inventory_state": "unreadable",
                    "memory_count": 0,
                    "status_counts": {},
                    "shared_memory_count": 0,
                    "member_private_memory_count": 0,
                    "observed_contributor_ids": [],
                    "latest_activity": None,
                    "latest_receipt_id": None,
                    "latest_receipt_hash": None,
                    "latest_merkle_root": None,
                    "semantic_index": {
                        "indexed_memory_count": 0,
                        "eligible_memory_count": 0,
                        "coverage": 0.0,
                    },
                }
            )
            continue
        finally:
            if connection is not None:
                connection.close()

        status_counts: dict[str, int] = {}
        contributors: set[str] = set()
        shared_count = 0
        private_count = 0
        latest_activity = None
        for row in memory_rows:
            status = str(row["status"])
            status_counts[status] = status_counts.get(status, 0) + 1
            scope = str(row["scope"])
            if scope == "global":
                shared_count += 1
            elif scope.startswith("member:"):
                private_count += 1
            try:
                labels = json.loads(row["labels_json"])
            except (TypeError, json.JSONDecodeError):
                labels = []
            for label in labels if isinstance(labels, list) else []:
                if isinstance(label, str) and label.startswith("contributor:"):
                    agent_id = label.removeprefix("contributor:")
                    if agent_id:
                        contributors.add(agent_id)
                        observed_agents.add(agent_id)
            if latest_activity is None and row["updated_at"]:
                latest_activity = str(row["updated_at"])
        eligible_count = sum(status_counts.get(status, 0) for status in ("active", "quarantined", "proposed"))
        room_items.append(
            {
                **descriptor,
                "inventory_state": "ready",
                "memory_count": len(memory_rows),
                "status_counts": status_counts,
                "shared_memory_count": shared_count,
                "member_private_memory_count": private_count,
                "observed_contributor_ids": sorted(contributors),
                "latest_activity": latest_activity,
                "latest_receipt_id": latest_receipt["receipt_id"] if latest_receipt is not None else None,
                "latest_receipt_hash": latest_receipt["receipt_hash"] if latest_receipt is not None else None,
                "latest_merkle_root": latest_receipt["merkle_root"] if latest_receipt is not None else None,
                "semantic_index": {
                    "indexed_memory_count": indexed_count,
                    "eligible_memory_count": eligible_count,
                    "coverage": round(indexed_count / eligible_count, 6) if eligible_count else 1.0,
                },
            }
        )
    room_items.sort(key=lambda item: (str(item.get("latest_activity") or ""), str(item["room_id"])), reverse=True)
    return {
        "schema": "zerker.room_inventory.v1",
        "tenant_id": tenant_id,
        "storage_root": str(Path(storage_root).expanduser().resolve(strict=False)),
        "room_count": len(room_items),
        "memory_count": sum(int(room["memory_count"]) for room in room_items),
        "shared_memory_count": sum(int(room["shared_memory_count"]) for room in room_items),
        "member_private_memory_count": sum(int(room["member_private_memory_count"]) for room in room_items),
        "unreadable_room_count": sum(1 for room in room_items if room["inventory_state"] == "unreadable"),
        "observed_contributor_ids": sorted(observed_agents),
        "rooms": room_items,
        "membership_authority": "gateway",
        "membership_note": "Contributors are derived from memory provenance; Gateway remains authoritative for Room membership.",
    }


def build_benchmark_state(root: Path | None = None) -> dict[str, Any]:
    root = root or Path.cwd()
    bench_root = root / ".zerker" / "bench"
    preferred = bench_root / "standard-synthetic-20260606-readiness" / "benchmark-matrix.json"
    candidates = []
    if preferred.exists():
        candidates.append(preferred)
    if bench_root.exists():
        candidates.extend(sorted(bench_root.glob("*/benchmark-matrix.json"), key=lambda path: path.stat().st_mtime, reverse=True))
    seen = set()
    matrix_paths = []
    for path in candidates:
        if path in seen:
            continue
        seen.add(path)
        matrix_paths.append(path)
    if not matrix_paths:
        return {
            "ok": False,
            "message": "No benchmark matrix found. Run zmem bench matrix synthetic --out .zerker/bench --seed 0 --run-id standard-synthetic-20260606-readiness.",
        }

    matrix_path = matrix_paths[0]
    try:
        matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "message": f"Benchmark matrix could not be read: {exc}"}

    mode_runs = matrix.get("mode_runs") or []
    modes = []
    best_mode = None
    best_accuracy = -1.0
    for run in mode_runs:
        summary = run.get("summary") or {}
        accuracy = float(summary.get("accuracy") or 0)
        if accuracy > best_accuracy:
            best_accuracy = accuracy
            best_mode = run.get("retrieval_mode") or run.get("run_id")
        modes.append(
            {
                "run_id": run.get("run_id"),
                "retrieval_mode": run.get("retrieval_mode"),
                "accuracy": accuracy,
                "pass": f"{summary.get('passed', 0)}/{summary.get('question_count', 0)}",
                "p95_retrieval_latency_ms": summary.get("p95_retrieval_latency_ms", 0),
                "total_tokens": summary.get("total_tokens", 0),
                "verification_status": summary.get("proof_verification_status") or "unknown",
            }
        )

    dashboard_path = matrix_path.parent / "benchmark-dashboard.html"
    return {
        "ok": True,
        "claim_status": "local synthetic proof" if matrix.get("benchmark") == "synthetic" else "local scaffold proof",
        "benchmark": matrix.get("benchmark"),
        "dataset": matrix.get("dataset"),
        "run_id": matrix.get("run_id"),
        "matrix_path": str(matrix_path),
        "dashboard_path": str(dashboard_path),
        "dashboard_ready": dashboard_path.exists(),
        "public_url": "http://127.0.0.1:8766/benchmarks.html",
        "matrix_hash": matrix.get("matrix_hash"),
        "comparison_hash": matrix.get("comparison_hash"),
        "verification_status": ((matrix.get("proof") or {}).get("verification_status") or "unknown"),
        "best_mode": best_mode,
        "best_accuracy": best_accuracy if best_accuracy >= 0 else 0,
        "modes": modes,
    }


def build_release_readiness_state(store: MemoryStore) -> dict[str, Any]:
    from .cli import (
        CLEAN_SHELL_OPERATOR_PROMPT_FILENAME,
        CLEAN_SHELL_PUBLIC_VERIFY_FILENAME,
        LAUNCH_ASSET_HANDOFF_FILENAME,
        PUBLIC_VERIFY_HANDOFF_FILENAME,
        PUBLIC_VERIFY_RESULT_FILENAME,
        PUBLIC_VERIFY_SUMMARY_FILENAME,
        RECEIVE_VERIFY_HANDOFF_FILENAME,
        RETURN_PACKET_FINALIZE_FILENAME,
        default_handoff_dir,
        default_launch_proof_dir,
        launch_asset_outputs_dir,
        launch_asset_status,
        operator_packet_status,
        public_verify_status,
        read_launch_proof_manifest,
        return_packet_status,
    )

    root = Path.cwd()
    launch_proof_dir = default_launch_proof_dir(cwd=root)
    handoff_dir = default_handoff_dir(cwd=root)
    repo_surface_present = any(
        (root / relative_path).exists()
        for relative_path in ("README.md", "install.sh", "scripts/release_smoke.py", "docs/PRODUCT_STATUS.md")
    )
    if not repo_surface_present:
        return {
            "repo_surface_present": False,
            "db_path": str(store.db_path),
            "launch_proof_dir": str(launch_proof_dir),
            "handoff_dir": str(handoff_dir),
            "capture_checklist_path": str(launch_proof_dir / "CAPTURE_CHECKLIST.md"),
            "public_verify_script_path": str(launch_proof_dir / "PUBLIC_VERIFY_COMMANDS.sh"),
            "public_verify_result_path": str(launch_proof_dir / PUBLIC_VERIFY_RESULT_FILENAME),
            "return_packet_finalize_script_path": str(launch_proof_dir / RETURN_PACKET_FINALIZE_FILENAME),
            "receive_verify_handoff_path": str(launch_proof_dir / RECEIVE_VERIFY_HANDOFF_FILENAME),
            "launch_assets_outputs_dir_path": str(launch_asset_outputs_dir(launch_proof_dir)),
        }
    public_verify = public_verify_status(root)
    operator_packet = operator_packet_status(root)
    asset_status = launch_asset_status(root)
    return_packet = return_packet_status(root)
    manifest = read_launch_proof_manifest(root)
    manifest_assets = manifest.get("launch_assets", []) if isinstance(manifest, dict) else []
    launch_proof_ready = (launch_proof_dir / "index.html").exists() and (launch_proof_dir / "launch-proof.json").exists()
    handoff_ready = (handoff_dir / "handoff.json").exists()
    blocker_names = []
    if not launch_proof_ready:
        blocker_names.append("launch_proof_artifacts")
    if not handoff_ready:
        blocker_names.append("handoff_artifacts")
    if not public_verify["ready"]:
        blocker_names.append("public_verify_evidence")
    if not asset_status["ready"]:
        blocker_names.append("launch_assets")
    strict_publish_ready = not blocker_names
    readiness = {
        "repo_surface_present": True,
        "launch_proof_ready": launch_proof_ready,
        "handoff_ready": handoff_ready,
        "launch_proof_dir": str(launch_proof_dir),
        "handoff_dir": str(handoff_dir),
        "capture_checklist_path": str(launch_proof_dir / "CAPTURE_CHECKLIST.md"),
        "launch_asset_handoff_path": str(launch_proof_dir / LAUNCH_ASSET_HANDOFF_FILENAME),
        "public_verify_handoff_path": str(launch_proof_dir / PUBLIC_VERIFY_HANDOFF_FILENAME),
        "receive_verify_handoff_path": str(launch_proof_dir / RECEIVE_VERIFY_HANDOFF_FILENAME),
        "public_verify_checklist_path": str(launch_proof_dir / "PUBLIC_VERIFY_CHECKLIST.md"),
        "public_verify_script_path": str(launch_proof_dir / "PUBLIC_VERIFY_COMMANDS.sh"),
        "operator_packet_ready": bool(operator_packet["ready"]),
        "operator_packet_details": str(operator_packet["details"]),
        "operator_packet_archive_path": str(operator_packet["archive_path"]),
        "operator_packet_missing_paths": list(operator_packet.get("missing_paths", [])),
        "public_verify_ready": bool(public_verify["ready"]),
        "public_verify_details": str(public_verify["details"]),
        "public_verify_logs_dir_path": str(public_verify["logs_dir_path"]),
        "public_verify_result_path": str(launch_proof_dir / PUBLIC_VERIFY_RESULT_FILENAME),
        "public_verify_summary_path": str(launch_proof_dir / PUBLIC_VERIFY_SUMMARY_FILENAME),
        "public_verify_runbook_path": str(launch_proof_dir / CLEAN_SHELL_PUBLIC_VERIFY_FILENAME),
        "public_verify_operator_prompt_path": str(launch_proof_dir / CLEAN_SHELL_OPERATOR_PROMPT_FILENAME),
        "return_packet_finalize_script_path": str(launch_proof_dir / RETURN_PACKET_FINALIZE_FILENAME),
        "public_verify_expected_count": int(public_verify["expected_count"]),
        "public_verify_present_count": int(public_verify["present_count"]),
        "public_verify_missing_paths": list(public_verify.get("missing_paths", [])),
        "launch_assets_ready": bool(asset_status["ready"]),
        "launch_assets_details": str(asset_status["details"]),
        "launch_assets_outputs_dir_path": str(asset_status["outputs_dir_path"]),
        "launch_assets_expected_count": int(asset_status["expected_count"]),
        "launch_assets_present_count": int(asset_status["present_count"]),
        "launch_assets_missing_paths": list(asset_status.get("missing_paths", [])),
        "expected_launch_assets": [
        asset
        for asset in manifest_assets
        if isinstance(asset, dict) and asset.get("id") and asset.get("deliverable") and asset.get("output_path")
        ],
        "return_packet_ready": bool(return_packet["ready"]),
        "return_packet_details": str(return_packet["details"]),
        "return_packet_archive_path": str(return_packet["archive_path"]),
        "return_packet_missing_paths": list(return_packet.get("missing_paths", [])),
        "local_alpha_ready": launch_proof_ready and handoff_ready,
        "local_alpha_blockers": [],
        "local_alpha_warnings": [],
        "strict_publish_ready": strict_publish_ready,
        "strict_publish_blockers": [{"name": name} for name in blocker_names],
        "strict_publish_warnings": [],
        "strict_publish_next_steps": [
            "zmem release-pack --summary-only",
            "zmem verify-public-verify --summary-only",
            "zmem verify-launch-assets --summary-only",
            "zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only",
        ],
    }
    readiness["db_path"] = str(store.db_path)
    return readiness


def create_dashboard_launch_proof(store: MemoryStore) -> dict[str, Any]:
    from .cli import run_launch_proof

    providers_path = store.db_path.parent / "providers.json"
    return run_launch_proof(
        policy_path=store.policy_path or default_policy_path(),
        providers_path=providers_path,
        out_dir=None,
        agent_id="codex",
        scope="project",
        task="deploy service to production after approval check",
        bt_trace_path=Path("examples") / "bt_trace.jsonl",
    )


def create_dashboard_release_pack(store: MemoryStore) -> dict[str, Any]:
    from .cli import run_release_pack

    providers_path = store.db_path.parent / "providers.json"
    return run_release_pack(
        store,
        policy_path=store.policy_path or default_policy_path(),
        providers_path=providers_path,
        agent_id="codex",
        scope="project",
        task="deploy service to production after approval check",
        bt_trace_path=Path("examples") / "bt_trace.jsonl",
        action_id=None,
        allow_placeholders=True,
    )


def create_dashboard_handoff(store: MemoryStore) -> dict[str, Any]:
    from .cli import create_handoff_package

    providers_path = store.db_path.parent / "providers.json"
    return create_handoff_package(
        store,
        providers_path=providers_path,
        out_dir=None,
        action_id=None,
    )


def _next_dashboard_import_db(store: MemoryStore) -> Path:
    target_dir = store.db_path.parent / "imports"
    target_db = target_dir / "imported.sqlite"
    suffix = 2
    while target_db.exists():
        target_db = target_dir / f"imported-{suffix}.sqlite"
        suffix += 1
    return target_db


def create_dashboard_handoff_preview(store: MemoryStore) -> dict[str, Any]:
    from .cli import default_handoff_dir, preview_handoff_package

    target_db = _next_dashboard_import_db(store)
    result = preview_handoff_package(
        store,
        handoff_dir=default_handoff_dir(cwd=Path.cwd()),
        target_db_path=target_db,
        assume_empty_target=True,
    )
    result["dashboard_target_is_new_copy"] = True
    return result


def create_dashboard_handoff_restore(store: MemoryStore, *, confirmed_preview_id: str | None = None) -> dict[str, Any]:
    from .cli import default_handoff_dir, restore_handoff_package

    target_db = _next_dashboard_import_db(store)
    target_dir = target_db.parent
    target_dir.mkdir(parents=True, exist_ok=True)
    target_store = MemoryStore(target_db, policy_path=store.policy_path)
    return restore_handoff_package(
        target_store,
        handoff_dir=default_handoff_dir(cwd=Path.cwd()),
        confirmed_preview_id=confirmed_preview_id,
    )


def create_dashboard_return_packet_verify(store: MemoryStore) -> dict[str, Any]:
    from .cli import default_launch_proof_dir, verify_return_packet_archive

    archive_path = default_launch_proof_dir(cwd=Path.cwd()) / "public-verify-return-packet.tar.gz"
    return verify_return_packet_archive(archive_path)


def create_dashboard_launch_assets_verify(store: MemoryStore) -> dict[str, Any]:
    from .cli import verify_launch_assets

    return verify_launch_assets(Path.cwd())


def required_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"missing required string field: {key}")
    return value


def serve(
    store: MemoryStore,
    *,
    host: str,
    port: int,
    rooms_root: Path | None = None,
    tenant_id: str = "local",
) -> None:
    store.init()
    server = DashboardServer(
        (host, port),
        store,
        rooms_root=rooms_root,
        tenant_id=tenant_id,
    )
    print(f"Zerker Memory Console running at http://{host}:{port}")
    server.serve_forever()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Zerker Memory local review console")
    parser.add_argument("--db", type=Path, default=default_db_path(), help="SQLite database path")
    parser.add_argument("--policy", type=Path, default=default_policy_path(), help="Policy config JSON path")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--rooms-root", type=Path, help="Room-store root to inspect; defaults beside --db")
    parser.add_argument("--tenant-id", default="local", help="Tenant identity for the local Rooms inventory")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    serve(
        MemoryStore(args.db, policy_path=args.policy),
        host=args.host,
        port=args.port,
        rooms_root=args.rooms_root,
        tenant_id=args.tenant_id,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
