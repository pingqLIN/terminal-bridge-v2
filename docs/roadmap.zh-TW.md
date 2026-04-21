# 路線圖

## 方向更新（2026-04-22）

目前方向正式收斂如下：

- TB2 繼續聚焦 local-first、operator-grade、multi-agent orchestration 與 governance
- 不把 TB2 定位成 Codex 原生 remote control 的替代品
- Windows 與 WSL 採雙軌實務：日常低摩擦操作優先 native Windows；高穩定互動協作優先 WSL `tmux`
- 保留一條獨立的外部 runtime / workflow 實驗線，作為 Windows / WSL 雙軌使用情境下的驗證與子代理 workflow 沙盒
- `codex_bridge_service` 視為針對 Codex 原生遙控能力的附屬原型，現在直接關閉，不再作為 TB2 主線方向

## 目前焦點

- 打磨 AI-first onboarding path
- 讓 GitHub、release 與開發文件跟上目前定位
- 持續收斂 Host / Guest / Human operator 的 live collaboration UX
- 把跨 Windows / WSL 的操作建議寫成正式 platform guidance

## 近期優先項

- 在 GUI 中進一步抽象 backend 與 room 識別子
- 補齊 release 與社群維運工具
- 強化 support matrix 與環境診斷說明
- 增加 transport 層面的回歸測試與文件範例
- 補強 native Windows 與 WSL 分流策略的文件、驗證與推薦路徑
- 參考漏斗狀治理層疊架構，規劃 `base -> model -> environment -> instruction_profile` 的 policy resolver 與 provenance contract

## 後續機會

- 常見 AI tool pairing 的 collaboration presets
- 更完整的 operator analytics 與 room observability
- 更好的 packaging 與 distribution
- 對 private-network operator deployment 提供更清楚且更安全的模式
- 建立 simulation-first、report-first、no-mutation 的 governance resolution surface，再視需要接到 apply / rollback 流程

## 暫時不做

- 把 TB2 做成雲端託管 agent 平台
- 追逐或複製 Codex 原生 app / remote-control / computer-use 能力
- 把所有 terminal 概念都藏進抽象 agent 模型
- 用另一套協定取代 MCP
