# terminal-bridge-v2 vs acpx — Project Comparison

This document compares **terminal-bridge-v2** (`tb2`) and **[acpx](https://github.com/openclaw/acpx)**, two tools that help AI agents interact with CLI coding agents. They solve related but distinct problems and are best understood as complementary rather than competing.

---

## TL;DR

| Dimension | terminal-bridge-v2 (tb2) | acpx |
|-----------|--------------------------|------|
| **Approach** | PTY scraping — polls terminal screen | ACP protocol — structured JSON messages |
| **Language** | Python ≥ 3.9 | TypeScript / Node.js ≥ 18 |
| **Session model** | In-memory, server-lifetime | Persistent to `~/.acpx/sessions/` |
| **Human oversight** | ✅ Approve / edit / reject queue | ❌ Not built-in |
| **Multi-agent bridging** | ✅ Two panes, auto-forward | ❌ Single agent focus |
| **Real-time monitoring** | ✅ Continuous adaptive polling | ❌ Request/response only |
| **Named sessions** | ❌ | ✅ `-s/--session <name>` |
| **Prompt queuing** | ❌ | ✅ Queue-aware IPC |
| **Fire-and-forget** | ❌ | ✅ `--no-wait` |
| **Output formats** | Text only | `text` / `json` / `quiet` |
| **Config files** | ❌ | ✅ global + project JSON |
| **MCP server** | ✅ 14-tool JSON-RPC HTTP API | ❌ |
| **Web GUI** | ✅ Built-in at `/` | ❌ |
| **Backends** | tmux / process+ConPTY / pipe | ACP adapters via `npx` |

---

## Approach

### terminal-bridge-v2 — PTY scraping

tb2 attaches to existing terminal panes (via tmux, ConPTY, or a pipe) and **polls** the screen content at configurable intervals. A hash-based diff engine detects new output lines in O(n) time. Any `MSG:` prefixed line from pane A is optionally forwarded to pane B, and vice versa.

This approach works with **any** CLI tool — Codex, Claude Code, Aider, Gemini, llama.cpp, or a custom script — because it only reads screen characters. It requires no changes to the wrapped tool.

### acpx — Agent Client Protocol (ACP)

acpx communicates with coding agents using the **Agent Client Protocol**, a structured JSON-RPC protocol. Instead of scraping characters from a PTY, acpx exchanges typed messages (`session/new`, `session/prompt`, `tool_call`, etc.) with ACP-compatible adapters.

This gives acpx access to rich structured events — thinking steps, tool-call status, diffs — without ANSI scraping. It requires an ACP adapter for each agent (`codex-acp`, `claude-agent-acp`, native Gemini/OpenCode support, etc.).

---

## Feature-by-feature comparison

### Session persistence

| | tb2 | acpx |
|---|---|---|
| State storage | In-memory (lost on restart) | `~/.acpx/sessions/*.json` |
| Cross-invocation resume | ❌ | ✅ |
| Named parallel sessions | ❌ | ✅ `-s <name>` |

tb2 server state is ephemeral — rooms and bridges are gone when the server restarts. acpx stores session metadata to disk so multi-turn conversations survive restarts.

### Human oversight

tb2 has a first-class human-intervention layer: every `MSG:` auto-forward can be queued for human review before delivery. Reviewers can approve, edit, or reject each message individually or in bulk. This is tb2's flagship feature and has no equivalent in acpx.

### Prompt queuing and fire-and-forget

acpx queues prompts per session via IPC (Unix socket or Windows named pipe). Multiple `acpx codex "..."` invocations submitted while a session is busy are serialised and executed in order. `--no-wait` returns immediately after acknowledging the queue. tb2 has no prompt queue — commands are sent directly.

### Output formats

acpx supports `--format text` (default), `--format json` (NDJSON event stream), and `--format quiet` (final text only). This makes acpx well-suited for automation pipelines. tb2 always outputs human-readable text.

### Multi-agent bridging

tb2 is designed for **two-pane bridging**: agent A and agent B run in separate terminal panes, and tb2 shuttles messages between them. acpx is focused on a single agent at a time. For multi-agent workflows tb2 is the right choice.

### MCP server

tb2 exposes 14 tools via JSON-RPC over HTTP (`POST /mcp`). Any MCP-compatible host (Codex CLI, Claude Code, Gemini CLI) can control tb2 remotely. acpx has no MCP server.

---

## When to use each tool

### Choose terminal-bridge-v2 when you need to:

- Bridge two agents so they relay messages to each other
- Continuously monitor terminal output in real time
- Put a human reviewer in the forwarding loop
- Control agents from an MCP host (Codex, Claude, Gemini)
- Work with tools that have no ACP adapter (Aider, llama.cpp, custom scripts)

### Choose acpx when you need to:

- Drive a single coding agent programmatically
- Persist sessions across invocations (`~/.acpx/sessions/`)
- Run multiple named parallel agent workstreams (`-s backend`, `-s frontend`)
- Queue follow-up prompts without waiting (`--no-wait`)
- Consume structured agent output (JSON event stream)

---

## Using the two tools together

tb2 and acpx complement each other. You can run an `acpx codex` session inside a terminal pane and then use tb2 to bridge it to a second agent:

```bash
# Pane 0.0: acpx codex session running
# Pane 0.1: second agent (e.g., Gemini CLI)

python3 -m tb2 broker \
  --a demo:0.0 \
  --b demo:0.1 \
  --profile acpx \
  --auto \
  --intervention
```

The `acpx` tool profile (added in tb2 v0.1.0) strips ANSI from acpx's structured output lines so the broker sees clean text. Human intervention can be layered on top to review any forwarded messages before delivery.

---

## Architecture diagrams

### terminal-bridge-v2

```
┌──────────────────────────────────────────────────────┐
│  MCP hosts (Codex CLI / Claude Code / Gemini CLI)    │
└────────────────────┬─────────────────────────────────┘
                     │ JSON-RPC POST /mcp
       ┌─────────────▼──────────────┐
       │  tb2 MCP server (:3189)    │
       │  ┌────────────────────┐    │
       │  │  Bridge Worker     │    │
       │  │  (adaptive poll)   │    │
       │  └───┬────────────────┘    │
       │      │ capture_both()      │
       │  ┌───▼──────┐  ┌────────┐  │
       │  │  Pane A  │  │ Pane B │  │
       │  │ (Agent)  │  │(Agent) │  │
       │  └──────────┘  └────────┘  │
       └────────────────────────────┘
```

### acpx

```
┌─────────────────────────────────────────────┐
│  acpx CLI invocation                        │
│   acpx codex "fix the tests"                │
└────────────────┬────────────────────────────┘
                 │ ACP JSON-RPC
  ┌──────────────▼──────────────────────────┐
  │  ACP adapter (codex-acp / claude-agent- │
  │  acp / gemini native / …)               │
  └──────────────┬──────────────────────────┘
                 │ spawns
         ┌───────▼──────────┐
         │  Coding agent    │
         │  (Codex / Claude │
         │   / Gemini / …)  │
         └──────────────────┘
```

---

## Summary

| Scenario | Recommended tool |
|----------|-----------------|
| Two-agent relay with human review | **tb2** |
| Single-agent persistent sessions | **acpx** |
| MCP-driven programmatic control | **tb2** |
| Structured JSON output pipeline | **acpx** |
| Parallel named workstreams | **acpx** |
| Works with any CLI tool (no ACP adapter) | **tb2** |
| Monitor acpx sessions from another agent | **tb2 with `acpx` profile** |
