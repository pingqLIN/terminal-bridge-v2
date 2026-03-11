"""MCP smoke tests that drive tb2 as a real remote-control plane."""

from __future__ import annotations

import base64
import os
import hashlib
import json
import socket
import struct
import threading
import time
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

import tb2.server as server_mod


class _WsClient:
    def __init__(self, sock: socket.socket, buffered: bytes = b""):
        self.sock = sock
        self.buffer = buffered

    def recv_exact(self, size: int, *, timeout: float = 5.0) -> bytes:
        self.sock.settimeout(timeout)
        while len(self.buffer) < size:
            chunk = self.sock.recv(4096)
            if not chunk:
                break
            self.buffer += chunk
        data = self.buffer[:size]
        self.buffer = self.buffer[size:]
        return data

    def close(self) -> None:
        self.sock.close()


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


def _tool(base_url: str, name: str, args: dict) -> dict:
    body = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": name, "arguments": args},
    }).encode("utf-8")
    req = urllib.request.Request(
        base_url,
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return payload["result"]["structuredContent"]


def _read_sse_event(resp, *, timeout: float = 5.0) -> tuple[str, dict]:
    deadline = time.time() + timeout
    event_name = "message"
    data_lines = []
    while time.time() < deadline:
        raw = resp.readline()
        if not raw:
            continue
        line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
        if not line:
            if data_lines:
                return event_name, json.loads("\n".join(data_lines))
            event_name = "message"
            data_lines = []
            continue
        if line.startswith(":"):
            continue
        if line.startswith("event:"):
            event_name = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            data_lines.append(line.split(":", 1)[1].lstrip())
    raise AssertionError("timed out waiting for SSE event")


def _ws_handshake(port: int) -> _WsClient:
    sock = socket.create_connection(("127.0.0.1", port), timeout=5.0)
    key = base64.b64encode(b"pytest-websocket-key").decode("ascii")
    request = (
        "GET /ws HTTP/1.1\r\n"
        "Host: 127.0.0.1\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        "\r\n"
    ).encode("utf-8")
    sock.sendall(request)
    response = b""
    while b"\r\n\r\n" not in response:
        response += sock.recv(4096)
    headers, _, buffered = response.partition(b"\r\n\r\n")
    response_text = headers.decode("utf-8", errors="replace")
    accept = base64.b64encode(
        hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("utf-8")).digest()
    ).decode("ascii")
    assert "101 Switching Protocols" in response_text
    assert f"Sec-WebSocket-Accept: {accept}" in response_text
    return _WsClient(sock, buffered)


def _ws_send_json(sock: _WsClient, payload: dict) -> None:
    raw = json.dumps(payload).encode("utf-8")
    mask = b"\x01\x02\x03\x04"
    masked = bytes(byte ^ mask[idx % 4] for idx, byte in enumerate(raw))
    header = bytearray([0x81])
    length = len(raw)
    if length < 126:
        header.append(0x80 | length)
    elif length < 65536:
        header.append(0x80 | 126)
        header.extend(struct.pack("!H", length))
    else:
        header.append(0x80 | 127)
        header.extend(struct.pack("!Q", length))
    sock.sock.sendall(bytes(header) + mask + masked)


def _ws_recv_json(sock: _WsClient, *, timeout: float = 5.0) -> dict:
    header = sock.recv_exact(2, timeout=timeout)
    opcode = header[0] & 0x0F
    length = header[1] & 0x7F
    if length == 126:
        length = struct.unpack("!H", sock.recv_exact(2, timeout=timeout))[0]
    elif length == 127:
        length = struct.unpack("!Q", sock.recv_exact(8, timeout=timeout))[0]
    payload = sock.recv_exact(length, timeout=timeout)
    assert opcode == 0x1
    return json.loads(payload.decode("utf-8"))


@pytest.fixture(autouse=True)
def clean_remote_control_state():
    yield
    with server_mod._bridges_lock:
        for bridge in server_mod._bridges.values():
            bridge.stop.set()
        server_mod._bridges.clear()
    deadline = time.time() + 1.0
    while time.time() < deadline:
        if not any(thread.name.startswith("bridge-") for thread in threading.enumerate()):
            break
        time.sleep(0.05)
    with server_mod._backend_cache_lock:
        for backend in server_mod._backend_cache.values():
            procs = getattr(backend, "_procs", {})
            sessions = sorted({target.split(":", 1)[0] for target in procs})
            for session in sessions:
                try:
                    backend.kill_session(session)
                except Exception:
                    pass
        server_mod._backend_cache.clear()


@pytest.fixture
def mcp_server():
    port = _free_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), server_mod.MCPHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{port}/mcp"
    deadline = time.time() + 5.0
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=0.5) as resp:
                if resp.status == 200:
                    break
        except Exception:
            time.sleep(0.05)

    yield {"base_url": base_url, "port": port}

    server.shutdown()
    server.server_close()
    thread.join(timeout=2.0)


class TestRemoteControlMcp:
    def test_room_binding_and_duplicate_bridge_detection(self, mcp_server):
        base_url = mcp_server["base_url"]
        init = _tool(base_url, "terminal_init", {
            "session": "mcp-room-check",
            "backend": "pipe",
            "backend_id": "mcp-room-check",
        })
        first = _tool(base_url, "bridge_start", {
            "pane_a": init["pane_a"],
            "pane_b": init["pane_b"],
            "backend": "pipe",
            "backend_id": "mcp-room-check",
            "room_id": "mcp-room-check-room",
            "bridge_id": "mcp-room-check-bridge",
        })
        second = _tool(base_url, "bridge_start", {
            "pane_a": init["pane_a"],
            "pane_b": init["pane_b"],
            "backend": "pipe",
            "backend_id": "mcp-room-check",
            "room_id": "mcp-room-check-room",
        })
        conflict = _tool(base_url, "bridge_start", {
            "pane_a": init["pane_a"],
            "pane_b": init["pane_b"],
            "backend": "pipe",
            "backend_id": "mcp-room-check",
            "room_id": "mcp-room-other",
        })

        assert first == {
            "bridge_id": "mcp-room-check-bridge",
            "room_id": "mcp-room-check-room",
        }
        assert second == {
            "bridge_id": "mcp-room-check-bridge",
            "room_id": "mcp-room-check-room",
            "existing": True,
        }
        assert conflict["error"] == (
            "pane pair already bridged by mcp-room-check-bridge in room "
            "mcp-room-check-room; stop it first"
        )

    def test_midline_forwarding_once_via_mcp(self, mcp_server):
        base_url = mcp_server["base_url"]
        init = _tool(base_url, "terminal_init", {
            "session": "mcp-forward-check",
            "backend": "pipe",
            "backend_id": "mcp-forward-check",
        })
        start = _tool(base_url, "bridge_start", {
            "pane_a": init["pane_a"],
            "pane_b": init["pane_b"],
            "backend": "pipe",
            "backend_id": "mcp-forward-check",
            "room_id": "mcp-forward-room",
            "bridge_id": "mcp-forward-bridge",
            "auto_forward": True,
            "profile": "generic",
        })
        command = "echo agent^> MSG:echo REMOTE_OK" if os.name == "nt" else "printf 'agent> MSG:echo REMOTE_OK\\n'"
        sent = _tool(base_url, "terminal_send", {
            "target": init["pane_a"],
            "backend": "pipe",
            "backend_id": "mcp-forward-check",
            "text": command,
            "enter": True,
        })

        time.sleep(1.2)

        room = _tool(base_url, "room_poll", {
            "room_id": "mcp-forward-room",
            "after_id": 0,
            "limit": 50,
        })
        pane_b = _tool(base_url, "terminal_capture", {
            "target": init["pane_b"],
            "backend": "pipe",
            "backend_id": "mcp-forward-check",
            "lines": 50,
        })

        forwarded = [
            msg for msg in room["messages"]
            if msg["author"] == "bridge" and msg["text"] == "[forwarded A->mcp-forward-check:b] echo REMOTE_OK"
        ]
        outputs = [line for line in pane_b["lines"] if line == "REMOTE_OK"]

        assert start == {
            "bridge_id": "mcp-forward-bridge",
            "room_id": "mcp-forward-room",
        }
        assert sent == {"ok": True}
        assert len(forwarded) == 1
        assert outputs == ["REMOTE_OK"]

    def test_room_stream_sse_receives_live_room_events(self, mcp_server):
        base_url = mcp_server["base_url"]
        port = mcp_server["port"]
        _tool(base_url, "room_create", {"room_id": "sse-room"})

        stream = urllib.request.urlopen(
            urllib.request.Request(
                f"http://127.0.0.1:{port}/rooms/sse-room/stream?after_id=0&limit=50",
                headers={"Accept": "text/event-stream"},
            ),
            timeout=5,
        )
        try:
            event_name, payload = _read_sse_event(stream)
            assert event_name == "ready"
            assert payload["room_id"] == "sse-room"

            _tool(base_url, "room_post", {"room_id": "sse-room", "author": "host", "text": "hello live"})
            event_name, payload = _read_sse_event(stream)
            assert event_name == "room"
            assert payload["room_id"] == "sse-room"
            assert payload["text"] == "hello live"
            assert payload["author"] == "host"
        finally:
            stream.close()

    def test_websocket_subscribe_and_room_post(self, mcp_server):
        base_url = mcp_server["base_url"]
        port = mcp_server["port"]
        _tool(base_url, "room_create", {"room_id": "ws-room"})

        sock = _ws_handshake(port)
        try:
            ready = _ws_recv_json(sock)
            assert ready["type"] == "ready"

            _ws_send_json(sock, {"action": "subscribe", "room_id": "ws-room", "after_id": 0})
            subscribed = _ws_recv_json(sock)
            assert subscribed == {
                "type": "subscribed",
                "room_id": "ws-room",
                "latest_id": 0,
                "transport": "websocket",
            }

            _tool(base_url, "room_post", {"room_id": "ws-room", "author": "guest", "text": "from ws test"})
            room_event = _ws_recv_json(sock)
            assert room_event["type"] == "room_event"
            assert room_event["event"]["room_id"] == "ws-room"
            assert room_event["event"]["text"] == "from ws test"
        finally:
            sock.close()
