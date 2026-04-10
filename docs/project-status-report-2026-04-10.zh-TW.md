---
description: 2026-04-10 terminal-bridge-v2 專案現況審核、git 分支評估、進度判讀與下一階段開發計畫
---

# terminal-bridge-v2 專案現況報告

日期：2026-04-10

## 狀態更新

2026-04-10 同日後續開發已完成 `Phase 1` 到 `Phase 3` 的主體交付。

- `Phase 1`：server 已引入正式 `workstream` model、`workstream_id` targeting 與 `status().workstreams`
- `Phase 2`：service state 已可持久化 workstream snapshot，並支援 service-managed restart restore / degraded contract
- `Phase 3`：GUI fleet sidebar 已接上真實 workstream data，selected scope 會驅動 review/status/audit；同時 runtime/workstream 型別已從 server 單檔抽出到獨立模組
- `Phase 4`：security posture 已落成 machine-readable contract，並加入 non-loopback `--allow-remote` guardrail
- `Phase 5`：packaging metadata、support tier、getting-started / FAQ / security posture 文件已收斂到目前實際完成度
- `Phase 6`：per-workstream health / alert / escalation 已正式進入 runtime、fleet summary、GUI 與 audit scope
- `Phase 7`：per-workstream action layer 已落地，包含 `review_mode`、policy snapshot、pause / resume review 與 policy mutation tools

本文件保留的是當時的審核基線與原始計畫。交付摘要請改看：

- [phase-1-3-delivery-report-2026-04-10.zh-TW.md](./phase-1-3-delivery-report-2026-04-10.zh-TW.md)
- [phase-4-5-delivery-report-2026-04-10.zh-TW.md](./phase-4-5-delivery-report-2026-04-10.zh-TW.md)
- [phase-6-delivery-report-2026-04-10.zh-TW.md](./phase-6-delivery-report-2026-04-10.zh-TW.md)
- [phase-7-delivery-report-2026-04-10.zh-TW.md](./phase-7-delivery-report-2026-04-10.zh-TW.md)

## 1. 專案狀態快照

### 1.1 專案目標

`terminal-bridge-v2` 的當前產品目標已相當明確：

- 提供一個 local-first 的 terminal orchestration control plane
- 讓 Host AI、Guest AI、Human operator 可在真實 terminal 中協作
- 同時暴露 CLI、browser GUI、MCP 三種操作面

這一點可以從 [README.md](../README.md)、[tb2/server.py](../tb2/server.py)、[tb2/gui.py](../tb2/gui.py) 的對齊程度確認，不再只是概念型專案。

### 1.2 Git 與分支現況

2026-04-10 實際檢查結果：

- 目前所在分支是 `main`
- `HEAD` 與 `origin/main` 對齊，沒有本地未推送 commit
- 本地 branch 目前只有 `main`
- 初始審核時 worktree 曾因根目錄 `.codex` 顯示未追蹤，現已納入 ignore 並清理回乾淨狀態
- remote 目前只剩 `origin/main`

判讀：

- 就「本地整理到只剩 main」來看，現在其實已經成立
- 就「整個 remote repo 只剩 main」來看，這不是單純本地整理，而是遠端分支治理動作
- 在有未追蹤本地 artifact 的情況下，不適合直接做 branch deletion、history rewrite、或 commit 壓縮操作

後續治理補充：

- 已將 repo 根目錄 `.codex` 加入 ignore，避免持續污染 worktree
- 已確認 `origin/copilot/fix-human-intervention` 完全 merged，並已刪除
- 已將過時的 README 分支與 3 條 GitHub Actions dependabot branches 清理完成
- 原本保留、帶有 `acpx` 方向內容的 `origin/copilot/update-documentation-for-project`，已依決策正式刪除

### 1.3 測試與驗證現況

本次實際驗證分兩輪：

- sandbox 內執行 `pytest -q`：
  - 334 passed
  - 1 failed
  - 10 errors
  - 失敗原因是 sandbox 拒絕 `tmux` 與 `socket()` 權限，不是產品回歸
- sandbox 外重新執行 `pytest -q`：
  - `363 passed in 14.03s`

結論：

- 目前主線在真實本機環境下可通過完整測試
- 測試數量已從舊文件中的 `285`、`310` 進一步成長到 `363`
- 這代表專案仍在持續增強 regression coverage，不是停留在文件宣稱階段

### 1.4 稽核信心

- 產品定位判讀：高
- 核心功能完成度判讀：高
- 1+n 架構成熟度判讀：中高
- release readiness 判讀：中
- 跨平台成熟度判讀：中低

## 2. 進度評估

### 2.1 已完成且可視為穩定主幹的能力

以下能力已不屬於草稿，而是已有程式、測試與文件三方對齊：

- CLI / MCP / GUI 三種控制面並存
- room / bridge registry 與基本多實例管理
- machine-readable source metadata
- intervention queue 與 approve / reject / edit 流程
- auto-forward guard、rate limit、circuit breaker
- persisted audit trail、rotation、`full|mask|drop` redaction policy
- `audit_recent`、`status.runtime`、service restart contract
- localhost-oriented request hardening 與 HTTP/WebSocket 基本邊界防護
- GUI 上的 preset-driven workflow、review、inspect、topology、audit 面板

從目前程式面積看，專案已經不是原型骨架：

- 核心程式約 10,879 行 Python
- 測試約 4,800 行
- [tb2/gui.py](../tb2/gui.py) 單檔已達 5,337 行
- [tb2/server.py](../tb2/server.py) 單檔已達 1,766 行

這表示產品已進入「功能成立，但需要架構再整形」階段。

### 2.2 部分完成、但尚未產品化完成的區塊

#### A. `1 + n` / fleet model

現況：

- GUI 已經開始出現 `workstream fleet` 與 `selected workstream` 的視覺模型
- runtime `status()` 雖仍保留 `rooms + bridges + bridge_details` 相容層，但 `workstreams` 已成為正式治理主語
- `workstream_id`、fleet-safe mutation targeting、per-workstream policy、`review_mode` 都已成為 server runtime contract 的一部分

判讀：

- `1 + n` 已經跨過純規劃期，進入可操作的 runtime / governance 階段
- 但目前仍缺 action enforcement、dependency rules 與 stale remediation，因此還不能算完整 fleet architecture

#### B. restart continuity / durability

現況：

- [tb2/service.py](../tb2/service.py) 已定義 machine-readable `runtime_contract()`
- 系統已明確告知 continuity mode
- 但 active room / bridge / pending intervention 仍非完整可恢復狀態

判讀：

- restart 行為已從「不明確」進展到「有正式契約」
- 但距離真正 recovery-ready 還有一段距離

#### C. GUI 成熟度

現況：

- GUI 不再只是 demo 頁面，而是有 workflow/preset/review/inspect/topology 任務分層
- 同時也累積了不少 operator-facing guidance
- 但核心前端仍集中在單一大檔 [tb2/gui.py](../tb2/gui.py)

判讀：

- UX 已經跨過「能用」門檻
- 但 maintainability、behavior isolation、componentization 仍偏弱

### 2.3 尚未完成的高風險缺口

#### 1. 認證與授權邊界仍不足

目前 repo 已經比舊審查更安全，但仍不應被視為 production-grade remote control plane。

核心原因：

- 缺少真正的 authn/authz
- high-trust、localhost-only 仍是主要安全假設
- human approval 仍是 workflow mode，不是不可繞過保證

#### 2. 多工作線操作的 targeting 邊界仍不夠硬

目前 server 對單線工作流很順，但若進一步擴成 fleet mode，`bridge_id` / `room_id` fallback 與自動解析會變成風險。

#### 3. 核心模組過大

目前最明顯的維護風險是：

- [tb2/gui.py](../tb2/gui.py)
- [tb2/server.py](../tb2/server.py)

這兩個檔案同時承擔產品流程、資料組裝、控制面契約與展示邏輯，後續若不拆，新增 feature 的摩擦會越來越高。

#### 4. release surface 仍落後於 code maturity

README 與 roadmap 已經很完整，但 release/admin/governance 相關面向仍偏弱：

- branch 治理沒有明確策略
- remote 非主線分支仍累積
- release posture 與產品定位仍需更明確收斂

## 3. 完成度判讀

以下不是假精確百分比，而是保守等級判讀。

| 面向 | 判讀 | 說明 |
| --- | --- | --- |
| 核心控制平面 | mostly done | CLI、MCP、GUI、room、bridge、intervention、audit 均已落地 |
| 單線 Host+Guest+Human workflow | mostly done | 已可穩定運作，且測試完整 |
| 稽核與事件契約 | mostly done | audit policy 與 recent query 已成熟，但仍可擴充 taxonomy |
| GUI operator experience | partial to mostly done | 任務導向 UI 已成形，但仍偏單檔與集中實作 |
| `1 + n` fleet 架構 | partial | 有方向、有 UI 雛形、有文件，但 runtime model 尚未正式完成 |
| restart recovery | partial | 已有 contract，尚未達到完整恢復 |
| security / trust boundary | partial | 已做基本 hardening，但不具 production-grade auth boundary |
| release readiness | partial | 代碼成熟度高於產品包裝與治理成熟度 |

## 4. 推薦下一步

### 4.1 Git / branch 整理結論

目前能安全下的結論只有三點：

1. 本地 branch 已只剩 `main`
2. `main` 已對齊 `origin/main`
3. remote 目前也已整理到只剩 `main`
4. 若後續要再做歷史壓縮，仍應視為獨立治理決策，不應直接在一般開發流中執行

若你要把 repo 層級也整理成「只剩 main」，建議先做一個單獨治理批次：

- 先確認 `.codex` 是否應加入 `.gitignore` 或移出 repo
- 維持 remote branch policy，避免再次累積長期未決分支
- 若要壓縮歷史，只能在明確允許 rewrite history 的前提下另開處理

### 4.2 執行形態建議

這個 repo 的下一輪工作不適合再採「想到哪補到哪」。

建議的執行形態：

- `Light` 類任務：文件、branch policy、ignore 清理、release copy 對齊
- `Medium` 類任務：GUI 切模組、status payload 整理、docs/release surface 收斂
- `Heavy` 類任務：workstream registry、fleet-safe targeting、restart recovery
- `Critical` 類任務：authn/authz、remote exposure posture、multi-workstream governance

## 5. 開發計畫

## Phase 0：Repository Hygiene 與 Release Governance

### 目標

先讓 repo 治理狀態追上目前主線成熟度。

### 任務

- 明確處理 `.codex` 的 repo 位置與追蹤策略
- 訂出 branch lifecycle：feature、copilot、dependabot、stale branch cleanup
- 建立 release checklist：定位、平台聲明、非目標、風險揭露
- 把「local-first / high-trust」寫成 release-facing 單一口徑

### 完成條件

- `git status --short --branch` 為乾淨
- stale remote branches 有明確保留或刪除決策
- release posture 文件可直接引用

## Phase 1：Workstream Runtime Model 正式化

### 目標

把 `1 + n` 從 GUI 心智模型推進成 server 正式資料模型。

### 任務

- 定義 `workstream_id`
- 建立 workstream summary 與 lookup
- 將 `status()` 擴成 workstream-oriented payload
- 將 mutation 類操作改成 fleet-safe targeting
- 明文化 `bridge_id`、`room_id`、`workstream_id` 的相容策略

### 完成條件

- 多條 workstream 同時存在時，不再依賴模糊 fallback
- GUI 與 MCP 都能以 workstream 為主語操作

## Phase 2：Durability / Recovery 補強

### 目標

把 restart contract 從「可觀察」提升到「最小可恢復」。

### 任務

- 持久化 active workstream metadata
- 持久化 pending intervention queue 或 checkpoint
- 定義 restart restore ordering
- 在 GUI 顯示 restored / orphaned / degraded state

### 完成條件

- restart 後可清楚辨識哪些工作線恢復、哪些遺失、哪些待人工接管

## Phase 3：GUI 模組化與 Fleet UX 重構

### 目標

降低單檔前端風險，並讓 fleet navigation 真正可操作。

### 任務

- 先把 [tb2/gui.py](../tb2/gui.py) 依資料模型、狀態刷新、畫面區塊切成可維護模組
- 將 overview / selected workstream / deep inspect 拆成三層
- 為 pending review、audit、diagnostics 建立一致的 selected-scope 邏輯
- 補更靠近行為層的 GUI 驗證

### 完成條件

- GUI 結構不再依賴單一巨大模板
- 8 到 12 條 workstream 下仍可快速定位與操作

## Phase 4：Security / Trust Boundary 明文化

### 目標

讓產品定位、文件、控制面邊界一致。

### 任務

- 明確定義 localhost-only 與 private-network 的支援邊界
- 決定是否導入最小 authn/authz
- 定義 approval policy 是否提供不可繞過模式
- 補齊 release-facing security posture 文件

### 完成條件

- 使用者不會再把 TB2 誤解成可直接公開暴露的 remote plane

## Phase 5：Packaging / Adoption Surface

### 目標

讓 repo 的外部採用方式跟得上目前實際完成度。

### 任務

- 收斂 getting-started、platform matrix、FAQ、release notes
- 增加更明確的 support tier
- 定義 demo path 與 production warning path

### 完成條件

- 新使用者能正確理解什麼能做、什麼不能做、什麼仍屬實驗性

## 6. 階段總結

### 本輪已確認完成

- 主線 `main` 與 `origin/main` 對齊
- 本地 branch 已只剩 `main`
- 完整測試在真實環境下 `363 passed`
- 專案核心能力已進入「可用且有回歸保護」階段
- `Phase 7` 已把 workstream governance 從 health observation 推進到 action layer

### 本輪已確認風險

- `1 + n` 雖已有正式 runtime model，但還沒有真正的 quota enforcement / stale remediation
- GUI / server 進一步擴張前需要先做結構化整理
- release/security posture 仍需收斂

### 下一輪最值得做的單一批次

若只選一個批次，我建議先做：

`Phase 8` 的 action enforcement / remediation 切片

也就是：

- 補真正的 quota enforcement
- 補 stale / orphan remediation tooling
- 再評估 main/sub dependency rules 是否需要正式化

原因很直接：

- 這會把目前已存在的 governance signal 從「可見、可調」進一步推到「可執行」
- 也能決定下一輪 GUI modularization 應該配合哪一種 operator action model
