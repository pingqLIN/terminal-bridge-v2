# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and this project follows Semantic Versioning in a lightweight, pragmatic way.

## [Unreleased]

### Added
- Traditional Chinese review artifacts covering release objections, devil's-advocate findings, remediation planning, and a P1 external review brief.
- Regression coverage for dead-process pruning in `process` / `pipe` session views, duplicate `bridge_start` room reuse, forbidden-origin transport requests, and incomplete MCP POST bodies.
- Machine-readable room event source fields so consumers can distinguish client, terminal, bridge automation, intervention, and control events without parsing `author`.
- Opt-in append-only JSONL audit trail support for room messages, bridge lifecycle, intervention actions, and direct operator control actions.
- Machine-readable security posture snapshots across `status`, `doctor`, `/healthz`, and `/mcp`, plus explicit non-loopback bind acknowledgment via `--allow-remote` / `TB2_ALLOW_REMOTE=1`.
- Release-facing security posture docs and support-tier guidance for local-first, private-network experimental, and public-edge unsupported adoption paths.
- Per-workstream health, alert severity, escalation, and silent-stream detection surfaced through `status.workstreams[*].health` and `status.fleet`.
- `audit_recent` now accepts `workstream_id` for fleet-safe governance review.
- New workstream action tools: `workstream_list`, `workstream_get`, `workstream_pause_review`, `workstream_resume_review`, and `workstream_update_policy`.
- New remediation tools: `workstream_stop` and `fleet_reconcile`.
- New dependency tooling: `workstream_update_dependency`, `bridge_start` tier metadata, and explicit `main` / `sub` topology in workstream status payloads.

### Changed
- README and FAQ now describe TB2 as local-first, high-trust operator tooling and clarify that approval gates are workflow controls rather than a hard security boundary.
- Local HTTP, SSE, and WebSocket control surfaces now enforce localhost-only `Origin` checks and safer request parsing.
- `tb2 doctor` now surfaces readiness, validation coverage, and next-step guidance alongside backend and client probes.
- Packaging metadata now declares the README, classifiers, project URLs, and adoption posture more clearly for external consumers.
- Bridge status now reports auto-forward guard state, and runaway auto-forward flows now switch into intervention until pending review is resolved.
- `status` now reports audit-trail enablement and destination details so operators can verify persistence state from the active control surface.
- GUI diagnostics now surface audit enablement and recent persisted entries for the active room / bridge scope.
- Audit persistence now rotates by size with bounded file retention instead of growing a single unbounded JSONL forever.
- GUI diagnostics audit view now supports event-level filtering and recent-entry limits for faster review.
- Persisted audit entries now redact text-bearing fields and expose the active redaction mode through the audit status snapshot.
- Audit text redaction now supports `mask`, `drop`, and explicit `full` modes so operators can choose between privacy and verbatim retention.
- `status.workstreams[*]` and `bridge_details[*]` now surface per-workstream governance `policy` plus `review_mode` so operators can see when review is `auto`, `guarded`, `paused`, or `manual`.
- `status` now surfaces reconciliation metadata for `orphaned_rooms`, `orphaned_workstreams`, and `stale_workstreams` so runtime drift is machine-readable.
- Per-workstream policy now includes enforced `pending_limit` quota guards, and `status.workstreams[*].dependency` now reports parent / child linkage and dependency blockers.
- GUI diagnostics now surface selected-workstream remediation controls for pause / resume review, stop-workstream, and fleet reconcile flows.

### Fixed
- HTTP, SSE, and WebSocket request handling now apply bounded-size, timeout, incomplete-body, and numeric-input validation more consistently.
- Backend caching now distinguishes shell and distro configuration, while `process` and `pipe` backends prune dead child state and reuse live panes instead of respawning duplicates.
- Bridge worker polling now waits once per capture cycle instead of once per output line, reducing burst-output latency.
- Burst and streak-based auto-forward loops now trip a breaker before unbounded terminal delivery, preserve the triggering handoff in the pending queue, and re-arm after review.
- Service-managed workstream restore now preserves per-workstream policy snapshots and guarded-review state instead of collapsing everything back to default bridge behavior.
- Operators now have an explicit remediation path for broken runtime artifacts instead of relying on ad hoc room cleanup or manual bridge-id hunting.
- Remote-control and restore flows now preserve the Phase 9 workstream contract, including default `tier` metadata and quota-guard recovery state.

## [0.2.0] - 2026-03-26

### Added
- Role-guided docs for Host AI, Guest AI, and Human Operator workflows.
- Dedicated control-console, platform-behavior, compatibility-matrix, and standard-operations guides.
- Shared OS utility layer for backend selection, shell defaults, and Enter-sequence policy.
- Regression coverage for platform policy, room-to-bridge resolution, and shell-aware remote control.

### Changed
- GUI presets and control-surface copy were rebuilt around workflow-first operator entry points.
- CLI and MCP intervention flows can now resolve bridges from `room_id` when `bridge_id` is unknown.
- Backend defaults now follow platform capability detection instead of fixed OS-only assumptions.
- Service state paths now use OS-appropriate defaults, including macOS Application Support handling.
- README and onboarding docs were rewritten to match the current product surface and support matrix.

## [0.1.0] - 2026-03-11

### Added
- AI-first room, bridge, and intervention workflow documentation.
- SSE and WebSocket room streaming support alongside `room_poll`.
- Workflow-first GUI and `tb2 room` operator CLI.
- Cross-platform service management and MCP-first control surface.
- Regression coverage for remote control, room transport, and intervention flows.
