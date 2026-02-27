# MCP 用戶端設定與相容性

本文件提供 `terminal-bridge-v2`（`tb2`）可重現的 MCP 設定流程，涵蓋：

- OpenAI Codex CLI
- Claude Code CLI
- Gemini CLI

並附上相依檢查與相容性驗證重點。

## 1) 前置需求

- Python `>=3.9`
- 安裝專案：

```bash
pip install -e .
```

- Windows `process` 後端相依：

```bash
pip install -e ".[windows]"
# 或
pip install pywinpty
```

## 2) 啟動 tb2 MCP 伺服器

```bash
python -m tb2 server --host 127.0.0.1 --port 3189
```

若要跨平台背景常駐託管，可改用：

```bash
python -m tb2 service start --host 127.0.0.1 --port 3189
python -m tb2 service status
```

可選的快速健康檢查：

```bash
curl -sS http://127.0.0.1:3189/healthz
```

所有用戶端共用端點：

- `http://127.0.0.1:3189/mcp`

## 3) 在三個 CLI 註冊 tb2

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

## 4) 健康檢查

```bash
codex mcp list
claude mcp list
gemini mcp list
```

預期結果：

- Claude 與 Gemini 顯示 `tb2 ... Connected`
- Codex 清單可見 `tb2 ... enabled`

## 5) 協定探測（建議）

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

## 6) 相容性重點

目前 `tb2` MCP 伺服器已補齊：

- `initialize`
- `ping`
- `notifications/initialized`
- `tools/list` 回傳 MCP 標準欄位（`name` `description` `inputSchema`）
- `resources/list` 與 `prompts/list` 空清單回應
- `initialize` 回應會回傳 client 要求的 `protocolVersion`（新版 MCP SDK 關鍵）

因此可與以下模式相容：

- Codex CLI URL transport
- Claude Code HTTP transport
- Gemini HTTP transport（MCP SDK streamable HTTP client）

## 7) 後端相依矩陣

| 後端 | 平台 | 相依 | Smoke 結果 |
| --- | --- | --- | --- |
| `tmux` | Linux/macOS/WSL | `tmux` | 本次 Windows 檢查未驗 |
| `process` | Windows/Linux/macOS | Windows 需 `pywinpty` | 通過 |
| `pipe` | 全平台 | 無 | 通過 |

Windows `process` 後端提醒：

- shell 啟動暖機後才會穩定看到第一批輸出
- 自動驗證建議在第一個命令前保留短暫等待

## 8) 移除註冊

```bash
codex mcp remove tb2
claude mcp remove -s user tb2
gemini mcp remove --scope user tb2
```

## 9) 非終端機使用者可用的 GUI

```bash
python -m tb2 gui --host 127.0.0.1 --port 3189
```

開啟：

- `http://127.0.0.1:3189/`
