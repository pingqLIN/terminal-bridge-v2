## Summary

- What changed?
- Why was it needed?

## Validation

During [temporary local validation mode](../docs/local-validation-mode.md), record
the tested commit/tree, native platform, command, exit code, counts and unrun checks.
Hosted CI/CodeQL are not equivalent to local tests. Required PR review still applies.

- [ ] `python3 tools/release_check.py`
- [ ] focused tests listed below when the change is narrower than full release check
- [ ] docs updated if user-facing behavior changed
- [ ] platform-specific notes added when relevant

Focused tests:

-

## Checklist

- [ ] narrow scope
- [ ] tests added or updated
- [ ] no unrelated changes included
