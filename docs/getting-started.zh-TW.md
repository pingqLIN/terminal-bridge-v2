# 入門指南

[English](getting-started.md) · [文件入口](README.zh-TW.md)

## 1. 安裝

需要 Python 3.9 以上。先取得專案 checkout，再於根目錄操作。

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[windows]"
```

如果環境政策不允許啟用腳本，直接用 `.\.venv\Scripts\python.exe` 取代後續命令中的 `python`，不必變更 execution policy。

Linux、macOS 或 WSL：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

開發測試另安裝 `python -m pip install -e ".[dev]"`。各 AI client 的安裝、登入、模型權限與費用由其本身管理。

## 2. 檢查本機能力

```bash
python -m tb2 doctor --json
python -m tb2 profiles --verbose
```

Windows 有 pywinpty 時可使用互動式 process；POSIX 可使用 tmux 或 process。pipe 只適合非互動式 stdin/stdout，不提供 TUI。doctor 的 client discovery 不代表模型認證或完整協作已通過。

## 3. 開啟同一個控制面

```bash
python -m tb2 gui --host 127.0.0.1 --port 3189
```

控制台：http://127.0.0.1:3189/
MCP：http://127.0.0.1:3189/mcp

已有 server 時直接開啟其網址，不再啟動第二個同 port server。GUI 與 MCP 共用同一個 server；process／pipe pane 需要由持有它的 runtime 操作，不能假設一次獨立 CLI init 建立的記憶體狀態會供下一個 CLI process 使用。

## 4. 第一次協作

1. 在控制台選擇 backend 與 Host／Guest profile，使用 Init Session 建立一組 pane。
2. 在 Start Collaboration 前選擇 Approval Gate，保持 auto-forward 與 intervention 都啟用。TB2 的 auto_forward 開啟 MSG 解析，intervention 再將解析出的訊息送入人工審核。
3. 在分配的 pane 啟動已設定好的 client。遇到登入、trust 或模型設定要求時，先由操作員確認影響。
4. 發送一個範圍明確的非破壞性任務。
5. Guest 以一行 MSG: 回覆；檢查 pending 的目的地與內容，再核准或拒絕。
6. 從目標 pane 的 capture 確認實際交付，不能只看 queued 或成功通知。
7. 完成後停止 workstream，確認 owned runtime 已清理。

```text
MSG: summarize the failing assertion in tests/test_server.py
```

一行只放一件事。一般 terminal output 不應自動當作交接。新 client 應保持 intervention 啟用，完成資格驗證後才考慮取消人工審核。

## 5. MCP 與維運

若只需 server：

```bash
python -m tb2 server --host 127.0.0.1 --port 3189
```

client 連線後，可依序使用 doctor、terminal_init、bridge_start、room_poll、intervention_list，再核准／拒絕並擷取目標端。保持 backend instance 與 pane 所有權一致；完成後用 workstream_stop 清理整組 owned workstream，bridge_stop 僅停止 bridge 的範圍依回傳結果確認。

選擇保存稽核時，可於啟動前設定 TB2_AUDIT=1；持久化文字預設 mask。完整文字另需明確 opt-in。服務快照不保證恢復 live terminal、訂閱或 pending queue。詳見[控制台](control-console.zh-TW.md)與[安全定位](security-posture.zh-TW.md)。

## 排除常見問題

- Windows process 不可用：確認安裝 windows extra 與目前使用的 Python 環境。
- Room stream 停滯：先重連傳輸或使用 room_poll，再診斷 bridge。
- 有 pending 卻未交付：確認 review 狀態及目標端 capture，不以重送取代診斷。
- Shell 不符預期：檢查 TB2_SHELL；Windows 不依賴 SHELL。
- Client 沒回覆：分開檢查 client 路徑、provider 可用性與 TB2 transport。

繼續閱讀：[角色指南](role-guides.zh-TW.md)、[MCP 設定](mcp-client-setup.zh-TW.md)、[驗證狀態](validation-status.zh-TW.md)。
