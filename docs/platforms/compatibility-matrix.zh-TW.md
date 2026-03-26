# 平台相容矩陣

這份文件專門記錄三件事：哪些情境已在本次工作中實機驗證、哪些只靠自動化模擬覆蓋、以及哪些仍待原生機器確認。

## 驗證快照

本次重寫使用的驗證快照：

- 日期：`2026-03-13`
- 實機驗證環境：Linux、Python `3.12.3`
- 驗證結果：完整 `pytest` suite 通過（`245 passed`）
- 自動化模擬覆蓋：Windows backend 選擇、Windows shell policy、macOS state-root 行為、WSL `tmux` 呼叫、PowerShell 與 `cmd.exe` shell 語義

本文件使用以下驗證等級：

- `runtime-verified`：本次工作中已在目前 workspace 實際執行
- `simulated`：有自動化測試或可確定的 code-path 斷言，但本次沒有在原生機器實跑
- `not verified`：設計上支援，但本次沒有驗證

## 作業系統矩陣

| OS / 環境 | 預設 Backend Policy | 驗證等級 | 說明 |
| --- | --- | --- | --- |
| Native Linux | `tmux` 存在就用 `tmux`，否則退到 `process` | runtime-verified | 本次 workspace 完整測試皆通過。 |
| Native macOS | `tmux` 存在就用 `tmux`，否則退到 `process` | simulated | 與 Linux 共用 POSIX shell 行為；service state-root 由測試覆蓋。 |
| Native Windows | 有 `pywinpty` 就用 `process`，否則有 `wsl.exe` 就退到 `tmux`，再不行退 `pipe` | simulated | 預設 shell 會忽略 `SHELL`，依序優先 `pwsh`、`powershell.exe`、`COMSPEC`。 |
| Native Windows -> WSL `tmux` | 透過 `wsl -d <distro> -- sh -lc` 跑 `tmux` | simulated | backend 測試有覆蓋 capture 與 command routing。 |
| Inside WSL | `tmux` 存在就用 `tmux`，否則退到 `process` | simulated | 與 Linux 同樣是 POSIX shell 語義，但 `tmux` 指令直接在 WSL 內執行。 |

## Backend 矩陣

| Backend | 最適合的場景 | 平台說明 | 驗證等級 |
| --- | --- | --- | --- |
| `tmux` | Linux、macOS、WSL 上的互動式 host/guest session | pane id 形如 `session:0.0` / `session:0.1`；capture 透過 `sh -lc` 與 quote 後的 pane target | Linux 實機驗證，其餘 simulated |
| `process` | 不靠 multiplexer 的互動式 session | pane id 形如 `session:a` / `session:b`；Windows 需 `pywinpty`；POSIX 用 PTY | Linux 實機驗證，Windows simulated |
| `pipe` | 非互動式或 fallback 工作流 | 最適合能走純 stdin/stdout 的 client；不支援 TUI | Linux 實機驗證，Windows shell 變體 simulated |

## Shell 矩陣

| Shell | 啟動參數 | `pipe` 的 Enter | `process` PTY 的 Enter | 驗證等級 |
| --- | --- | --- | --- | --- |
| `pwsh` / `powershell.exe` | 自動補 `-NoLogo -NoProfile` | `\\r\\n` | `\\r\\n` | simulated |
| `cmd.exe` | 無額外參數 | `\\r\\n` | `\\r\\n` | simulated |
| `bash` | 無額外參數 | `\\n` | `\\r` | Linux 實機驗證 |
| `zsh` | 無額外參數 | `\\n` | `\\r` | simulated |
| `sh` | 無額外參數 | `\\n` | `\\r` | 透過 `tmux` helper path 實機驗證 |

## 路徑與狀態差異

| 面向 | Windows | macOS | Linux / WSL |
| --- | --- | --- | --- |
| Service state root | `%LOCALAPPDATA%\\tb2` 或 `~/AppData/Local/tb2` | 若有 `XDG_STATE_HOME` 則用 `XDG_STATE_HOME/tb2`，否則預設 `~/Library/Application Support/tb2`，但若已存在舊版 `~/.local/state/tb2` state 檔就沿用舊路徑 | 若有 `XDG_STATE_HOME` 則用 `XDG_STATE_HOME/tb2`，否則 `~/.local/state/tb2` |
| 預設 shell override | 只看 `TB2_SHELL` | 先 `TB2_SHELL`，再 `SHELL` | 先 `TB2_SHELL`，再 `SHELL` |
| 預設 pane 命名 | `process` / `pipe` 用 `session:a`、`session:b` | `tmux` 用 `session:0.0`、`session:0.1`；`process` / `pipe` 用 `session:a`、`session:b` | 與 macOS 相同 |

## 標準建議組合

| 場景 | 建議組合 | 原因 |
| --- | --- | --- |
| Linux 上的 Host + Guest coding | `tmux` + `codex` / `claude-code` / `gemini` / `aider` | 可觀測性最好，pane addressing 最穩 |
| macOS 上的 Host + Guest coding | 有 `tmux` 就用 `tmux`，否則用 `process` | operator 模型與 Linux 一致；有 `tmux` 時 shell 驚喜最少 |
| Windows 上的 Host + Guest coding | `process` + `pwsh` | 若安裝了 `pywinpty`，這是最穩定的原生互動路徑 |
| 沒有 `pywinpty` 的 Windows | 走 WSL `tmux`，再不行才退 `pipe` | 避免落到失敗的原生互動路徑 |
| 非互動式 automation | `pipe` | 給 scripting 或 JSON-mode 工具的 I/O 面最單純 |

## 已知行為差異

- POSIX 上的 `process` PTY 會用 `\\r` 模擬 Enter，因為 terminal key semantics 不等同於單純的文字換行。
- POSIX 上的 `pipe` 會用 `\\n`，因為它寫進的是 stdin，不是 terminal key event stream。
- Windows 預設 shell policy 會忽略 `SHELL`，避免 Git Bash 或 MSYS 的環境變數意外接管 native Windows 預設。
- macOS 會在既有 state 檔存在時保留舊的 `~/.local/state/tb2` 路徑，避免升級後看不到正在跑的 service。

## 決策檢查表

- 新機器第一次使用前先跑 `python -m tb2 doctor`。
- Windows 上若 `process` 不可用，先安裝 `pywinpty`，或改走 WSL `tmux`。
- Linux / macOS 若沒有 `tmux`，請改用 `process`，不要硬塞 `tmux`。
- 只有在 client 不需要真實 terminal 時才選 `pipe`。
