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

No. The recommended default is local-only binding on `127.0.0.1`. If you expose it beyond localhost, treat it as a sensitive control surface and put proper network controls in front of it.

## What is the default orchestration pattern?

Host-mediated collaboration. The host owns the room and bridge lifecycle, guests emit short `MSG:` handoffs, and the human operator stays in the control loop when needed.
