---
description: 依據 devil's advocate review 整理的 terminal-bridge-v2 修復計畫，按優先級拆解成可執行 backlog
---

# terminal-bridge-v2 修復計畫

## 目的

這份文件把 [devils-advocate-review.zh-TW.md](./devils-advocate-review.zh-TW.md) 裡的風險，整理成可執行的修補 backlog。

目標不是一次把產品變成完整的 production platform，而是先把最容易造成誤用、失控、或定位失真的缺口補起來。

## 狀態更新（2026-03-27）

目前 branch 已完成第一個短期 milestone 的主要工程項目：

- `P0` 第 1 到 5 項已在 `tb2/server.py`、`tb2/room.py` 與對應測試中落地
- `P1` 第 6 到 8 項已在 `tb2/server.py`、`tb2/process_backend.py`、`tb2/pipe_backend.py` 與對應測試中落地
- 本地完整驗證為 `.venv/bin/python -m pytest -q` => `285 passed in 13.34s`

目前剩餘的高價值項目主要集中在：

- `P2` 的 runaway / rate limit 類保護
- 更明確的 release positioning 與 FAQ / README 對齊
- 持久化 audit trail 的設計與範圍定義

## 修補原則

- 先補邊界，再補體驗
- 先補可低成本高收益的防線，再補較大的設計重構
- 文件敘述要和實際安全邊界一致
- 驗收條件必須可測試，不只靠主觀描述

## P0

### 1. WebSocket 與 HTTP 加入 `Origin` 驗證

#### 目標

避免弱來源直接把本機控制面當成可濫用入口，至少先建立最基本的 browser-origin 邊界。

#### 範圍

- `tb2/server.py`
- `/mcp` POST
- `/ws` WebSocket upgrade

#### 建議作法

- 允許清單至少包含：
  - `http://127.0.0.1`
  - `http://localhost`
  - 對應 port 的同源變體
- 若沒有 `Origin`，明確定義策略：
  - CLI / 非瀏覽器 client 是否允許無 `Origin`
  - 若允許，需在文件中寫清楚

#### 驗收條件

- 合法 localhost origin 可正常使用
- 非 localhost origin 會回 `403`
- WebSocket 與 HTTP 都有一致策略
- 新增對應測試

### 2. HTTP request body 增加大小限制與安全解析

#### 目標

避免超大請求直接吃掉記憶體。

#### 範圍

- `tb2/server.py`

#### 建議作法

- 加入 `MAX_BODY`
- `Content-Length` 缺失或非法時回 `400`
- 超過上限時回 `413`

#### 驗收條件

- 小型合法請求可正常處理
- 超過限制的請求被拒絕
- 非法 `Content-Length` 不會造成未處理例外

### 3. HTTP POST 路徑加入讀取逾時

#### 目標

降低 slow client / slow loris 類型的 thread occupation 風險。

#### 範圍

- `tb2/server.py`

#### 建議作法

- 在讀 body 前設定 socket timeout
- timeout 時回可預期錯誤，不讓 thread 無限阻塞

#### 驗收條件

- 正常請求不受影響
- 慢速或不完整請求會被 timeout
- 不會留下卡死 thread

### 4. 為 `room_id` 與其他外部 ID 建立格式驗證

#### 目標

避免超長字串、碰撞濫用與不一致命名。

#### 範圍

- `tb2/room.py`
- `tb2/server.py`

#### 建議作法

- 對 `room_id` 設長度上限與 regex
- 視需要比照處理 `bridge_id`
- 將驗證失敗回成一致錯誤物件

#### 驗收條件

- 合法 ID 可正常建立
- 非法 ID 會被拒絕
- 超長 ID 不會進入核心資料結構

### 5. 統一所有整數輸入的安全解析

#### 目標

避免 `int()` 直接把壞輸入升級成 HTTP 500 或未處理例外。

#### 範圍

- SSE query parsing
- WebSocket subscribe 參數
- `poll_ms`
- `lines`
- 其他外部整數欄位

#### 建議作法

- 建立共用 parse helper
- 對非法值給預設值或回錯誤，策略要一致

#### 驗收條件

- 對壞輸入沒有未處理例外
- 所有相關 handler 行為一致
- 測試覆蓋 query string 與 JSON body 兩種入口

## P1

### 6. 修正 backend cache key，納入 `shell` / `distro`

#### 目標

避免不同 backend 設定被悄悄共用，造成實際行為與使用者設定不一致。

#### 範圍

- `tb2/server.py`

#### 建議作法

- cache key 至少納入：
  - `backend`
  - `backend_id`
  - `shell`
  - `distro`
- 或直接明確規定同一 `backend_id` 不允許改變設定

#### 驗收條件

- 同 `backend_id` + 不同 `shell` 不會回同一實例
- 同 `backend_id` + 不同 `distro` 不會回同一 tmux backend
- 新增回歸測試

### 7. 讓 `ProcessBackend` / `PipeBackend.init_session()` 變成 idempotent

#### 目標

避免重複初始化同一 session 時產生 orphan process。

#### 範圍

- `tb2/process_backend.py`
- `tb2/pipe_backend.py`

#### 可選策略

- 若 session 已存在，直接回傳既有 pane id
- 或明確拒絕重複初始化並回錯

#### 驗收條件

- 重複呼叫不會產生額外 child process
- `kill_session()` 能完整清乾淨該 session 資源
- 新增 PID / process-count 層級的測試

### 8. 把 bridge 的 `sleep()` 移出逐行處理迴圈

#### 目標

避免輸出越多延遲越高，讓 bridge latency 和輪詢頻率脫鉤。

#### 範圍

- `tb2/server.py`

#### 建議作法

- `sleep()` 應該放在單次 capture / process cycle 之後，而不是每行之後
- 保留 adaptive polling 機制，但只作用於下一次輪詢

#### 驗收條件

- 多行輸出不再造成線性延遲
- 現有 bridge 行為測試不退化
- 補一個 latency regression test

### 9. 為 `author` 與可信來源語義重新定義欄位

#### 目標

避免 UI 或 automation 將自由字串誤判為可信身份。

#### 範圍

- `tb2/server.py`
- `tb2/room.py`
- GUI 顯示層

#### 建議作法

- 保留 `author` 作為顯示用欄位
- 另加 machine-readable source 欄位，例如：
  - `source_type`
  - `source_role`
  - `trusted`

#### 驗收條件

- 上游 consumer 不需再靠 `author == "bridge"` 這類字串判斷權威性
- 舊行為若要保留，需明確標示相容策略

## P2

### 10. 為 `auto_forward` 加入 rate limit 與 circuit breaker

#### 目標

降低 agent runaway、互相觸發與高頻 loop 的放大效應。

#### 範圍

- `tb2/server.py`
- 可能延伸到 profile / intervention 設定

#### 建議作法

- 每 bridge 設每秒最大自動轉發數
- 設連續自動轉發上限
- 超限時自動切換到 intervention 或停橋

#### 驗收條件

- loop 場景下不會無限自動送出
- operator 能看見被 breaker 攔下的事件
- 有對應測試覆蓋 burst / runaway 場景

### 11. 重新校正文案與產品定位

#### 目標

讓 README、docs、release surfaces 對外表述和實際成熟度一致。

#### 範圍

- `README.md`
- `README.zh-TW.md`
- `docs/faq*.md`
- release / announcement 文案

#### 建議作法

- 強調：
  - local-first
  - high-trust only
  - not safe to expose publicly
  - experimental / operator-grade
- 弱化或避免：
  - production-ready
  - strongly enforced human approval
  - broadly safe remote control plane

#### 驗收條件

- 主要入口文件不再暗示超出實際能力的保證
- FAQ 與 README 敘述一致

### 12. 規劃更完整的持久化 audit trail

#### 目標

讓產品在未來有機會從「即時協作 buffer」升級成「可追溯控制面」。

#### 範圍

- room events
- intervention actions
- bridge lifecycle
- operator actions

#### 說明

這不是當前必做的 blocking fix，但如果產品方向是 control plane，遲早要補。

#### 驗收條件

- 至少有設計草案
- 明確定義哪些事件必須持久化
- 明確定義 retention 與隱私邊界

## 建議執行順序

1. 先完成所有 P0，因為這些是最基本的安全與輸入邊界。
2. 再做 P1，因為這些是已經驗證可重現的實作缺陷。
3. 最後做 P2，因為這些偏向產品收斂與長期能力建設。

## 建議的第一個里程碑

若要快速收斂成一個可接受的短期版本，我建議第一個 milestone 只包含：

- P0 全部
- P1 的第 6、7、8 項

做完之後，TB2 雖然仍然不是完整 production platform，但至少可以：

- 把最危險的邊界缺口補上
- 修掉已可重現的 backend / session / latency 問題
- 讓後續文件定位更有根據

## 完成定義

只有當下列條件都成立，這份 remediation plan 才算真的落地：

- 所有 P0 項目都有程式修補
- 每個 P0 / P1 項目都有對應測試
- README 與 FAQ 已同步更新定位
- 有一份簡短 changelog 或 release note 說明修補範圍與剩餘限制
