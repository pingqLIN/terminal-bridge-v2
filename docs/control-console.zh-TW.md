# 控制台指南

內建瀏覽器控制台現在改成先看 scenario preset，再把進階控制放到明確可展開區塊。

## 設計目標

控制台應該幫 Human Operator 做下一個正確動作，而不是逼他先像 MCP 協定實作者那樣思考。

這代表：

- 頁面上方先以任務為主
- 右上角語言切換可在 English 與繁體中文間快速切換
- 右上角版面切換可快速改成加寬或堆疊排列
- 進階 identifiers 仍然找得到
- diagnostics 仍然保留
- 既有 server action 全部都還能到達

## Scenario Presets

### Quick Pairing

預設用於：

- 啟動一組 Host + Guest
- 啟動 bridge
- 監看 live room
- 發送短 operator 指示

主要控制：

- backend
- profile
- session
- `Init Session`
- `Start Collaboration`
- `Stop Bridge`

預設可見面板：

- session launch
- live room
- operator message composer
- 精簡 status summary

### Approval Gate

預設用於：

- 所有轉發都要人工審核
- 涉及程式碼修改或 shell 風險的任務

相對 Quick Pairing 的差異：

- `auto_forward=true`
- `intervention=true`
- pending queue 變成一級面板

主要控制：

- refresh pending
- 所選 handoff 細節
- approve selected
- reject selected
- approve all
- reject all

### MCP Operator

預設用於：

- 監看外部 MCP client
- 另一個 app 負責 tool calls，瀏覽器只做觀測與人工介入

主要控制：

- room 與 bridge summary
- transport health
- operator room message post
- raw status snapshot

進階控制仍保留給：

- 明確 `backend_id`
- 明確 `bridge_id`
- 明確 `room_id`

### Diagnostics

預設用於：

- smoke test
- backend 驗證
- capture、interrupt、audit triage 為主的流程

主要控制：

- terminal capture
- interrupt Host
- interrupt Guest
- interrupt both
- audit status
- recent audit entries
- audit event filter
- audit entry limit
- raw status

### Handoff Radar

預設用於：

- Host 需要同時盯 live room 與 review queue 的密集 review 流程
- bridge 維持運作時，連續做 approve / reject 決策

主要控制：

- live room stream
- review queue
- approve selected
- reject selected

### Quiet Loop

預設用於：

- 低噪音 pairing
- human operator 主要只想看啟動與即時訊息主線

主要控制：

- launch card
- live room
- operator message composer

status 與 diagnostics 會刻意退到次要位置，除非 operator 主動展開。

### Mission Control

預設用於：

- Host 主導的總控班次
- 需要同時看拓樸、診斷、room 監看

主要控制：

- raw status snapshot
- live room
- diagnostics
- review queue

## 資訊階層

### 1. Hero strip

顯示：

- 目前 preset
- 當前 endpoint
- transport 狀態
- 目前語言
- 一句話解釋這個 preset 在做什麼

### 2. Main task card

只顯示完成當前 preset 所需欄位。

對 Quick Pairing 來說，應該是：

- backend
- profile
- session
- auto-forward
- intervention

### 3. Live collaboration card

bridge 建立後永遠可見。

顯示：

- room stream
- operator message composer
- send to Host
- send to Guest
- post to room

### 4. Review queue card

只有在 `Approval Gate` 預設展開。

其他 preset 下除非已有 pending item，否則應該收起來。

顯示：

- pending list
- 所選 handoff 細節
- 核准時改寫文字
- approve / reject controls

### 5. Diagnostics card

除非 preset 是 `Diagnostics`，否則預設收起。

包含：

- capture Host
- capture Guest
- interrupt 控制
- audit 啟用狀態
- 目前 audit redaction mode
- 最近持久化 audit events
- 進入 diagnostics panel 前，持久化 audit entry 會先遮罩文字欄位
- Diagnostics audit 輸出是拿來做 correlation 與 operator review，不是 verbatim transcript recovery
- 當 redaction mode 是 `full` 時，面板應明確顯示 raw-text warning，避免 operator 把 durable audit 誤當成安全預設
- 當 `requested_mode=full` 但實際 `mode=mask` 時，面板也應明確顯示 raw text 仍被 policy 阻擋，直到設定 `TB2_AUDIT_ALLOW_FULL_TEXT=1`
- audit event filter
- audit entry limit
- raw status JSON

### 6. Status card

顯示：

- 結構化的 guard / pending / subscriber / audit 摘要
- raw status JSON
- activity log

### 7. Advanced details

永遠可用，但不應該是主畫面重點。

建議收起：

- `backend_id`
- `bridge_id`
- `room_id`
- pane A / pane B raw IDs
- transport 選擇

## 必須保留的動作

精簡後的控制台仍需完整可達：

- `terminal_init`
- `bridge_start`
- `bridge_stop`
- `room_post`
- `terminal_capture`
- `terminal_interrupt`
- `intervention_list`
- `intervention_approve`
- `intervention_reject`
- `audit_recent`
- `status`

## 建議預設

| Preset | Transport | Auto-forward | Intervention |
| --- | --- | --- | --- |
| Quick Pairing | `sse` | 開 | 關 |
| Approval Gate | `sse` | 開 | 開 |
| MCP Operator | `ws` 或 `sse` | 關 | 關 |
| Diagnostics | `room_poll` | 關 | 關 |
| Handoff Radar | `sse` | 開 | 開 |
| Quiet Loop | `sse` | 開 | 關 |
| Mission Control | `ws` | 關 | 關 |

## 操作規則

如果使用者說不出為什麼需要 raw ID，那個控制大概率就應該藏在 Advanced 裡。
