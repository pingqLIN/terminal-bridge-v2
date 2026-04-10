# 入門指南

這份文件提供從乾淨 checkout 到可用 `tb2` session 的最短穩定路徑。

## 1. 安裝

### Linux / macOS

```bash
pip install -e ".[dev]"
```

### Windows

```bash
pip install -e ".[windows,dev]"
```

## 2. 先跑 `tb2 doctor`

```bash
python -m tb2 doctor
```

請先看這幾個區塊：

- `Readiness`：backend、transport、first-class client 是否真的達到可用狀態
- `Validation snapshot`：哪些能力是 runtime 實跑驗證、哪些只是測試模擬
- `Backends`：這台機器實際能跑哪些 backend
- `Supported CLI tools`：哪些 first-class client 已存在於 `PATH`
- `recommended_backend`：TB2 目前會自動選哪個預設 backend

健康狀態下，輸出大致會像這樣：

```text
Readiness:
  - backend=ready  clients=ready  transport=ready
Validation snapshot:
  - linux_runtime: executed locally  full pytest suite passed in the current workspace
Next steps:
  - Use `tmux` as the default backend on this machine.
  - Run `python -m tb2 init --session demo` before opening GUI, broker, or MCP flows.
```

## 3. 選對 backend 路徑

### 標準預設 policy

- Windows：有 `pywinpty` 就用 `process`，否則透過 WSL 走 `tmux`，再不行才退 `pipe`
- Linux / macOS / WSL：有 `tmux` 就用 `tmux`，否則退 `process`

### 實務規則

- 想要最穩定的 POSIX operator 視角，就選 `tmux`
- 不想依賴 multiplexer，但仍要互動式流程，就選 `process`
- 只有非互動式工具才選 `pipe`

## 4. 五分鐘啟動第一個 session

### CLI 優先

```bash
python -m tb2 init --session demo
python -m tb2 broker --a demo:0.0 --b demo:0.1 --profile codex --auto
```

在 Windows 的 `process` 或 `pipe` 上，pane id 會長成 `demo:a` 與 `demo:b`。

### 第一個 GUI session

```bash
python -m tb2 gui --host 127.0.0.1 --port 3189
```

打開 `http://127.0.0.1:3189/`，然後：

1. 從 `Quick Pairing` 開始。
2. 點 `Init Session`。
3. 點 `Start Collaboration`。
4. 若需要人工審核，再切到 `Approval Gate`。
5. 如果 status 卡片顯示 auto-forward guard 已阻擋，請先把待審佇列 review 完，讓 delivery re-arm。

如果你是刻意要把 GUI 綁到 loopback 以外，請加上 `--allow-remote`，並把這種部署視為 `private-network-experimental`。

### 第一個 MCP session

```bash
python -m tb2 server --host 127.0.0.1 --port 3189
```

把 MCP endpoint 註冊進 client 後，建議照這個順序：

1. `doctor`
2. `terminal_init`
3. `bridge_start`
4. `room_poll` 或 room stream
5. `room_post` / `terminal_send`
6. `status`
7. 需要 durable incident context 時，再用 `audit_recent`
8. `bridge_stop`

若要綁到非 loopback 位址，現在必須明確確認：

```bash
python -m tb2 server --host 10.0.0.5 --port 3189 --allow-remote
```

### 第一個 audit-enabled service session

```bash
TB2_AUDIT=1 python -m tb2 service start --host 127.0.0.1 --port 3189
python -m tb2 service status
python -m tb2 service audit --lines 10
```

當你希望從第一輪就保留 durable operator 與 bridge events 時，請走這條路徑。
這不會改變目前的 restart 契約：`service stop` 或 `service restart` 後，live room / bridge / pending intervention state 仍會遺失。

如果 service host 不是 loopback，也請加上 `--allow-remote`，並把真正的 trust boundary 放在外部網路控管上。

## 5. 先理解 handoff 契約

跨 agent handoff 請使用 `MSG:`。

範例：

```text
MSG: summarize the failing assertion in tests/test_server.py
MSG: ready for review on the shell fallback patch
```

規則：

- 一行 `MSG:` 只放一個可執行請求
- 不要塞多段長文
- 當轉發不應該立刻送出時，請啟用 `intervention`
- 要判斷事件來源時請優先看 machine-readable `source` metadata，不要只靠 `author` 文字推斷

## 6. 常見首次啟動失敗

### Windows 上 `process` 不可用

- 安裝 `pywinpty`
- 或改走 WSL `tmux`

### Linux / macOS 上沒有 `tmux`

- 安裝 `tmux`
- 或改用 `process`

### Room stream 看起來 stale

- 先在 GUI 重連 transport
- 或退回 `room_poll`
- 只有排除 transport 後才重啟 bridge

### Audit 看起來是空的

- 先確認 service 是用 `TB2_AUDIT=1` 或 `TB2_AUDIT_DIR` 啟動
- 再看 `python -m tb2 service status` 裡的 `audit.enabled` 與目前寫入路徑
- 用 `python -m tb2 service audit --lines 20 --event bridge.started` 驗證事件是否真的有落盤

### 啟動了錯的 shell

- 明確設定 `TB2_SHELL`
- 在 Windows 上不要依賴 `SHELL`

## 下一步文件

- [角色導向指南](role-guides.zh-TW.md)
- [平台相容矩陣](platforms/compatibility-matrix.zh-TW.md)
- [MCP 用戶端設定](mcp-client-setup.zh-TW.md)
- [安全姿態](security-posture.zh-TW.md)
