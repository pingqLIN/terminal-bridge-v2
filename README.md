# terminal-bridge-v2

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
