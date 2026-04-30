# Standard Operations

This document defines the standard operator playbook for installing, launching, monitoring, and stopping `tb2` across supported environments.

## 1. Standard Install

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

If `doctor` reports that `process` is unavailable on Windows, install `pywinpty` or switch to the WSL `tmux` path.

## 2. Standard Startup

### Fresh local session

```bash
python -m tb2 init --session demo
python -m tb2 broker --a demo:0.0 --b demo:0.1 --profile codex --auto
```

On Windows, when the selected backend is `process`, pane ids will look like `demo:a` and `demo:b`.

### Browser control console

```bash
python -m tb2 gui --host 127.0.0.1 --port 3189
```

Open `http://127.0.0.1:3189/`.

### MCP server

```bash
python -m tb2 server --host 127.0.0.1 --port 3189
```

Or detached:

```bash
python -m tb2 service start --host 127.0.0.1 --port 3189
python -m tb2 service status
```

### Audit-enabled detached service

```bash
TB2_AUDIT=1 python -m tb2 service start --host 127.0.0.1 --port 3189
python -m tb2 service status
python -m tb2 service audit --lines 10
```

Use `TB2_AUDIT_DIR` when you need an explicit destination, and verify retention with `TB2_AUDIT_MAX_BYTES` / `TB2_AUDIT_MAX_FILES` when the service is meant to keep longer incident history.

## 3. Standard Health Checks

### CLI checks

```bash
python -m tb2 doctor
python -m tb2 service status
python -m tb2 service audit --lines 10
```

### HTTP checks

```bash
curl -sS http://127.0.0.1:3189/healthz
curl -sS http://127.0.0.1:3189/mcp
```

### Scheduled health check

For a long-running local control plane, keep a timer outside the TB2 service that only observes health. Do not auto-restart TB2 from this check, because active room, bridge, and pending intervention state is intentionally not fully durable.

The repo includes a reusable check:

```bash
python3 tools/tb2_scheduled_health_check.py --unit tb2.service --base-url http://127.0.0.1:3189 --log ~/.local/state/tb2/health-check.jsonl
```

It verifies:

- `tb2.service` is active
- `/health` reports `ok=true`, `ready=true`, `codexAvailable=true`, and `backendReady=true`
- `/healthz` reports `ok=true`
- `doctor` readiness reports backend, client, and transport as ready

On machines where root systemd installation is available, use the templates under `deploy/systemd/`. If user-level systemd linger is enabled, the templates under `deploy/systemd/user/` are also available.

On this workstation, user linger is disabled, so the active schedule is a user crontab entry:

```bash
crontab -l
tail -n 20 ~/.local/state/tb2/health-check.jsonl
tail -n 20 ~/.local/state/tb2/health-check-cron.log
```

### GUI checks

- `Quick Pairing` preset should show backend, profile, session, and bridge actions.
- `Approval Gate` preset should show the pending list and approval actions.
- `MCP Operator` preset should keep room and status monitoring visible for external MCP-driven control.
- `Diagnostics` preset should foreground capture, interrupt, audit state, and status.
- `Diagnostics` preset should let the operator inspect recent audit entries and narrow them by event and limit.
- `Mission Control` preset should keep status, room, and diagnostics visible at the same time.

## 4. Standard Shutdown

### Stop a bridge

```bash
python -m tb2 room pending --bridge-id <BRIDGE_ID>
python -m tb2 room reject --bridge-id <BRIDGE_ID> --id all
```

When the room has exactly one active bridge, you can use the lighter room-scoped path:

```bash
python -m tb2 room pending --room-id <ROOM_ID>
python -m tb2 room reject --room-id <ROOM_ID> --id all
```

Then stop the bridge:

```bash
python -m tb2 room watch --room-id <ROOM_ID>
```

Or stop it via MCP / GUI with `bridge_stop`.

### Stop the detached service

```bash
python -m tb2 service stop
```

### Restart the detached service

```bash
python -m tb2 service restart --host 127.0.0.1 --port 3189
python -m tb2 service status
```

Current contract:

- restart preserves service-manager metadata, persisted audit policy overrides, and any existing audit files
- restart does not preserve active rooms, bridges, or pending interventions
- `status.runtime` distinguishes direct runs, service-managed fresh starts, and restart-after-loss flows through `launch_mode` and `continuity.mode`
- operators should re-establish sessions and bridges after restart

## 5. Standard Troubleshooting

### Linux / macOS

- If `tmux` is missing, use the `process` backend instead of forcing `tmux`.
- If pane capture looks stale, reconnect the room transport before restarting the bridge.
- If the wrong shell is launching, set `TB2_SHELL`.

### Windows

- If `process` is unavailable, install `pywinpty`.
- If native Windows still cannot provide the interactive path you need, use WSL `tmux`.
- If a non-native shell was expected, remember that Windows ignores `SHELL`; use `TB2_SHELL` explicitly.

### All platforms

- Keep host binding on `127.0.0.1`.
- Keep one active bridge per pane pair.
- Prefer `intervention` mode when testing a new guest profile or a new CLI client.
- Use `pipe` only when the client does not need TUI behavior.
- If audit is part of your runbook, verify `audit.enabled`, the active file path, the active redaction mode, and a filtered `service audit` query before trusting incident history.
