# AI Orchestration Guide

This guide is for AI-operated `tb2` sessions, especially when one agent is the host and one or more guest agents participate through panes or MCP.

## Roles

- Host: owns the room, bridge lifecycle, and intervention decisions.
- Guest: performs work inside a pane and emits machine-detectable handoff lines.
- Human operator: can monitor, approve, edit, or interrupt when needed.

## Recommended first-class clients

Use these first when you want predictable prompt detection and forwarding:

- `codex`
- `claude-code`
- `gemini`
- `aider`

## Message contract

Guests should emit task handoff lines with `MSG:`.

Examples:

```text
MSG: summarize your current blocker
MSG: echo READY_FOR_REVIEW
agent> MSG: request clarification on failing test
```

Guidelines:

- keep one actionable request per `MSG:` line
- avoid multi-paragraph `MSG:` payloads
- prefer explicit intent over conversational filler

## Host workflow

1. Create panes with `terminal_init`.
2. Start one bridge per pane pair with `bridge_start`.
3. Use `auto_forward=true` when guests should talk directly.
4. Use `intervention=true` when the host wants approval control.
5. Prefer the live room stream before sending more work:
   - GUI defaults to SSE
   - `tb2 room watch` defaults to SSE and falls back to `room_poll`
   - WebSocket stays available for advanced clients

## Guest workflow

1. Work normally inside the pane.
2. Emit `MSG:` only for cross-agent communication or host attention.
3. Do not assume every plain output line will be forwarded.
4. When blocked, emit a short `MSG:` rather than a long transcript.

## MCP-first pattern

For AI hosts, the most stable control surface is MCP:

- `terminal_init`
- `bridge_start`
- `terminal_send`
- `room_poll`
- `GET /rooms/{room_id}/stream`
- `GET /ws`
- `tb2 room watch`
- `intervention_list`
- `intervention_approve`
- `intervention_reject`
- `doctor`

## Guardrails

- Keep one room per active collaborative thread.
- Do not reuse the same pane pair across multiple rooms at the same time.
- Run `doctor` before the first session on a new machine.
- Prefer `process` on Windows and `tmux` on Linux/macOS for first-class clients.
- Treat Host-mediated orchestration as the default product path; peer-style room usage is advanced mode, not the primary UX.
