# Sidepanel 相容性說明

本文件說明 TB2 提供的 localhost 相容介面，讓 TB2 可替代現有的 `chrome-sidepanel-ai-terminal` 獨立橋接 client。

## 適用對象

- 現有的 Chrome sidepanel client
- 本機-only 的 operator workflow
- 每個 room 同步一次只維持一個對話，且每次只允許一個進行中的請求

此介面刻意收斂，僅提供 sidepanel 使用的最小控制面，並不替代完整 MCP API。

## API 端點

基底網址示例：

- `http://127.0.0.1:3189`

Sidepanel 相容端點：

- `GET /health`
- `POST /v1/tb2/rooms`
- `GET /v1/tb2/poll?roomId=<id>&afterId=<n>`
- `POST /v1/tb2/message`

## 目前執行模型

TB2 將 sidepanel 相容路徑與長生命週期 Host/Guest bridge 解耦。

- `POST /v1/tb2/rooms` 會建立一個實際 TB2 room，並初始化對應 terminal session
- `POST /v1/tb2/message` 會先把使用者 prompt 寫入 room，接著啟動一次性 `codex exec`
- 送入 `codex exec` 的 prompt 會包進最近 room 對話紀錄，保留多輪上下文，不需要額外抓取 TUI 內容
- `GET /v1/tb2/poll` 先回傳 `system` 類型的逐段 log preview（含 `streamKey`），再在完成後以同一 `streamKey` 回傳替換型 `assistant` 最終訊息

## 訊息契約

`GET /v1/tb2/poll` 回傳訊息採用遞增 id，payload 形如：

```json
{
  "id": 3,
  "role": "assistant",
  "text": "final answer",
  "created_at": "2026-04-15T12:00:00+00:00",
  "meta": {
    "provider": "local-tb2-codex-bridge",
    "session": "sp-abcd1234",
    "streamKey": "run-id",
    "replace": true,
    "final": true
  }
}
```

正在輸出中的 preview 訊息包含：

- `role=system`
- `meta.streamKey`
- `meta.replace=true`
- `meta.final=false`

最終回應訊息則包含：

- `role=assistant`
- `meta.streamKey`
- `meta.replace=true`
- `meta.final=true`

## Health 契約

`GET /health` 回傳欄位對應 sidepanel client 目前需求：

- `ok`
- `ready`
- `provider`
- `bridgeMode`
- `codexAvailable`
- `tb2RuntimeInstalled`
- `roomCount`
- `note`

補充診斷欄位：

- `backendReady`
- `hostPlatform`
- `runtimeCodexPath`
- `runtimeWorkdir`

`ready` 是保守條件：

- `codexAvailable=true` 代表 TB2 找到 `codex` 可執行檔
- `backendReady=true` 代表預設 TB2 backend 可以成功建立 sidepanel room session
- 後端啟動失敗時，`ready=false`，且 `note` 會攜帶最後一次 bootstrap error，避免 client 無條件重試 `/v1/tb2/rooms`

## Codex wrapper 啟動失敗模式

這台機器上的 Windows Codex wrapper 依賴一個已啟動的 TB2 listener：
`http://127.0.0.1:3189/mcp`。
這和下方 sidepanel 相容路徑不同，但兩者共用同一個 TB2 runtime process。

需要先區分這幾個健康狀態：

- `tb2.service` 可以是 running
- `backendReady=true` 也可能成立
- `codexAvailable=false` 仍然會讓 `ready=false`

在 `tb2/server.py` 中，`codexAvailable` 的計算方式是：

- 若有設定 `TB2_SIDEPANEL_CODEX`，優先使用它
- 否則退回 `shutil.which("codex")`

這代表即使互動式 WSL shell 看得到 `codex`，systemd service 仍可能因為沒有繼承同一份 `PATH` 而失敗。

這台機器上已觀察到的失敗樣態：

- 互動式 WSL shell 解析到 `/home/miles/.local/bin/codex`
- `/health` 回傳 `backendReady=true` 但 `codexAvailable=false`
- 於是 `ready=false`

建議恢復順序：

1. 在 `/etc/systemd/system/tb2.service` 設定 `TB2_SIDEPANEL_CODEX=/home/miles/.local/bin/codex`，或把 service 的 `PATH` 擴充到同一個目錄
2. 重新啟動 service：`systemctl restart tb2.service`
3. 驗證 `curl http://127.0.0.1:3189/health` 是否回傳 `codexAvailable=true` 與 `ready=true`

若 Windows Codex wrapper 仍顯示 `MCP tb2 start failed: timeout waiting for 127.0.0.1:3189`，那是另一個 listener 問題。此時應先檢查 listener，再檢查 service 環境，最後檢查 `codex` binary 路徑。

## 並發規則

每個 room 一次只允許一個進行中的請求。

若 client 在前一次請求尚未完成時再次送 `message`，TB2 回傳：

```json
{
  "ok": false,
  "error": "room already has a pending prompt",
  "roomId": "abcd1234"
}
```

## 安全邊界

此相容層仍是 local-first 控制面：

- 建議固定綁定 `127.0.0.1`
- 保留標準 localhost 瀏覽器 origin
- 只有在綁定至 loopback 時，才接受 `chrome-extension://...`
- 這只是一種本機傳輸便利性，不應被視為真正的身份驗證邊界

若需遠端存取，請改用 TB2 一般 server 綁定流程，並搭配 `--allow-remote` 與外部控管。

## 程式截圖

以下是目前主控台預覽（共用截圖資源）：

<img src="images/control-center.png" alt="terminal-bridge-v2 control console preview" width="960">
