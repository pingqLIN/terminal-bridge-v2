# AI 協作指南

這份文件從 cooperating agents 的角度解釋 TB2，而不是只從 transport primitive 的角度介紹。

## 角色模型

TB2 以三個主角色與一個可選整合角色為核心。

### Host AI

Host AI 負責：

- 拆解計畫
- 管理 room 生命週期
- 決定 pane pairing
- 設定 intervention policy
- 最終整合結果

常見 Host 動作：

- 建立 panes
- 啟停 bridge
- approve 或 reject Guest 的 `MSG:` 請求
- 把 operator 指示回貼到 room

### Guest AI

Guest AI 負責：

- 在單一 pane 中執行聚焦任務
- 在需要 Host 介入時發出簡潔 `MSG:` 行
- 不把一般 shell chatter 汙染成 handoff channel

常見 Guest 動作：

- 在 pane 內工作
- 要求 review
- 要求補上下文
- 回報 ready 狀態

### Human Operator

Human Operator 負責：

- 選擇啟動 preset
- 決定哪些情境一定要人工審核
- 當工具失控時中斷 pane
- 把澄清訊息送給 Host、Guest 或整個 room

### MCP Integrator

MCP Integrator 負責：

- 把 TB2 註冊到上游 client
- 把工具映射成內部流程
- 決定控制要走瀏覽器 UI、terminal UI，還是直接 tool calls

## 按角色查功能

### Host AI 功能索引

| 需求 | TB2 surface |
| --- | --- |
| 建立配對 session | `terminal_init` |
| 啟動委派循環 | `bridge_start` |
| 直接發送指示 | `terminal_send`、`room_post` |
| 查看待審請求 | `intervention_list` |
| approve 或 edit | `intervention_approve` |
| 停止風險工作 | `terminal_interrupt`、`bridge_stop` |

### Guest AI 功能索引

| 需求 | 契約 |
| --- | --- |
| 要求 Host 動作 | 輸出 `MSG:` |
| 要求 review | 輸出單一短而可執行的 `MSG:` |
| 回報狀態 | 使用機器可讀的 `MSG:`，例如 `READY_FOR_REVIEW` |
| 持續本地工作 | 保持一般輸出，不是每行都該被轉發 |

### Human Operator 功能索引

| 需求 | TB2 surface |
| --- | --- |
| 啟動任務導向 session | 瀏覽器 UI preset |
| 監看 live room | 瀏覽器 UI、SSE、WebSocket、`room watch` |
| 送 room-only 上下文 | `room_post` |
| 直接送給 Host / Guest | 帶 `deliver` 的 `room_post`，或瀏覽器送出按鈕 |
| 檢查 terminal 狀態 | `terminal_capture` |
| 從失控工作恢復 | `terminal_interrupt` |

## Host AI Playbook

### 1. 從乾淨 room 開始

建議順序：

1. `terminal_init`
2. `bridge_start`
3. 視需要 `room_post`
4. 觀察 room stream
5. 送出下一輪工作

### 2. 先選定一種 forwarding policy

| Policy | 設定 | 適用情境 |
| --- | --- | --- |
| 直接協作 | `auto_forward=true`、`intervention=false` | Guest 工作低風險且高頻 |
| 審核後轉發 | `auto_forward=true`、`intervention=true` | 轉發內容可能改動程式碼或基礎設施 |
| 只進 room | `auto_forward=false` | Host 想先看過再決定是否送到另一個 pane |

### 3. 讓 handoff channel 保持狹窄

建議 Guest `MSG:` 模式：

```text
MSG: summarize the failing assertion and propose the smallest fix
MSG: request Host review of the last command before retrying
MSG: READY_FOR_REVIEW
```

避免：

- 敘事型 transcript
- 一行塞多個要求
- shell prompt 與格式噪音

## Guest AI Playbook

### 1. 像聚焦 worker，而不是第二個 room moderator

應該做：

- 正常輸出工作過程
- 把 `MSG:` 留給協作邊界
- 讓 `MSG:` 短且直接可執行

不該做：

- 把每個狀態行都當 handoff
- 用 `MSG:` 輸出多段長文
- 在 intervention 開啟時假設轉發一定立即送達

### 2. 使用明確 review state

範例：

```text
MSG: READY_FOR_REVIEW
MSG: NEED_HOST_DECISION on dependency upgrade
MSG: BLOCKED waiting for fixture path
```

## Human Operator Playbook

### Quick Pairing

適用於：

- 你想快速建立 Host + Guest
- 不需要每個轉發都人工審核
- 主要是看 live room，只偶爾插手

### Approval Gate

適用於：

- 所有轉發命令都需要人工 review
- Guest 可能動到程式碼、測試或 shell state

### MCP Operator

適用於：

- 真正的控制面在另一個 MCP client
- 瀏覽器 UI 主要只拿來看 transport、room、intervention 狀態

### Diagnostics

適用於：

- 你在驗證 backend 行為
- 你更需要 capture 或 interrupt，而不是協作介面
- 任務本質是 smoke test 或 incident recovery

## 建議 Profiles

目前最穩定的互動協作 profiles：

- `codex`
- `claude-code`
- `gemini`
- `aider`

Fallback profiles：

- `generic`
- `llama`

## 真正重要的護欄

- 一條活躍協作線對應一個 room。
- 同一組 pane 不要同時掛到多個 room。
- 平台能力改變時重新跑 `doctor`。
- 預設心智模型請維持 Host-mediated orchestration；peer-to-peer chat 應視為進階模式。

## 相關文件

- [入門指南](getting-started.zh-TW.md)
- [控制台指南](control-console.zh-TW.md)
- [MCP 用戶端設定](mcp-client-setup.zh-TW.md)
- [平台與終端行為](platform-behavior.zh-TW.md)
