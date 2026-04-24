---
description: 2026-04-22 第一輪 6 位外部 reviewer 對 terminal-bridge-v2 概念、方向與開發必要性的批判審查摘要
---

# terminal-bridge-v2 第一輪外部審查報告

日期：2026-04-22

## 目的

這份文件整理第一輪 6 位外部 reviewer 的批判結果。

本輪只審查 3 件事：

- 專案概念是否成立
- 現在的開發方向是否合理
- 這個專案是否還值得繼續投入

本文件不是 PR review，也不是 bug audit。
重點是方向判斷、必要性判斷與 stop / continue 決策。

## 審查範圍

本輪 reviewer 分別從下列角度審查：

- 產品策略 / 市場定位
- 技術架構 / 可維護性
- 平台 / runtime / cross-OS reality
- governance / audit / operator-control-plane 價值
- 使用者工作流 / adoption / operator experience
- 投資審查 / 是否值得繼續開發

主要依據材料包括：

- [README.md](../README.md)
- [README.zh-TW.md](../README.zh-TW.md)
- [docs/roadmap.zh-TW.md](./roadmap.zh-TW.md)
- [docs/development-execution-plan.zh-TW.md](./development-execution-plan.zh-TW.md)
- [docs/project-status-report-2026-04-10.zh-TW.md](./project-status-report-2026-04-10.zh-TW.md)
- [docs/governance-layering.md](./governance-layering.md)
- [docs/platform-behavior.md](./platform-behavior.md)
- [tb2/server.py](../tb2/server.py)
- [tb2/gui.py](../tb2/gui.py)
- [tb2/governance.py](../tb2/governance.py)
- [tb2/backend.py](../tb2/backend.py)
- [tb2/osutils.py](../tb2/osutils.py)
- [tb2/support.py](../tb2/support.py)

## 總結判斷

本輪 6 位 reviewer 的結論高度一致：

- 專案不該停止
- 但不能再擴張
- 只能以窄化版主線繼續

本輪最接近共識的總結句是：

> TB2 值得繼續，但只值得做成 local-first、high-trust、operator-grade 的 terminal workflow governance layer。

## 核心結論

### 1. 專案不是沒有價值，但價值面很窄

reviewer 普遍認為，TB2 真正有價值的使用者不是一般 AI 開發者，也不是一般 MCP 使用者，而是：

- 已經在 terminal 中跑多 agent 協作的人
- 需要 human review / approve / interrupt 的人
- 在意 audit、incident review、operator oversight 的人

這代表 TB2 的採用對象是高紀律、高信任、低人數的 operator 群體，不是廣義市場。

### 2. 如果不再收斂，專案會重新滑回「AI 控制台」敘事

雖然目前文件已正式收斂，不再把 TB2 講成 Codex 原生 remote-control 替代品，但 reviewer 一致認為 repo 仍殘留很多會把產品拖回舊方向的結構：

- sidepanel compatibility
- browser GUI 的 productized preset 敘事
- `Mission Control` 類型的操作面包裝
- 過多 client / surface 的存在感

也就是說，方向收斂目前大多還停留在文件，不完全是程式與模組邊界。

### 3. 治理層目前還不是 moat

reviewer 對這一點的批評很直接：

- `governance` 目前主要是 resolver
- resolver 目前主要是 read-only explain layer
- explain layer 很容易被複製

目前的 `matched_layers`、`effective_config`、`provenance` 有價值，但仍屬於說明層，不是 authoritative control layer。

若要變成真正產品方向，後續必須補上：

- authoritative governance source
- policy decision chain
- exception / waiver model
- drift detection
- fleet compliance view

### 4. 平台策略成立，但敘事仍需更誠實

reviewer 普遍認同 Windows / WSL 雙軌策略有實務必要，但不接受「雙主線等價成熟」的暗示。

更準確的描述應該是：

- `Windows-native operator path`
- `WSL tmux collaboration path`

也就是：

- Windows 原生主要是低摩擦啟動與日常操作層
- WSL `tmux` 才是主要協作 runtime

同時 reviewer 也認為 `tmux`、`process`、`pipe` 不是同等替代品，而是不同 operating model，不應過度包裝成「無痛 fallback」。

### 5. 架構邊界還沒有跟著產品定位一起收斂

最嚴重的技術警訊不是單一 bug，而是 `tb2/server.py` 的聚合程度。

reviewer 認為目前 `server.py` 同時吸收了：

- server / MCP / HTTP
- bridge runtime
- workstream state
- audit / recovery / security aggregation
- governance snapshot
- sidepanel compatibility adapter

這表示新需求仍會自然往同一個單體疊加。
若不先收斂模組邊界，產品方向再怎麼修正，技術上仍會往「什麼都塞進 control plane」演化。

## 具體問題清單

### P0

- 專案存在理由仍不夠硬，對外更像能力集合，不像非做不可的產品
- 與 Codex 原生能力的重疊風險仍高，尤其是操作面與 compatibility surface
- governance layer 目前只是 explain-only resolver，還不是產品護城河
- `server.py` 已是 god-module，顯示概念邊界沒有被架構強制

### P1

- Windows / WSL 雙軌敘事仍稍嫌過度樂觀
- cross-platform 支援的外部理解風險大於實際驗證範圍
- adoption 面其實很窄，但 README / GUI 仍帶有較大的「teams / platform」口吻

### P2

- GUI preset 敘事過早 productization
- maintainer-specific 文案仍殘留在 GUI 與 side-route 文件
- explain-only governance 若繼續擴張文件與 surface，會稀釋真正值得投資的治理骨幹

## 本輪 reviewer 認可的主線

下列方向是本輪 reviewer 普遍認可、且認為仍值得投資的部分：

- `Room / Bridge / Workstream` 主骨架
- `audit / provenance / replayable review`
- `fleet health / reconciliation / remediation`
- `Windows operator path + WSL tmux collaboration path`
- `MCP interoperability`，但只作為接入面

## 本輪 reviewer 建議凍結或降級的部分

- sidepanel compatibility 主線化
- 任何新的 client-specific compatibility surface
- GUI preset / mission-control productization 擴張
- 在治理尚未成為 authoritative source 前就做 runtime auto-apply / rollback
- 任何重新靠近通用 remote-control plane 的敘事

## 決議建議

基於本輪審查，最務實的決議應是：

1. 接受專案可繼續，但只以窄化版主線繼續
2. 明確停止所有會重新擴張 surface 的方向
3. 接下來 1 到 3 個月只做去風險化工作，不做平台式擴張

## 後續文件

本輪審查之後的實作決議與具體開發批次，請看：

- [development-book-round1-2026-04-22.zh-TW.md](./development-book-round1-2026-04-22.zh-TW.md)
