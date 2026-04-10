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
5. If the status card shows the auto-forward guard as blocked, clear the pending queue through review to re-arm delivery.

If you intentionally bind the GUI beyond loopback, add `--allow-remote` and treat that deployment as `private-network-experimental`.

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
6. `status`
7. `audit_recent` when you need persisted incident context
8. `bridge_stop`

Non-loopback MCP binding now requires explicit acknowledgment:

```bash
python -m tb2 server --host 10.0.0.5 --port 3189 --allow-remote
```

### First audit-enabled service session

```bash
TB2_AUDIT=1 python -m tb2 service start --host 127.0.0.1 --port 3189
python -m tb2 service status
python -m tb2 service audit --lines 10
```

Use this path when you want durable operator and bridge events from the first run.
It does not change the current restart contract: live room / bridge / pending intervention state is still lost after `service stop` or `service restart`.

If the service host is not loopback, add `--allow-remote` and make sure external network controls carry the actual trust boundary.

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
- treat `source` metadata as the machine-readable signal for where an event came from; do not infer trust from `author` alone

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

### Audit looks empty

- confirm the service was started with `TB2_AUDIT=1` or `TB2_AUDIT_DIR`
- check `python -m tb2 service status` for `audit.enabled` and the active file path
- use `python -m tb2 service audit --lines 20 --event bridge.started` to verify persisted writes

### Wrong shell starts

- set `TB2_SHELL`
- do not rely on `SHELL` on Windows

## Next docs

- [Role Guides](role-guides.md)
- [Platform Compatibility Matrix](platforms/compatibility-matrix.md)
- [MCP Client Setup](mcp-client-setup.md)
- [Security Posture](security-posture.md)
