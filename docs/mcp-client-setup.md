# MCP Client Setup

This guide is for the person or agent that wants to use TB2 as a stable local MCP control plane.

## What TB2 exposes over MCP

Core tools:

- `terminal_init`
- `terminal_capture`
- `terminal_send`
- `terminal_interrupt`
- `room_create`
- `room_poll`
- `room_post`
- `bridge_start`
- `bridge_stop`
- `intervention_list`
- `intervention_approve`
- `intervention_reject`
- `list_profiles`
- `doctor`
- `status`

Use them as three capability groups:

| Capability group | Tools |
| --- | --- |
| launch and I/O | `terminal_init`, `terminal_send`, `terminal_capture`, `terminal_interrupt` |
| collaboration state | `room_create`, `room_poll`, `room_post`, `status` |
| delegation control | `bridge_start`, `bridge_stop`, `intervention_list`, `intervention_approve`, `intervention_reject` |

## Server Startup Options

### Foreground

```bash
python -m tb2 server --host 127.0.0.1 --port 3189
```

### Background service

```bash
python -m tb2 service start --host 127.0.0.1 --port 3189
python -m tb2 service status
```

Health probe:

```bash
curl -sS http://127.0.0.1:3189/healthz
```

MCP endpoint:

- `http://127.0.0.1:3189/mcp`

## Register TB2 in Each Client

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

## Verify Registration

```bash
codex mcp list
claude mcp list
gemini mcp list
```

Expected signs:

- Claude and Gemini show `Connected`
- Codex shows `enabled`

## Host AI Tool Map

If the Host AI is driving the workflow, this is the minimal useful sequence:

1. `doctor`
2. `terminal_init`
3. `bridge_start`
4. `room_poll` or stream subscribe
5. `intervention_list`
6. `intervention_approve` or `intervention_reject`
7. `status`

### Bridge resolution shortcuts

TB2 now supports a lighter control path for intervention tools:

- `intervention_list`, `intervention_approve`, `intervention_reject`, and `terminal_interrupt` accept `bridge_id` when you already know it
- if `bridge_id` is unknown, pass `room_id` when that room has exactly one active bridge
- if the whole server currently has exactly one active bridge, these tools can resolve it automatically
- when multiple active bridges exist, TB2 returns an explicit error plus `bridge_candidates`

The `status` tool now also returns `bridge_details` so another AI client can map `bridge_id`, `room_id`, panes, profile, and pending count without guessing.

## Human Operator Tool Map

When a human is supervising through an MCP-capable app instead of the browser UI:

1. `status`
2. `room_poll`
3. `room_post`
4. `terminal_capture`
5. `terminal_interrupt`

## Protocol Probes

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

## Compatibility Notes

TB2 currently ships:

- `initialize`
- `ping`
- `notifications/initialized`
- `tools/list`
- empty `resources/list`
- empty `prompts/list`

Current compatibility guidance:

- use HTTP MCP transport
- bind to localhost unless you have an explicit trust boundary
- check `doctor` before blaming a client integration issue on MCP itself
- read `tools/list` before hard-coding intervention arguments; the schema now advertises `room_id` fallback for bridge-scoped tools

## Remove Registration

```bash
codex mcp remove tb2
claude mcp remove -s user tb2
gemini mcp remove --scope user tb2
```

## Related Docs

- [Getting Started](getting-started.md)
- [AI Orchestration Guide](ai-orchestration.md)
- [Platform and Terminal Behavior](platform-behavior.md)
