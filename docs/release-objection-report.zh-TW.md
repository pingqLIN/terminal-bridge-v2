---
description: 以反對方角度評估 terminal-bridge-v2 為何目前不應發布、不可作為一般推薦方案、也不適合在較弱信任邊界下使用
---

# terminal-bridge-v2 反對發布／反對使用報告

## 結論摘要

以反對方立場，我不建議把 `terminal-bridge-v2` 以「可廣泛推薦的控制平面」姿態發布，也不建議在缺乏強信任邊界的環境中使用。

目前較合理的定位是：

- 本機、單機、單使用者、明確知道風險的實驗性工具
- 內部原型或受控試點工具

不合理的定位是：

- 可安全暴露的 remote control plane
- 可直接推薦給一般工程團隊的 production-grade 多代理協作平台
- 可被視為具備強制性 human-in-the-loop 安全保證的產品

## 狀態更新（2026-03-27）

這份文件保留的是反對發布立場的論證，不等於目前 branch 完全沒有進展。到目前為止，已完成的收斂包括：

- localhost-only `Origin` 驗證已覆蓋 HTTP JSON-RPC、SSE 與 WebSocket
- HTTP request body 已加入大小限制、讀取逾時與不完整讀取防護
- `room_id` / `bridge_id` 與外部整數欄位已做一致驗證
- backend cache key、local backend session idempotence、bridge polling latency 問題已修補
- 本地完整驗證已更新為 `.venv/bin/python -m pytest -q` => `285 passed in 13.34s`

因此本文仍然最值得保留的反對理由，主要是產品定位與信任邊界層級的問題，而不是上面這批已完成的輸入邊界 hardening。

## 評估方法

- 讀取 `README.md`、`docs/*.md`、`tb2/*.py`、`tests/*.py`
- 在本機 Linux / Python 3.12.3 環境重跑完整 `pytest`，結果為 `285 passed in 13.34s`
- 以「為什麼不該發布 / 不該使用 / 不建議採用」為目標找反證
- 優先採用可直接對應到程式與文件的證據
- 無法直接證明但高度合理的部分，明確標示為「懷疑 / 推論」

## 主要反對理由

### 1. 控制面缺乏內建認證、授權與來源驗證，不具備可安全發布的基本邊界

#### 理由

這個專案的核心能力是直接建立 terminal session、擷取 terminal、送指令到 pane、批准待轉發訊息，等同提供本機指令控制平面。這類能力如果沒有內建 authn/authz 或 origin 驗證，發布時就只能依賴「使用者自己不要綁錯 host」。

這不是次要瑕疵，而是產品邊界本身尚未成立。

#### 證據

- `README.md` 自己將產品定義為 local orchestration layer，並且同時暴露 CLI、browser console、MCP endpoint 三種控制面；見 [README.md](../README.md) 第 30-36 行。
- `README.md` 將 `127.0.0.1:3189/mcp` 當成標準 MCP 控制入口；見 [README.md](../README.md) 第 119-129 行。
- `README.md` 的 Safety Notes 明確寫出「Keep server binding on `127.0.0.1`」與「Treat the MCP endpoint and browser console as sensitive local control surfaces」；見 [README.md](../README.md) 第 199-204 行。
- FAQ 直接回答「Is the service safe to expose publicly? No.」；見 [docs/faq.md](../docs/faq.md) 第 19-21 行。
- server 端對 `/mcp` 的 `POST` 只做 JSON-RPC 解析與 method dispatch，沒有任何認證或授權檢查；見 [tb2/server.py](../tb2/server.py) 第 935-980 行。
- `terminal_send` 可以直接把文字送入 pane；見 [tb2/server.py](../tb2/server.py) 第 352-358 行。
- `room_post` 在帶 `deliver` 參數時可以直接把訊息送入 pane；見 [tb2/server.py](../tb2/server.py) 第 383-419 行。
- WebSocket upgrade 只檢查 `Upgrade` 與 `Sec-WebSocket-Key`，沒有檢查 `Origin`、token、session 或任何 ACL；見 [tb2/server.py](../tb2/server.py) 第 1150-1166 行與第 1198-1257 行。

#### 懷疑 / 推論

- 任意本機程序只要能連到 `127.0.0.1:3189`，就可把 TB2 當成 terminal control plane 使用。
- 若使用者誤把 host 綁到 `0.0.0.0` 或經由 port forward 對外暴露，風險會立即放大。
- 由於 WebSocket 沒做 origin 檢查，瀏覽器端跨來源濫用是合理懷疑。即使 HTTP JSON-RPC 受 CORS 影響，WebSocket 本身仍可能成為更弱的入口。

#### 影響

- 不適合 public release 成「安全可用的本機控制服務」
- 不適合被推薦為跨主機或跨網段 remote operator plane
- 一旦宣傳語氣超過實際安全邊界，容易造成錯誤採用

### 2. 專案宣稱的人類審核與 approval gate，不是強制安全保證

#### 理由

文件多次強調 human approval path、approval gates、human-in-the-loop，但實作上這是一個「可開可關」的模式，不是不可繞過的保證。只要 client 選擇不同流程，仍可直接把內容送進 terminal。

如果產品訊息讓使用者以為「有 GUI review queue = 有強制人工審核」，那就是認知風險。

#### 證據

- `README.md` 把 human approval path 與 approval gates 當成主要價值主張；見 [README.md](../README.md) 第 38-43 行與第 47-53 行。
- 文件明確提供 `direct collaboration` 模式：`auto_forward=true`, `intervention=false`；見 [docs/ai-orchestration.md](../docs/ai-orchestration.md) 第 103-109 行。
- 文件也明確寫出某些情境「you do not need approval on every forwarded message」；見 [docs/ai-orchestration.md](../docs/ai-orchestration.md) 第 155-161 行。
- `InterventionLayer` 在 `active=False` 時，訊息直接標成 `Action.AUTO` 通過；見 [tb2/intervention.py](../tb2/intervention.py) 第 36-65 行。
- bridge worker 在 `auto_forward` 開啟且 intervention 未啟用時，會直接 `backend.send(..., enter=True)`；見 [tb2/server.py](../tb2/server.py) 第 100-132 行。
- 即使沒有 intervention，`room_post(deliver=...)` 也能直接把訊息送進 pane；見 [tb2/server.py](../tb2/server.py) 第 392-413 行。

#### 懷疑 / 推論

- 不同 client 或 operator 很容易因為追求效率而選擇 direct collaboration，最後把「人工監督」降格成文件建議而不是系統約束。
- 真正高風險工作流裡，TB2 的 approval 比較像 convenience feature，不像 enforceable control。

#### 影響

- 不應將本專案描述為「已內建強制 human-in-the-loop 保護」
- 不應推薦給需要合規、審批留痕、不可繞過人工核准的場景

### 3. 跨平台成熟度不足，現階段不適合廣泛發布

#### 理由

專案對外訊息強調 Windows / macOS / Linux / WSL 混合環境支援，但 README 自己承認目前真正 runtime 驗證的是 Linux；其他平台主要是 simulated tests。這代表支援矩陣目前仍偏工程信心，而不是充分場域驗證。

#### 證據

- 本次在目前工作區以 Linux / Python 3.12.3 實測，完整 `pytest` 為 `277 passed in 13.95s`。
- `README.md` 明寫：
  - Linux: runtime-verified
  - Windows: simulated in automated tests
  - macOS: simulated in automated tests
  - WSL: simulated in backend tests
  見 [README.md](../README.md) 第 141-148 行。
- `README.md` 也寫出不同平台 backend fallback 與 shell policy 差異；見 [README.md](../README.md) 第 150-157 行。
- roadmap 仍把「make GitHub and release surfaces match the maturity of the codebase」「clearer support matrix and environment diagnostics」列為進行中或近期優先項；見 [docs/roadmap.md](../docs/roadmap.md) 第 5-14 行。

#### 懷疑 / 推論

- 真實使用時的 shell 行為、Enter key 語義、PTY/TUI 相容性、Windows/WSL 邊界條件，仍可能有大量環境特有問題尚未被踩到。
- 若現在就主打「跨平台可用」，很可能造成 early adopter 在非 Linux 環境承受整合成本。

#### 影響

- 不適合現在就做大範圍對外發布
- 不適合作為「跨平台協作基礎設施」向一般團隊推薦
- 其中 Linux 信心已因本次重測提升，但 Windows / macOS / WSL 的「非實機驗證」問題仍然成立

### 4. 訊息、審批與觀測資料都是易失且有上限的，不符合可靠控制平面的期待

#### 理由

作為 control plane，最怕的是訊息遺失、審批遺失、訂閱 backlog 被截斷、服務重啟後狀態消失。但目前核心狀態幾乎都在記憶體，且大量使用 bounded deque。這代表產品比較像 live collaboration buffer，而不是可追溯、可恢復、可稽核的控制系統。

#### 證據

- room 訊息儲存使用 `deque(maxlen=max_messages)`，預設上限 2000；見 [tb2/room.py](../tb2/room.py) 第 68-77 行。
- subscription queue 預設 `max_queue=400`，backlog 預設 200；見 [tb2/room.py](../tb2/room.py) 第 111-128 行。
- room 超過 1 小時 idle 會被 cleanup；見 [tb2/room.py](../tb2/room.py) 第 193-200 行。
- intervention pending queue 上限 200，history 上限 500；見 [tb2/intervention.py](../tb2/intervention.py) 第 43-48 行。
- server 內的 bridge registry 是全域記憶體字典 `_bridges`；見 [tb2/server.py](../tb2/server.py) 第 142-168 行。
- room registry 也是全域記憶體字典 `_rooms`；見 [tb2/room.py](../tb2/room.py) 第 168-180 行。
- process backend 的 pane buffer 也只有 `deque(maxlen=5000)`；見 [tb2/process_backend.py](../tb2/process_backend.py) 第 38-62 行。

#### 懷疑 / 推論

- 高流量、短暫斷線、長時間審批等待、server restart 等情況下，重要 handoff 或待審訊息可能被截斷或直接消失。
- 如果事後要做 incident review、operator audit、合規追蹤，現有資料模型很難支撐。

#### 影響

- 不適合宣稱自己是可依賴的 operator control plane
- 不適合用於需要 audit trail、事後鑑識、長時程工作流的場景

### 5. 自動轉發邏輯高度依賴簡單字串解析，誤判成本偏高

#### 理由

TB2 的 bridge 自動化價值來自「從終端輸出中找到可轉發 handoff」。但目前核心判定非常薄：本質上是找 `MSG:` 前綴，加上一些 prompt regex。這對 demo 很有效，對 production orchestration 則偏脆弱。

#### 證據

- `ToolProfile.parse_message()` 只是找字串 `MSG:`，確認前一字元是空白，然後把後面內容整段取出；見 [tb2/profile.py](../tb2/profile.py) 第 39-48 行。
- prompt detection 也是以 regex 列表做判斷；見 [tb2/profile.py](../tb2/profile.py) 第 18-37 行。
- bridge worker 只要 `parse_message()` 有結果，就可能進入 auto-forward 或 pending queue；見 [tb2/server.py](../tb2/server.py) 第 100-132 行。
- 文件還特別提醒 guest 要避免 narrative transcripts、multiple asks、formatting noise，反面說明這條通道本來就容易被內容品質影響；見 [docs/ai-orchestration.md](../docs/ai-orchestration.md) 第 111-141 行。

#### 懷疑 / 推論

- 模型輸出、工具回顯、log、範例文字、貼上的 transcript，都可能意外包含 `MSG:`。
- 一旦 parser 誤判，錯誤內容會直接變成待審指令，甚至在 intervention 關閉時直接進 shell。

#### 影響

- 不適合高風險自動化
- 不適合作為通用型 agent handoff 協議直接對外宣稱穩定

## 次要但仍重要的反對意見

### 6. 專案目前更像 power-user 工具，不像可普及採用的產品

- README 自己承認 CLI 最快，但前提是使用者已理解 panes、shell、bridge ids；見 [README.md](../README.md) 第 57-62 行。
- README 也承認 GUI 雖然較 approachable，但仍然是 local-host oriented；見 [README.md](../README.md) 第 57-62 行。
- 這意味著 TB2 的真正使用門檻仍然偏高，容易在早期採用時把操作負擔轉嫁給使用者。

## 反對方結論

如果要站在反對發布的一側，我的主張會是：

1. 現在不應把 TB2 當成「安全、成熟、可廣泛推薦」的 remote control plane 發布。
2. 現在不應把 TB2 描述成「已具備強制人類審批保護」的多代理協作產品。
3. 現在不應把 TB2 直接推薦給一般工程團隊做跨平台 production adoption。

比較誠實的對外定位應該是：

- terminal-native、local-first、high-trust 的 AI 協作原型工具
- 適合熟悉 terminal、能自行維護安全邊界的進階使用者
- 尚未完成 security posture、support matrix、release maturity 收斂

## 若仍要發布，至少需要先補的條件

- 內建 authentication / authorization
- WebSocket `Origin` 驗證與明確的 network trust model
- 不可繞過的 approval policy 選項
- 更完整的持久化 audit trail
- 真實 Windows / macOS / WSL runtime 驗證
- 對「可發布範圍」與「不建議使用情境」做更明確聲明

## 本次檢查限制

- 本次已重跑目前工作區的 Linux 測試，但這不等於完成 Windows / macOS / WSL 的實機驗證。
