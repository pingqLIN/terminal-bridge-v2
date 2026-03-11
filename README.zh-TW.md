<h1 align="center">terminal-bridge-v2</h1>

<p align="center">
  <strong>以 AI-first terminal orchestration 為核心的 CLI LLM 協作控制面</strong>
</p>

<p align="center">
  <a href="https://github.com/pingqLIN/terminal-bridge-v2/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/pingqLIN/terminal-bridge-v2/ci.yml?branch=main&label=ci" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-%3E%3D3.9-blue.svg" alt="Python >= 3.9"></a>
  <img src="https://img.shields.io/badge/MCP-JSON--RPC-orange.svg" alt="MCP JSON-RPC">
  <img src="https://img.shields.io/badge/status-rebuilt%20main-green.svg" alt="Rebuilt main">
</p>

<p align="center">
  <a href="#為什麼是-tb2">為什麼是 TB2</a> •
  <a href="#快速開始">快速開始</a> •
  <a href="#核心使用場景">核心使用場景</a> •
  <a href="#文件導覽">文件導覽</a> •
  <a href="#專案狀態">專案狀態</a> •
  <a href="README.md">English</a>
</p>

---

## 為什麼是 TB2

`tb2` 是一個給終端型 AI 工具使用的本地控制面。

它讓你能在 Codex、Claude Code、Gemini、Aider 等 CLI client 上實作 Host / Guest / Human operator 協作，而不失去可觀測性與人類控制點。

TB2 的差異點在於：

- `AI-first terminal orchestration`：rooms、bridges、intervention、live room transport 都是第一級概念
- `MCP-first control surface`：同一套專案可以從 CLI、GUI、或 MCP client 控制
- `human-in-the-loop by design`：可在轉發前 approve、edit、reject、interrupt
- `cross-platform runtime`：Windows 用 `process`，Linux/macOS 用 `tmux`，`pipe` 支援非互動模式

## 你可以拿它做什麼

- 在真實 terminal pane 中同時跑 Host 與一個或多個 Guest agent
- 用 `MSG:` handoff 在 agent 之間橋接訊息，並套上 guardrails
- 用 GUI、SSE、WebSocket、或 `tb2 room watch` 觀看 live collaboration room
- 透過 MCP server 把整個控制面交給 AI host 或其他工具使用

## 快速開始

建議先做環境檢查：

```bash
python -m tb2 doctor
```

### Windows

```bash
pip install -e ".[windows,dev]"
python -m tb2 --backend process init --session demo
python -m tb2 --backend process broker --a demo:a --b demo:b --profile codex --auto
```

### Linux / macOS

```bash
pip install -e ".[dev]"
python -m tb2 init --session demo
python -m tb2 broker --a demo:0.0 --b demo:0.1 --profile codex --auto
```

### MCP server 與 GUI

```bash
python -m tb2 service start --host 127.0.0.1 --port 3189
python -m tb2 gui --host 127.0.0.1 --port 3189
```

在瀏覽器開啟 `http://127.0.0.1:3189/`。

![控制台介面](docs/images/control-center.png)

## 核心使用場景

### Host-mediated coding workflow

- Host 管 room、bridge 與 intervention 決策。
- Guest 在 pane 內工作，並發出簡短 `MSG:` handoff。
- Human operator 只在需要時介入。

### MCP-first 本地協作控制面

- 在 Codex、Claude Code、Gemini 或其他 MCP client 中註冊 `http://127.0.0.1:3189/mcp`
- 透過穩定的本地 endpoint 呼叫 `terminal_init`、`bridge_start`、`room_post` 與 intervention 工具

### 審核後再轉發

- 當 auto-forward 不應直接送到目標 pane 時，開啟 `--intervention`
- 先 approve、edit、或 reject，再決定是否送出

更多場景可見 [docs/use-cases.zh-TW.md](docs/use-cases.zh-TW.md)。

## 完整支援的 First-Class Clients

| 工具 | Profile | Windows | Linux / macOS | 狀態 |
| --- | --- | --- | --- | --- |
| OpenAI Codex CLI | `codex` | `process` | `tmux` | First-class |
| Claude Code CLI | `claude-code` | `process` | `tmux` | First-class |
| Gemini CLI | `gemini` | `process` | `tmux` | First-class |
| Aider | `aider` | `process` | `tmux` | First-class |

其餘 profile 仍保留：

- `generic`：未知 shell-like 工具的保底 profile
- `llama`：llama.cpp 或 Ollama 類 shell 的社群 profile

## 文件導覽

建議從這裡開始：

- [入門指南](docs/getting-started.zh-TW.md)
- [AI 協作指南](docs/ai-orchestration.zh-TW.md)
- [MCP 用戶端設定](docs/mcp-client-setup.zh-TW.md)
- [使用場景](docs/use-cases.zh-TW.md)
- [常見問題](docs/faq.zh-TW.md)
- [路線圖](docs/roadmap.zh-TW.md)

英文版文件：

- [README.md](README.md)
- [docs/getting-started.md](docs/getting-started.md)
- [docs/ai-orchestration.md](docs/ai-orchestration.md)
- [docs/use-cases.md](docs/use-cases.md)
- [docs/faq.md](docs/faq.md)
- [docs/roadmap.md](docs/roadmap.md)

## 專案狀態

TB2 已經不是概念 repo。目前主幹已包含：

- 多 backend runtime：`tmux`、`process`、`pipe`
- broker、MCP server、GUI、background service manager
- room、bridge、intervention 原語
- SSE 與 WebSocket live room transport，以及 `room_poll` fallback
- 本地驗證通過的非 E2E 回歸測試

目前產品方向：

- 預設走 `MCP-first`
- 預設採 `Host / Guest / Human operator` orchestration
- peer-style room usage 保留，但視為 advanced mode

## 安全提醒

- 預設 host 應維持在 `127.0.0.1`
- 如果要暴露到 localhost 以外，請把 TB2 視為敏感控制面
- 第一次在新機器上使用前，先跑 `python -m tb2 doctor`
- 當轉發內容需要人類審查時，請啟用 `--intervention`

## 貢獻與支援

- [CONTRIBUTING.md](CONTRIBUTING.md)
- [SUPPORT.md](SUPPORT.md)
- [SECURITY.md](SECURITY.md)
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- [CHANGELOG.md](CHANGELOG.md)
