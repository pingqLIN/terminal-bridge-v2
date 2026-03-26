# AI Orchestration Guide

This guide describes TB2 from the perspective of cooperating agents instead of from the perspective of raw transport primitives.

## Role Model

TB2 is built around three active roles and one optional integration role.

### Host AI

The Host AI owns:

- plan decomposition
- room lifecycle
- pane pairing
- intervention policy
- final synthesis

Typical Host actions:

- create panes
- start or stop bridges
- approve or reject forwarded `MSG:` requests
- post operator guidance back into the room

### Guest AI

The Guest AI owns:

- focused implementation or analysis work inside one pane
- emitting concise `MSG:` lines when Host action is needed
- not polluting the handoff channel with normal shell chatter

Typical Guest actions:

- work locally in its pane
- ask for review
- ask for missing context
- signal readiness

### Human Operator

The Human Operator owns:

- choosing the launch preset
- deciding when approval is mandatory
- interrupting a pane when a tool goes sideways
- sending clarification to Host, Guest, or the whole room

### MCP Integrator

The MCP Integrator owns:

- registering TB2 with upstream clients
- mapping tools to internal workflows
- deciding whether control flows through browser UI, terminal UI, or direct tool calls

## Functional Index by Role

### Host AI functional index

| Need | TB2 surface |
| --- | --- |
| create a paired session | `terminal_init` |
| start delegation loop | `bridge_start` |
| send direct guidance | `terminal_send`, `room_post` |
| review pending requests | `intervention_list` |
| approve or edit | `intervention_approve` |
| stop risky work | `terminal_interrupt`, `bridge_stop` |

### Guest AI functional index

| Need | Contract |
| --- | --- |
| ask Host for action | emit `MSG:` |
| request review | emit one short actionable `MSG:` |
| signal state | use a machine-readable `MSG:` such as `READY_FOR_REVIEW` |
| continue local work | keep output plain, not every line should be forwarded |

### Human Operator functional index

| Need | TB2 surface |
| --- | --- |
| launch a task-oriented session | browser UI preset |
| watch live room traffic | browser UI, SSE, WebSocket, or `room watch` |
| send room-only context | `room_post` |
| send directly to Host / Guest | `room_post` with `deliver`, or browser send buttons |
| inspect terminal state | `terminal_capture` |
| recover from runaway work | `terminal_interrupt` |

## Host AI Playbook

### 1. Start from a clean room

Preferred order:

1. `terminal_init`
2. `bridge_start`
3. optional `room_post`
4. observe room stream
5. issue next work item

### 2. Pick one forwarding policy

| Policy | Settings | Use it when |
| --- | --- | --- |
| direct collaboration | `auto_forward=true`, `intervention=false` | Guest work is low-risk and high-frequency |
| approval-gated | `auto_forward=true`, `intervention=true` | forwarded actions may mutate code or infrastructure |
| room-only | `auto_forward=false` | Host wants to inspect before any cross-pane delivery |

### 3. Keep the handoff channel narrow

Recommended Guest `MSG:` patterns:

```text
MSG: summarize the failing assertion and propose the smallest fix
MSG: request Host review of the last command before retrying
MSG: READY_FOR_REVIEW
```

Avoid:

- narrative transcripts
- multiple asks in one `MSG:`
- shell prompts and formatting noise

## Guest AI Playbook

### 1. Behave like a focused worker, not a second room moderator

Do:

- produce normal output while working
- reserve `MSG:` for coordination boundaries
- keep `MSG:` text short and directly actionable

Do not:

- treat every status line as a handoff
- emit multi-line essays as `MSG:`
- assume forwarded delivery is immediate when intervention is enabled

### 2. Use explicit review states

Examples:

```text
MSG: READY_FOR_REVIEW
MSG: NEED_HOST_DECISION on dependency upgrade
MSG: BLOCKED waiting for fixture path
```

## Human Operator Playbook

### Quick Pairing

Use this when:

- you want to launch Host + Guest fast
- you do not need approval on every forwarded message
- you mainly watch the live room and only step in occasionally

### Approval Gate

Use this when:

- forwarded commands need human review
- Guest agents may touch code, tests, or shell state that should be supervised

### MCP Operator

Use this when:

- the real control plane is another MCP client
- the browser UI is mainly for transport, room, and intervention visibility

### Diagnostics

Use this when:

- you are validating backend behavior
- you need capture or interrupt more than collaboration
- the task is smoke testing or incident recovery

## Recommended Profiles

These profiles are currently the most predictable for interactive collaboration:

- `codex`
- `claude-code`
- `gemini`
- `aider`

Fallback profiles:

- `generic`
- `llama`

## Guardrails That Matter in Practice

- Use one room per active collaboration thread.
- Do not attach the same pane pair to multiple rooms at the same time.
- Re-run `doctor` whenever platform capabilities change.
- Keep Host-mediated orchestration as the default mental model; peer-to-peer chat is an advanced mode.

## Related Docs

- [Getting Started](getting-started.md)
- [Control Console Guide](control-console.md)
- [MCP Client Setup](mcp-client-setup.md)
- [Platform and Terminal Behavior](platform-behavior.md)
