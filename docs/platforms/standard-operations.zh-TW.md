# 標準操作手冊

這份文件定義 `tb2` 在不同平台上的標準安裝、啟動、監看、與停止流程。

## 1. 標準安裝

### Linux / macOS

```bash
pip install -e ".[dev]"
python -m tb2 doctor
```

### Windows

```bash
pip install -e ".[windows,dev]"
python -m tb2 doctor
```

如果 `doctor` 顯示 Windows 上的 `process` 不可用，請先安裝 `pywinpty`，或改走 WSL `tmux` 路徑。

## 2. 標準啟動

### 全新本地 session

```bash
python -m tb2 init --session demo
python -m tb2 broker --a demo:0.0 --b demo:0.1 --profile codex --auto
```

在 Windows 上，如果選到的 backend 是 `process`，pane id 會長成 `demo:a` 與 `demo:b`。

### 瀏覽器控制台

```bash
python -m tb2 gui --host 127.0.0.1 --port 3189
```

打開 `http://127.0.0.1:3189/`。

### MCP 伺服器

```bash
python -m tb2 server --host 127.0.0.1 --port 3189
```

或用背景 service：

```bash
python -m tb2 service start --host 127.0.0.1 --port 3189
python -m tb2 service status
```

### 啟用 audit 的背景 service

```bash
TB2_AUDIT=1 python -m tb2 service start --host 127.0.0.1 --port 3189
python -m tb2 service status
python -m tb2 service audit --lines 10
```

若要寫到明確目錄，請改用 `TB2_AUDIT_DIR`。若這台 service 需要保留較長的 incident history，請再用 `TB2_AUDIT_MAX_BYTES` / `TB2_AUDIT_MAX_FILES` 確認 retention 邊界。

## 3. 標準健康檢查

### CLI 檢查

```bash
python -m tb2 doctor
python -m tb2 service status
python -m tb2 service audit --lines 10
```

### HTTP 檢查

```bash
curl -sS http://127.0.0.1:3189/healthz
curl -sS http://127.0.0.1:3189/mcp
```

### GUI 檢查

- `Quick Pairing` preset 應顯示 backend、profile、session 與 bridge 動作。
- `Approval Gate` preset 應顯示 pending list 與 approve / reject 動作。
- `MCP Operator` preset 應保留 room 與 status 監看能力，供外部 MCP 驅動時使用。
- `Diagnostics` preset 應把 capture、interrupt、audit 狀態、status 放在前景。
- `Diagnostics` preset 應可檢視最近 audit entries，並用 event 與 limit 進一步縮小範圍。
- `Mission Control` preset 應同時保留 status、room、diagnostics。

## 4. 標準停止流程

### 停止 bridge

先確認 pending items：

```bash
python -m tb2 room pending --bridge-id <BRIDGE_ID>
python -m tb2 room reject --bridge-id <BRIDGE_ID> --id all
```

如果該 room 只有一條 active bridge，也可以直接走較輕量的 room-scoped 路徑：

```bash
python -m tb2 room pending --room-id <ROOM_ID>
python -m tb2 room reject --room-id <ROOM_ID> --id all
```

之後透過 GUI / MCP 呼叫 `bridge_stop`，或在控制流中明確停止 bridge。

### 停止背景 service

```bash
python -m tb2 service stop
```

## 5. 標準排錯流程

### Linux / macOS

- 若沒有 `tmux`，請改用 `process`，不要強制使用 `tmux`。
- pane capture 看起來 stale 時，先重連 room transport，再考慮重啟 bridge。
- shell 啟錯時，明確設定 `TB2_SHELL`。

### Windows

- `process` 不可用時先安裝 `pywinpty`。
- 若 native Windows 還是無法滿足互動需求，就改走 WSL `tmux`。
- 若你預期會用非原生 shell，請記得 Windows 不看 `SHELL`；要明確設 `TB2_SHELL`。

### 全平台通用

- host binding 維持在 `127.0.0.1`。
- 同一組 pane pair 只保留一個 active bridge。
- 新 guest profile 或新 CLI client 先在 `intervention` 模式下驗證。
- 只有在 client 不需要 TUI 時才用 `pipe`。
- 若 audit 是 runbook 的一部分，請先確認 `audit.enabled`、目前寫入檔案路徑，以及一條可過濾的 `service audit` 查詢真的有資料，再把 incident history 當成可信訊號。
