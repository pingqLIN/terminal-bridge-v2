# GUI 開發輪次紀錄

## Round 1

### 評估

- 主要問題是 GUI 雖然已分頁，但仍偏功能集合，缺少工作狀態導航。
- `launch settings` 與 `live runtime` 的區別不夠清楚。
- `Review` 與 `Inspect` 都偏靜態資訊區，而不是操作員決策面板。

### 開發

- 建立 `Workflow / Topology / Review / Inspect` 分頁狀態摘要。
- 新增全域 `workspace strip`，集中顯示 preset、session、panes、bridge、routing、audit。
- 把 Topology 右側改成 `Launch Plan` 與 `Live Runtime` 對照。

### 檢驗

- `python3 -m py_compile tb2/*.py`
- 重啟 GUI 到 `127.0.0.1:3190`
- 用 `curl` 檢查 `workspace-strip`、`relation-compare` 已存在

### 外部審查

- 從 `clarify` 視角看，主要歧義來自術語與 staged/live 混用。
- 從 `arrange` 視角看，跨分頁脈絡斷裂是最主要問題。

### 修正

- 收斂 terminology
- 補跨頁 session context
- 補 launch/live 對照

## Round 2

### 評估

- `Review` 雖有 approve / reject / edit，但缺少決策提示。
- `Inspect` 雖有 status / diagnostics，但沒有摘要層。

### 開發

- 新增 `Review Checklist`
- 新增 `review-strip` 與 `review-note`
- 新增 `inspect-strip`
- 讓 `pending-edit` 即時影響決策提示

### 檢驗

- `python3 -m py_compile tb2/*.py`
- 用 `curl` 檢查 `review-strip`、`inspect-strip`、`review-note` 已存在

### 外部審查

- 從 `critique` 視角看，Review 必須像 decision console，不只是 queue。
- 從 `harden` 視角看，空狀態與 selected state 要有更明確 fallback。

### 修正

- 補 selected pending 的判斷文案
- 補 inspect health 摘要層

## Round 3

### 評估

- Topology 節點已可點擊，但 node、badge、ledger 三種入口缺少一致焦點。
- 使用者缺少一個中心區域理解「目前我選中的元件或連線代表什麼」。

### 開發

- 新增 `Topology Spotlight`
- 節點、ledger、badge 共用同一個 relation focus state
- 新增 `Jump to Matched Control`
- 補 selected state 樣式與 spotlight facts

### 檢驗

- `python3 -m py_compile tb2/*.py`
- 實際重啟 GUI
- 用 `curl` 檢查 `relation-spotlight`、`relation-spotlight-jump`、`badge.dataset.badgeKey` 已存在

### 外部審查

- 從 `polish` 視角看，拓樸現在更接近操作介面，而不是示意圖。
- 從 `clarify` 視角看，spotlight 有效降低了節點與帳本之間的判讀跳躍。

### 修正

- badge 也接入 spotlight
- preset 切換時重置 relation focus，避免殘留舊焦點

## 目前狀態

- GUI 正在 `http://127.0.0.1:3190/`
- 已完成 3 輪閉環
- 尚未 commit

## 下一步建議

- 補 Inspect 內部更細的 `health / audit / raw detail` 結構
- 視需要把 hero 再 compact 化
- 最後跑一次完整 `audit` 與 `critique` 視角總檢
