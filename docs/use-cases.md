# Use Cases

`tb2` is most useful when you need terminal-native AI tools to collaborate without losing human control.

## 1. Host and guest coding loop

- Host agent owns the plan, room, and bridge.
- Guest agent works inside a pane and emits short `MSG:` handoffs.
- Human operator can watch the room, approve sensitive forwards, and interrupt when needed.

Best fit:

- code review handoffs
- multi-step refactors
- delegated debugging

## 2. MCP-first local orchestration

- Run `tb2` as a local MCP server.
- Use your preferred CLI client to call `terminal_init`, `bridge_start`, `room_post`, and intervention tools.
- Keep the control plane stable even if individual clients differ in UX.

Best fit:

- tool chaining
- reproducible local automation
- mixed-client workflows across Codex, Claude Code, Gemini, and Aider

## 3. Human-in-the-loop approval queue

- Enable intervention mode when auto-forwarding needs review.
- Approve, edit, or reject pending handoffs before they reach the target pane.

Best fit:

- production-adjacent changes
- prompts that should be reviewed before execution
- shared operator environments

## 4. Cross-platform operator console

- Use `process` on Windows and `tmux` on Linux or macOS.
- Watch live rooms through GUI, SSE, WebSocket, or `tb2 room watch`.

Best fit:

- local command center setups
- support and triage workflows
- demos where observability matters as much as automation
