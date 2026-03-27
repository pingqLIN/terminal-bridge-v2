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
6. `bridge_stop`

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

### 啟動了錯的 shell

- 明確設定 `TB2_SHELL`
- 在 Windows 上不要依賴 `SHELL`

## 下一步文件

- [角色導向指南](role-guides.zh-TW.md)
- [平台相容矩陣](platforms/compatibility-matrix.zh-TW.md)
- [MCP 用戶端設定](mcp-client-setup.zh-TW.md)
