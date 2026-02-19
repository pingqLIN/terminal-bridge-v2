# terminal-bridge-v2

[English](README.md)

> 通用 CLI LLM 遙控 + 即時監控 + 人工介入

## 功能特色

- **後端抽象** — 可插拔的終端後端（tmux、process、pipe）
- **工具設定檔** — 內建支援 Codex、Claude Code、Aider、llama.cpp 及自訂工具
- **人工介入** — 待審佇列，支援核准/編輯/拒絕後再轉發
- **自適應輪詢** — 閒置時指數退避，偵測到活動時立即重置
- **高效差異比對** — 基於 hash 的 O(n) 新行偵測
- **單次擷取** — 一次 subprocess 呼叫同時擷取兩個 pane

## 快速開始

```bash
# 建立 tmux session
python -m tb2 init --session demo

# 在另一個終端 attach
tmux attach -t demo

# 使用 Codex profile 啟動 broker
python -m tb2 broker --a demo:0.0 --b demo:0.1 --profile codex --auto

# 啟用人工審查模式
python -m tb2 broker --a demo:0.0 --b demo:0.1 --profile codex --auto --intervention
```

## Broker 指令

| 指令 | 說明 |
|------|------|
| `/a <文字>` | 發送到 pane A |
| `/b <文字>` | 發送到 pane B |
| `/both <文字>` | 同時發送到兩個 pane |
| `/auto on\|off` | 切換自動轉發 |
| `/pause` | 啟用人工審查 |
| `/resume` | 停用審查並放行待審訊息 |
| `/pending` | 列出待審訊息 |
| `/approve <id\|all>` | 核准訊息 |
| `/reject <id\|all>` | 拒絕訊息 |
| `/edit <id> <文字>` | 編輯後送出 |
| `/profile [名稱]` | 顯示/切換 profile |
| `/status` | Broker 狀態 |

## 可用 Profile

- `generic` — 預設 shell 提示
- `codex` — OpenAI Codex CLI
- `claude-code` — Claude Code CLI
- `aider` — Aider CLI
- `llama` — llama.cpp chat
- `gemini` — Gemini CLI

## 使用 Gemini 3 Pro 編排 README

以 `tb2` process backend 呼叫 `gemini-3-pro-preview` 產生 README 編排草稿

```bash
# 1) 啟動 MCP server
python3 -m tb2 --backend process server --host 127.0.0.1 --port 3189

# 2) 初始化 readme session
curl -sS http://127.0.0.1:3189/mcp \
  -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"terminal_init","arguments":{"backend":"process","backend_id":"gemini-readme","session":"readme"}}}'

# 3) 對 readme:a 發送 Gemini 3 Pro 任務
curl -sS http://127.0.0.1:3189/mcp \
  -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"terminal_send","arguments":{"backend":"process","backend_id":"gemini-readme","target":"readme:a","enter":true,"text":"gemini -m gemini-3-pro-preview -p \"請用繁體中文提出 README 重排提案，輸出 Markdown。\""}}}'
```

完整流程請見 `docs/gemini-readme-workflow.zh-TW.md`

## 執行畫面配圖

先用 PowerShell 產生截圖

```powershell
pwsh -File .\scripts\capture_tb2_screenshot.ps1 -OutputDir .\docs\images -Prefix tb2-gemini -Count 3
```

![tb2 + Gemini 畫面 1](docs/images/tb2-gemini-01-20260218-215825.png)
![tb2 + Gemini 畫面 2](docs/images/tb2-gemini-02-20260218-215827.png)
![tb2 + Gemini 畫面 3](docs/images/tb2-gemini-03-20260218-215830.png)

## 授權

[MIT License](https://opensource.org/licenses/MIT)

## 🤖 AI 輔助開發

本專案由 AI 輔助開發。

**使用的 AI 模型/服務：**

- Claude Opus 4（主要架構設計與實作）
- OpenAI Codex CLI（程式碼審查與子代理人貢獻）

> ⚠️ **免責聲明：** 儘管作者已盡力審查和驗證 AI 產生的程式碼，但無法保證其正確性、安全性或適用於任何特定用途。使用風險自負。
