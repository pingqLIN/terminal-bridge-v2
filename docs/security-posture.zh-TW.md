# 安全姿態

TB2 目前應視為 local-first 的 operator control plane。

目前 release posture 建議這樣理解：

| Tier | 狀態 | 適用情境 |
| --- | --- | --- |
| `operator-beta` | 目前 release 成熟度 | local-first operator 工作流，需有人類 operator 主動管理；適合受控使用，不適合無人看管的公開基礎設施 |
| `local-first-supported` | supported | 同一台受信任 operator 主機上的 loopback CLI、GUI、MCP 工作流 |
| `private-network-experimental` | experimental | 有明確 `--allow-remote` 確認，且外部另有網路控管的私網 operator-managed 存取 |
| `public-edge-unsupported` | unsupported | 直接對外網暴露、零信任遠端存取，或期待 TB2 自己就是硬 auth 邊界 |

## TB2 目前有明確做的事

- 預設 bind host 維持在 `127.0.0.1`
- 只要不是 loopback bind，現在必須明確加上 `--allow-remote` 或 `TB2_ALLOW_REMOTE=1`
- GUI、SSE、WebSocket、MCP POST 的 browser `Origin` 檢查仍只接受 localhost 類型來源
- `status`、`doctor`、`/healthz`、`/mcp` 都會公開 machine-readable 的 `security` / `security_posture`

## TB2 沒有聲稱做到的事

- TB2 目前沒有 production-grade authn/authz
- approval gate 與 `intervention` 是 workflow control，不是 authorization 保證
- TB2 不應被視為可直接公開暴露的 remote control plane

## 遠端存取規則

如果要綁到 loopback 以外，必須是明確有意識的操作：

```bash
python -m tb2 server --host 10.0.0.5 --port 3189 --allow-remote
```

建議同步補上的外部控制：

- 用 VPN、SSH tunnel 或 firewall ACLs 包住 TB2
- 能綁特定 private address，就不要直接用 `0.0.0.0`
- 保持 operator 與 browser 存取都走受信任的網路路徑

## 安全通報

若 repository 已啟用 GitHub private vulnerability reporting，請優先使用該路徑。若未啟用，請使用 repository owner 在專案 profile 或 package metadata 中提供的私人聯絡管道，且不要把 exploit details 放到公開 issue、discussion 或 pull request。

## Operator 檢查表

- 先跑 `python -m tb2 doctor`，確認目前 support tier。
- 把目前 release 視為 `operator-beta`：保留人類 operator 介入，不要假設可以直接公開部署。
- 除非真的需要 private-network access，否則讓 `status.security.support_tier` 保持在 `local-first-supported`。
- 一旦進入 `private-network-experimental`，真正的 trust boundary 必須寫在你自己的外部網路控管裡，不要假設 TB2 本身已提供。
