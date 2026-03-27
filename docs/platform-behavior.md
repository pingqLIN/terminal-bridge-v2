# Platform and Terminal Behavior

This document records what TB2 behavior has been validated on real runtime, what is covered by automated tests, and what differs across backends, shells, and transports.

## Validation Snapshot

Recorded on March 27, 2026.

| Area | Validation mode | Current note |
| --- | --- | --- |
| Linux runtime | executed locally | full pytest suite passed: `288 passed` |
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

## Service State Path Policy

| Platform | Preferred state root | Compatibility rule |
| --- | --- | --- |
| Windows | `%LOCALAPPDATA%/tb2` | falls back to `~/AppData/Local/tb2` |
| macOS | `~/Library/Application Support/tb2` | respects `XDG_STATE_HOME` and preserves legacy `~/.local/state/tb2` if state files exist |
| Linux | `$XDG_STATE_HOME/tb2` or `~/.local/state/tb2` | standard XDG-style fallback |

## Transport Notes

| Transport | Best use | Caveat |
| --- | --- | --- |
| SSE | default live-room watch path | one-way stream only |
| WebSocket | advanced client control | more moving parts than SSE |
| `room_poll` | scripted fallback and diagnostics | less live, more round-trips |

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
