"""Workflow-first built-in web GUI for tb2 MCP control."""

from __future__ import annotations

from .audit import AUDIT_EVENT_CATALOG
from .osutils import default_backend_name

GUI_HTML_TEMPLATE = r"""
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Terminal Bridge</title>
    <style>
      :root {
        --bg: #f6f1e7;
        --panel: rgba(255, 250, 241, 0.92);
        --panel-strong: #fffdf8;
        --line: #d9ccb8;
        --ink: #17212f;
        --muted: #5d6570;
        --accent: #2f4b5c;
        --accent-strong: #223744;
        --accent-soft: #e4eaee;
        --info: #3f5668;
        --success: #4b5f53;
        --accent-alt: #746456;
        --danger: #6c4d48;
        --shadow: 0 14px 30px rgba(34, 29, 24, 0.08);
        --shadow-soft: 0 6px 14px rgba(34, 29, 24, 0.05);
        --shadow-press: 0 2px 6px rgba(34, 29, 24, 0.06);
        --radius: 12px;
        --control-height: 38px;
        --control-padding-x: 11px;
        --shell-width: 1380px;
        --shell-gutter: 28px;
        --layout-left: minmax(320px, 380px);
        --layout-right: minmax(0, 1fr);
      }

      * {
        box-sizing: border-box;
      }

      body {
        margin: 0;
        color: var(--ink);
        font-family: "Noto Sans TC", "PingFang TC", "Microsoft JhengHei", "Heiti TC", "Segoe UI", sans-serif;
        font-size: 14px;
        line-height: 1.45;
        background:
          radial-gradient(circle at top left, rgba(23, 33, 47, 0.08), transparent 28%),
          radial-gradient(circle at top right, rgba(116, 100, 86, 0.10), transparent 30%),
          linear-gradient(180deg, #f1eadf 0%, #e4d7c5 100%);
      }

      body[data-layout="wide"] {
        --shell-width: 1520px;
        --shell-gutter: 22px;
        --layout-left: minmax(360px, 460px);
        --layout-right: minmax(0, 1.2fr);
      }

      body[data-layout="stacked"] {
        --shell-width: 1480px;
        --shell-gutter: 20px;
      }

      body[data-home="preset-only"] {
        --shell-width: 920px;
      }

      body[data-scene="radar"] {
        --bg: #f6ecdd;
        --panel: rgba(255, 247, 236, 0.94);
        --panel-strong: #fffaf0;
        --line: #d7b98f;
        --accent: #92552f;
        --accent-strong: #6d3e21;
        --accent-soft: #f1dcc4;
        --accent-alt: #8f6e49;
        --danger: #8c4434;
      }

      body[data-scene="quiet"] {
        --bg: #eef2ef;
        --panel: rgba(247, 251, 248, 0.95);
        --panel-strong: #fbfdfb;
        --line: #bfd0c7;
        --accent: #47625a;
        --accent-strong: #324740;
        --accent-soft: #dbe8e1;
        --accent-alt: #6c7e75;
        --danger: #7d5c55;
      }

      body[data-scene="mission"] {
        --bg: #e9ebf1;
        --panel: rgba(244, 247, 255, 0.94);
        --panel-strong: #f9fbff;
        --line: #bec8df;
        --accent: #38507b;
        --accent-strong: #263a5b;
        --accent-soft: #d8e2f6;
        --accent-alt: #66779e;
        --danger: #7e4f58;
      }

      body::before {
        content: "";
        position: fixed;
        inset: 0;
        pointer-events: none;
        background-image: linear-gradient(rgba(217, 204, 184, 0.18) 1px, transparent 1px),
          linear-gradient(90deg, rgba(217, 204, 184, 0.18) 1px, transparent 1px);
        background-size: 24px 24px;
        mask-image: linear-gradient(180deg, rgba(0, 0, 0, 0.25), transparent 85%);
      }

      main {
        position: relative;
        width: min(var(--shell-width), calc(100vw - var(--shell-gutter)));
        margin: 24px auto 48px;
        display: grid;
        gap: 14px;
      }

      body[data-home="preset-only"] main {
        margin-top: 56px;
      }

      body[data-home="preset-only"] .hero {
        padding: 18px;
      }

      body[data-home="preset-only"] .hero-header,
      body[data-home="preset-only"] .layout,
      body[data-home="preset-only"] .layout-secondary {
        display: none;
      }

      .hero,
      .card {
        position: relative;
        overflow: hidden;
        border: 1px solid var(--line);
        border-radius: var(--radius);
        background: var(--panel);
        box-shadow: var(--shadow);
        backdrop-filter: blur(12px);
        outline: 1px solid rgba(255, 255, 255, 0.45);
        outline-offset: -1px;
      }

      .hero {
        padding: 22px;
        box-shadow: var(--shadow), inset 0 1px 0 rgba(255, 255, 255, 0.42);
      }

      .card {
        --card-accent: var(--accent);
        --card-soft: rgba(255, 255, 255, 0.72);
        box-shadow: var(--shadow-soft), inset 0 1px 0 rgba(255, 255, 255, 0.38);
      }

      .hero::after,
      .card::after {
        content: "";
        position: absolute;
        inset: auto -30% -65% auto;
        width: 220px;
        height: 220px;
        border-radius: 999px;
        background: radial-gradient(circle, rgba(23, 33, 47, 0.08), transparent 72%);
        pointer-events: none;
      }

      .card::before {
        content: "";
        position: absolute;
        inset: 0 auto 0 0;
        width: 4px;
        background: var(--card-accent);
        pointer-events: none;
      }

      .eyebrow {
        margin: 0 0 8px;
        color: var(--accent);
        font-size: 0.74rem;
        font-weight: 600;
        letter-spacing: 0.1em;
        text-transform: uppercase;
      }

      h1,
      h2,
      h3,
      p {
        margin: 0;
      }

      h1 {
        font-size: clamp(1.8rem, 3.4vw, 2.45rem);
        line-height: 1;
        letter-spacing: -0.04em;
        font-weight: 600;
        max-width: 12ch;
      }

      h2 {
        font-size: 1.02rem;
        letter-spacing: 0.01em;
        font-weight: 600;
      }

      .hero-copy {
        display: grid;
        gap: 10px;
        max-width: 72ch;
      }

      .hero-copy p {
        color: var(--muted);
        font-size: 0.9rem;
        line-height: 1.52;
      }

      .hero-header {
        display: flex;
        justify-content: space-between;
        gap: 16px;
        align-items: flex-start;
      }

      .hero-controls {
        min-width: 200px;
        display: grid;
        gap: 12px;
        justify-items: end;
      }

      .control-switch {
        display: grid;
        gap: 6px;
        justify-items: end;
      }

      .control-actions {
        display: flex;
        gap: 6px;
        flex-wrap: wrap;
        justify-content: flex-end;
      }

      .control-label {
        color: var(--muted);
        font-size: 0.72rem;
        font-weight: 500;
        letter-spacing: 0.08em;
        text-transform: uppercase;
      }

      .meta,
      .actions,
      .checks,
      .badge-row,
      .toolbar {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        align-items: center;
      }

      .actions {
        align-items: stretch;
      }

      .actions > button {
        min-width: 136px;
      }

      .meta {
        margin-top: 12px;
      }

      .badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 5px 11px;
        border-radius: 10px;
        border: 1px solid var(--line);
        background: rgba(255, 255, 255, 0.7);
        color: var(--muted);
        font-size: 0.76rem;
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.42);
      }

      .badge strong {
        color: var(--ink);
        font-weight: 600;
      }

      .preset-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 9px;
        margin-top: 14px;
      }

      .preset {
        appearance: none;
        position: relative;
        width: 100%;
        text-align: left;
        min-height: 84px;
        padding: 14px;
        border-radius: 10px;
        border: 1px solid var(--line);
        background: rgba(255, 255, 255, 0.9);
        color: var(--ink);
        cursor: pointer;
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.5);
        transition: transform 160ms ease, border-color 160ms ease, background 160ms ease, box-shadow 160ms ease;
      }

      .preset::before {
        content: "";
        position: absolute;
        inset: 0 0 auto 0;
        height: 3px;
        background: rgba(47, 75, 92, 0.22);
      }

      .preset:hover {
        transform: translateY(-1px);
        box-shadow: var(--shadow-soft), inset 0 1px 0 rgba(255, 255, 255, 0.56);
      }

      .preset.active {
        border-color: var(--accent);
        background: rgba(47, 75, 92, 0.08);
        box-shadow: 0 0 0 1px rgba(47, 75, 92, 0.1), var(--shadow-soft), inset 0 1px 0 rgba(255, 255, 255, 0.42);
      }

      .preset b {
        display: block;
        margin-bottom: 5px;
        font-size: 0.86rem;
        letter-spacing: 0.02em;
        font-weight: 600;
        line-height: 1.25;
      }

      .preset span {
        color: var(--muted);
        font-size: 0.76rem;
        line-height: 1.42;
      }

      .layout {
        display: grid;
        grid-template-columns: var(--layout-left) var(--layout-right);
        gap: 16px;
        align-items: start;
      }

      .layout-secondary {
        display: grid;
        gap: 12px;
      }

      body[data-layout="stacked"] .layout {
        grid-template-columns: 1fr;
      }

      .stack {
        display: grid;
        gap: 14px;
      }

      .card {
        padding: 16px;
      }

      .card-head {
        display: grid;
        gap: 6px;
        margin-bottom: 12px;
        padding-bottom: 10px;
        border-bottom: 1px solid rgba(217, 204, 184, 0.75);
      }

      .card-head p {
        color: var(--muted);
        font-size: 0.82rem;
        line-height: 1.45;
        max-width: 66ch;
      }

      .card-head p:empty,
      .disclosure-copy:empty {
        display: none;
      }

      .card-kicker {
        color: var(--muted);
        font-size: 0.68rem;
        font-weight: 500;
        letter-spacing: 0.08em;
        text-transform: uppercase;
      }

      .card--current {
        box-shadow: 0 0 0 1px rgba(47, 75, 92, 0.12), var(--shadow-soft), inset 0 1px 0 rgba(255, 255, 255, 0.4);
      }

      .stage-note {
        margin: 0 0 12px;
        padding: 9px 10px;
        border: 1px dashed rgba(217, 204, 184, 0.9);
        border-radius: 9px;
        color: var(--muted);
        font-size: 0.76rem;
        line-height: 1.4;
        background: rgba(255, 255, 255, 0.42);
      }

      .disclosure {
        display: grid;
        gap: 0;
        margin-top: 0;
        border-top: 0;
        padding-top: 0;
      }

      .disclosure > summary {
        list-style: none;
      }

      .disclosure > summary::-webkit-details-marker {
        display: none;
      }

      .disclosure-summary {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        cursor: pointer;
        padding: 0;
        color: var(--ink);
        font-size: inherit;
        font-weight: inherit;
        letter-spacing: 0;
        text-transform: none;
      }

      .summary-stack {
        display: grid;
        gap: 4px;
      }

      .disclosure-meta {
        flex: 0 0 auto;
        display: inline-flex;
        align-items: center;
        min-height: 28px;
        padding: 4px 9px;
        border: 1px solid var(--line);
        border-radius: 8px;
        color: var(--muted);
        font-size: 0.72rem;
        background: rgba(255, 255, 255, 0.78);
      }

      .disclosure-body {
        display: grid;
        gap: 12px;
        padding-top: 12px;
      }

      .disclosure-copy {
        color: var(--muted);
        font-size: 0.8rem;
        line-height: 1.45;
      }

      .status-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 8px;
      }

      .stat {
        border: 1px solid var(--line);
        border-radius: 10px;
        background: var(--panel-strong);
        min-height: 74px;
        padding: 11px 12px;
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.72), inset 0 0 0 1px rgba(255, 255, 255, 0.24);
      }

      .stat b {
        display: block;
        margin-bottom: 5px;
        color: var(--muted);
        font-size: 0.68rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
      }

      .stat span {
        font-size: 0.84rem;
        font-weight: 500;
      }

      .card--live .stat:nth-child(1) {
        border-color: rgba(47, 75, 92, 0.18);
        background: rgba(234, 238, 241, 0.92);
      }

      .card--live .stat:nth-child(2) {
        border-color: rgba(63, 86, 104, 0.16);
        background: rgba(238, 241, 243, 0.92);
      }

      .card--live .stat:nth-child(3) {
        border-color: rgba(116, 100, 86, 0.16);
        background: rgba(243, 239, 236, 0.94);
      }

      .card--live .stat:nth-child(4) {
        border-color: rgba(75, 95, 83, 0.16);
        background: rgba(239, 242, 240, 0.94);
      }

      .row {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 10px;
        align-items: start;
      }

      .row.one {
        grid-template-columns: 1fr;
      }

      label {
        display: block;
        margin-bottom: 5px;
        color: var(--muted);
        font-size: 0.72rem;
        font-weight: 500;
        letter-spacing: 0.05em;
        line-height: 1.25;
        text-transform: uppercase;
      }

      input,
      select,
      textarea,
      pre {
        width: 100%;
        padding: 9px var(--control-padding-x);
        border: 1px solid var(--line);
        border-radius: 9px;
        background: rgba(255, 255, 255, 0.88);
        color: var(--ink);
        font: inherit;
        font-size: 0.86rem;
        line-height: 1.3;
        box-shadow: inset 0 1px 1px rgba(34, 29, 24, 0.02), inset 0 0 0 1px rgba(255, 255, 255, 0.18);
      }

      input,
      select {
        min-height: var(--control-height);
      }

      textarea,
      pre {
        min-height: 120px;
        font-family: "IBM Plex Mono", "Consolas", monospace;
        font-size: 0.76rem;
        line-height: 1.42;
      }

      textarea {
        resize: vertical;
      }

      select[size] {
        min-height: 208px;
        background: rgba(250, 245, 237, 0.96);
      }

      textarea[readonly],
      pre {
        border-color: #233243;
        background: #17212f;
        color: #d8e4f0;
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04), inset 0 0 0 1px rgba(255, 255, 255, 0.02);
      }

      pre {
        margin: 0;
        white-space: pre-wrap;
        overflow: auto;
        max-height: 320px;
      }

      #stream-box,
      #status-box,
      #log-box,
      #capture-a-box,
      #capture-b-box {
        border-left: 4px solid var(--card-accent);
      }

      button {
        appearance: none;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 6px;
        border: 1px solid transparent;
        border-radius: 9px;
        min-height: var(--control-height);
        padding: 8px var(--control-padding-x);
        background: var(--accent);
        color: #f7fffd;
        font: inherit;
        font-weight: 500;
        font-size: 0.8rem;
        letter-spacing: 0.01em;
        line-height: 1.2;
        text-align: center;
        vertical-align: middle;
        cursor: pointer;
        box-shadow: var(--shadow-soft), inset 0 1px 0 rgba(255, 255, 255, 0.12);
        transition: transform 140ms ease, box-shadow 140ms ease, border-color 140ms ease, background 140ms ease;
      }

      button:hover {
        transform: translateY(-1px);
        box-shadow: 0 10px 18px rgba(23, 33, 47, 0.09), inset 0 1px 0 rgba(255, 255, 255, 0.14);
      }

      button:active {
        transform: translateY(0);
        box-shadow: var(--shadow-press), inset 0 1px 1px rgba(0, 0, 0, 0.08);
      }

      button.alt {
        background: var(--info);
      }

      button.ok {
        background: var(--success);
      }

      button.warn {
        background: var(--danger);
      }

      button.ghost {
        background: rgba(255, 255, 255, 0.88);
        color: var(--ink);
        border: 1px solid var(--line);
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.5);
      }

      .control-button {
        min-width: 54px;
        min-height: 32px;
        padding: 6px 10px;
        border-radius: 8px;
        font-size: 0.73rem;
        line-height: 1.1;
        box-shadow: none;
      }

      .control-button.active {
        background: var(--ink);
        color: #fffdf8;
        border-color: var(--ink);
      }

      .checks {
        color: var(--muted);
        font-size: 0.8rem;
        margin: 10px 0 2px;
      }

      .checks label {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        margin: 0;
      }

      .checks input {
        width: auto;
        margin: 0;
      }

      .hidden {
        display: none;
      }

      details {
        margin-top: 12px;
        border-top: 1px dashed var(--line);
        padding-top: 12px;
      }

      summary {
        cursor: pointer;
        color: var(--accent);
        font-weight: 600;
        font-size: 0.78rem;
        letter-spacing: 0.04em;
        text-transform: uppercase;
      }

      .queue {
        display: grid;
        gap: 10px;
      }

      .note {
        padding: 10px 12px;
        border-radius: 10px;
        background: rgba(244, 240, 236, 0.96);
        border: 1px solid #d8ccb9;
        border-left: 4px solid var(--accent-alt);
        color: #5d5146;
        font-size: 0.78rem;
        line-height: 1.45;
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.42);
      }

      .note.note--quiet {
        border-left-width: 2px;
        background: rgba(250, 248, 244, 0.96);
      }

      .subtle {
        color: var(--muted);
        font-size: 0.76rem;
      }

      .card--launch {
        --card-accent: var(--accent);
      }

      .card--review {
        --card-accent: var(--success);
      }

      .card--diagnostics {
        --card-accent: var(--danger);
      }

      .card--live {
        --card-accent: var(--info);
      }

      .card--status {
        --card-accent: var(--accent-alt);
      }

      @media (max-width: 1120px) {
        .layout {
          grid-template-columns: 1fr;
        }

        .status-grid {
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }
      }

      @media (max-width: 820px) {
        .preset-grid,
        .status-grid,
        .row {
          grid-template-columns: 1fr;
        }

        .actions > button {
          min-width: 0;
          width: 100%;
        }

        main {
          width: min(100vw - 18px, 100%);
          margin: 10px auto 28px;
        }

        .hero,
        .card {
          border-radius: 10px;
        }

        .hero-header {
          display: grid;
        }

        .hero-controls,
        .control-switch {
          justify-items: start;
        }

        .control-actions {
          justify-content: flex-start;
        }
      }
    </style>
  </head>
  <body>
    <main>
      <section class="hero">
        <div class="hero-header">
          <div class="hero-copy">
            <p class="eyebrow" data-i18n="hero.eyebrow">Host, Guest, and Human operator workflow</p>
            <h1 data-i18n="hero.title">Terminal Bridge</h1>
            <p data-i18n="hero.body">
              Pick a preset, start collaboration, watch the live room, and open advanced controls
              only when you actually need raw IDs, capture, or transport tuning.
            </p>
            <div class="meta">
              <span class="badge"><strong data-i18n="badges.mcp">MCP</strong> __MCP_ENDPOINT__</span>
              <span class="badge"><strong data-i18n="badges.transport">Transport</strong> <span id="transport-badge">idle</span></span>
              <span class="badge"><strong data-i18n="badges.preset">Preset</strong> <span id="preset-badge">Quick Pairing</span></span>
            </div>
          </div>
          <div class="hero-controls">
            <div class="control-switch">
              <span class="control-label" data-i18n="locale.label">Language</span>
              <div class="control-actions">
                <button class="ghost control-button" data-lang="en" type="button">EN</button>
                <button class="ghost control-button" data-lang="zh-TW" type="button">繁中</button>
              </div>
            </div>
            <div class="control-switch">
              <span class="control-label" data-i18n="layout.label">Layout</span>
              <div class="control-actions">
                <button class="ghost control-button" data-layout-mode="balanced" type="button" data-i18n="layout.balanced">Balanced</button>
                <button class="ghost control-button" data-layout-mode="wide" type="button" data-i18n="layout.wide">Wide</button>
                <button class="ghost control-button" data-layout-mode="stacked" type="button" data-i18n="layout.stacked">Stacked</button>
              </div>
            </div>
          </div>
        </div>
        <div class="preset-grid" id="preset-grid">
          <button class="preset" data-preset="quick" type="button">
            <b>Quick Pairing</b>
            <span>Fast Host + Guest launch with the minimum number of choices.</span>
          </button>
          <button class="preset" data-preset="approval" type="button">
            <b>Approval Gate</b>
            <span>Every forwarded handoff is held for human review before delivery.</span>
          </button>
          <button class="preset" data-preset="mcp" type="button">
            <b>MCP Operator</b>
            <span>Another client drives tool calls while this console stays focused on oversight.</span>
          </button>
          <button class="preset" data-preset="diagnostics" type="button">
            <b>Diagnostics</b>
            <span>Capture, interrupt, and raw status for backend validation and recovery.</span>
          </button>
          <button class="preset" data-preset="radar" type="button">
            <b>Handoff Radar</b>
            <span>Keep the live stream and approval queue side by side for dense review loops.</span>
          </button>
          <button class="preset" data-preset="quiet" type="button">
            <b>Quiet Loop</b>
            <span>Strip the console down to launch and live collaboration with minimal operator noise.</span>
          </button>
          <button class="preset" data-preset="mission" type="button">
            <b>Mission Control</b>
            <span>Surface topology, diagnostics, and coordination together for a host-led control shift.</span>
          </button>
        </div>
      </section>

      <section class="layout">
        <div class="stack">
          <article class="card card--launch card--current" id="launch-card">
            <div class="card-head">
              <span class="card-kicker" data-i18n="flow.launch">Step 1 · Launch</span>
              <h2 id="preset-title">Quick Pairing</h2>
              <p id="preset-copy">Launch Host and Guest, start a bridge, and watch the room without opening every advanced control first.</p>
            </div>
            <div class="stage-note" id="launch-note" data-i18n="cards.launchNote">Start here first. Once panes and bridge are ready, the live room becomes the main workspace.</div>

            <div class="row">
              <div>
                <label for="backend" data-i18n="fields.backend">backend</label>
                <select id="backend">__BACKEND_OPTIONS__</select>
              </div>
              <div>
                <label for="profile" data-i18n="fields.profile">profile</label>
                <select id="profile">
                  <option value="generic">generic</option>
                  <option value="codex">codex</option>
                  <option value="claude-code">claude-code</option>
                  <option value="gemini">gemini</option>
                  <option value="aider">aider</option>
                  <option value="llama">llama</option>
                </select>
              </div>
            </div>

            <div class="row">
              <div>
                <label for="session" data-i18n="fields.session">session</label>
                <input id="session" value="tb2-ai-first">
              </div>
              <div>
                <label for="deliver" data-i18n="fields.deliver">human delivery target</label>
                <select id="deliver">
                  <option value="" data-i18n="deliver.roomOnly">room only</option>
                  <option value="a" data-i18n="deliver.host">Host pane</option>
                  <option value="b" data-i18n="deliver.guest">Guest pane</option>
                  <option value="both" data-i18n="deliver.both">Both panes</option>
                </select>
              </div>
            </div>

            <div class="checks">
              <label><input id="auto-forward" type="checkbox" checked><span data-i18n="fields.autoForward">auto-forward Guest `MSG:` handoffs</span></label>
              <label><input id="intervention" type="checkbox"><span data-i18n="fields.intervention">require human approval before forwarding</span></label>
            </div>

            <div class="actions">
              <button id="init-session" type="button" data-i18n="actions.initSession">Init Session</button>
              <button id="start-bridge" class="alt" type="button" data-i18n="actions.startBridge">Start Collaboration</button>
              <button id="stop-bridge" class="warn" type="button" data-i18n="actions.stopBridge">Stop Bridge</button>
              <button id="refresh-status" class="ghost" type="button" data-i18n="actions.refreshStatus">Refresh Status</button>
            </div>

            <details>
              <summary data-i18n="actions.advanced">Advanced IDs, pane mapping, and transport</summary>
              <div class="row" style="margin-top: 12px;">
                <div>
                  <label for="backend-id" data-i18n="fields.backendId">backend_id</label>
                  <input id="backend-id" value="default">
                </div>
                <div>
                  <label for="transport" data-i18n="fields.transport">live room transport</label>
                  <select id="transport">
                    <option value="sse" data-i18n="transport.sse">SSE</option>
                    <option value="ws" data-i18n="transport.ws">WebSocket</option>
                    <option value="poll" data-i18n="transport.poll">room_poll</option>
                  </select>
                </div>
              </div>
              <div class="row">
                <div>
                  <label for="bridge-id" data-i18n="fields.bridgeId">bridge_id</label>
                  <input id="bridge-id" placeholder="auto if empty" data-i18n-placeholder="placeholders.autoIfEmpty">
                </div>
                <div>
                  <label for="room-id" data-i18n="fields.roomId">room_id</label>
                  <input id="room-id" placeholder="auto if empty" data-i18n-placeholder="placeholders.autoIfEmpty">
                </div>
              </div>
              <div class="row">
                <div>
                  <label for="pane-a" data-i18n="fields.paneHost">Host pane target</label>
                  <input id="pane-a" placeholder="filled by Init Session" data-i18n-placeholder="placeholders.filledByInit">
                </div>
                <div>
                  <label for="pane-b" data-i18n="fields.paneGuest">Guest pane target</label>
                  <input id="pane-b" placeholder="filled by Init Session" data-i18n-placeholder="placeholders.filledByInit">
                </div>
              </div>
            </details>
          </article>
        </div>

        <div class="stack">
          <article class="card card--live" id="live-card">
            <div class="card-head">
              <span class="card-kicker" data-i18n="flow.live">Step 2 · Live Room</span>
              <h2 data-i18n="cards.liveTitle">Live Collaboration</h2>
              <p data-i18n="cards.liveCopy">The room stream stays central. Send operator guidance to Host, Guest, or the room without leaving the task flow.</p>
            </div>
            <div class="status-grid">
              <div class="stat"><b data-i18n="metrics.host">Host</b><span id="metric-host">not ready</span></div>
              <div class="stat"><b data-i18n="metrics.guest">Guest</b><span id="metric-guest">not ready</span></div>
              <div class="stat"><b data-i18n="metrics.room">Room</b><span id="metric-room">not attached</span></div>
              <div class="stat"><b data-i18n="metrics.pending">Pending</b><span id="metric-pending">0</span></div>
            </div>
            <div class="note hidden" id="guard-note" data-i18n="cards.guardNote">Auto-forward guard active. New handoffs now route to review.</div>
            <div class="note note--quiet" id="live-empty" data-i18n="cards.liveEmpty">Start a bridge to reveal room controls and the live stream.</div>
            <div id="live-shell" class="hidden">
              <div class="row" style="margin-top: 12px;">
                <div>
                  <label for="send-text" data-i18n="fields.sendText">human operator message</label>
                  <textarea id="send-text" placeholder="Send guidance, clarification, or approval context" data-i18n-placeholder="placeholders.sendText"></textarea>
                </div>
                <div>
                  <label for="stream-box" data-i18n="fields.stream">live room stream</label>
                  <pre id="stream-box"></pre>
                </div>
              </div>
              <div class="actions" style="margin-top: 12px;">
                <button id="send-host" type="button" data-i18n="actions.sendHost">Send to Host</button>
                <button id="send-guest" class="alt" type="button" data-i18n="actions.sendGuest">Send to Guest</button>
                <button id="send-room" class="ghost" type="button" data-i18n="actions.sendRoom">Post to Room</button>
              </div>
            </div>
          </article>
        </div>
      </section>

      <section class="layout-secondary">
        <article class="card card--review hidden" id="pending-card">
          <details class="disclosure" id="pending-details">
            <summary class="disclosure-summary">
              <div class="summary-stack">
                <span class="card-kicker" data-i18n="flow.oversight">Step 3 · Oversight</span>
                <h2 data-i18n="cards.reviewTitle">Review Queue</h2>
              </div>
              <span class="disclosure-meta" id="pending-summary-meta">0 pending</span>
            </summary>
            <div class="disclosure-body">
              <p class="disclosure-copy" data-i18n="cards.reviewCopy">Approval Gate makes this the primary operating panel. In other presets it stays available but secondary.</p>
              <div class="note note--quiet" id="pending-empty" data-i18n="cards.reviewEmpty">No pending approvals yet. This section expands when intervention is enabled or approvals arrive.</div>
              <div class="queue">
                <div class="actions">
                  <button id="refresh-pending" class="ghost" type="button" data-i18n="actions.refreshPending">Refresh Pending</button>
                  <button id="approve-all" class="ok" type="button" data-i18n="actions.approveAll">Approve All</button>
                  <button id="reject-all" class="warn" type="button" data-i18n="actions.rejectAll">Reject All</button>
                </div>
                <div id="pending-work">
                  <div>
                    <label for="pending-select" data-i18n="fields.pendingSelect">pending intervention items</label>
                    <select id="pending-select" size="8"></select>
                  </div>
                  <div style="margin-top: 10px;">
                    <label for="pending-detail" data-i18n="fields.pendingDetail">selected pending detail</label>
                    <pre id="pending-detail"></pre>
                  </div>
                  <div style="margin-top: 10px;">
                    <label for="pending-edit" data-i18n="fields.pendingEdit">edited approval text</label>
                    <textarea id="pending-edit" placeholder="Optional replacement text for the selected pending message" data-i18n-placeholder="placeholders.pendingEdit"></textarea>
                  </div>
                  <div class="actions" style="margin-top: 10px;">
                    <button id="approve-selected" class="ok" type="button" data-i18n="actions.approveSelected">Approve Selected</button>
                    <button id="reject-selected" class="warn" type="button" data-i18n="actions.rejectSelected">Reject Selected</button>
                  </div>
                </div>
              </div>
            </div>
          </details>
        </article>

        <article class="card card--status" id="status-card">
          <details class="disclosure" id="status-details">
            <summary class="disclosure-summary">
              <div class="summary-stack">
                <span class="card-kicker" data-i18n="flow.status">Support · Status</span>
                <h2 data-i18n="cards.statusTitle">Status and Activity</h2>
              </div>
              <span class="disclosure-meta" id="status-summary-meta">Expand</span>
            </summary>
            <div class="disclosure-body">
              <p class="disclosure-copy" data-i18n="cards.statusCopy">Status and log.</p>
              <div class="note" id="status-note" data-i18n="cards.statusNote">Presets hide complexity, but they do not remove it. Open raw status when pane IDs, bridge IDs, or transport state matter.</div>
              <div class="badge-row" id="status-badges"></div>
              <div class="row">
                <div>
                  <label for="status-box" data-i18n="fields.status">server status</label>
                  <pre id="status-box"></pre>
                </div>
                <div>
                  <label for="log-box" data-i18n="fields.log">activity log</label>
                  <pre id="log-box"></pre>
                </div>
              </div>
            </div>
          </details>
        </article>

        <article class="card card--diagnostics hidden" id="diagnostics-card">
          <details class="disclosure" id="diagnostics-details">
            <summary class="disclosure-summary">
              <div class="summary-stack">
                <span class="card-kicker" data-i18n="flow.diagnostics">Advanced · Diagnostics</span>
                <h2 data-i18n="cards.diagnosticsTitle">Diagnostics</h2>
              </div>
              <span class="disclosure-meta" id="diagnostics-summary-meta">advanced tools</span>
            </summary>
            <div class="disclosure-body">
              <p class="disclosure-copy" data-i18n="cards.diagnosticsCopy">Use this when the task is capture, interrupt, raw verification, or backend troubleshooting rather than normal collaboration.</p>
              <div class="actions">
                <button id="capture-host" class="ghost" type="button" data-i18n="actions.captureHost">Capture Host</button>
                <button id="capture-guest" class="ghost" type="button" data-i18n="actions.captureGuest">Capture Guest</button>
                <button id="interrupt-host" class="warn" type="button" data-i18n="actions.interruptHost">Interrupt Host</button>
                <button id="interrupt-guest" class="warn" type="button" data-i18n="actions.interruptGuest">Interrupt Guest</button>
                <button id="interrupt-both" class="warn" type="button" data-i18n="actions.interruptBoth">Interrupt Both</button>
              </div>
              <div style="margin-top: 14px;">
                <label for="audit-box" data-i18n="fields.audit">audit trail</label>
                <div class="row" style="margin-top: 8px;">
                  <div>
                    <label for="audit-event" data-i18n="fields.auditEvent">audit event</label>
                    <select id="audit-event">
                      <option value="" data-i18n="auditEvents.all">all events</option>
                      __AUDIT_EVENT_OPTIONS__
                    </select>
                  </div>
                  <div>
                    <label for="audit-limit" data-i18n="fields.auditLimit">recent audit limit</label>
                    <input id="audit-limit" type="number" min="1" max="50" value="12">
                  </div>
                </div>
                <div class="actions" style="margin-top: 8px;">
                  <button id="refresh-audit" class="ghost" type="button" data-i18n="actions.refreshAudit">Refresh Audit</button>
                </div>
                <div class="note" id="audit-note" data-i18n="cards.auditDisabled">Audit trail is off. Set TB2_AUDIT=1 or TB2_AUDIT_DIR and restart the server to persist events.</div>
                <pre id="audit-box"></pre>
              </div>
              <details>
                <summary data-i18n="cards.captureSummary">Captured terminal state</summary>
                <div class="row" style="margin-top: 12px;">
                  <div>
                    <label for="capture-a-box" data-i18n="fields.captureHost">Host capture</label>
                    <textarea id="capture-a-box" readonly></textarea>
                  </div>
                  <div>
                    <label for="capture-b-box" data-i18n="fields.captureGuest">Guest capture</label>
                    <textarea id="capture-b-box" readonly></textarea>
                  </div>
                </div>
              </details>
            </div>
          </details>
        </article>
      </section>
    </main>

    <script>
      const MCP_ENDPOINT = '__MCP_ENDPOINT__';
      const SERVER_ROOT = new URL(MCP_ENDPOINT, window.location.href).origin;
      const I18N = {
        en: {
          title: 'Terminal Bridge',
          hero: {
            eyebrow: 'Host, Guest, and Human operator workflow',
            title: 'Terminal Bridge',
            body: 'Start task, choose preset, adjust parameters.'
          },
          badges: {
            mcp: 'MCP',
            transport: 'Transport',
            preset: 'Preset'
          },
          locale: {
            label: 'Language'
          },
          layout: {
            label: 'Layout',
            balanced: 'Balanced',
            wide: 'Wide',
            stacked: 'Stacked'
          },
          presets: {
            quick: {
              label: 'Quick Pairing',
              summary: 'Fast Host + Guest launch with the minimum number of choices.',
              copy: 'Init session and start bridge.'
            },
            approval: {
              label: 'Approval Gate',
              summary: 'Every forwarded handoff is held for human review before delivery.',
              copy: 'Review before delivery.'
            },
            mcp: {
              label: 'MCP Operator',
              summary: 'External MCP control with Vector linkage.',
              copy: 'Monitor room and bridge. Vector data can link with the Skill 0 main project vector database.'
            },
            diagnostics: {
              label: 'Diagnostics',
              summary: 'Capture and interrupt tools.',
              copy: 'Open tools when needed.'
            },
            radar: {
              label: 'Handoff Radar',
              summary: 'Dense review mode with live handoffs and the approval queue in one sweep.',
              copy: 'Stay on the room and the queue together.'
            },
            quiet: {
              label: 'Quiet Loop',
              summary: 'Low-noise collaboration view focused on launch plus live operator messaging.',
              copy: 'Keep the loop small and calm.'
            },
            mission: {
              label: 'Mission Control',
              summary: 'Host-centric console for topology, diagnostics, and coordination at the same time.',
              copy: 'Run the shift from status, room, and diagnostics together.'
            }
          },
          fields: {
            backend: 'backend',
            profile: 'profile',
            session: 'session',
            deliver: 'human delivery target',
            autoForward: 'auto-forward Guest `MSG:` handoffs',
            intervention: 'require human approval before forwarding',
            backendId: 'backend_id',
            transport: 'live room transport',
            bridgeId: 'bridge_id',
            roomId: 'room_id',
            paneHost: 'Host pane target',
            paneGuest: 'Guest pane target',
            pendingSelect: 'pending intervention items',
            pendingDetail: 'selected pending detail',
            pendingEdit: 'edited approval text',
            captureHost: 'Host capture',
            captureGuest: 'Guest capture',
            audit: 'audit trail',
            auditEvent: 'audit event',
            auditLimit: 'recent audit limit',
            sendText: 'human operator message',
            stream: 'live room stream',
            status: 'server status',
            log: 'activity log'
          },
          deliver: {
            roomOnly: 'room only',
            host: 'Host pane',
            guest: 'Guest pane',
            both: 'Both panes'
          },
          transport: {
            sse: 'SSE',
            ws: 'WebSocket',
            poll: 'room_poll',
            active: '{mode} active',
            idle: 'idle'
          },
          actions: {
            initSession: 'Init Session',
            startBridge: 'Start Collaboration',
            stopBridge: 'Stop Bridge',
            refreshStatus: 'Refresh Status',
            advanced: 'Advanced IDs, pane mapping, and transport',
            refreshPending: 'Refresh Pending',
            approveAll: 'Approve All',
            rejectAll: 'Reject All',
            approveSelected: 'Approve Selected',
            rejectSelected: 'Reject Selected',
            refreshAudit: 'Refresh Audit',
            captureHost: 'Capture Host',
            captureGuest: 'Capture Guest',
            interruptHost: 'Interrupt Host',
            interruptGuest: 'Interrupt Guest',
            interruptBoth: 'Interrupt Both',
            sendHost: 'Send to Host',
            sendGuest: 'Send to Guest',
            sendRoom: 'Post to Room'
          },
          cards: {
            reviewTitle: 'Review Queue',
            reviewCopy: 'Approve or reject pending items.',
            reviewEmpty: 'No pending items.',
            reviewMetaIdle: 'Expand',
            reviewMetaPending: '{count} pending',
            pendingDetailEmpty: 'Select a pending item to inspect the full review context.',
            pendingDetailAction: 'Action',
            pendingDetailCreated: 'Created',
            pendingDetailRoute: 'Route',
            pendingDetailOriginal: 'Original',
            pendingDetailEdited: 'Edited',
            pendingDetailEditedFallback: '(not edited)',
            diagnosticsTitle: 'Diagnostics',
            diagnosticsCopy: 'Capture and interrupt tools.',
            diagnosticsMeta: 'Tools',
            diagnosticsMetaAudited: 'Audit on',
            captureSummary: 'Captured terminal state',
            launchNote: 'Init session, then start bridge.',
            liveTitle: 'Live Collaboration',
            liveCopy: 'Watch room and send messages.',
            liveEmpty: 'Start bridge to show room tools.',
            guardReasonFallback: 'unspecified',
            guardNote: 'Auto-forward guard active. New handoffs now route to review: {reason}',
            auditDisabled: 'Audit trail is off. Set TB2_AUDIT=1 or TB2_AUDIT_DIR and restart the server to persist events.',
            auditEnabled: 'Audit trail is writing to {file}.',
            auditRedaction: 'Persisted text fields are redacted ({mode}).',
            auditRedactionRequested: 'Requested redaction mode is {requested}; effective mode is {mode}.',
            auditRedactionFullWarning: 'Warning: full mode stores raw text in durable audit entries.',
            auditRedactionFullBlocked: 'Full mode was requested but is blocked until {env}=1 is set.',
            auditDestinationFallback: 'configured destination',
            auditError: 'Audit trail error: {error}',
            auditEmpty: 'No recent audit entries for the current scope.',
            auditScope: 'Scope: {scope}. Filter: {event}. Limit: {limit}.',
            auditScopeFallback: 'global',
            statusTitle: 'Status and Activity',
            statusCopy: 'Status and log.',
            statusNote: 'Open to view details.',
            statusMetaIdle: 'Expand',
            statusMetaReady: 'Active',
            statusMetaGuarded: 'Guarded',
            statusBadgeReady: 'Delivery active',
            statusBadgeGuarded: 'Guarded',
            statusBadgePending: 'Pending {count}',
            statusBadgeTransport: 'Subscribers {total} ({sse} SSE / {websocket} WS)',
            statusBadgeTransportIdle: 'Subscribers idle',
            statusBadgeAuditOn: 'Audit on',
            statusBadgeAuditOff: 'Audit off',
            statusBadgeAuditRaw: 'Audit raw text',
            statusBadgeAuditRawBlocked: 'Audit raw blocked'
          },
          auditEvents: {
            all: 'all events'
          },
          metrics: {
            host: 'Host',
            guest: 'Guest',
            room: 'Room',
            pending: 'Pending',
            notReady: 'not ready',
            notAttached: 'not attached'
          },
          placeholders: {
            autoIfEmpty: 'auto if empty',
            filledByInit: 'filled by Init Session',
            pendingEdit: 'Optional replacement text for the selected pending message',
            sendText: 'Send guidance, clarification, or approval context'
          },
          logs: {
            sseReady: 'SSE ready for room {roomId}',
            sseDisconnected: 'SSE stream disconnected',
            wsSubscribed: 'WebSocket subscribed to room {roomId}',
            wsError: 'ws error: {error}',
            wsClosed: 'WebSocket stream closed',
            sessionReady: 'Host + Guest panes ready in session {session}',
            bridgeOnline: 'Collaboration bridge online: {bridgeId}',
            bridgeStopped: 'Bridge stopped',
            roomPosted: 'Human operator message posted{target}',
            captureDone: 'Captured {target}',
            interruptSent: 'Interrupt sent to {target}',
            approved: 'Pending handoff approved',
            rejected: 'Pending handoff rejected',
            ready: 'GUI ready, endpoint {endpoint}',
            languageChanged: 'Language switched to {language}',
            layoutChanged: 'Layout switched to {layout}'
          },
          errors: {
            toolCallFailed: 'tool call failed',
            paneTargetsRequired: 'pane targets are required',
            bridgeIdRequired: 'bridge_id is required',
            roomIdRequired: 'room_id is required',
            messageEmpty: 'message is empty',
            targetPaneRequired: 'target pane is required',
            selectPendingFirst: 'select a pending item first',
            errorPrefix: 'error: {message}'
          },
          languages: {
            en: 'English',
            'zh-TW': 'Traditional Chinese'
          },
          layouts: {
            balanced: 'Balanced',
            wide: 'Wide',
            stacked: 'Stacked'
          },
          flow: {
            launch: 'Step 1 · Launch',
            live: 'Step 2 · Live Room',
            oversight: 'Step 3 · Oversight',
            status: 'Support · Status',
            diagnostics: 'Advanced · Diagnostics'
          }
        },
        'zh-TW': {
          title: 'Terminal Bridge',
          hero: {
            eyebrow: 'Host、Guest 與 Human Operator 協作流程',
            title: 'Terminal Bridge',
            body: '啟動任務 選擇preset 調整參數'
          },
          badges: {
            mcp: 'MCP',
            transport: '傳輸',
            preset: '場景'
          },
          locale: {
            label: '語言'
          },
          layout: {
            label: '版面',
            balanced: '標準',
            wide: '加寬',
            stacked: '堆疊'
          },
          presets: {
            quick: {
              label: '快速配對',
              summary: '用最少選項啟動一組 Host + Guest。',
              copy: '初始化 Session，啟動 Bridge。'
            },
            approval: {
              label: '審核閘門',
              summary: '每一筆轉發 handoff 都先進人工審核再送出。',
              copy: '送出前先審核。'
            },
            mcp: {
              label: 'MCP 操作台',
              summary: '外部 MCP 控制，可連動 Vector 資訊。',
              copy: '監看 room 與 bridge。Vector 資訊可和 Skill 0 主專案的向量資料庫連動利用。'
            },
            diagnostics: {
              label: '診斷模式',
              summary: '擷取與中斷工具。',
              copy: '需要時開啟工具。'
            },
            radar: {
              label: '交接雷達',
              summary: '把 live handoff 與審核佇列放在同一個工作面，適合密集 review。',
              copy: 'room 與 queue 一起盯。'
            },
            quiet: {
              label: '靜默迴圈',
              summary: '低噪音協作視角，只保留啟動與即時訊息主線。',
              copy: '把操作面收斂到最安靜的迴圈。'
            },
            mission: {
              label: '任務總控台',
              summary: '同時打開拓樸、診斷與協調，適合 Host 主導值班。',
              copy: '用狀態、room 與診斷一起帶班。'
            }
          },
          fields: {
            backend: 'backend',
            profile: 'profile',
            session: 'session',
            deliver: '人工訊息送達目標',
            autoForward: '自動轉發 Guest 的 `MSG:` handoff',
            intervention: '轉發前必須先經人工核准',
            backendId: 'backend_id',
            transport: 'live room 傳輸方式',
            bridgeId: 'bridge_id',
            roomId: 'room_id',
            paneHost: 'Host pane 目標',
            paneGuest: 'Guest pane 目標',
            pendingSelect: '待處理 intervention 項目',
            pendingDetail: '目前待審細節',
            pendingEdit: '核准時改寫文字',
            captureHost: 'Host capture',
            captureGuest: 'Guest capture',
            audit: 'audit trail',
            auditEvent: 'audit event',
            auditLimit: 'recent audit limit',
            sendText: 'human operator 訊息',
            stream: 'live room stream',
            status: 'server status',
            log: 'activity log'
          },
          deliver: {
            roomOnly: '只發到 room',
            host: 'Host pane',
            guest: 'Guest pane',
            both: '兩邊 pane'
          },
          transport: {
            sse: 'SSE',
            ws: 'WebSocket',
            poll: 'room_poll',
            active: '{mode} 已啟用',
            idle: '閒置'
          },
          actions: {
            initSession: '初始化 Session',
            startBridge: '開始協作',
            stopBridge: '停止 Bridge',
            refreshStatus: '更新狀態',
            advanced: '進階 IDs、pane 對應與 transport',
            refreshPending: '更新待審項目',
            approveAll: '全部核准',
            rejectAll: '全部退回',
            approveSelected: '核准所選項目',
            rejectSelected: '退回所選項目',
            refreshAudit: '更新 Audit',
            captureHost: '擷取 Host',
            captureGuest: '擷取 Guest',
            interruptHost: '中斷 Host',
            interruptGuest: '中斷 Guest',
            interruptBoth: '同時中斷',
            sendHost: '送到 Host',
            sendGuest: '送到 Guest',
            sendRoom: '發到 Room'
          },
          cards: {
            reviewTitle: '審核佇列',
            reviewCopy: '核准或退回待審項目。',
            reviewEmpty: '目前沒有待審項目。',
            reviewMetaIdle: '展開',
            reviewMetaPending: '{count} 筆待審',
            pendingDetailEmpty: '先選一筆待審項目，再查看完整審核脈絡。',
            pendingDetailAction: 'Action',
            pendingDetailCreated: '建立時間',
            pendingDetailRoute: '路徑',
            pendingDetailOriginal: '原始內容',
            pendingDetailEdited: '改寫內容',
            pendingDetailEditedFallback: '（尚未改寫）',
            diagnosticsTitle: '診斷模式',
            diagnosticsCopy: '擷取與中斷工具。',
            diagnosticsMeta: '工具',
            diagnosticsMetaAudited: 'Audit 已啟用',
            captureSummary: '擷取的 terminal 狀態',
            launchNote: '先初始化 Session，再啟動 Bridge。',
            liveTitle: '即時協作',
            liveCopy: '查看 room 並送出訊息。',
            liveEmpty: '啟動 Bridge 後顯示 room 工具。',
            guardReasonFallback: '未提供原因',
            guardNote: 'Auto-forward guard 已啟用。新的 handoff 會改送 review：{reason}',
            auditDisabled: 'Audit trail 目前未啟用。請設定 TB2_AUDIT=1 或 TB2_AUDIT_DIR，並重新啟動 server 才會持久化事件。',
            auditEnabled: 'Audit trail 正在寫入 {file}。',
            auditRedaction: '持久化文字欄位會先做遮罩（{mode}）。',
            auditRedactionRequested: '要求的 redaction mode 是 {requested}；目前實際生效的是 {mode}。',
            auditRedactionFullWarning: '警告：full mode 會把 raw text 寫進 durable audit entry。',
            auditRedactionFullBlocked: '目前雖然要求 full mode，但在設定 {env}=1 前都會被阻擋。',
            auditDestinationFallback: '已設定的目的地',
            auditError: 'Audit trail 錯誤：{error}',
            auditEmpty: '目前 scope 沒有最近的 audit entries。',
            auditScope: '目前 scope：{scope}。Filter：{event}。Limit：{limit}。',
            auditScopeFallback: '全域',
            statusTitle: '狀態與活動',
            statusCopy: '',
            statusNote: '展開查看詳細資訊。',
            statusMetaIdle: '展開',
            statusMetaReady: '運作中',
            statusMetaGuarded: '受保護',
            statusBadgeReady: '轉發中',
            statusBadgeGuarded: '受保護',
            statusBadgePending: '待審 {count}',
            statusBadgeTransport: '訂閱 {total}（SSE {sse} / WS {websocket}）',
            statusBadgeTransportIdle: '目前沒有訂閱',
            statusBadgeAuditOn: 'Audit 已啟用',
            statusBadgeAuditOff: 'Audit 未啟用',
            statusBadgeAuditRaw: 'Audit 含 raw text',
            statusBadgeAuditRawBlocked: 'Audit raw 已阻擋'
          },
          auditEvents: {
            all: '全部事件'
          },
          metrics: {
            host: 'Host',
            guest: 'Guest',
            room: 'Room',
            pending: '待審',
            notReady: '尚未就緒',
            notAttached: '尚未連接'
          },
          placeholders: {
            autoIfEmpty: '留空則自動產生',
            filledByInit: '按 Init Session 後自動填入',
            pendingEdit: '可選填，用來覆蓋目前待審訊息的送出內容',
            sendText: '輸入指示、補充說明或核准脈絡'
          },
          logs: {
            sseReady: 'SSE 已連上 room {roomId}',
            sseDisconnected: 'SSE 串流已中斷',
            wsSubscribed: 'WebSocket 已訂閱 room {roomId}',
            wsError: 'ws 錯誤: {error}',
            wsClosed: 'WebSocket 串流已關閉',
            sessionReady: 'Host + Guest panes 已在 session {session} 建立完成',
            bridgeOnline: '協作 bridge 已上線: {bridgeId}',
            bridgeStopped: 'Bridge 已停止',
            roomPosted: '已送出 human operator 訊息{target}',
            captureDone: '已擷取 {target}',
            interruptSent: '已送出 interrupt 到 {target}',
            approved: '待審 handoff 已核准',
            rejected: '待審 handoff 已退回',
            ready: 'GUI 已就緒，endpoint {endpoint}',
            languageChanged: '語言已切換為 {language}',
            layoutChanged: '版面已切換為 {layout}'
          },
          errors: {
            toolCallFailed: '工具呼叫失敗',
            paneTargetsRequired: '必須先提供 pane targets',
            bridgeIdRequired: '必須提供 bridge_id',
            roomIdRequired: '必須提供 room_id',
            messageEmpty: '訊息不可為空',
            targetPaneRequired: '必須提供 target pane',
            selectPendingFirst: '請先選擇一筆待審項目',
            errorPrefix: '錯誤: {message}'
          },
          languages: {
            en: 'English',
            'zh-TW': '繁體中文'
          },
          layouts: {
            balanced: '標準',
            wide: '加寬',
            stacked: '堆疊'
          },
          flow: {
            launch: '步驟 1 · 啟動',
            live: '步驟 2 · 即時協作',
            oversight: '步驟 3 · 人工審核',
            status: '支援 · 狀態',
            diagnostics: '進階 · 診斷'
          }
        }
      };
      const PRESETS = {
        quick: {
          transport: 'sse',
          autoForward: true,
          intervention: false,
          showPending: false,
          showDiagnostics: false,
          showStatus: true,
          focus: 'launch',
          scene: 'quick'
        },
        approval: {
          transport: 'sse',
          autoForward: true,
          intervention: true,
          showPending: true,
          showDiagnostics: false,
          showStatus: true,
          focus: 'pending',
          scene: 'approval'
        },
        mcp: {
          transport: 'ws',
          autoForward: false,
          intervention: false,
          showPending: false,
          showDiagnostics: false,
          showStatus: true,
          focus: 'status',
          scene: 'mcp'
        },
        diagnostics: {
          transport: 'poll',
          autoForward: false,
          intervention: false,
          showPending: false,
          showDiagnostics: true,
          showStatus: true,
          focus: 'diagnostics',
          scene: 'diagnostics'
        },
        radar: {
          transport: 'sse',
          autoForward: true,
          intervention: true,
          showPending: true,
          showDiagnostics: false,
          showStatus: true,
          focus: 'pending',
          scene: 'radar'
        },
        quiet: {
          transport: 'sse',
          autoForward: true,
          intervention: false,
          showPending: false,
          showDiagnostics: false,
          showStatus: false,
          focus: 'live',
          scene: 'quiet'
        },
        mission: {
          transport: 'ws',
          autoForward: false,
          intervention: false,
          showPending: true,
          showDiagnostics: true,
          showStatus: true,
          focus: 'status',
          scene: 'mission'
        }
      };

      const state = {
        reqId: 1,
        locale: 'en',
        layout: 'balanced',
        preset: 'quick',
        home: true,
        lastMsgId: 0,
        poller: null,
        sse: null,
        ws: null,
        guard: null,
        audit: null,
        auditEvents: [],
        pendingItems: [],
        seen: new Set()
      };

      const $ = id => document.getElementById(id);

      function lookup(locale, path) {
        return path.split('.').reduce((node, key) => (
          node && typeof node === 'object' && key in node ? node[key] : undefined
        ), I18N[locale] || I18N.en);
      }

      function t(path) {
        return lookup(state.locale, path) ?? lookup('en', path) ?? path;
      }

      function format(path, values) {
        return t(path).replace(/\{(\w+)\}/g, (_, key) => String((values && values[key]) ?? ''));
      }

      function preferredLocale() {
        try {
          const saved = window.localStorage.getItem('tb2-lang');
          if (saved && I18N[saved]) return saved;
        } catch (_) {
          // Ignore storage failures and fall back to navigator language.
        }
        const detected = String(window.navigator.language || '').toLowerCase();
        if (detected.startsWith('zh')) return 'zh-TW';
        return 'en';
      }

      function preferredLayout() {
        try {
          const saved = window.localStorage.getItem('tb2-layout');
          if (saved === 'balanced' || saved === 'wide' || saved === 'stacked') return saved;
        } catch (_) {
          // Ignore storage failures and fall back to the default layout.
        }
        return 'wide';
      }

      function transportName(mode) {
        return t('transport.' + mode);
      }

      function setLanguageButtons() {
        document.querySelectorAll('[data-lang]').forEach(button => {
          button.classList.toggle('active', button.dataset.lang === state.locale);
        });
      }

      function setLayoutButtons() {
        document.querySelectorAll('[data-layout-mode]').forEach(button => {
          button.classList.toggle('active', button.dataset.layoutMode === state.layout);
        });
      }

      function renderPresetCards() {
        document.querySelectorAll('[data-preset]').forEach(button => {
          const name = button.dataset.preset;
          const label = lookup(state.locale, 'presets.' + name + '.label') || lookup('en', 'presets.' + name + '.label');
          const summary = lookup(state.locale, 'presets.' + name + '.summary') || lookup('en', 'presets.' + name + '.summary');
          const titleNode = button.querySelector('b');
          const summaryNode = button.querySelector('span');
          if (titleNode) titleNode.textContent = label;
          if (summaryNode) summaryNode.textContent = summary;
        });
      }

      function translatePage() {
        document.title = t('title');
        document.documentElement.lang = state.locale;
        document.querySelectorAll('[data-i18n]').forEach(node => {
          node.textContent = t(node.dataset.i18n);
        });
        document.querySelectorAll('[data-i18n-placeholder]').forEach(node => {
          node.setAttribute('placeholder', t(node.dataset.i18nPlaceholder));
        });
        renderPresetCards();
        setLanguageButtons();
        setLayoutButtons();
        renderAudit();
      }

      function applyLocale(locale) {
        state.locale = I18N[locale] ? locale : 'en';
        try {
          window.localStorage.setItem('tb2-lang', state.locale);
        } catch (_) {
          // Ignore storage failures.
        }
        translatePage();
        applyPreset(state.preset);
        syncMetrics();
      }

      function applyLayout(mode) {
        state.layout = mode === 'stacked' || mode === 'balanced' || mode === 'wide' ? mode : 'balanced';
        document.body.dataset.layout = state.layout;
        document.body.dataset.home = state.home ? 'preset-only' : 'workspace';
        try {
          window.localStorage.setItem('tb2-layout', state.layout);
        } catch (_) {
          // Ignore storage failures.
        }
        setLayoutButtons();
      }

      function revealWorkspace() {
        if (!state.home) return;
        state.home = false;
        document.body.dataset.home = 'workspace';
      }

      const log = text => {
        const box = $('log-box');
        box.textContent += '[' + new Date().toLocaleTimeString() + '] ' + text + '\n';
        box.scrollTop = box.scrollHeight;
      };

      const commonArgs = () => ({
        backend: $('backend').value.trim(),
        backend_id: $('backend-id').value.trim() || 'default'
      });

      const normalize = raw => {
        if (!raw || typeof raw !== 'object') return raw;
        if (raw.structuredContent && typeof raw.structuredContent === 'object') return raw.structuredContent;
        if (!Array.isArray(raw.content)) return raw;
        const item = raw.content.find(entry => entry && entry.type === 'text' && typeof entry.text === 'string');
        if (!item) return {};
        try {
          return JSON.parse(item.text);
        } catch (_) {
          return { text: item.text };
        }
      };

      function formatBridgeCandidates(payload) {
        const candidates = Array.isArray(payload && payload.bridge_candidates) ? payload.bridge_candidates : [];
        if (!candidates.length) return '';
        const labels = candidates.map(item => {
          if (!item || typeof item !== 'object') return '';
          const bridgeId = String(item.bridge_id || '').trim();
          const roomId = String(item.room_id || '').trim();
          if (bridgeId && roomId) return bridgeId + ' (' + roomId + ')';
          return bridgeId;
        }).filter(Boolean);
        if (!labels.length) return '';
        return ' | candidates: ' + labels.join(', ');
      }

      async function rpc(method, params) {
        const resp = await fetch(MCP_ENDPOINT, {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({
            jsonrpc: '2.0',
            id: state.reqId++,
            method,
            params: params || {}
          })
        });
        const data = await resp.json();
        if (data.error) throw new Error(data.error.message || JSON.stringify(data.error));
        return data.result;
      }

      async function tool(name, args) {
        const raw = await rpc('tools/call', { name, arguments: args || {} });
        const out = normalize(raw);
        if (raw && raw.isError) throw new Error(((out && out.error) || t('errors.toolCallFailed')) + formatBridgeCandidates(out));
        if (out && typeof out.error === 'string') throw new Error(out.error + formatBridgeCandidates(out));
        return out;
      }

      function setHidden(id, hidden) {
        $(id).classList.toggle('hidden', hidden);
      }

      function syncMetrics() {
        $('metric-host').textContent = $('pane-a').value.trim() || t('metrics.notReady');
        $('metric-guest').textContent = $('pane-b').value.trim() || t('metrics.notReady');
        $('metric-room').textContent = $('room-id').value.trim() || t('metrics.notAttached');
        $('transport-badge').textContent = $('transport').value ? format('transport.active', {
          mode: transportName($('transport').value)
        }) : t('transport.idle');
        syncPanels();
      }

      function syncPanels() {
        const hasPanes = Boolean($('pane-a').value.trim() && $('pane-b').value.trim());
        const hasBridge = Boolean($('bridge-id').value.trim());
        const hasRoom = Boolean($('room-id').value.trim());
        const liveActive = hasBridge && hasRoom;
        const pendingCount = Number($('metric-pending').textContent || '0') || 0;
        const guardBlocked = Boolean(state.guard && state.guard.blocked);
        const preset = PRESETS[state.preset] || PRESETS.quick;
        const focus = preset.focus || 'launch';
        const showStatus = preset.showStatus !== false;

        $('launch-card').classList.toggle('card--current', focus === 'launch' || (!liveActive && focus !== 'status'));
        $('live-card').classList.toggle('card--current', focus === 'live' || ((hasPanes || liveActive) && focus === 'launch'));
        $('pending-card').classList.toggle('card--current', focus === 'pending' || pendingCount > 0 || state.preset === 'approval');
        $('status-card').classList.toggle('card--current', focus === 'status');
        $('diagnostics-card').classList.toggle('card--current', focus === 'diagnostics');

        setHidden('live-shell', !liveActive);
        setHidden('live-empty', liveActive);
        setHidden('guard-note', !guardBlocked);

        setHidden('pending-card', !(preset.showPending || pendingCount > 0));
        setHidden('diagnostics-card', !preset.showDiagnostics);
        setHidden('status-card', !showStatus);
        setHidden('pending-empty', pendingCount > 0);
        setHidden('pending-work', pendingCount === 0);

        $('pending-summary-meta').textContent = pendingCount > 0
          ? format('cards.reviewMetaPending', { count: pendingCount })
          : t('cards.reviewMetaIdle');
        $('status-summary-meta').textContent = guardBlocked
          ? t('cards.statusMetaGuarded')
          : (hasBridge || hasRoom ? t('cards.statusMetaReady') : t('cards.statusMetaIdle'));
        $('diagnostics-summary-meta').textContent = state.audit && state.audit.enabled
          ? t('cards.diagnosticsMetaAudited')
          : t('cards.diagnosticsMeta');
        if (guardBlocked) {
          $('guard-note').textContent = format('cards.guardNote', {
            reason: state.guard.guard_reason || t('cards.guardReasonFallback')
          });
        }

        $('pending-details').open = state.preset === 'approval' || pendingCount > 0;
        $('status-details').open = focus === 'status';
        if (state.preset === 'diagnostics') $('diagnostics-details').open = true;
        if (focus === 'diagnostics') $('diagnostics-details').open = true;
      }

      function applyPreset(name) {
        const preset = PRESETS[name] || PRESETS.quick;
        state.preset = name;
        revealWorkspace();
        document.body.dataset.scene = preset.scene || name;
        const label = t('presets.' + name + '.label');
        $('preset-badge').textContent = label;
        $('preset-title').textContent = label;
        $('preset-copy').textContent = t('presets.' + name + '.copy');
        $('transport').value = preset.transport;
        $('auto-forward').checked = preset.autoForward;
        $('intervention').checked = preset.intervention;
        document.querySelectorAll('[data-preset]').forEach(button => {
          button.classList.toggle('active', button.dataset.preset === name);
        });
        syncMetrics();
      }

      function appendEvent(event) {
        if (!event) return;
        const key = event.event_id || String(event.id || '');
        if (key && state.seen.has(key)) return;
        if (key) state.seen.add(key);
        state.lastMsgId = Math.max(state.lastMsgId, Number(event.id || 0));
        const box = $('stream-box');
        const source = event.source || {};
        const role = String(source.role || event.source_role || '').trim();
        const trusted = Boolean(source.trusted ?? event.trusted);
        const label = role && role !== (event.author || '') ? (event.author || '?') + ' (' + role + ')' : (event.author || '?');
        const trust = trusted ? ' [trusted]' : '';
        box.textContent += '[' + (event.kind || 'chat') + '] ' + label + trust + ' | ' + (event.text || '') + '\n';
        box.scrollTop = box.scrollHeight;
      }

      function formatAuditEntry(item) {
        const ts = item && item.ts ? new Date(Number(item.ts) * 1000).toLocaleTimeString() : '?';
        const event = String((item && item.event) || 'event');
        const bridgeId = String((item && item.bridge_id) || '').trim();
        const roomId = String((item && item.room_id) || '').trim();
        const scope = [bridgeId, roomId].filter(Boolean).join(' / ');
        return '[' + ts + '] ' + event + (scope ? ' | ' + scope : '') + '\n' + JSON.stringify(item, null, 2);
      }

      function auditNoteText(audit, scope, event, limit) {
        const enabled = Boolean(audit && audit.enabled);
        const destination = String((audit && (audit.file || audit.root)) || '').trim() || t('cards.auditDestinationFallback');
        let note = enabled
          ? format('cards.auditEnabled', { file: destination })
          : t('cards.auditDisabled');
        if (audit && audit.redaction && audit.redaction.mode) {
          note += ' ' + format('cards.auditRedaction', { mode: String(audit.redaction.mode) });
        }
        if (
          audit
          && audit.redaction
          && audit.redaction.requested_mode
          && audit.redaction.requested_mode !== audit.redaction.mode
        ) {
          note += ' ' + format('cards.auditRedactionRequested', {
            requested: String(audit.redaction.requested_mode),
            mode: String(audit.redaction.mode)
          });
        }
        if (audit && audit.redaction && audit.redaction.raw_text_opt_in_blocked) {
          note += ' ' + format('cards.auditRedactionFullBlocked', {
            env: String(audit.redaction.raw_text_opt_in_env || 'TB2_AUDIT_ALLOW_FULL_TEXT')
          });
        }
        if (audit && audit.redaction && audit.redaction.stores_raw_text) {
          note += ' ' + t('cards.auditRedactionFullWarning');
        }
        if (audit && audit.last_error) {
          note += ' ' + format('cards.auditError', { error: audit.last_error });
        }
        note += ' ' + format('cards.auditScope', { scope, event, limit });
        return note;
      }

      function renderAudit() {
        const audit = state.audit || {};
        const bridgeId = $('bridge-id').value.trim();
        const roomId = $('room-id').value.trim();
        const scope = [bridgeId, roomId].filter(Boolean).join(' / ') || t('cards.auditScopeFallback');
        const event = $('audit-event').value.trim() || t('auditEvents.all');
        const limit = $('audit-limit').value.trim() || '12';
        const note = auditNoteText(audit, scope, event, limit);
        $('audit-note').textContent = note;
        $('refresh-audit').disabled = !audit.enabled;
        $('audit-box').textContent = state.auditEvents.length
          ? state.auditEvents.map(formatAuditEntry).join('\n\n')
          : t('cards.auditEmpty');
      }

      function stopTransport() {
        if (state.poller) {
          clearInterval(state.poller);
          state.poller = null;
        }
        if (state.sse) {
          state.sse.close();
          state.sse = null;
        }
        if (state.ws) {
          state.ws.close();
          state.ws = null;
        }
      }

      async function pollRoom() {
        const roomId = $('room-id').value.trim();
        if (!roomId) return;
        const res = await tool('room_poll', { room_id: roomId, after_id: state.lastMsgId, limit: 200 });
        for (const msg of res.messages || []) appendEvent(msg);
      }

      function connectTransport() {
        stopTransport();
        const roomId = $('room-id').value.trim();
        if (!roomId) return;
        const mode = $('transport').value;
        $('transport-badge').textContent = mode + ' active';
        if (mode === 'poll') {
          pollRoom();
          state.poller = setInterval(() => run(pollRoom), 1200);
          return;
        }
        if (mode === 'sse') {
          const es = new EventSource(
            SERVER_ROOT + '/rooms/' + encodeURIComponent(roomId) + '/stream?after_id=' +
            encodeURIComponent(String(state.lastMsgId)) + '&limit=200'
          );
          state.sse = es;
          es.addEventListener('room', event => appendEvent(JSON.parse(event.data)));
          es.addEventListener('ready', event => log(format('logs.sseReady', { roomId: JSON.parse(event.data).room_id })));
          es.onerror = () => log(t('logs.sseDisconnected'));
          return;
        }
        const wsUrl = new URL(SERVER_ROOT + '/ws', window.location.href);
        wsUrl.protocol = wsUrl.protocol === 'https:' ? 'wss:' : 'ws:';
        const ws = new WebSocket(wsUrl.toString());
        state.ws = ws;
        ws.addEventListener('open', () => {
          ws.send(JSON.stringify({
            action: 'subscribe',
            room_id: roomId,
            after_id: state.lastMsgId,
            limit: 200
          }));
        });
        ws.addEventListener('message', event => {
          const msg = JSON.parse(event.data);
          if (msg.type === 'room_event' && msg.event) appendEvent(msg.event);
          if (msg.type === 'subscribed') log(format('logs.wsSubscribed', { roomId: msg.room_id }));
          if (msg.type === 'error') log(format('logs.wsError', { error: msg.error }));
        });
        ws.addEventListener('close', () => log(t('logs.wsClosed')));
      }

      function formatPendingTimestamp(ts) {
        const value = Number(ts || 0);
        if (!value) return '?';
        const date = new Date(value * 1000);
        return Number.isNaN(date.getTime()) ? String(ts) : date.toLocaleString();
      }

      function selectedPendingItem() {
        const id = $('pending-select').value;
        if (!id) return null;
        return state.pendingItems.find(item => String(item.id) === id) || null;
      }

      function renderPendingDetail() {
        const item = selectedPendingItem();
        const box = $('pending-detail');
        const edit = $('pending-edit');
        if (!item) {
          box.textContent = t('cards.pendingDetailEmpty');
          if (document.activeElement !== edit) edit.value = '';
          return;
        }
        if (document.activeElement !== edit) edit.value = String(item.edited_text || '');
        box.textContent = [
          t('cards.pendingDetailAction') + ': ' + String(item.action || '?'),
          t('cards.pendingDetailCreated') + ': ' + formatPendingTimestamp(item.created_at),
          t('cards.pendingDetailRoute') + ': ' + String(item.from_pane || '?') + ' -> ' + String(item.to_pane || '?'),
          t('cards.pendingDetailOriginal') + ': ' + String(item.text || ''),
          t('cards.pendingDetailEdited') + ': ' + String(item.edited_text || t('cards.pendingDetailEditedFallback')),
        ].join('\n');
      }

      function fillPending(items) {
        state.pendingItems = Array.isArray(items) ? items : [];
        const select = $('pending-select');
        select.innerHTML = '';
        for (const item of state.pendingItems) {
          const option = document.createElement('option');
          option.value = String(item.id);
          option.textContent = '#' + item.id + ' [' + item.action + '] ' + item.from_pane + ' -> ' + item.to_pane + ' | ' + item.text;
          select.appendChild(option);
        }
        if (select.options.length) select.selectedIndex = 0;
        $('metric-pending').textContent = String(state.pendingItems.length);
        renderPendingDetail();
        syncPanels();
      }

      function bridgeArgs() {
        const args = {};
        const bridgeId = $('bridge-id').value.trim();
        const roomId = $('room-id').value.trim();
        if (bridgeId) args.bridge_id = bridgeId;
        if (!bridgeId && roomId) args.room_id = roomId;
        return args;
      }

      function clearBridgeState() {
        $('bridge-id').value = '';
        $('pending-edit').value = '';
        state.guard = null;
        fillPending([]);
      }

      function isInactiveBridgeError(message) {
        if (!message) return false;
        return message === 'bridge not found'
          || message === 'bridge_id required: no active bridges'
          || message.startsWith('no active bridge for room ');
      }

      function statusSummaryLabels(status, detail, subscribers) {
        const guard = detail && detail.auto_forward_guard ? detail.auto_forward_guard : null;
        const labels = [
          guard && guard.blocked ? t('cards.statusBadgeGuarded') : t('cards.statusBadgeReady'),
          format('cards.statusBadgePending', { count: detail ? detail.pending_count : 0 }),
          subscribers
            ? format('cards.statusBadgeTransport', {
                total: subscribers.total,
                sse: subscribers.sse,
                websocket: subscribers.websocket,
              })
            : t('cards.statusBadgeTransportIdle'),
          status && status.audit && status.audit.enabled ? t('cards.statusBadgeAuditOn') : t('cards.statusBadgeAuditOff'),
        ];
        if (status && status.audit && status.audit.enabled && status.audit.redaction && status.audit.redaction.raw_text_opt_in_blocked) {
          labels.push(t('cards.statusBadgeAuditRawBlocked'));
        }
        if (status && status.audit && status.audit.enabled && status.audit.redaction && status.audit.redaction.stores_raw_text) {
          labels.push(t('cards.statusBadgeAuditRaw'));
        }
        return labels;
      }

      function renderStatusSummary(status) {
        const box = $('status-badges');
        box.innerHTML = '';
        const detail = inferBridgeDetail(status);
        const roomId = $('room-id').value.trim() || (detail && detail.room_id) || '';
        const rooms = Array.isArray(status && status.rooms) ? status.rooms : [];
        const room = rooms.find(item => item && item.id === roomId);
        const subscribers = room && room.subscribers ? room.subscribers : null;
        const labels = statusSummaryLabels(status, detail, subscribers);
        for (const label of labels) {
          const badge = document.createElement('span');
          badge.className = 'badge';
          badge.textContent = label;
          box.appendChild(badge);
        }
      }

      function inferBridgeId(status) {
        const detail = inferBridgeDetail(status);
        if (detail) return detail.bridge_id || '';
        return '';
      }

      function inferBridgeDetail(status) {
        const bridgeId = $('bridge-id').value.trim();
        const roomId = $('room-id').value.trim();
        const details = Array.isArray(status && status.bridge_details) ? status.bridge_details : [];
        if (!details.length) return null;
        if (bridgeId) {
          const exact = details.find(item => item && item.bridge_id === bridgeId);
          if (exact) return exact;
        }
        if (roomId) {
          const matches = details.filter(item => item.room_id === roomId);
          if (matches.length === 1) return matches[0];
          return null;
        }
        if (details.length === 1) return details[0];
        return null;
      }

      async function refreshPending() {
        const args = bridgeArgs();
        if (!args.bridge_id && !args.room_id) {
          fillPending([]);
          return {};
        }
        let res;
        try {
          res = await tool('intervention_list', args);
        } catch (err) {
          if (isInactiveBridgeError(err.message || '')) {
            clearBridgeState();
            syncMetrics();
            return { pending: [], count: 0 };
          }
          throw err;
        }
        if (res.bridge_id) $('bridge-id').value = res.bridge_id;
        fillPending(res.pending || []);
        return res;
      }

      async function refreshStatus() {
        const res = await tool('status', {});
        const detail = inferBridgeDetail(res);
        const inferred = detail ? (detail.bridge_id || '') : '';
        if (!$('bridge-id').value.trim() && inferred) $('bridge-id').value = inferred;
        state.guard = detail && detail.auto_forward_guard ? detail.auto_forward_guard : null;
        state.audit = res.audit || null;
        $('status-box').textContent = JSON.stringify(res, null, 2);
        renderStatusSummary(res);
        renderAudit();
        syncMetrics();
        return res;
      }

      async function refreshAudit() {
        const args = Object.assign({}, bridgeArgs());
        const rawLimit = Number($('audit-limit').value || '12');
        args.limit = Math.max(1, Math.min(50, Number.isFinite(rawLimit) ? rawLimit : 12));
        const event = $('audit-event').value.trim();
        if (event) args.event = event;
        const res = await tool('audit_recent', args);
        state.audit = res.audit || state.audit;
        state.auditEvents = Array.isArray(res.events) ? res.events : [];
        renderAudit();
        syncMetrics();
        return res;
      }

      async function refreshReviewState() {
        await refreshPending();
        await refreshStatus();
        await refreshAudit();
      }

      async function initSession() {
        const res = await tool('terminal_init', Object.assign({
          session: $('session').value.trim() || 'tb2-ai-first'
        }, commonArgs()));
        $('pane-a').value = res.pane_a || '';
        $('pane-b').value = res.pane_b || '';
        syncMetrics();
        log(format('logs.sessionReady', { session: res.session || '' }));
        return res;
      }

      async function startBridge() {
        if (!$('pane-a').value.trim() || !$('pane-b').value.trim()) throw new Error(t('errors.paneTargetsRequired'));
        const args = Object.assign({
          pane_a: $('pane-a').value.trim(),
          pane_b: $('pane-b').value.trim(),
          profile: $('profile').value.trim() || 'generic',
          auto_forward: $('auto-forward').checked,
          intervention: $('intervention').checked
        }, commonArgs());
        if ($('bridge-id').value.trim()) args.bridge_id = $('bridge-id').value.trim();
        if ($('room-id').value.trim()) args.room_id = $('room-id').value.trim();
        const res = await tool('bridge_start', args);
        $('bridge-id').value = res.bridge_id || '';
        $('room-id').value = res.room_id || '';
        state.lastMsgId = 0;
        state.seen = new Set();
        $('stream-box').textContent = '';
        connectTransport();
        await refreshReviewState();
        log(format('logs.bridgeOnline', { bridgeId: res.bridge_id || '' }));
        return res;
      }

      async function stopBridge() {
        const bridgeId = $('bridge-id').value.trim();
        if (!bridgeId) throw new Error(t('errors.bridgeIdRequired'));
        const res = await tool('bridge_stop', { bridge_id: bridgeId });
        stopTransport();
        clearBridgeState();
        await refreshReviewState();
        log(t('logs.bridgeStopped'));
        return res;
      }

      async function sendRoom(deliver) {
        const roomId = $('room-id').value.trim();
        const text = $('send-text').value.trim();
        if (!roomId) throw new Error(t('errors.roomIdRequired'));
        if (!text) throw new Error(t('errors.messageEmpty'));
        const args = { room_id: roomId, author: 'human-operator', text };
        if (deliver) Object.assign(args, bridgeArgs(), { deliver });
        const res = await tool('room_post', args);
        $('send-text').value = '';
        await refreshAudit();
        log(format('logs.roomPosted', {
          target: deliver ? ' ' + (state.locale === 'zh-TW' ? '到 ' : 'to ') + deliver : (state.locale === 'zh-TW' ? '到 room' : ' to room')
        }));
        return res;
      }

      async function capture(targetId, outId) {
        const target = $(targetId).value.trim();
        if (!target) throw new Error(t('errors.targetPaneRequired'));
        const res = await tool('terminal_capture', Object.assign({ target, lines: 160 }, commonArgs()));
        $(outId).value = (res.lines || []).join('\n');
        log(format('logs.captureDone', { target }));
        return res;
      }

      async function interrupt(target) {
        const res = await tool('terminal_interrupt', Object.assign({ target }, bridgeArgs()));
        await refreshAudit();
        log(format('logs.interruptSent', { target }));
        return res;
      }

      async function approveSelected() {
        const id = $('pending-select').value;
        if (!id) throw new Error(t('errors.selectPendingFirst'));
        const args = Object.assign({ id: Number(id) }, bridgeArgs());
        const edited = $('pending-edit').value.trim();
        if (edited) args.edited_text = edited;
        const res = await tool('intervention_approve', args);
        if (res.bridge_id) $('bridge-id').value = res.bridge_id;
        await refreshReviewState();
        log(t('logs.approved'));
        return res;
      }

      async function rejectSelected() {
        const id = $('pending-select').value;
        if (!id) throw new Error(t('errors.selectPendingFirst'));
        const res = await tool('intervention_reject', Object.assign({ id: Number(id) }, bridgeArgs()));
        if (res.bridge_id) $('bridge-id').value = res.bridge_id;
        await refreshReviewState();
        log(t('logs.rejected'));
        return res;
      }

      async function run(fn) {
        try {
          return await fn();
        } catch (err) {
          log(format('errors.errorPrefix', { message: err.message }));
          throw err;
        }
      }

      function bind() {
        document.querySelectorAll('[data-preset]').forEach(button => {
          button.addEventListener('click', () => applyPreset(button.dataset.preset));
        });
        document.querySelectorAll('[data-lang]').forEach(button => {
          button.addEventListener('click', () => {
            if (button.dataset.lang === state.locale) return;
            applyLocale(button.dataset.lang);
            log(format('logs.languageChanged', {
              language: t('languages.' + state.locale)
            }));
          });
        });
        document.querySelectorAll('[data-layout-mode]').forEach(button => {
          button.addEventListener('click', () => {
            if (button.dataset.layoutMode === state.layout) return;
            applyLayout(button.dataset.layoutMode);
            log(format('logs.layoutChanged', {
              layout: t('layouts.' + state.layout)
            }));
          });
        });
        $('init-session').onclick = () => run(initSession);
        $('start-bridge').onclick = () => run(startBridge);
        $('stop-bridge').onclick = () => run(stopBridge);
        $('refresh-status').onclick = () => run(refreshStatus);
        $('refresh-pending').onclick = () => run(refreshPending);
        $('refresh-audit').onclick = () => run(refreshAudit);
        $('audit-event').onchange = () => run(refreshAudit);
        $('audit-limit').onchange = () => run(refreshAudit);
        $('send-host').onclick = () => run(() => sendRoom('a'));
        $('send-guest').onclick = () => run(() => sendRoom('b'));
        $('send-room').onclick = () => run(() => sendRoom($('deliver').value || ''));
        $('capture-host').onclick = () => run(() => capture('pane-a', 'capture-a-box'));
        $('capture-guest').onclick = () => run(() => capture('pane-b', 'capture-b-box'));
        $('interrupt-host').onclick = () => run(() => interrupt('a'));
        $('interrupt-guest').onclick = () => run(() => interrupt('b'));
        $('interrupt-both').onclick = () => run(() => interrupt('both'));
        $('approve-selected').onclick = () => run(approveSelected);
        $('reject-selected').onclick = () => run(rejectSelected);
        $('approve-all').onclick = () => run(() => tool('intervention_approve', Object.assign({
          id: 'all'
        }, bridgeArgs())).then(() => refreshReviewState()));
        $('reject-all').onclick = () => run(() => tool('intervention_reject', Object.assign({
          id: 'all'
        }, bridgeArgs())).then(() => refreshReviewState()));
        $('transport').onchange = () => {
          syncMetrics();
          connectTransport();
        };
        $('pending-select').onchange = () => renderPendingDetail();
      }

      async function boot() {
        state.locale = preferredLocale();
        state.layout = preferredLayout();
        bind();
        translatePage();
        applyLayout(state.layout);
        document.body.dataset.home = 'preset-only';
        log(format('logs.ready', { endpoint: MCP_ENDPOINT }));
        await run(async () => {
          const profiles = await tool('list_profiles', {});
          if (!profiles || !Array.isArray(profiles.profiles)) return;
          const select = $('profile');
          const known = new Set(Array.from(select.options).map(option => option.value));
          for (const profile of profiles.profiles) {
            if (known.has(profile)) continue;
            const option = document.createElement('option');
            option.value = profile;
            option.textContent = profile;
            select.appendChild(option);
          }
        });
        await run(refreshPending);
        await run(refreshStatus);
        await run(refreshAudit);
      }

      boot();
    </script>
  </body>
</html>
"""


def _backend_options() -> str:
    default = default_backend_name()
    options = []
    for name in ("process", "tmux", "pipe"):
        selected = " selected" if name == default else ""
        options.append(f'<option value="{name}"{selected}>{name}</option>')
    return "".join(options)


def _audit_event_options() -> str:
    options = []
    for event in AUDIT_EVENT_CATALOG:
        options.append(f'<option value="{event}">{event}</option>')
    return "".join(options)


def build_gui_html(mcp_endpoint: str = "/mcp") -> str:
    return (
        GUI_HTML_TEMPLATE
        .replace("__MCP_ENDPOINT__", mcp_endpoint)
        .replace("__BACKEND_OPTIONS__", _backend_options())
        .replace("__AUDIT_EVENT_OPTIONS__", _audit_event_options())
    )
