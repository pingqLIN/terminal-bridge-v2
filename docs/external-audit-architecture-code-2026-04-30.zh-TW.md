---
description: 2026-04-30 external-audit-orchestrator 多 reviewer 對 TB2 架構、runtime code、operator/release surface 的審查彙整
---

# TB2 架構與程式碼外部審查報告

日期：2026-04-30

## Audit Mode

`same-provider-subagent`

本輪依 `$external-audit-orchestrator` 執行。審查採 read-only，多 reviewer 分工：

- 架構 / governance / 1+n workstream model
- runtime / state persistence / sidepanel / scheduling reliability
- docs / operator experience / release readiness

## Scope

- repo：`/home/miles/dev2/projects/terminal-bridge-v2`
- branch：`main`
- reviewed HEAD：`83af7ee Add health check log rotation and cron installer`
- scope：current HEAD plus working tree state at review time

## Reference Inputs

- `local-project`: `/home/miles/dev2/projects/terminal-bridge-v2` - audited architecture, runtime code, tests, docs, and scheduling tools
- `local-skill`: `/mnt/q/UniText/runtime/skills/external-audit-orchestrator/SKILL.md` - used audit mode, report shape, and attribution requirements
- `local-skill`: `/mnt/q/UniText/runtime/skills/project-development-loop/SKILL.md` - used 10-hour execution planning and durable loop requirements
- `local-memory`: `/home/miles/.codex/memories/MEMORY.md` - used prior TB2 governance/workstream and project-loop context

## Findings

### Critical

#### 1. Service restart continuity cannot restore real prior workstreams

`restart_service()` can overwrite previous `workstreams` during the service-manager handoff, so `_restore_workstreams_from_service_state()` may see an empty snapshot. Fix by carrying previous snapshots into the new service state and adding restart handoff tests.

### Warning / High

#### 2. Runtime snapshot persistence has race windows

State persistence is read/modify/write with a fixed temp path. Concurrent runtime updates can lose newer snapshots or collide on temp replacement. Fix with a process-wide lock, unique temp files, atomic replace, and concurrent persistence tests.

#### 3. Cleanup can remove active but quiet bridges

TTL cleanup can delete rooms based only on `last_active`, then remove active bridges/workstreams when the room disappears. Cleanup must exclude runtime-referenced rooms, persist every drop, and write audit evidence.

#### 4. Legacy `bridge_stop` can orphan dependent sub-workstreams

`workstream_stop` has descendant checks, but legacy `bridge_stop` can bypass them. Route bridge stop through fleet-safe semantics or add descendant/cascade guards.

#### 5. Mutation tools still allow implicit single-bridge targeting

The resolver can fall back to the sole active bridge. That is convenient for 1+1 mode but unsafe for fleet mutation semantics. Mutation handlers need a stricter targeting mode.

#### 6. Scheduled health check operational contract is ambiguous

cron, user-systemd, and system-systemd modes are mixed. Health checks can assume a `tb2.service` unit that standard TB2-managed service startup does not create. Clarify `--skip-systemd` / scope behavior and update EN / zh-TW docs.

#### 7. Cron installer emits unquoted shell commands

The crontab line interpolates repo, Python, URL, and log paths without shell quoting. Use safe quoting, create log directories, and add tests for spaces/metacharacters.

#### 8. Scheduled health rotation is unsafe under overlapping runs

Rotate + append lacks a lock. Overlapping cron runs can lose entries or collide during archive rename. Add file locking or cron `flock`.

#### 9. Sidepanel prompt submission has a race window

Concurrent `/v1/tb2/message` requests can both spawn Codex before pending state is reserved. Reserve state under lock and roll back on spawn failure.

#### 10. Governance policy provenance can misclassify startup drift

Governance policy drift can be reported as `workstream_update_policy` even when no operator update happened. Distinguish startup drift from operator exceptions or apply safe baseline policy at startup.

### Suggestions

- service status should not trust PID existence alone
- scheduled health logs should be permission-hardened and avoid unnecessary local path leakage
- release / packaging posture should keep local-first operator-beta boundaries clear
- security reporting should provide a concrete private fallback or state the enabled GitHub mechanism

## Assumptions

- TB2 remains local-first, loopback-supported, private-network-experimental, and public-edge-unsupported.
- 1+n first stage means fleet-managed independent pair workstreams, not single-host multi-guest orchestration.
- Native Windows / macOS runtime behavior was not validated in this audit.

## Disposition

`fix-and-rerun`

## Next Action

Fix service restart / persistence / cleanup and scheduled health operational contract first, then rerun focused same-provider audit for the completed batch scopes.
