# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and this project follows Semantic Versioning in a lightweight, pragmatic way.

## [Unreleased]

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
