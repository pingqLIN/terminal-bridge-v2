<h1 align="center">terminal-bridge-v2</h1>

<p align="center">
  <strong>給 Host AI、Guest AI 與 Human Operator 在真實 terminal 協作時共用的一套本地控制面。</strong>
</p>

<p align="center">
  <a href="https://github.com/pingqLIN/terminal-bridge-v2/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/pingqLIN/terminal-bridge-v2/ci.yml?branch=main&label=ci" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-%3E%3D3.9-blue.svg" alt="Python >= 3.9"></a>
  <img src="https://img.shields.io/badge/MCP-JSON--RPC-orange.svg" alt="MCP JSON-RPC">
  <img src="https://img.shields.io/badge/tested-linux%20runtime-green.svg" alt="Tested on Linux runtime">
</p>

<p align="center">
  <a href="README.md">English</a> •
  <a href="#為什麼是-tb2">為什麼是 TB2</a> •
  <a href="#主要工作流">主要工作流</a> •
  <a href="#依角色選入口">依角色選入口</a> •
  <a href="#平台快照">平台快照</a> •
  <a href="#文件地圖">文件地圖</a>
</p>

<p align="center">
  <img src="docs/images/control-center.png" alt="terminal-bridge-v2 control console preview" width="860">
</p>

## 為什麼是 TB2

`tb2` 是一個本地 orchestration layer，給想要保留真實 terminal 工作流、又不想失去人工控制的團隊使用。

當你要把 Host AI、Guest AI 與 Human Operator 放進同一套可觀測的 room / bridge 模型，同時還要保有 room-level visibility、approval gate 與 cross-platform control 時，TB2 就是那個控制面。

同一套控制面可以從這些入口操作：

- CLI
- 瀏覽器控制台
- 支援 MCP 的 client，例如 Codex CLI、Claude Code、Gemini CLI

TB2 特別適合這類情境：

- 穩定的 handoff 契約
- 人工審核路徑
- room 與 bridge 的觀測能力
- 能適配 Windows、macOS、Linux、WSL 的 backend 策略

## 為什麼團隊會選 TB2

| 決策問題 | TB2 的回答 |
| --- | --- |
| 你要的是真實 terminal，不是 toy chat sandbox | bridge 直接對應實際 pane、shell 與 operator workflow |
| 你要把 Host AI、Guest AI、Human review 放進同一個 loop | rooms、interventions、approval gates 都是 first-class 能力 |
| 你的 agents 來自不同 client | CLI、browser GUI、MCP 可以共用同一個本地 control plane |
| 你的環境跨 Windows / macOS / Linux / WSL | backend fallback 與 shell policy 已寫進文件並由測試覆蓋 |
| 你要 UI 好上手，但不能犧牲完整功能 | task preset 先精簡主畫面，進階控制仍完整保留 |

## 入口怎麼選

| 入口 | 最適合的情境 | 取捨 |
| --- | --- | --- |
| CLI | 操作者已經知道 panes、shell 與 bridge ids | 速度最快，但預設使用者已理解 TB2 內部結構 |
| Browser GUI | human operator 需要任務 preset、review queue 與 room 可視化 | 最容易上手，但仍以本地主機操作為中心 |
| MCP endpoint | 另一個 AI client 應該把 TB2 當 tool surface 來驅動 | 自動化最好，但前提是 client 自己已有操作介面 |
| 混合模式：MCP + GUI | AI client 負責流程，human 負責監看與放行 | 監管能力最強，但需要同時維持兩個入口 |

## 主要工作流

| 工作流 | 最適合的場景 | 預設入口 |
| --- | --- | --- |
| Host + Guest coding loop | 委派式開發、review、debug | CLI 或 MCP + GUI oversight |
| Approval-gated review | 需要 human-in-the-loop 的轉發 | GUI `Approval Gate` preset |
| MCP control plane | Codex / Claude / Gemini orchestration | `http://127.0.0.1:3189/mcp` |

瀏覽器控制台現在是任務導向 preset：

- `Quick Pairing`：啟動新的 host + guest session，並直接進入 live room
- `Approval Gate`：審核、編輯、核准待轉發 handoff
- `MCP Operator`：監看由外部 MCP client 驅動的 workflow
- `Diagnostics`：capture panes、interrupt agents、檢查 status
- `Handoff Radar`：把 live room 與審核佇列並排，適合密集交接與 review
- `Quiet Loop`：把 UI 收斂成啟動與即時協作主線，降低操作噪音
- `Mission Control`：把拓樸、診斷與協調同時打開，適合 Host 主導的總控視角

## 快速安裝

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

如果 `doctor` 顯示 Windows 的 `process` backend 不可用，請安裝 `pywinpty`，或改走 WSL `tmux` 路徑。

## 五分鐘跑起第一個 Session

### CLI 優先

```bash
python -m tb2 init --session demo
python -m tb2 broker --a demo:0.0 --b demo:0.1 --profile codex --auto
```

在 Windows 上若使用 `process` backend，pane id 會是 `demo:a` 與 `demo:b`。

### GUI 優先

```bash
python -m tb2 gui --host 127.0.0.1 --port 3189
```

打開 `http://127.0.0.1:3189/`。

### MCP 優先

```bash
python -m tb2 server --host 127.0.0.1 --port 3189
```

接著註冊：

- Codex CLI：`codex mcp add tb2 --url http://127.0.0.1:3189/mcp`
- Claude Code：`claude mcp add --transport http -s user tb2 http://127.0.0.1:3189/mcp`
- Gemini CLI：`gemini mcp add tb2 http://127.0.0.1:3189/mcp --transport http --scope user`

## 依角色選入口

| 如果你是... | 從這裡開始 |
| --- | --- |
| 還在評估 TB2 是否適合團隊 | [入門指南](docs/getting-started.zh-TW.md) |
| 要跑 host agent 或 orchestration loop | [角色導向指南](docs/role-guides.zh-TW.md#host-ai) |
| 要設計 guest prompt 或輸出契約 | [角色導向指南](docs/role-guides.zh-TW.md#guest-ai) |
| 要當 human reviewer 或支援操作者 | [角色導向指南](docs/role-guides.zh-TW.md#human-operator) |
| 要接 MCP client 或 automation | [MCP 用戶端設定](docs/mcp-client-setup.zh-TW.md) |

## 平台快照

### 本 repo 目前記錄的驗證狀態

- Linux：本次 workspace 內實機驗證，完整 `pytest` suite 通過
- Windows：以自動化測試模擬 backend fallback、shell policy、remote-control 行為與 state 路徑
- macOS：以自動化測試模擬 POSIX shell 與 service state 行為
- WSL：以 backend 測試模擬 `wsl -d <distro> -- sh -lc` 的 `tmux` 執行路徑

### 目前預設 backend policy

| 環境 | 預設值 |
| --- | --- |
| Windows | 有 `pywinpty` 就用 `process`，否則有 WSL 就退到 `tmux`，再不行退到 `pipe` |
| Linux / macOS / WSL | 有 `tmux` 就用 `tmux`，否則退到 `process` |

完整 shell、路徑、Enter 行為差異請看 [平台相容矩陣](docs/platforms/compatibility-matrix.zh-TW.md)。

## 控制台

瀏覽器控制台現在的原則是不再一次把所有按鈕攤平，而是依任務 preset 先過濾出主要動作。

- 主要工作流按鈕固定可見
- approval controls 只在 approval-centric 場景浮到前面
- raw ids 與 backend mapping 仍保留在進階區塊
- diagnostics 與 direct terminal operations 完整保留，但不再主導預設視覺層級
- 內建語言切換支援 English 與繁體中文
- 內建版面切換可在標準、加寬、堆疊三種排列間切換

這樣對 operator 來說更易進入，同時不犧牲完整功能面。

## 文件地圖

### 從這裡開始

- [入門指南](docs/getting-started.zh-TW.md)
- [角色導向指南](docs/role-guides.zh-TW.md)
- [控制台指南](docs/control-console.zh-TW.md)
- [平台行為說明](docs/platform-behavior.zh-TW.md)
- [平台相容矩陣](docs/platforms/compatibility-matrix.zh-TW.md)
- [標準操作手冊](docs/platforms/standard-operations.zh-TW.md)

### 架構與整合

- [AI 協作說明](docs/ai-orchestration.zh-TW.md)
- [MCP 用戶端設定](docs/mcp-client-setup.zh-TW.md)
- [使用場景與工作流索引](docs/use-cases.zh-TW.md)

### 英文版

- [README.md](README.md)
- [docs/getting-started.md](docs/getting-started.md)
- [docs/role-guides.md](docs/role-guides.md)
- [docs/control-console.md](docs/control-console.md)
- [docs/platform-behavior.md](docs/platform-behavior.md)
- [docs/platforms/compatibility-matrix.md](docs/platforms/compatibility-matrix.md)
- [docs/platforms/standard-operations.md](docs/platforms/standard-operations.md)

## 安全提醒

- server binding 預設維持在 `127.0.0.1`。
- MCP endpoint 與 browser console 都應視為敏感的本地控制面。
- 驗證新 profile、新 client、新流程時，優先開 `intervention` mode。
- 同一組 pane pair 只保留一個 active bridge。

## 專案支援

- [CONTRIBUTING.md](CONTRIBUTING.md)
- [SUPPORT.md](SUPPORT.md)
- [SECURITY.md](SECURITY.md)
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- [CHANGELOG.md](CHANGELOG.md)
