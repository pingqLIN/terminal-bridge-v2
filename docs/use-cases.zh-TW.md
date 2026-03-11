# 使用場景

當你需要讓終端型 AI 工具彼此協作，但又不想失去人類控制點時，`tb2` 最有價值。

## 1. Host 與 Guest 的協作迴圈

- Host 擁有 plan、room、bridge 與 intervention 決策權。
- Guest 在 pane 內工作，並用簡短的 `MSG:` 做 handoff。
- Human operator 可以看 room、審核敏感轉發、必要時中斷。

適合：

- code review handoff
- 多步驟重構
- 委派式除錯

## 2. MCP-first 的本地協作控制面

- 把 `tb2` 當作本地 MCP server。
- 用你偏好的 CLI client 呼叫 `terminal_init`、`bridge_start`、`room_post` 與 intervention 工具。
- 即使不同 client 的 UX 不同，也能維持穩定控制面。

適合：

- 工具鏈串接
- 可重現的本地自動化
- 混合 Codex、Claude Code、Gemini、Aider 的工作流

## 3. Human-in-the-loop 審核佇列

- 當 auto-forward 需要審查時，開啟 intervention mode。
- 在訊息送到目標 pane 前，先 approve、edit、或 reject。

適合：

- 接近正式環境的變更
- 執行前需要人工確認的 prompt
- 共用 operator 環境

## 4. 跨平台 operator console

- Windows 用 `process`，Linux / macOS 用 `tmux`。
- 可透過 GUI、SSE、WebSocket、或 `tb2 room watch` 觀看 live room。

適合：

- 本地 command center
- support / triage 流程
- 需要強調可觀測性的 demo
