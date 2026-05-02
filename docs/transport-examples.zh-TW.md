# Transport 範例

以下範例示範本機 TB2 server 的三種 room transport path。請先啟動 server：

```bash
python -m tb2 server --host 127.0.0.1 --port 3189
```

使用下列範例前，請先透過 GUI、`status` 或 `room_create` 建立或取得 `room_id`。

## `room_poll`

當 client 需要最簡單的 scripted fallback 時使用 `room_poll`。它不如 streaming 即時，但適合測試、自動化與受限 MCP client。

```bash
curl -sS http://127.0.0.1:3189/mcp \
  -H 'content-type: application/json' \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "room_poll",
      "arguments": {
        "room_id": "ROOM_ID",
        "after_id": 0,
        "limit": 50
      }
    }
  }'
```

下一次 poll 時，把回傳的 latest id 當成新的 `after_id`。

## SSE

當 client 需要單向 live room stream，且可以用 cursor 重連時使用 SSE。

```bash
curl -N 'http://127.0.0.1:3189/rooms/ROOM_ID/stream?after_id=0&limit=200'
```

stream 會先送出 `ready` event，接著送出含 room payload 的 `message` events。重連時，請把最後收到的 id 放進 `after_id`，或送出 `Last-Event-ID`。

## WebSocket

當 client 想用同一條雙向連線處理 subscription 與 `room_post`、`intervention_list`、`status` 等 actions 時使用 WebSocket。

Browser console 範例：

```js
const ws = new WebSocket("ws://127.0.0.1:3189/ws");
ws.onmessage = (event) => console.log(JSON.parse(event.data));
ws.onopen = () => {
  ws.send(JSON.stringify({
    action: "subscribe",
    room_id: "ROOM_ID",
    after_id: 0,
    limit: 200
  }));
};
```

用同一條 socket 發送 room message：

```js
ws.send(JSON.stringify({
  action: "room_post",
  room_id: "ROOM_ID",
  author: "human",
  text: "MSG: confirm transport is connected"
}));
```

## 選擇規則

| 需求 | Transport |
| --- | --- |
| 簡單測試或 degraded client path | `room_poll` |
| 單向 live read-only stream | SSE |
| 同一條連線同時做 live stream 與 control actions | WebSocket |

除非你明確用 `--allow-remote` 啟動 server 並加上外部網路控管，否則 GUI 與 MCP access 應維持在 loopback。
