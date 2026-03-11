# Getting Started

This guide is the shortest reliable path from a fresh checkout to a usable `tb2` session.

## 1. Install

```bash
pip install -e .
```

Windows interactive sessions also need:

```bash
pip install -e ".[windows]"
```

## 2. Check local compatibility

Run:

```bash
python -m tb2 doctor
```

Focus on two sections:

- `Backends`: confirms whether `tmux`, `process`, and `pipe` are usable.
- `Transports`: confirms `SSE`, `WebSocket`, and `room_poll` availability.
- `Supported CLI tools`: confirms whether first-class clients are actually installed.

## 3. Pick a fully supported client

`tb2` currently treats these as first-class interactive clients:

| Tool | Profile | Windows | Linux / macOS |
|------|---------|---------|---------------|
| OpenAI Codex CLI | `codex` | `process` | `tmux` |
| Claude Code CLI | `claude-code` | `process` | `tmux` |
| Gemini CLI | `gemini` | `process` | `tmux` |
| Aider | `aider` | `process` | `tmux` |

## 4. Start your first session

### Windows

```bash
python -m tb2 --backend process init --session demo
python -m tb2 --backend process broker --a demo:a --b demo:b --profile codex --auto
```

### Linux / macOS

```bash
python -m tb2 init --session demo
python -m tb2 broker --a demo:0.0 --b demo:0.1 --profile codex --auto
```

## 5. Know the message contract

The most important convention is:

- lines containing `MSG:` are treated as forwarding candidates
- `--auto` enables automatic forwarding
- `--intervention` queues forwarded messages for approval instead of sending them immediately

Examples:

```text
MSG: summarize the current failure
agent> MSG: echo READY
```

## 6. When you want programmatic control

Start the MCP server:

```bash
python -m tb2 server --host 127.0.0.1 --port 3189
```

Then register `http://127.0.0.1:3189/mcp` in your MCP-capable CLI.

For human-operator workflows, you now have three room watch paths:

- workflow-first browser GUI via `python -m tb2 gui`
- `python -m tb2 room watch --room-id <ROOM_ID>` for terminal-only oversight
- direct room streams via `GET /rooms/{room_id}/stream` or `GET /ws`

See:

- [MCP Client Setup](mcp-client-setup.md)
- [AI Orchestration Guide](ai-orchestration.md)
