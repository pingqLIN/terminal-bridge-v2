---
description: 整理外部惡魔代言人審查與本地補充驗證，作為 terminal-bridge-v2 的反對發布與風險總結
---

# terminal-bridge-v2 DEVIL'S ADVOCATE REVIEW

## 摘要

以反對方角度看，`terminal-bridge-v2` 目前比較適合被定位成：

- 本機、單機、單使用者、高信任邊界下的實驗性控制平面
- 熟悉 terminal 與 AI workflow 的進階使用者工具
- 內部原型、受控試點或研究性 workflow 基礎設施

目前不適合被定位成：

- 可安全暴露或可寬鬆信任部署的 remote control plane
- 具備強制 human-in-the-loop 保證的產品
- 可直接對一般工程團隊廣泛推薦的 production-grade 多代理協作平台

這份整理版以兩個來源為基礎：

- 外部審查：`~/.copilot/session-state/.../devils-advocate-review-terminal-bridge-v2.md`
- 本地補充：直接檢查 `tb2/*.py`、`tests/*.py`，並在目前 Linux 環境執行 `python3 -m pytest`

## 狀態更新（2026-03-27）

這份文件保留的是反對發布視角的審查脈絡，但目前 branch 已經補掉其中一批高優先、低成本的缺口：

- `/mcp`、`/ws`、`/rooms/{room_id}/stream` 已加入 localhost-only `Origin` 驗證
- HTTP request body 已加入大小限制、讀取逾時與不完整 body 檢查
- `room_id` / `bridge_id` 與外部整數輸入已加入一致驗證
- backend cache key、`process` / `pipe` session idempotence、bridge per-cycle polling 已完成修補
- 本地完整驗證已更新為 `.venv/bin/python -m pytest -q` => `285 passed in 13.34s`

因此本文中把上述問題列為「當前未修」的段落，應視為歷史審查背景；目前仍然成立的核心反對理由，主要剩下：

- 缺乏 authentication / authorization
- human approval 仍是可選模式，不是不可繞過保證
- room / intervention / bridge 狀態仍以 in-memory 為主
- 非 Linux 平台仍以 simulated coverage 為主

## 測試與檢查範圍

- 本地 `.venv/bin/python -m pytest -q` 結果為 `285 passed in 13.34s`
- 目前工作區可完成完整測試，因此本文件的主要結論來自靜態檢查、設計邊界分析與最小重現，而非測試失敗訊號

## 主要反對理由

### 1. 控制面缺乏內建驗證邊界，不適合被描述成可安全發布的控制服務

外部審查最強的一點是：TB2 的能力本質上就是 terminal control plane，但 server 端沒有內建 authentication / authorization，也沒有明確的來源驗證。

關鍵證據：

- `tb2/server.py` 的 `/mcp` POST handler 只有 JSON-RPC 解析與 method dispatch，沒有認證流程
- `tb2/server.py` 的 WebSocket handler 只檢查 `Upgrade` 與 `Sec-WebSocket-Key`，未檢查 `Origin`
- `README.md` 與 `docs/faq.md` 都明示這是敏感的 local control surface，且不應公開暴露

反對方結論不是「這個專案錯了」，而是「目前的安全姿態和可能被理解的產品定位不匹配」。

### 2. Human approval 是模式，不是不可繞過的安全保證

文件大量強調 approval gate、human review、human-in-the-loop，但實作上這些能力可以被關閉，且仍有其他直接送指令到 pane 的路徑。

關鍵證據：

- `tb2/intervention.py` 中 `InterventionLayer(active=False)` 時，訊息直接走 `Action.AUTO`
- `tb2/server.py` 的 bridge worker 在 `auto_forward=True` 且 intervention 關閉時會直接 `backend.send(...)`
- `tb2/server.py` 的 `handle_room_post()` 在帶 `deliver` 時也可以直接把文字送到 pane

因此 TB2 比較像「提供可選的人類審核工作流」，不是「系統層級強制審批」。

### 3. 資料面以記憶體 bounded buffer 為主，不符合高可靠控制平面的期待

room、subscription、intervention history、bridge registry 都是 in-memory 結構，且多數有固定上限；這對 live collaboration 很合理，但對 audit trail、incident review、長時程工作流並不夠。

關鍵證據：

- `tb2/room.py` 的 room message buffer 預設 `max_messages=2000`
- `tb2/room.py` 的 subscription queue 預設 `max_queue=400`
- `tb2/intervention.py` 的 pending queue 上限 200、history 上限 500
- `tb2/server.py` 的 `_bridges` 與 `tb2/room.py` 的 `_rooms` 都只存在於記憶體

這表示 TB2 更接近「即時協作緩衝層」，而不是「可恢復、可稽核、可持久化的 control system」。

### 4. 跨平台訊號偏強，但實機成熟度仍主要集中在 Linux

README 已經相對誠實地說明：

- Linux：runtime verified
- Windows / macOS / WSL：多數仍以 simulated tests 為主

這不代表其他平台不能用，而是代表目前若以「跨平台成熟控制面」對外宣稱，風險仍高於實際驗證程度。

## 高優先風險

### 1. 缺少 `Origin` 檢查，WebSocket 與本機 HTTP surface 的信任模型過弱

位置：

- `tb2/server.py` 的 WebSocket handler，約第 1150 行附近
- `tb2/server.py` 的 `/mcp` POST 處理，約第 935 行附近

外部審查指出，若沒有 `Origin` 驗證，DNS rebinding 與 CSWSH 風險就不能被輕忽。這點我認為成立，而且屬於低成本、高價值修補。

建議最低限度先做：

- 僅接受 `http://127.0.0.1`、`http://localhost`、對應 port 的 `Origin`
- 在文件中把 network trust model 寫清楚

### 2. 請求主體沒有大小上限，存在記憶體耗盡 DoS 面

位置：

- `tb2/server.py` `do_POST()` 直接以 `Content-Length` 讀取 request body

若本機惡意程序或弱信任來源送出超大 `Content-Length`，server 目前沒有預先拒絕機制。

建議：

- 在讀取前加 `MAX_BODY`
- 對 `Content-Length` 非法值回 `400`
- 超過上限回 `413`

### 3. HTTP POST 路徑沒有讀取逾時，容易被慢速連線拖住執行緒

位置：

- `tb2/server.py` `do_POST()`

目前 WebSocket 路徑有 `self.connection.settimeout(0.5)`，但 HTTP body 讀取路徑沒有等價保護。對 `ThreadingHTTPServer` 來說，這會把 slow client 直接轉成 thread occupation 問題。

### 4. `room_id` 缺乏格式與長度限制

位置：

- `tb2/server.py` `handle_room_create()` / `handle_bridge_start()`
- `tb2/room.py` `create_room()`

這帶來三類風險：

- 超長字串造成資源浪費
- 不同流程可故意重用同一 room id
- 名稱碰撞時缺乏明確命名空間

建議：

- 將 `room_id` 限制為固定 regex 與合理長度
- 若 room id 屬於敏感命名，考慮引入 namespace 或 opaque id

## 本地補充發現

### 5. backend cache key 忽略 `shell` / `distro`，會把不同設定錯誤共用成同一實例

位置：

- `tb2/server.py:179-201`

`_make_backend()` 目前只用 `backend` + `backend_id` 做 cache key，沒有把 `shell` 或 `distro` 納入辨識。

我本地直接重現：

```python
import tb2.server as s

b1 = s._make_backend({"backend": "process", "backend_id": "x", "shell": "/bin/bash"})
b2 = s._make_backend({"backend": "process", "backend_id": "x", "shell": "/bin/sh"})

assert b1 is b2
assert b2.shell == "/bin/bash"
```

這表示：

- GUI 或 MCP client 若重用同一 `backend_id`
- 但切換了 shell 或 WSL distro
- server 仍可能悄悄回用舊 backend

這是實際會導致行為錯亂的缺陷，不只是設計偏好。

### 6. `process` / `pipe` backend 的 `init_session()` 不是 idempotent，重複初始化會遺失舊 child process

位置：

- `tb2/process_backend.py:105-110`
- `tb2/pipe_backend.py:64-69`

`TmuxBackend.init_session()` 會先檢查 session 是否存在；但 `ProcessBackend` 與 `PipeBackend` 每次都直接 `_spawn()` 新 pane，沒有先檢查 session 是否已存在。

本地最小重現顯示：

- 第一次 `ProcessBackend.init_session("dup")` 產生一組 PID
- 第二次再呼叫同名 session，會產生新 PID 覆蓋 `_procs["dup:a"]` / `_procs["dup:b"]`
- 舊 PID 仍然活著，但 backend 已失去控制引用

結果是：

- `kill_session("dup")` 只能清掉最新的一組
- 舊 process 可能變成 orphan

這對長時間運行的 service 或 GUI 重試流程是實質風險。

### 7. bridge 輪詢節流放在逐行處理迴圈內，輸出越多延遲越大

位置：

- `tb2/server.py:94-135`

`Bridge._process_new_lines()` 目前在每處理一行後 `sleep(max(0.05, self._current_poll / 1000.0))`。這會把「輪詢節流」錯誤地變成「每行輸出都額外延遲」。

本地最小重現：

- `poll_ms=100`，處理 5 行，約耗時 `0.5s`
- `poll_ms=400`，處理 3 行，約耗時 `1.2s`

這代表 burst output 時：

- room 更新延遲線性放大
- auto-forward / intervention queue 會變慢
- 正是高輸出場景下最容易觀察到卡頓

這個問題比表面看起來更重要，因為它直接影響控制面的互動即時性。

## 中優先風險

### 8. 多個 `int()` 解析點缺少完整保護，可能把壞輸入升級成 HTTP 500

外部審查指出 SSE query parsing 的 `after_id` / `limit` 沒有包 `try/except`。這點成立，且 `poll_ms`、`lines`、WebSocket subscribe 參數也有類似模式。

重點不是單一例外，而是：

- 外部輸入的整數解析策略目前不一致
- 某些 handler 會回錯誤物件，某些路徑會直接丟例外

建議統一做安全解析 helper。

### 9. `author` 是自由字串，容易造成 UI 或 operator 層級的身份混淆

位置：

- `tb2/server.py` `handle_room_post()`

這不一定是底層安全漏洞，但確實會讓上層 consumer 很容易把 `author="bridge"`、`author="system"` 之類字串誤當可信來源。

若 UI 或後續 automation 會依 `author` 判斷權威性，這裡需要更明確的欄位設計。

### 10. `auto_forward` 沒有明確速率限制或 circuit breaker

位置：

- `tb2/server.py` `Bridge._process_new_lines()`

目前 dedupe 只靠 `forwarded_recent` 保存最近 80 筆 `(tag, parsed)`。這可以擋住完全重複訊息，但無法處理：

- 不斷變化但語義相同的 loop
- 高頻互相觸發的 agent output
- 長時間自動化 runaway

若產品要更接近「可安心運行的控制平面」，這裡至少需要：

- 每 bridge 的速率限制
- 連續自動轉發次數上限
- 可自動切入 intervention 的斷路器

## 可保留的正面觀察

下列面向代表專案並不是雜亂原型，而是已有一定工程紀律：

- 大部分核心模組有測試覆蓋
- JSON-RPC 與 WebSocket 路徑已有基本 shape 驗證
- 多處共享狀態都有鎖
- `_sanitize_header_value()` 有處理 header splitting
- state file 採原子寫入
- 預設綁定 `127.0.0.1`
- `tmux` 相關參數大多避免 shell injection

反對發布的重點不是「完全不能用」，而是「現有實作能力與可能的對外定位之間仍有明顯落差」。

## 建議的修補優先序

### P0

- WebSocket / HTTP 增加 `Origin` 驗證
- 為 HTTP request body 加大小限制與讀取逾時
- 為 `room_id`、`bridge_id`、query int parsing 建立統一驗證

### P1

- 修正 `_make_backend()` cache key，把 `shell` / `distro` 納入
- 讓 `ProcessBackend` / `PipeBackend.init_session()` 變成 idempotent，或至少拒絕重複初始化
- 把 bridge 的 `sleep()` 移出逐行處理迴圈

### P2

- 為 `auto_forward` 增加 rate limit / circuit breaker
- 重新設計 message `author` 與可信來源欄位
- 明確區分「實驗性 local-first 工具」與「可發布控制面」的文件敘述

## 反對方最終結論

如果要用一句話總結：

`terminal-bridge-v2` 現在已經是一個有工程骨架、在 Linux 本地工作流上頗有潛力的 terminal-native AI orchestration 工具，但還沒有收斂到可以被描述為安全、成熟、可廣泛推薦的控制平面。

若近期要對外發布，最誠實的說法應該是：

- local-first
- high-trust only
- experimental / operator-grade
- not safe to expose publicly

而不是：

- secure remote operator plane
- enforced human approval system
- production-ready multi-agent control platform
