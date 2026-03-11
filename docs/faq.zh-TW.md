# 常見問題

## TB2 是 multi-agent framework 嗎？

不是那種抽象的 orchestration library。`tb2` 比較像是終端導向的控制面，圍繞真實 terminal session 提供 rooms、bridges、transport 與人工介入能力。

## 目前哪些 client 是 first-class？

目前 repo 把 `codex`、`claude-code`、`gemini`、`aider` 視為 first-class interactive clients。`generic` 與 `llama` 仍保留給更廣泛的相容情境。

## 一定要用 MCP 嗎？

不一定。你可以直接用本地 CLI 與 GUI。當 AI host 或其他工具需要穩定的程式化控制面時，MCP 會是最推薦的方式。

## 既然有 SSE 和 WebSocket，為什麼還保留 `room_poll`？

為了相容性與 fallback。`room_poll` 仍適合測試、退化環境與簡單 client；SSE 和 WebSocket 則補強 live collaboration UX。

## service 適合直接暴露到公網嗎？

不適合。建議預設只綁定 `127.0.0.1`。如果真的要暴露到 localhost 以外，應把它視為敏感控制面，另外加上明確的網路與存取防護。

## 預設協作模式是什麼？

Host-mediated collaboration。由 host 管理 room 與 bridge 生命週期，guest 用簡短 `MSG:` 做 handoff，human operator 在需要時介入控制。
