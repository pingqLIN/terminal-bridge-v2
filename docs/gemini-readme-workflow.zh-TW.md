# Gemini 3 Pro README 編排工作流

此流程用 `tb2` 作為橋接層，呼叫 `gemini` 產生 README 編排草稿，再由人工審閱後落地

## 前置條件

- 已安裝 `tb2`
- 已安裝並完成登入 `gemini` CLI
- 建議先確認 model 可用

```bash
gemini -m gemini-3-pro-preview -p "reply OK only"
```

## Step 1 啟動 tb2 MCP server

```bash
python3 -m tb2 --backend process server --host 127.0.0.1 --port 3189
```

## Step 2 初始化雙 pane

```bash
curl -sS http://127.0.0.1:3189/mcp \
  -H 'content-type: application/json' \
  -d '{
    "jsonrpc":"2.0",
    "id":1,
    "method":"tools/call",
    "params":{
      "name":"terminal_init",
      "arguments":{
        "backend":"process",
        "backend_id":"gemini-readme",
        "session":"readme"
      }
    }
  }'
```

## Step 3 對 pane A 下達 Gemini 3 Pro 編排任務

```bash
curl -sS http://127.0.0.1:3189/mcp \
  -H 'content-type: application/json' \
  -d '{
    "jsonrpc":"2.0",
    "id":2,
    "method":"tools/call",
    "params":{
      "name":"terminal_send",
      "arguments":{
        "backend":"process",
        "backend_id":"gemini-readme",
        "target":"readme:a",
        "enter":true,
        "text":"gemini -m gemini-3-pro-preview -p \"請用繁體中文為 terminal-bridge-v2 產出 README 章節重排提案，需含：功能總覽、快速開始、MCP 工具、人工介入流程、截圖區塊、常見問題。輸出 Markdown。\""
      }
    }
  }'
```

## Step 4 擷取 Gemini 輸出

```bash
curl -sS http://127.0.0.1:3189/mcp \
  -H 'content-type: application/json' \
  -d '{
    "jsonrpc":"2.0",
    "id":3,
    "method":"tools/call",
    "params":{
      "name":"terminal_capture",
      "arguments":{
        "backend":"process",
        "backend_id":"gemini-readme",
        "target":"readme:a",
        "lines":200
      }
    }
  }'
```

## Step 5 截圖配圖

在 Windows PowerShell 執行

```powershell
pwsh -File .\scripts\capture_tb2_screenshot.ps1 `
  -OutputDir .\docs\images `
  -Prefix tb2-gemini `
  -DelaySec 3 `
  -Count 3 `
  -IntervalSec 2
```

## Step 6 放入 README 配圖區塊

```md
## 執行畫面

![tb2 + Gemini 畫面 1](docs/images/tb2-gemini-01-20260101-120001.png)
![tb2 + Gemini 畫面 2](docs/images/tb2-gemini-02-20260101-120003.png)
![tb2 + Gemini 畫面 3](docs/images/tb2-gemini-03-20260101-120005.png)
```

## 備註

- 專案已提供 `readme.mf` 版型草稿，可直接覆寫或搬移到 `README.md`
- 正式對外建議仍維持 `README.md` 與 `README.zh-TW.md`
