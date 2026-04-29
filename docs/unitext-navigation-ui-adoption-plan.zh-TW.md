---
description: 參考 UniText Project Map Web UI 導覽設計，套用到 TB2 Web GUI 的審查先行開發計畫
---

# TB2 Web UI 導覽重構計畫

日期：`2026-04-29`

## 目標

把 UniText Project Map 的 operator-console 導覽概念移植到 TB2 Web GUI，讓 TB2 從「多卡片控制集合」更明確地轉成「可操作的遠端 Agents CLI 拓樸控制台」。

完成後應達到：

- 使用者不需要刻意讀說明，也能完成基本操作：準備 panes、啟動 bridge、打開 review gate、查看 live room、檢查狀態、執行 recovery。
- 資訊以階層式揭露：全域 session context、主要工作區、拓樸地圖、右側 detail inspector、advanced diagnostics 分層清楚。
- 頁面總高度維持在 `2.5 viewport` 以內，長內容改由面板內部 scroll 承載。
- 拓樸操作可用滑鼠完成部署與設定；常通連線有清楚但不干擾的線路動畫。
- 所有實作經外部審查與真實瀏覽器檢查後才視為完成。

## UniText 可借用的導覽概念

| UniText 概念 | 對 TB2 的轉化 |
|---|---|
| 單一 primary workspace tabs | 保留 `Workflow / Topology / Review / Inspect` 為唯一主要導覽，不再讓 preset rail、workspace strip、拓樸操作互相競爭。 |
| 掃描路徑：summary -> controls -> map -> detail | TB2 轉成 `session strip -> workspace controls -> topology map -> selected detail / runtime inspector`。 |
| Map 是主要工作面 | `Topology` 不只是說明圖，而是主要操作面，可部署、設定、檢查、恢復。 |
| 去除重複 controls | 同一操作只保留一個主入口；其他區塊改成 mirror、status 或 jump，不再複製完整操作群。 |
| Masthead collapse latch | TB2 hero / preset grid 進入 workspace 後改成 compact cockpit，提供明確展開控制，避免佔用值班高度。 |
| Viewport controls | 拓樸圖增加 fit、reset、zoom 或 pan affordance；第一批可先做 bounded layout 與焦點定位，後續再做真正 pan/zoom。 |
| Text scale range | TB2 目前先保留既有密度；若新增 text scale，必須不破壞中英雙語與拓樸節點排版。 |

## 目前 TB2 狀態

已存在：

- `tb2/gui.py` 提供單檔 HTML/CSS/JS GUI。
- 已有 `Workflow / Topology / Review / Inspect` workspace tabs。
- 已有 topology relation view、node focus、ledger、runtime facts。
- 已有 topology 操作列：Prepare、Start Bridge、Review Gate、Live Room、Inspect、Recover。
- 已有 active relation line animation 與 `prefers-reduced-motion` fallback。
- 已有 workspace 高度上限：`max-height: calc(250svh - 72px)`。

仍需重構：

- `preset-grid`、`workspace-strip`、workspace tabs、拓樸操作列之間仍有資訊層級競爭。
- Topology 的操作列已能工作，但還未完全成為主要 cockpit；右側 detail/Launch Mirror/Live Runtime/Connection Ledger 仍偏多段並列。
- Hero 進入 workspace 後仍是固定區塊，還沒有 UniText 式的 masthead latch 或 compact cockpit。
- 真實瀏覽器檢查目前缺少 repo-local Playwright path；Batch 1 必須先建立 `tools/gui_browser_smoke.py`，通過後才開始 UI 重構。

## 設計方向

### Aesthetic Thesis

`Local Agent Operations Cockpit`

TB2 應像本機遠端 agents CLI 的控制儀表板，而不是 SaaS dashboard。視覺語言要克制、密集、可掃描；主要記憶點是「拓樸就是操作面」。

### Anti-Attractor

本次明確拒絕：

- 用 hero、卡片文案、說明文字取代操作導引。
- 重複出現同一組控制，讓使用者不知道哪個才是主入口。
- 把 topology 做成靜態裝飾圖。
- 用過多紫藍漸層、glass、orb 或行銷式 dashboard 裝飾。
- 手機版只把桌面壓成一欄，卻不處理操作順序。

## 開發批次

### Batch 0：計畫與外部審查

範圍：

- 本文件。
- 外部 reviewer 檢查：UniText 概念是否正確轉化、實作順序是否安全、驗收條件是否足夠。

完成條件：

- 外部審查沒有 blocking finding。
- 若有 non-blocking finding，先納入本文件後再進入 Batch 1。

### Batch 1：Browser Gate Baseline

目標：

- 先建立 repo-local 真實瀏覽器檢查，再開始任何 UI 重構。
- 之後每一個 UI batch 完成後都必須重跑同一個 browser smoke。

實作點：

- 新增 `tools/gui_browser_smoke.py`。
- 使用 Python Playwright；若 `.venv` 缺少 `playwright`，先在 `.venv` 補齊相依套件與 Chromium browser。
- 腳本可自行啟動或連到既有 server，並輸出 JSON summary。
- 外部審查與最終驗收必須使用 `--self-start`，避免連到舊 server 造成 browser evidence 無法追溯。
- 腳本的 `--help` 與 JSON summary 必須明確標示本次是 self-started server 還是連到 pre-existing server，並記錄 `ui_source_hash` 與 cwd，方便外部 reviewer 判讀驗證情境。
- 保留 screenshot evidence 到 `.tb2-gui-smoke/`，該資料夾不納入 commit，除非後續另行要求保存。

固定命令：

```bash
.venv/bin/python tools/gui_browser_smoke.py --self-start --base-url http://127.0.0.1:3192 --out .tb2-gui-smoke
```

失敗條件：

- desktop 或 mobile topology 頁面發生 console error 或 page error。
- 找不到 `#topology-actions`、`#relation-diagram`、`[data-topology-action]`。
- workspace body 沒有標示 `data-workspace-tab="topology"`，或 masthead 沒有預設 compact。
- `#relation-details` 沒有預設 open。
- desktop 或 mobile 的 topology action bar 沒有出現在第一個 viewport 附近，或 relation diagram 被推到過低位置。
- mobile relation diagram 節點互相重疊，導致拓樸不能被滑鼠或觸控穩定操作。
- `Review Gate` 點擊後沒有讓 `#intervention` 進入 checked 狀態。
- active topology line 沒有 `relation-flow` animation，或 reduced-motion mode 無法停用動畫。
- document 出現水平 overflow。
- document height 超過 `2.5 viewport`，且沒有明確 main/internal scroll 容器承載內容。

完成條件：

- Browser smoke 在目前 main 狀態可重複執行。
- 後續 Batch 2 到 Batch 4 都把這個命令列入驗收。

### Batch 2：Navigation Hierarchy

目標：

- 將 TB2 workspace 導覽整理成單一路徑：`session cockpit -> workspace tabs -> active workspace`。
- `preset-grid` 進入 workspace 後改成 compact scene switcher 或折疊 disclosure。
- `workspace-strip` 改成更像 persistent session summary，而不是另一組 navigation。

實作點：

- `tb2/gui.py`
- `tests/test_server.py`

驗收：

- Workspace 模式中第一螢幕能看到 active tab、session summary、主要操作面。
- 不需要捲到遠處才知道下一步。
- 頁面高度仍不超過 `2.5 viewport`。
- 真實瀏覽器檢查通過：
  ```bash
  .venv/bin/python tools/gui_browser_smoke.py --self-start --base-url http://127.0.0.1:3192 --out .tb2-gui-smoke
  ```

### Batch 3：Topology Cockpit

目標：

- 將 `Topology` 分頁改成主要遠端 agents CLI 操作面。
- 操作列、拓樸圖、spotlight、runtime facts 形成一個 cockpit，而不是多個並列 card。

實作點：

- `Topology` 工作面預設打開，不再把主要 map/action surface 藏在未展開 disclosure 後面。
- Topology action bar 加入狀態：ready、blocked、running、attention。
- 點擊 relation node / line 後，右側 inspector 顯示下一步操作與 runtime truth。
- `Launch Mirror` 改名或視覺化為 `Launch Settings`，`Live Runtime` 更明確區分正在運行的契約。
- action state 與 runtime truth 優先只從既有 `status`、bridge detail、pending items、audit state、form state 推導；除非外部審查另行同意，不新增後端 mutation contract。

驗收：

- 新使用者在 topology 頁不用讀長說明即可找出：先 prepare，再 start，之後看 room 或 review。
- 修改 staged settings 與 active runtime 的差異在畫面上可見。
- 常通線動畫保留，且 reduced motion 可停用。
- 真實瀏覽器檢查通過：
  ```bash
  .venv/bin/python tools/gui_browser_smoke.py --self-start --base-url http://127.0.0.1:3192 --out .tb2-gui-smoke
  ```

### Batch 4：Masthead Latch 與 Viewport Discipline

目標：

- 移植 UniText masthead collapse latch 概念。
- 控制整體高度與 mobile 操作順序。

實作點：

- Workspace 模式預設 compact masthead。
- 提供 expand/collapse control，狀態寫入 localStorage。
- Topology map 在 desktop 優先使用寬度；mobile 依序呈現 controls、map、detail，不讓控制列溢出。

驗收：

- Desktop 與 mobile viewport 都沒有水平 overflow。
- Browser smoke 量測 desktop 與 mobile：`document.documentElement.scrollWidth <= viewport width + 2`。
- Browser smoke 量測 desktop 與 mobile：`document.documentElement.scrollHeight / viewport height <= 2.5`，或 `main` 使用明確 internal scroll 且 document 本身不超過上限。
- Masthead 不會因高度變化自動展開/收合造成 layout loop。
- 真實瀏覽器檢查通過：
  ```bash
  .venv/bin/python tools/gui_browser_smoke.py --self-start --base-url http://127.0.0.1:3192 --out .tb2-gui-smoke
  ```

### Batch 5：Final Review Gates

目標：

- 把外部審查與 browser evidence 納入完成條件。

實作點：

- 更新 GUI browser smoke，至少覆蓋：
  - desktop topology V3
  - mobile/narrow topology V3
  - topology action click: review gate toggles state
  - no console/page errors
  - active line animation exists
  - compact masthead default
  - relation details default open
  - topology action bar and relation diagram first-viewport placement
  - mobile relation node overlap detection
  - page height/overflow constraints

驗收命令：

```bash
.venv/bin/python -m compileall tb2/gui.py
pytest tests/test_server.py -k gui
git diff --check
```

真實瀏覽器檢查：

```bash
.venv/bin/python tools/gui_browser_smoke.py --self-start --base-url http://127.0.0.1:3192 --out .tb2-gui-smoke
```

## 外部審查要求

審查者需檢查：

- UniText 導覽概念是否被正確抽象，而不是照抄 unrelated governance UI。
- TB2 的主要操作路徑是否更短、更清楚。
- 是否保留 terminal-native / local-first / operator-grade 的產品定位。
- 是否有足夠 browser-level 驗證，不只 HTML 字串測試。
- 是否有不必要的後端契約改動。

Blocking findings：

- 需要新增後端 mutation contract 但沒有測試。
- 導覽變得比目前更難掃描。
- Topology 失去 live runtime truth，變成裝飾圖。
- Browser smoke 不可重複或不能在 repo 中執行。
- Browser smoke 只在最後執行，沒有作為各 UI batch 的回歸門檻。

## 完成定義

- 開發計畫完成並通過外部審查。
- Batch 1 到 Batch 5 完成。
- 外部實作後審查無 blocking finding。
- 真實瀏覽器檢查通過並留下可重跑腳本或明確命令。
- Repo 狀態乾淨，變更已 commit。
