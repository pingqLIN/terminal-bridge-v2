---
description: 2026-04-30 依外部多 reviewer 審查結果收斂的 TB2 10 小時 project-development-loop 執行計畫
---

# TB2 10 小時開發計畫

日期：2026-04-30

依據：[external-audit-architecture-code-2026-04-30.zh-TW.md](external-audit-architecture-code-2026-04-30.zh-TW.md)

## 目標

在 10 小時 `$project-development-loop` 中，優先修掉外部審查指出的高風險基礎問題，並保持每個 batch 可測、可 review、可 rollback。

本輪不做 production deployment、secret/auth/billing/quota 變更、public remote-control surface 擴張、大型 GUI redesign、不可回復 migration。

## Execution Preflight

開始 loop 前必須：

- 確認 `git status --short --branch`
- 將本輪外部審查報告與開發計畫 commit 成獨立文件 slice
- 記錄 branch ahead-of-origin 狀態；本輪可本地繼續開發，但不自動 push
- 初始化 `.tb2-project-loop/2026-04-30-10hr/` durable state
- 若沒有啟動 `tools/overnight_loop_status.py` monitor，不把 `status.jsonl` 當成 active evidence

## Batch 1：Service state persistence and restart continuity

優先級：`P0`

來源 finding：

- Critical: Service restart continuity cannot restore real prior workstreams
- High: runtime snapshot persistence is racy and can lose or break service state

工作：

- `tb2/service.py` state persistence 加 process-wide lock
- 改用 unique temp path + atomic replace
- `_build_state()` 保留 previous `workstreams`
- 補 concurrent persistence test
- 補 restart handoff test

驗收：

- focused service tests pass
- previous `workstreams` 不會被新 process state 清空
- state write 並行呼叫不拋 shared temp file error
- concurrent read / modify / save 被序列化，較新的 snapshot 不被較舊 snapshot 覆蓋
- restart carry-forward snapshot 會出現在新 state，供 `_restore_workstreams_from_service_state()` 消費

## Batch 2：Active runtime cleanup safety

優先級：`P0`

工作：

- cleanup daemon 排除 active bridge / workstream referenced rooms
- bridge/workstream cleanup drop 時 persist snapshot
- bridge/workstream cleanup drop 時寫 audit event
- 補 active quiet bridge 不被 TTL cleanup 移除的 test

驗收：

- active bridge referenced room 不因 idle TTL 被刪
- orphan cleanup 仍可運作
- cleanup-driven drop 有 snapshot 與 durable audit event

## Batch 3：Scheduled health operational contract

優先級：`P0`

工作：

- cron command 用 safe shell quoting
- install 時建立 log parent directories
- health append/rotate 加 file lock
- log dir/file 設 user-private permissions
- 明確 `--skip-systemd` / systemd scope 行為
- 更新 EN / zh-TW standard operations docs
- systemd templates 選定 example/placeholder 或明確警告策略

驗收：

- cron tests 覆蓋空白與 shell metacharacters
- scheduled health tests 覆蓋 rotation locking / permission intent
- docs 不再暗示 cron mode 必然存在 `tb2.service`

## Batch 4：Fleet-safe mutation targeting

優先級：`P1`

工作：

- 為 mutation handlers 定義 strict resolver mode
- `bridge_stop` 加 descendant guard 或導向 `workstream_stop`
- 保留 read-only / compatibility fallback
- 補 bridge_stop with children regression test

## Batch 5：Governance provenance truth

優先級：`P1`

工作：

- compliance issue reason 區分 `startup_policy_drift` / `operator_exception`
- 或將 safe governance baseline policy 在 bridge startup 套用並記錄 provenance
- 更新 governance docs
- 補 governance compliance tests

## Batch 6：Sidepanel concurrency hardening

優先級：`P1`

工作：

- sidepanel message reserve state under lock
- spawn failure 時 rollback pending/run state
- 補 concurrent request test

## Batch 7：Service identity and release tail work

優先級：`P2`

工作：

- service PID identity 增加最低限度 command / health probe check
- release/security docs 補 operator-beta 與 private report fallback

## 10 小時 Loop 操作

使用 repo-local state：

- `.tb2-project-loop/2026-04-30-10hr/state.json`
- `.tb2-project-loop/2026-04-30-10hr/history.jsonl`
- `.tb2-project-loop/2026-04-30-10hr/status.jsonl`，只有 monitor 啟動後才視為 active evidence

每個 batch 完成條件：

- focused tests pass
- `git diff --check` pass
- commit 一個 reviewable slice
- `tools/project_loop_state.py checkpoint` 記錄完成與 next action

## First Action

從 Batch 1 開始：先寫 characterization tests，再改 persistence lock、unique temp、restart workstream carry-over。

## Review Gate

Batch 1 與 Batch 3 完成後重新跑 same-provider focused audit。review gate 只阻擋該 batch 所屬 findings 與新 regression；已排到後續 batch 的 downstream finding 記入 loop state，但不阻擋目前 batch 收尾。
