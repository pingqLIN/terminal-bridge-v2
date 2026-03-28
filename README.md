<h1 align="center">terminal-bridge-v2</h1>

<p align="center">
  <strong>One local control plane for Host AI, Guest AI, and Human operators working in real terminals.</strong>
</p>

<p align="center">
  <a href="https://github.com/pingqLIN/terminal-bridge-v2/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/pingqLIN/terminal-bridge-v2/ci.yml?branch=main&label=ci" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-%3E%3D3.9-blue.svg" alt="Python >= 3.9"></a>
  <img src="https://img.shields.io/badge/MCP-JSON--RPC-orange.svg" alt="MCP JSON-RPC">
  <img src="https://img.shields.io/badge/tested-linux%20runtime-green.svg" alt="Tested on Linux runtime">
</p>

<p align="center">
  <a href="README.zh-TW.md">繁體中文</a> •
  <a href="#why-tb2">Why TB2</a> •
  <a href="#primary-workflows">Primary Workflows</a> •
  <a href="#choose-your-role">Choose Your Role</a> •
  <a href="#platform-snapshot">Platform Snapshot</a> •
  <a href="#docs-map">Docs Map</a>
</p>

<p align="center">
  <img src="docs/images/control-center.png" alt="terminal-bridge-v2 control console preview" width="860">
</p>

## Why TB2

`tb2` is a local orchestration layer for teams that want terminal-native AI workflows without losing human control.

Use it when you need one place to run a Host AI, one or more Guest AIs, and a Human operator while keeping room-level visibility, approval gates, and cross-platform control. The same control plane can be driven from:

- CLI commands
- a browser console
- MCP-capable clients such as Codex CLI, Claude Code, and Gemini CLI

TB2 is most useful when you want terminal-native agents to collaborate, but you still need:

- a stable handoff contract
- a human approval path
- room and bridge observability
- a backend strategy that adapts to Windows, macOS, Linux, and WSL

## Positioning

TB2 is best treated today as:

- local-first, high-trust operator tooling
- an experimental control surface for teams that already understand terminal-native AI workflows

TB2 is not designed to be:

- a publicly exposed remote control plane
- a hard-enforced approval or authorization boundary

## Why Teams Choose TB2

| Decision point | TB2 answer |
| --- | --- |
| You want real terminals, not a toy chat sandbox | Bridges map onto actual panes, shells, and operator workflows |
| You need Host AI, Guest AI, and Human review in one loop | Rooms, interventions, and approval gates are first-class |
| Your agents use different clients | CLI, browser GUI, and MCP can drive the same local control plane |
| Your fleet is mixed-platform | Backend fallback and shell policy are documented and tested per environment |
| You need a UI that is approachable without losing power | Task presets simplify the first screen while keeping advanced controls reachable |

## Which Surface To Choose

| Surface | Best when | Tradeoff |
| --- | --- | --- |
| CLI | one operator already knows the panes, shell, and bridge ids | fastest path, but assumes the user already understands TB2 internals |
| Browser GUI | a human operator needs task presets, review queues, and room visibility | most approachable surface, but still local-host oriented |
| MCP endpoint | another AI client should drive actions as tools | best automation path, but assumes the client already has its own UX |
| Hybrid: MCP + GUI | an AI client drives the workflow while a human supervises delivery | strongest oversight model, but requires keeping both surfaces open |

## Primary Workflows

| Workflow | Best For | Default Surface |
| --- | --- | --- |
| Host + Guest coding loop | delegated coding, review, debugging | CLI or MCP + GUI oversight |
| Approval-gated review | human-in-the-loop forwarding | GUI `Approval Gate` preset |
| MCP control plane | Codex / Claude / Gemini orchestration | `http://127.0.0.1:3189/mcp` |

The control console now groups controls by task preset:

- `Quick Pairing`: start a fresh host + guest session and live room
- `Approval Gate`: review, edit, and release pending handoffs
- `MCP Operator`: supervise an externally-driven MCP workflow
- `Diagnostics`: capture panes, interrupt agents, and inspect status
- `Handoff Radar`: keep live room traffic and the approval queue side by side
- `Quiet Loop`: reduce the UI to launch plus live operator collaboration
- `Mission Control`: surface topology, diagnostics, and coordination together

Recent operator-facing guardrails now show up in the surfaces as well:

- room events include machine-readable `source` metadata alongside `author`
- bridge status exposes `auto_forward_guard` so the GUI can show blocked delivery states
- runaway auto-forward protection switches delivery into review instead of silently continuing
- opt-in JSONL audit trail can persist room, bridge, intervention, and operator actions via `TB2_AUDIT=1` or `TB2_AUDIT_DIR`
- persisted audit files now rotate by default at 5 MiB and keep up to 5 files total; override with `TB2_AUDIT_MAX_BYTES` and `TB2_AUDIT_MAX_FILES`
- operators can inspect persisted entries through `tb2 service audit` or the MCP `audit_recent` tool
- the GUI Diagnostics card now shows audit enablement plus recent persisted events for the active room or bridge
- the GUI audit view now supports event filtering and a bounded recent-entry limit for faster incident triage

## Quick Install

### Linux / macOS

```bash
pip install -e ".[dev]"
python -m tb2 doctor
```

### Windows

```bash
pip install -e ".[windows,dev]"
python -m tb2 doctor
```

If `doctor` reports that the Windows `process` backend is unavailable, install `pywinpty` or use the WSL `tmux` path.

## Five-Minute First Session

### CLI-first

```bash
python -m tb2 init --session demo
python -m tb2 broker --a demo:0.0 --b demo:0.1 --profile codex --auto
```

On Windows with the `process` backend, pane ids look like `demo:a` and `demo:b`.

### GUI-first

```bash
python -m tb2 gui --host 127.0.0.1 --port 3189
```

Open `http://127.0.0.1:3189/`.

### MCP-first

```bash
python -m tb2 server --host 127.0.0.1 --port 3189
```

Then register:

- Codex CLI: `codex mcp add tb2 --url http://127.0.0.1:3189/mcp`
- Claude Code: `claude mcp add --transport http -s user tb2 http://127.0.0.1:3189/mcp`
- Gemini CLI: `gemini mcp add tb2 http://127.0.0.1:3189/mcp --transport http --scope user`

## Choose Your Role

| If you are... | Start here |
| --- | --- |
| deciding whether TB2 fits your team | [Getting Started](docs/getting-started.md) |
| running the host agent or orchestrator loop | [Role Guides](docs/role-guides.md#host-ai) |
| writing guest prompts or agent output conventions | [Role Guides](docs/role-guides.md#guest-ai) |
| acting as the human reviewer or support operator | [Role Guides](docs/role-guides.md#human-operator) |
| wiring up MCP clients and automations | [MCP Client Setup](docs/mcp-client-setup.md) |

## Platform Snapshot

### Validation status recorded in this repo

- Linux: runtime-verified in the current workspace, full `pytest` suite passed
- Windows: simulated in automated tests for backend fallback, shell policy, remote-control behavior, and state paths
- macOS: simulated in automated tests for POSIX shell semantics and service state handling
- WSL: simulated in backend tests for `wsl -d <distro> -- sh -lc` `tmux` execution

### Current default backend policy

| Environment | Default |
| --- | --- |
| Windows | `process` if `pywinpty` is available, else `tmux` if WSL is available, else `pipe` |
| Linux / macOS / WSL | `tmux` if installed, else `process` |

For full shell, path, and Enter-key behavior differences, see [Platform Compatibility Matrix](docs/platforms/compatibility-matrix.md).

## Control Console

The browser console is intentionally task-filtered rather than exposing every control at once.

- primary workflow actions stay visible
- approval controls only surface in approval-centric scenarios
- raw ids and backend mapping remain available under advanced sections
- diagnostics and direct terminal operations stay complete, but no longer dominate the default layout
- built-in language toggle supports English and Traditional Chinese
- built-in layout toggle switches between balanced, wide, and stacked workspace arrangements

This keeps the UI approachable for operators while preserving the full MCP and terminal control surface.

## Docs Map

### Start here

- [Getting Started](docs/getting-started.md)
- [Role Guides](docs/role-guides.md)
- [Control Console Guide](docs/control-console.md)
- [Platform Behavior Notes](docs/platform-behavior.md)
- [Platform Compatibility Matrix](docs/platforms/compatibility-matrix.md)
- [Standard Operations](docs/platforms/standard-operations.md)

### Architecture and integration

- [AI Orchestration](docs/ai-orchestration.md)
- [MCP Client Setup](docs/mcp-client-setup.md)
- [Use Cases and Workflow Index](docs/use-cases.md)
- [Development Execution Plan (zh-TW)](docs/development-execution-plan.zh-TW.md)

### Traditional Chinese

- [README.zh-TW.md](README.zh-TW.md)
- [docs/getting-started.zh-TW.md](docs/getting-started.zh-TW.md)
- [docs/role-guides.zh-TW.md](docs/role-guides.zh-TW.md)
- [docs/control-console.zh-TW.md](docs/control-console.zh-TW.md)
- [docs/platform-behavior.zh-TW.md](docs/platform-behavior.zh-TW.md)
- [docs/platforms/compatibility-matrix.zh-TW.md](docs/platforms/compatibility-matrix.zh-TW.md)
- [docs/platforms/standard-operations.zh-TW.md](docs/platforms/standard-operations.zh-TW.md)
- [docs/development-execution-plan.zh-TW.md](docs/development-execution-plan.zh-TW.md)

## Safety Notes

- Treat TB2 as local-first, high-trust, operator-grade tooling rather than a public control service.
- Keep server binding on `127.0.0.1` unless you fully trust the network path.
- Browser-origin checks are intentionally limited to localhost-style origins, so keep GUI and MCP access on loopback.
- Treat the MCP endpoint and browser console as sensitive local control surfaces.
- Approval gates and `intervention` flows support supervised delivery, but they are workflow controls rather than a security boundary.
- Use `intervention` mode when you are validating a new profile, a new client, or a risky workflow.
- Keep one active bridge per pane pair.

## Project Support

- [CONTRIBUTING.md](CONTRIBUTING.md)
- [SUPPORT.md](SUPPORT.md)
- [SECURITY.md](SECURITY.md)
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- [CHANGELOG.md](CHANGELOG.md)
