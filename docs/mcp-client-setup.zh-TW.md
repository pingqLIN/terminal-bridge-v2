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
- `audit_recent`

可把它們看成四組能力：

| 能力群組 | 工具 |
| --- | --- |
| 啟動與 I/O | `terminal_init`、`terminal_send`、`terminal_capture`、`terminal_interrupt` |
| 協作狀態 | `room_create`、`room_poll`、`room_post`、`status` |
| 委派控制 | `bridge_start`、`bridge_stop`、`intervention_list`、`intervention_approve`、`intervention_reject` |
| 持久化觀測 | `status`、`audit_recent`、`tb2 service audit` |

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

## Audit 與持久化檢查

若你希望保留 durable operator records，請在啟動背景 service 前先打開 audit：

```bash
TB2_AUDIT=1 python -m tb2 service start --host 127.0.0.1 --port 3189
python -m tb2 service status
python -m tb2 service audit --lines 10
```

若要把 audit 寫到明確目錄，改用 `TB2_AUDIT_DIR`：

```bash
TB2_AUDIT_DIR=/tmp/tb2-audit python -m tb2 service start --host 127.0.0.1 --port 3189
python -m tb2 service audit --lines 20 --event bridge.started
python -m tb2 service audit --lines 20 --room-id demo-room
```

建議至少驗證：

- `status` 會回 `audit` 物件，包含 `enabled`、`file`、retention 設定，以及 `redaction` contract
- `audit_recent` 能查到目前 room 或 bridge 的持久化事件，但文字欄位會先做遮罩
- `tb2 service audit` 可用 `event`、`room_id`、`bridge_id` 過濾，但同樣遵守這個 redaction 契約
- 預設 redaction mode 是 `mask`；現在若設成 `TB2_AUDIT_TEXT_MODE=full`，還必須再加上 `TB2_AUDIT_ALLOW_FULL_TEXT=1`，否則 client 應預期 `requested_mode=full` 但實際 `mode=mask`
- client 應把 `requested_mode != mode` 且 `raw_text_opt_in_blocked=true` 視為 policy boundary，而不是暫時性錯誤
- 若未另外指定，retention 預設是單一 active file 5 MiB、總共保留 5 個檔案；可用 `TB2_AUDIT_MAX_BYTES` 與 `TB2_AUDIT_MAX_FILES` 覆寫

## Host AI 工具地圖

若 Host AI 是主要協作驅動者，最小可用順序是：

1. `doctor`
2. `terminal_init`
3. `bridge_start`
4. `room_poll` 或 stream subscribe
5. `intervention_list`
6. `intervention_approve` 或 `intervention_reject`
7. `status`
8. `audit_recent`

### bridge 解析捷徑

TB2 現在對 intervention 類工具支援更輕量的解析路徑：

- `intervention_list`、`intervention_approve`、`intervention_reject`、`terminal_interrupt` 在已知情況下可直接用 `bridge_id`
- 若不知道 `bridge_id`，但 `room_id` 只綁定一條 active bridge，可改傳 `room_id`
- 若整個 server 目前只有一條 active bridge，這些工具可自動解析
- 若同時存在多條 active bridge，TB2 會回傳明確錯誤與 `bridge_candidates`

`status` 現在也會回傳 `bridge_details`，讓其他 AI client 可以直接看到 `bridge_id`、`room_id`、pane、profile 與 pending count，而不是自己猜。
它同時也會回傳 `audit` snapshot，讓 client 在呼叫 `audit_recent` 前先判斷目前是否真的有持久化事件可查。
這個 `audit` snapshot 現在也會帶出 text redaction mode 與 machine-readable storage flags，讓 client 不必靠文件敘述推論 durable metadata 與 live room content 的差別。
它現在也會回傳 machine-readable `runtime` contract，讓 client 明確知道 live room / bridge / intervention state 目前仍是記憶體態，service restart 後會遺失。請把 `launch_mode`、`snapshot_schema_version`、`audit_policy_persistence`、`continuity.mode` 視為正式欄位，用來區分 direct local run、service-managed fresh start，或 restart 後 state lost 的情境。當 TB2 走 managed service path 時，`audit_policy_persistence=service_state` 代表 restart 會延續 audit policy 輸入，但不會恢復 live collaboration state。

## Human Operator 工具地圖

如果人類是透過支援 MCP 的 app 監看，而不是透過瀏覽器 UI：

1. `status`
2. `room_poll`
3. `room_post`
4. `terminal_capture`
5. `terminal_interrupt`
6. `audit_recent`

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
