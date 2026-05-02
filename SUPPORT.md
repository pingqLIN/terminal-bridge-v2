# Support

## Where to ask what

- Usage questions and orchestration patterns: GitHub Discussions
- Confirmed bugs and docs fixes: GitHub Issues
- Security concerns: follow [SECURITY.md](SECURITY.md)

## Before opening an issue

Please include:

- OS and Python version
- `python -m tb2 doctor --json` output
- transport path when relevant: `room_poll`, SSE, WebSocket, MCP, GUI, or CLI
- backend and profile used
- exact commands
- expected behavior vs actual behavior

For repo checkout regressions, also include:

```bash
python3 tools/release_check.py --skip-tests
```

Use the full `python3 tools/release_check.py` when the report concerns tests, packaging, release readiness, or broad maintenance behavior.

## Self-serve docs

- [README.md](README.md)
- [docs/getting-started.md](docs/getting-started.md)
- [docs/ai-orchestration.md](docs/ai-orchestration.md)
- [docs/mcp-client-setup.md](docs/mcp-client-setup.md)
- [docs/transport-examples.md](docs/transport-examples.md)

## Maintainer note

This project currently uses a lightweight support model. Clear reproduction details help a lot and usually lead to faster triage.

Current support tiers:

- `local-first-supported`: best-effort support for loopback operator workflows
- `private-network-experimental`: narrower support, with the expectation that external network controls are part of the deployment
- `public-edge-unsupported`: not a supported operating model
