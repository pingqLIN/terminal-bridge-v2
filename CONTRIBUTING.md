# Contributing to terminal-bridge-v2

Thanks for taking the time to improve `tb2`.

## Before you start

- Read [README.md](README.md) for the project story and supported paths.
- Use [docs/getting-started.md](docs/getting-started.md) for a first local setup.
- For AI-first collaboration work, read [docs/ai-orchestration.md](docs/ai-orchestration.md).

## Ways to contribute

- Report bugs with a reproducible environment and command sequence.
- Propose new integrations or workflow improvements through Discussions or issues.
- Improve docs, onboarding, support matrix details, and examples.
- Submit focused pull requests with tests when behavior changes.

## Development setup

```bash
pip install -e ".[dev]"
```

For Windows interactive support:

```bash
pip install -e ".[windows]"
```

Run the baseline test suite before opening a PR:

```bash
pytest -q -m "not e2e"
```

## Branch and PR guidelines

- The default branch is `main`.
- Keep pull requests narrow and reviewable.
- Include docs updates when the user-facing workflow changes.
- Add or update tests when behavior, parsing, transport, or guardrails change.
- Call out platform-specific behavior if the change differs across `tmux`, `process`, or `pipe`.

## Good issue reports include

- host OS and Python version
- `tb2 doctor` output
- backend used (`tmux`, `process`, or `pipe`)
- CLI client used (`codex`, `claude-code`, `gemini`, `aider`, or other)
- exact commands and observed output

## Communication

- Use Discussions for open-ended usage questions and orchestration patterns.
- Use Issues for actionable bugs, focused feature requests, and docs corrections.
- Use the security policy for confidential vulnerability reports.
