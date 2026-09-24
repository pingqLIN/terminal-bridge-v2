# Temporary local validation mode

TB2 uses a temporary, explicitly approved local-validation process while hosted
GitHub Actions cannot run. This removes the CI dependency from the development
path; **it does not resolve GitHub account billing** or turn skipped checks green.

## Repository settings

The following server-side changes were applied on 2026-09-24:

- Disable the `CI` and `CodeQL` workflows (`disabled_manually`). Keep their YAML
  files intact so the same workflows can be restored.
- Remove `main`'s three required status checks: `test (ubuntu-latest, 3.11)`,
  `test (windows-latest, 3.11)`, and `analyze` (GitHub Actions app `15368`).
- Preserve the required PR review, stale-review dismissal, conversation resolution,
  force-push prohibition and branch-deletion prohibition. Existing administrator
  enforcement settings are unchanged; this mode does not authorize review bypass.

Other workflows, Dependabot/security settings and repository-wide Actions permissions
are unchanged. Those independent automations can still encounter the billing issue;
they are not these three required checks. Historical failed runs remain unchanged.

Workflow disablement is repository state, not a YAML edit or a portable setting for
forks. Do not create same-name commit statuses to impersonate GitHub Actions results.

## Local acceptance before a normal PR merge

Use a project virtual environment with development dependencies and platform extras
already installed. Run from the repository root:

```bash
python tools/release_check.py --pytest-args -q -m "not e2e" -p no:cacheprovider -o addopts=""
```

The wrapper checks diff hygiene, doctor JSON, client-profile metadata and tests.
For a narrower documentation-only change, the full non-E2E suite is also a valid
recorded check:

```bash
git diff --check
python -m pytest -q -m "not e2e" -p no:cacheprovider -o addopts=""
```

Record the tested commit/tree, platform, command, real exit code and test counts
in the PR summary. Preserve raw evidence privately; share only sanitized summaries.
The reviewer checks that the evidence still matches the submitted tree. Do not merge
using administrator bypass merely because hosted CI is unavailable.

Native Windows tests are not hosted Linux tests. Local pytest is not a replacement
for CodeQL security analysis, provider collaboration acceptance or real tmux E2E.
List these gaps explicitly rather than describing local validation as equivalent CI.

## Restore hosted validation

After the account owner resolves billing, a maintainer can restore the two workflows
and the exact backed-up required checks. Keep the private pre-change API snapshots;
restore only the status-check field, not an old copy of the whole protection object.

```bash
gh api --method PUT repos/pingqLIN/terminal-bridge-v2/actions/workflows/244512559/enable
gh api --method PUT repos/pingqLIN/terminal-bridge-v2/actions/workflows/244512560/enable
gh api --method PATCH repos/pingqLIN/terminal-bridge-v2/branches/main/protection/required_status_checks --input restore-required-status-checks.json
```

The restore payload must contain `strict: true` and the original three `checks`
with their `app_id: 15368`. Read back the workflow states and full branch protection;
confirm unrelated fields are unchanged. Run hosted checks on the exact candidate
commit before claiming hosted validation is restored. Remove this temporary policy
through a normal reviewed change after those checks succeed.

API references: [disable/enable a workflow](https://docs.github.com/en/rest/actions/workflows),
[status-check protection](https://docs.github.com/en/rest/branches/branch-protection).
