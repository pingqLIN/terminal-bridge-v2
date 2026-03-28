# 平台與終端行為

這份文件記錄 TB2 哪些行為是在真實 runtime 驗證、哪些由自動化測試模擬，以及不同 backend、shell、transport 之間有哪些差異。

## 驗證快照

記錄時間：2026 年 3 月 27 日。

| 範圍 | 驗證方式 | 目前說明 |
| --- | --- | --- |
| Linux runtime | 本機實際執行 | 完整 pytest suite 通過：`295 passed` |
| `tmux` workflow | 本機實際執行 | 目前 Linux 環境的 end-to-end tests 通過 |
| Windows backend 與 shell policy | 針對性測試模擬 | 已涵蓋 shell argv、fallback backend policy、remote-control handoff 規則 |
| macOS state path 與 backend fallback policy | 針對性測試模擬 | 已涵蓋 XDG precedence、legacy state 保留與 POSIX shell 行為 |

## Backend 矩陣

| Backend | Pane naming | 互動品質 | 最適用途 | 主要限制 |
| --- | --- | --- | --- | --- |
| `tmux` | `session:0.0`、`session:0.1` | 最高 | Linux/macOS/WSL 的 agent 協作 | 需要 `tmux` |
| `process` | `session:a`、`session:b` | 高 | Windows 原生、POSIX fallback | Windows 需要 `pywinpty` |
| `pipe` | `session:a`、`session:b` | TUI 差，line tool 可用 | 非互動或 batch tooling | 沒有真實 terminal 語意 |

## 預設 Backend Policy

TB2 現在依 capability 選預設。

| 條件 | 預設 |
| --- | --- |
| Linux / macOS 且有 `tmux` | `tmux` |
| Linux / macOS 沒有 `tmux` | `process` |
| Windows 且有 `pywinpty` | `process` |
| Windows 沒有 `pywinpty` 但有 WSL | `tmux` |
| 以上都不成立 | `pipe` |

## Shell 選擇策略

### Windows

優先順序：

1. `TB2_SHELL`
2. `pwsh`
3. `powershell.exe`
4. `COMSPEC`

重要行為：

- TB2 在 native Windows 會刻意忽略 `SHELL`，避免 Git Bash 或 MSYS 的環境變數意外變成原生 Windows Python process 的預設 shell。

### Linux / macOS

優先順序：

1. `TB2_SHELL`
2. `SHELL`
3. `/bin/bash`
4. `/bin/zsh`
5. `/bin/sh`
6. `PATH` 中的 `sh`

## Enter 行為差異

| Runtime | Shell family | TB2 送出的 Enter 序列 | 原因 |
| --- | --- | --- | --- |
| `process` PTY | POSIX shells | `\r` | 更接近真實 terminal 的 Enter 行為 |
| `process` PTY | `cmd` / `pwsh` / `powershell` | `\r\n` | 符合 Windows console 預期 |
| `pipe` | POSIX shells | `\n` | line-oriented stdin |
| `pipe` | `cmd` / `pwsh` / `powershell` | `\r\n` | 符合 Windows shell stdin |
| `tmux` | tmux 裡的任何 shell | `tmux send-keys Enter` | 由 pane-aware terminal semantics 處理 |

## Shell Family 備註

| Shell family | 目前支援姿態 | 備註 |
| --- | --- | --- |
| `bash` / `zsh` / `sh` | POSIX 第一級支援 | 適合 `tmux` 與 `process` |
| `pwsh` / `powershell.exe` | Windows 第一級支援 | TB2 會自動補 `-NoLogo -NoProfile` |
| `cmd.exe` | 可支援 | Windows 最低摩擦 fallback |
| Windows 上的 Git Bash / MSYS shell | 明確指定時支援 | 不再被當成隱式預設值 |

## Service State Path 策略

| 平台 | 優先 state root | 相容規則 |
| --- | --- | --- |
| Windows | `%LOCALAPPDATA%/tb2` | 若缺少則退到 `~/AppData/Local/tb2` |
| macOS | `~/Library/Application Support/tb2` | 同時尊重 `XDG_STATE_HOME`，並在存在 state 檔時保留 `~/.local/state/tb2` |
| Linux | `$XDG_STATE_HOME/tb2` 或 `~/.local/state/tb2` | 標準 XDG fallback |

## Transport 備註

| Transport | 最適用途 | 限制 |
| --- | --- | --- |
| SSE | 預設 live-room 監看路徑 | 只有單向 stream |
| WebSocket | 進階 client control | 比 SSE 更複雜 |
| `room_poll` | script fallback 與 diagnostics | 即時性較低、round-trip 較多 |

## Event 與 Guard 語義

- room event 現在除了 `author` 之外，也會公開 machine-readable `source` metadata
- `source_type`、`source_role`、`trusted` 應被視為 automation 與 UI 判斷的正式契約
- bridge status 會附帶 `auto_forward_guard`，方便 operator 看見 runaway 保護何時把 delivery 切進 review

## 哪些是實跑，哪些是模擬

### 本機實際執行

- 完整 pytest suite
- Linux 上的 e2e tests
- 目前 server 實作支撐的瀏覽器控制流程

### 由針對性測試模擬

- Windows 從 `process` 退到 `tmux` 或 `pipe`
- Windows shell 選擇與 PowerShell argv 行為
- Windows remote-control shell handoff 決策
- macOS state-root migration 與 XDG precedence
- `process` 與 `pipe` 在 POSIX shell 的 Enter 行為

## 實務建議

- 平台能力有變化時請重新執行 `python -m tb2 doctor`。
- backend 選擇應視為機器 capability 問題，而不是個人偏好問題。
- 如果 UI、CLI、MCP 範例裡的 pane naming 對不上，先檢查目前 backend。
- 如果 Guest 輸出沒有被轉發，先看 `MSG:` 是否符合契約，以及目前 active profile 是什麼。
