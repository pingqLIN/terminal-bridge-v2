---
description: 2026-04-22 依據第一輪外部審查收斂出的 terminal-bridge-v2 窄化主線開發書
---

# terminal-bridge-v2 開發書

日期：2026-04-22

## 目的

這份開發書不是一般 roadmap。

它的用途是把第一輪外部審查轉成清楚的 build / stop / defer 決策，讓後續開發不再同時追 3 條互相拉扯的方向。

這份文件服務的不是「要不要做更多」，而是：

- 哪些東西現在還值得做
- 哪些東西必須凍結
- 接下來 1 到 3 個月如何證明 TB2 的窄化主線有成立價值

前一份審查摘要見：

- [external-review-round1-2026-04-22.zh-TW.md](./external-review-round1-2026-04-22.zh-TW.md)

## 主線定義

從這一輪開始，TB2 的主線明確定義為：

> local-first、high-trust、operator-grade 的 terminal workflow governance layer

具體來說，TB2 應服務的是：

- 真實 terminal 中的 Host / Guest / Human 協作
- 需要 review / approve / interrupt 的高信任工作流
- 需要 audit、reconciliation、fleet health、policy provenance 的 operator

TB2 不應再服務的敘事：

- 通用 AI remote-control plane
- Codex 原生能力替代品
- 廣義 multi-agent terminal platform
- 為每個 client 各做一個 compatibility facade

## 第一原則

後續開發全部遵守以下原則：

1. 先收斂治理與可觀測性，再談新 surface
2. 先定義 authoritative contract，再談自動套用
3. 先降低維護面積，再談擴張 adoption
4. 先誠實說明 platform reality，再談跨平台支援

## 停止清單

以下項目從這一輪開始視為停止或凍結：

### 1. 停止新增 surface

- 不新增新的 client-specific surface
- 不新增新的 compatibility adapter
- 不新增新的 GUI product preset 敘事

### 2. 停止回到 remote-control 敘事

- 不再把 TB2 描述成通用 remote-control plane
- 不再把 sidepanel compatibility 當成產品主線
- 不再投資任何會重新與 Codex 原生能力正面重疊的互動面

### 3. 停止在治理未成熟前擴張自動化

- 不做 runtime auto-apply
- 不做 rollback productization
- 不做第二套與 workstream policy 平行競爭的 policy system

## 保留清單

以下項目是這一輪明確保留、且值得繼續深化的核心：

### 1. 主骨架

- Room
- Bridge
- Workstream

這是 TB2 最小但真實的協作模型，不應被削弱。

### 2. 治理與可觀測性

- governance layering
- provenance
- audit event contract
- review decision trace
- fleet health
- reconciliation

### 3. 平台真實性

- Windows-native operator path
- WSL tmux collaboration path
- doctor / capability report / support posture

## 接下來 1 到 3 個月的開發目標

本階段目標不是擴功能，而是回答一個更基本的問題：

> TB2 是否能成為一個可被外部採信的 operator governance tool？

為了回答這個問題，後續只做 4 大批次。

## Batch A: Authoritative Governance 基礎化

### 目標

把目前 explain-only governance resolver 推進成真正可承接 runtime 決策的單一真相來源。

### 必做

- 定義 advisory keys / enforceable keys / mutable exception keys
- 明確定義 governance 與既有 workstream policy 的邊界
- 讓至少一小部分 runtime state 由 governance resolution 正式投影
- 為 governance decision 建立可追溯記錄

### 驗收

- 文件可明確回答哪些 key 只是說明、哪些 key 會影響行為
- `status` 可看出治理來源與例外狀態
- audit 可記錄治理決策的來源與 override

## Batch B: Audit Decision Chain

### 目標

讓重要操作不只留下 event，還能回答「為什麼這個決策會發生」。

### 必做

- 定義 decision-oriented audit taxonomy
- 補 governance-to-audit provenance
- 補 operator override / waiver / exception 的可追溯模型
- 補 drift detection 最小契約

### 驗收

- 至少可針對 review / guard / policy override 做 decision trace
- recent audit 不只回事件，還能定位 policy 來源

## Batch C: Fleet Compliance View

### 目標

把治理能力從單點 resolver 提升到多 workstream 的 compliance 視角。

### 必做

- 為 fleet 增加 policy compliance summary
- 暴露例外、漂移、blocked、manual takeover 的治理視圖
- 讓 operator 能看到哪些 workstream 偏離預期治理

### 驗收

- `status.fleet` 或獨立 governance surface 可看出 compliance state
- GUI 或 MCP 至少有一個 read-only fleet governance 視圖

## Batch D: 模組邊界收斂

### 目標

把產品定位落進架構邊界，不再讓 `server.py` 繼續吸收所有新功能。

### 必做

- 把 sidepanel compatibility 明確降級為 adapter
- 將 governance、status aggregation、compat adapter 從 `server.py` 再往外拆
- 為 GUI 訂出停止擴張的結構邊界

### 驗收

- `server.py` 不再是所有功能的唯一落點
- sidepanel compatibility 不再被視為主線能力
- GUI 的核心任務被壓回 operator console，而不是持續 productization

## 平台策略

後續平台敘事採以下正式描述：

- `WSL tmux` 是主要協作 runtime
- `native Windows process` 是主要低摩擦 operator path
- `tmux`、`process`、`pipe` 是不同 operating model，不是等價 fallback
- `macOS` 在沒有持續真機驗證前，僅能描述為 policy-compatible

## 文件策略

後續文件不再用「功能很多」證明產品方向。

文件只應反覆強調以下一句核心故事：

> 我已經在 terminal 裡跑多 agent，但我缺一個本地的人類監督與可追溯控制層。

若某份文件、某個頁面、某個 preset 無法回到這句核心故事，就應考慮刪除、降級或移出主線。

## 本階段不做

以下項目明確列為本階段不做：

- 新的 GUI preset 擴張
- 新的 mission-control 包裝
- 新的 compatibility surface
- 真正的 public / internet-facing support 敘事
- 未經 authoritative governance 定義就直接做 runtime auto-apply

## 階段完成標準

這一輪主線若要算完成，至少要交出一份外部可採信的最小證據包：

- 明確 support matrix
- 明確 non-goals
- 明確 restore / degraded semantics
- 明確 auth boundary
- 明確 advisory vs mutable governance boundary
- 明確 operator decision trace

如果做不到這一組證據包，就不應再擴張功能面。

## 最後結論

這一輪外部審查沒有否定 TB2。

真正被否定的是這幾種舊方向：

- 把 TB2 做成通用 AI 控制台
- 把 surface 擴張當成產品進展
- 把 explain-only governance 誤當成 moat

後續唯一合理的路，是把 TB2 壓回一個更小、但更硬的產品：

`operator-grade governance layer for terminal-native multi-agent workflows`
