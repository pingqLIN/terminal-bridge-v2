# FAQ

## Is TB2 a multi-agent framework?

Not in the abstract orchestration-library sense. `tb2` is a terminal-native control plane for CLI AI tools, with rooms, bridges, transport, and human intervention built around real terminal sessions.

## Which clients are first-class today?

The repo currently treats `codex`, `claude-code`, `gemini`, and `aider` as first-class interactive clients. `generic` and `llama` remain available for broader compatibility.

## Do I need MCP to use TB2?

No. You can use the local CLI and GUI directly. MCP is the preferred control surface when an AI host or another tool needs stable programmatic control.

## Why keep `room_poll` if SSE and WebSocket exist?

Compatibility and fallback. `room_poll` stays useful for tests, degraded environments, and simple clients, while SSE and WebSocket improve live collaboration UX.

## Is the service safe to expose publicly?

No. The recommended default is local-only binding on `127.0.0.1`. If you expose it beyond localhost, TB2 now requires explicit `--allow-remote` acknowledgment and you should treat it as a sensitive control surface behind external network controls.

## Why does TB2 require `--allow-remote` on non-loopback binds?

Because the product posture is still local-first. The flag is an operator acknowledgment that you are leaving the supported loopback path and entering a private-network experimental mode.

## Are approval gates a hard security boundary?

No. Approval presets and `intervention` flows help supervised collaboration, but TB2 still has other terminal-delivery paths. Treat approval gates as workflow controls, not authorization guarantees.

## What is the default orchestration pattern?

Host-mediated collaboration. The host owns the room and bridge lifecycle, guests emit short `MSG:` handoffs, and the human operator stays in the control loop when needed.
