# MCP Client Setup and Compatibility

This guide records a reproducible MCP setup for `terminal-bridge-v2` (`tb2`) with:

- OpenAI Codex CLI
- Claude Code CLI
- Gemini CLI

It also includes dependency checks and a quick compatibility matrix.

## 1) Prerequisites

- Python `>=3.9`
- Install project:

```bash
pip install -e .
```

- Windows process backend support:

```bash
pip install -e ".[windows]"
# or
pip install pywinpty
```

- Recommended first check:

```bash
python -m tb2 doctor
```

`tb2 doctor` reports backend readiness plus whether the first-class interactive clients (`codex`, `claude`, `gemini`, `aider`) are installed on the current machine.

## 2) Start tb2 MCP server

```bash
python -m tb2 server --host 127.0.0.1 --port 3189
```

For cross-platform detached hosting, you can use:

```bash
python -m tb2 service start --host 127.0.0.1 --port 3189
python -m tb2 service status
```

Optional quick health check:

```bash
curl -sS http://127.0.0.1:3189/healthz
```

Endpoint used by all clients:

- `http://127.0.0.1:3189/mcp`

## 3) Register tb2 in each CLI

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

## 4) Verify health

```bash
codex mcp list
claude mcp list
gemini mcp list
```

Expected result:

- `tb2 ... Connected` in Claude and Gemini
- `tb2 ... enabled` in Codex list output

## 5) Protocol probes (optional but recommended)

Initialize:

```bash
curl -sS http://127.0.0.1:3189/mcp \
  -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"probe","version":"1"}}}'
```

Ping:

```bash
curl -sS http://127.0.0.1:3189/mcp \
  -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":2,"method":"ping","params":{}}'
```

Tool list:

```bash
curl -sS http://127.0.0.1:3189/mcp \
  -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/list","params":{}}'
```

## 6) Compatibility notes

`tb2` MCP server now includes:

- `initialize`
- `ping`
- `notifications/initialized`
- `tools/list` with MCP-style tool metadata (`name`, `description`, `inputSchema`)
- optional empty responses for `resources/list` and `prompts/list`
- client protocol echo in initialize response (important for newer MCP SDK versions)

This setup is compatible with:

- Codex CLI URL transport
- Claude Code HTTP transport
- Gemini HTTP transport (streamable HTTP client in MCP SDK)

## 7) Backend dependency matrix

| Backend | Platform | Dependency | Smoke result |
| --- | --- | --- | --- |
| `tmux` | Linux/macOS/WSL | `tmux` | not tested in this Windows check |
| `process` | Windows/Linux/macOS | Windows needs `pywinpty` | pass |
| `pipe` | all | none | pass |

Windows process backend note:

- First command output may appear after shell warm-up
- Wait a short moment before first capture/assertion in automated checks

## 8) Remove registration

```bash
codex mcp remove tb2
claude mcp remove -s user tb2
gemini mcp remove --scope user tb2
```

## 9) Optional GUI for non-terminal users

```bash
python -m tb2 gui --host 127.0.0.1 --port 3189
```

Open:

- `http://127.0.0.1:3189/`
