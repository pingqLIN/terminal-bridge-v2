---
description: 2026-04-22 起算的 TB2 五小時開發計畫，聚焦治理 resolver MVP、文件收斂與可驗證 CLI surface
---

# TB2 五小時開發計畫

日期：2026-04-22

## 目標

在五小時開發窗內，把 TB2 從「已定義治理分層文件」推進到「repo 內已有最小可驗證治理解析能力」。

本輪不追求：

- runtime auto-apply
- policy rollback
- GUI integration
- drift audit

本輪追求：

- repo-local governance resolver MVP
- machine-readable resolution payload
- CLI 可直接解析與輸出
- 對應測試與文件同步

## 目前前提

- 基礎文件入口已收斂到 local-first、operator-grade、multi-agent orchestration / governance
- Windows / WSL 雙軌已成為正式 guidance
- `codex_bridge_service` 已被視為關閉的附屬原型
- 治理分層最小契約已寫入 `docs/governance-layering*.md`

## 執行批次

### Batch 1：Resolver Core

目標：

- 建立 `base -> model -> environment -> instruction_profile` 的最小解析核心

範圍：

- `tb2/governance.py`
- 預設 layer config
- precedence / provenance merge 邏輯

驗收：

- 能輸出 `matched_layers`
- 能輸出 `effective_config`
- 能輸出 `provenance`

### Batch 2：CLI Surface

目標：

- 讓 operator 可透過 CLI 解析治理，不必靠手動閱讀文件

範圍：

- `tb2/cli.py`
- `tb2 governance resolve ...`

驗收：

- 支援指定 `--model`
- 支援指定 `--environment`
- 支援指定 `--instruction-profile`
- 支援 JSON 輸出

### Batch 3：Tests

目標：

- 用測試固定 precedence 與 payload shape

範圍：

- `tests/test_governance.py`
- `tests/test_cli.py`

驗收：

- 覆蓋 layer override
- 覆蓋 provenance
- 覆蓋 CLI argument parsing 與 command output

### Batch 4：Docs Integration

目標：

- 把新 CLI 與 resolver 使用方式接回文件

範圍：

- `README*`
- `docs/governance-layering*.md`
- 必要時補 `docs/getting-started*`

驗收：

- 文件不再只描述方向，也能指向實際命令
- 明確標示仍是 simulation-first / no-mutation

### Batch 5：Stabilization and Review

目標：

- 跑 targeted tests
- 做一次 code / docs review
- 產出下一輪建議

驗收：

- 新增測試通過
- 主要文件與 CLI 敘事一致
- 列出下一輪是否接 GUI 或 server surface

## 停止條件

若出現下列任一情況，本輪不再打開新的功能：

- precedence model 出現需要重大架構分歧的爭議
- CLI surface 已落地，但測試或文件尚未收斂
- 剩餘時間不足以完成並 review 下一個批次

## 本輪完成定義

只有當下列條件成立，這個五小時計畫才算完成：

- repo 內已有 governance resolver MVP
- CLI 可解析並輸出治理結果
- 測試覆蓋 precedence 與 provenance
- 文件說明與實作一致
- 留下下一輪開發切入點
