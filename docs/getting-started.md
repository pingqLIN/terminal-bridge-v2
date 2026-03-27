# Getting Started

This is the shortest reliable path from a fresh checkout to a useful `tb2` session.

## 1. Install

### Linux / macOS

```bash
pip install -e ".[dev]"
```

### Windows

```bash
pip install -e ".[windows,dev]"
```

## 2. Run `tb2 doctor`

```bash
python -m tb2 doctor
```

Check these sections first:

- `Readiness`: whether backend, transport, and first-class client setup are actually ready
- `Validation snapshot`: what TB2 behavior was runtime-validated vs simulated in tests
- `Backends`: which backend can actually run on this machine
- `Supported CLI tools`: which first-class clients are available in `PATH`
- `recommended_backend`: what TB2 will choose by default

Typical healthy output now looks like:

```text
Readiness:
  - backend=ready  clients=ready  transport=ready
Validation snapshot:
  - linux_runtime: executed locally  full pytest suite passed in the current workspace
Next steps:
  - Use `tmux` as the default backend on this machine.
  - Run `python -m tb2 init --session demo` before opening GUI, broker, or MCP flows.
```

## 3. Pick the backend path

### Standard default policy

- Windows: `process` if `pywinpty` is available, else `tmux` through WSL, else `pipe`
- Linux / macOS / WSL: `tmux` if installed, else `process`

### Practical rule

- choose `tmux` when you want the most stable operator view on POSIX
- choose `process` when you need an interactive path without a multiplexer
- choose `pipe` only for non-interactive tools

## 4. Start your first session in 5 minutes

### CLI-first session

```bash
python -m tb2 init --session demo
python -m tb2 broker --a demo:0.0 --b demo:0.1 --profile codex --auto
```

On Windows `process` or `pipe`, pane ids look like `demo:a` and `demo:b`.

### First GUI session

```bash
python -m tb2 gui --host 127.0.0.1 --port 3189
```

Open `http://127.0.0.1:3189/`, then:

1. Start with `Quick Pairing`.
2. Click `Init Session`.
3. Click `Start Collaboration`.
4. Switch to `Approval Gate` if you want human review before delivery.

### First MCP session

```bash
python -m tb2 server --host 127.0.0.1 --port 3189
```

Register the MCP endpoint in your client, then use this sequence:

1. `doctor`
2. `terminal_init`
3. `bridge_start`
4. `room_poll` or room stream
5. `room_post` / `terminal_send`
6. `bridge_stop`

## 5. Understand the handoff contract

Cross-agent handoffs should use `MSG:`.

Example:

```text
MSG: summarize the failing assertion in tests/test_server.py
MSG: ready for review on the shell fallback patch
```

Rules:

- one actionable request per `MSG:` line
- no multi-paragraph payloads
- use `intervention` when a forwarded line should not be delivered immediately

## 6. Common first-run failures

### `process` unavailable on Windows

- install `pywinpty`
- or use the WSL `tmux` path

### `tmux` missing on Linux / macOS

- install `tmux`
- or use the `process` backend instead

### Room stream looks stale

- reconnect transport in the GUI
- or fall back to `room_poll`
- only restart the bridge after transport has been ruled out

### Wrong shell starts

- set `TB2_SHELL`
- do not rely on `SHELL` on Windows

## Next docs

- [Role Guides](role-guides.md)
- [Platform Compatibility Matrix](platforms/compatibility-matrix.md)
- [MCP Client Setup](mcp-client-setup.md)
