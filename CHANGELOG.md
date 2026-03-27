# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and this project follows Semantic Versioning in a lightweight, pragmatic way.

## [Unreleased]

### Added
- Traditional Chinese review, release-objection, remediation, and external-review planning docs for the current hardening pass.
- Regression coverage for dead-process pruning in `process` / `pipe` session views and duplicate `bridge_start` room reuse.

### Changed
- Local HTTP, SSE, and WebSocket control surfaces now enforce localhost-only `Origin` checks and safer request parsing.
- `process` and `pipe` backends now prune dead child state from `has_session()` and `list_panes()` results.
- Bridge startup and polling paths were tightened to avoid stale room creation and per-line latency amplification during burst output.

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
