# Roadmap

## Current focus

The second-phase [observation core](workflow-observation.md) is implemented as an
opt-in library and offline CLI. Its next integration gate is a verified source
mapping with explicit attempt and execution/acceptance identities. UI wiring and
automatic execution are not part of this increment.

- polish the AI-first onboarding path
- keep GitHub and release surfaces aligned with the operator-beta codebase
- tighten live collaboration UX around Host, Guest, and Human operator workflows
- keep the service-restart and diagnostics contracts easy for agents and operators to verify

## Near-term priorities

- richer GUI abstraction over backend and room identifiers
- stronger release and community tooling, especially issue templates and release-check commands
- deeper examples for `doctor --json`, `profiles --verbose`, scheduled health checks, and runtime continuity handoff
- more transport-level regression coverage and docs examples
- native Windows and WSL validation refreshes beyond simulated policy coverage

## Later opportunities

- deeper collaboration presets for common AI tool pairings
- richer operator analytics and room observability
- packaging and distribution improvements
- safer remote deployment patterns with explicit security posture
- reusable installer or packaging paths once the operator-beta surface stays stable

## Non-goals for now

- turning TB2 into a cloud-hosted agent platform
- hiding all terminal concepts behind generic agent abstractions
- replacing MCP with a separate orchestration protocol
