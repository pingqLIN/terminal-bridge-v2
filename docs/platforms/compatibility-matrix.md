# Platform Compatibility Matrix

This document records what has been runtime-validated, what is covered by automated simulation, and what still needs native-machine confirmation.

## Validation Snapshot

Current rewrite snapshot:

- Date: `2026-03-13`
- Runtime-validated environment: Linux, Python `3.12.3`
- Validation result: full `pytest` suite passed (`245 passed`)
- Simulated in automated tests: Windows backend selection, Windows shell policy, macOS state-root behavior, WSL `tmux` invocation, PowerShell and `cmd.exe` shell semantics

Validation levels used below:

- `runtime-verified`: executed in the current workspace during this rewrite
- `simulated`: covered by automated tests or deterministic code-path assertions, but not executed on a native machine in this session
- `not verified`: supported by design only, with no current-session validation

## OS Matrix

| OS / Environment | Default Backend Policy | Validation Level | Notes |
| --- | --- | --- | --- |
| Native Linux | `tmux` if installed, else `process` | runtime-verified | Full suite passed in the current workspace. |
| Native macOS | `tmux` if installed, else `process` | simulated | POSIX shell behavior is shared with Linux; service state-root behavior is covered by tests. |
| Native Windows | `process` if `pywinpty` exists, else `tmux` if `wsl.exe` exists, else `pipe` | simulated | Default shell ignores `SHELL` and prefers `pwsh`, `powershell.exe`, then `COMSPEC`. |
| Native Windows -> WSL `tmux` | `tmux` through `wsl -d <distro> -- sh -lc` | simulated | Covered by backend tests for capture and command routing. |
| Inside WSL | `tmux` if installed, else `process` | simulated | Same POSIX shell semantics as Linux, but `tmux` commands run directly inside WSL. |

## Backend Matrix

| Backend | Best Fit | Platform Notes | Validation Level |
| --- | --- | --- | --- |
| `tmux` | interactive host/guest sessions on Linux, macOS, and WSL | Pane ids look like `session:0.0` / `session:0.1`; capture uses `sh -lc` and quoted pane targets | runtime-verified on Linux, simulated elsewhere |
| `process` | interactive sessions without a multiplexer | Pane ids look like `session:a` / `session:b`; Windows requires `pywinpty`; POSIX uses a PTY | runtime-verified on Linux, simulated on Windows |
| `pipe` | non-interactive or fallback workflows | Best when the client can operate over plain stdin/stdout; no TUI support | runtime-verified on Linux, simulated on Windows shell variants |

## Shell Matrix

| Shell | Launch Args | Enter Sequence in `pipe` | Enter Sequence in `process` PTY | Validation Level |
| --- | --- | --- | --- | --- |
| `pwsh` / `powershell.exe` | `-NoLogo -NoProfile` added automatically | `\\r\\n` | `\\r\\n` | simulated |
| `cmd.exe` | no extra args | `\\r\\n` | `\\r\\n` | simulated |
| `bash` | no extra args | `\\n` | `\\r` | runtime-verified on Linux |
| `zsh` | no extra args | `\\n` | `\\r` | simulated |
| `sh` | no extra args | `\\n` | `\\r` | runtime-verified through `tmux` helper path |

## Path And State Differences

| Surface | Windows | macOS | Linux / WSL |
| --- | --- | --- | --- |
| Service state root | `%LOCALAPPDATA%\\tb2` or `~/AppData/Local/tb2` | `XDG_STATE_HOME/tb2` if set, else `~/Library/Application Support/tb2`, but legacy `~/.local/state/tb2` is preserved when existing state files are found | `XDG_STATE_HOME/tb2` if set, else `~/.local/state/tb2` |
| Default shell override | `TB2_SHELL` only | `TB2_SHELL`, then `SHELL` | `TB2_SHELL`, then `SHELL` |
| Default pane naming | `session:a`, `session:b` for `process` / `pipe` | `session:0.0`, `session:0.1` for `tmux`; `session:a`, `session:b` for `process` / `pipe` | same as macOS |

## Standard Recommendations

| Scenario | Recommended Combination | Why |
| --- | --- | --- |
| Host + Guest coding on Linux | `tmux` + `codex` / `claude-code` / `gemini` / `aider` | Best visibility and stable pane addressing |
| Host + Guest coding on macOS | `tmux` when installed, else `process` | Same operator model as Linux, with fewer shell surprises when `tmux` is present |
| Host + Guest coding on Windows | `process` + `pwsh` | Best native interactive path when `pywinpty` is installed |
| Windows machine without `pywinpty` | `tmux` through WSL, else `pipe` | Avoids a broken default interactive path |
| Non-interactive automation | `pipe` | Simplest I/O surface for scripting or JSON-mode tools |

## Known Behavioral Differences

- `process` PTY on POSIX sends Enter as `\\r` because terminal key semantics are not the same as plain text newline.
- `pipe` on POSIX sends Enter as `\\n` because it writes to stdin, not a terminal key event stream.
- Windows default shell policy ignores `SHELL` so Git Bash or MSYS environment variables do not hijack the native Windows default unexpectedly.
- Native macOS keeps old `~/.local/state/tb2` state files visible when they already exist, so upgrades do not strand an existing service.

## Decision Checklist

- Run `python -m tb2 doctor` before first use on a new machine.
- If `process` is unavailable on Windows, install `pywinpty` or move to the WSL `tmux` path.
- If `tmux` is missing on Linux or macOS, use the `process` backend rather than forcing `tmux`.
- Choose `pipe` only when the client does not need a real terminal.
