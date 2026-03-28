# Role Guides

Use this document when you already know `tb2` is the right tool and now need to know how each role should operate inside the same control plane.

## Role Index

| Role | Primary Goal | Recommended Surface | Read This Section |
| --- | --- | --- | --- |
| Host AI | Run the collaboration loop and decide when work moves between panes | MCP or CLI | [Host AI](#host-ai) |
| Guest AI | Do focused work and emit structured handoffs | Terminal pane | [Guest AI](#guest-ai) |
| Human Operator | Observe, approve, reject, interrupt, and audit | GUI first, CLI/MCP second | [Human Operator](#human-operator) |
| MCP Integrator | Connect Codex, Claude Code, Gemini, or custom clients | MCP HTTP endpoint | [MCP Integrator](#mcp-integrator) |

## Host AI

### Responsibilities

- Create or attach to a two-pane session.
- Start exactly one bridge for each active pane pair.
- Pick the profile that matches the guest tool.
- Decide whether handoffs go through direct auto-forwarding or the approval queue.
- Stop the bridge when the task is done.

### Standard Lifecycle

1. Run `python -m tb2 doctor`.
2. Create panes with `terminal_init` or `tb2 init`.
3. Start the bridge with `bridge_start`.
4. Monitor the room feed before issuing new work.
5. Use `intervention_list` when approval mode is enabled.
6. Stop the bridge with `bridge_stop`.

### Safe Defaults

- Prefer the default backend chosen by `tb2`.
- Use `auto_forward=true` only when the guest is already following a strict `MSG:` contract.
- Use `intervention=true` when a forwarded request may change code, execute commands, or reach a shared environment.
- Keep one room per active collaboration thread.

### Message Contract

The host should treat `MSG:` as the only stable cross-agent handoff signal.

Good examples:

```text
MSG: summarize the failing assertion in tests/test_server.py
MSG: run the platform-specific smoke test and report the result
MSG: prepare a patch for the CLI help text only
```

Bad examples:

```text
MSG: here is a long diary of everything I tried over the last 20 minutes
MSG: maybe do something about the bug if you have time
```

### Failure Recovery

- If `bridge_start` returns a preflight error, capture both panes before retrying.
- If the room stream goes quiet, reconnect transport before restarting the bridge.
- If the guest emits malformed `MSG:` lines, switch to approval mode and send explicit operator notes through `room_post`.

## Guest AI

### Responsibilities

- Work inside the assigned pane.
- Emit short, actionable `MSG:` lines only when a handoff is required.
- Keep normal terminal output readable and avoid flooding the room with noise.

### Output Rules

- Keep one request per `MSG:` line.
- Prefer imperative, concrete requests.
- Avoid multi-line `MSG:` payloads.
- Avoid ANSI-heavy or prompt-heavy wrappers when you can choose a cleaner output mode.

### Blocking Patterns

Use these shapes when the guest needs help:

```text
MSG: need clarification on the expected backend for native macOS
MSG: capture looks stale after restart; please reconnect the room stream
MSG: ready for review on the backend fallback patch
```

### What Not To Do

- Do not assume every plain output line is forwarded.
- Do not use `MSG:` for internal scratch notes.
- Do not ask the host to infer intent from a long transcript when a short request would be clearer.

## Human Operator

### Responsibilities

- Watch the room feed.
- Decide whether a pending handoff should be approved, edited, rejected, or interrupted.
- Keep the control plane healthy: transport connected, room selected, bridge id correct.

### Recommended Surface

- Start with the browser console at `python -m tb2 gui`.
- Use the `Approval Gate` preset when you need human review.
- Use `MCP Operator` when the bridge already exists and your job is oversight only.
- Fall back to CLI or direct MCP calls only when the GUI is not available.

### Approval Checklist

- Is the target pane correct?
- Is the message specific enough to execute safely?
- Does the request need editing before delivery?
- Should the operator interrupt the current task before forwarding?

### Audit Expectations

- Keep host binding on `127.0.0.1`.
- Prefer room-posted operator notes over ad hoc terminal typing when you want an auditable trail.
- Refresh pending items before bulk approval or rejection.

## MCP Integrator

### Primary Goal

Expose `tb2` as a stable local control plane to Codex CLI, Claude Code, Gemini CLI, or custom MCP clients.

### Core Endpoint

- `http://127.0.0.1:3189/mcp`

### Core Tool Surface

- `terminal_init`
- `terminal_capture`
- `terminal_send`
- `terminal_interrupt`
- `bridge_start`
- `bridge_stop`
- `room_create`
- `room_poll`
- `room_post`
- `intervention_list`
- `intervention_approve`
- `intervention_reject`
- `doctor`
- `status`

### Recommended Call Sequence

1. `doctor`
2. `terminal_init`
3. `bridge_start`
4. `room_poll` or room stream subscription
5. `room_post` / `terminal_send`
6. `intervention_list` and approve or reject as needed
7. `bridge_stop`

### Integration Rules

- Treat the server as local-only infrastructure.
- Keep `backend_id` stable when multiple clients need to reuse the same backend instance.
- Do not start multiple bridges over the same pane pair in different rooms.
- Use room streaming for observability and `status` for topology.

See also:

- [Getting Started](getting-started.md)
- [MCP Client Setup](mcp-client-setup.md)
- [Platform Compatibility Matrix](platforms/compatibility-matrix.md)
