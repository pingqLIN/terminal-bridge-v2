---
description: 評估 terminal-bridge-v2 目前拓樸是否屬於 1+1+(1監控)，並提出往 1+n 穩健擴展的開發計畫
---

# terminal-bridge-v2 `1 + n` 架構擴展開發計畫

## 1. 結論先行

目前的 `tb2`，若從**產品操作模型**來看，基本上可以描述為：

- `1` 個 Host AI
- `1` 個 Guest AI
- `1` 個 Human operator / monitor

也就是你說的 `1 + 1 + (1監控)`，這個判斷**大致正確**。

但若從**底層 runtime 能力**來看，系統並不是嚴格只支援單一協作線。現有 server 其實已經具備：

- 多個 `room`
- 多個 `bridge`
- 以 `bridge_id` / `room_id` 做解析
- `status()` 回傳整體 `rooms` 與 `bridge_details`

因此更精確的說法是：

- **現在的 UX、預設工作流、控制面心智模型是 `1 + 1 + (1監控)`**
- **現在的 server registry 與 room/bridge 資料模型，已經有「有限多實例」基礎**
- **但還沒有真正產品化成穩健的 `1 + n` 架構**

換句話說，現在不是從零開始做 `1 + n`，而是要把「已存在的多 bridge 雛形」提升成「可操作、可觀測、可治理、可恢復」的正式架構。

## 2. 目前狀態判讀

### 2.1 已經具備的 `1 + n` 基礎

- `tb2/server.py` 內有全域 `_bridges` registry，可同時持有多個 bridge。
- `tb2/room.py` 內有全域 `_rooms` registry，可同時持有多個 room。
- `_resolve_bridge()` 已支援：
  - 明確 `bridge_id`
  - 用 `room_id` fallback
  - 單一 active bridge 時自動解析
  - 多個 active bridge 時要求 caller 補 `bridge_id`
- `status()` 已回傳：
  - `rooms`
  - `bridges`
  - `bridge_details`
  - `transports`
  - `audit`
  - `runtime`

這表示系統底層已不是單例架構。

### 2.2 仍然停留在 `1 + 1 + (1監控)` 的地方

- `bridge_start` 仍然以一組 `pane_a` + `pane_b` 為中心。
- 文件與角色指南都明確假設「一條活躍協作線對應一個 room」。
- GUI 的主要控制結構仍是：
  - 一組 launch plan
  - 一組 live runtime summary
  - 一個 review queue 焦點
  - 一張 topology 主圖
- 多 bridge 雖然存在於 `status()`，但 GUI 仍偏向「目前這一組 active bridge」的操作心智。
- 目前 live collaboration state 仍以 in-memory 為主，service restart 不會恢復 active rooms / bridges / pending interventions。

### 2.3 目前最大的誤區

最需要避免的錯誤是：

- **把「可以同時存在多個 bridge」誤認成「已經支援 1+n 產品級運營」**

目前只是「server 內部可容納多個實例」，還沒有完整處理：

- 多協作線命名與分群
- 多 bridge 的排程與治理
- 多 room 的 UI 與操作縮放
- 多工作線的 fault isolation
- restart / recovery / audit continuity
- 多工作線下的 operator cognitive load

另外還有兩個不能在 `1 + n` 擴展時被模糊掉的現有邊界：

- **一組 pane pair 仍只能掛一個 active bridge**
- **`remote` 目前最多只能作為邏輯上的 location metadata，不代表 TB2 已適合做跨主機公開控制平面**

## 3. `1 + n` 的正式目標

建議把未來架構目標定義為：

> 一個 Host control plane，可同時管理多個 Guest workstreams，並讓 Human operator 以分層方式監看、審核、介入、診斷與恢復。

也就是：

- `1` 個 Host orchestration surface
- `n` 個 Guest workstreams
- `1` 個 Human operator plane
- `m` 個 rooms / bridges / transports / review queues 作為 runtime objects

這裡的關鍵不是只有 `Guest 數量增加`，而是**管理平面與執行平面必須解耦**。

### 3.1 先釐清 `1 + n` 的真正含義

在開始改資料模型前，必須先把 `1 + n` 的目標拓樸講清楚，否則 implementation 很容易從第一天就走偏。

目前至少有兩種可能：

1. **`1` 個 Host，同時對 `n` 個 Guest workstreams**
- 一個主控 Host，同時協調多個 Guest。
- 問題會集中在 fan-out、上下文切換與優先級管理。

2. **`n` 條獨立 `1 + 1` pair workstreams，由 `1` 個 operator / control plane 管理**
- 每條線仍是 `Host + Guest` pair。
- Human operator、GUI、MCP 是 fleet manager。
- 這更貼近目前 `Bridge(pane_a, pane_b)` 的現實模型。

以現有實作來看，**第二種才是穩健的第一階段目標**。因此本計畫建議先把 `1 + n` 定義成：

- `1` 個 operator / control plane
- `n` 條 pair-based workstreams

等到 workstream、routing、recovery 都穩定後，再評估是否值得演進到真正的 single-host multi-guest orchestration。

## 4. 建議的目標拓樸

### 4.1 概念分層

建議把未來拓樸切成 4 層：

1. **Control Plane**
- Host AI
- Browser GUI
- MCP client(s)
- Operator actions

2. **Coordination Plane**
- Workstream registry
- Routing policy
- Review policy
- Scheduling / assignment

3. **Execution Plane**
- Guest bridge workers
- Pane pairs or task-specific pane groups
- Room transport and subscriptions

4. **Durability / Observability Plane**
- Audit trail
- Runtime snapshots
- Recovery metadata
- Metrics / health / fault signals

### 4.2 從「Bridge」升級為「Workstream」

目前 `bridge` 是實際中心物件，但未來 `1 + n` 下，建議新增顯式上層概念：

- `workstream_id`

每個 workstream 綁定：

- 一個 room
- 一個 bridge
- 一組 pane endpoints
- 一個 profile
- 一組 routing / review policy
- 一組 health / audit metadata

這樣可以把：

- `operator 正在看哪條線`
- `哪條線 blocked`
- `哪條線是 coding / review / diagnostics 模式`

從「臨時拼接 bridge_detail」提升成正式資料模型。

## 5. 擴展時最重要的穩健性原則

### 5.1 先穩定識別，再擴張數量

`1 + n` 的第一步不是先把 GUI 畫成很多卡片，而是先定義穩定 identity：

- `workstream_id`
- `room_id`
- `bridge_id`
- `pane_group_id` 或 `session_id`
- `role` / `profile` / `task_mode`

如果 identity 沒整理好，後面所有 UI、audit、restart、批次操作都會混亂。

### 5.2 先做分群與隔離，再做總覽

多 workstream 一定會帶來操作風險。必須優先做：

- per-workstream policy
- per-workstream review queue
- per-workstream rate / guard
- per-workstream stop / interrupt
- per-workstream audit slice

不要先做「總表很帥」，卻還是共享一堆全域副作用。

同時要保留目前已經存在、而且實際上很重要的隔離規則：

- 同一組 pane pair 不允許同時掛多個 active bridge
- 同一條 workstream 的 review / interrupt / direct deliver 操作，不能默默落到其他 workstream

### 5.3 GUI 不能只做放大版，必須改成層級式導航

現在的 topology view 適合看一條線。進入 `1 + n` 後，GUI 必須變成：

- fleet summary
- workstream list
- selected workstream detail
- deep diagnostic panel

也就是：

- **總覽層**
- **單線層**
- **元件層**

而不是把現在這張圖複製成 10 張塞進同一頁。

### 5.4 restart / continuity 必須先補足

README 已明說目前 restart 不恢復 active rooms / bridges / pending interventions。

如果真的進到 `1 + n`，這會從「可接受限制」變成「運營級風險」，因為：

- 你不只會失去一條線
- 而是一次失去整個 fleet 的 live state

所以 `1 + n` 前，至少要先完成：

- workstream snapshot persistence
- pending intervention persistence
- bridge runtime state persistence
- restart recovery contract

### 5.5 `local / remote` 要先定義成什麼

如果 GUI 未來要標示 `local / remote`，建議先把它定義成**邏輯位置欄位**，而不是網路暴露能力聲明。

建議分兩層：

- `location`
  - `local_process`
  - `local_service`
  - `remote_managed`
- `trust_boundary`
  - `loopback_only`
  - `private_network`
  - `external_exposed`

原因是目前 repo 的安全定位仍明確偏向：

- localhost / loopback
- 高信任邊界
- 非公開 remote control plane

若只寫 `local / remote`，未來很容易讓 operator 誤以為 remote workstream 已自帶足夠 auth / isolation。

### 5.5 fleet mode 下必須收斂 mutation targeting

目前多個操作工具仍允許：

- 直接給 `bridge_id`
- 退而求其次給 `room_id`
- 在只有一條 active bridge 時自動猜測

這在單線模式是方便，但進入 `1 + n` 後會變成治理風險。尤其是：

- `room_post(deliver=...)`
- `terminal_interrupt`
- `intervention_approve`
- `intervention_reject`

都屬於 mutation 類操作。

因此必須先定義 fleet-safe targeting 原則：

- fleet mode 預設要求顯式 `workstream_id`
- `bridge_id` / `room_id` 只作相容層，不再作 silent guess
- GUI 要明確顯示「目前操作作用域」

### 5.6 多 bridge 代表多輪詢，不只是多幾個 registry item

現在每條 bridge 都是自己的 worker thread，持續對 backend 做 `capture_both()` 輪詢。

這代表 `1 + n` 的主要風險不只在資料模型，還包括：

- backend subprocess 壓力
- tmux / process backend 的公平性
- polling 頻率與 freshness tradeoff
- noisy workstream 對其他 workstream 的拖累

所以 scheduler、fairness、backpressure 必須進需求，而不是留到最後才補。

## 6. 分階段開發計畫

## Phase 0: 架構定義與命名收斂

### 目標

把現在模糊的 bridge-centric 模型，整理成 workstream-centric 模型。

### 交付物

- 新的資料模型定義：
  - `workstream`
  - `workstream_status`
  - `workstream_policy`
  - `workstream_health`
- 文件更新：
  - architecture note
  - GUI terminology
  - MCP integration guidance

### 必做項目

- 定義 `workstream_id`
- 明確規範 `bridge_id` 與 `room_id` 的關係
- 保留並明文化「one active bridge per pane pair」
- 定義 main / sub、本機 / 遠端、control / execution 的分類欄位
- 在 `status()` 中引入 workstream-oriented 聚合欄位
- 明確選定第一版 `1 + n` 是 fleet-managed `n` 條 pair workstreams，而不是直接宣稱 single-host multi-guest
- 定義舊版 `bridge_*` / `room_*` 工具與 `workstream_id` 的相容關係

### 風險

- 若仍沿用目前 bridge-only 視角，GUI 與 MCP 之後會越補越亂

## Phase 1: Runtime 與狀態模型重構

### 目標

讓 server 真的能穩定管理多條協作線，而不是只靠全域 dict 湊出來。

### 交付物

- `WorkstreamRegistry`
- `status()` 的 workstream summary
- per-workstream health state
- per-workstream policy snapshot

### 必做項目

- 把 `_bridges` / `_rooms` 的關係明文化
- 增加 workstream-level CRUD / lookup
- 將 `_resolve_bridge()` 提升為 workstream-aware resolution
- 將 mutation 類操作改成 fleet-safe targeting
- 支援明確列出：
  - active workstreams
  - blocked workstreams
  - orphaned rooms
  - orphaned bridges
- 加入 per-workstream scheduler / fairness / backpressure 指標

### 驗收

- 同時啟動多個 bridge 時，所有操作都能明確解析目標，不靠單一 active bridge 猜測
- noisy workstream 不會顯著拖慢其他 workstream 的 room freshness

## Phase 2: Durability 與 Recovery

### 目標

補足 `1 + n` 必要的持久化與重啟恢復基礎。

### 交付物

- persisted workstream snapshots
- persisted pending interventions
- recovery contract docs
- startup reconciliation logic

### 必做項目

- 將 active workstream metadata 持久化
- 將 pending queue 持久化或至少 checkpoint 化
- service restart 後可重建：
  - room metadata
  - bridge metadata
  - review state
- 將 `continuity.mode` 從 runtime label 提升為正式恢復協議
- 明確定義 restore ordering：
  - workstream metadata
  - room metadata
  - bridge worker
  - pending interventions
  - health state

### 驗收

- service restart 後，operator 能看到哪些 workstream 被恢復、哪些遺失、哪些需手動接管

## Phase 3: GUI 資訊架構重構

### 目標

讓 GUI 從單線視角轉成 fleet + detail 的雙層操作模型。

### 交付物

- Fleet overview
- Workstream selector
- Workstream detail topology
- Health / alert / review grouping

### 必做項目

- 新增 workstream list / filter / grouping
- 拓樸圖改成：
  - 全域 summary
  - 選中 workstream 的 detail topology
- 加入 main / sub、本機 / 遠端、control / execution 的視覺層級
- 將 review queue 從全域單卡改成：
  - fleet pending summary
  - selected workstream pending detail

### 驗收

- 8 到 12 條 workstream 同時存在時，operator 仍能在 3 步內定位目標線並做操作

## Phase 4: MCP / Automation 面向擴展

### 目標

讓外部 client 能把 `tb2` 當作多 workstream orchestration substrate，而不只是單線工具集合。

### 交付物

- workstream-aware MCP tools
- bulk / scoped operations
- machine-readable health summaries

### 必做項目

- 新增或調整工具：
  - `workstream_list`
  - `workstream_get`
  - `workstream_stop`
  - `workstream_pause_review`
  - `workstream_resume_review`
- status payload 改成 machine-friendly aggregation
- audit query 支援 workstream slice
- 保留舊版 `bridge_*` / `room_*` 工具的相容層與遷移策略

### 驗收

- 外部 MCP client 可以不靠 GUI，也能安全管理多條 workstream

## Phase 5: Guardrail 與運營治理

### 目標

把多 workstream 的風險控制補齊。

### 必做項目

- per-workstream quota / rate guard
- per-workstream audit severity / alert
- operator escalation policy
- stale / orphan / silent stream detection
- main / sub workstream 依賴規則

### 驗收

- 單一 workstream 出問題時，不會拖垮整體操作面

## 7. GUI 上應新增的正式分層

為了支援你提到的 main / sub、本機 / 遠端，建議未來 GUI 節點與群組至少帶這些正式欄位：

- `tier`: `main` / `sub`
- `location`: `local` / `remote`
- `plane`: `control` / `coordination` / `execution` / `durability`
- `scope`: `global` / `workstream`
- `health`: `ok` / `warn` / `down`

這些欄位應該不是只有 UI 視覺效果，而要直接來自 runtime model。

## 8. 優先順序建議

如果只看穩健性，不看炫技，建議實作順序是：

1. `Phase 0` 命名與資料模型
2. `Phase 1` workstream registry
3. `Phase 2` durability / recovery
4. `Phase 3` GUI fleet + detail
5. `Phase 4` MCP 擴展
6. `Phase 5` guardrail / governance

不要先做：

- 很華麗的 multi-topology GUI
- 一次顯示很多線的動畫圖
- 批次控制按鈕

如果底層 identity、resolution、recovery 還沒穩定，這些都只會放大風險。

## 9. 建議的近期實作切片

建議先做一個小而高訊號的切片：

### Slice A

- 定義 `workstream_id`
- `status()` 新增 workstream summary
- GUI 新增 workstream picker
- review / diagnostics 先跟 selected workstream 對齊

### Slice B

- 將 pending queue 與 bridge health 正式綁到 workstream
- 加入 per-workstream guard summary

### Slice C

- 補 persistence / recovery metadata
- GUI 顯示 restored / orphaned / degraded state

這樣可以先驗證：

- 資料模型是否成立
- GUI 是否真的能承受多條線
- operator 是否能理解新心智模型

## 10. 最後判斷

### 現況判定

- 說目前是 `1 + 1 + (1監控)`：**正確，但不完整**
- 更完整的說法：
  - **產品層是 `1 + 1 + (1監控)`**
  - **底層 runtime 已有多 bridge / 多 room 雛形**
  - **尚未收斂成穩健的 `1 + n` 平台**

### 建議方向

真正穩健的擴展路線不是：

- 先把畫面塞更多節點

而是：

- 先把 `bridge -> workstream` 模型化
- 先把 identity / resolution / recovery 補齊
- 再讓 GUI 與 MCP 成為這個新模型的前端

這樣未來你要區分：

- main / sub
- 本機 / 遠端
- 主線 / 支線
- coding / review / diagnostics

才不會只是視覺標籤，而是系統真正可治理的結構。
