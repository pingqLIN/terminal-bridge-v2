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
