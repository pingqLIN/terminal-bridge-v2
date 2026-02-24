"""Simple built-in web GUI for tb2 MCP control."""

from __future__ import annotations


GUI_HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>tb2 Control Center</title>
  <style>
    :root {
      --bg-top: #f8fbff;
      --bg-bottom: #e7f0ff;
      --panel: #ffffff;
      --panel-2: #f2f7ff;
      --ink: #13233f;
      --muted: #4e6388;
      --accent: #127a68;
      --accent-2: #0f5cc0;
      --warn: #d95729;
      --line: #c7d7ef;
      --radius: 14px;
      --shadow: 0 10px 30px rgba(22, 59, 123, 0.12);
      --mono: "JetBrains Mono", "Fira Code", Consolas, monospace;
      --sans: "IBM Plex Sans", "Segoe UI", Tahoma, sans-serif;
    }

    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: var(--sans);
      color: var(--ink);
      background: linear-gradient(180deg, var(--bg-top), var(--bg-bottom));
      min-height: 100vh;
    }

    .wrap {
      width: min(1200px, 96vw);
      margin: 22px auto 28px;
      display: grid;
      gap: 14px;
    }

    .hero {
      border: 1px solid var(--line);
      border-radius: var(--radius);
      padding: 16px 18px;
      box-shadow: var(--shadow);
      background:
        radial-gradient(circle at 12% 20%, rgba(18, 122, 104, 0.16), transparent 36%),
        radial-gradient(circle at 88% 12%, rgba(15, 92, 192, 0.15), transparent 34%),
        var(--panel);
    }

    .hero h1 {
      margin: 0 0 8px;
      font-size: clamp(1.2rem, 2.2vw, 1.8rem);
      letter-spacing: 0.01em;
    }

    .hero .sub {
      margin: 0;
      color: var(--muted);
      font-size: 0.95rem;
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(12, minmax(0, 1fr));
      gap: 12px;
    }

    .card {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      padding: 12px;
      box-shadow: var(--shadow);
    }

    .card h2 {
      margin: 0 0 10px;
      font-size: 0.96rem;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      color: var(--accent-2);
    }

    .left { grid-column: span 5; }
    .right { grid-column: span 7; }
    .full { grid-column: span 12; }

    @media (max-width: 980px) {
      .left, .right, .full { grid-column: span 12; }
    }

    .row {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
      margin-bottom: 8px;
    }

    .row.one {
      grid-template-columns: 1fr;
    }

    label {
      display: block;
      font-size: 0.78rem;
      color: var(--muted);
      margin-bottom: 4px;
    }

    input, select, textarea {
      width: 100%;
      font: inherit;
      color: var(--ink);
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 8px 9px;
      background: var(--panel-2);
    }

    textarea, pre {
      font-family: var(--mono);
      font-size: 0.83rem;
      line-height: 1.35;
    }

    textarea {
      min-height: 94px;
      resize: vertical;
    }

    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin: 8px 0 0;
    }

    button {
      border: 0;
      border-radius: 10px;
      padding: 8px 12px;
      font-weight: 600;
      cursor: pointer;
      background: var(--accent-2);
      color: #fff;
    }

    button.alt { background: var(--accent); }
    button.warn { background: var(--warn); }
    button.ghost {
      background: #d9e7ff;
      color: #0e366e;
    }

    .checks {
      display: flex;
      gap: 16px;
      align-items: center;
      margin: 2px 0 6px;
      color: var(--muted);
      font-size: 0.86rem;
    }

    .checks input { width: auto; margin-right: 6px; }

    .codebox {
      margin-top: 8px;
      border: 1px solid var(--line);
      border-radius: 10px;
      background: #f4f8ff;
      padding: 8px;
      max-height: 220px;
      overflow: auto;
      white-space: pre-wrap;
      word-break: break-word;
    }

    .badge {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border-radius: 999px;
      padding: 4px 10px;
      font-size: 0.78rem;
      color: #084636;
      background: #ccf3e8;
      border: 1px solid #95e0cb;
    }

    .muted { color: var(--muted); }
  </style>
</head>
<body>
  <main class="wrap">
    <section class="hero">
      <h1>tb2 Control Center</h1>
      <p class="sub">A browser GUI for non terminal users to drive tb2 through MCP</p>
      <p><span class="badge" id="api-badge">MCP endpoint __MCP_ENDPOINT__</span></p>
    </section>

    <section class="grid">
      <article class="card left">
        <h2>Session Setup</h2>
        <div class="row">
          <div>
            <label for="backend">backend</label>
            <select id="backend">
              <option value="process">process</option>
              <option value="tmux">tmux</option>
              <option value="pipe">pipe</option>
            </select>
          </div>
          <div>
            <label for="backend-id">backend_id</label>
            <input id="backend-id" value="default" />
          </div>
        </div>
        <div class="row">
          <div>
            <label for="session">session</label>
            <input id="session" value="tb2-gui" />
          </div>
          <div>
            <label for="profile">profile</label>
            <select id="profile">
              <option value="generic">generic</option>
              <option value="codex">codex</option>
              <option value="claude-code">claude-code</option>
              <option value="aider">aider</option>
              <option value="llama">llama</option>
              <option value="gemini">gemini</option>
            </select>
          </div>
        </div>
        <div class="row">
          <div>
            <label for="pane-a">pane A</label>
            <input id="pane-a" placeholder="auto filled by Init Session" />
          </div>
          <div>
            <label for="pane-b">pane B</label>
            <input id="pane-b" placeholder="auto filled by Init Session" />
          </div>
        </div>
        <div class="checks">
          <label><input id="auto-forward" type="checkbox" checked />auto forward</label>
          <label><input id="intervention" type="checkbox" />intervention</label>
        </div>
        <div class="row">
          <div>
            <label for="bridge-id">bridge_id</label>
            <input id="bridge-id" placeholder="auto generated if empty" />
          </div>
          <div>
            <label for="room-id">room_id</label>
            <input id="room-id" placeholder="auto generated if empty" />
          </div>
        </div>
        <div class="actions">
          <button id="init-session">Init Session</button>
          <button id="start-bridge" class="alt">Start Bridge</button>
          <button id="stop-bridge" class="warn">Stop Bridge</button>
          <button id="refresh-status" class="ghost">Refresh Status</button>
        </div>
        <pre class="codebox" id="status-box"></pre>
      </article>

      <article class="card right">
        <h2>Message Control</h2>
        <div class="row one">
          <div>
            <label for="send-text">text to send</label>
            <textarea id="send-text" placeholder="Type a message for pane A or pane B"></textarea>
          </div>
        </div>
        <div class="actions">
          <button id="send-a">Send to A</button>
          <button id="send-b">Send to B</button>
          <button id="capture-a" class="ghost">Capture A</button>
          <button id="capture-b" class="ghost">Capture B</button>
        </div>
        <div class="row">
          <div>
            <label for="capture-a-box">capture pane A</label>
            <textarea id="capture-a-box" readonly></textarea>
          </div>
          <div>
            <label for="capture-b-box">capture pane B</label>
            <textarea id="capture-b-box" readonly></textarea>
          </div>
        </div>
      </article>

      <article class="card full">
        <h2>Live Room Stream</h2>
        <p class="muted">Auto polling is active after bridge start</p>
        <pre class="codebox" id="stream-box"></pre>
      </article>

      <article class="card full">
        <h2>Activity Log</h2>
        <pre class="codebox" id="log-box"></pre>
      </article>
    </section>
  </main>

  <script>
    const MCP_ENDPOINT = "__MCP_ENDPOINT__";
    const state = {
      reqId: 1,
      lastMsgId: 0,
      poller: null
    };

    function el(id) {
      return document.getElementById(id);
    }

    function nowTag() {
      return new Date().toLocaleTimeString();
    }

    function logLine(text) {
      const box = el("log-box");
      box.textContent += "[" + nowTag() + "] " + text + "\n";
      box.scrollTop = box.scrollHeight;
    }

    function setStatus(obj) {
      el("status-box").textContent = JSON.stringify(obj, null, 2);
    }

    async function rpc(method, params) {
      const payload = {
        jsonrpc: "2.0",
        id: state.reqId++,
        method: method,
        params: params || {}
      };
      const res = await fetch(MCP_ENDPOINT, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.error) {
        throw new Error(data.error.message || JSON.stringify(data.error));
      }
      return data.result;
    }

    function extractToolText(result) {
      if (!result || !Array.isArray(result.content)) return "";
      for (const item of result.content) {
        if (item && item.type === "text" && typeof item.text === "string") {
          return item.text;
        }
      }
      return "";
    }

    function normalizeToolResult(result) {
      if (!result || typeof result !== "object") return result;
      const isMcpEnvelope =
        Array.isArray(result.content) ||
        Object.prototype.hasOwnProperty.call(result, "structuredContent") ||
        Object.prototype.hasOwnProperty.call(result, "isError");
      if (!isMcpEnvelope) return result;

      if (result.structuredContent && typeof result.structuredContent === "object") {
        return result.structuredContent;
      }

      const text = extractToolText(result);
      if (!text) return {};
      try {
        return JSON.parse(text);
      } catch (_err) {
        return { text: text };
      }
    }

    async function callTool(name, args) {
      const raw = await rpc("tools/call", {
        name: name,
        arguments: args || {}
      });
      const normalized = normalizeToolResult(raw);

      const isMcpEnvelope =
        raw &&
        typeof raw === "object" &&
        (Array.isArray(raw.content) ||
          Object.prototype.hasOwnProperty.call(raw, "structuredContent") ||
          Object.prototype.hasOwnProperty.call(raw, "isError"));

      if (isMcpEnvelope && raw.isError) {
        const msg =
          (normalized && typeof normalized.error === "string" && normalized.error) ||
          extractToolText(raw) ||
          "tool call failed";
        throw new Error(msg);
      }
      if (!isMcpEnvelope && normalized && typeof normalized.error === "string") {
        throw new Error(normalized.error);
      }
      return normalized;
    }

    function commonArgs() {
      return {
        backend: el("backend").value.trim(),
        backend_id: el("backend-id").value.trim() || "default"
      };
    }

    async function refreshStatus() {
      const result = await callTool("status", {});
      setStatus(result);
      return result;
    }

    function appendStream(text) {
      const box = el("stream-box");
      box.textContent += text + "\n";
      box.scrollTop = box.scrollHeight;
    }

    async function pollRoom() {
      const roomId = el("room-id").value.trim();
      if (!roomId) return;
      try {
        const result = await callTool("room_poll", {
          room_id: roomId,
          after_id: state.lastMsgId,
          limit: 200
        });
        if (Array.isArray(result.messages)) {
          for (const msg of result.messages) {
            appendStream("#" + msg.id + " " + msg.author + " | " + msg.text);
            state.lastMsgId = Math.max(state.lastMsgId, msg.id || 0);
          }
        }
      } catch (err) {
        logLine("poll failed: " + err.message);
      }
    }

    function startPolling() {
      if (state.poller) {
        clearInterval(state.poller);
      }
      state.poller = setInterval(pollRoom, 1200);
    }

    async function initSession() {
      const args = Object.assign({
        session: el("session").value.trim() || "tb2-gui"
      }, commonArgs());
      const result = await callTool("terminal_init", args);
      el("pane-a").value = result.pane_a || "";
      el("pane-b").value = result.pane_b || "";
      logLine("session ready: " + result.session);
      return result;
    }

    async function startBridge() {
      const paneA = el("pane-a").value.trim();
      const paneB = el("pane-b").value.trim();
      if (!paneA || !paneB) {
        throw new Error("pane A and pane B are required");
      }
      const args = Object.assign({
        pane_a: paneA,
        pane_b: paneB,
        profile: el("profile").value.trim() || "generic",
        auto_forward: el("auto-forward").checked,
        intervention: el("intervention").checked
      }, commonArgs());
      if (el("bridge-id").value.trim()) args.bridge_id = el("bridge-id").value.trim();
      if (el("room-id").value.trim()) args.room_id = el("room-id").value.trim();
      const result = await callTool("bridge_start", args);
      el("bridge-id").value = result.bridge_id || "";
      el("room-id").value = result.room_id || "";
      state.lastMsgId = 0;
      startPolling();
      logLine("bridge started: " + (result.bridge_id || ""));
      return result;
    }

    async function stopBridge() {
      const bridgeId = el("bridge-id").value.trim();
      if (!bridgeId) throw new Error("bridge_id is required");
      const result = await callTool("bridge_stop", { bridge_id: bridgeId });
      logLine("bridge stopped");
      return result;
    }

    async function sendToPane(targetInputId) {
      const target = el(targetInputId).value.trim();
      const text = el("send-text").value;
      if (!target) throw new Error("target pane is required");
      if (!text.trim()) throw new Error("text is empty");
      const args = Object.assign({
        target: target,
        text: text,
        enter: true
      }, commonArgs());
      await callTool("terminal_send", args);
      logLine("sent text to " + target);
    }

    async function capturePane(targetInputId, outputId) {
      const target = el(targetInputId).value.trim();
      if (!target) throw new Error("target pane is required");
      const args = Object.assign({
        target: target,
        lines: 200
      }, commonArgs());
      const result = await callTool("terminal_capture", args);
      el(outputId).value = (result.lines || []).join("\n");
      logLine("captured " + target + " lines=" + result.count);
    }

    async function safeRun(fn, okText) {
      try {
        const result = await fn();
        if (okText) logLine(okText);
        return result;
      } catch (err) {
        logLine("error: " + err.message);
      }
    }

    function bindUi() {
      el("init-session").addEventListener("click", function () {
        safeRun(initSession);
      });
      el("start-bridge").addEventListener("click", function () {
        safeRun(startBridge);
      });
      el("stop-bridge").addEventListener("click", function () {
        safeRun(stopBridge);
      });
      el("send-a").addEventListener("click", function () {
        safeRun(function () { return sendToPane("pane-a"); });
      });
      el("send-b").addEventListener("click", function () {
        safeRun(function () { return sendToPane("pane-b"); });
      });
      el("capture-a").addEventListener("click", function () {
        safeRun(function () { return capturePane("pane-a", "capture-a-box"); });
      });
      el("capture-b").addEventListener("click", function () {
        safeRun(function () { return capturePane("pane-b", "capture-b-box"); });
      });
      el("refresh-status").addEventListener("click", function () {
        safeRun(refreshStatus);
      });
    }

    async function boot() {
      bindUi();
      logLine("GUI ready, endpoint " + MCP_ENDPOINT);
      await safeRun(async function () {
        const profiles = await callTool("list_profiles", {});
        if (profiles && Array.isArray(profiles.profiles)) {
          const select = el("profile");
          const known = new Set();
          for (const opt of Array.from(select.options)) known.add(opt.value);
          for (const p of profiles.profiles) {
            if (!known.has(p)) {
              const op = document.createElement("option");
              op.value = p;
              op.textContent = p;
              select.appendChild(op);
            }
          }
        }
      });
      await safeRun(refreshStatus);
    }

    boot();
  </script>
</body>
</html>
"""


def build_gui_html(mcp_endpoint: str = "/mcp") -> str:
    """Render the built-in GUI HTML."""
    return GUI_HTML_TEMPLATE.replace("__MCP_ENDPOINT__", mcp_endpoint)
