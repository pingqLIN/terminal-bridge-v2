---
description: TB2 治理分層最小契約，定義 precedence、effective config 與 provenance
---

# TB2 治理分層

## 目的

這份文件定義 TB2 目前採用的治理分層最小契約。

現在的目標不是立刻把治理自動 apply 到所有 runtime 路徑，而是先讓 operator、文件與後續實作能共用同一套 precedence 與 provenance 語言。

## 目前姿態

這一層目前是：

- simulation-first
- report-first
- no-mutation

這裡的 `no-mutation` 指的是未來分層治理 resolver 的 rollout 姿態。

它不會取代 TB2 現有已存在的 mutable runtime controls，例如：

- `workstream_update_policy`
- `workstream_update_dependency`
- `workstream_pause_review`
- `workstream_resume_review`

換句話說：

- 現有 per-workstream control layer 仍然是可變動的
- 分層治理 resolver 目前先負責解釋「應該生效的治理配置」

## Layer 順序

目前預期的覆蓋順序如下：

1. `base`
2. `model`
3. `environment`
4. `instruction_profile`

若同一個 key 在多層同時出現，後面的 layer 覆蓋前面的 layer。

## 每層的意義

| Layer | 用途 |
| --- | --- |
| `base` | repo 預設的 guardrail、audit、review baseline |
| `model` | 不同 agent client / model 類別的 review cadence、handoff 密度、更新節奏 |
| `environment` | native Windows、WSL、Linux、private-network operator 等環境差異 |
| `instruction_profile` | `quick-pairing`、`approval-gate`、`mcp-operator`、`diagnostics` 等任務模式 |

## 預期 Resolver 輸出

未來若實作治理 resolver，最小輸出至少應包含：

- `matched_layers`
- `effective_config`
- `provenance`

`Batch A` 也先建立一條最小 runtime 邊界：

- `review_mode` 是第一個 authoritative governance key
- `preferred_backend` 目前仍是 advisory
- `rate_limit`、`pending_limit` 這類 per-workstream policy key 仍屬 mutable exception keys，不在第一批 authoritative subset 內
- operator `pause_review` / `resume_review` 現在只會在 baseline 為 `auto` 時形成明確的 review-mode exception；不會覆蓋 authoritative `manual` baseline
- `workstream_update_policy` 現在會把 policy mutation 記錄成 policy baseline 之上的 mutable exception，而不是沒有語義的設定更新

`Batch B` 目前開始把治理決策做成可消費的機器輸出：

- 每個 workstream 的 governance payload 會附帶 `decision_trace`
- fleet status 會額外摘要 `governance_review_overrides`、`governance_policy_overrides`、`governance_exceptions`

### `matched_layers`

列出這次解析實際命中的 layer。

### `effective_config`

列出覆蓋解析後真正生效的治理配置。

### `provenance`

明確指出每個生效 key 最後來自哪一層。

## 目前 CLI 入口

可用：

```bash
python -m tb2 governance resolve \
  --model gpt-5.4 \
  --environment wsl-tmux \
  --instruction-profile approval-gate \
  --json
```

這會回傳目前模擬解析出的治理結果，不會改動 runtime state。

若 caller 在 `bridge_start` 明確指定 `instruction_profile`，TB2 可以把 authoritative `review_mode` 的最小子集投影到啟動時行為。這一批刻意只做很窄的 projection，不代表已經進入一般化 auto-apply。

同一份 read-only 解析結果也已透過 MCP/server tool 暴露：

- `governance_resolve`

目前 governance overlay 契約也已在 repo 內正式提供：

- schema：[`../schemas/governance.layers.schema.json`](../schemas/governance.layers.schema.json)
- sample：[`../examples/governance.layers.sample.json`](../examples/governance.layers.sample.json)
- CLI schema 輸出：`python -m tb2 governance schema`
- CLI sample 輸出：`python -m tb2 governance sample`

也支援額外的 JSON overlay：

```bash
python -m tb2 governance resolve \
  --environment wsl-tmux \
  --instruction-profile approval-gate \
  --config ./governance.layers.json \
  --json
```

overlay 檔案沿用相同的 top-level layer keys：

```json
{
  "environment": {
    "wsl-tmux": {
      "preferred_backend": "tmux"
    }
  },
  "instruction_profile": {
    "approval-gate": {
      "approval_mode": "required"
    }
  }
}
```

## 這份文件目前不宣稱的事

這份文件目前不宣稱 TB2 已有：

- 完整治理 resolver
- 自動 apply / rollback
- drift audit 或 policy sync
- 從文件自動投影到 runtime 行為的機制

目前只宣稱：

- precedence model 已定義
- effective payload shape 已有最小方向
- 後續治理設計不應再把 policy 散落到 README、preset 說明與 operator 默契中

## 與 Runtime Controls 的關係

TB2 目前已存在的 mutable runtime action layer 包含：

- review pause / resume
- policy mutation
- dependency mutation
- remediation action

治理分層不是要取代這一層，而是提供更高層的語言，讓未來可以回答：

- 為什麼某個 policy 會生效
- 它來自 `base`、`model`、`environment`，還是 `instruction_profile`
- 哪些 key 只應該停留在 advisory，哪些 key 之後可以安全 apply

## 建議下一步

1. 先固定文件與 sample payload
2. 再做 resolver prototype
3. 再決定哪些 key 可以進 apply / rollback
4. 最後才考慮 drift audit 與 guard task
