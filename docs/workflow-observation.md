# Workflow observation

TB2's second-phase observation architecture is an optional, read-only Python
component. The existing terminal, room, workstream and approval paths are unchanged.

## Run it

Install in a project virtual environment:

```bash
python -m pip install -e ".[observation]"
python -m tb2 observe demo
```

The bundled, explicitly synthetic example uses the production reducer and projector.
It shows a blocked main task and an accepted repair. The result is
`ELIGIBLE_FOR_RESUME` with `executable: false`; it never dispatches a task, contacts
a model, opens a port or starts a terminal. This is not live-agent acceptance.

## Five logical layers

| Layer | Implementation | Boundary |
| --- | --- | --- |
| Tag | `normalize.py` | Explicit domain/vocabulary; reports cannot complete tasks |
| Event | `adapters.py`, `reducer.py` | Verified source capability, closed schema, receipt order and conflicts |
| State | `model.py`, `reducer.py` | Rebuildable observation, not canonical task state |
| Relation | `relations.py` | Scoped dependency/hierarchy graph with revision tombstones |
| Projection | `projection.py` | Deterministic summary, graph and evidence references; no execution |

`SourceVerifier` is a trusted in-process integration interface, not an authentication
mechanism for arbitrary Python code. The integrator must verify exact source, task,
attempt, contract, executor and evidence bindings. JSON cannot supply these capabilities.
The test driver and its synthetic verification flags live under `tests/`, not in an
HTTP or MCP route. Runtime freshness never rewrites task lifecycle.

`ObservationJournal` offers a single-writer, hash-chained local journal, replay and
checksummed checkpoints. Corrupt checkpoints fall back to verified journal replay;
middle corruption fails closed; a truncated tail recovers the valid prefix and
disables further append. Hashes detect corruption, not hostile local modification.
There is no retention/compaction policy or power-loss durability guarantee. Keep the
journal private and use bounded sessions. Observation is opt-in and does not alter
existing terminal service availability or approval gates.

## Canonical source inspection

An optional TaskContracts inspection command calls its existing `inspect()` verifier.
Supply your own authorized task/project locations and a trusted local
`scripts/task_contract.py`. That verifier is **executed as Python code**; never take
its path from an incoming event or an untrusted sender.

```bash
python -m tb2 observe task --task-dir /authorized/task --project /authorized/project --verifier /trusted/TaskContracts-Automation/scripts/task_contract.py --project-id demo --goal-id main --as-of 2026-09-24T00:00:00.000Z
```

The command emits bounded metadata, not task prose or source paths. It brackets
verification with source digests and retries torn reads within a bounded budget.
Exit 0 means `VERIFIED_SOURCE_SNAPSHOT`, not task completion or schema-compatible
five-layer ingestion. Nonzero means the source could not be safely inspected.

Current TaskContracts v1.0–v1.2 lacks the required explicit attempt identity and
execution/acceptance references. Its READY/RUNNING/PASS vocabulary is not silently
mapped to CREATED/EXECUTING/COMPLETE. The adapter returns `event: null` and explicit
limitations. A compatible authoritative adapter is a future integration decision;
TB2 does not modify TaskContracts to manufacture one.

## Validation and adoption

Seven frozen schemas, vocabulary and portable fixtures were adopted from the
five-layer 0.1.0-rc.1 research baseline. TB2 owns this packaged offline consumer;
no new integration repository, scheduler, registry or cross-repository publisher
was introduced. JSON formatting is normalized; contract meanings are unchanged.
Runtime dependencies include real RFC3339 format validation and local-only schema
references. Defaults prohibit raw-terminal collection and automatic dispatch.

```bash
python -m pip install -e ".[dev]"
python -m pytest tests/test_workflow_observation.py tests/test_observation_graph.py tests/test_observation_taskcontracts.py -q
python -m pytest -q -m "not e2e" -p no:cacheprovider -o addopts=""
```

The suite includes 48 structural cases and 32 deterministic replay scenarios,
plus storage/privacy/graph/source-adapter regressions. Source adapter tests create
temporary tasks; they are not evidence of production task integration. Existing
provider collaboration limitations in [Validation Status](validation-status.md)
remain. No UI deployment, service restart, automatic resume or provider run is
part of this increment.
