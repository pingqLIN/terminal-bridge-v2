# 角色導向使用指南

這份文件用來回答一個問題：同一套 `tb2` 控制面中，不同角色各自該怎麼操作。

## 角色索引

| 角色 | 主要目標 | 建議入口 | 請讀這節 |
| --- | --- | --- | --- |
| Host AI | 管理協作循環與 handoff 決策 | MCP 或 CLI | [Host AI](#host-ai) |
| Guest AI | 專注做事並輸出結構化 handoff | terminal pane | [Guest AI](#guest-ai) |
| Human Operator | 監看、核准、拒絕、中斷、留下操作紀錄 | GUI 優先，CLI/MCP 次之 | [Human Operator](#human-operator) |
| MCP 整合者 | 接上 Codex、Claude Code、Gemini 或自訂 client | MCP HTTP endpoint | [MCP Integrator](#mcp-integrator) |

## Host AI

### 職責

- 建立或接手一組雙 pane session。
- 每組 pane pair 只啟動一個 bridge。
- 為 guest 選對 profile。
- 決定 handoff 是直接 auto-forward 還是進 approval queue。
- 任務結束後停止 bridge。

### 標準生命週期

1. 先跑 `python -m tb2 doctor`。
2. 用 `terminal_init` 或 `tb2 init` 建立 panes。
3. 用 `bridge_start` 啟動 bridge。
4. 先看 room feed，再發下一輪任務。
5. 如果開啟 approval mode，就看 `intervention_list`。
6. 完工後用 `bridge_stop` 收尾。

### 安全預設

- 優先使用 `tb2` 自動選出的預設 backend。
- 只有在 guest 已經嚴格遵守 `MSG:` 契約時才用 `auto_forward=true`。
- 只要 handoff 可能改程式、跑命令、或觸及共享環境，就用 `intervention=true`。
- 一條活躍協作線對應一個 room。

### 訊息契約

Host 應把 `MSG:` 視為唯一穩定的跨代理 handoff 訊號。

好的例子：

```text
MSG: summarize the failing assertion in tests/test_server.py
MSG: run the platform-specific smoke test and report the result
MSG: prepare a patch for the CLI help text only
```

不好的例子：

```text
MSG: here is a long diary of everything I tried over the last 20 minutes
MSG: maybe do something about the bug if you have time
```

### 失敗處理

- `bridge_start` preflight 失敗時，先 capture 兩邊 pane 再重試。
- room stream 安靜到不合理時，先重連 transport，不要第一時間重啟 bridge。
- guest 的 `MSG:` 格式不穩定時，切到 approval mode，並改用 `room_post` 發送明確的 operator 指令。

## Guest AI

### 職責

- 在指定 pane 內工作。
- 只有需要 handoff 時才輸出短而可執行的 `MSG:`。
- 保持一般 terminal output 可讀，不要把 room 淹沒。

### 輸出規則

- 一行 `MSG:` 只放一個請求。
- 優先寫清楚、可執行的指令。
- 避免多行 `MSG:`。
- 若能選擇輸出模式，盡量避免過重的 ANSI 與 prompt 包裝。

### 阻塞時的標準寫法

```text
MSG: need clarification on the expected backend for native macOS
MSG: capture looks stale after restart; please reconnect the room stream
MSG: ready for review on the backend fallback patch
```

### 不要做的事

- 不要假設所有普通輸出都會被轉發。
- 不要把內部自言自語寫成 `MSG:`。
- 不要丟長篇 transcript 讓 host 自己猜意圖。

## Human Operator

### 職責

- 持續看 room feed。
- 決定待審 handoff 要 approve、edit、reject，還是直接 interrupt。
- 維持控制面健康：transport 在線、room 正確、bridge id 正確。

### 建議入口

- 先用 `python -m tb2 gui` 打開瀏覽器控制台。
- 需要人工審核時，用 `Approval Queue` preset。
- bridge 已存在，只要監看時，用 `Observe Room` preset。
- GUI 不可用時再退回 CLI 或直接 MCP。

### 核准檢查表

- 目標 pane 對嗎？
- 訊息是否具體到可以安全執行？
- 是否需要先編輯再送？
- 是否應先 interrupt 再轉發？

### 稽核建議

- host binding 維持在 `127.0.0.1`。
- 想留下可追蹤紀錄時，優先用 room-posted operator note，不要直接手打進 terminal。
- 大量 approve/reject 前先 refresh pending items。

## MCP Integrator

### 主要目標

把 `tb2` 暴露成穩定的本地控制面，供 Codex CLI、Claude Code、Gemini CLI 或自訂 MCP client 使用。

### 核心端點

- `http://127.0.0.1:3189/mcp`

### 核心工具面

- `terminal_init`
- `terminal_capture`
- `terminal_send`
- `terminal_interrupt`
- `bridge_start`
- `bridge_stop`
- `room_create`
- `room_poll`
- `room_post`
- `intervention_list`
- `intervention_approve`
- `intervention_reject`
- `doctor`
- `status`

### 建議呼叫順序

1. `doctor`
2. `terminal_init`
3. `bridge_start`
4. `room_poll` 或 room stream 訂閱
5. `room_post` / `terminal_send`
6. `intervention_list`，再決定 approve 或 reject
7. `bridge_stop`

### 整合規則

- 把 server 視為本地專用基礎設施。
- 多個 client 需要共用 backend instance 時，`backend_id` 要固定。
- 不要在不同 room 上重複使用同一組 pane pair 啟動多個 bridge。
- 可觀測性優先靠 room streaming，拓樸優先看 `status`。

延伸閱讀：

- [入門指南](getting-started.zh-TW.md)
- [MCP 用戶端設定](mcp-client-setup.zh-TW.md)
- [平台相容矩陣](platforms/compatibility-matrix.zh-TW.md)
