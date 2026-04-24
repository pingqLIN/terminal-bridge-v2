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
