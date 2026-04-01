---
description: 2026-03-28 通盤審查後整理的 terminal-bridge-v2 開發執行書，收斂短中期修補與驗收順序
---

# terminal-bridge-v2 開發執行書

## 目的

這份文件把本輪通盤審查的結果整理成可直接執行的開發批次。

重點不是再寫一份抽象 roadmap，而是把已確認的缺口拆成：

- 哪些已在本輪落地
- 哪些屬於下一批必做項目
- 哪些需要先定義契約，再實作
- 每一批如何驗收

## 審查方式

本輪由 4 條審查線平行進行：

- runtime / architecture
- GUI / operator experience
- testing / QA
- docs / onboarding / release readiness

本輪也補跑了完整驗證：

- `.venv/bin/python -m pytest -q` => `310 passed in 14.59s`

## 狀態更新（2026-03-28）

本輪已直接落地的項目：

- GUI review queue 新增 selected handoff detail，讓 operator 可直接看到 `action`、`created_at`、route、original text、edited text
- GUI status card 新增結構化摘要 badges，把 guard、pending、subscriber、audit 狀態前景化
- audit / MCP onboarding 文件補上 `audit_recent`、`tb2 service audit`、audit-enabled service flow
- 多份 release-facing 文件的驗證快照已更新到目前主線狀態
- `Batch A` 第一段已落地：`bridge.start_existing`、`bridge.start_conflict`、`bridge.start_failed`、`room.deleted`、`room.cleaned_up` 現在都有 durable event，GUI audit filter 也已改讀單一 event catalog
- `Batch B` 第一段已落地：`status` 現在會回 machine-readable `runtime` contract，正式標示目前 restart 行為為 `state_lost`
- `Batch C` 第一段已落地：audit 文字欄位現在有 `full` / `mask` / `drop` 策略，`status.audit.redaction`、`audit_recent`、`tb2 service audit` 都已對齊同一個 contract；其中 `full` 已改成 explicit opt-in，必須再加 `TB2_AUDIT_ALLOW_FULL_TEXT=1`
- audit privacy boundary 第一段已落地：持久化 audit 透過 `TB2_AUDIT_TEXT_MODE=full|mask|drop` 統一處理 `text` / `edited_text` / `guard_text`，預設 `mask`；若要求 `full`，還必須額外確認 `TB2_AUDIT_ALLOW_FULL_TEXT=1`，而 contract 也已暴露到 `status.audit.redaction`

本輪審查後，接下來的高價值缺口已收斂成 4 大主題：

1. runtime continuity
2. audit lifecycle contract
3. audit privacy boundary
4. GUI / QA contract hardening

## 已確認缺口

### 1. Runtime continuity 仍是 memory-only

目前 `rooms`、active `bridges`、pending interventions 都只存在記憶體中。

風險：

- service restart 後，operator 會保留 audit 歷史，但失去當前控制狀態
- 無法安全恢復、繼續，或明確 unwind 重啟前的協作流程

涉及路徑：

- `tb2/server.py`
- `tb2/room.py`
- `tb2/intervention.py`
- `tb2/service.py`

### 2. Audit lifecycle taxonomy 還不完整

目前 audit 對 happy path 已可用，但 failure / conflict / reuse / cleanup 路徑還沒有完整、穩定、單一來源的事件契約。

風險：

- `bridge_start` preflight failure
- duplicate `bridge_id`
- pane-pair conflict
- room create / reuse / delete
- stale cleanup

這些控制面轉移可能沒有一致的 durable event。

涉及路徑：

- `tb2/server.py`
- `tb2/room.py`
- `tb2/audit.py`
- `tests/test_server.py`

### 3. Audit redaction contract 已初步落地，但 policy 還可再收斂

目前 text-bearing events 已不再無條件落 raw text，但 rollout policy 與哪些場景該允許 `full` 仍需收斂。

風險：

- 不同 operator policy 若沒先對齊，可能誤用 `full` 導致敏感內容落盤
- incident review 若忽略 redaction mode，可能誤把 masked audit 當成完整 transcript

涉及路徑：

- `tb2/audit.py`
- `tb2/server.py`
- `tb2/room.py`

### 4. GUI 與 QA 的 contract 仍可再收斂

本輪已補 operator 決策上下文與 status summary，而且：

- Diagnostics audit event filter 已改成讀單一 event catalog，不再是 GUI 硬編碼 taxonomy
- GUI regression 已補上 Node 驅動的 behavior probe，但仍缺 browser-level interaction test 與更完整的 DOM state 驗證

涉及路徑：

- `tb2/gui.py`
- `tb2/server.py`
- `tests/test_server.py`

## 執行批次

## Batch A：Audit Contract Hardening

### 目標

把 audit 從「可查最近事件」提升成「可做 incident review 的穩定控制面契約」。

### 範圍

- 建立單一 audit event catalog
- 補齊 reuse / conflict / failure / cleanup / delete 類事件
- 收斂 GUI 與 MCP 對 event names 的依賴

### 驗收條件

- `bridge_start` 成功、reuse、conflict、preflight failure 都有對應 durable event
- room create / reuse / delete / cleanup 有一致事件
- `audit_recent` 與 GUI filter 不再各自硬編 taxonomy
- 新增 negative-path regression tests

## Batch B：Restart-State Contract

### 目標

先定義 restart 後狀態的正式契約，再決定是「明確遺失」還是「最小恢復」。

### 範圍

- 定義 service restart 後 `status` 應如何表現
- 定義 room / bridge / pending interventions 的 continuity 邊界
- 若要恢復，至少做 minimal snapshot 或 replayable state

### 驗收條件

- `tests/test_service.py` 與 `tests/test_remote_control.py` 鎖定 restart contract
- 文件清楚說明 restart 後哪些狀態保留、哪些不保留
- operator 可以從 `status` 與 audit 明確判斷目前是 fresh/direct start，還是 restart 後 state lost

## Batch C：Audit Privacy Boundary

### 目標

讓 audit 具備可控的文字欄位處理策略，而不是無條件落 raw text。

### 範圍

- 設計 `full` / `mask` / `drop` 三級策略
- 對 `terminal.sent`、`intervention.submitted`、operator room posts 等事件套用 sanitize
- 文件與 CLI / MCP 行為同步說明

### 驗收條件

- text-bearing events 可依策略被完整保留、遮罩或移除
- 預設策略明確且文件一致
- regression tests 覆蓋各策略輸出
- `full` mode 被標示為 exception-only，需由 operator policy 明確授權後才可啟用

## Batch D：GUI / QA Contract Hardening

### 目標

把 GUI 從「字串存在」提升成「關鍵狀態轉移可驗證」。

### 範圍

- 抽出或固定 `refreshPending` / `refreshStatus` / `refreshAudit` 的 state transition contract
- 為 pending detail、status summary、audit refresh chain 補更接近行為的驗證

### 驗收條件

- stale bridge state recovery 有固定測試
- operator action 後 audit refresh chain 有固定測試
- pending detail / status summary 的關鍵輸出不再只靠 HTML grep 驗證

## 建議優先順序

1. Batch A：Audit Contract Hardening
2. Batch B：Restart-State Contract
3. Batch C：Audit Privacy Boundary
4. Batch D：GUI / QA Contract Hardening

原因：

- A 決定事件契約，是後續 GUI、MCP、incident review 的基礎
- B 決定 service restart 後的正式邊界，屬於 operator safety 問題
- C 關乎 durable data 的安全性
- D 是讓既有功能更穩，但前提仍是先把 A/B/C 的契約定好

## 本輪已完成的直接修補

### Operator surface

- review queue 新增 selected detail pane
- pending item 選取時，edit box 與 detail 會一起對齊目前項目
- status card 新增 guard / pending / transport / audit badges

### Docs and onboarding

- MCP client setup 補上 `audit_recent` 與 `tb2 service audit`
- getting started / standard operations 補上 audit-enabled service flow
- platform / compatibility / remediation 文件同步更新驗證快照

## 後續工作建議

- 下一輪不要再先加新 preset 或新 UI 元件
- 先把 audit event catalog 做成 server 單一來源
- 同一輪內把 negative-path audit tests 一起補上
- restart-state contract 若暫時不做 restore，也要先把「state is lost by design」寫成文件與測試
