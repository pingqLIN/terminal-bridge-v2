---
description: 2026-04-24 project-development-loop overnight maintenance state and handoff
---

# Overnight Loop State

日期：2026-04-24

## 目前 checkpoint

- repo：`/home/miles/dev2/projects/terminal-bridge-v2`
- branch：`main`
- checkpoint commit：`e609875 Add governance projection status surfaces`
- 狀態：`main` ahead of `origin/main` by 5 commits after checkpoint
- durable monitor：`tools/overnight_loop_status.py`
- local state path：`.tb2-overnight/2026-04-24/status.jsonl`

## 已完成批次

### Batch 1: Authoritative governance projection surfaces

- governance resolver 現在回傳 authoritative keys、exception keys、key classes 與 runtime projection。
- workstream snapshot 可保留 governance metadata。
- GUI status summary 現在可顯示 governance layer、review mode 與 preferred backend。
- audit schema 接受 governance decision/context 欄位。
- Windows winpty process backend 改為以 argv list 呼叫 `PtyProcess.spawn`，避免含空白路徑被拆錯。
- 第一輪外部審查與主線開發書已納入 docs，作為後續 stop / continue / defer 依據。

### Batch 2: README direction alignment and overnight resumability

- README / README.zh-TW 已將 Chrome sidepanel 語氣從主線相容性改為 `Compatibility Adapter`。
- 新增 repo-local overnight status writer，讓 unattended loop 可定期留下 git/status/process snapshot。
- `.tb2-overnight/` 列入 local artifact ignore，避免監控輸出污染 commit。

### Batch 3: Read-only fleet governance compliance summary

- `status.governance_compliance` 現在提供 fleet-level compliance state、issue count 與 per-workstream issue list。
- `status.fleet` 現在提供 compact governance compliance counters，方便 operator 先掃描整體狀態。
- 此批次只新增 read-only projection，不改 runtime auto-apply、不改 policy mutation 行為。

### Batch 4: GUI governance compliance badge

- GUI status badges 現在會在 fleet governance compliance 不是 `compliant` 時顯示治理合規狀態。
- 只新增 read-only badge，不新增按鈕、不新增 mutation surface。

## 驗證

- `python3 -m pytest tests/test_governance.py tests/test_process_backend.py`
  - 結果：`44 passed`
- `git diff --check`
  - 結果：無輸出
- `python3 -m pytest`
  - 結果：`413 passed`
- `python3 -m pytest tests/test_server.py::TestStatusHandler::test_status tests/test_server.py::TestWorkstreamHandlers::test_status_reports_governance_exception_summary`
  - 結果：`2 passed`
- `python3 -m pytest tests/test_server.py`
  - 結果：`141 passed`
- `python3 -m pytest tests/test_server.py::TestGuiRouting::test_gui_html_surfaces_status_summary_badges`
  - 結果：`1 passed`
- `python3 -m pytest tests/test_server.py`
  - 結果：`141 passed`（Batch 4 rerun）

## 監控指令

一次性 snapshot：

```bash
python3 tools/overnight_loop_status.py --state-dir .tb2-overnight/2026-04-24 --label manual --iterations 1
```

背景 overnight 監控範例：

```bash
nohup python3 tools/overnight_loop_status.py --state-dir .tb2-overnight/2026-04-24 --label overnight --interval-seconds 1800 --iterations 16 > .tb2-overnight/2026-04-24/watcher.log 2>&1 &
```

## 下一步

1. 依 `docs/development-book-round1-2026-04-22.zh-TW.md` 選下一個 bounded batch。
2. 優先 Batch B / C 的 read-only 決策鏈與 fleet compliance，不新增新的 client-specific surface。
3. 若進入 Batch D，只做小型 extraction plan 或 adapter boundary，不開大範圍 `server.py` 重構。

## Overnight guardrails

- 不做 production deployment。
- 不做 secret、auth、billing、quota 變更。
- 不做 destructive cleanup。
- 不做 runtime auto-apply 或 difficult rollback migration。
- 若需要長期架構拆分 `tb2/server.py`，先留下計畫或小型 extraction，不開大範圍重構。