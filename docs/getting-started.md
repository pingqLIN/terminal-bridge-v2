# Getting Started

[繁體中文](getting-started.zh-TW.md) · [Documentation](README.md)

## 1. Install

Requires Python 3.9 or later. Run from the root of a project checkout.

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[windows]"
```

If policy prevents activation, use `.\.venv\Scripts\python.exe` instead of `python` below; no execution-policy change is necessary.

Linux, macOS, or WSL:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

For development tests, also install `python -m pip install -e ".[dev]"`. Each AI client manages its own installation, authentication, model access, and usage charges.

## 2. Inspect local capability

```bash
python -m tb2 doctor --json
python -m tb2 profiles --verbose
```

Windows can use interactive process with pywinpty. POSIX can use tmux or process. Pipe is for non-interactive stdin/stdout and does not provide a TUI. Client discovery is not proof of provider authentication or successful collaboration.

## 3. Open one control plane

```bash
python -m tb2 gui --host 127.0.0.1 --port 3189
```

Console: http://127.0.0.1:3189/
MCP: http://127.0.0.1:3189/mcp

If a server already runs, open its URL instead of starting another server on that port. GUI and MCP share the server. Process/pipe panes must be operated through the runtime that owns them; a standalone CLI init does not make its in-memory state available to the next CLI process.

## 4. First collaboration

1. Select the backend and Host/Guest profiles; create a pane pair with Init Session.
2. Before Start Collaboration, choose Approval Gate and keep both auto-forward and intervention enabled. In TB2, auto_forward enables MSG parsing; intervention routes parsed messages to review before delivery.
3. Start configured clients in the assigned panes. Have the operator review login, trust, or model-setting requests.
4. Send one bounded, non-destructive task.
5. Have the Guest emit one MSG: line. Inspect its destination and content, then approve or reject.
6. Capture the destination pane to verify actual delivery; queued or success notifications alone are insufficient.
7. Stop the workstream and confirm its owned runtime is cleaned up.

```text
MSG: summarize the failing assertion in tests/test_server.py
```

Use one request per line. Ordinary terminal output is not a handoff. Keep intervention enabled for new clients; disable review only after qualification.

## 5. MCP and operations

For a server without browser opening:

```bash
python -m tb2 server --host 127.0.0.1 --port 3189
```

After client registration, use doctor, terminal_init, bridge_start, room_poll, and intervention_list, then approve/reject and capture the destination. Keep backend-instance and pane ownership consistent. Use workstream_stop for owned-workstream cleanup; confirm the scope reported by bridge_stop when stopping only a bridge.

For persisted audit, set TB2_AUDIT=1 before launch. Durable text defaults to mask; full text requires explicit opt-in. Service snapshots do not guarantee restoration of live terminals, subscriptions, or pending queues. See [Control Console](control-console.md) and [Security Posture](security-posture.md).

## Troubleshooting

- Windows process unavailable: check the windows extra and active Python environment.
- Stale room stream: reconnect transport or use room_poll before diagnosing the bridge.
- Pending but no delivery: inspect review state and destination capture before resending.
- Unexpected shell: inspect TB2_SHELL; Windows does not rely on SHELL.
- No client response: separate client/provider readiness from TB2 transport.

Next: [Role Guides](role-guides.md), [MCP setup](mcp-client-setup.md), [Validation Status](validation-status.md).
