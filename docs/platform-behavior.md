# Platform and Terminal Behavior

This document records what TB2 behavior has been validated on real runtime, what is covered by automated tests, and what differs across backends, shells, and transports.

## Validation Snapshot

Recorded on March 28, 2026.

| Area | Validation mode | Current note |
| --- | --- | --- |
| Linux runtime | executed locally | full pytest suite passed in the current workspace: `310 passed` |
| `tmux` workflow | executed locally | end-to-end tests passed in the current Linux environment |
| Windows backend and shell policy | simulated by targeted tests | shell argv, fallback backend policy, remote-control handoff rules covered |
| macOS state-path and backend fallback policy | simulated by targeted tests | XDG precedence, legacy state preservation, POSIX shell behavior covered |

## Backend Matrix

| Backend | Pane naming | Interactive quality | Best fit | Major caveat |
| --- | --- | --- | --- | --- |
| `tmux` | `session:0.0`, `session:0.1` | highest | Linux/macOS/WSL agent collaboration | requires `tmux` |
| `process` | `session:a`, `session:b` | high | native Windows, POSIX fallback | Windows needs `pywinpty` |
| `pipe` | `session:a`, `session:b` | low for TUI, fine for line tools | non-interactive or batch tooling | no real terminal semantics |

## Default Backend Policy

TB2 now picks defaults by capability.

| Condition | Default |
| --- | --- |
| Linux / macOS with `tmux` | `tmux` |
| Linux / macOS without `tmux` | `process` |
| Windows with `pywinpty` | `process` |
| Windows without `pywinpty`, with WSL | `tmux` |
| none of the above | `pipe` |

## Shell Selection Policy

### Windows

Priority:

1. `TB2_SHELL`
2. `pwsh`
3. `powershell.exe`
4. `COMSPEC`

Important behavior:

- TB2 intentionally ignores `SHELL` on native Windows so Git Bash or MSYS environment variables do not accidentally become the default shell for native Windows Python processes.

### Linux / macOS

Priority:

1. `TB2_SHELL`
2. `SHELL`
3. `/bin/bash`
4. `/bin/zsh`
5. `/bin/sh`
6. `sh` in `PATH`

## Enter-Key Behavior by Runtime

| Runtime | Shell family | Enter sequence used by TB2 | Reason |
| --- | --- | --- | --- |
| `process` PTY | POSIX shells | `\r` | closer to actual terminal Enter behavior |
| `process` PTY | `cmd` / `pwsh` / `powershell` | `\r\n` | matches Windows console expectations |
| `pipe` | POSIX shells | `\n` | line-oriented stdin |
| `pipe` | `cmd` / `pwsh` / `powershell` | `\r\n` | line-oriented Windows shell stdin |
| `tmux` | any shell inside tmux | `tmux send-keys Enter` | pane-aware terminal semantics |

## Shell Family Notes

| Shell family | Current support posture | Notes |
| --- | --- | --- |
| `bash` / `zsh` / `sh` | first-class on POSIX | good fit for `tmux` and `process` |
| `pwsh` / `powershell.exe` | first-class on Windows | TB2 adds `-NoLogo -NoProfile` automatically |
| `cmd.exe` | supported | lowest-friction native fallback on Windows |
| Git Bash / MSYS shells on Windows | supported when explicit | not used as implicit default anymore |

## Audit Trail Opt-In

- `TB2_AUDIT=1` enables an append-only JSONL audit trail under the normal TB2 state root at `audit/events.jsonl`
- `TB2_AUDIT_DIR=/path/to/dir` writes the same stream to an explicit directory instead
- by default TB2 rotates the active audit file at 5 MiB and keeps 5 files total; use `TB2_AUDIT_MAX_BYTES` and `TB2_AUDIT_MAX_FILES` to tune that boundary
- the audit stream is off by default so test runs and casual local sessions do not silently write durable operator records
- current persisted scope is intentionally narrow: room messages, bridge lifecycle, intervention decisions, and direct operator actions such as `terminal_send` / interrupt
- `status` now includes an `audit` snapshot so operators can see whether persistence is enabled and where entries are being written
- persisted audit entries now redact text-bearing fields such as `text`, `edited_text`, and `guard_text`; default `mask` mode keeps placeholders plus metadata, and `TB2_AUDIT_TEXT_MODE=full|mask|drop` can switch between raw, masked, or metadata-only persistence
- `status.audit.redaction` exposes the active text-redaction contract so clients can reason about what was persisted
- `TB2_AUDIT_TEXT_MODE=mask` is the default; use `full` only when you explicitly want raw text in the durable log, or `drop` when you want metadata without even the `[redacted]` placeholder
- `status` now also includes a `runtime` contract that explicitly marks live control state as `memory_only` with `restart_behavior=state_lost`
- operators can read recent entries through `tb2 service audit` locally or the MCP `audit_recent` tool remotely
- the GUI Diagnostics card now mirrors that state and shows recent persisted events for the current room / bridge scope
- GUI operators can further narrow that view by event name and recent-entry limit without leaving the main console

## Service State Path Policy

| Platform | Preferred state root | Compatibility rule |
| --- | --- | --- |
| Windows | `%LOCALAPPDATA%/tb2` | falls back to `~/AppData/Local/tb2` |
| macOS | `~/Library/Application Support/tb2` | respects `XDG_STATE_HOME` and preserves legacy `~/.local/state/tb2` if state files exist |
| Linux | `$XDG_STATE_HOME/tb2` or `~/.local/state/tb2` | standard XDG-style fallback |

## Restart-State Contract

- detached service state only persists process-manager metadata such as PID, host, port, log path, and audit destination
- live room, bridge, and pending intervention state remains memory-only inside the running server
- after `tb2 service stop` or `tb2 service restart`, operators should assume live collaboration state is lost by design
- audit history can survive restart when enabled, but it is a historical ledger, not a runtime restore path

## Transport Notes

| Transport | Best use | Caveat |
| --- | --- | --- |
| SSE | default live-room watch path | one-way stream only |
| WebSocket | advanced client control | more moving parts than SSE |
| `room_poll` | scripted fallback and diagnostics | less live, more round-trips |

## Event and Guard Semantics

- room events now expose machine-readable `source` metadata alongside `author`
- `source_type`, `source_role`, and `trusted` should be treated as the contract for automation or UI logic
- bridge status includes `auto_forward_guard` so operators can tell when runaway protection has switched delivery into review

## What Was Executed vs Simulated

### Executed locally in the current environment

- full pytest suite
- e2e tests on Linux
- browser-control flows backed by the current server implementation

### Simulated by targeted tests

- Windows fallback from `process` to `tmux` or `pipe`
- Windows shell selection and PowerShell argv handling
- Windows remote-control shell handoff decisions
- macOS state-root migration and XDG precedence
- POSIX shell Enter behavior used by `process` and `pipe`

## Operational Advice

- Re-run `python -m tb2 doctor` whenever platform capabilities change.
- Treat backend choice as a machine capability question, not as a personal preference question.
- If the UI, CLI, and MCP examples disagree on pane names, check the active backend first.
- If Guest output is not being forwarded, inspect the exact `MSG:` line and the active profile before assuming bridge failure.
