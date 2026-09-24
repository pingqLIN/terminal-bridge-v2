<p align="center">
  <img src="docs/images/kindergarten/05-readme-banner.png" alt="TB2：AI 角色在小橋上交接訊息，由人類操作員監看" width="100%">
</p>

# terminal-bridge-v2

**讓 AI 在真實終端協作，讓交接看得見、讓人能參與審核的本地控制面。**

[English](README.md) · [快速開始](docs/getting-started.zh-TW.md) · [文件入口](docs/README.zh-TW.md) · [驗證狀態](docs/validation-status.zh-TW.md)

TB2 把 Host AI、Guest AI 與人類操作員放在同一個工作流程：用 bridge 連接終端 pane，在 room 觀察訊息，並在轉送前審核交接內容。CLI、瀏覽器控制台與本地 MCP endpoint 都能操作同一套控制面。

## 可以做什麼

| 功能 | 用途 |
| --- | --- |
| 終端擷取、傳送與中斷 | 透過 `tmux`、`process` 或非互動式 `pipe` fallback 操作既有 CLI agent |
| `MSG:` 結構化交接 | 將可執行請求與一般終端輸出分開 |
| 人工審核佇列 | 檢視、編輯、核准或拒絕待交接訊息 |
| Room 與 workstream | 觀察協作、審核政策、相依關係與生命週期 |
| 瀏覽器控制台 | 提供 Quick Pairing、Approval Gate、Mission Control 等七種情境 |
| MCP 與訊息串流 | 從 client 呼叫工具，透過 polling、SSE 或 WebSocket 觀察訊息 |
| 稽核與治理 | 選擇保存遮罩後的稽核事件，查閱生效政策及其來源 |

## 快速開始

需要 Python 3.9 以上。在專案 checkout 中建立虛擬環境後安裝。

**Windows / PowerShell**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[windows]"
python -m tb2 doctor --json
python -m tb2 gui --host 127.0.0.1 --port 3189
```

**Linux / macOS / WSL**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m tb2 doctor --json
python -m tb2 gui --host 127.0.0.1 --port 3189
```

控制台位於 **http://127.0.0.1:3189/**。依[入門指南](docs/getting-started.zh-TW.md)選擇 backend，先啟用審核再傳送任務。AI client 需要各自安裝、登入與取得 provider 存取權；模型使用可能產生費用。

若 TB2 server 已在執行，直接開啟其控制台。MCP client 使用 `http://127.0.0.1:3189/mcp`。

## 如何協作

![AI 角色透過小橋交接一張 MSG 卡片](docs/images/kindergarten/02-msg-class.png)

1. Host 準備範圍明確的任務，選擇 Guest profile。
2. Guest 在指定 pane 工作，需要交接時輸出一行簡短的 `MSG:`。
3. 操作員確認目的地與內容，再核准、編輯或拒絕交付。
4. 觀察目標端實際輸出，完成後停止 workstream。

```text
MSG: summarize the failing assertion in tests/test_server.py
```

配圖把 TB2 比喻成練習協作規則的幼兒園。Host 是合適 client 都可擔任的角色，人類老師代表操作員；這是工作流程的比喻，不表示 TB2 會訓練模型。詳見[圖解角色指南](docs/role-guides.zh-TW.md)。

## 目前成熟度

第二階段新增[工作流程觀測模組](docs/workflow-observation.zh-TW.md)，提供決定性的五層讀模型、
可重播 journal 與可選用的權威來源檢查。無須啟動服務即可試用：

```bash
python -m pip install -e ".[observation]"
python -m tb2 observe demo
```

範例使用合成資料；TaskContracts 檢查為唯讀，目前尚未將原生狀態映射成完整綁定的五層任務事件。

**v0.2.0 · operator beta。** 控制功能已實作，完整跨 client 協作仍待驗收。

- 2026 年 9 月 10 日本地非 E2E 測試：**470 passed、1 skipped、4 deselected**。
- Native Windows ConPTY 行輸入與按鍵已有直接驗證；partial TUI capture 與訊息解析修復已有回歸測試。
- 最新 Codex Host／Claude Code Guest 驗收尚未完成 Guest→Host 核准交付及可重複性。
- Agy CLI 選用 Claude 模型的單次回覆與 parser 相容性檢查已通過；經 TB2 執行與完整雙向交付仍未驗證。
- Linux／WSL 歷史實機結果、平台模擬測試與目前 Windows 證據分開記錄。

詳見[驗證狀態](docs/validation-status.zh-TW.md)與保留日期的[平台相容矩陣](docs/platforms/compatibility-matrix.zh-TW.md)。

## 使用邊界

- 支援同一台可信任電腦上的本地操作，維持預設 loopback 綁定。
- 私有網路使用屬實驗性；不支援直接暴露到網際網路。
- 人工審核協助操作決策，但不是安全沙箱或正式認證／授權邊界。
- 稽核保存可選擇啟用，持久化文字預設遮罩；完整文字需要明確 opt-in，且可能保存敏感內容。
- 服務快照協助恢復，但不保證還原存活終端行程、room 訂閱或待審訊息。
- 已提供手動服務生命週期命令；目前驗收證據尚未建立無人值守自動啟動與自動恢復能力。

調整網路暴露或稽核設定前，請閱讀[安全定位](docs/security-posture.zh-TW.md)。

## 延伸閱讀

- [角色指南](docs/role-guides.zh-TW.md)：Host、Guest、操作員與 MCP 整合者。
- [控制台](docs/control-console.zh-TW.md)：情境 preset 與操作功能。
- [MCP 設定](docs/mcp-client-setup.zh-TW.md)與[傳輸範例](docs/transport-examples.zh-TW.md)。
- [治理分層](docs/governance-layering.zh-TW.md)：生效設定及來源。
- [專案結構](docs/repository-structure.zh-TW.md)與[貢獻指南](CONTRIBUTING.md)。
- [支援](SUPPORT.md)、[安全通報](SECURITY.md)、[變更紀錄](CHANGELOG.md)。

專案採用 [MIT](LICENSE)。AI 服務商名稱與風格化標誌用於辨識插圖角色，不代表背書；詳見[圖片說明](docs/images/kindergarten/README.zh-TW.md)。
