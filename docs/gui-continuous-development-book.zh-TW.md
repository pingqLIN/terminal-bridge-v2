# GUI 持續開發書

## 目的

本文件定義 Terminal Bridge GUI 在長時間 YOLO 開發模式下的固定節奏，避免開發只停留在零散修補。流程以 3 輪循環推進：

1. 評估
2. 開發
3. 檢驗
4. 外部審查
5. 修正

每一輪都要完成一次完整閉環，再進入下一輪。

## 設計基線

本 GUI 的設計與流程基線來自：

- [.impeccable.md](/home/miles/dev2/projects/terminal-bridge-v2/.impeccable.md)
- [gui-clarify-improvement-plan.zh-TW.md](/home/miles/dev2/projects/terminal-bridge-v2/docs/gui-clarify-improvement-plan.zh-TW.md)
- [README.md](/home/miles/dev2/projects/terminal-bridge-v2/README.md)
- [docs/control-console.md](/home/miles/dev2/projects/terminal-bridge-v2/docs/control-console.md)
- [docs/use-cases.md](/home/miles/dev2/projects/terminal-bridge-v2/docs/use-cases.md)

核心原則：

- 這不是面向大眾的 SaaS dashboard，而是 operator-grade control console。
- 介面優先服務高壓情境下的 Human Operator、Host AI Supervisor、MCP Integrator。
- 視覺與互動應該減少歧義，而不是增加裝飾。
- `launch settings` 與 `live runtime` 必須嚴格分離。

## 建議技能

本任務建議按順序使用以下技能視角：

- `frontend-design`
- `clarify`
- `arrange`
- `polish`
- `harden`
- `audit`
- `critique`

用途對應：

- `clarify`：收斂術語、空狀態、操作提示、錯誤文案。
- `arrange`：重整區塊結構、導航、資訊密度、分頁節奏。
- `polish`：做最後視覺一致性、對齊、節點互動、細節修飾。
- `harden`：處理 runtime drift、空資料、disabled state、keyboard flow。
- `audit`：做技術面檢查，確認 a11y、responsive、anti-pattern。
- `critique`：站在 operator workflow 角度做 UX 外部審查。

## 建議工具

本任務優先使用本地工具，不依賴外部服務：

- `git status --short --branch`
- `python3 -m py_compile tb2/*.py`
- `curl -sS http://127.0.0.1:3190/`
- `ss -ltnp`
- `rg`

若需要更進一步互動驗證，可補：

- 真實瀏覽器互動檢查
- 截圖比對
- 手動 keyboard flow 檢查

目前階段不需要額外第三方平台或雲端審查工具；本地 GUI、狀態端點與程式碼審查已足夠支撐前 3 輪。

## 三輪開發節奏

### Round 1：資訊架構與術語澄清

目標：

- 建立工作流導向分頁。
- 建立全域 session summary strip。
- 收斂 `launch plan / live runtime / review / inspect` 的命名。
- 讓拓樸圖從靜態示意變成可操作導航。

驗收：

- 使用者不需要閱讀原始 JSON 即可理解現在在哪一個工作階段。
- `Workflow / Topology / Review / Inspect` 各自有明確定位。
- 節點、帳本、摘要區有一致的語意。

### Round 2：決策支援與 runtime 脈絡

目標：

- Review 面板從按鈕集合變成決策面板。
- Inspect 面板從 debug dump 變成診斷入口。
- 顯示 `guard / pending / transport / audit / room / bridge` 的摘要。

驗收：

- 使用者能快速知道該 approve、edit、reject 的差異。
- 使用者進入 Inspect 後能先讀摘要，再決定是否展開 raw detail。

### Round 3：外部審查導向修正與最後 polish

目標：

- 以 `audit` 與 `critique` 視角重看整體 GUI。
- 修掉還殘留的互動歧義、a11y 弱點與高壓判讀成本。
- 補上焦點狀態、選取狀態、跨區塊跳轉一致性。

驗收：

- 所有主要節點都有明確可見的互動回饋。
- keyboard flow 不會迷失。
- 沒有明顯的 launch/live 混淆。

## 每輪固定流程

### 1. 評估

每輪開始先做：

- 讀目前 GUI HTML 結構與 `tb2/gui.py`
- 看目前 `git status`
- 確認 GUI 是否在 `127.0.0.1:3190`
- 記錄本輪要解決的 3 到 5 個具體問題

### 2. 開發

原則：

- 一次處理同一類問題，不交錯做太多 unrelated 微調。
- 先改資訊架構與互動，再補文案與細節。
- 優先保留既有操作習慣，避免大幅破壞已存在的控制流程。

### 3. 檢驗

最小檢驗集：

- `python3 -m py_compile tb2/*.py`
- 重新啟動 GUI
- `curl` 檢查新節點、新區塊、新互動鉤子是否已輸出

### 4. 外部審查

這裡的「外部審查」不是指第三方平台，而是刻意改變視角重看：

- 用 `audit` 視角看可用性與技術品質
- 用 `critique` 視角看操作流程與高壓認知負擔
- 用 `harden` 視角看空狀態、drift、disabled 與 fallback

每輪外部審查後，至少列出：

- 1 個高風險誤解點
- 1 個可讀性或資訊層級問題
- 1 個互動一致性問題

### 5. 修正

修正原則：

- 先修誤導使用者的問題，再修純視覺問題。
- 先修 runtime truth 相關問題，再修裝飾層。
- 修正後立刻再次做最小檢驗。

## 五小時連續開發建議節奏

### 第 1 小時

- 完成 Round 1 收尾
- 清理 terminology 與 meta summary
- 補齊跨分頁脈絡

### 第 2 小時

- 深化 Review decision support
- 深化 Inspect health summary
- 修補 runtime drift 的顯示與提示

### 第 3 小時

- 深化 Topology 互動
- 補 spotlight、selected state、keyboard flow
- 補 cross-panel jump consistency

### 第 4 小時

- 跑 audit / critique 視角重審
- 針對真正影響 operator 判讀的問題修正

### 第 5 小時

- 做最後 polish
- 整理變更摘要
- 補文件與驗收紀錄

## 當前優先開發清單

- 完成 Topology spotlight 的互動驗證與 keyboard polish
- 強化 badge / ledger / node 三者的選取一致性
- 把 Inspect 再細分成更明確的 health vs raw detail 層次
- 視需要把 hero 進一步 compact 化
- 最後做一次 `audit` 與 `critique` 視角總檢

## 輸出要求

每完成一輪，至少要留下：

- 本輪處理的問題
- 本輪做的實作
- 本輪檢驗結果
- 外部審查觀察
- 下一輪修正方向
