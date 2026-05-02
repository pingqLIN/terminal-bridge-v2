# Transport Examples

These examples show the three supported room transport paths from a local TB2 server. Start the server first:

```bash
python -m tb2 server --host 127.0.0.1 --port 3189
```

Create or discover a `room_id` through the GUI, `status`, or `room_create` before using the examples below.

## `room_poll`

Use `room_poll` when a client needs the simplest scripted fallback. It is less live than streaming, but it works well for tests, automation, and constrained MCP clients.

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

Use the returned latest id as the next `after_id`.

## SSE

Use SSE when a client wants a one-way live room stream and can reconnect with a cursor.

```bash
curl -N 'http://127.0.0.1:3189/rooms/ROOM_ID/stream?after_id=0&limit=200'
```

The stream sends a `ready` event first, then `message` events with room payloads. On reconnect, pass the last received id as `after_id` or send `Last-Event-ID`.

## WebSocket

Use WebSocket when the client wants one bidirectional connection for subscription plus actions such as `room_post`, `intervention_list`, and `status`.

Browser console example:

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

Post into the room on the same socket:

```js
ws.send(JSON.stringify({
  action: "room_post",
  room_id: "ROOM_ID",
  author: "human",
  text: "MSG: confirm transport is connected"
}));
```

## Selection Rule

| Need | Transport |
| --- | --- |
| Simple test or degraded client path | `room_poll` |
| Live read-only stream | SSE |
| Live stream plus control actions on one connection | WebSocket |

Keep GUI and MCP access on loopback unless you intentionally start the server with `--allow-remote` and external network controls.
