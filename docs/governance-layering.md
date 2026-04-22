---
description: Minimal TB2 governance layering contract for precedence, effective config, and provenance
---

# Governance Layering

## Purpose

This document defines the minimal governance layering contract for TB2.

The current goal is not to auto-apply governance into every runtime path.
The goal is to give operators, docs, and future implementation work one shared language for precedence and provenance.

## Current Posture

This layer is currently:

- simulation-first
- report-first
- no-mutation

Here, `no-mutation` applies to the future layered governance resolver.

It does not replace TB2's existing mutable runtime controls such as:

- `workstream_update_policy`
- `workstream_update_dependency`
- `workstream_pause_review`
- `workstream_resume_review`

In other words:

- the existing per-workstream control layer remains mutable
- the layered governance resolver should first explain what policy ought to be in effect

## Layer Order

The current intended override order is:

1. `base`
2. `model`
3. `environment`
4. `instruction_profile`

Later layers override earlier layers when the same key appears in multiple places.

## Meaning of Each Layer

| Layer | Purpose |
| --- | --- |
| `base` | repo-default guardrail, audit, and review baseline |
| `model` | review cadence, handoff density, and update rhythm for different agent clients or model classes |
| `environment` | runtime differences such as native Windows, WSL, Linux, or private-network operator contexts |
| `instruction_profile` | task-mode differences such as `quick-pairing`, `approval-gate`, `mcp-operator`, or `diagnostics` |

## Expected Resolver Output

When a governance resolver is implemented, its minimal output should include:

- `matched_layers`
- `effective_config`
- `provenance`

Batch A also establishes a minimal runtime boundary:

- `review_mode` is the first authoritative governance key
- `preferred_backend` remains advisory
- per-workstream policy keys such as `rate_limit` and `pending_limit` remain mutable exception keys outside the authoritative subset
- operator `pause_review` / `resume_review` now behave as explicit review-mode exceptions only when the baseline is `auto`; they do not override an authoritative `manual` baseline
- `workstream_update_policy` now records policy mutation as a mutable exception layer over the policy baseline rather than as an unqualified config change

Batch B starts exposing machine-readable decision consumption:

- each workstream governance payload now includes `decision_trace`
- fleet status now summarizes governance exception pressure through `governance_review_overrides`, `governance_policy_overrides`, and `governance_exceptions`

### `matched_layers`

Lists the layers that actually matched for the current resolution.

### `effective_config`

Lists the configuration that is effectively in force after override resolution.

### `provenance`

Explains which layer supplied each final key.

## Current CLI Entry

Use:

```bash
python -m tb2 governance resolve \
  --model gpt-5.4 \
  --environment wsl-tmux \
  --instruction-profile approval-gate \
  --json
```

This returns the current simulated governance resolution without mutating runtime state.

When a caller explicitly sets an `instruction_profile` during `bridge_start`, TB2 may project the authoritative `review_mode` subset into runtime startup behavior. This is intentionally narrow and does not yet imply general auto-apply.

The same read-only resolution is also available through the MCP/server tool:

- `governance_resolve`

The governance overlay contract is now published in-repo:

- schema: [`../schemas/governance.layers.schema.json`](../schemas/governance.layers.schema.json)
- sample: [`../examples/governance.layers.sample.json`](../examples/governance.layers.sample.json)
- CLI schema output: `python -m tb2 governance schema`
- CLI sample output: `python -m tb2 governance sample`

An optional JSON overlay is also supported:

```bash
python -m tb2 governance resolve \
  --environment wsl-tmux \
  --instruction-profile approval-gate \
  --config ./governance.layers.json \
  --json
```

The overlay file should use the same top-level layer keys:

```json
{
  "environment": {
    "wsl-tmux": {
      "preferred_backend": "tmux"
    }
  },
  "instruction_profile": {
    "approval-gate": {
      "approval_mode": "required"
    }
  }
}
```

## What This Doc Does Not Claim

This document does not claim that TB2 already has:

- a full governance resolver
- automatic apply / rollback
- drift audit or policy sync
- automatic projection from docs into runtime behavior

It only claims that:

- the precedence model is now defined
- the intended effective payload shape is defined
- future governance work should stop scattering policy meaning across README text, presets, and operator habit

## Relationship to Runtime Controls

TB2 already has a mutable runtime action layer for:

- review pause / resume
- policy mutation
- dependency mutation
- remediation action

Governance layering does not replace that action layer.
It provides the higher-level language needed to answer:

- why a policy is in effect
- whether it came from `base`, `model`, `environment`, or `instruction_profile`
- which future keys should remain advisory versus safely applyable

## Suggested Next Steps

1. Fix the docs and sample payloads first.
2. Build a resolver prototype second.
3. Decide which keys are safe for apply / rollback third.
4. Add drift audit or guard tasks only after the above is stable.
