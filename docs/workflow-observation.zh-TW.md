# 工作流程觀測

第二階段新增可選用的唯讀 Python 觀測模組；既有 terminal、room、workstream
與人工審核路徑保持不變。英文[架構文件](workflow-observation.md)為介面說明主版本。

## 直接執行

在專案虛擬環境安裝：

```bash
python -m pip install -e ".[observation]"
python -m tb2 observe demo
```

範例明確標示為合成資料，實際執行正式 reducer／projector：主線仍為 BLOCKED，
修復任務完成驗收後只產生 `ELIGIBLE_FOR_RESUME`，且 `executable: false`。
不呼叫模型、不開 port、不建立終端、不派送任務，也不代表真實 Agent 協作驗收。

## 五層分工

| 層 | 實作 | 邊界 |
| --- | --- | --- |
| Tag | `normalize.py` | 明確區分領域與詞彙；回報不等於驗收 |
| Event | `adapters.py`、`reducer.py` | 驗證來源、封閉 schema、順序及衝突 |
| State | `model.py`、`reducer.py` | 可重建觀測，不取代權威任務狀態 |
| Relation | `relations.py` | 有範圍與版本的相依圖，保留刪除標記 |
| Projection | `projection.py` | 固定輸入得到固定摘要／關係圖／證據參照，不執行動作 |

`SourceVerifier` 是可信任程式內整合介面，不是任意 Python 程式碼的認證機制。
整合者必須確認來源、task、attempt、contract、executor 與 evidence 的精確綁定。
JSON 不能自行提供信任旗標；合成驗證旗標只在 `tests/` 的測試 driver。
runtime 新鮮度不會改寫任務生命週期。

`ObservationJournal` 提供單一寫入者、雜湊鏈 journal、重播與 checksum checkpoint。
checkpoint 損壞時由 journal 重建；中段損壞拒絕載入；尾端截斷可恢復有效前綴，
但停用後續 append。雜湊用於偵測損壞，不能防止惡意本地寫入。
目前沒有 retention／compaction 政策，也不保證斷電耐久性；請將 journal 留在私有位置，
以有界 session 使用。此模組不接管既有服務或放寬人工審核。

## 真正來源檢查

來源命令呼叫 TaskContracts 現有 `inspect()` verifier。請指定有權存取的 task、project
與可信任的 `scripts/task_contract.py`。verifier 會被當成 Python 程式碼執行，
不得使用外來事件或不可信任發送者提供的路徑。

```bash
python -m tb2 observe task --task-dir /authorized/task --project /authorized/project --verifier /trusted/TaskContracts-Automation/scripts/task_contract.py --project-id demo --goal-id main --as-of 2026-09-24T00:00:00.000Z
```

命令只輸出去敏感化 metadata，不輸出任務正文或來源路徑。驗證前後比對來源 digest，
遇到半寫／讀取中異動時有限重試。exit 0 的 `VERIFIED_SOURCE_SNAPSHOT` 只表示來源檢查通過，
不表示任務完成或已成功映射五層事件；非零表示無法安全檢查。

TaskContracts v1.0–v1.2 尚無必要的明確 attempt 身份與 execution／acceptance 參照，
READY／RUNNING／PASS 也不能直接視為 CREATED／EXECUTING／COMPLETE。
adapter 因此保留 `event: null` 與限制代碼，不改寫權威來源來製造相容性。

## 驗證與採納

採納五層 0.1.0-rc.1 研究基線中的七份 frozen schema、詞彙與可攜 fixtures，
由 TB2 封裝為離線 consumer；沒有新增跨專案 publisher、scheduler 或 registry。
只正規化 JSON 排版，不改變契約語義；使用真正 RFC3339 格式驗證與本地 schema 參照。
預設禁止 raw-terminal collection 與 automatic dispatch。

```bash
python -m pip install -e ".[dev]"
python -m pytest tests/test_workflow_observation.py tests/test_observation_graph.py tests/test_observation_taskcontracts.py -q
python -m pytest -q -m "not e2e" -p no:cacheprovider -o addopts=""
```

涵蓋 48 組結構案例、32 組決定性重播，以及儲存、隱私、關係圖、來源 adapter 回歸。
來源測試使用暫存任務，不代表 production 任務整合完成。
[既有 provider 協作限制](validation-status.zh-TW.md)維持不變。
本增量不包含 UI 部署、服務重啟、自動續跑或 provider 呼叫。
