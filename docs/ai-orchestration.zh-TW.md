# AI 協作指南

這份文件用在 AI 主導的 `tb2` 協作情境，特別是主持者 agent 帶著一個或多個客座 agent / 子代理一起工作時。

## 角色分工

- 主持者：負責 room、bridge 生命週期，以及 intervention 決策。
- 客座代理：在 pane 內執行任務，並輸出可被辨識的 handoff 行。
- 人類操作者：可監看、核准、編輯、拒絕或中斷。

## 建議優先使用的完整支援工具

若你想要較穩定的 prompt detection 與 message forwarding，優先使用：

- `codex`
- `claude-code`
- `gemini`
- `aider`

## 訊息契約

客座代理若要跨 agent 溝通，請輸出 `MSG:`。

範例：

```text
MSG: summarize your current blocker
MSG: echo READY_FOR_REVIEW
agent> MSG: request clarification on failing test
```

建議：

- 一行 `MSG:` 只放一個可執行要求
- 不要把整段長篇對話都塞進 `MSG:`
- 優先寫清楚意圖，不要靠客套語猜測

## 主持者工作流

1. 先用 `terminal_init` 建立 panes。
2. 再用 `bridge_start` 啟動一組 pane pair 的 bridge。
3. 需要客座代理直接互相溝通時，設 `auto_forward=true`。
4. 需要主持者審核時，設 `intervention=true`。
5. 在送出下一輪任務前，優先看 live room stream：
   - GUI 預設走 SSE
   - `tb2 room watch` 預設走 SSE，失敗時退回 `room_poll`
   - WebSocket 保留給進階 client

## 客座代理工作流

1. 平常在 pane 內正常工作。
2. 只有在跨代理溝通或要叫主持者注意時才輸出 `MSG:`。
3. 不要假設所有普通輸出都會被轉發。
4. 卡住時，用短 `MSG:` 說明阻塞點，不要丟整段 transcript。

## MCP 優先模式

對 AI 主持者來說，最穩定的控制面是 MCP：

- `terminal_init`
- `bridge_start`
- `terminal_send`
- `room_poll`
- `GET /rooms/{room_id}/stream`
- `GET /ws`
- `tb2 room watch`
- `intervention_list`
- `intervention_approve`
- `intervention_reject`
- `doctor`

## 護欄建議

- 一條活躍協作線對應一個 room。
- 同一組 pane 不要同時掛到多個 room。
- 新機器第一次使用前先跑 `doctor`。
- 完整支援工具優先使用：Windows 選 `process`，Linux/macOS 選 `tmux`。
- Host-mediated orchestration 是預設產品路徑；peer-style room 用法屬於進階模式，不是主要 UX。
