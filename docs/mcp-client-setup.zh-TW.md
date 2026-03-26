# MCP 用戶端設定

這份文件給想把 TB2 當成穩定本地 MCP control plane 的人或代理。

## TB2 透過 MCP 提供什麼

核心工具：

- `terminal_init`
- `terminal_capture`
- `terminal_send`
- `terminal_interrupt`
- `room_create`
- `room_poll`
- `room_post`
- `bridge_start`
- `bridge_stop`
- `intervention_list`
- `intervention_approve`
- `intervention_reject`
- `list_profiles`
- `doctor`
- `status`

可把它們看成三組能力：

| 能力群組 | 工具 |
| --- | --- |
| 啟動與 I/O | `terminal_init`、`terminal_send`、`terminal_capture`、`terminal_interrupt` |
| 協作狀態 | `room_create`、`room_poll`、`room_post`、`status` |
| 委派控制 | `bridge_start`、`bridge_stop`、`intervention_list`、`intervention_approve`、`intervention_reject` |

## Server 啟動方式

### 前景執行

```bash
python -m tb2 server --host 127.0.0.1 --port 3189
```

### 背景服務

```bash
python -m tb2 service start --host 127.0.0.1 --port 3189
python -m tb2 service status
```

健康檢查：

```bash
curl -sS http://127.0.0.1:3189/healthz
```

MCP 端點：

- `http://127.0.0.1:3189/mcp`

## 在各客戶端註冊 TB2

### Codex CLI

```bash
codex mcp add tb2 --url http://127.0.0.1:3189/mcp
```

### Claude Code CLI

```bash
claude mcp add --transport http -s user tb2 http://127.0.0.1:3189/mcp
```

### Gemini CLI

```bash
gemini mcp add tb2 http://127.0.0.1:3189/mcp --transport http --scope user
```

## 驗證註冊

```bash
codex mcp list
claude mcp list
gemini mcp list
```

預期訊號：

- Claude 與 Gemini 顯示 `Connected`
- Codex 顯示 `enabled`

## Host AI 工具地圖

若 Host AI 是主要協作驅動者，最小可用順序是：

1. `doctor`
2. `terminal_init`
3. `bridge_start`
4. `room_poll` 或 stream subscribe
5. `intervention_list`
6. `intervention_approve` 或 `intervention_reject`
7. `status`

### bridge 解析捷徑

TB2 現在對 intervention 類工具支援更輕量的解析路徑：

- `intervention_list`、`intervention_approve`、`intervention_reject`、`terminal_interrupt` 在已知情況下可直接用 `bridge_id`
- 若不知道 `bridge_id`，但 `room_id` 只綁定一條 active bridge，可改傳 `room_id`
- 若整個 server 目前只有一條 active bridge，這些工具可自動解析
- 若同時存在多條 active bridge，TB2 會回傳明確錯誤與 `bridge_candidates`

`status` 現在也會回傳 `bridge_details`，讓其他 AI client 可以直接看到 `bridge_id`、`room_id`、pane、profile 與 pending count，而不是自己猜。

## Human Operator 工具地圖

如果人類是透過支援 MCP 的 app 監看，而不是透過瀏覽器 UI：

1. `status`
2. `room_poll`
3. `room_post`
4. `terminal_capture`
5. `terminal_interrupt`

## 協定探測

初始化：

```bash
curl -sS http://127.0.0.1:3189/mcp \
  -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"probe","version":"1"}}}'
```

心跳：

```bash
curl -sS http://127.0.0.1:3189/mcp \
  -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":2,"method":"ping","params":{}}'
```

工具清單：

```bash
curl -sS http://127.0.0.1:3189/mcp \
  -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/list","params":{}}'
```

## 相容性說明

TB2 目前提供：

- `initialize`
- `ping`
- `notifications/initialized`
- `tools/list`
- 空的 `resources/list`
- 空的 `prompts/list`

目前相容性建議：

- 優先使用 HTTP MCP transport
- 除非你有明確信任邊界，否則請綁定 localhost
- 出現問題時先跑 `doctor`，不要第一時間把錯誤歸咎於 MCP 協定
- 不要硬編 intervention 參數；先看 `tools/list`，schema 已經會標出可用 `room_id` 當 bridge-scoped 工具的 fallback

## 移除註冊

```bash
codex mcp remove tb2
claude mcp remove -s user tb2
gemini mcp remove --scope user tb2
```

## 相關文件

- [入門指南](getting-started.zh-TW.md)
- [AI 協作指南](ai-orchestration.zh-TW.md)
- [平台與終端行為](platform-behavior.zh-TW.md)
