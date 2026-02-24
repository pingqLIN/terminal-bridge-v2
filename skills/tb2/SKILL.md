---
name: tb2
description: Use terminal-bridge-v2 (tb2) as a universal CLI LLM remote control plane — bridge two terminal panes, capture and diff output in real time, auto-forward MSG: lines, and put a human in the review loop.
---

# terminal-bridge-v2 (tb2)

## When to use this skill

Use this skill when you need to:

- Monitor and relay output between two CLI LLM agents running in terminal panes
- Capture, diff, and auto-forward messages from one agent to another
- Place a human reviewer in the loop before any message is delivered
- Drive the workflow from an MCP JSON-RPC HTTP API (Codex, Claude Code, Gemini)

## What tb2 is

`tb2` is a Python-based universal CLI LLM control plane. It polls two terminal panes, detects new output via hash-based diffing, and optionally forwards `MSG:` prefixed lines from one pane to the other. A human-intervention queue lets you approve, edit, or reject messages before delivery.

Core capabilities:

- Multi-backend terminal control: `tmux` (Linux/macOS), `process`/ConPTY (Windows), `pipe` (non-interactive)
- Real-time output monitoring with adaptive exponential-backoff polling (100 ms → 3 s)
- Hash-based O(n) diff engine — detects new lines without O(n²) suffix scanning
- `MSG:` auto-forward between pane A and pane B
- Human-intervention queue with approve / edit / reject per message
- 14-tool MCP JSON-RPC HTTP API on `POST /mcp`
- Built-in web GUI at `/`
- Tool profiles for Codex, Claude Code, Aider, Gemini, llama.cpp, and acpx

## Install

```bash
git clone https://github.com/pingqLIN/terminal-bridge-v2.git
cd terminal-bridge-v2
pip install -e .
```

Windows ConPTY support:

```bash
pip install -e ".[windows]"
```

## Start the MCP server

```bash
python -m tb2 server --host 127.0.0.1 --port 3189
```

All tools are available at `POST http://127.0.0.1:3189/mcp` as JSON-RPC calls.

## Command model

```
python -m tb2 [--backend {tmux,process,pipe}] [--distro DISTRO] [--use-wsl]
              {init,list,capture,send,broker,profiles,server,gui} ...
```

### Subcommands

| Subcommand | Purpose | Key flags |
|------------|---------|-----------|
| `init` | Create session with pane A and pane B | `--session NAME` |
| `list` | List panes in a session | `--session NAME` |
| `capture` | Capture pane output | `--target PANE` `--lines N` |
| `send` | Send text to a pane | `--target PANE` `--text TEXT` `--enter` |
| `broker` | Interactive broker REPL | `--a PANE` `--b PANE` `--profile NAME` `--auto` `--intervention` |
| `profiles` | List available tool profiles | — |
| `server` | Start MCP HTTP server | `--host ADDR` `--port PORT` |
| `gui` | Start web GUI | `--host ADDR` `--port PORT` `--no-browser` |

## Typical workflow

### 1. Create a session (Linux/macOS with tmux)

```bash
python3 -m tb2 init --session demo
```

This creates `demo:0.0` (pane A) and `demo:0.1` (pane B).

### 2. Start the broker

```bash
# Auto-forward MSG: lines from A → B and B → A
python3 -m tb2 broker --a demo:0.0 --b demo:0.1 --profile codex --auto

# With human review queue
python3 -m tb2 broker --a demo:0.0 --b demo:0.1 --profile codex --auto --intervention
```

### 3. Broker commands

| Command | Effect |
|---------|--------|
| `/a <text>` | Send text + Enter to pane A |
| `/b <text>` | Send text + Enter to pane B |
| `/both <text>` | Send to both panes |
| `/auto on\|off` | Toggle MSG: auto-forward |
| `/pause` | Enable human review queue |
| `/resume` | Flush queue and disable review |
| `/pending` | List pending messages |
| `/approve <id\|all>` | Approve and deliver |
| `/reject <id\|all>` | Discard |
| `/edit <id> <text>` | Replace text and deliver |
| `/profile [name]` | Show or switch profile |
| `/status` | Show state + poll interval |
| `/quit` | Exit |

Any bare text (no `/`) is sent to pane A.

## MCP API

All tools accept JSON-RPC at `POST /mcp`. Example:

```bash
curl -sS http://127.0.0.1:3189/mcp \
  -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call",
       "params":{"name":"terminal_init","arguments":{"session":"demo"}}}'
```

### Tool reference

| Tool | Purpose |
|------|---------|
| `terminal_init` | Create session with pane A and pane B |
| `terminal_capture` | Read current screen content of a pane |
| `terminal_send` | Send text to a pane (optionally press Enter) |
| `terminal_interrupt` | Send Ctrl+C to bridge pane(s) |
| `room_create` | Create a message room (idempotent) |
| `room_poll` | Fetch messages after a cursor id |
| `room_post` | Post a message; optionally deliver to a pane |
| `bridge_start` | Start background poller between two panes |
| `bridge_stop` | Stop a bridge worker |
| `intervention_list` | List messages pending human review |
| `intervention_approve` | Approve and deliver pending message(s) |
| `intervention_reject` | Discard pending message(s) |
| `list_profiles` | Enumerate available tool profiles |
| `status` | Active rooms and bridge ids |

## Tool profiles

Profiles teach tb2 how a specific CLI tool behaves — which lines signal "waiting for input" and whether to strip ANSI escape codes.

| Profile | Prompt patterns | Strip ANSI | Wraps |
|---------|----------------|------------|-------|
| `acpx` | `$ # >` | Yes | acpx ACP client |
| `aider` | `aider> >` | Yes | Aider CLI |
| `claude-code` | `> claude> $` | No | Claude Code CLI |
| `codex` | `› > $` | No | OpenAI Codex CLI |
| `gemini` | `> gemini> ✦` | Yes | Gemini CLI |
| `generic` | `$ # >` | No | Any shell |
| `llama` | `> llama>` | No | llama.cpp / Ollama |

Switch profile at runtime: `/profile gemini`

## Register tb2 as an MCP server

### Codex CLI

```bash
codex mcp add tb2 --url http://127.0.0.1:3189/mcp
```

### Claude Code CLI

```bash
claude mcp add --transport http -s user tb2 http://127.0.0.1:3189/mcp
```

### Gemini CLI

```bash
gemini mcp add tb2 http://127.0.0.1:3189/mcp --transport http --scope user
```

## Human-intervention workflow

Enable with `--intervention` flag or `bridge_start { "intervention": true }`:

1. Broker detects a `MSG:` prefixed line from pane A
2. Message enters the **PENDING** queue
3. Human reviews with `/pending` (or `intervention_list`)
4. Choose:
   - `/approve <id>` — deliver original text
   - `/edit <id> <new text>` — deliver modified text
   - `/reject <id>` — discard silently
5. `/resume` flushes all pending and disables the queue

## Using tb2 with acpx

[acpx](https://github.com/openclaw/acpx) is a headless ACP client that wraps Codex, Claude, Gemini, and others. You can run an `acpx` session in pane A and another agent in pane B, then use tb2 to bridge them:

```bash
# Start acpx in pane A, another agent in pane B
python3 -m tb2 broker --a demo:0.0 --b demo:0.1 --profile acpx --auto
```

The `acpx` profile strips ANSI from acpx's structured output (`[thinking]`, `[tool]`, `[done]` lines) so the broker sees clean text.

## Practical patterns

### Two agents relaying prompts

```bash
python3 -m tb2 init --session lab
python3 -m tb2 broker --a lab:0.0 --b lab:0.1 --profile codex --auto
# In pane A, the agent prefixes replies with "MSG: <text>" to forward to B
```

### Via MCP (programmatic orchestration)

```python
import json, urllib.request

def call(method, **args):
    body = json.dumps({"jsonrpc":"2.0","id":1,"method":"tools/call",
                       "params":{"name":method,"arguments":args}}).encode()
    req = urllib.request.Request("http://127.0.0.1:3189/mcp",
                                 data=body, headers={"Content-Type":"application/json"})
    return json.loads(urllib.request.urlopen(req).read())

panes = call("terminal_init", session="demo")
call("bridge_start", pane_a=panes["result"]["structuredContent"]["pane_a"],
                     pane_b=panes["result"]["structuredContent"]["pane_b"],
                     auto_forward=True, profile="codex")
```
