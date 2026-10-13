# Validation Status

## Temporary acceptance policy — 2026-09-24

Hosted CI and CodeQL are disabled and their three required checks have been removed
from `main` under the approved [local validation policy](local-validation-mode.md).
PR review and other branch protections remain. This avoids the hosted CI dependency;
GitHub billing is unresolved, and skipped hosted checks are not passing checks.

## Second-phase observation increment — 2026-09-24

The optional [workflow observation core](workflow-observation.md) passes its 48
structural and 32 deterministic semantic scenarios. CLI demo execution and four
actual-verifier tests using temporary canonical tasks passed. The source adapter
is inspection-only (`event: null`); full authoritative ingestion and deployed UI
integration are not accepted. No provider calls or service restarts were made.
The historical collaboration evidence below remains separately scoped.

Updated: 2026-09-10. Version: 0.2.0, operator beta.

## Evidence summary

| Scope | Status | Evidence boundary |
| --- | --- | --- |
| Local non-E2E Python suite | PASS | 470 passed, 1 skipped, 4 deselected; excludes real model collaboration |
| Windows ConPTY line and single-key input | PASS | Direct qualification on 2026-08-31 |
| Partial TUI capture, strict MSG parser, pane backend reuse | PASS | Working-tree fixes and regression coverage |
| Real Host output becomes pending; rejection prevents delivery | PASS | Existing bounded two-run evidence |
| Claude Code Guest-to-Host approved delivery | INCOMPLETE | Missing Guest marker and destination delivery evidence |
| Repeatable full cross-client acceptance | INCOMPLETE | No two complete runs with both approved and rejected delivery |
| Agy CLI selecting a Claude model | LIMITED PASS | One standalone response, parsed by generic profile; not run through TB2 backend |
| Incumbent deployment, autostart, automatic recovery | UNKNOWN | Not verified in this review |

The Agy test selected `claude-sonnet-4-6` using CLI 1.1.25. Underlying provider model identity was not independently verified. The CLI warned that `--mode plan` has no effect with slash-command expansion disabled; this is not evidence of plan-mode isolation.

## Interpretation

A passing test establishes only its tested layer. Client discovery, model listings, input echo, queued/pending states, and successful approval responses do not replace destination-side delivery evidence. Qualify new clients with a fixed pairing and backend, real responses, approved delivery, rejection without delivery, and repeatability.

This sanitized summary describes the working tree, not a release claim or GitHub CI result. See the dated [compatibility matrix](platforms/compatibility-matrix.md) for historical platform evidence.

## Reproduce the test suite

After installing development dependencies:

```bash
python -m pytest -q -m "not e2e" -p no:cacheprovider -o addopts=""
```

Real tmux E2E requires a dedicated disposable test environment. Provider collaboration requires separate client access and a usage budget.
