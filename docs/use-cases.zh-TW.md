# 使用場景

這份文件把常見 TB2 任務映射到合適的 preset、transport 與 review posture。

## 1. 一般 Host + Guest coding loop

使用：

- preset：`Quick Pairing`
- transport：`SSE`
- forwarding：`auto_forward=true`
- review：`intervention=false`

適合：

- 委派除錯
- code review 迴圈
- Host 仍保留最終判斷權的多步驟重構

## 2. 敏感轉發且需要人工審核

使用：

- preset：`Approval Gate`
- transport：`SSE`
- forwarding：`auto_forward=true`
- review：`intervention=true`

適合：

- 可能改動 repo 的 shell 命令
- dependency 變更
- migration 或 CI 修復

## 3. 從其他 AI client 做 MCP-first orchestration

使用：

- preset：`MCP Operator`
- 瀏覽器 UI 主要拿來看 status、room 與 pending queue
- 真正的啟動與控制走 MCP tools

適合：

- 讓 Codex 規劃，Guest 在 panes 裡工作
- 讓 Claude Code 或 Gemini 驅動 tool calls
- 以穩定 control plane 做可重現本地自動化

## 4. Terminal incident recovery

使用：

- preset：`Diagnostics`
- transport：`room_poll` 或 `SSE`
- 以 capture、interrupt、status 為主

適合：

- Guest 工具卡死
- pane 輸出難以理解
- 驗證 shell 啟動與 backend 行為

## 5. 純 CLI operator workflow

使用：

- `python -m tb2 room watch --room-id <ROOM_ID>`
- `python -m tb2 capture --target <PANE>`
- `python -m tb2 send --target <PANE> --text "..."`

適合：

- SSH-only 環境
- 低摩擦 demo
- 沒有瀏覽器的恢復流程

## 6. 密集 handoff review 迴圈

使用：

- preset：`Handoff Radar`
- transport：`SSE`
- forwarding：`auto_forward=true`
- review：`intervention=true`

適合：

- 反覆 review / approve / reject 的流程
- Host 需要同時盯 room 與 pending queue 的工作面
- Guest 主要在 shell 裡頻繁送出 handoff 的情境

## 7. 低噪音 pairing 與 operator 指導

使用：

- preset：`Quiet Loop`
- transport：`SSE`
- forwarding：`auto_forward=true`
- review：`intervention=false`

適合：

- human operator 主要只會送短指示的 pairing
- 不想讓 diagnostics 先佔走視覺重心的 demo
- 啟動與 live room 就是主流程的情境

## 8. Host 主導的總控班次

使用：

- preset：`Mission Control`
- transport：`WebSocket`
- forwarding：`auto_forward=false`
- review：預設 `intervention=false`

適合：

- Host AI 同時看拓樸、診斷與 room 流量
- raw status 與 live room 同樣重要的 investigation
- 需要更寬 control-plane 視角的長時間 session

## 9. 什麼時候從簡單模式切進進階模式

以下情況請留在預設任務 preset：

- pane ID 來自同一條啟動流程
- 目前只有一條 active bridge
- 不需要自訂 transport 細節

以下情況請打開進階控制：

- 你需要明確指定 `backend_id`、`bridge_id`、`room_id`
- 你要固定 `transport`
- 你同時混用瀏覽器 UI 與 MCP automation
- 你在 debug pane naming 或 delivery routing

## 相關文件

- [控制台指南](control-console.zh-TW.md)
- [AI 協作指南](ai-orchestration.zh-TW.md)
- [平台與終端行為](platform-behavior.zh-TW.md)
