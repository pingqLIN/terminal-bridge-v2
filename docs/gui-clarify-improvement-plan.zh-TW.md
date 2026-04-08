# GUI 釐清與流程改善計畫

## 使用技能
- `frontend-design`
- `clarify`
- `arrange`
- `polish`
- `harden`

本文件先完成評估，再整理出後續開發計畫。設計 context 已先寫入 [.impeccable.md](/home/miles/dev2/projects/terminal-bridge-v2/.impeccable.md)，作為後續 GUI 改版的基線。

## 評估前提

根據 [README.md](/home/miles/dev2/projects/terminal-bridge-v2/README.md)、[docs/control-console.md](/home/miles/dev2/projects/terminal-bridge-v2/docs/control-console.md)、[docs/use-cases.md](/home/miles/dev2/projects/terminal-bridge-v2/docs/use-cases.md)、[docs/role-guides.md](/home/miles/dev2/projects/terminal-bridge-v2/docs/role-guides.md) 可明確推得：

- 主要使用者是技術型 Human Operator、Host AI 監督者、MCP Integrator。
- 主要場景是本機 terminal-native AI 協作、人工審核、診斷與 incident recovery。
- 介面應該是 operator-grade、task-first、在壓力情境下仍然清楚。

這代表目前 GUI 不需要朝大眾產品或行銷頁風格優化，而是要朝：

- 降低操作歧義
- 降低高壓情境下的判讀成本
- 明確區分 launch config 與 live runtime
- 讓操作員快速知道下一步該做什麼

## 目前 GUI 可加強的重點

### 1. 導航已經分頁化，但還缺少「工作狀態導航」

現況：
- 已經有 `Workflow / Topology / Review / Inspect` 分頁。
- 但分頁本身沒有顯示目前是否有 pending、是否有 active bridge、是否有 audit、是否有 diagnostics attention。

問題：
- 使用者切頁前無法快速知道哪一頁目前最值得看。
- 在 review 或 incident 情境下，分頁只是分類，不是工作導引。

建議：
- 在分頁列加上動態 badge。
- `Review` 顯示 pending count。
- `Topology` 顯示 active links / active nodes。
- `Inspect` 顯示 audit on/off 與 guard/attention 狀態。
- `Workflow` 顯示 session/bridge/room 是否 ready。

優先級：`P1`

### 2. 名詞仍有交錯，對操作員的心智模型不夠穩定

現況：
- 同一個概念會在不同區塊看到 `Approval Gate`、`Review Queue`、`intervention`、`pending`、`handoff`。
- `Inspect` 分頁內又同時有 `Status` 與 `Diagnostics`，語意邊界不夠清楚。
- `Host / Guest`、`pane A / pane B`、`Host pane target / Guest pane target` 都存在。

問題：
- 操作員會知道這些技術名詞，但在高壓情境下，混用會讓判斷速度變慢。
- GUI 應該讓詞彙穩定，而不是讓使用者自己做語意映射。

建議：
- 建立 GUI canonical terminology 表。
- 對外顯示固定用：
  - `Review`
  - `Pending handoffs`
  - `Host pane`
  - `Guest pane`
  - `Launch settings`
  - `Live runtime`
- `intervention` 保留給進階文字或 API 映射，不作為主視覺用語。

優先級：`P1`

### 3. 關聯視圖已可點擊，但缺少明確的可操作提示

現況：
- 節點已可點擊並會跳到對應控制區。
- 但圖面上沒有清楚提示「節點可點擊」。

問題：
- 新使用者不一定會發現這是可操作拓樸，而不是靜態示意圖。

建議：
- 在 Relation View 標題下加一行微文案，例如：
  - `Click a node to jump to the matching control area.`
  - `點擊節點可直接跳到對應控制區。`
- 在 hover/focus 狀態增加更明確的 affordance。
- 在 ledger 項目也支援反向點擊聚焦。

優先級：`P1`

### 4. Launch Mirror 與 Live Runtime 的差異雖然已存在，但還不夠直觀

現況：
- Relation View 已有 note 說明 active bridge 與 launch settings 不一致時要重啟 bridge。
- 但這個概念仍然散落在 note、facts、diagram 與 main launch card 之間。

問題：
- 使用者容易以為改了右側 mirror control 就等於 runtime 已變更。
- 這是最容易造成誤判的地方。

建議：
- 在 Launch card 與 Relation View 同步加上明確狀態條：
  - `Editing launch settings`
  - `Active bridge still running previous settings`
- 把「launch config」與「live runtime」做視覺分層。
- 需要時顯示 `Restart bridge to apply` 的單一 CTA，而不是只放說明文字。

優先級：`P0`

### 5. Workflow 分頁仍偏向「控制集合」，不是「任務流程」

現況：
- Launch 與 Live 已經在同一分頁。
- 但流程提示仍偏弱，尤其對第一次進入 GUI 的使用者來說。

問題：
- 使用者看到很多控制，但不知道現在該先做哪一步。
- `Quick Pairing`、`Approval Gate`、`Mission Control` 的差異主要靠 preset 文案理解，缺少更直接的流程線索。

建議：
- 在 Workflow 分頁加入目前步驟狀態條：
  - `1. Init session`
  - `2. Start bridge`
  - `3. Watch room`
  - `4. Review if needed`
- 每一步用 ready / pending / blocked 狀態呈現。
- 根據 preset 切換主要 CTA 順序與輔助文案。

優先級：`P1`

### 6. Review 分頁缺少「風險與判斷」輔助資訊

現況：
- 可以 refresh、approve、reject、edit。
- 但 review decision 的判斷輔助仍偏少。

問題：
- 使用者知道如何按按鈕，但不一定知道什麼時候應該 approve、reject、edit、interrupt。
- 在 shell-risk 或 code mutation 情境下，缺乏 decision support。

建議：
- 在 selected pending detail 補上更清楚的 decision scaffold：
  - target pane
  - original text
  - edited text
  - why this reached review
  - recommended operator checks
- 在 Review 分頁加上簡短 checklist。

優先級：`P1`

### 7. Inspect 分頁目前把 Status 與 Diagnostics 並排，但層次仍太平

現況：
- `Status` 與 `Diagnostics` 都存在。
- 但 `raw JSON`、`activity log`、`capture`、`interrupt`、`audit` 都是同層級可見。

問題：
- 對 incident recovery 很完整，但對日常檢查過於密集。
- 容易讓 Inspect 看起來像 debug dump，而不是 operator tool。

建議：
- Inspect 分頁內部再拆成子段落：
  - `Health`
  - `Audit`
  - `Capture`
  - `Interrupt`
  - `Raw status`
- 預設先顯示 health summary 與 audit summary。
- `raw JSON` 預設折疊。

優先級：`P2`

### 8. 空狀態與過渡狀態仍偏技術描述，缺少操作導引

現況：
- 目前常見字樣有 `not ready`、`not attached`、`disabled`、`Expand`。

問題：
- 這些字可以描述狀態，但不能幫助使用者做下一步。
- `Expand` 類字樣在 disclosure meta 裡資訊價值很低。

建議：
- 把空狀態改成動作導向：
  - `Init Session to create Host and Guest panes`
  - `Start a bridge to attach a live room`
  - `No pending handoffs right now`
- 把 disclosure meta 改成狀態性摘要，而不是 generic wording。

優先級：`P1`

### 9. Hero 區對新使用者仍有幫助，但對回訪操作員略顯冗長

現況：
- Hero 保留 preset grid、語言、layout、摘要說明。

問題：
- 對第一次進入很好，但對長時間值班的 operator 來說，hero 的存在感仍偏高。

建議：
- 保留 hero，但在 workspace 模式下降低高度。
- 已進入工作流後，預設收合 preset grid 或改成 compact mode。
- 讓操作員把 hero 切到 `compact briefing`。

優先級：`P2`

### 10. 程序層面仍缺少「跨分頁一致的 session summary」

現況：
- metrics 在 Workflow 分頁。
- Topology 有 runtime facts。
- Inspect 有 raw status。

問題：
- 使用者切頁後，容易失去同一份 session context。

建議：
- 在全域區域加入 compact session strip：
  - session
  - bridge
  - room
  - profile
  - pending
  - audit
- 每頁都可看到同一份精簡上下文。

優先級：`P1`

## 建議的開發方向

### Phase 1：Clarify 與 terminology 收斂

目標：
- 先把最容易造成誤解的地方修乾淨。

工作：
- 建立 canonical terminology 表。
- 統一 `review / pending handoff / launch settings / live runtime / inspect` 等文案。
- 將 generic meta 文案改成狀態摘要。
- 補上 `node is clickable` 的明示提示。

涉及 skill：
- `clarify`
- `polish`

主要檔案：
- [tb2/gui.py](/home/miles/dev2/projects/terminal-bridge-v2/tb2/gui.py)
- [docs/control-console.md](/home/miles/dev2/projects/terminal-bridge-v2/docs/control-console.md)

### Phase 2：Workflow 導引與分頁狀態導航

目標：
- 讓分頁不只是分類，而是能指引工作。

工作：
- 在分頁列加入 live badges 與 counts。
- 補 workflow step strip。
- 加入全域 compact session summary。
- 調整 hero 讓 workspace 狀態更精簡。

涉及 skill：
- `arrange`
- `clarify`
- `onboard`

主要檔案：
- [tb2/gui.py](/home/miles/dev2/projects/terminal-bridge-v2/tb2/gui.py)

### Phase 3：Review 與 Inspect 的 operator decision support

目標：
- 在高風險與高壓情境下，加快正確判斷。

工作：
- 在 Review panel 增加 operator checklist。
- 顯示 handoff 為何進 review。
- Inspect 分頁拆成 `Health / Audit / Capture / Interrupt / Raw`。
- 讓 raw status 預設折疊。

涉及 skill：
- `clarify`
- `harden`
- `arrange`

主要檔案：
- [tb2/gui.py](/home/miles/dev2/projects/terminal-bridge-v2/tb2/gui.py)
- 相關測試檔案

### Phase 4：Topology 視覺與程序整合深化

目標：
- 讓 Relation View 成為真正的操作樞紐，而不是進階輔助圖。

工作：
- ledger 與 nodes 雙向可點擊。
- 節點 hover 顯示簡短 runtime summary。
- 加入 launch vs runtime 差異的明確 CTA。
- 在 topology 內顯示 why-active / why-blocked / why-muted。

涉及 skill：
- `arrange`
- `polish`
- `clarify`

主要檔案：
- [tb2/gui.py](/home/miles/dev2/projects/terminal-bridge-v2/tb2/gui.py)

## 建議的實作順序

1. 先做 terminology 與 microcopy 收斂。
2. 再做分頁 badge 與 session summary。
3. 接著補 Review / Inspect 的 decision support。
4. 最後深化 topology 互動與 polish。

## 驗收標準

完成後，GUI 應該能達成：

- 新 operator 進入 `Workflow` 後，10 秒內知道下一步要做什麼。
- 使用者在 `Topology` 一眼看懂哪些元件是 launch config，哪些是 live runtime。
- `Review` 分頁在 pending 出現時，不需要依賴 raw status 就能做大部分決策。
- `Inspect` 分頁對 incident recovery 有幫助，但平時不會造成過度資訊負擔。
- 中英雙語切換後，不會出現術語漂移或相同概念多種說法。
