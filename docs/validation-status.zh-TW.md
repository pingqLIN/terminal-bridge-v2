# 驗證狀態

## 第二階段觀測增量 — 2026-09-24

[工作流程觀測核心](workflow-observation.zh-TW.md)通過 48 組結構案例與 32 組決定性語意情境。
CLI 範例實跑、四項使用暫存權威任務的真正 verifier 測試均通過。
來源 adapter 目前僅檢查（`event: null`）；尚未驗收完整權威事件映射或 UI 部署。
本增量未呼叫 provider、未重啟服務；以下歷史協作證據維持原範圍。

更新日期：2026-09-10。版本：0.2.0，operator beta。

## 證據摘要

| 範圍 | 狀態 | 證據界線 |
| --- | --- | --- |
| 本地非 E2E Python suite | PASS | 470 passed、1 skipped、4 deselected；不包含真實模型協作 |
| Windows ConPTY 行輸入／單鍵 | PASS | 2026-08-31 實機資格驗證 |
| Partial TUI capture／嚴格 MSG parser／pane backend reuse | PASS | 工作區修復及回歸測試 |
| 真實 Host 訊息形成 pending，reject 不交付 | PASS | 既有兩輪受限驗收紀錄 |
| Claude Code Guest→Host 核准交付 | INCOMPLETE | 未取得 Guest marker 與目標端交付證據 |
| 完整跨 client 重複驗收 | INCOMPLETE | 尚無兩輪各自完成 approve 與 reject 的證據 |
| Agy CLI 選用 Claude 模型 | LIMITED PASS | 一次獨立 CLI 回覆；generic parser 可解析，尚未走 TB2 backend |
| 本機服務正式部署、自動啟動／恢復 | UNKNOWN | 本次未驗證 |

Agy 測試指定 `claude-sonnet-4-6`，CLI 版本 1.1.25。路由由 CLI 選取，未獨立證實 provider 底層模型身份。CLI 警告停用 slash command expansion 時 `--mode plan` 不生效；這次不構成 plan 模式隔離驗證。

## 如何解讀

測試通過只證明其覆蓋層。client 可偵測、模型可列出、命令回顯、queued／pending 或 approve 回傳成功，都不能取代目標端收到訊息的證據。新 client 的驗收須固定 pairing 與 backend，取得真實回覆、核准交付、拒絕不交付與可重複性。

本頁是去敏感化的工作區驗證摘要，不表示這些修復已發布；本地測試也不等於 GitHub CI 結果。歷史平台結果見[相容矩陣](platforms/compatibility-matrix.zh-TW.md)。

## 重現測試

先安裝開發依賴，再執行：

```bash
python -m pytest -q -m "not e2e" -p no:cacheprovider -o addopts=""
```

真實 tmux E2E 需要專用可丟棄測試環境。完整 provider 協作需要另外準備 client 存取權與費用預算。
