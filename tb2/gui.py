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
      body[data-home="preset-only"] .workspace-nav,
      body[data-home="preset-only"] .workspace-panels,
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

      .workspace-nav {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        align-items: center;
      }

      .workspace-tab {
        display: grid;
        gap: 2px;
        align-content: center;
        justify-items: start;
        appearance: none;
        border: 1px solid var(--line);
        background: rgba(255, 255, 255, 0.72);
        color: var(--muted);
        border-radius: 10px;
        min-height: 40px;
        min-width: 136px;
        padding: 8px 14px 9px;
        font: inherit;
        font-size: 0.8rem;
        font-weight: 600;
        letter-spacing: 0.03em;
        cursor: pointer;
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.46);
      }

      .workspace-tab.active {
        border-color: var(--accent);
        background: rgba(47, 75, 92, 0.1);
        color: var(--ink);
        box-shadow: 0 0 0 1px rgba(47, 75, 92, 0.08), var(--shadow-soft), inset 0 1px 0 rgba(255, 255, 255, 0.52);
      }

      .workspace-tab-label {
        color: var(--ink);
        font-size: 0.8rem;
        font-weight: 700;
        letter-spacing: 0.03em;
      }

      .workspace-tab-meta {
        color: var(--muted);
        font-size: 0.68rem;
        font-weight: 600;
        letter-spacing: 0.02em;
        text-transform: none;
      }

      .workspace-tab.active .workspace-tab-meta {
        color: var(--accent);
      }

      .workspace-strip {
        display: grid;
        grid-template-columns: repeat(6, minmax(0, 1fr));
        gap: 10px;
      }

      .workspace-chip {
        display: grid;
        gap: 4px;
        min-height: 72px;
        padding: 11px 12px;
        border-radius: 12px;
        border: 1px solid rgba(217, 204, 184, 0.78);
        background: rgba(255, 255, 255, 0.76);
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.52);
      }

      .workspace-chip strong {
        color: var(--muted);
        font-size: 0.67rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
      }

      .workspace-chip span {
        color: var(--ink);
        font-size: 0.84rem;
        line-height: 1.28;
      }

      .workspace-chip small {
        color: var(--muted);
        font-size: 0.72rem;
        line-height: 1.35;
      }

      .workspace-chip.is-attention {
        border-color: rgba(108, 77, 72, 0.36);
        background: linear-gradient(180deg, rgba(255, 249, 246, 0.96), rgba(247, 240, 236, 0.94));
      }

      .workspace-chip.is-active {
        border-color: rgba(47, 75, 92, 0.22);
      }

      .workspace-chip.is-muted {
        opacity: 0.6;
      }

      .workspace-panels {
        display: grid;
        gap: 12px;
      }

      .workspace-panel {
        display: none;
        gap: 12px;
      }

      .workspace-panel.is-active {
        display: grid;
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

      .focus-target {
        box-shadow: 0 0 0 2px rgba(47, 75, 92, 0.22), var(--shadow-soft), inset 0 1px 0 rgba(255, 255, 255, 0.42);
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

      .card--relation {
        --card-accent: var(--accent-strong);
      }

      .relation-shell {
        display: grid;
        grid-template-columns: minmax(0, 1.5fr) minmax(300px, 0.9fr);
        gap: 16px;
        align-items: start;
      }

      .relation-stage,
      .relation-sidebar {
        display: grid;
        gap: 12px;
      }

      .relation-stage-head {
        display: grid;
        gap: 10px;
      }

      .relation-stage-note {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        justify-content: space-between;
        gap: 8px 12px;
        padding: 10px 12px;
        border-radius: 12px;
        border: 1px dashed rgba(217, 204, 184, 0.9);
        background: rgba(255, 255, 255, 0.7);
        color: var(--muted);
        font-size: 0.76rem;
        line-height: 1.4;
      }

      .relation-stage-note strong {
        color: var(--ink);
        font-size: 0.75rem;
        letter-spacing: 0.04em;
        text-transform: uppercase;
      }

      .relation-badges {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }

      .relation-badges .badge {
        background: rgba(255, 255, 255, 0.82);
      }

      .relation-badges .badge.is-active {
        border-color: rgba(47, 75, 92, 0.26);
      }

      .relation-badges .badge.is-standby {
        border-style: dashed;
        opacity: 0.86;
      }

      .relation-badges .badge.is-muted {
        opacity: 0.56;
      }

      .relation-badges .badge.is-attention {
        border-color: rgba(108, 77, 72, 0.36);
      }

      .relation-badges .badge.is-selected {
        box-shadow: 0 0 0 2px rgba(47, 75, 92, 0.16);
      }

      .relation-scroller {
        overflow-x: auto;
        padding-bottom: 2px;
      }

      .relation-diagram {
        position: relative;
        min-width: 930px;
        min-height: 456px;
        border-radius: 18px;
        border: 1px solid color-mix(in oklab, var(--line) 74%, white);
        background:
          radial-gradient(circle at top left, rgba(47, 75, 92, 0.12), transparent 26%),
          radial-gradient(circle at bottom right, rgba(116, 100, 86, 0.12), transparent 22%),
          linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(247, 241, 233, 0.98));
        overflow: hidden;
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.62), var(--shadow-soft);
      }

      .relation-diagram::before {
        content: "";
        position: absolute;
        inset: 0;
        pointer-events: none;
        background-image:
          linear-gradient(rgba(217, 204, 184, 0.14) 1px, transparent 1px),
          linear-gradient(90deg, rgba(217, 204, 184, 0.14) 1px, transparent 1px);
        background-size: 32px 32px;
        mask-image: linear-gradient(180deg, rgba(0, 0, 0, 0.55), transparent 100%);
      }

      .relation-lanes {
        position: absolute;
        inset: 12px;
        pointer-events: none;
      }

      .relation-lane {
        position: absolute;
        top: 10px;
        bottom: 10px;
        border-radius: 18px;
        border: 1px solid rgba(217, 204, 184, 0.46);
        background: linear-gradient(180deg, rgba(255, 255, 255, 0.5), rgba(255, 255, 255, 0.14));
      }

      .relation-lane span {
        position: absolute;
        top: 14px;
        left: 18px;
        display: inline-flex;
        align-items: center;
        min-height: 28px;
        padding: 4px 10px;
        border-radius: 999px;
        border: 1px solid rgba(217, 204, 184, 0.72);
        background: rgba(255, 255, 255, 0.84);
        color: var(--muted);
        font-size: 0.7rem;
        font-weight: 600;
        letter-spacing: 0.08em;
        text-transform: uppercase;
      }

      .relation-lane--operator {
        left: 14px;
        width: 26%;
      }

      .relation-lane--control {
        left: 37%;
        width: 26%;
      }

      .relation-lane--execution {
        right: 14px;
        width: 26%;
      }

      .relation-lines {
        position: absolute;
        inset: 0;
        z-index: 1;
        width: 100%;
        height: 100%;
        pointer-events: none;
      }

      .relation-link {
        fill: none;
        stroke: rgba(47, 75, 92, 0.62);
        stroke-width: 2.6;
        stroke-linecap: round;
      }

      .relation-link.is-active {
        filter: drop-shadow(0 0 8px rgba(47, 75, 92, 0.1));
      }

      .relation-link.is-standby {
        stroke-dasharray: 8 7;
        opacity: 0.68;
      }

      .relation-link.is-muted {
        stroke-dasharray: 4 8;
        opacity: 0.28;
      }

      .relation-link.is-attention {
        stroke: rgba(108, 77, 72, 0.86);
      }

      .relation-pin {
        fill: rgba(255, 255, 255, 0.94);
        stroke: rgba(47, 75, 92, 0.46);
        stroke-width: 1.4;
      }

      .relation-pin.is-attention {
        stroke: rgba(108, 77, 72, 0.74);
      }

      .relation-link-badge rect {
        fill: rgba(255, 255, 255, 0.985);
        stroke: rgba(217, 204, 184, 0.78);
        stroke-width: 1;
        rx: 999px;
        ry: 999px;
      }

      .relation-link-badge text {
        fill: var(--muted);
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.01em;
      }

      .relation-link-badge.is-active rect {
        stroke: rgba(47, 75, 92, 0.22);
      }

      .relation-link-badge.is-standby rect {
        stroke-dasharray: 4 4;
        opacity: 0.9;
      }

      .relation-link-badge.is-muted {
        opacity: 0.46;
      }

      .relation-link-badge.is-attention rect {
        stroke: rgba(108, 77, 72, 0.28);
      }

      .relation-link-group {
        pointer-events: none;
      }

      .relation-link-group.is-selected .relation-link {
        stroke-width: 3.4;
        filter: drop-shadow(0 0 10px rgba(47, 75, 92, 0.16));
      }

      .relation-link-group.is-selected .relation-link-badge rect {
        stroke-width: 1.4;
        stroke: rgba(47, 75, 92, 0.34);
      }

      .relation-node {
        position: absolute;
        z-index: 2;
        width: 180px;
        min-height: 118px;
        padding: 12px 14px;
        border: 1px solid color-mix(in oklab, var(--line) 76%, white);
        border-radius: 18px;
        background: linear-gradient(180deg, rgba(255, 255, 255, 0.99), rgba(248, 243, 235, 0.985));
        box-shadow: var(--shadow-soft), inset 0 1px 0 rgba(255, 255, 255, 0.68);
        transform: translate(-50%, -50%);
        display: grid;
        gap: 6px;
        cursor: pointer;
      }

      .relation-node-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
      }

      .relation-node-state {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        min-width: 0;
      }

      .status-led {
        position: relative;
        display: inline-flex;
        width: 12px;
        height: 12px;
        flex: 0 0 auto;
        border-radius: 999px;
        border: 1px solid rgba(47, 75, 92, 0.2);
        background: rgba(125, 97, 88, 0.5);
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.5);
      }

      .status-led::after {
        content: "";
        position: absolute;
        inset: 1.5px;
        border-radius: inherit;
        background: radial-gradient(circle at 35% 35%, rgba(255, 255, 255, 0.72), rgba(255, 255, 255, 0.06) 68%);
      }

      .status-led.is-ok {
        background: linear-gradient(180deg, rgba(124, 214, 146, 0.98), rgba(54, 164, 87, 0.98));
        box-shadow: 0 0 0 1px rgba(90, 195, 120, 0.18), 0 0 16px rgba(108, 212, 138, 0.34);
      }

      .status-led.is-warn {
        background: linear-gradient(180deg, rgba(252, 219, 112, 0.98), rgba(214, 160, 36, 0.98));
        box-shadow: 0 0 0 1px rgba(237, 194, 82, 0.18), 0 0 16px rgba(245, 206, 96, 0.3);
      }

      .status-led.is-down {
        background: linear-gradient(180deg, rgba(241, 138, 138, 0.98), rgba(186, 62, 62, 0.98));
        box-shadow: 0 0 0 1px rgba(219, 102, 102, 0.18), 0 0 16px rgba(232, 120, 120, 0.3);
      }

      .relation-node::before {
        content: "";
        position: absolute;
        inset: 0 auto 0 0;
        width: 4px;
        border-radius: 18px 0 0 18px;
        background: rgba(47, 75, 92, 0.22);
      }

      .relation-node.is-active {
        box-shadow: 0 0 0 1px rgba(47, 75, 92, 0.14), var(--shadow-soft), inset 0 1px 0 rgba(255, 255, 255, 0.7);
      }

      .relation-node.is-active::before {
        background: var(--accent);
      }

      .relation-node.is-standby {
        opacity: 0.8;
      }

      .relation-node.is-standby::before {
        background: rgba(116, 100, 86, 0.44);
      }

      .relation-node.is-muted {
        opacity: 0.46;
        filter: saturate(0.78);
      }

      .relation-node.is-attention {
        border-color: rgba(108, 77, 72, 0.7);
        box-shadow: 0 0 0 1px rgba(108, 77, 72, 0.14), var(--shadow-soft), inset 0 1px 0 rgba(255, 255, 255, 0.62);
      }

      .relation-node.is-attention::before {
        background: var(--danger);
      }

      .relation-node-tag {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: fit-content;
        min-height: 24px;
        padding: 3px 8px;
        border-radius: 999px;
        border: 1px solid rgba(217, 204, 184, 0.78);
        background: rgba(255, 255, 255, 0.84);
        color: var(--accent);
        font-size: 0.62rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
      }

      .relation-node strong {
        color: var(--ink);
        font-size: 0.88rem;
        line-height: 1.18;
      }

      .relation-node span {
        color: var(--muted);
        font-size: 0.74rem;
        line-height: 1.32;
      }

      .relation-node code {
        display: inline-flex;
        align-items: center;
        min-height: 28px;
        padding: 5px 8px;
        border-radius: 10px;
        background: rgba(240, 236, 228, 0.92);
        color: var(--accent-strong);
        font-size: 0.68rem;
        font-family: "IBM Plex Mono", "Consolas", monospace;
        word-break: break-word;
      }

      .relation-node-actions {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin-top: 2px;
      }

      .relation-node-action {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        min-height: 28px;
        padding: 4px 9px;
        border-radius: 999px;
        border: 1px solid rgba(217, 204, 184, 0.84);
        background: rgba(255, 255, 255, 0.96);
        color: var(--accent-strong);
        font-size: 0.67rem;
        font-weight: 700;
        letter-spacing: 0.03em;
      }

      .relation-node-action strong {
        font-size: 0.64rem;
        line-height: 1;
        color: var(--muted);
      }

      .relation-node-action em {
        font-style: normal;
        color: var(--accent-strong);
      }

      .relation-node-action.is-on {
        border-color: rgba(47, 75, 92, 0.24);
      }

      .relation-node-action.is-off {
        border-style: dashed;
      }

      .relation-node:focus-visible {
        outline: 2px solid rgba(47, 75, 92, 0.32);
        outline-offset: 3px;
      }

      .relation-node.is-selected {
        box-shadow: 0 0 0 2px rgba(47, 75, 92, 0.2), var(--shadow-soft), inset 0 1px 0 rgba(255, 255, 255, 0.7);
      }

      .relation-sidebar {
        align-content: start;
      }

      .relation-panel {
        display: grid;
        gap: 10px;
        padding: 14px;
        border-radius: 14px;
        border: 1px solid rgba(217, 204, 184, 0.8);
        background: rgba(255, 255, 255, 0.76);
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.48);
      }

      .relation-panel-head {
        display: grid;
        gap: 3px;
      }

      .relation-panel-head strong {
        color: var(--ink);
        font-size: 0.82rem;
        letter-spacing: 0.03em;
        text-transform: uppercase;
      }

      .relation-panel-head span {
        color: var(--muted);
        font-size: 0.76rem;
        line-height: 1.4;
      }

      .relation-controls {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 10px;
        align-items: end;
      }

      .relation-checks {
        display: grid;
        gap: 10px;
        padding: 10px 12px;
        border-radius: 12px;
        border: 1px solid rgba(217, 204, 184, 0.7);
        background: rgba(250, 246, 240, 0.84);
      }

      .relation-checks label {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        margin: 0;
        color: var(--muted);
        font-size: 0.78rem;
        letter-spacing: 0;
        text-transform: none;
      }

      .relation-checks input {
        width: auto;
        margin: 0;
      }

      .relation-note {
        margin: 0;
      }

      .runtime-compare {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 10px;
      }

      .runtime-card {
        display: grid;
        gap: 9px;
        padding: 12px;
        border-radius: 12px;
        border: 1px solid rgba(217, 204, 184, 0.78);
        background: rgba(255, 255, 255, 0.88);
      }

      .runtime-card-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
      }

      .runtime-card.is-active {
        border-color: rgba(47, 75, 92, 0.24);
      }

      .runtime-card.is-attention {
        border-color: rgba(108, 77, 72, 0.36);
        background: linear-gradient(180deg, rgba(255, 249, 246, 0.96), rgba(247, 239, 234, 0.94));
      }

      .runtime-card strong {
        color: var(--ink);
        font-size: 0.76rem;
        letter-spacing: 0.06em;
        text-transform: uppercase;
      }

      .runtime-card span {
        color: var(--muted);
        font-size: 0.74rem;
        line-height: 1.38;
      }

      .runtime-list {
        display: grid;
        gap: 6px;
      }

      .runtime-list b {
        color: var(--muted);
        font-size: 0.65rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
      }

      .runtime-list em {
        color: var(--ink);
        font-style: normal;
        font-size: 0.8rem;
        line-height: 1.3;
      }

      .runtime-drift {
        display: inline-flex;
        align-items: center;
        width: fit-content;
        min-height: 24px;
        padding: 3px 8px;
        border-radius: 999px;
        border: 1px solid rgba(108, 77, 72, 0.28);
        background: rgba(255, 247, 244, 0.94);
        color: var(--danger);
        font-size: 0.68rem;
        font-weight: 700;
        letter-spacing: 0.04em;
      }

      .relation-spotlight {
        display: grid;
        gap: 10px;
        padding: 14px;
        border-radius: 14px;
        border: 1px solid rgba(217, 204, 184, 0.8);
        background: rgba(255, 255, 255, 0.8);
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.48);
      }

      .relation-spotlight-head {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        justify-content: space-between;
        gap: 8px 12px;
      }

      .relation-spotlight-head strong {
        color: var(--ink);
        font-size: 0.82rem;
        letter-spacing: 0.03em;
        text-transform: uppercase;
      }

      .relation-spotlight-head span {
        color: var(--muted);
        font-size: 0.74rem;
        line-height: 1.35;
      }

      .relation-spotlight-code {
        display: inline-flex;
        align-items: center;
        min-height: 28px;
        padding: 5px 8px;
        border-radius: 10px;
        background: rgba(240, 236, 228, 0.92);
        color: var(--accent-strong);
        font-size: 0.68rem;
        font-family: "IBM Plex Mono", "Consolas", monospace;
        word-break: break-word;
      }

      .relation-spotlight-copy {
        color: var(--muted);
        font-size: 0.76rem;
        line-height: 1.45;
      }

      .relation-spotlight-facts {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 9px;
      }

      .relation-spotlight-fact {
        display: grid;
        gap: 4px;
        min-height: 66px;
        padding: 10px 12px;
        border-radius: 12px;
        border: 1px solid rgba(217, 204, 184, 0.72);
        background: rgba(255, 255, 255, 0.88);
      }

      .relation-spotlight-fact strong {
        color: var(--muted);
        font-size: 0.66rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
      }

      .relation-spotlight-fact span {
        color: var(--ink);
        font-size: 0.8rem;
        line-height: 1.3;
      }

      .relation-facts {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 9px;
      }

      .relation-fact {
        display: grid;
        gap: 4px;
        min-height: 72px;
        padding: 10px 12px;
        border-radius: 12px;
        border: 1px solid rgba(217, 204, 184, 0.78);
        background: rgba(255, 255, 255, 0.84);
        color: var(--muted);
        font-size: 0.74rem;
      }

      .relation-fact strong {
        color: var(--muted);
        font-size: 0.68rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
      }

      .relation-fact span {
        color: var(--ink);
        font-size: 0.82rem;
        line-height: 1.28;
      }

      .relation-ledger {
        display: grid;
        gap: 8px;
      }

      .relation-link-item {
        display: grid;
        gap: 4px;
        padding: 10px 12px;
        border-radius: 12px;
        border: 1px solid rgba(217, 204, 184, 0.72);
        background: rgba(255, 255, 255, 0.84);
      }

      .relation-link-item strong {
        color: var(--ink);
        font-size: 0.78rem;
        line-height: 1.24;
      }

      .relation-link-item span {
        color: var(--muted);
        font-size: 0.74rem;
        line-height: 1.35;
      }

      .relation-link-item.is-active {
        border-color: rgba(47, 75, 92, 0.28);
      }

      .relation-link-item.is-attention {
        border-color: rgba(108, 77, 72, 0.34);
      }

      .relation-link-item.is-muted {
        opacity: 0.54;
      }

      .relation-link-item.is-selected {
        box-shadow: 0 0 0 2px rgba(47, 75, 92, 0.16);
      }

      .queue-guide {
        display: grid;
        gap: 8px;
        margin-bottom: 10px;
        padding: 12px;
        border-radius: 12px;
        border: 1px solid rgba(217, 204, 184, 0.82);
        background: rgba(255, 255, 255, 0.74);
      }

      .queue-guide strong {
        color: var(--ink);
        font-size: 0.76rem;
        letter-spacing: 0.05em;
        text-transform: uppercase;
      }

      .queue-guide ul {
        margin: 0;
        padding-left: 18px;
        color: var(--muted);
        font-size: 0.76rem;
        line-height: 1.45;
      }

      .summary-strip {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 10px;
      }

      .summary-tile {
        display: grid;
        gap: 4px;
        min-height: 72px;
        padding: 11px 12px;
        border-radius: 12px;
        border: 1px solid rgba(217, 204, 184, 0.78);
        background: rgba(255, 255, 255, 0.8);
      }

      .summary-tile strong {
        color: var(--muted);
        font-size: 0.66rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
      }

      .summary-tile span {
        color: var(--ink);
        font-size: 0.84rem;
        line-height: 1.28;
      }

      .summary-tile small {
        color: var(--muted);
        font-size: 0.72rem;
        line-height: 1.35;
      }

      .summary-tile.is-attention {
        border-color: rgba(108, 77, 72, 0.34);
        background: linear-gradient(180deg, rgba(255, 249, 246, 0.96), rgba(247, 239, 234, 0.94));
      }

      .summary-tile.is-active {
        border-color: rgba(47, 75, 92, 0.24);
      }

      .summary-tile.is-muted {
        opacity: 0.62;
      }

      .decision-note {
        margin: 0;
      }

      .inspect-guide {
        display: grid;
        gap: 8px;
        margin-bottom: 10px;
        padding: 12px;
        border-radius: 12px;
        border: 1px solid rgba(217, 204, 184, 0.82);
        background: rgba(255, 255, 255, 0.74);
      }

      .inspect-guide strong {
        color: var(--ink);
        font-size: 0.76rem;
        letter-spacing: 0.05em;
        text-transform: uppercase;
      }

      .inspect-guide p {
        margin: 0;
        color: var(--muted);
        font-size: 0.76rem;
        line-height: 1.45;
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

      .fleet-sidebar {
        display: flex;
        flex-direction: column;
        gap: 12px;
      }

      .workstream-panel {
        display: flex;
        flex-direction: column;
        gap: 16px;
      }

      [data-tooltip] {
        position: relative;
        cursor: help;
        border-bottom: 1px dashed var(--muted);
      }

      [data-tooltip]::after {
        content: attr(data-tooltip);
        position: absolute;
        bottom: calc(100% + 10px);
        left: 50%;
        transform: translateX(-50%) translateY(4px);
        background: rgba(34, 55, 68, 0.95);
        color: #fff;
        padding: 8px 12px;
        border-radius: 8px;
        font-size: 0.76rem;
        line-height: 1.4;
        width: 260px;
        text-align: left;
        pointer-events: none;
        opacity: 0;
        visibility: hidden;
        transition: opacity 0.2s ease, transform 0.2s ease;
        z-index: 100;
        box-shadow: 0 8px 24px rgba(0,0,0,0.15);
        backdrop-filter: blur(4px);
        font-weight: 400;
      }

      [data-tooltip]:hover::after {
        opacity: 1;
        visibility: visible;
        transform: translateX(-50%) translateY(0);
      }

      details.disclosure summary {
        padding: 10px 14px;
        background: rgba(255, 255, 255, 0.4);
        border: 1px solid rgba(217, 204, 184, 0.4);
        border-radius: 8px;
        transition: background 0.2s ease;
      }

      details.disclosure summary:hover {
        background: rgba(255, 255, 255, 0.7);
      }

      @media (max-width: 1120px) {
        .layout {
          grid-template-columns: 1fr;
        }

        .workspace-strip {
          grid-template-columns: repeat(3, minmax(0, 1fr));
        }

        .status-grid {
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }

        .relation-shell {
          grid-template-columns: 1fr;
        }
      }

      @media (max-width: 820px) {
        .workspace-nav {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }

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

        .relation-controls,
        .relation-facts,
        .runtime-compare,
        .summary-strip {
          grid-template-columns: 1fr;
        }

        .relation-diagram {
          min-width: 760px;
        }
      }

      @media (max-width: 640px) {
        .workspace-strip {
          grid-template-columns: 1fr;
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
        <!-- Fleet Sidebar (1+n architecture) -->
        <aside class="fleet-sidebar card">
          <div class="card-head" style="margin-bottom: 4px; padding-bottom: 4px; border-bottom: none;">
            <p class="card-kicker" data-i18n="fleet.title">Workstream Fleet</p>
            <h2 data-i18n="fleet.overview">Overview</h2>
          </div>
          <p class="subtle" style="margin-bottom: 12px; margin-top: -6px;" data-i18n="fleet.hint">Select a workstream to manage.</p>
          <div class="subtle" id="fleet-summary-meta" style="margin-bottom: 12px;">0 workstreams</div>
          <div class="preset-grid" id="workstream-list" style="grid-template-columns: 1fr; margin-top: 0; gap: 8px;"></div>
        </aside>

        <div class="workstream-panel">
          <section class="workspace-nav" id="workspace-nav" aria-label="Workspace Tabs">
            <button class="workspace-tab active" data-workspace-tab="workflow" type="button">
              <span class="workspace-tab-label">Workflow</span>
              <span class="workspace-tab-meta" id="workspace-meta-workflow">launch + live</span>
            </button>
            <button class="workspace-tab" data-workspace-tab="topology" type="button">
              <span class="workspace-tab-label">Topology</span>
              <span class="workspace-tab-meta" id="workspace-meta-topology">live graph</span>
            </button>
            <button class="workspace-tab" data-workspace-tab="review" type="button">
              <span class="workspace-tab-label">Review</span>
              <span class="workspace-tab-meta" id="workspace-meta-review">queue idle</span>
            </button>
            <button class="workspace-tab" data-workspace-tab="inspect" type="button">
              <span class="workspace-tab-label">Inspect</span>
              <span class="workspace-tab-meta" id="workspace-meta-inspect">status + diagnostics</span>
            </button>
          </section>

          <section class="workspace-strip" id="workspace-strip"></section>

          <section class="workspace-panels">
        <section class="workspace-panel is-active" data-workspace-panel="workflow">
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
                <label for="backend" data-i18n="fields.backend" data-tooltip="決定 AI 代理程式要在哪種環境下被喚醒執行。例如獨立進程 (process) 或是常駐在背景終端 (tmux) 中。">backend</label>
                <select id="backend">__BACKEND_OPTIONS__</select>
              </div>
              <div>
                <label for="profile" data-i18n="fields.profile" data-tooltip="決定這次連線要套用哪一種特性或預設系統提示策略 (System Prompt)，像是套用特定角色或行為限制。">profile</label>
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

            <details id="launch-advanced">
              <summary data-i18n="actions.advanced">Advanced IDs, pane mapping, and transport</summary>
              <div class="row" style="margin-top: 12px;">
                <div>
                  <label for="backend-id" data-i18n="fields.backendId">backend_id</label>
                  <input id="backend-id" value="default">
                </div>
                <div>
                  <label for="transport" data-i18n="fields.transport" data-tooltip="網頁介面即時接收對話與資料流的通道協議。SSE 耗能低適合單向接收，WebSocket 適合高頻的雙向控制。">live room transport</label>
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
        </section>

        <section class="workspace-panel" data-workspace-panel="topology">
          <section class="layout-secondary">
            <article class="card card--relation" id="relation-card">
          <details class="disclosure" id="relation-details">
            <summary class="disclosure-summary">
              <div class="summary-stack">
                <span class="card-kicker" data-i18n="flow.relation">Support · Relation View</span>
                <h2 data-i18n="cards.relationTitle">Relation View</h2>
              </div>
              <span class="disclosure-meta" id="relation-summary-meta">topology</span>
            </summary>
            <div class="disclosure-body">
              <p class="disclosure-copy" data-i18n="cards.relationCopy">See which components are live for the current preset, how they connect, and adjust the routing controls without leaving the console.</p>
              <div class="relation-shell">
                <div class="relation-stage">
                  <div class="relation-stage-head">
                    <div class="relation-badges" id="relation-badges"></div>
                    <div class="relation-stage-note">
                      <strong data-i18n="cards.relationHintTitle">Topology Actions</strong>
                      <span data-i18n="cards.relationHint">Click any node to jump to the matching control area. The left card is the launch plan; the right card reflects the live runtime contract.</span>
                    </div>
                  </div>
                  <div class="relation-scroller">
                    <div class="relation-diagram" id="relation-diagram">
                      <div class="relation-lanes">
                        <div class="relation-lane relation-lane--operator"><span data-i18n="relationLanes.operator">Operator Surface</span></div>
                        <div class="relation-lane relation-lane--control"><span data-i18n="relationLanes.control">Control Plane</span></div>
                        <div class="relation-lane relation-lane--execution"><span data-i18n="relationLanes.execution">Execution Plane</span></div>
                      </div>
                      <svg class="relation-lines" id="relation-lines" viewBox="0 0 980 428" preserveAspectRatio="xMidYMid meet"></svg>
                    </div>
                  </div>
                </div>
                <div class="relation-sidebar">
                  <section class="relation-panel">
                    <div class="relation-panel-head">
                      <strong data-i18n="cards.relationConfigTitle">Launch Mirror</strong>
                      <span data-i18n="cards.relationConfigCopy">Edit the same launch settings used by the main console without leaving the topology view.</span>
                    </div>
                    <div class="relation-controls">
                      <div>
                        <label for="relation-backend" data-i18n="fields.backend">backend</label>
                        <select id="relation-backend">__BACKEND_OPTIONS__</select>
                      </div>
                      <div>
                        <label for="relation-profile" data-i18n="fields.profile">profile</label>
                        <select id="relation-profile">
                          <option value="generic">generic</option>
                          <option value="codex">codex</option>
                          <option value="claude-code">claude-code</option>
                          <option value="gemini">gemini</option>
                          <option value="aider">aider</option>
                          <option value="llama">llama</option>
                        </select>
                      </div>
                      <div>
                        <label for="relation-transport" data-i18n="fields.transport">live room transport</label>
                        <select id="relation-transport">
                          <option value="sse" data-i18n="transport.sse">SSE</option>
                          <option value="ws" data-i18n="transport.ws">WebSocket</option>
                          <option value="poll" data-i18n="transport.poll">room_poll</option>
                        </select>
                      </div>
                      <div>
                        <label for="relation-deliver" data-i18n="fields.deliver">human delivery target</label>
                        <select id="relation-deliver">
                          <option value="" data-i18n="deliver.roomOnly">room only</option>
                          <option value="a" data-i18n="deliver.host">Host pane</option>
                          <option value="b" data-i18n="deliver.guest">Guest pane</option>
                          <option value="both" data-i18n="deliver.both">Both panes</option>
                        </select>
                      </div>
                    </div>
                    <div class="relation-checks">
                      <label><input id="relation-auto-forward" type="checkbox"><span data-i18n="fields.autoForward">auto-forward Guest `MSG:` handoffs</span></label>
                      <label><input id="relation-intervention" type="checkbox"><span data-i18n="fields.intervention">require human approval before forwarding</span></label>
                      <button id="relation-refresh" class="ghost" type="button" data-i18n="actions.refreshStatus">Refresh Status</button>
                    </div>
                    <div class="note note--quiet relation-note" id="relation-note" data-i18n="cards.relationNote">
                      Quick edits update launch settings immediately. Restart the active bridge if you need profile or approval changes to take effect on a running loop.
                    </div>
                    <section class="relation-spotlight" id="relation-spotlight">
                      <div class="relation-spotlight-head">
                        <strong id="relation-spotlight-title" data-i18n="cards.relationSpotlightTitle">Topology Spotlight</strong>
                        <span id="relation-spotlight-state">active</span>
                      </div>
                      <div class="relation-spotlight-code hidden" id="relation-spotlight-code"></div>
                      <div class="relation-spotlight-copy" id="relation-spotlight-copy" data-i18n="cards.relationSpotlightCopy">Select a node or connection to inspect the current state, why it matters, and where to jump next.</div>
                      <div class="relation-spotlight-facts" id="relation-spotlight-facts"></div>
                      <div class="actions">
                        <button id="relation-spotlight-jump" class="ghost" type="button" data-i18n="actions.jumpToFocus">Jump to Matched Control</button>
                      </div>
                    </section>
                    <div class="runtime-compare" id="relation-compare"></div>
                  </section>
                  <section class="relation-panel">
                    <div class="relation-panel-head">
                      <strong data-i18n="cards.relationFactsTitle">Live Runtime</strong>
                      <span data-i18n="cards.relationFactsCopy">The view stays aligned with live room, bridge, audit, and runtime state rather than decorative placeholder data.</span>
                    </div>
                    <div class="relation-facts" id="relation-facts"></div>
                  </section>
                  <section class="relation-panel">
                    <div class="relation-panel-head">
                      <strong data-i18n="cards.relationLedgerTitle">Connection Ledger</strong>
                      <span data-i18n="cards.relationLedgerCopy">Each line below describes the exact route or dependency currently shown in the diagram.</span>
                    </div>
                    <div class="relation-ledger" id="relation-ledger"></div>
                  </section>
                </div>
              </div>
            </div>
          </details>
            </article>
          </section>
        </section>

        <section class="workspace-panel" data-workspace-panel="review">
          <section class="layout-secondary">
            <article class="card card--review" id="pending-card">
          <details class="disclosure" id="pending-details">
            <summary class="disclosure-summary">
              <div class="summary-stack">
                <span class="card-kicker" data-i18n="flow.oversight">Step 3 · Oversight</span>
                <h2 data-i18n="cards.reviewTitle">Review Queue</h2>
              </div>
              <span class="disclosure-meta" id="pending-summary-meta">0 pending</span>
            </summary>
            <div class="disclosure-body">
              <p class="disclosure-copy" data-i18n="cards.reviewCopy">Approval Gate makes this the primary decision panel. In other presets it stays available for guarded handoffs and exception review.</p>
              <div class="queue-guide">
                <strong data-i18n="cards.reviewGuideTitle">Review Checklist</strong>
                <ul id="review-guide-list">
                  <li data-i18n="cards.reviewGuidePoint1">Confirm the route is correct before delivery.</li>
                  <li data-i18n="cards.reviewGuidePoint2">Edit the message only when operator intent must be clarified.</li>
                  <li data-i18n="cards.reviewGuidePoint3">Reject when the handoff is unsafe, incomplete, or targeted at the wrong pane.</li>
                </ul>
              </div>
              <div class="summary-strip" id="review-strip"></div>
              <div class="note decision-note" id="review-note" data-i18n="cards.reviewDecisionIdle">No item selected yet. Choose a pending handoff to load the decision context.</div>
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
          </section>
        </section>

        <section class="workspace-panel" data-workspace-panel="inspect">
          <section class="layout-secondary">
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
              <div class="inspect-guide">
                <strong data-i18n="cards.inspectGuideTitle">Inspect Flow</strong>
                <p data-i18n="cards.inspectGuideCopy">Use Status for the current runtime truth, Activity for recent operator and transport events, and Diagnostics only when you need capture, interrupt, or audit investigation.</p>
              </div>
              <div class="summary-strip" id="inspect-strip"></div>
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

            <article class="card card--diagnostics" id="diagnostics-card">
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
                <button id="pause-review" class="ghost" type="button" data-i18n="actions.pauseReview">Pause Review</button>
                <button id="resume-review" class="ghost" type="button" data-i18n="actions.resumeReview">Resume Review</button>
                <button id="stop-workstream" class="warn" type="button" data-i18n="actions.stopWorkstream">Stop Workstream</button>
                <button id="reconcile-fleet" class="ghost" type="button" data-i18n="actions.reconcileFleet">Reconcile Fleet</button>
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
        </section>
      </section>
        </div>
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
          workspace: {
            workflow: 'Workflow',
            topology: 'Topology',
            review: 'Review',
            inspect: 'Inspect'
          },
          workspaceMeta: {
            workflowSetup: 'init session + bridge',
            workflowReady: 'launch + live ready',
            topologyIdle: 'launch map',
            topologyLive: 'live links visible',
            reviewOff: 'review off',
            reviewArmed: 'review armed',
            inspectIdle: 'idle',
            inspectLive: 'runtime + logs',
            inspectAudit: 'audit + diagnostics'
          },
          fleet: {
            title: 'Workstream Fleet',
            overview: 'Overview',
            hint: 'Select a workstream to manage.',
            empty: 'No active workstreams yet.',
            count: '{count} workstreams',
            countAlerts: '{count} workstreams · {warn} warn · {critical} critical',
            pending: '{count} pending',
            idle: 'idle',
            main: 'main',
            mainChildren: 'main + {count} sub',
            subOf: 'sub of {parent}',
            stateLive: 'live',
            stateRestored: 'restored',
            stateDegraded: 'degraded',
            healthOk: 'healthy',
            healthWarn: 'warn',
            healthCritical: 'critical',
            escalateReview: 'review',
            escalateIntervene: 'intervene'
          },
          strip: {
            preset: 'Preset',
            session: 'Session',
            panes: 'Panes',
            bridge: 'Bridge',
            routing: 'Routing',
            audit: 'Audit',
            emptySession: 'not set',
            panesReady: 'Host + Guest ready',
            panesWaiting: 'waiting for panes',
            bridgeLive: 'live bridge',
            bridgeIdle: 'not running',
            roomAttached: 'room {room}',
            roomPending: 'room pending',
            routeReview: 'review before delivery',
            routeDirect: 'direct handoff',
            routeManual: 'manual relay',
            auditOn: 'durable trail on',
            auditOff: 'disabled'
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
            pauseReview: 'Pause Review',
            resumeReview: 'Resume Review',
            stopWorkstream: 'Stop Workstream',
            reconcileFleet: 'Reconcile Fleet',
            jumpToFocus: 'Jump to Matched Control',
            sendHost: 'Send to Host',
            sendGuest: 'Send to Guest',
            sendRoom: 'Post to Room'
          },
          cards: {
            relationTitle: 'Relation View',
            relationCopy: 'See which components are live for the current preset, how they connect, and adjust the routing controls without leaving the console.',
            relationConfigTitle: 'Launch Plan',
            relationConfigCopy: 'Edit the staged launch settings here. They affect the next bridge start immediately, but not the already running bridge.',
            relationFactsTitle: 'Live Runtime',
            relationFactsCopy: 'This panel reflects the active room, bridge, audit, and runtime contract exactly as they are running right now.',
            relationLedgerTitle: 'Connection Ledger',
            relationLedgerCopy: 'Each line below describes the exact route or dependency currently shown in the diagram.',
            relationHintTitle: 'Topology Actions',
            relationHint: 'Click any node to jump to the matching control area. The launch card shows the staged plan; the runtime card shows the live contract.',
            relationSpotlightTitle: 'Topology Spotlight',
            relationSpotlightCopy: 'Select a node or connection to inspect the current state, why it matters, and where to jump next.',
            relationDriftLaunch: 'Launch plan changed',
            relationDriftRuntime: 'Live bridge still uses the previous contract',
            relationNote: 'Quick edits update launch settings immediately. Restart the active bridge if you need profile or approval changes to take effect on a running loop.',
            relationNoteLive: 'The active bridge is still running with profile {profile}, auto-forward {autoForward}, and review {intervention}. Restart the bridge to apply the edited launch settings.',
            relationMeta: '{preset} · {links} live links',
            reviewTitle: 'Review Queue',
            reviewCopy: 'Approval Gate makes this the main decision panel. In other presets it stays ready for guarded handoffs, corrections, and exception review.',
            reviewGuideTitle: 'Review Checklist',
            reviewGuidePoint1: 'Confirm the target route is correct before delivery.',
            reviewGuidePoint2: 'Edit the message only when operator intent must be clarified.',
            reviewGuidePoint3: 'Reject when the handoff is unsafe, incomplete, or aimed at the wrong pane.',
            reviewDecisionIdle: 'No item selected yet. Choose a pending handoff to load the decision context.',
            reviewDecisionApprove: 'Approve when the route, target pane, and wording are already safe for delivery.',
            reviewDecisionEdit: 'Edit before approve because the message has operator intent but needs tighter wording or context.',
            reviewDecisionReject: 'Reject because the route, target, or content is unsafe, incomplete, or misdirected.',
            reviewTilePending: 'Pending',
            reviewTileRoute: 'Route',
            reviewTileAction: 'Action',
            reviewTileEdited: 'Edited',
            reviewEditedYes: 'edited text present',
            reviewEditedNo: 'send original text',
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
            launchNote: 'Stage the launch plan here. Init Session prepares panes; Start Collaboration begins the active bridge.',
            liveTitle: 'Live Collaboration',
            liveCopy: 'Use this panel once the bridge is active. Watch the room, send operator guidance, and confirm guarded delivery behavior.',
            liveEmpty: 'Start Collaboration to unlock room controls and the live stream.',
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
            statusCopy: 'Read the runtime snapshot first, then correlate it with recent transport and operator activity.',
            statusNote: 'Presets reduce clutter, but they do not change the underlying runtime. Open this panel when room, bridge, pane, or subscriber truth matters.',
            inspectGuideTitle: 'Inspect Flow',
            inspectGuideCopy: 'Use Status for runtime truth, Activity for recent events, and Diagnostics only when you need capture, interrupt, or audit investigation.',
            inspectTileBridge: 'Bridge',
            inspectTileRoom: 'Room',
            inspectTileTransport: 'Transport',
            inspectTileGuard: 'Guard',
            inspectTileDependency: 'Dependency',
            inspectDependencyClear: 'No dependency blocker',
            inspectGuardActive: 'guarded',
            inspectGuardIdle: 'not guarding',
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
            statusBadgeAuditRawBlocked: 'Audit raw blocked',
            statusBadgeSecurity: 'Security {tier}',
            statusBadgeHealth: 'Health {state}',
            statusBadgeEscalation: 'Escalation {mode}'
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
          relation: {
            gui: 'Browser GUI',
            guiDetail: 'Operator console',
            mcp: 'MCP Client',
            mcpDetail: 'External tool driver',
            server: 'TB2 Server',
            serverDetail: 'JSON-RPC / status hub',
            room: 'Live Room',
            roomDetail: 'Shared handoff buffer',
            bridge: 'Bridge Worker',
            bridgeDetail: 'Message relay',
            host: 'Host Pane',
            guest: 'Guest Pane',
            review: 'Review Queue',
            reviewDetail: 'Human approval gate',
            audit: 'Audit Trail',
            auditDetail: 'Persisted events',
            runtime: 'Runtime',
            backend: 'Backend',
            profile: 'Profile',
            transport: 'Transport',
            subscribersLabel: 'Subscribers',
            continuity: 'Continuity',
            guard: 'Guard',
            pending: 'Pending',
            autoForwardLabel: 'Auto-forward',
            reviewMode: 'Review',
            active: 'active',
            standby: 'standby',
            muted: 'off',
            attention: 'guarded',
            direct: 'direct',
            none: 'not attached',
            subscribers: '{total} subscribers',
            pendingCount: '{count} pending',
            auditOff: 'disabled',
            auditOn: '{mode} redaction',
            autoForwardOn: 'on',
            autoForwardOff: 'off',
            reviewOn: 'on',
            reviewOff: 'off',
            autoForwardShort: 'Auto FWD',
            reviewShort: 'Review Gate',
            launchConfig: 'Launch config'
          },
          relationLanes: {
            operator: 'Operator Surface',
            control: 'Control Plane',
            execution: 'Execution Plane'
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
            reviewPaused: 'Review paused for the selected workstream',
            reviewResumed: 'Review resumed for the selected workstream',
            approved: 'Pending handoff approved',
            rejected: 'Pending handoff rejected',
            workstreamStopped: 'Stopped {count} workstream(s)',
            fleetReconciled: 'Fleet reconciled: {workstreams} workstream(s), {rooms} room(s)',
            ready: 'GUI ready, endpoint {endpoint}',
            languageChanged: 'Language switched to {language}',
            layoutChanged: 'Layout switched to {layout}'
          },
          errors: {
            toolCallFailed: 'tool call failed',
            paneTargetsRequired: 'pane targets are required',
            bridgeIdRequired: 'bridge_id is required',
            roomIdRequired: 'room_id is required',
            workstreamTargetRequired: 'workstream, bridge, or room target is required',
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
            relation: 'Support · Relation View',
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
          workspace: {
            workflow: '工作流',
            topology: '拓樸',
            review: '審核',
            inspect: '檢查'
          },
          workspaceMeta: {
            workflowSetup: '初始化與啟動',
            workflowReady: '主流程就緒',
            topologyIdle: '啟動拓樸',
            topologyLive: 'live 連線中',
            reviewOff: '審核關閉',
            reviewArmed: '審核待命',
            inspectIdle: '待命',
            inspectLive: '狀態與活動',
            inspectAudit: 'audit 與診斷'
          },
          fleet: {
            title: 'Workstream Fleet',
            overview: 'Overview',
            hint: '選擇一條 workstream 進行操作。',
            empty: '目前還沒有 active workstream。',
            count: '{count} 條 workstream',
            countAlerts: '{count} 條 workstream · {warn} 條警示 · {critical} 條嚴重',
            pending: '{count} 筆待審',
            idle: '閒置',
            main: 'main',
            mainChildren: 'main + {count} 條 sub',
            subOf: 'sub -> {parent}',
            stateLive: '運行中',
            stateRestored: '已恢復',
            stateDegraded: '降級',
            healthOk: '健康',
            healthWarn: '警示',
            healthCritical: '嚴重',
            escalateReview: '需審核',
            escalateIntervene: '需介入'
          },
          strip: {
            preset: 'Preset',
            session: 'Session',
            panes: 'Panes',
            bridge: 'Bridge',
            routing: 'Routing',
            audit: 'Audit',
            emptySession: '尚未設定',
            panesReady: 'Host + Guest 已就緒',
            panesWaiting: '尚待建立 panes',
            bridgeLive: 'bridge 運作中',
            bridgeIdle: '尚未啟動',
            roomAttached: 'room {room}',
            roomPending: '尚未綁定 room',
            routeReview: '送出前先審核',
            routeDirect: '直接交接',
            routeManual: '人工 relay',
            auditOn: '持久化紀錄啟用',
            auditOff: '未啟用'
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
            pauseReview: '暫停審核',
            resumeReview: '恢復審核',
            stopWorkstream: '停止 Workstream',
            reconcileFleet: '整理 Fleet',
            jumpToFocus: '跳到對應控制區',
            sendHost: '送到 Host',
            sendGuest: '送到 Guest',
            sendRoom: '發到 Room'
          },
          cards: {
            relationTitle: '關聯視圖',
            relationCopy: '直接查看目前 preset 啟用了哪些元件、彼此怎麼連線，並在同一區快速調整路由與啟動設定。',
            relationConfigTitle: '啟動計畫',
            relationConfigCopy: '這裡編輯的是下一次啟動要套用的設定。它會立刻改變 staged launch plan，但不會直接改掉正在運行的 bridge。',
            relationFactsTitle: 'Live Runtime',
            relationFactsCopy: '這裡只顯示目前正在運作的 room、bridge、audit 與 runtime 契約，不會混入裝飾性假資料。',
            relationLedgerTitle: '連線帳本',
            relationLedgerCopy: '下方每一筆都對應圖上目前畫出的實際連線、路由或依賴關係。',
            relationHintTitle: '拓樸操作',
            relationHint: '點擊任一節點即可跳到對應控制區。左邊卡片是 staged launch plan，右邊卡片是 live runtime contract。',
            relationSpotlightTitle: '拓樸焦點',
            relationSpotlightCopy: '選擇節點或連線後，這裡會說明目前狀態、它的重要性，以及下一步可以跳去哪個控制區。',
            relationDriftLaunch: '啟動計畫已變更',
            relationDriftRuntime: '目前 live bridge 仍沿用上一版契約',
            relationNote: '這裡的快速編輯會立即更新啟動設定。若目前 bridge 已在運行，想讓 profile 或審核設定生效仍需重新啟動 bridge。',
            relationNoteLive: '目前 active bridge 仍以 profile {profile}、auto-forward {autoForward}、review {intervention} 運作。若要套用你剛修改的啟動設定，請重新啟動 bridge。',
            relationMeta: '{preset} · {links} 條啟用連線',
            reviewTitle: '審核佇列',
            reviewCopy: '審核閘門模式下，這裡是主要決策面板；其他 preset 也會在 guarded handoff、改寫與例外處理時回到這裡。',
            reviewGuideTitle: '審核檢查表',
            reviewGuidePoint1: '先確認送達目標與路徑是否正確。',
            reviewGuidePoint2: '只有在需要釐清 operator 意圖時才改寫訊息。',
            reviewGuidePoint3: '若 handoff 有風險、資訊不完整、或目標 pane 錯誤，就直接退回。',
            reviewDecisionIdle: '尚未選定項目。先選一筆待審 handoff，才會載入決策脈絡。',
            reviewDecisionApprove: '當路徑、目標 pane 與文字內容都已可安全送達時，直接核准。',
            reviewDecisionEdit: '這筆 handoff 意圖正確，但需要補足語氣或脈絡時，先改寫再核准。',
            reviewDecisionReject: '若路徑、目標或內容有風險、不完整、或送錯對象，就直接退回。',
            reviewTilePending: '待審',
            reviewTileRoute: '路徑',
            reviewTileAction: '動作',
            reviewTileEdited: '改寫',
            reviewEditedYes: '已有改寫文字',
            reviewEditedNo: '送出原始內容',
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
            launchNote: '先在這裡排好啟動計畫。Init Session 用來建立 panes；開始協作才會真的啟動 active bridge。',
            liveTitle: '即時協作',
            liveCopy: 'Bridge 啟動後，這裡就是主要操作面。查看 room、送出 operator 指示，並觀察 guarded delivery 是否如預期運作。',
            liveEmpty: '按下開始協作後，這裡才會顯示 room 控制與 live stream。',
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
            statusCopy: '先讀取 runtime snapshot，再對照最近的 transport 與 operator activity。',
            statusNote: 'Preset 會幫你收斂畫面，但不會改變底層 runtime。當 room、bridge、pane 或 subscriber 真實狀態重要時，就打開這裡。',
            inspectGuideTitle: '檢查流程',
            inspectGuideCopy: 'Status 用來看 runtime truth，Activity 用來對照最近事件，Diagnostics 則只在需要 capture、interrupt 或 audit 調查時再使用。',
            inspectTileBridge: 'Bridge',
            inspectTileRoom: 'Room',
            inspectTileTransport: 'Transport',
            inspectTileGuard: 'Guard',
            inspectTileDependency: 'Dependency',
            inspectDependencyClear: '目前沒有 dependency blocker',
            inspectGuardActive: '警戒中',
            inspectGuardIdle: '未警戒',
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
            statusBadgeAuditRawBlocked: 'Audit raw 已阻擋',
            statusBadgeSecurity: 'Security {tier}',
            statusBadgeHealth: '健康度 {state}',
            statusBadgeEscalation: '升級 {mode}'
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
          relation: {
            gui: 'Browser GUI',
            guiDetail: '操作控制台',
            mcp: 'MCP Client',
            mcpDetail: '外部工具驅動端',
            server: 'TB2 Server',
            serverDetail: 'JSON-RPC / status 中樞',
            room: 'Live Room',
            roomDetail: '共享 handoff 緩衝區',
            bridge: 'Bridge Worker',
            bridgeDetail: '訊息轉發工作器',
            host: 'Host Pane',
            guest: 'Guest Pane',
            review: 'Review Queue',
            reviewDetail: '人工審核閘門',
            audit: 'Audit Trail',
            auditDetail: '持久化事件紀錄',
            runtime: 'Runtime',
            backend: 'Backend',
            profile: 'Profile',
            transport: 'Transport',
            subscribersLabel: 'Subscribers',
            continuity: 'Continuity',
            guard: 'Guard',
            pending: '待審',
            autoForwardLabel: '自動轉發',
            reviewMode: '審核',
            active: '啟用中',
            standby: '待命',
            muted: '關閉',
            attention: '警戒中',
            direct: '直接',
            none: '尚未連接',
            subscribers: '{total} 個訂閱',
            pendingCount: '{count} 筆待審',
            auditOff: '未啟用',
            auditOn: '{mode} 遮罩',
            autoForwardOn: '開啟',
            autoForwardOff: '關閉',
            reviewOn: '開啟',
            reviewOff: '關閉',
            autoForwardShort: '自動轉發',
            reviewShort: '審核閘門',
            launchConfig: '啟動設定'
          },
          relationLanes: {
            operator: '操作面',
            control: '控制平面',
            execution: '執行平面'
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
            reviewPaused: '已暫停所選 workstream 的審核',
            reviewResumed: '已恢復所選 workstream 的審核',
            approved: '待審 handoff 已核准',
            rejected: '待審 handoff 已退回',
            workstreamStopped: '已停止 {count} 條 workstream',
            fleetReconciled: 'Fleet 已整理：{workstreams} 條 workstream，{rooms} 個 room',
            ready: 'GUI 已就緒，endpoint {endpoint}',
            languageChanged: '語言已切換為 {language}',
            layoutChanged: '版面已切換為 {layout}'
          },
          errors: {
            toolCallFailed: '工具呼叫失敗',
            paneTargetsRequired: '必須先提供 pane targets',
            bridgeIdRequired: '必須提供 bridge_id',
            roomIdRequired: '必須提供 room_id',
            workstreamTargetRequired: '必須提供 workstream、bridge 或 room 目標',
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
            relation: '支援 · 關聯視圖',
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

      const RELATION_CANVAS = { width: 980, height: 428 };
      const RELATION_NODE_BOX = { width: 180, height: 126 };
      const RELATION_POSITIONS = {
        gui: { x: 150, y: 96 },
        mcp: { x: 150, y: 214 },
        audit: { x: 150, y: 332 },
        room: { x: 490, y: 96 },
        server: { x: 490, y: 214 },
        review: { x: 490, y: 332 },
        host: { x: 830, y: 96 },
        bridge: { x: 830, y: 214 },
        guest: { x: 830, y: 332 },
      };

      const state = {
        reqId: 1,
        locale: 'en',
        layout: 'balanced',
        workspaceTab: 'workflow',
        preset: 'quick',
        home: true,
        relationFocus: null,
        lastMsgId: 0,
        poller: null,
        sse: null,
        ws: null,
        guard: null,
        audit: null,
        statusSnapshot: null,
        auditEvents: [],
        pendingItems: [],
        selectedWorkstreamId: '',
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

      function preferredWorkspaceTab() {
        try {
          const saved = window.localStorage.getItem('tb2-workspace-tab');
          if (saved === 'workflow' || saved === 'topology' || saved === 'review' || saved === 'inspect') return saved;
        } catch (_) {
          // Ignore storage failures and fall back to the default tab.
        }
        return 'workflow';
      }

      function recommendedWorkspaceTab(name) {
        if (name === 'approval' || name === 'radar') return 'review';
        if (name === 'mcp' || name === 'mission') return 'topology';
        if (name === 'diagnostics') return 'inspect';
        return 'workflow';
      }

      function transportName(mode) {
        return t('transport.' + mode);
      }

      function deliverName(value) {
        if (value === 'a') return t('deliver.host');
        if (value === 'b') return t('deliver.guest');
        if (value === 'both') return t('deliver.both');
        return t('deliver.roomOnly');
      }

      function setSelectValue(select, value) {
        if (!select) return;
        const exists = Array.from(select.options).some(option => option.value === value);
        if (!exists) return;
        select.value = value;
      }

      function workstreamsFromStatus(status) {
        return Array.isArray(status && status.workstreams) ? status.workstreams : [];
      }

      function workstreamStateLabel(name) {
        if (name === 'restored') return t('fleet.stateRestored');
        if (name === 'degraded') return t('fleet.stateDegraded');
        return t('fleet.stateLive');
      }

      function workstreamHealthLabel(health) {
        const stateName = health && health.state ? String(health.state) : 'ok';
        if (stateName === 'critical') return t('fleet.healthCritical');
        if (stateName === 'warn') return t('fleet.healthWarn');
        return t('fleet.healthOk');
      }

      function workstreamEscalationLabel(health) {
        const escalation = health && health.escalation ? String(health.escalation) : 'observe';
        if (escalation === 'intervene') return t('fleet.escalateIntervene');
        if (escalation === 'review') return t('fleet.escalateReview');
        return '';
      }

      function inferWorkstream(status) {
        const workstreams = workstreamsFromStatus(status);
        if (!workstreams.length) return null;
        if (state.selectedWorkstreamId) {
          const exact = workstreams.find(item => item && item.workstream_id === state.selectedWorkstreamId);
          if (exact) return exact;
        }
        const bridgeId = $('bridge-id').value.trim();
        if (bridgeId) {
          const exact = workstreams.find(item => item && item.bridge_id === bridgeId);
          if (exact) return exact;
        }
        const roomId = $('room-id').value.trim();
        if (roomId) {
          const exact = workstreams.find(item => item && item.room_id === roomId);
          if (exact) return exact;
        }
        return workstreams.find(item => item && item.bridge_active) || workstreams[0];
      }

      function bridgeIsActive(detail) {
        if (!detail) return false;
        if (typeof detail.bridge_active === 'boolean') return detail.bridge_active;
        return Boolean(detail.bridge_id);
      }

      function applyWorkstreamSelection(item) {
        if (!item) return;
        state.selectedWorkstreamId = String(item.workstream_id || '');
        $('room-id').value = String(item.room_id || '');
        $('bridge-id').value = item.bridge_active ? String(item.bridge_id || '') : '';
        $('pane-a').value = String(item.pane_a || $('pane-a').value || '');
        $('pane-b').value = String(item.pane_b || $('pane-b').value || '');
        setSelectValue($('profile'), String(item.profile || 'generic'));
        if (item.backend && item.backend.kind) setSelectValue($('backend'), String(item.backend.kind));
        $('auto-forward').checked = Boolean(item.auto_forward);
        $('intervention').checked = Boolean(item.intervention);
        syncMetrics();
      }

      function syncMirroredSelectOptions(sourceId, targetId) {
        const source = $(sourceId);
        const target = $(targetId);
        if (!source || !target) return;
        const known = new Set(Array.from(target.options).map(option => option.value));
        Array.from(source.options).forEach(option => {
          if (known.has(option.value)) return;
          const clone = document.createElement('option');
          clone.value = option.value;
          clone.textContent = option.textContent;
          const i18nKey = option.getAttribute('data-i18n');
          if (i18nKey) clone.setAttribute('data-i18n', i18nKey);
          target.appendChild(clone);
        });
      }

      function syncRelationControls() {
        syncMirroredSelectOptions('backend', 'relation-backend');
        syncMirroredSelectOptions('profile', 'relation-profile');
        syncMirroredSelectOptions('transport', 'relation-transport');
        syncMirroredSelectOptions('deliver', 'relation-deliver');
        setSelectValue($('relation-backend'), $('backend').value);
        setSelectValue($('relation-profile'), $('profile').value);
        setSelectValue($('relation-transport'), $('transport').value);
        setSelectValue($('relation-deliver'), $('deliver').value);
        $('relation-auto-forward').checked = $('auto-forward').checked;
        $('relation-intervention').checked = $('intervention').checked;
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

      function setWorkspaceButtons() {
        document.querySelectorAll('[data-workspace-tab]').forEach(button => {
          const active = button.dataset.workspaceTab === state.workspaceTab;
          button.classList.toggle('active', active);
          button.setAttribute('aria-pressed', active ? 'true' : 'false');
          button.setAttribute('aria-current', active ? 'page' : 'false');
        });
      }

      function workspaceMetaText(name) {
        const detail = inferBridgeDetail(state.statusSnapshot);
        const bridgeActive = bridgeIsActive(detail) || Boolean($('bridge-id').value.trim());
        const roomActive = Boolean((detail && detail.room_id) || $('room-id').value.trim());
        const pendingCount = state.pendingItems.length;
        const reviewEnabled = detail ? Boolean(detail.intervention) : $('intervention').checked;
        const auditActive = Boolean(state.audit && state.audit.enabled);
        if (name === 'workflow') {
          const hasPanes = Boolean($('pane-a').value.trim() && $('pane-b').value.trim());
          return hasPanes || bridgeActive ? t('workspaceMeta.workflowReady') : t('workspaceMeta.workflowSetup');
        }
        if (name === 'topology') {
          return bridgeActive || roomActive ? t('workspaceMeta.topologyLive') : t('workspaceMeta.topologyIdle');
        }
        if (name === 'review') {
          if (pendingCount > 0) return format('cards.reviewMetaPending', { count: pendingCount });
          return reviewEnabled ? t('workspaceMeta.reviewArmed') : t('workspaceMeta.reviewOff');
        }
        if (name === 'inspect') {
          if (auditActive) return t('workspaceMeta.inspectAudit');
          return bridgeActive || roomActive ? t('workspaceMeta.inspectLive') : t('workspaceMeta.inspectIdle');
        }
        return '';
      }

      function renderWorkspaceTabs() {
        document.querySelectorAll('[data-workspace-tab]').forEach(button => {
          const name = button.dataset.workspaceTab || 'workflow';
          const label = button.querySelector('.workspace-tab-label');
          const meta = button.querySelector('.workspace-tab-meta');
          if (label) label.textContent = t('workspace.' + name);
          if (meta) meta.textContent = workspaceMetaText(name);
        });
      }

      function addWorkspaceChip(container, label, value, detail, stateName) {
        const item = document.createElement('div');
        item.className = 'workspace-chip is-' + stateName;
        const title = document.createElement('strong');
        title.textContent = label;
        const main = document.createElement('span');
        main.textContent = value;
        const sub = document.createElement('small');
        sub.textContent = detail;
        item.appendChild(title);
        item.appendChild(main);
        item.appendChild(sub);
        container.appendChild(item);
      }

      function addSummaryTile(container, label, value, detail, stateName) {
        const item = document.createElement('div');
        item.className = 'summary-tile is-' + stateName;
        const title = document.createElement('strong');
        title.textContent = label;
        const main = document.createElement('span');
        main.textContent = value;
        const sub = document.createElement('small');
        sub.textContent = detail;
        item.appendChild(title);
        item.appendChild(main);
        item.appendChild(sub);
        container.appendChild(item);
      }

      function renderWorkspaceStrip() {
        const container = $('workspace-strip');
        if (!container) return;
        container.replaceChildren();
        const detail = inferBridgeDetail(state.statusSnapshot);
        const roomId = $('room-id').value.trim() || (detail && detail.room_id) || '';
        const bridgeId = $('bridge-id').value.trim() || (bridgeIsActive(detail) ? (detail && detail.bridge_id) : '') || '';
        const sessionId = $('session').value.trim();
        const hasPanes = Boolean($('pane-a').value.trim() && $('pane-b').value.trim());
        const bridgeActive = Boolean(bridgeId);
        const reviewEnabled = detail ? Boolean(detail.intervention) : $('intervention').checked;
        const autoForward = detail ? Boolean(detail.auto_forward) : $('auto-forward').checked;
        const pendingCount = state.pendingItems.length;
        const auditActive = Boolean(state.audit && state.audit.enabled);
        addWorkspaceChip(
          container,
          t('strip.preset'),
          t('presets.' + state.preset + '.label'),
          t('presets.' + state.preset + '.summary'),
          'active'
        );
        addWorkspaceChip(
          container,
          t('strip.session'),
          sessionId || t('strip.emptySession'),
          hasPanes ? t('strip.panesReady') : t('strip.panesWaiting'),
          hasPanes ? 'active' : 'muted'
        );
        addWorkspaceChip(
          container,
          t('strip.panes'),
          hasPanes ? $('pane-a').value.trim() + ' / ' + $('pane-b').value.trim() : t('strip.panesWaiting'),
          hasPanes ? t('strip.panesReady') : t('cards.launchNote'),
          hasPanes ? 'active' : 'muted'
        );
        addWorkspaceChip(
          container,
          t('strip.bridge'),
          bridgeActive ? bridgeId : t('strip.bridgeIdle'),
          roomId ? format('strip.roomAttached', { room: roomId }) : t('strip.roomPending'),
          bridgeActive ? 'active' : 'muted'
        );
        addWorkspaceChip(
          container,
          t('strip.routing'),
          pendingCount > 0
            ? format('cards.reviewMetaPending', { count: pendingCount })
            : (reviewEnabled ? t('strip.routeReview') : (autoForward ? t('strip.routeDirect') : t('strip.routeManual'))),
          reviewEnabled
            ? (pendingCount > 0 ? t('cards.reviewGuidePoint1') : t('relation.reviewDetail'))
            : (autoForward ? t('fields.autoForward') : t('cards.reviewEmpty')),
          pendingCount > 0 ? 'attention' : (reviewEnabled || autoForward ? 'active' : 'muted')
        );
        addWorkspaceChip(
          container,
          t('strip.audit'),
          auditActive ? t('strip.auditOn') : t('strip.auditOff'),
          auditActive
            ? format('relation.auditOn', { mode: String((state.audit.redaction && state.audit.redaction.mode) || 'default') })
            : t('relation.auditOff'),
          auditActive ? 'active' : 'muted'
        );
      }

      function setWorkspaceTab(name, options) {
        const next = name === 'topology' || name === 'review' || name === 'inspect' ? name : 'workflow';
        state.workspaceTab = next;
        document.querySelectorAll('[data-workspace-panel]').forEach(panel => {
          panel.classList.toggle('is-active', panel.dataset.workspacePanel === next);
        });
        setWorkspaceButtons();
        if (!options || options.persist !== false) {
          try {
            window.localStorage.setItem('tb2-workspace-tab', next);
          } catch (_) {
            // Ignore storage failures.
          }
        }
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
        setWorkspaceButtons();
        renderWorkspaceTabs();
        renderWorkspaceStrip();
        renderReviewSummary();
        renderInspectSummary(state.statusSnapshot || {});
        renderAudit();
        renderRelationView();
      }

      function applyLocale(locale) {
        state.locale = I18N[locale] ? locale : 'en';
        try {
          window.localStorage.setItem('tb2-lang', state.locale);
        } catch (_) {
          // Ignore storage failures.
        }
        translatePage();
        applyPreset(state.preset, { keepTab: true });
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

      function pulseTarget(target) {
        if (!target) return;
        target.classList.remove('focus-target');
        window.setTimeout(() => target.classList.add('focus-target'), 0);
        window.setTimeout(() => target.classList.remove('focus-target'), 2200);
      }

      function focusControlArea(targetId, tab, options) {
        const requested = $(targetId);
        const target = requested && !requested.classList.contains('hidden')
          ? requested
          : (tab === 'inspect' ? $('status-card') : (tab === 'review' ? $('pending-card') : $('launch-card')));
        if (!target) return;
        setWorkspaceTab(tab, { persist: false });
        if (options && options.openId) {
          const disclosure = $(options.openId);
          if (disclosure && 'open' in disclosure) disclosure.open = true;
        }
        window.requestAnimationFrame(() => {
          target.setAttribute('tabindex', '-1');
          target.scrollIntoView({ behavior: 'smooth', block: 'start' });
          target.focus({ preventScroll: true });
          pulseTarget(target);
        });
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
        syncRelationControls();
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
        $('launch-card').classList.toggle('card--current', focus === 'launch' || (!liveActive && focus !== 'status'));
        $('live-card').classList.toggle('card--current', focus === 'live' || ((hasPanes || liveActive) && focus === 'launch'));
        $('pending-card').classList.toggle('card--current', focus === 'pending' || pendingCount > 0 || state.preset === 'approval');
        $('status-card').classList.toggle('card--current', focus === 'status');
        $('diagnostics-card').classList.toggle('card--current', focus === 'diagnostics');

        setHidden('live-shell', !liveActive);
        setHidden('live-empty', liveActive);
        setHidden('guard-note', !guardBlocked);

        setHidden('pending-card', false);
        setHidden('diagnostics-card', false);
        setHidden('status-card', false);
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
        if (state.preset === 'mission' || state.preset === 'mcp') $('relation-details').open = true;
        if (state.preset === 'diagnostics') $('diagnostics-details').open = true;
        if (focus === 'diagnostics') $('diagnostics-details').open = true;
        renderWorkspaceTabs();
        renderWorkspaceStrip();
        renderReviewSummary();
        renderInspectSummary(state.statusSnapshot || {});
        renderRelationView();
      }

      function applyPreset(name, options) {
        const preset = PRESETS[name] || PRESETS.quick;
        state.preset = name;
        state.relationFocus = null;
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
        if (!(options && options.keepTab)) {
          setWorkspaceTab(recommendedWorkspaceTab(name), { persist: false });
        }
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

      function relativePendingAge(ts) {
        const value = Number(ts || 0);
        if (!value) return '?';
        const deltaSeconds = Math.max(0, Math.round(Date.now() / 1000) - value);
        if (deltaSeconds < 60) return deltaSeconds + 's';
        if (deltaSeconds < 3600) return Math.floor(deltaSeconds / 60) + 'm';
        if (deltaSeconds < 86400) return Math.floor(deltaSeconds / 3600) + 'h';
        return Math.floor(deltaSeconds / 86400) + 'd';
      }

      function selectedPendingItem() {
        const id = $('pending-select').value;
        if (!id) return null;
        return state.pendingItems.find(item => String(item.id) === id) || null;
      }

      function reviewDecisionText(item, edited) {
        if (!item) return t('cards.reviewDecisionIdle');
        const text = String(item.text || '');
        const routeMismatch = String(item.to_pane || '').trim() === '';
        if (routeMismatch) return t('cards.reviewDecisionReject');
        if (edited && edited !== text) return t('cards.reviewDecisionEdit');
        if (!text.trim()) return t('cards.reviewDecisionReject');
        return t('cards.reviewDecisionApprove');
      }

      function renderReviewSummary() {
        const container = $('review-strip');
        const note = $('review-note');
        if (!container || !note) return;
        container.replaceChildren();
        const item = selectedPendingItem();
        const edited = $('pending-edit').value.trim();
        if (!item) {
          addSummaryTile(container, t('cards.reviewTilePending'), format('relation.pendingCount', { count: state.pendingItems.length }), t('cards.reviewEmpty'), state.pendingItems.length > 0 ? 'attention' : 'muted');
          addSummaryTile(container, t('cards.reviewTileRoute'), t('relation.none'), t('cards.pendingDetailEmpty'), 'muted');
          addSummaryTile(container, t('cards.reviewTileAction'), t('cards.reviewDecisionIdle'), t('cards.reviewGuidePoint1'), 'muted');
          addSummaryTile(container, t('cards.reviewTileEdited'), t('cards.reviewEditedNo'), t('cards.pendingDetailEditedFallback'), 'muted');
          note.textContent = t('cards.reviewDecisionIdle');
          return;
        }
        const route = String(item.from_pane || '?') + ' -> ' + String(item.to_pane || '?');
        const hasEditedText = Boolean(edited && edited !== String(item.text || ''));
        addSummaryTile(container, t('cards.reviewTilePending'), '#' + String(item.id || '?'), relativePendingAge(item.created_at), 'attention');
        addSummaryTile(container, t('cards.reviewTileRoute'), route, formatPendingTimestamp(item.created_at), 'active');
        addSummaryTile(container, t('cards.reviewTileAction'), String(item.action || '?'), reviewDecisionText(item, edited), 'active');
        addSummaryTile(container, t('cards.reviewTileEdited'), hasEditedText ? t('cards.reviewEditedYes') : t('cards.reviewEditedNo'), hasEditedText ? edited : t('cards.pendingDetailEditedFallback'), hasEditedText ? 'attention' : 'muted');
        note.textContent = reviewDecisionText(item, edited);
      }

      function renderInspectSummary(status) {
        const container = $('inspect-strip');
        if (!container) return;
        container.replaceChildren();
        const detail = inferBridgeDetail(status || state.statusSnapshot);
        const roomId = $('room-id').value.trim() || (detail && detail.room_id) || '';
        const rooms = Array.isArray(status && status.rooms) ? status.rooms : [];
        const room = rooms.find(item => item && item.id === roomId) || null;
        const subscribers = room && room.subscribers ? room.subscribers : null;
        const guard = detail && detail.auto_forward_guard ? detail.auto_forward_guard : state.guard;
        const transportMode = $('transport').value.trim() || 'sse';
        addSummaryTile(
          container,
          t('cards.inspectTileBridge'),
          bridgeIsActive(detail) && detail && detail.bridge_id ? String(detail.bridge_id) : t('strip.bridgeIdle'),
          detail && detail.profile ? String(detail.profile) : t('relation.none'),
          bridgeIsActive(detail) ? 'active' : 'muted'
        );
        addSummaryTile(
          container,
          t('cards.inspectTileRoom'),
          roomId || t('relation.none'),
          subscribers ? format('relation.subscribers', { total: subscribers.total || 0 }) : t('cards.statusBadgeTransportIdle'),
          roomId ? 'active' : 'muted'
        );
        addSummaryTile(
          container,
          t('cards.inspectTileTransport'),
          transportName(transportMode),
          subscribers
            ? format('cards.statusBadgeTransport', {
                total: subscribers.total || 0,
                sse: subscribers.sse || 0,
                websocket: subscribers.websocket || 0,
              })
            : t('cards.statusBadgeTransportIdle'),
          subscribers && subscribers.total > 0 ? 'active' : 'muted'
        );
        addSummaryTile(
          container,
          t('cards.inspectTileGuard'),
          guard && guard.blocked ? t('cards.inspectGuardActive') : t('cards.inspectGuardIdle'),
          guard && guard.guard_reason ? String(guard.guard_reason) : t('cards.inspectGuideCopy'),
          guard && guard.blocked ? 'attention' : 'active'
        );
        addSummaryTile(
          container,
          t('cards.inspectTileDependency'),
          workstreamDependencyLabel(detail),
          workstreamDependencyBlocker(detail) || t('cards.inspectDependencyClear'),
          workstreamDependencyBlocker(detail) ? 'attention' : 'active'
        );
      }

      function renderPendingDetail() {
        const item = selectedPendingItem();
        const box = $('pending-detail');
        const edit = $('pending-edit');
        if (!item) {
          box.textContent = t('cards.pendingDetailEmpty');
          if (document.activeElement !== edit) edit.value = '';
          renderReviewSummary();
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
        renderReviewSummary();
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
        const workstreamId = state.selectedWorkstreamId.trim();
        const bridgeId = $('bridge-id').value.trim();
        const roomId = $('room-id').value.trim();
        if (workstreamId) args.workstream_id = workstreamId;
        if (bridgeId) args.bridge_id = bridgeId;
        if (!bridgeId && roomId) args.room_id = roomId;
        return args;
      }

      function clearBridgeState() {
        state.selectedWorkstreamId = '';
        $('bridge-id').value = '';
        $('pending-edit').value = '';
        state.guard = null;
        state.statusSnapshot = null;
        fillPending([]);
      }

      function requireWorkstreamTarget() {
        const args = bridgeArgs();
        if (args.workstream_id || args.bridge_id || args.room_id) return args;
        throw new Error(t('errors.workstreamTargetRequired'));
      }

      function workstreamDependencyLabel(detail) {
        if (!detail) return t('relation.none');
        const dependency = detail && detail.dependency ? detail.dependency : null;
        const tier = dependency && dependency.tier ? String(dependency.tier) : String(detail.tier || 'main');
        if (tier === 'sub') {
          const parent = dependency && dependency.parent_workstream_id
            ? String(dependency.parent_workstream_id)
            : String(detail.parent_workstream_id || '?');
          return format('fleet.subOf', { parent });
        }
        const childCount = dependency ? Number(dependency.child_count || 0) : 0;
        return childCount > 0 ? format('fleet.mainChildren', { count: childCount }) : t('fleet.main');
      }

      function workstreamDependencyBlocker(detail) {
        const dependency = detail && detail.dependency ? detail.dependency : null;
        const blockers = dependency && Array.isArray(dependency.blocking_reasons) ? dependency.blocking_reasons : [];
        return blockers.length ? String(blockers[0]) : '';
      }

      function isInactiveBridgeError(message) {
        if (!message) return false;
        return message === 'bridge not found'
          || message.startsWith('workstream ') && message.endsWith(' has no active bridge')
          || message === 'bridge_id required: no active bridges'
          || message.startsWith('no active bridge for room ');
      }

      function renderWorkstreamFleet(status) {
        const box = $('workstream-list');
        const meta = $('fleet-summary-meta');
        if (!box || !meta) return;
        const workstreams = workstreamsFromStatus(status);
        box.innerHTML = '';
        if (status && status.fleet && (status.fleet.warn || status.fleet.critical)) {
          meta.textContent = format('fleet.countAlerts', {
            count: workstreams.length,
            warn: Number(status.fleet.warn || 0),
            critical: Number(status.fleet.critical || 0)
          });
        } else {
          meta.textContent = workstreams.length ? format('fleet.count', { count: workstreams.length }) : t('fleet.empty');
        }
        if (!workstreams.length) return;
        const selected = inferWorkstream(status);
        if (selected) applyWorkstreamSelection(selected);
        workstreams.forEach(item => {
          const button = document.createElement('button');
          button.type = 'button';
          button.className = 'preset' + (selected && selected.workstream_id === item.workstream_id ? ' active' : '');
          const title = document.createElement('b');
          title.textContent = String(item.workstream_id || '');
          const detail = document.createElement('span');
          const roomId = String(item.room_id || '');
          const pending = Number(item.pending_count || 0) || 0;
          const pendingLabel = pending > 0 ? format('fleet.pending', { count: pending }) : t('fleet.idle');
          const health = item.health || null;
          const escalation = workstreamEscalationLabel(health);
          const healthLabel = workstreamHealthLabel(health);
          const dependencyLabel = workstreamDependencyLabel(item);
          detail.textContent = workstreamStateLabel(String(item.state || 'live')) + ' · ' + healthLabel + (escalation ? ' · ' + escalation : '') + ' · ' + pendingLabel + ' · ' + dependencyLabel + ' · ' + roomId;
          button.appendChild(title);
          button.appendChild(detail);
          button.onclick = () => run(async () => {
            applyWorkstreamSelection(item);
            await refreshPending();
            await refreshAudit();
            renderStatusSummary(state.statusSnapshot || status);
            renderRelationView();
          });
          box.appendChild(button);
        });
      }

      function statusSummaryLabels(status, detail, subscribers) {
        const guard = detail && detail.auto_forward_guard ? detail.auto_forward_guard : null;
        const healthState = detail && detail.health && detail.health.state ? String(detail.health.state) : 'ok';
        const healthLabel = healthState === 'critical'
          ? t('fleet.healthCritical')
          : (healthState === 'warn' ? t('fleet.healthWarn') : t('fleet.healthOk'));
        const escalationMode = detail && detail.health && detail.health.escalation ? String(detail.health.escalation) : 'observe';
        const escalationLabel = escalationMode === 'intervene'
          ? t('fleet.escalateIntervene')
          : (escalationMode === 'review' ? t('fleet.escalateReview') : '');
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
        if (status && status.security && status.security.support_tier) {
          labels.push(format('cards.statusBadgeSecurity', { tier: status.security.support_tier }));
        }
        if (detail && detail.health && detail.health.state && detail.health.state !== 'ok') {
          labels.push(format('cards.statusBadgeHealth', { state: healthLabel }));
        }
        if (detail && detail.health && detail.health.escalation && detail.health.escalation !== 'observe' && escalationLabel) {
          labels.push(format('cards.statusBadgeEscalation', { mode: escalationLabel }));
        }
        return labels;
      }

      function renderStatusSummary(status) {
        const box = $('status-badges');
        box.innerHTML = '';
        renderWorkstreamFleet(status);
        const note = $('status-note');
        if (note) {
          const active = inferBridgeDetail(status);
          const quotaReason = active && active.auto_forward_guard && active.auto_forward_guard.quota_reason
            ? String(active.auto_forward_guard.quota_reason)
            : '';
          const dependencyBlocker = workstreamDependencyBlocker(active);
          const alertSummary = active && active.health && active.health.summary && active.health.state !== 'ok'
            ? String(active.health.summary)
            : '';
          const warnings = Array.isArray(status && status.security && status.security.warnings)
            ? status.security.warnings
            : [];
          note.textContent = quotaReason || dependencyBlocker || alertSummary || (warnings.length ? warnings[0] : t('cards.statusNote'));
        }
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
        renderWorkspaceTabs();
        renderWorkspaceStrip();
        renderInspectSummary(status);
      }

      function inferBridgeId(status) {
        const detail = inferBridgeDetail(status);
        if (detail) return detail.bridge_id || '';
        return '';
      }

      function inferBridgeDetail(status) {
        const workstream = inferWorkstream(status);
        if (workstream) return workstream;
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

      function relationStateName(flags) {
        if (flags && flags.attention) return 'attention';
        if (flags && flags.active) return 'active';
        if (flags && flags.standby) return 'standby';
        return 'muted';
      }

      function relationBooleanLabel(value, onKey, offKey) {
        return value ? t('relation.' + onKey) : t('relation.' + offKey);
      }

      function relationStatusLabel(name) {
        return t('relation.' + name);
      }

      function relationLedTone(stateName) {
        if (stateName === 'active') return 'ok';
        if (stateName === 'attention' || stateName === 'standby') return 'warn';
        return 'down';
      }

      function relationToggleLabel(value, onKey, offKey) {
        return value ? t('relation.' + onKey) : t('relation.' + offKey);
      }

      function toggleRelationSetting(name) {
        if (name === 'auto-forward') {
          $('auto-forward').checked = !$('auto-forward').checked;
          syncMetrics();
          return;
        }
        if (name === 'intervention') {
          $('intervention').checked = !$('intervention').checked;
          syncMetrics();
        }
      }

      function setRelationFocus(focus) {
        state.relationFocus = focus || null;
        renderRelationView();
      }

      function addRelationFact(container, label, value) {
        const item = document.createElement('span');
        item.className = 'relation-fact';
        const key = document.createElement('strong');
        key.textContent = label;
        const text = document.createElement('span');
        text.textContent = value;
        item.appendChild(key);
        item.appendChild(text);
        container.appendChild(item);
      }

      function addRelationBadge(container, label, value, stateName) {
        const badge = document.createElement('span');
        badge.className = 'badge is-' + stateName;
        const strong = document.createElement('strong');
        strong.textContent = label;
        const text = document.createElement('span');
        text.textContent = value;
        badge.appendChild(strong);
        badge.appendChild(text);
        container.appendChild(badge);
        return badge;
      }

      function addSpotlightFact(container, label, value) {
        const item = document.createElement('div');
        item.className = 'relation-spotlight-fact';
        const key = document.createElement('strong');
        key.textContent = label;
        const text = document.createElement('span');
        text.textContent = value;
        item.appendChild(key);
        item.appendChild(text);
        container.appendChild(item);
      }

      function relationNodeFocusTarget(key) {
        if (key === 'room') return { tab: 'workflow', targetId: 'live-card' };
        if (key === 'review') return { tab: 'review', targetId: 'pending-card', openId: 'pending-details' };
        if (key === 'audit') return { tab: 'inspect', targetId: 'diagnostics-card', openId: 'diagnostics-details' };
        if (key === 'mcp' || key === 'server') return { tab: 'inspect', targetId: 'status-card', openId: 'status-details' };
        if (key === 'host' || key === 'guest') return { tab: 'workflow', targetId: 'launch-card', openId: 'launch-advanced' };
        if (key === 'bridge' || key === 'gui') return { tab: 'workflow', targetId: 'launch-card' };
        return { tab: 'topology', targetId: 'relation-card', openId: 'relation-details' };
      }

      function addRelationNode(container, definition) {
        const node = document.createElement('div');
        node.className = 'relation-node is-' + definition.state;
        if (state.relationFocus && state.relationFocus.kind === 'node' && state.relationFocus.key === definition.key) {
          node.classList.add('is-selected');
        }
        node.style.left = String((definition.x / RELATION_CANVAS.width) * 100) + '%';
        node.style.top = String((definition.y / RELATION_CANVAS.height) * 100) + '%';
        node.dataset.nodeKey = definition.key;
        node.setAttribute('role', 'button');
        node.setAttribute('tabindex', '0');

        const head = document.createElement('div');
        head.className = 'relation-node-head';
        const stateWrap = document.createElement('div');
        stateWrap.className = 'relation-node-state';
        const led = document.createElement('span');
        led.className = 'status-led is-' + relationLedTone(definition.state);
        const tag = document.createElement('div');
        tag.className = 'relation-node-tag';
        tag.textContent = t('relation.' + definition.state);
        stateWrap.appendChild(led);
        stateWrap.appendChild(tag);
        head.appendChild(stateWrap);

        const title = document.createElement('strong');
        title.textContent = definition.title;

        const detail = document.createElement('span');
        detail.textContent = definition.detail;

        node.appendChild(head);
        node.appendChild(title);
        node.appendChild(detail);

        if (definition.code) {
          const code = document.createElement('code');
          code.textContent = definition.code;
          node.appendChild(code);
        }

        if (Array.isArray(definition.controls) && definition.controls.length) {
          const actions = document.createElement('div');
          actions.className = 'relation-node-actions';
          for (const control of definition.controls) {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'relation-node-action is-' + (control.on ? 'on' : 'off');
            button.dataset.controlAction = control.action;
            button.dataset.nodeKey = definition.key;
            button.setAttribute('aria-pressed', control.on ? 'true' : 'false');
            const label = document.createElement('strong');
            label.textContent = control.label;
            const value = document.createElement('em');
            value.textContent = control.value;
            button.appendChild(label);
            button.appendChild(value);
            actions.appendChild(button);
          }
          node.appendChild(actions);
        }

        container.appendChild(node);
      }

      function relationLinkGeometry(definition, start, end) {
        const halfWidth = RELATION_NODE_BOX.width / 2;
        const halfHeight = RELATION_NODE_BOX.height / 2;
        const horizontal = Math.abs(end.x - start.x) >= Math.abs(end.y - start.y);
        if (!horizontal) {
          const source = {
            x: start.x,
            y: start.y + (end.y >= start.y ? halfHeight : -halfHeight),
          };
          const target = {
            x: end.x,
            y: end.y - (end.y >= start.y ? halfHeight : -halfHeight),
          };
          const drift = definition.routeDrift || (end.x >= start.x ? 24 : -24);
          const controlY = (source.y + target.y) / 2 + (definition.routeLift || 0);
          const controlX = source.x + drift;
          return {
            source,
            target,
            label: { x: ((source.x + target.x) / 2) + drift * 0.35, y: controlY - 10 },
            d: 'M' + source.x + ' ' + source.y
              + ' C ' + controlX + ' ' + controlY
              + ', ' + (target.x - drift) + ' ' + controlY
              + ', ' + target.x + ' ' + target.y,
          };
        }
        const source = {
          x: start.x + (end.x >= start.x ? halfWidth : -halfWidth),
          y: start.y,
        };
        const target = {
          x: end.x - (end.x >= start.x ? halfWidth : -halfWidth),
          y: end.y,
        };
        const spread = Math.max(54, Math.abs(target.x - source.x) * 0.26);
        const lift = definition.routeLift || 0;
        const direction = end.x >= start.x ? 1 : -1;
        const c1x = source.x + spread * direction;
        const c2x = target.x - spread * direction;
        const c1y = source.y + lift;
        const c2y = target.y + lift;
        return {
          source,
          target,
          label: { x: (source.x + target.x) / 2, y: ((source.y + target.y) / 2) + lift * 0.55 - 8 },
          d: 'M' + source.x + ' ' + source.y
            + ' C ' + c1x + ' ' + c1y
            + ', ' + c2x + ' ' + c2y
            + ', ' + target.x + ' ' + target.y,
        };
      }

      function addRelationLink(svg, definition) {
        const start = RELATION_POSITIONS[definition.from];
        const end = RELATION_POSITIONS[definition.to];
        if (!start || !end) return;
        const geometry = relationLinkGeometry(definition, start, end);

        const group = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        group.setAttribute('class', 'relation-link-group');
        group.dataset.linkKey = definition.key || '';
        if (state.relationFocus && state.relationFocus.kind === 'link' && state.relationFocus.key === definition.key) {
          group.classList.add('is-selected');
        }

        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        path.setAttribute('d', geometry.d);
        path.setAttribute('class', 'relation-link is-' + definition.state);
        group.appendChild(path);

        for (const point of [geometry.source, geometry.target]) {
          const pin = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
          pin.setAttribute('cx', String(point.x));
          pin.setAttribute('cy', String(point.y));
          pin.setAttribute('r', '5.5');
          pin.setAttribute('class', 'relation-pin is-' + definition.state);
          group.appendChild(pin);
        }

        if (definition.label) {
          const badge = document.createElementNS('http://www.w3.org/2000/svg', 'g');
          badge.setAttribute('class', 'relation-link-badge is-' + definition.state);
          const x = geometry.label.x + (definition.dx || 0);
          const y = geometry.label.y + (definition.dy || 0);
          const width = Math.max(78, definition.label.length * 7.2 + 18);
          const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
          rect.setAttribute('x', String(x - width / 2));
          rect.setAttribute('y', String(y - 12));
          rect.setAttribute('width', String(width));
          rect.setAttribute('height', '24');
          const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
          text.setAttribute('x', String(x));
          text.setAttribute('y', String(y + 4));
          text.setAttribute('text-anchor', 'middle');
          text.textContent = definition.label;
          badge.appendChild(rect);
          badge.appendChild(text);
          group.appendChild(badge);
        }

        svg.appendChild(group);
      }

      function addRelationLedgerItem(container, definition, nodes) {
        const item = document.createElement('div');
        item.className = 'relation-link-item is-' + definition.state;
        if (state.relationFocus && state.relationFocus.kind === 'link' && state.relationFocus.key === definition.key) {
          item.classList.add('is-selected');
        }
        item.dataset.linkKey = definition.key || '';
        item.setAttribute('role', 'button');
        item.setAttribute('tabindex', '0');

        const title = document.createElement('strong');
        title.textContent = nodes[definition.from].title + ' -> ' + nodes[definition.to].title;

        const route = document.createElement('span');
        route.textContent = definition.label + ' · ' + relationStatusLabel(definition.state);

        item.appendChild(title);
        item.appendChild(route);

        if (definition.detail) {
          const detail = document.createElement('span');
          detail.textContent = definition.detail;
          item.appendChild(detail);
        }

        container.appendChild(item);
      }

      function addRuntimeLine(container, label, value) {
        const item = document.createElement('span');
        item.className = 'runtime-list';
        const key = document.createElement('b');
        key.textContent = label;
        const text = document.createElement('em');
        text.textContent = value;
        item.appendChild(key);
        item.appendChild(text);
        container.appendChild(item);
      }

      function addRuntimeCard(container, options) {
        const card = document.createElement('section');
        card.className = 'runtime-card is-' + options.state;
        const head = document.createElement('div');
        head.className = 'runtime-card-head';
        const led = document.createElement('span');
        led.className = 'status-led is-' + relationLedTone(options.state);
        const title = document.createElement('strong');
        title.textContent = options.title;
        head.appendChild(title);
        head.appendChild(led);
        const summary = document.createElement('span');
        summary.textContent = options.summary;
        card.appendChild(head);
        card.appendChild(summary);
        if (options.drift) {
          const drift = document.createElement('span');
          drift.className = 'runtime-drift';
          drift.textContent = options.drift;
          card.appendChild(drift);
        }
        const list = document.createElement('div');
        list.className = 'runtime-list-wrap';
        for (const line of options.lines) addRuntimeLine(list, line.label, line.value);
        card.appendChild(list);
        container.appendChild(card);
      }

      function relationSpotlightPayload(context) {
        const focus = state.relationFocus;
        if (!focus || !context) return null;
        if (focus.kind === 'node') {
          const node = context.nodeMap[focus.key];
          if (!node) return null;
          return {
            title: node.title,
            state: relationStatusLabel(node.state),
            copy: node.detail,
            code: node.code || '',
            target: relationNodeFocusTarget(node.key),
            facts: [
              { label: t('relation.runtime'), value: relationStatusLabel(node.state) },
              { label: t('relation.profile'), value: context.bridgeProfile || context.profileName },
              { label: t('relation.room'), value: context.roomId || t('relation.none') },
              { label: t('relation.pending'), value: format('relation.pendingCount', { count: context.pendingCount }) },
            ],
          };
        }
        if (focus.kind === 'link') {
          const link = context.linkMap[focus.key];
          if (!link) return null;
          return {
            title: context.nodeMap[link.from].title + ' -> ' + context.nodeMap[link.to].title,
            state: relationStatusLabel(link.state),
            copy: link.detail || link.label,
            code: link.label,
            target: relationNodeFocusTarget(link.to),
            facts: [
              { label: t('relation.transport'), value: context.transportLabel },
              { label: t('fields.deliver'), value: context.deliverLabel },
              { label: t('relation.guard'), value: context.guardLabel },
              { label: t('relation.pending'), value: format('relation.pendingCount', { count: context.pendingCount }) },
            ],
          };
        }
        if (focus.kind === 'badge') {
          const badge = context.badgeMap[focus.key];
          if (!badge) return null;
          return {
            title: badge.label,
            state: relationStatusLabel(badge.state),
            copy: badge.copy,
            code: badge.value,
            target: badge.target,
            facts: badge.facts,
          };
        }
        return null;
      }

      function renderRelationSpotlight(context) {
        const title = $('relation-spotlight-title');
        const stateBox = $('relation-spotlight-state');
        const copy = $('relation-spotlight-copy');
        const code = $('relation-spotlight-code');
        const facts = $('relation-spotlight-facts');
        const jump = $('relation-spotlight-jump');
        if (!stateBox || !copy || !code || !facts || !jump) return;
        facts.replaceChildren();
        const payload = relationSpotlightPayload(context);
        if (!payload) {
          if (title) title.textContent = t('cards.relationSpotlightTitle');
          stateBox.textContent = t('relation.active');
          copy.textContent = t('cards.relationSpotlightCopy');
          code.textContent = '';
          code.classList.add('hidden');
          jump.disabled = true;
          return;
        }
        if (title) title.textContent = payload.title;
        stateBox.textContent = payload.state;
        copy.textContent = payload.copy;
        if (payload.code) {
          code.textContent = payload.code;
          code.classList.remove('hidden');
        } else {
          code.textContent = '';
          code.classList.add('hidden');
        }
        for (const fact of payload.facts) addSpotlightFact(facts, fact.label, fact.value);
        jump.disabled = false;
        jump.onclick = () => focusControlArea(payload.target.targetId, payload.target.tab, payload.target);
      }

      function renderRelationView() {
        const diagram = $('relation-diagram');
        const svg = $('relation-lines');
        const facts = $('relation-facts');
        const badges = $('relation-badges');
        const ledger = $('relation-ledger');
        const compare = $('relation-compare');
        if (!diagram || !svg || !facts || !badges || !ledger || !compare) return;

        syncRelationControls();

        const status = state.statusSnapshot || {};
        const detail = inferBridgeDetail(status);
        const rooms = Array.isArray(status && status.rooms) ? status.rooms : [];
        const preset = PRESETS[state.preset] || PRESETS.quick;
        const presetLabel = t('presets.' + state.preset + '.label');
        const bridgeId = $('bridge-id').value.trim() || (bridgeIsActive(detail) ? (detail && detail.bridge_id) : '') || '';
        const roomId = $('room-id').value.trim() || (detail && detail.room_id) || '';
        const hostPane = $('pane-a').value.trim() || (detail && detail.pane_a) || '';
        const guestPane = $('pane-b').value.trim() || (detail && detail.pane_b) || '';
        const backendName = $('backend').value.trim() || t('relation.direct');
        const profileName = $('profile').value.trim() || 'generic';
        const transportMode = $('transport').value.trim() || 'sse';
        const deliverLabel = deliverName($('deliver').value.trim());
        const room = rooms.find(item => item && item.id === roomId) || (rooms.length === 1 ? rooms[0] : null);
        const subscribers = room && room.subscribers ? room.subscribers : { total: 0, sse: 0, websocket: 0 };
        const pendingCount = detail ? Number(detail.pending_count || 0) : (Number($('metric-pending').textContent || '0') || 0);
        const guard = detail && detail.auto_forward_guard ? detail.auto_forward_guard : state.guard;
        const audit = state.audit || status.audit || {};
        const runtime = status.runtime || {};
        const bridgeProfile = detail && detail.profile ? String(detail.profile) : profileName;
        const bridgeAutoForward = detail ? Boolean(detail.auto_forward) : $('auto-forward').checked;
        const bridgeIntervention = detail ? Boolean(detail.intervention) : $('intervention').checked;
        const relationNote = $('relation-note');
        const mcpFocused = state.preset === 'mcp' || state.preset === 'mission';
        const roomActive = Boolean(roomId);
        const bridgeActive = Boolean(bridgeId);
        const hasPanes = Boolean(hostPane && guestPane);
        const reviewEnabled = bridgeActive ? bridgeIntervention : $('intervention').checked;
        const reviewAttention = Boolean((guard && guard.blocked) || pendingCount > 0);
        const auditActive = Boolean(audit && audit.enabled);
        const transportLabel = transportName(transportMode);
        const guardLabel = guard && guard.blocked ? t('relation.attention') : (reviewEnabled ? t('relation.standby') : t('relation.muted'));
        const relayLabel = bridgeAutoForward ? 'MSG relay' : 'manual relay';
        const reviewLabel = bridgeIntervention ? 'intervention' : 'review off';
        const configDrift = Boolean(
          bridgeActive
          && detail
          && (
            bridgeProfile !== profileName
            || bridgeAutoForward !== $('auto-forward').checked
            || bridgeIntervention !== $('intervention').checked
          )
        );

        relationNote.textContent = configDrift
          ? format('cards.relationNoteLive', {
              profile: bridgeProfile,
              autoForward: relationBooleanLabel(bridgeAutoForward, 'autoForwardOn', 'autoForwardOff'),
              intervention: relationBooleanLabel(bridgeIntervention, 'reviewOn', 'reviewOff'),
            })
          : t('cards.relationNote');

        svg.replaceChildren();
        diagram.querySelectorAll('.relation-node').forEach(node => node.remove());
        badges.replaceChildren();
        facts.replaceChildren();
        ledger.replaceChildren();
        compare.replaceChildren();

        addRuntimeCard(compare, {
          title: t('cards.relationConfigTitle'),
          summary: t('cards.relationConfigCopy'),
          state: configDrift ? 'attention' : 'active',
          lines: [
            { label: t('relation.profile'), value: profileName },
            { label: t('relation.transport'), value: transportName(transportMode) },
            { label: t('fields.deliver'), value: deliverLabel },
            {
              label: t('relation.autoForwardLabel'),
              value: relationBooleanLabel($('auto-forward').checked, 'autoForwardOn', 'autoForwardOff')
            },
            {
              label: t('relation.reviewMode'),
              value: relationBooleanLabel($('intervention').checked, 'reviewOn', 'reviewOff')
            },
          ],
          drift: configDrift ? t('cards.relationDriftLaunch') : ''
        });
        addRuntimeCard(compare, {
          title: t('cards.relationFactsTitle'),
          summary: t('cards.relationFactsCopy'),
          state: bridgeActive || roomActive ? (configDrift ? 'attention' : 'active') : 'muted',
          lines: [
            { label: t('relation.profile'), value: bridgeActive ? bridgeProfile : t('relation.none') },
            { label: t('relation.room'), value: roomActive ? roomId : t('relation.none') },
            { label: t('relation.bridge'), value: bridgeActive ? bridgeId : t('relation.none') },
            {
              label: t('relation.autoForwardLabel'),
              value: relationBooleanLabel(bridgeAutoForward, 'autoForwardOn', 'autoForwardOff')
            },
            {
              label: t('relation.reviewMode'),
              value: relationBooleanLabel(bridgeIntervention, 'reviewOn', 'reviewOff')
            },
          ],
          drift: configDrift ? t('cards.relationDriftRuntime') : ''
        });

        const nodes = [
          {
            key: 'gui',
            state: relationStateName({ active: true }),
            title: t('relation.gui'),
            detail: t('relation.guiDetail'),
            code: state.layout + ' / ' + state.locale,
          },
          {
            key: 'mcp',
            state: relationStateName({ active: mcpFocused, standby: !mcpFocused }),
            title: t('relation.mcp'),
            detail: t('relation.mcpDetail'),
            code: mcpFocused ? '/mcp' : '',
          },
          {
            key: 'audit',
            state: relationStateName({
              active: auditActive,
              standby: !auditActive && (preset.showDiagnostics || state.preset === 'mission'),
            }),
            title: t('relation.audit'),
            detail: auditActive
              ? format('relation.auditOn', { mode: String((audit.redaction && audit.redaction.mode) || 'default') })
              : t('relation.auditOff'),
            code: auditActive ? String(audit.file || audit.root || '') : '',
          },
          {
            key: 'server',
            state: relationStateName({ active: true }),
            title: t('relation.server'),
            detail: t('relation.serverDetail'),
            code: String(runtime.launch_mode || t('relation.direct')),
          },
          {
            key: 'room',
            state: relationStateName({ active: roomActive, standby: !roomActive }),
            title: t('relation.room'),
            detail: roomActive ? format('relation.subscribers', { total: subscribers.total || 0 }) : t('relation.none'),
            code: roomId,
          },
          {
            key: 'review',
            state: relationStateName({
              attention: reviewAttention,
              active: reviewEnabled,
              standby: !reviewEnabled && preset.showPending,
            }),
            title: t('relation.review'),
            detail: reviewAttention
              ? format('relation.pendingCount', { count: pendingCount })
              : (reviewEnabled ? t('relation.reviewDetail') : t('relation.reviewOff')),
            code: guard && guard.guard_reason ? String(guard.guard_reason) : '',
            controls: [
              {
                action: 'intervention',
                label: t('relation.reviewShort'),
                value: relationToggleLabel(bridgeIntervention, 'reviewOn', 'reviewOff'),
                on: bridgeIntervention,
              },
            ],
          },
          {
            key: 'bridge',
            state: relationStateName({ active: bridgeActive, standby: !bridgeActive && hasPanes }),
            title: t('relation.bridge'),
            detail: bridgeActive ? t('relation.bridgeDetail') : t('relation.launchConfig'),
            code: bridgeId,
            controls: [
              {
                action: 'auto-forward',
                label: t('relation.autoForwardShort'),
                value: relationToggleLabel(bridgeAutoForward, 'autoForwardOn', 'autoForwardOff'),
                on: bridgeAutoForward,
              },
            ],
          },
          {
            key: 'host',
            state: relationStateName({ active: Boolean(hostPane && bridgeActive), standby: Boolean(hostPane && !bridgeActive) }),
            title: t('relation.host'),
            detail: hostPane ? t('fields.paneHost') : t('metrics.notReady'),
            code: hostPane,
          },
          {
            key: 'guest',
            state: relationStateName({ active: Boolean(guestPane && bridgeActive), standby: Boolean(guestPane && !bridgeActive) }),
            title: t('relation.guest'),
            detail: guestPane ? t('fields.paneGuest') + ' · ' + bridgeProfile : t('metrics.notReady'),
            code: guestPane,
          },
        ];

        const nodeMap = Object.fromEntries(nodes.map(node => [node.key, node]));

        const links = [
          {
            key: 'gui-server',
            from: 'gui',
            to: 'server',
            label: 'tools/call',
            state: 'active',
            routeLift: -18,
            dx: 0,
            dy: -4,
            detail: t('relation.gui') + ' -> ' + t('relation.server') + ' JSON-RPC',
          },
          {
            key: 'mcp-server',
            from: 'mcp',
            to: 'server',
            label: 'HTTP /mcp',
            state: mcpFocused ? 'active' : 'standby',
            routeLift: 0,
            dx: -4,
            dy: 0,
            detail: t('relation.mcp') + ' endpoint /mcp',
          },
          {
            key: 'server-room',
            from: 'server',
            to: 'room',
            label: 'room state',
            state: roomActive ? 'active' : 'standby',
            routeLift: 16,
            dx: 0,
            dy: 2,
            detail: roomActive ? roomId : t('relation.none'),
          },
          {
            key: 'gui-room',
            from: 'gui',
            to: 'room',
            label: transportLabel,
            state: roomActive ? 'active' : 'standby',
            routeLift: -34,
            dx: 0,
            dy: -4,
            detail: format('relation.subscribers', { total: subscribers.total || 0 }),
          },
          {
            key: 'room-bridge',
            from: 'room',
            to: 'bridge',
            label: relayLabel,
            state: bridgeActive && roomActive ? (reviewAttention ? 'attention' : 'active') : 'standby',
            routeLift: -18,
            dx: 0,
            dy: -2,
            detail: relationBooleanLabel(bridgeAutoForward, 'autoForwardOn', 'autoForwardOff'),
          },
          {
            key: 'bridge-host',
            from: 'bridge',
            to: 'host',
            label: 'pane A',
            state: hostPane ? (bridgeActive ? 'active' : 'standby') : 'muted',
            routeLift: -22,
            dx: 0,
            dy: -2,
            detail: hostPane || t('metrics.notReady'),
          },
          {
            key: 'bridge-guest',
            from: 'bridge',
            to: 'guest',
            label: 'pane B',
            state: guestPane ? (bridgeActive ? 'active' : 'standby') : 'muted',
            routeLift: 22,
            dx: 0,
            dy: 2,
            detail: bridgeProfile + ' · ' + (guestPane || t('metrics.notReady')),
          },
          {
            key: 'bridge-review',
            from: 'bridge',
            to: 'review',
            label: reviewLabel,
            state: reviewAttention ? 'attention' : (reviewEnabled ? 'active' : 'standby'),
            routeLift: 28,
            routeDrift: -32,
            dx: 12,
            dy: 0,
            detail: format('relation.pendingCount', { count: pendingCount }),
          },
          {
            key: 'server-audit',
            from: 'server',
            to: 'audit',
            label: auditActive ? 'TB2_AUDIT' : t('relation.auditOff'),
            state: auditActive ? 'active' : (preset.showDiagnostics || state.preset === 'mission' ? 'standby' : 'muted'),
            routeLift: 18,
            routeDrift: -28,
            dx: 12,
            dy: 0,
            detail: auditActive ? String(audit.file || audit.root || '') : t('relation.auditOff'),
          },
        ];

        for (const link of links) addRelationLink(svg, link);
        for (const node of nodes) {
          const position = RELATION_POSITIONS[node.key];
          addRelationNode(diagram, Object.assign({}, node, position));
        }

        const linkMap = Object.fromEntries(links.map(link => [link.key, link]));
        if (!state.relationFocus) {
          const preferredNode = nodes.find(node => node.state === 'attention')
            || nodes.find(node => node.state === 'active' && node.key === 'bridge')
            || nodes.find(node => node.state === 'active');
          if (preferredNode) state.relationFocus = { kind: 'node', key: preferredNode.key };
        }

        const activeNodes = nodes.filter(node => node.state === 'active' || node.state === 'attention').length;
        const liveLinks = links.filter(link => link.state === 'active' || link.state === 'attention').length;
        $('relation-summary-meta').textContent = format('cards.relationMeta', {
          preset: presetLabel,
          links: liveLinks,
        });

        const badgeDefinitions = [
          {
            key: 'preset',
            label: t('badges.preset'),
            value: presetLabel,
            state: relationStateName({ active: true }),
            copy: t('presets.' + state.preset + '.summary'),
            target: { tab: 'workflow', targetId: 'launch-card' },
            facts: [
              { label: t('strip.preset'), value: presetLabel },
              { label: t('relation.runtime'), value: String(runtime.launch_mode || t('relation.direct')) },
            ],
          },
          {
            key: 'runtime',
            label: t('relation.runtime'),
            value: String(runtime.launch_mode || t('relation.direct')),
            state: relationStateName({ active: true }),
            copy: t('cards.relationFactsCopy'),
            target: relationNodeFocusTarget('server'),
            facts: [
              { label: t('relation.runtime'), value: String(runtime.launch_mode || t('relation.direct')) },
              { label: t('relation.continuity'), value: String(runtime.continuity && runtime.continuity.mode ? runtime.continuity.mode : t('relation.direct')) },
            ],
          },
          {
            key: 'transport',
            label: t('relation.transport'),
            value: transportLabel,
            state: relationStateName({ active: roomActive, standby: !roomActive }),
            copy: t('relation.roomDetail'),
            target: relationNodeFocusTarget('room'),
            facts: [
              { label: t('relation.room'), value: roomId || t('relation.none') },
              { label: t('relation.subscribersLabel'), value: format('relation.subscribers', { total: subscribers.total || 0 }) },
            ],
          },
          {
            key: 'pending',
            label: t('relation.pending'),
            value: format('relation.pendingCount', { count: pendingCount }),
            state: relationStateName({ attention: pendingCount > 0, active: pendingCount === 0 && reviewEnabled, standby: pendingCount === 0 && !reviewEnabled }),
            copy: t('cards.reviewCopy'),
            target: relationNodeFocusTarget('review'),
            facts: [
              { label: t('relation.pending'), value: format('relation.pendingCount', { count: pendingCount }) },
              { label: t('relation.guard'), value: guardLabel },
            ],
          },
          {
            key: 'audit',
            label: t('relation.audit'),
            value: auditActive ? format('relation.auditOn', { mode: String((audit.redaction && audit.redaction.mode) || 'default') }) : t('relation.auditOff'),
            state: relationStateName({ active: auditActive, standby: !auditActive && (preset.showDiagnostics || state.preset === 'mission') }),
            copy: t('cards.auditDisabled'),
            target: relationNodeFocusTarget('audit'),
            facts: [
              { label: t('relation.audit'), value: auditActive ? format('relation.auditOn', { mode: String((audit.redaction && audit.redaction.mode) || 'default') }) : t('relation.auditOff') },
              { label: t('relation.runtime'), value: auditActive ? String(audit.file || audit.root || '') : t('relation.none') },
            ],
          },
          {
            key: 'coverage',
            label: t('cards.relationTitle'),
            value: String(activeNodes) + '/9 active',
            state: relationStateName({ active: bridgeActive || roomActive, standby: !bridgeActive && hasPanes }),
            copy: t('cards.relationLedgerCopy'),
            target: { tab: 'topology', targetId: 'relation-card', openId: 'relation-details' },
            facts: [
              { label: t('relation.pending'), value: format('relation.pendingCount', { count: pendingCount }) },
              { label: t('relation.transport'), value: transportLabel },
            ],
          },
        ];
        const badgeMap = Object.fromEntries(badgeDefinitions.map(badge => [badge.key, badge]));
        for (const badgeDefinition of badgeDefinitions) {
          const badge = addRelationBadge(badges, badgeDefinition.label, badgeDefinition.value, badgeDefinition.state);
          badge.dataset.badgeKey = badgeDefinition.key;
          badge.setAttribute('role', 'button');
          badge.setAttribute('tabindex', '0');
          if (state.relationFocus && state.relationFocus.kind === 'badge' && state.relationFocus.key === badgeDefinition.key) {
            badge.classList.add('is-selected');
          }
        }

        addRelationFact(facts, t('relation.runtime'), String(runtime.launch_mode || t('relation.direct')));
        addRelationFact(
          facts,
          t('relation.continuity'),
          String(runtime.continuity && runtime.continuity.mode ? runtime.continuity.mode : t('relation.direct'))
        );
        addRelationFact(facts, t('relation.profile'), bridgeActive ? bridgeProfile : profileName);
        addRelationFact(facts, t('relation.transport'), transportName(transportMode));
        addRelationFact(facts, t('relation.room'), roomActive ? roomId : t('relation.none'));
        addRelationFact(facts, t('relation.bridge'), bridgeActive ? bridgeId : t('relation.none'));
        addRelationFact(
          facts,
          t('relation.autoForwardLabel'),
          relationBooleanLabel(bridgeAutoForward, 'autoForwardOn', 'autoForwardOff')
        );
        addRelationFact(
          facts,
          t('relation.reviewMode'),
          relationBooleanLabel(bridgeIntervention, 'reviewOn', 'reviewOff')
        );
        addRelationFact(facts, t('relation.pending'), format('relation.pendingCount', { count: pendingCount }));
        addRelationFact(facts, t('relation.subscribersLabel'), format('relation.subscribers', { total: subscribers.total || 0 }));
        addRelationFact(
          facts,
          t('relation.audit'),
          auditActive ? format('relation.auditOn', { mode: String((audit.redaction && audit.redaction.mode) || 'default') }) : t('relation.auditOff')
        );
        addRelationFact(
          facts,
          t('relation.guard'),
          guardLabel
        );

        for (const link of links) addRelationLedgerItem(ledger, link, nodeMap);
        renderRelationSpotlight({
          nodeMap,
          linkMap,
          badgeMap,
          profileName,
          bridgeProfile,
          roomId,
          pendingCount,
          transportLabel,
          deliverLabel,
          guardLabel,
        });
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
            const selected = inferWorkstream(state.statusSnapshot || {});
            if (selected && Array.isArray(selected.pending)) {
              fillPending(selected.pending);
            } else {
              fillPending([]);
            }
            syncMetrics();
            return { pending: selected && Array.isArray(selected.pending) ? selected.pending : [], count: selected ? Number(selected.pending_count || 0) : 0 };
          }
          throw err;
        }
        if (res.bridge_id) $('bridge-id').value = res.bridge_id;
        fillPending(res.pending || []);
        return res;
      }

      async function refreshStatus() {
        const res = await tool('status', {});
        state.statusSnapshot = res;
        const selected = inferWorkstream(res);
        if (selected) applyWorkstreamSelection(selected);
        const detail = inferBridgeDetail(res);
        const inferred = bridgeIsActive(detail) && detail ? (detail.bridge_id || '') : '';
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
        if (state.selectedWorkstreamId.trim()) args.workstream_id = state.selectedWorkstreamId.trim();
        const res = await tool('bridge_start', args);
        state.selectedWorkstreamId = String(res.workstream_id || state.selectedWorkstreamId || '');
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

      async function pauseReview() {
        const res = await tool('workstream_pause_review', requireWorkstreamTarget());
        await refreshReviewState();
        log(t('logs.reviewPaused'));
        return res;
      }

      async function resumeReview() {
        const res = await tool('workstream_resume_review', requireWorkstreamTarget());
        await refreshReviewState();
        log(t('logs.reviewResumed'));
        return res;
      }

      async function stopWorkstream() {
        const res = await tool('workstream_stop', Object.assign({ cascade: true }, requireWorkstreamTarget()));
        if (res.bridge_stopped) stopTransport();
        if (res.workstream_removed) clearBridgeState();
        await refreshReviewState();
        const removedCount = Array.isArray(res.removed) && res.removed.length ? res.removed.length : 1;
        log(format('logs.workstreamStopped', { count: removedCount }));
        return res;
      }

      async function reconcileFleet() {
        const res = await tool('fleet_reconcile', { apply: true });
        if (state.selectedWorkstreamId && Array.isArray(res.dropped_workstreams) && res.dropped_workstreams.includes(state.selectedWorkstreamId)) {
          stopTransport();
          clearBridgeState();
        }
        await refreshReviewState();
        log(format('logs.fleetReconciled', {
          workstreams: Array.isArray(res.dropped_workstreams) ? res.dropped_workstreams.length : 0,
          rooms: Array.isArray(res.deleted_rooms) ? res.deleted_rooms.length : 0,
        }));
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
        document.querySelectorAll('[data-workspace-tab]').forEach(button => {
          button.addEventListener('click', () => setWorkspaceTab(button.dataset.workspaceTab));
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
        $('pause-review').onclick = () => run(pauseReview);
        $('resume-review').onclick = () => run(resumeReview);
        $('stop-workstream').onclick = () => run(stopWorkstream);
        $('reconcile-fleet').onclick = () => run(reconcileFleet);
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
        ['backend', 'profile', 'deliver', 'auto-forward', 'intervention'].forEach(id => {
          $(id).addEventListener('change', () => syncMetrics());
        });
        $('relation-backend').onchange = () => {
          $('backend').value = $('relation-backend').value;
          syncMetrics();
        };
        $('relation-profile').onchange = () => {
          $('profile').value = $('relation-profile').value;
          syncMetrics();
        };
        $('relation-transport').onchange = () => {
          $('transport').value = $('relation-transport').value;
          $('transport').dispatchEvent(new Event('change'));
        };
        $('relation-deliver').onchange = () => {
          $('deliver').value = $('relation-deliver').value;
          syncMetrics();
        };
        $('relation-auto-forward').onchange = () => {
          $('auto-forward').checked = $('relation-auto-forward').checked;
          syncMetrics();
        };
        $('relation-intervention').onchange = () => {
          $('intervention').checked = $('relation-intervention').checked;
          syncMetrics();
        };
        $('relation-refresh').onclick = () => run(refreshStatus);
        $('pending-select').onchange = () => renderPendingDetail();
        $('pending-edit').addEventListener('input', () => renderReviewSummary());
        $('relation-diagram').addEventListener('click', event => {
          const action = event.target.closest('.relation-node-action');
          if (action) {
            toggleRelationSetting(action.dataset.controlAction || '');
            setRelationFocus({ kind: 'node', key: action.dataset.nodeKey || '' });
            return;
          }
          const node = event.target.closest('.relation-node');
          if (!node) return;
          setRelationFocus({ kind: 'node', key: node.dataset.nodeKey || '' });
          const target = relationNodeFocusTarget(node.dataset.nodeKey || '');
          focusControlArea(target.targetId, target.tab, target);
        });
        $('relation-diagram').addEventListener('keydown', event => {
          const action = event.target.closest('.relation-node-action');
          if (action && (event.key === 'Enter' || event.key === ' ')) {
            event.preventDefault();
            toggleRelationSetting(action.dataset.controlAction || '');
            setRelationFocus({ kind: 'node', key: action.dataset.nodeKey || '' });
            return;
          }
          if (event.key !== 'Enter' && event.key !== ' ') return;
          const node = event.target.closest('.relation-node');
          if (!node) return;
          event.preventDefault();
          setRelationFocus({ kind: 'node', key: node.dataset.nodeKey || '' });
          const target = relationNodeFocusTarget(node.dataset.nodeKey || '');
          focusControlArea(target.targetId, target.tab, target);
        });
        $('relation-ledger').addEventListener('click', event => {
          const item = event.target.closest('.relation-link-item');
          if (!item) return;
          setRelationFocus({ kind: 'link', key: item.dataset.linkKey || '' });
        });
        $('relation-ledger').addEventListener('keydown', event => {
          if (event.key !== 'Enter' && event.key !== ' ') return;
          const item = event.target.closest('.relation-link-item');
          if (!item) return;
          event.preventDefault();
          setRelationFocus({ kind: 'link', key: item.dataset.linkKey || '' });
        });
        $('relation-badges').addEventListener('click', event => {
          const badge = event.target.closest('.badge');
          if (!badge) return;
          setRelationFocus({ kind: 'badge', key: badge.dataset.badgeKey || '' });
        });
        $('relation-badges').addEventListener('keydown', event => {
          if (event.key !== 'Enter' && event.key !== ' ') return;
          const badge = event.target.closest('.badge');
          if (!badge) return;
          event.preventDefault();
          setRelationFocus({ kind: 'badge', key: badge.dataset.badgeKey || '' });
        });
      }

      async function boot() {
        state.locale = preferredLocale();
        state.layout = preferredLayout();
        state.workspaceTab = preferredWorkspaceTab();
        bind();
        translatePage();
        setWorkspaceTab(state.workspaceTab, { persist: false });
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
          syncMirroredSelectOptions('profile', 'relation-profile');
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
