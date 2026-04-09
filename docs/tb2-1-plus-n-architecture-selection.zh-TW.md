---
description: terminal-bridge-v2 1+n 架構選型建議書，整理多連線技術方案、市場對照、TB2 差異與推薦路線
---

# TB2 `1 + n` 架構選型建議書

## 1. 文件目的

這份文件的目的不是先決定 UI 長什麼樣，而是先回答更關鍵的問題：

- TB2 若要從目前的 `1 + 1 + (1監控)` 模型擴展到 `1 + n`
- 應該採用哪一類技術方案
- 應該向哪些主流產品學習
- 哪些能力值得借鑑，哪些不適合直接照搬

本文件以目前 repo 的實作與已公開文件為基礎，並對照主流商用 / 開源多代理平台的架構特徵，提出正式建議。

## 2. 執行摘要

### 2.1 現況判定

目前 TB2 最準確的描述是：

- 產品操作模型：`1 + 1 + (1監控)`
- runtime 能力：已有多 `room` / 多 `bridge` 雛形
- 產品成熟度：尚未進入穩健可運營的 `1 + n`

### 2.2 核心結論

TB2 若要往 `1 + n` 發展，**最合理的第一階段選型**不是：

- 直接改成全 WebSocket bus
- 直接上 message broker
- 直接做跨主機 remote operator plane
- 直接做 single-host multi-guest fan-out

而是：

1. 保留現有 `HTTP control + SSE room streaming` 為主控制面
2. 引入正式 `workstream` 模型，將現有 `bridge + room + pane pair` 提升成一級物件
3. 先把 `1 + n` 定義為：
   - `1` 個 control plane
   - 管理 `n` 條獨立的 pair-based workstreams
4. 在第二階段補 durability / recovery / fleet-safe targeting
5. 等這些穩定後，再評估是否需要 broker、sandbox isolation、或更重的 remote runtime 分層

### 2.3 推薦選型

**推薦路線：Hybrid control plane + workstream-first runtime**

- Control plane：`HTTP JSON-RPC + SSE`，必要時保留 `WebSocket` 作補充 transport
- Runtime model：`workstream-first`
- State model：`durable checkpoint + recovery contract`
- Governance model：`per-workstream targeting + review + guard + audit`

這條路線最符合 TB2 的既有優勢，也最能降低架構跳躍造成的重工風險。

## 3. TB2 目前的架構特徵

### 3.1 目前強項

- 真 terminal pane control，而不是抽象對話沙盒
- `room`、`bridge`、`intervention`、`operator review` 是一級概念
- CLI、Browser GUI、MCP 都能驅動同一個本地控制面
- 對高信任、本機、human-in-the-loop 協作很直接

### 3.2 目前限制

- live collaboration state 仍主要是 in-memory
- `service restart` 不恢復 active rooms / bridges / pending interventions
- GUI 與操作心智模型仍偏向單線
- 多 bridge 雖可存在，但不等於 fleet-ready
- localhost / loopback 仍是正式安全邊界

### 3.3 擴展時最不能忽略的現有約束

- 一組 pane pair 仍只能掛一個 active bridge
- mutation 類操作目前仍存在 `bridge_id` / `room_id` / 單一 active bridge 自動解析的歷史行為
- 多 bridge 代表多 polling worker，不只是多幾個 registry item

## 4. 多連線技術方案研究

以下把可行方案分成 6 類，從 TB2 實際可用性角度評估。

## 4.1 方案 A：`HTTP control + SSE fan-out + optional WebSocket`

### 做法

- 控制操作走 `HTTP JSON-RPC`
- room / event stream 走 `SSE`
- 視需要再加 `WebSocket` 補雙向同步

### 優點

- 架構最接近 TB2 現況
- operator console 容易做、容易 debug
- SSE 對 room stream 非常自然
- 容易保留 CLI / MCP / Browser 的多入口模式
- 漸進式演化成本最低

### 缺點

- 多 workstream 下，connection management 會變複雜
- 高頻互動同步不如 full WebSocket
- 若沒有正式 workstream model，很容易讓 UI 邏輯分裂

### 適合 TB2 的程度

非常高。這是最合理的第一階段主路線。

## 4.2 方案 B：Full WebSocket multiplex bus

### 做法

- 全部控制與狀態同步都走 WebSocket
- 單連線承載多 workstream 的 command / event / telemetry

### 優點

- 雙向互動能力強
- 可做更即時的 fleet UI
- 適合高頻更新、拖拉、批次控制、presence

### 缺點

- reconnect / session / auth / backpressure 複雜度顯著提高
- 對目前 TB2 來說屬於架構跳躍
- 若 durability 還沒補齊，只會把狀態同步問題放大

### 適合 TB2 的程度

中。可以作為第二階段補強，不適合作為第一步。

## 4.3 方案 C：Durable workflow / thread model

### 做法

- 將每條協作線視為可持久化、可中斷、可恢復的 workflow / thread / run
- human-in-the-loop 不再只是即時 queue，而是正式 runtime checkpoint

### 優點

- 最有利於 `1 + n`
- restart / recovery / audit / interrupt 都能有一致模型
- 對 fleet 管理與長時程任務最穩健

### 缺點

- 要接受更明確的 runtime state machine
- persistence schema 與恢復邏輯會是大工程
- 要重新定義目前 bridge lifecycle

### 適合 TB2 的程度

很高，但應作為 runtime model 的升級，而不是先推翻 control plane。

## 4.4 方案 D：Message broker bus

### 做法

- event、command、review、telemetry 都走 broker
- 例如 Kafka、NATS、Redis Streams 之類的模式

### 優點

- 天然支援多 worker、重試、回放、隔離
- 跨主機 / 多租戶更容易
- fleet / enterprise path 比較完整

### 缺點

- 對 TB2 現在來說過重
- 維運與部署成本高
- 會把本地工具定位拉離原本的 local-first 優勢

### 適合 TB2 的程度

低到中。除非未來產品定位改變，否則不建議第一階段採用。

## 4.5 方案 E：Sandbox runtime RPC

### 做法

- 每個 agent / workstream 都進 sandbox runtime
- control plane 透過 RPC 對 sandbox 下指令

### 優點

- 隔離邊界清楚
- 安全性與可重現性較好
- 更適合低信任工作負載

### 缺點

- 與 TB2 的 terminal-native 路線有張力
- 執行成本與開發成本都高
- 不一定適合本地人機混合控制場景

### 適合 TB2 的程度

中。適合未來做「高風險工作負載隔離層」，不適合取代主路線。

## 4.6 方案 F：Hybrid

### 做法

- Control plane 用 `HTTP + SSE`
- runtime state 用 durable workstream model
- 必要時再以 WebSocket 補高頻同步
- 未來若需要跨主機，再局部引入 broker 或 sandbox

### 優點

- 最符合 TB2 目前的漸進式演化邏輯
- 保留既有優勢
- 不必一次重寫整體系統

### 缺點

- 前期設計一定要清楚分層
- 如果 workstream model 不先做好，hybrid 會退化成拼裝架構

### 適合 TB2 的程度

最高。這是本文件推薦方案。

## 5. 市場調查：主流商用 / 開源類似程式

先說清楚：市場上沒有一個與 TB2 完全同型的產品。最接近的是「多代理協作 + 人工介入 + 可觀測性」這類平台，但多半不是 terminal pane first。

## 5.1 LangGraph Platform / Studio

### 主方案

- thread / run / assistant 模型
- checkpointer / durable execution
- interrupt / human-in-the-loop
- streaming run API / webhook

### 強項

- durability 非常成熟
- human-in-the-loop 與 resume 模型清楚
- 很適合長時程 workflow

### 對 TB2 的啟發

- 應學 durability / interrupt / resume
- 不必照搬整個 graph 抽象

## 5.2 CrewAI / CrewAI AMP

### 主方案

- crews / flows / tasks / processes
- human-in-the-loop feedback
- observability 與商業化平台整合

### 強項

- 流程編排完整
- 商業化敘事與 fleet 管理成熟
- observability 思路值得參考

### 對 TB2 的啟發

- 應學 fleet summary、流程層治理、observability
- 不應直接把 TB2 變成純 workflow builder

## 5.3 Microsoft AutoGen / AutoGen Studio

### 主方案

- multi-agent teams
- `UserProxyAgent`
- local / Docker code execution
- Studio UI

### 強項

- agent team abstraction 彈性高
- human feedback 與 code execution 整合自然

### 對 TB2 的啟發

- 應學 team abstraction
- 不必改成 conversation-first 架構

## 5.4 OpenHands

### 主方案

- REST backend
- sandbox runtime
- Docker / local runtime isolation
- code agent oriented workflow

### 強項

- runtime isolation 清楚
- 安全邊界比 terminal-native 模式更好建立

### 對 TB2 的啟發

- 應學 runtime boundary 與隔離思維
- 不應犧牲 TB2 的 terminal-native 核心優勢

## 6. TB2 與主流方案的差異

## 6.1 TB2 的獨特定位

TB2 不是 LangGraph、CrewAI、AutoGen、OpenHands 的直接替代品。

TB2 的特殊性在於：

- 真實 terminal pane 是核心執行單位
- `room + bridge + intervention + operator review` 是核心產品語義
- Browser GUI、CLI、MCP 三種入口共同指向同一個本地控制面
- human operator 不是附屬角色，而是架構中心之一

## 6.2 TB2 比主流方案更強的地方

- 對本地 terminal 協作的貼合度很高
- operator 控制感比多數 agent framework 更直接
- room stream 與 handoff contract 非常適合 coding / debugging / review loop

## 6.3 TB2 明顯落後的地方

- durability / recovery
- fleet-safe targeting
- 正式 workstream abstraction
- 多線 GUI 縮放能力
- 恢復與審計的一致 runtime model

## 7. 選型比較表

| 方案 | 適合 TB2 近程 | durability | fleet scalability | implementation cost | 評價 |
| --- | --- | --- | --- | --- | --- |
| HTTP + SSE | 高 | 低 | 中 | 低 | 可作 control plane 基線 |
| Full WebSocket | 中 | 低 | 中高 | 中高 | 可作高頻互動補強 |
| Durable workflow model | 高 | 高 | 高 | 高 | 必須導入，但應分階段 |
| Message broker | 低 | 高 | 高 | 很高 | 過早導入風險大 |
| Sandbox runtime RPC | 中 | 中高 | 中 | 高 | 適合作為隔離層，不是主線 |
| Hybrid | 很高 | 高 | 高 | 中高 | 最推薦 |

## 8. 正式建議

## 8.1 推薦架構

### Phase 1 選型

- Control plane：`HTTP JSON-RPC + SSE`
- Runtime object：`workstream`
- Execution unit：`pair-based bridge`
- Recovery model：`checkpoint / snapshot`

### Phase 2 補強

- 視需要在 GUI 補 `WebSocket`
- 引入 per-workstream scheduler / fairness / backpressure
- 完成 fleet-safe targeting

### Phase 3 再評估

- 是否需要 broker
- 是否需要 sandbox runtime
- 是否值得往 single-host multi-guest 演進

## 8.2 為什麼不是直接改成 single-host multi-guest

原因很簡單：

- 現在 bridge 是 `pane_a + pane_b` binary pair model
- 文件、GUI、review queue、operator 心智模型都以單 pair 為中心
- 如果直接跳到 single-host multi-guest，會一次重寫：
  - routing
  - targeting
  - review
  - UI
  - recovery

這個跨度過大，風險不合理。

## 8.3 為什麼不是先上 broker

因為 TB2 目前的主要瓶頸不是「缺 broker」，而是：

- 缺正式 workstream model
- 缺 durability
- 缺 fleet-safe targeting
- 缺 GUI fleet information architecture

這些沒補之前，上 broker 只會把系統變得更重。

## 9. 推薦的實作順序

1. 定義 `workstream` 與 fleet-safe targeting
2. 調整 `status()` 成 workstream-first payload
3. 補 snapshot / checkpoint / recovery contract
4. GUI 改成 fleet overview + selected workstream detail
5. 補 fairness / backpressure / health model
6. 最後才評估 WebSocket 強化、broker、sandbox

## 10. 決策建議

如果要做正式架構決策，我的建議是：

> TB2 的 `1 + n` 第一階段，應採用 **Hybrid control plane + workstream-first runtime**。

也就是：

- **不要改變 TB2 是本地 terminal-native control plane 的核心定位**
- **先把 bridge 升級成 workstream**
- **先把 runtime 與恢復模型補穩**
- **再把 GUI 與 MCP 升級成 fleet 管理面**

這樣做，才能同時保留：

- TB2 現有的 terminal-native 優勢
- human operator 的直接控制能力
- 未來向 `1 + n` 穩健擴展的可能

## 11. 參考資料

- LangGraph human-in-the-loop  
  https://docs.langchain.com/oss/python/langgraph/human-in-the-loop
- LangGraph durable execution  
  https://docs.langchain.com/oss/javascript/langgraph/durable-execution
- LangGraph webhook / cloud run patterns  
  https://langchain-ai.github.io/langgraphjs/cloud/how-tos/webhooks
- CrewAI documentation  
  https://docs.crewai.com/en
- CrewAI human feedback in flows  
  https://docs.crewai.com/en/learn/human-feedback-in-flows
- CrewAI human-in-the-loop  
  https://docs.crewai.com/en/learn/human-in-the-loop
- CrewAI observability  
  https://docs.crewai.com/en/observability
- AutoGen human-in-the-loop  
  https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/human-in-the-loop.html
- AutoGen teams  
  https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/teams.html
- AutoGen code executors  
  https://microsoft.github.io/autogen/stable/user-guide/core-user-guide/components/command-line-code-executors.html
- AutoGen Studio  
  https://microsoft.github.io/autogen/dev/user-guide/autogenstudio-user-guide/index.html
- OpenHands runtime architecture  
  https://docs.openhands.dev/usage/architecture/runtime
- OpenHands Docker runtime  
  https://docs.openhands.dev/usage/runtimes/docker
