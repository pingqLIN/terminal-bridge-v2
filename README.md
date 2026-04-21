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

## Direction Update

As of `2026-04-22`, TB2 is being developed as a local-first, operator-grade governance layer for terminal-native multi-agent workflows.

That means:

- TB2 stays focused on Host / Guest / Human orchestration, review, audit, and workstream governance
- TB2 does not try to become a replacement for Codex native remote-control or computer-use surfaces
- Windows and WSL are treated as a deliberate dual-track operator model:
  - native Windows for lower-friction day-to-day use
  - WSL `tmux` for the most stable interactive collaboration loops
- a separate external runtime / workflow experiment is being used alongside TB2 to explore that dual-track model
- `codex_bridge_service` is treated as a closed side prototype for Codex-native remote control and is no longer part of the TB2 mainline direction

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
- an experimental operator control surface for teams that already understand terminal-native AI workflows
- a governance layer over terminal-native workstreams rather than a general remote-control replacement

TB2 is not designed to be:

- a publicly exposed remote control plane
- a hard-enforced approval or authorization boundary

## Support Tiers

| Tier | Status | Intended use |
| --- | --- | --- |
| `local-first-supported` | supported | loopback-only operator workflows on one trusted machine |
| `private-network-experimental` | experimental | private-network access with explicit `--allow-remote` acknowledgment and external controls |
| `public-edge-unsupported` | unsupported | internet-facing exposure or any expectation that TB2 itself is a hard auth boundary |

## Governance Direction

TB2 governance is moving toward a layered policy model so platform differences, model differences, and task-mode differences do not stay scattered across docs and operator habit.

The current intended layering order is:

1. `base`
2. `model`
3. `environment`
4. `instruction_profile`

The near-term goal is a simulation-first, report-first, no-mutation governance surface that can explain:

- which layers matched
- which effective config is currently implied
- where each effective key came from

This future no-mutation posture applies to the layered governance resolver.
It does not replace the existing mutable per-workstream controls such as review pause / resume, dependency updates, or `workstream_update_policy`.
In other words, TB2 should first become better at explaining layered governance before it starts auto-mutating that higher-level policy surface.

See [Governance Layering](docs/governance-layering.md).

## Why Teams Choose TB2

| Decision point | TB2 answer |
| --- | --- |
| You want real terminals, not a toy chat sandbox | Bridges map onto actual panes, shells, and operator workflows |
| You need Host AI, Guest AI, and Human review in one loop | Rooms, interventions, and approval gates are first-class |
| Your agents use different clients | CLI, browser GUI, and MCP can drive the same local control plane |
| Your fleet is mixed-platform | Backend fallback and shell policy are documented, with Linux runtime verification and simulated coverage for Windows, macOS, and WSL |
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
- persisted audit entries default to `mask` mode and redact text-bearing fields; use `TB2_AUDIT_TEXT_MODE=full|mask|drop` to request whether the durable record keeps raw text, masked placeholders, or metadata-only summaries, and set `TB2_AUDIT_ALLOW_FULL_TEXT=1` before `full` can take effect in service/config-driven flows
- audit clients should treat `status.audit.redaction.requested_mode`, the effective `mode`, `raw_text_opt_in_acknowledged`, and `raw_text_opt_in_blocked` as the machine-readable policy boundary for durable text storage
- direct local runs are still `memory_only` / `state_lost`, while service-managed runs persist workstream snapshots with `best_effort_restore` semantics; active room, bridge, and pending intervention state should still be treated as not fully durable
- `status.runtime` now distinguishes direct local runs from service-managed fresh starts, restart-after-loss flows, and best-effort restored service runs via `launch_mode`, `snapshot_schema_version`, and `continuity` metadata
- `status.workstreams[*].health` now surfaces per-workstream severity, alert summaries, escalation level, and silent-stream detection
- `status.fleet` now aggregates `healthy`, `warn`, `critical`, and escalation counts so one noisy workstream is easier to isolate
- `audit_recent` now accepts `workstream_id` for fleet-safe governance review
- `status.workstreams[*]` now also exposes `policy` and `review_mode` so operators can distinguish `auto`, `guarded`, `paused`, and `manual` review states
- MCP operators can now call `workstream_list`, `workstream_get`, `workstream_pause_review`, `workstream_resume_review`, and `workstream_update_policy` to pause review or tune per-workstream guardrails without falling back to ad hoc bridge-only targeting
- `status.reconciliation` and `status.fleet` now surface `orphaned_rooms`, `orphaned_workstreams`, and `stale_workstreams` so fleet drift is visible without reading raw room state
- MCP operators can now call `workstream_stop` and `fleet_reconcile` to stop broken workstreams or clean up orphaned runtime artifacts through an explicit remediation path
- workstreams now expose `dependency` metadata with `main` / `sub` topology, child linkage, and blocked-parent reasons directly in `status.workstreams[*]`
- per-workstream `pending_limit` is now enforced as a real quota guard, and operators can update `tier` / `parent_workstream_id` through `workstream_update_dependency`
- the GUI Diagnostics card now exposes pause / resume review, stop-workstream, and fleet-reconcile controls for the selected workstream

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

Recommended operator split:

- use native Windows when the goal is lower-friction day-to-day launching and local operator work
- use WSL `tmux` when the goal is the most stable terminal-native collaboration loop

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

If you intentionally bind beyond loopback, add `--allow-remote` and treat the deployment as `private-network-experimental`.

### MCP-first

```bash
python -m tb2 server --host 127.0.0.1 --port 3189
```

Then register:

- Codex CLI: `codex mcp add tb2 --url http://127.0.0.1:3189/mcp`
- Claude Code: `claude mcp add --transport http -s user tb2 http://127.0.0.1:3189/mcp`
- Gemini CLI: `gemini mcp add tb2 http://127.0.0.1:3189/mcp --transport http --scope user`

Non-loopback MCP binding now requires explicit acknowledgment:

```bash
python -m tb2 server --host 10.0.0.5 --port 3189 --allow-remote
```

## Chrome Sidepanel Compatibility

TB2 now also exposes a localhost compatibility layer for the existing `chrome-sidepanel-ai-terminal` client.

- `GET /health`
- `POST /v1/tb2/rooms`
- `GET /v1/tb2/poll?roomId=<id>&afterId=<n>`
- `POST /v1/tb2/message`

Current behavior:

- room creation initializes a real TB2 session and room id
- prompt dispatch uses one-shot `codex exec` runs and wraps recent room transcript into each request
- poll returns streaming log previews via `streamKey` / `replace` / `final` metadata before the final assistant message lands
- browser-origin checks still assume loopback, but localhost browser apps and `chrome-extension://...` clients are both accepted on loopback

See [Sidepanel Compatibility](docs/sidepanel-compat.md).

### Sidepanel preview

<img src="docs/images/control-center.png" alt="terminal-bridge-v2 control console preview" width="960">

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
- [Security Posture](docs/security-posture.md)

### Architecture and integration

- [AI Orchestration](docs/ai-orchestration.md)
- [Governance Layering](docs/governance-layering.md)
- [MCP Client Setup](docs/mcp-client-setup.md)
- [Sidepanel Compatibility](docs/sidepanel-compat.md)
- [Use Cases and Workflow Index](docs/use-cases.md)
- [Development Execution Plan (zh-TW)](docs/development-execution-plan.zh-TW.md)

### Traditional Chinese

- [README.zh-TW.md](README.zh-TW.md)
- [docs/getting-started.zh-TW.md](docs/getting-started.zh-TW.md)
- [docs/role-guides.zh-TW.md](docs/role-guides.zh-TW.md)
- [docs/control-console.zh-TW.md](docs/control-console.zh-TW.md)
- [docs/platform-behavior.zh-TW.md](docs/platform-behavior.zh-TW.md)
- [docs/governance-layering.zh-TW.md](docs/governance-layering.zh-TW.md)
- [docs/platforms/compatibility-matrix.zh-TW.md](docs/platforms/compatibility-matrix.zh-TW.md)
- [docs/platforms/standard-operations.zh-TW.md](docs/platforms/standard-operations.zh-TW.md)
- [docs/development-execution-plan.zh-TW.md](docs/development-execution-plan.zh-TW.md)

## Safety Notes

- Treat TB2 as local-first, high-trust, operator-grade tooling rather than a public control service.
- Keep server binding on `127.0.0.1` unless you fully trust the network path.
- If you bind to a non-loopback address, TB2 now requires explicit `--allow-remote` acknowledgment.
- Browser-origin checks are intentionally limited to localhost-style origins, so keep GUI and MCP access on loopback.
- Chrome extension origins are accepted only on loopback for the sidepanel compatibility surface; do not treat that as remote auth.
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
