# 入門指南

這份文件提供從乾淨環境到可用 `tb2` session 的最短穩定路徑。

## 1. 安裝

```bash
pip install -e .
```

Windows 互動式 session 另外需要：

```bash
pip install -e ".[windows]"
```

## 2. 先做本機相容性檢查

執行：

```bash
python -m tb2 doctor
```

請先看兩個區塊：

- `Backends`：確認 `tmux`、`process`、`pipe` 是否能用
- `Transports`：確認 `SSE`、`WebSocket`、`room_poll` 是否可用
- `Supported CLI tools`：確認完整支援的 CLI 是否真的安裝在本機

## 3. 選擇完整支援的工具

`tb2` 目前把下面四套視為完整支援的互動式 CLI：

| 工具 | Profile | Windows | Linux / macOS |
|------|---------|---------|---------------|
| OpenAI Codex CLI | `codex` | `process` | `tmux` |
| Claude Code CLI | `claude-code` | `process` | `tmux` |
| Gemini CLI | `gemini` | `process` | `tmux` |
| Aider | `aider` | `process` | `tmux` |

## 4. 啟動第一個 session

### Windows

```bash
python -m tb2 --backend process init --session demo
python -m tb2 --backend process broker --a demo:a --b demo:b --profile codex --auto
```

### Linux / macOS

```bash
python -m tb2 init --session demo
python -m tb2 broker --a demo:0.0 --b demo:0.1 --profile codex --auto
```

## 5. 先理解訊息約定

最重要的約定是：

- 包含 `MSG:` 的行會被視為可轉發訊息
- `--auto` 會啟用自動轉發
- `--intervention` 會先把轉發訊息放進待審佇列，不會立刻送出

範例：

```text
MSG: summarize the current failure
agent> MSG: echo READY
```

## 6. 如果你要做程式化控制

啟動 MCP server：

```bash
python -m tb2 server --host 127.0.0.1 --port 3189
```

接著把 `http://127.0.0.1:3189/mcp` 註冊到支援 MCP 的 CLI。

如果你要走 human-operator 流程，現在有三條 room 觀看路徑：

- `python -m tb2 gui`：workflow-first 瀏覽器介面
- `python -m tb2 room watch --room-id <ROOM_ID>`：純終端監看
- 直接使用 `GET /rooms/{room_id}/stream` 或 `GET /ws`

延伸閱讀：

- [MCP 用戶端設定](mcp-client-setup.zh-TW.md)
- [AI 協作指南](ai-orchestration.zh-TW.md)
