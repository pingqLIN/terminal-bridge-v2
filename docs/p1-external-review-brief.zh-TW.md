---
description: 提供給外部 reviewer 的 P1 修補審查範圍、重點與提示詞
---

# P1 外部審查 Brief

## 審查目標

請針對 `terminal-bridge-v2` 已完成的 `P1` 修補做外部審查，重點不是重跑整個專案，而是檢查這批修補是否：

- 真正修掉原本的缺陷
- 引入新的行為回歸
- 在邊界情況下仍有遺漏

## 本次 P1 修補範圍

### 1. backend cache key 修正

目的：

- 避免不同 backend 設定被錯誤共用成同一個實例

主要檔案：

- `tb2/server.py`

請特別檢查：

- cache key 是否仍漏掉任何重要配置維度
- `process` / `pipe` 的 `shell`
- `tmux` 的 `distro`
- 是否有因 cache key 改動導致原有重用行為被破壞

### 2. `ProcessBackend` / `PipeBackend.init_session()` idempotent

目的：

- 避免重複初始化同一 session 時產生 orphan process

主要檔案：

- `tb2/process_backend.py`
- `tb2/pipe_backend.py`

請特別檢查：

- session 已存在時直接重用是否合理
- 是否可能掩蓋半殘狀態或 dead process
- `kill_session()` 是否仍能正確清理
- 是否還存在 race condition 或 process leak

### 3. bridge 輪詢節流位置修正

目的：

- 避免每一行輸出都 sleep，造成輸出越多延遲越大

主要檔案：

- `tb2/server.py`

請特別檢查：

- `sleep()` 移到 per-cycle 後是否仍符合原始 polling 設計
- 是否可能造成 busy loop
- stop signal 的反應時間是否被影響
- 在 `new_a/new_b` 為空與非空時，poll interval 是否仍合理

## 建議 reviewer 閱讀檔案

- `tb2/server.py`
- `tb2/process_backend.py`
- `tb2/pipe_backend.py`
- `tests/test_server.py`
- `tests/test_process_backend.py`
- `tests/test_pipe_backend.py`

## 建議 reviewer 優先回答的問題

1. 這批 `P1` 修補是否確實解決了原先的三個問題？
2. 有沒有新的邊界條件會造成錯誤行為？
3. 測試是否只覆蓋 happy path，還漏了哪些關鍵場景？
4. 哪個修補最可能在實機環境出現預期外副作用？
5. 若要再補一個測試，你最建議補哪一個？

## 建議審查提示詞

```text
請對 terminal-bridge-v2 最近完成的 P1 修補做 code review。

審查重點：
1. backend cache key 是否完整反映 backend 配置，避免錯誤共用
2. ProcessBackend / PipeBackend 的 init_session 是否真的 idempotent，且不會掩蓋半壞狀態或造成資源洩漏
3. bridge worker 的 sleep 移到 per-cycle 後，是否修正了線性延遲問題，同時沒有引入 busy loop、stop latency 或 polling 行為回歸

請優先找：
- 實際 bug
- 行為回歸
- 邊界條件遺漏
- 測試缺口

請不要重複描述已知設計目標，重點放在 actionable findings。

請優先閱讀：
- tb2/server.py
- tb2/process_backend.py
- tb2/pipe_backend.py
- tests/test_server.py
- tests/test_process_backend.py
- tests/test_pipe_backend.py
```

## 本地驗證資訊

本地已通過：

```bash
.venv/bin/python -m pytest -q
```

結果：

- `285 passed in 13.34s`

## 注意事項

- 不需要把 sandbox 內 `tmux` / socket 權限限制誤判成產品缺陷
- 本次 review 目標是 `P1` 修補品質，不是重新做完整安全審查
