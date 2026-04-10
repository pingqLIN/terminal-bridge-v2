# Security Posture

TB2 is a local-first operator control plane.

Treat the current release posture as:

| Tier | Status | Intended use |
| --- | --- | --- |
| `local-first-supported` | supported | loopback-only CLI, GUI, and MCP workflows on one trusted operator machine |
| `private-network-experimental` | experimental | operator-managed private-network access with explicit `--allow-remote` acknowledgment and external network controls |
| `public-edge-unsupported` | unsupported | internet-facing exposure, zero-trust remote access, or any expectation that TB2 is a hard auth boundary |

## What TB2 does enforce

- default bind host stays on `127.0.0.1`
- non-loopback bind now requires explicit acknowledgment through `--allow-remote` or `TB2_ALLOW_REMOTE=1`
- browser `Origin` checks remain limited to localhost-style origins for GUI, SSE, WebSocket, and MCP POST flows
- `status`, `doctor`, `/healthz`, and `/mcp` expose a machine-readable `security` / `security_posture` snapshot

## What TB2 does not claim

- TB2 does not provide production-grade authn/authz
- approval gates and `intervention` are workflow controls, not authorization guarantees
- TB2 should not be treated as a public remote control plane

## Remote access rule

If you bind beyond loopback, do it intentionally:

```bash
python -m tb2 server --host 10.0.0.5 --port 3189 --allow-remote
```

Recommended additional controls:

- place TB2 behind VPN, SSH tunnel, or firewall ACLs
- prefer a specific private address over `0.0.0.0`
- keep operator and browser access on trusted network paths

## Operator checklist

- Run `python -m tb2 doctor` and confirm the reported support tier.
- Keep `status.security.support_tier` at `local-first-supported` unless you explicitly need private-network access.
- If you move to `private-network-experimental`, document the external controls that carry the real trust boundary.
