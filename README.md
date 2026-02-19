# terminal-bridge-v2

[中文版](README.zh-TW.md)

> Universal CLI LLM remote control + real-time monitoring + human intervention

## Features

- **Backend abstraction** — pluggable terminal backends (tmux, screen, direct pipe)
- **Tool profiles** — built-in support for Codex, Claude Code, Aider, llama.cpp, and custom tools
- **Human intervention** — pending queue with approve/edit/reject before auto-forward
- **Adaptive polling** — exponential backoff when idle, instant reset on activity
- **Efficient diff** — hash-based O(n) new-line detection
- **Single-call capture** — both panes captured in one subprocess invocation

## Quick Start

```bash
# Create tmux session
python -m tb2 init --session demo

# Attach in another terminal
tmux attach -t demo

# Start broker with Codex profile
python -m tb2 broker --a demo:0.0 --b demo:0.1 --profile codex --auto

# With human review enabled
python -m tb2 broker --a demo:0.0 --b demo:0.1 --profile codex --auto --intervention
```

## Broker Commands

| Command | Description |
|---------|-------------|
| `/a <text>` | Send to pane A |
| `/b <text>` | Send to pane B |
| `/both <text>` | Send to both |
| `/auto on\|off` | Toggle auto-forward |
| `/pause` | Enable human review |
| `/resume` | Disable review + deliver pending |
| `/pending` | List pending messages |
| `/approve <id\|all>` | Approve message(s) |
| `/reject <id\|all>` | Reject message(s) |
| `/edit <id> <text>` | Edit and deliver |
| `/profile [name]` | Show/switch profile |
| `/status` | Broker status |

## Available Profiles

- `generic` — default shell prompts
- `codex` — OpenAI Codex CLI
- `claude-code` — Claude Code CLI
- `aider` — Aider CLI
- `llama` — llama.cpp chat
- `gemini` — Gemini CLI

## Use Gemini 3 Pro To Redesign README

Use `tb2` process backend to call `gemini-3-pro-preview` and generate README layout drafts

```bash
# 1) Start MCP server
python3 -m tb2 --backend process server --host 127.0.0.1 --port 3189

# 2) Init readme session
curl -sS http://127.0.0.1:3189/mcp \
  -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"terminal_init","arguments":{"backend":"process","backend_id":"gemini-readme","session":"readme"}}}'

# 3) Send Gemini 3 Pro task to readme:a
curl -sS http://127.0.0.1:3189/mcp \
  -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"terminal_send","arguments":{"backend":"process","backend_id":"gemini-readme","target":"readme:a","enter":true,"text":"gemini -m gemini-3-pro-preview -p \"Propose a full README structure for terminal-bridge-v2 and output Markdown.\""}}}'
```

Full workflow reference  
`docs/gemini-readme-workflow.zh-TW.md`

## Runtime Screenshots

Capture screenshots on Windows PowerShell

```powershell
pwsh -File .\scripts\capture_tb2_screenshot.ps1 -OutputDir .\docs\images -Prefix tb2-gemini -Count 3
```

![tb2 + Gemini screen 1](docs/images/tb2-gemini-01-20260218-215825.png)
![tb2 + Gemini screen 2](docs/images/tb2-gemini-02-20260218-215827.png)
![tb2 + Gemini screen 3](docs/images/tb2-gemini-03-20260218-215830.png)

## License

[MIT License](https://opensource.org/licenses/MIT)

## 🤖 AI-Assisted Development

This project was developed with AI assistance.

**AI Models/Services Used:**

- Claude Opus 4 (primary architect & implementation)
- OpenAI Codex CLI (code review & sub-agent contributions)

> ⚠️ **Disclaimer:** While the author has made every effort to review and validate the AI-generated code, no guarantee can be made regarding its correctness, security, or fitness for any particular purpose. Use at your own risk.
