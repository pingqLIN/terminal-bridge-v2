<h1 align="center">terminal-bridge-v2</h1>

<p align="center">
  <strong>AI-first terminal orchestration for CLI-native LLM workflows</strong>
</p>

<p align="center">
  <a href="https://github.com/pingqLIN/terminal-bridge-v2/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/pingqLIN/terminal-bridge-v2/ci.yml?branch=main&label=ci" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-%3E%3D3.9-blue.svg" alt="Python >= 3.9"></a>
  <img src="https://img.shields.io/badge/MCP-JSON--RPC-orange.svg" alt="MCP JSON-RPC">
  <img src="https://img.shields.io/badge/status-rebuilt%20main-green.svg" alt="Rebuilt main">
</p>

<p align="center">
  <a href="#why-tb2">Why TB2</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#core-use-cases">Use Cases</a> •
  <a href="#docs">Docs</a> •
  <a href="#project-status">Project Status</a> •
  <a href="README.zh-TW.md">中文版</a>
</p>

---

## Why TB2

`tb2` is a local control plane for terminal-native AI tools.

It gives you a practical way to run Host / Guest / Human operator workflows across Codex, Claude Code, Gemini, Aider, and similar CLI clients without giving up observability or human control.

What makes TB2 different:

- `AI-first terminal orchestration`: rooms, bridges, intervention, and live room transport are first-class concepts
- `MCP-first control surface`: use the same project from CLI, GUI, or MCP-capable AI clients
- `human-in-the-loop by design`: approve, edit, reject, or interrupt before forwarded actions land
- `cross-platform runtime`: `process` on Windows, `tmux` on Linux/macOS, `pipe` for non-interactive paths

## What You Can Do With It

- run a Host agent and one or more Guest agents inside real terminal panes
- bridge `MSG:` handoffs between agents with guardrails and optional approval
- watch a live collaboration room over GUI, SSE, WebSocket, or `tb2 room watch`
- expose the whole control plane through an MCP server for AI-driven orchestration

## Quick Start

Recommended first step:

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

### MCP server and GUI

```bash
python -m tb2 service start --host 127.0.0.1 --port 3189
python -m tb2 gui --host 127.0.0.1 --port 3189
```

Open `http://127.0.0.1:3189/` in your browser.

![Control Center](docs/images/control-center.png)

## Core Use Cases

### Host-mediated coding workflow

- Host owns the room, bridge, and intervention decisions.
- Guest works in a pane and emits short `MSG:` handoffs.
- Human operator watches the room and steps in only when needed.

### MCP-first local orchestration

- register `http://127.0.0.1:3189/mcp` in Codex, Claude Code, Gemini, or another MCP client
- call `terminal_init`, `bridge_start`, `room_post`, and intervention tools through a stable local endpoint

### Approval-gated forwarding

- turn on `--intervention` when auto-forwarded messages should not go straight to the target pane
- approve, edit, or reject before delivery

See [docs/use-cases.md](docs/use-cases.md) for fuller scenarios.

## Supported First-Class Clients

| Tool | Profile | Windows | Linux / macOS | Status |
| --- | --- | --- | --- | --- |
| OpenAI Codex CLI | `codex` | `process` | `tmux` | First-class |
| Claude Code CLI | `claude-code` | `process` | `tmux` | First-class |
| Gemini CLI | `gemini` | `process` | `tmux` | First-class |
| Aider | `aider` | `process` | `tmux` | First-class |

Other profiles remain available:

- `generic` for unknown shell-like tools
- `llama` as a community profile for llama.cpp or Ollama-style shells

## Docs

Start here:

- [Getting Started](docs/getting-started.md)
- [AI Orchestration Guide](docs/ai-orchestration.md)
- [MCP Client Setup](docs/mcp-client-setup.md)
- [Use Cases](docs/use-cases.md)
- [FAQ](docs/faq.md)
- [Roadmap](docs/roadmap.md)

Traditional Chinese docs:

- [README.zh-TW.md](README.zh-TW.md)
- [docs/getting-started.zh-TW.md](docs/getting-started.zh-TW.md)
- [docs/ai-orchestration.zh-TW.md](docs/ai-orchestration.zh-TW.md)
- [docs/use-cases.zh-TW.md](docs/use-cases.zh-TW.md)
- [docs/faq.zh-TW.md](docs/faq.zh-TW.md)
- [docs/roadmap.zh-TW.md](docs/roadmap.zh-TW.md)

## Project Status

TB2 is no longer a concept repo. The current mainline includes:

- multi-backend runtime: `tmux`, `process`, `pipe`
- broker, MCP server, GUI, and background service manager
- room, bridge, and intervention primitives
- SSE and WebSocket live room transport plus `room_poll` fallback
- non-E2E regression suite currently passing in local validation

Current product direction:

- default to `MCP-first`
- default to `Host / Guest / Human operator` orchestration
- keep peer-style room usage available, but treat it as advanced mode

## Safety Notes

- default host binding should stay on `127.0.0.1`
- if you expose TB2 beyond localhost, treat it as a sensitive control surface
- run `python -m tb2 doctor` before first use on a new machine
- use `--intervention` when forwarded actions need human review

## Contributing and Support

- [CONTRIBUTING.md](CONTRIBUTING.md)
- [SUPPORT.md](SUPPORT.md)
- [SECURITY.md](SECURITY.md)
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- [CHANGELOG.md](CHANGELOG.md)
