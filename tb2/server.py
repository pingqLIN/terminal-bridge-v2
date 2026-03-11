"""MCP-compatible HTTP server for TerminalBridge v2.

Provides JSON-RPC endpoints for multi-agent room-based communication
with improved efficiency: per-room locks, bounded storage, session TTL.
"""

from __future__ import annotations

import base64
import hashlib
import json
import socket
import struct
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, unquote, urlparse

from .backend import TerminalBackend, TmuxBackend, TmuxError
from .diff import diff_new_lines, strip_prompt_tail
from .intervention import Action, InterventionLayer
from .profile import get_profile, list_profiles, strip_ansi
from .support import doctor_report
from .gui import build_gui_html
from .room import Room, RoomMessage, RoomSubscription, cleanup_stale, create_room, delete_room, get_room, list_rooms


# ---------------------------------------------------------------------------
# Bridge worker
# ---------------------------------------------------------------------------

class Bridge:
    def __init__(self, bridge_id: str, backend: TmuxBackend, room: Room,
                 pane_a: str, pane_b: str, *,
                 profile_name: str = "generic",
                 poll_ms: int = 400, lines: int = 200,
                 auto_forward: bool = False, intervention: bool = False):
        self.bridge_id = bridge_id
        self.backend = backend
        self.room = room
        self.pane_a = pane_a
        self.pane_b = pane_b
        self.profile_name = profile_name
        self.poll_ms = poll_ms
        self.lines = lines
        self.auto_forward = auto_forward
        self.intervention_layer = InterventionLayer(active=intervention)
        self.stop = threading.Event()
        self.prev_a: list = []
        self.prev_b: list = []
        self.forwarded_recent = deque(maxlen=80)
        # Adaptive polling
        self._current_poll: float = float(poll_ms)
        self._min_poll: float = 100.0
        self._max_poll: float = 3000.0

    def worker(self) -> None:
        profile = get_profile(self.profile_name)
        try:
            self.prev_a, self.prev_b = self.backend.capture_both(
                self.pane_a, self.pane_b, self.lines)
            self.prev_a = strip_prompt_tail(self.prev_a, profile.prompt_patterns)
            self.prev_b = strip_prompt_tail(self.prev_b, profile.prompt_patterns)
        except TmuxError:
            return

        while not self.stop.is_set():
            try:
                curr_a, curr_b = self.backend.capture_both(
                    self.pane_a, self.pane_b, self.lines)
            except TmuxError:
                break

            curr_a = strip_prompt_tail(curr_a, profile.prompt_patterns)
            curr_b = strip_prompt_tail(curr_b, profile.prompt_patterns)

            new_a = diff_new_lines(self.prev_a, curr_a)
            new_b = diff_new_lines(self.prev_b, curr_b)
            self.prev_a = curr_a
            self.prev_b = curr_b

            # Adaptive backoff
            if new_a or new_b:
                self._current_poll = self._min_poll
            else:
                self._current_poll = min(self._current_poll * 1.5, self._max_poll)

            self._process_new_lines("A", self.pane_a, self.pane_b, new_a, profile)
            self._process_new_lines("B", self.pane_b, self.pane_a, new_b, profile)

    def _process_new_lines(self, tag: str, from_pane: str, to_pane: str,
                           new_lines: list, profile: Any) -> None:
        for ln in new_lines:
            if not ln.strip():
                continue
            text = strip_ansi(ln) if profile.strip_ansi else ln
            self.room.post(author=tag, text=text, kind="terminal",
                           meta={"pane": from_pane, "bridge_id": self.bridge_id})
            if self.auto_forward:
                parsed = profile.parse_message(ln)
                if parsed:
                    fp = (tag, parsed)
                    if fp in self.forwarded_recent:
                        continue
                    self.forwarded_recent.append(fp)
                    msg = self.intervention_layer.submit(from_pane, to_pane, parsed)
                    if msg.action == Action.AUTO:
                        try:
                            self.backend.send(to_pane, parsed, enter=True)
                            self.room.post(author="bridge",
                                           text=f"[forwarded {tag}->{to_pane}] {parsed}",
                                           kind="system",
                                           meta={"bridge_id": self.bridge_id, "to_pane": to_pane})
                        except TmuxError as exc:
                            self.room.post(author="bridge",
                                           text=f"[forward failed {tag}->{to_pane}] {exc}",
                                           kind="system",
                                           meta={"bridge_id": self.bridge_id, "to_pane": to_pane})
                    else:
                        self.room.post(
                            author="bridge",
                            text=f"[pending #{msg.id} {tag}->{to_pane}] {parsed}",
                            kind="intervention",
                            meta={
                                "bridge_id": self.bridge_id,
                                "pending_id": msg.id,
                                "from_pane": from_pane,
                                "to_pane": to_pane,
                            },
                        )

            time.sleep(max(0.05, self._current_poll / 1000.0))


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_bridges_lock = threading.Lock()
_bridges: Dict[str, Bridge] = {}

_transport_lock = threading.Lock()
_sse_subscribers: Dict[str, int] = {}
_ws_subscribers: Dict[str, int] = {}
_ws_clients = 0


# ---------------------------------------------------------------------------
# Cleanup daemon
# ---------------------------------------------------------------------------

def _cleanup_daemon() -> None:
    while True:
        time.sleep(300)  # every 5 min
        cleanup_stale(ttl_seconds=3600)
        # Also stop bridges whose rooms are gone
        with _bridges_lock:
            stale = [bid for bid, b in _bridges.items() if get_room(b.room.room_id) is None]
            for bid in stale:
                _bridges[bid].stop.set()
                del _bridges[bid]


_cleanup_thread = threading.Thread(target=_cleanup_daemon, daemon=True)
_cleanup_thread.start()


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

_backend_cache: Dict[str, TerminalBackend] = {}
_backend_cache_lock = threading.Lock()


def _make_backend(args: Dict[str, Any]) -> TerminalBackend:
    """Get or create a backend instance. Cached by (kind, backend_id)."""
    kind = str(args.get("backend", "tmux"))
    backend_id = str(args.get("backend_id", "default"))
    key = f"{kind}:{backend_id}"

    with _backend_cache_lock:
        if key in _backend_cache:
            return _backend_cache[key]

        if kind == "process":
            from .process_backend import ProcessBackend
            b: TerminalBackend = ProcessBackend(shell=str(args.get("shell", "")))
        elif kind == "pipe":
            from .pipe_backend import PipeBackend
            b = PipeBackend(shell=str(args.get("shell", "")))
        else:
            kwargs = {}
            if "distro" in args:
                kwargs["distro"] = args["distro"]
            b = TmuxBackend(**kwargs)

        _backend_cache[key] = b
        return b


def _get_bridge(bridge_id: str) -> Optional[Bridge]:
    with _bridges_lock:
        return _bridges.get(bridge_id)


def _pending_to_dict(msg: Any) -> Dict[str, Any]:
    return {
        "id": msg.id,
        "from_pane": msg.from_pane,
        "to_pane": msg.to_pane,
        "text": msg.text,
        "action": msg.action.value,
        "edited_text": msg.edited_text,
        "created_at": msg.created_at,
    }


def _room_message_payload(room: Room, msg: RoomMessage) -> Dict[str, Any]:
    meta = dict(msg.meta)
    bridge_id = meta.get("bridge_id")
    return {
        "event_id": f"{room.room_id}:{msg.id}",
        "id": msg.id,
        "room_id": room.room_id,
        "bridge_id": bridge_id,
        "author": msg.author,
        "text": msg.text,
        "kind": msg.kind,
        "meta": meta,
        "created_at": msg.ts,
        "ts": msg.ts,
    }


def _transport_counter(store: Dict[str, int], room_id: str, delta: int) -> None:
    with _transport_lock:
        next_value = store.get(room_id, 0) + delta
        if next_value <= 0:
            store.pop(room_id, None)
        else:
            store[room_id] = next_value


def _ws_client_delta(delta: int) -> None:
    global _ws_clients
    with _transport_lock:
        _ws_clients = max(0, _ws_clients + delta)


def _transport_snapshot() -> Dict[str, Any]:
    with _transport_lock:
        sse = dict(_sse_subscribers)
        ws = dict(_ws_subscribers)
        ws_clients = _ws_clients
    room_ids = sorted(set(sse) | set(ws))
    return {
        "sse_subscribers": sum(sse.values()),
        "websocket_clients": ws_clients,
        "rooms": [
            {
                "room_id": room_id,
                "sse": sse.get(room_id, 0),
                "websocket": ws.get(room_id, 0),
                "total": sse.get(room_id, 0) + ws.get(room_id, 0),
            }
            for room_id in room_ids
        ],
    }


def _deliver_pending(bridge: Bridge, msg: Any) -> None:
    text = msg.edited_text if msg.edited_text else msg.text
    bridge.backend.send(msg.to_pane, text, enter=True)
    bridge.room.post(
        author="bridge",
        text=f"[approved #{msg.id} -> {msg.to_pane}] {text}",
        kind="intervention",
        meta={"bridge_id": bridge.bridge_id, "pending_id": msg.id, "to_pane": msg.to_pane},
    )


def handle_terminal_init(args: Dict[str, Any]) -> Dict[str, Any]:
    backend = _make_backend(args)
    session = str(args.get("session", "tb2"))
    a, b = backend.init_session(session)
    return {"session": session, "pane_a": a, "pane_b": b}


def handle_terminal_capture(args: Dict[str, Any]) -> Dict[str, Any]:
    backend = _make_backend(args)
    target = str(args["target"])
    lines = int(args.get("lines", 200))
    captured = backend.capture(target, lines)
    return {"lines": captured, "count": len(captured)}


def handle_terminal_send(args: Dict[str, Any]) -> Dict[str, Any]:
    backend = _make_backend(args)
    target = str(args["target"])
    text = str(args["text"])
    enter = bool(args.get("enter", False))
    backend.send(target, text, enter=enter)
    return {"ok": True}


def handle_room_create(args: Dict[str, Any]) -> Dict[str, Any]:
    room_id = args.get("room_id")
    room = create_room(room_id)
    return {"room_id": room.room_id}


def handle_room_poll(args: Dict[str, Any]) -> Dict[str, Any]:
    room = get_room(str(args["room_id"]))
    if not room:
        return {"error": "room not found"}
    try:
        after_id = int(args.get("after_id", 0))
        limit = int(args.get("limit", 50))
    except (ValueError, TypeError):
        return {"error": "after_id and limit must be integers"}
    msgs = room.poll(after_id=after_id, limit=limit)
    return {
        "messages": [_room_message_payload(room, m) for m in msgs],
        "latest_id": room.latest_id,
    }


def handle_room_post(args: Dict[str, Any]) -> Dict[str, Any]:
    room = get_room(str(args["room_id"]))
    if not room:
        return {"error": "room not found"}
    msg = room.post(
        author=str(args.get("author", "user")),
        text=str(args["text"]),
        kind=str(args.get("kind", "chat")),
    )
    # Optionally deliver to a bridge pane
    deliver = args.get("deliver")
    bridge_id = args.get("bridge_id")
    deliver_error = None
    if deliver and bridge_id:
        with _bridges_lock:
            bridge = _bridges.get(bridge_id)
        if bridge:
            try:
                if bridge.room.room_id != room.room_id:
                    deliver_error = (
                        f"bridge {bridge_id} belongs to room {bridge.room.room_id}, not {room.room_id}"
                    )
                elif deliver in ("a", "A"):
                    bridge.backend.send(bridge.pane_a, msg.text, enter=True)
                elif deliver in ("b", "B"):
                    bridge.backend.send(bridge.pane_b, msg.text, enter=True)
                elif str(deliver).lower() == "both":
                    bridge.backend.send(bridge.pane_a, msg.text, enter=True)
                    bridge.backend.send(bridge.pane_b, msg.text, enter=True)
                else:
                    deliver_error = "deliver must be one of: a, b, both"
            except Exception as exc:
                deliver_error = str(exc)
        else:
            deliver_error = f"bridge {bridge_id} not found"
    result: Dict[str, Any] = {"id": msg.id}
    if deliver_error:
        result["deliver_error"] = deliver_error
    return result


def handle_bridge_start(args: Dict[str, Any]) -> Dict[str, Any]:
    import uuid
    backend = _make_backend(args)
    pane_a = str(args["pane_a"])
    pane_b = str(args["pane_b"])
    requested_room_id = str(args.get("room_id", "")).strip()
    requested_bridge_id = str(args.get("bridge_id", "")).strip()
    room = create_room(requested_room_id) if requested_room_id else create_room()
    bridge_id = requested_bridge_id or uuid.uuid4().hex[:12]
    profile_name = str(args.get("profile", "generic"))
    poll_ms = int(args.get("poll_ms", 400))
    lines = int(args.get("lines", 200))

    with _bridges_lock:
        if requested_bridge_id and requested_bridge_id in _bridges:
            existing = _bridges[requested_bridge_id]
            if existing.backend is backend and existing.pane_a == pane_a and existing.pane_b == pane_b:
                return {"bridge_id": existing.bridge_id, "room_id": existing.room.room_id, "existing": True}
            return {"error": f"bridge_id already exists: {requested_bridge_id}"}

        for existing in _bridges.values():
            if existing.backend is not backend:
                continue
            if existing.pane_a != pane_a or existing.pane_b != pane_b:
                continue
            if requested_room_id and existing.room.room_id != requested_room_id:
                return {
                    "error": (
                        f"pane pair already bridged by {existing.bridge_id} "
                        f"in room {existing.room.room_id}; stop it first"
                    )
                }
            return {"bridge_id": existing.bridge_id, "room_id": existing.room.room_id, "existing": True}

    try:
        backend.capture_both(pane_a, pane_b, lines)
    except Exception as exc:
        return {"error": f"bridge preflight failed: {exc}"}

    bridge = Bridge(
        bridge_id=bridge_id,
        backend=backend,
        room=room,
        pane_a=pane_a,
        pane_b=pane_b,
        profile_name=profile_name,
        poll_ms=poll_ms,
        lines=lines,
        auto_forward=bool(args.get("auto_forward", False)),
        intervention=bool(args.get("intervention", False)),
    )
    with _bridges_lock:
        _bridges[bridge_id] = bridge
    t = threading.Thread(target=bridge.worker, daemon=True, name=f"bridge-{bridge_id}")
    t.start()
    return {"bridge_id": bridge_id, "room_id": room.room_id}


def handle_bridge_stop(args: Dict[str, Any]) -> Dict[str, Any]:
    bridge_id = str(args["bridge_id"])
    with _bridges_lock:
        bridge = _bridges.pop(bridge_id, None)
    if bridge:
        bridge.stop.set()
        return {"ok": True}
    return {"error": "bridge not found"}


def handle_intervention_list(args: Dict[str, Any]) -> Dict[str, Any]:
    bridge_id = str(args["bridge_id"])
    bridge = _get_bridge(bridge_id)
    if not bridge:
        return {"error": "bridge not found"}
    pending = bridge.intervention_layer.list_pending()
    return {
        "bridge_id": bridge_id,
        "pending": [_pending_to_dict(msg) for msg in pending],
        "count": len(pending),
    }


def handle_intervention_approve(args: Dict[str, Any]) -> Dict[str, Any]:
    bridge_id = str(args["bridge_id"])
    bridge = _get_bridge(bridge_id)
    if not bridge:
        return {"error": "bridge not found"}

    mid = args.get("id", "all")
    edited_text = args.get("edited_text")
    if edited_text is not None and mid in ("all", None):
        return {"error": "edited_text requires a specific pending message id"}
    if mid == "all" or mid is None:
        approved = bridge.intervention_layer.approve_all()
    else:
        try:
            msg_id = int(mid)
        except (TypeError, ValueError):
            return {"error": "id must be an integer or 'all'"}
        msg = bridge.intervention_layer.approve(msg_id, edited_text=str(edited_text) if edited_text is not None else None)
        if not msg:
            return {"error": f"pending message {msg_id} not found"}
        approved = [msg]

    delivered: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    for msg in approved:
        try:
            _deliver_pending(bridge, msg)
            delivered.append({"id": msg.id, "to_pane": msg.to_pane})
        except Exception as exc:
            errors.append({"id": msg.id, "error": str(exc)})

    return {
        "bridge_id": bridge_id,
        "approved": len(approved),
        "delivered": delivered,
        "errors": errors,
        "remaining": len(bridge.intervention_layer.list_pending()),
    }


def handle_intervention_reject(args: Dict[str, Any]) -> Dict[str, Any]:
    bridge_id = str(args["bridge_id"])
    bridge = _get_bridge(bridge_id)
    if not bridge:
        return {"error": "bridge not found"}

    mid = args.get("id", "all")
    if mid == "all" or mid is None:
        rejected = bridge.intervention_layer.reject_all()
    else:
        try:
            msg_id = int(mid)
        except (TypeError, ValueError):
            return {"error": "id must be an integer or 'all'"}
        msg = bridge.intervention_layer.reject(msg_id)
        if not msg:
            return {"error": f"pending message {msg_id} not found"}
        bridge.room.post(
            author="bridge",
            text=f"[rejected #{msg.id}] {msg.text}",
            kind="intervention",
            meta={"bridge_id": bridge.bridge_id, "pending_id": msg.id, "to_pane": msg.to_pane},
        )
        rejected = 1
    if rejected and (mid == "all" or mid is None):
        bridge.room.post(
            author="bridge",
            text=f"[rejected {rejected} pending message(s)]",
            kind="intervention",
            meta={"bridge_id": bridge.bridge_id},
        )

    return {
        "bridge_id": bridge_id,
        "rejected": rejected,
        "remaining": len(bridge.intervention_layer.list_pending()),
    }


def handle_terminal_interrupt(args: Dict[str, Any]) -> Dict[str, Any]:
    bridge_id = str(args["bridge_id"])
    bridge = _get_bridge(bridge_id)
    if not bridge:
        return {"error": "bridge not found"}

    target = args.get("target", "both")
    panes: List[str]
    if target in ("a", "A"):
        panes = [bridge.pane_a]
    elif target in ("b", "B"):
        panes = [bridge.pane_b]
    elif target in ("both", "all", None):
        panes = [bridge.pane_a, bridge.pane_b]
    else:
        panes = [str(target)]

    sent: List[str] = []
    errors: List[Dict[str, str]] = []
    for pane in panes:
        try:
            bridge.backend.send(pane, "\x03", enter=False)
            bridge.room.post(
                author="bridge",
                text=f"[interrupt -> {pane}] ^C",
                kind="system",
                meta={"bridge_id": bridge.bridge_id, "pane": pane},
            )
            sent.append(pane)
        except Exception as exc:
            errors.append({"pane": pane, "error": str(exc)})

    return {"bridge_id": bridge_id, "sent": sent, "errors": errors, "ok": len(errors) == 0}


def handle_list_profiles(_args: Dict[str, Any]) -> Dict[str, Any]:
    return {"profiles": list_profiles()}


def handle_doctor(args: Dict[str, Any]) -> Dict[str, Any]:
    distro = args.get("distro")
    return doctor_report(distro=str(distro) if distro else None)


def handle_status(_args: Dict[str, Any]) -> Dict[str, Any]:
    rooms = list_rooms()
    with _bridges_lock:
        bridge_ids = list(_bridges.keys())
    transports = _transport_snapshot()
    transport_by_room = {item["room_id"]: item for item in transports["rooms"]}
    return {
        "rooms": [{"id": r.room_id, "messages": r.message_count, "age": time.time() - r.created_at,
                   "subscribers": transport_by_room.get(
                       r.room_id,
                       {"room_id": r.room_id, "sse": 0, "websocket": 0, "total": 0},
                   )}
                  for r in rooms],
        "bridges": bridge_ids,
        "transports": transports,
    }


HANDLERS = {
    "terminal_init": handle_terminal_init,
    "terminal_capture": handle_terminal_capture,
    "terminal_send": handle_terminal_send,
    "terminal_interrupt": handle_terminal_interrupt,
    "room_create": handle_room_create,
    "room_poll": handle_room_poll,
    "room_post": handle_room_post,
    "bridge_start": handle_bridge_start,
    "bridge_stop": handle_bridge_stop,
    "intervention_list": handle_intervention_list,
    "intervention_approve": handle_intervention_approve,
    "intervention_reject": handle_intervention_reject,
    "list_profiles": handle_list_profiles,
    "doctor": handle_doctor,
    "status": handle_status,
}

TOOL_DESCRIPTIONS = {
    "terminal_init": "Create a terminal session with pane A and pane B.",
    "terminal_capture": "Capture recent lines from a target pane.",
    "terminal_send": "Send text to a target pane.",
    "terminal_interrupt": "Send Ctrl+C to one or both panes of a bridge.",
    "room_create": "Create a chat room buffer.",
    "room_poll": "Poll room messages after a cursor id.",
    "room_post": "Post a message to a room and optionally deliver to pane(s).",
    "bridge_start": "Start background bridge worker between two panes.",
    "bridge_stop": "Stop a running bridge worker.",
    "intervention_list": "List pending human-review messages.",
    "intervention_approve": "Approve pending message(s) for delivery.",
    "intervention_reject": "Reject pending message(s).",
    "list_profiles": "List available parsing profiles.",
    "doctor": "Report local backend support and first-class CLI compatibility.",
    "status": "Return active rooms and bridge ids.",
}

_DEFAULT_TOOL_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {},
    "additionalProperties": True,
}

SERVER_INFO = {"name": "terminal-bridge-v2", "version": "0.1.0"}
LATEST_PROTOCOL_VERSION = "2025-11-25"


def _tool_specs() -> List[Dict[str, Any]]:
    tools: List[Dict[str, Any]] = []
    for name in HANDLERS:
        tools.append({
            "name": name,
            "description": TOOL_DESCRIPTIONS.get(name, name),
            "inputSchema": _DEFAULT_TOOL_SCHEMA,
        })
    return tools


def _as_tool_text(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    try:
        return json.dumps(payload, ensure_ascii=False, indent=2)
    except TypeError:
        return str(payload)


def _as_structured_content(payload: Any) -> Dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    return {"result": payload}


def _tool_call_result(payload: Any, *, is_error: bool = False) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "content": [{"type": "text", "text": _as_tool_text(payload)}],
        "structuredContent": _as_structured_content(payload),
    }
    if is_error:
        result["isError"] = True
    return result


def _looks_like_tool_error(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    err = payload.get("error")
    return isinstance(err, str) and bool(err.strip())


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload).encode("utf-8")


def _parse_room_stream_request(path: str, query: str) -> Tuple[Optional[str], int, int]:
    if not path.startswith("/rooms/") or not path.endswith("/stream"):
        return None, 0, 0
    room_id = unquote(path[len("/rooms/"):-len("/stream")]).strip("/")
    params = parse_qs(query)
    after_id = int(params.get("after_id", ["0"])[0] or 0)
    backlog_limit = int(params.get("limit", ["200"])[0] or 200)
    return room_id, after_id, backlog_limit


def _sse_bytes(event_name: str, payload: Dict[str, Any], *, event_id: Optional[str] = None) -> bytes:
    lines: List[str] = []
    if event_id:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event_name}")
    data = json.dumps(payload, ensure_ascii=False)
    for line in data.splitlines():
        lines.append(f"data: {line}")
    lines.append("")
    lines.append("")
    return "\n".join(lines).encode("utf-8")


def _ws_accept_value(key: str) -> str:
    guid = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
    digest = hashlib.sha1((key + guid).encode("utf-8")).digest()
    return base64.b64encode(digest).decode("ascii")


def _ws_read_exact(stream: Any, size: int) -> bytes:
    chunks: List[bytes] = []
    remaining = size
    while remaining > 0:
        chunk = stream.read(remaining)
        if not chunk:
            raise EOFError("websocket closed")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _ws_read_frame(stream: Any) -> Tuple[int, bytes]:
    header = _ws_read_exact(stream, 2)
    first, second = header[0], header[1]
    opcode = first & 0x0F
    masked = (second & 0x80) != 0
    length = second & 0x7F
    if length == 126:
        length = struct.unpack("!H", _ws_read_exact(stream, 2))[0]
    elif length == 127:
        length = struct.unpack("!Q", _ws_read_exact(stream, 8))[0]
    mask = _ws_read_exact(stream, 4) if masked else b""
    payload = _ws_read_exact(stream, length) if length else b""
    if masked:
        payload = bytes(byte ^ mask[idx % 4] for idx, byte in enumerate(payload))
    return opcode, payload


def _ws_frame(payload: bytes, *, opcode: int = 0x1) -> bytes:
    header = bytearray([0x80 | (opcode & 0x0F)])
    length = len(payload)
    if length < 126:
        header.append(length)
    elif length < 65536:
        header.append(126)
        header.extend(struct.pack("!H", length))
    else:
        header.append(127)
        header.extend(struct.pack("!Q", length))
    return bytes(header) + payload


def _handle_get_path(path: str) -> Tuple[int, str, bytes]:
    if path in ("", "/", "/ui", "/index.html"):
        html = build_gui_html("/mcp").encode("utf-8")
        return 200, "text/html; charset=utf-8", html

    if path == "/healthz":
        return 200, "application/json", _json_bytes({"ok": True})

    if path == "/mcp":
        return 200, "application/json", _json_bytes({
            "ok": True,
            "service": "terminal-bridge-v2",
            "endpoint": "/mcp",
            "ui": "/",
            "rooms_stream": "/rooms/{room_id}/stream",
            "websocket": "/ws",
        })

    return 404, "application/json", _json_bytes({
        "error": "not found",
        "path": path,
    })


# ---------------------------------------------------------------------------
# HTTP handler (MCP JSON-RPC)
# ---------------------------------------------------------------------------

class MCPHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        room_id, after_id, backlog_limit = _parse_room_stream_request(path, parsed.query)
        if room_id is not None:
            self._serve_room_sse(room_id, after_id=after_id, backlog_limit=backlog_limit)
            return
        if path == "/ws":
            self._serve_websocket()
            return
        code, content_type, body = _handle_get_path(path)
        self._reply_raw(code, content_type, body)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path != "/mcp":
            self._reply(404, {"error": "not found", "path": path})
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            req = json.loads(body)
        except json.JSONDecodeError:
            self._reply(400, {"error": "invalid JSON"})
            return

        # JSON-RPC batch support
        if isinstance(req, list):
            responses: List[Dict[str, Any]] = []
            for item in req:
                if not isinstance(item, dict):
                    responses.append({
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {"code": -32600, "message": "invalid request"},
                    })
                    continue
                res = self._handle_rpc(item)
                if res is not None:
                    responses.append(res)
            if responses:
                self._reply(200, responses)
            else:
                self._reply_empty(202)
            return

        if not isinstance(req, dict):
            self._reply(200, {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32600, "message": "invalid request"},
            })
            return

        response = self._handle_rpc(req)
        if response is None:
            self._reply_empty(202)
            return
        self._reply(200, response)

    def _handle_rpc(self, req: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        method = str(req.get("method", ""))
        params = req.get("params", {})
        req_id = req.get("id")
        is_notification = "id" not in req
        if not isinstance(params, dict):
            params = {}

        # MCP initialize handshake
        if method == "initialize":
            protocol = str(params.get("protocolVersion", LATEST_PROTOCOL_VERSION))
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": protocol,
                    "capabilities": {
                        "tools": {"listChanged": False},
                        "resources": {},
                        "prompts": {},
                    },
                    "serverInfo": SERVER_INFO,
                },
            }

        # MCP lifecycle notification
        if method == "notifications/initialized":
            if is_notification:
                return None
            return {"jsonrpc": "2.0", "id": req_id, "result": {}}

        # MCP ping
        if method == "ping":
            return {"jsonrpc": "2.0", "id": req_id, "result": {}}

        # MCP tools/list
        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": _tool_specs()}}

        # MCP tools/call
        if method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})
            if not isinstance(tool_name, str) or not tool_name:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32602, "message": "tools/call requires a non-empty string name"},
                }
            if not isinstance(tool_args, dict):
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32602, "message": "tools/call arguments must be an object"},
                }
            handler = HANDLERS.get(tool_name)
            if not handler:
                payload = {"error": f"unknown tool: {tool_name}", "tool": tool_name}
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": _tool_call_result(payload, is_error=True),
                }
            try:
                payload = handler(tool_args)
            except Exception as exc:
                payload = {"error": str(exc), "tool": tool_name}
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": _tool_call_result(payload, is_error=True),
                }
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": _tool_call_result(payload, is_error=_looks_like_tool_error(payload)),
            }

        # Optional lists for clients that probe server capabilities
        if method == "resources/list":
            return {"jsonrpc": "2.0", "id": req_id, "result": {"resources": []}}
        if method == "prompts/list":
            return {"jsonrpc": "2.0", "id": req_id, "result": {"prompts": []}}

        # Ignore unknown notifications to avoid noisy disconnects.
        if is_notification:
            return None
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"unknown method: {method}"},
        }

    def _reply(self, code: int, body: Any) -> None:
        data = json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _reply_raw(self, code: int, content_type: str, body: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _reply_empty(self, code: int) -> None:
        self.send_response(code)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _serve_room_sse(self, room_id: str, *, after_id: int, backlog_limit: int) -> None:
        room = get_room(room_id)
        if not room:
            self._reply(404, {"error": "room not found", "room_id": room_id})
            return

        last_event_id = self.headers.get("Last-Event-ID", "").strip()
        if last_event_id and ":" in last_event_id:
            _, _, tail = last_event_id.rpartition(":")
            if tail.isdigit():
                after_id = max(after_id, int(tail))

        try:
            sub = room.subscribe(after_id=after_id, backlog_limit=backlog_limit)
        except RuntimeError:
            self._reply(410, {"error": "room closed", "room_id": room_id})
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        self.wfile.flush()
        _transport_counter(_sse_subscribers, room_id, 1)
        try:
            ready = {
                "type": "ready",
                "room_id": room_id,
                "latest_id": room.latest_id,
                "transport": "sse",
            }
            self.wfile.write(_sse_bytes("ready", ready))
            self.wfile.flush()
            while True:
                try:
                    items = sub.get(timeout=15.0, limit=100)
                except EOFError:
                    break
                if not items:
                    self.wfile.write(b": keep-alive\n\n")
                    self.wfile.flush()
                    continue
                for msg in items:
                    payload = _room_message_payload(room, msg)
                    self.wfile.write(_sse_bytes("room", payload, event_id=payload["event_id"]))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            sub.close()
            _transport_counter(_sse_subscribers, room_id, -1)

    def _serve_websocket(self) -> None:
        upgrade = self.headers.get("Upgrade", "")
        key = self.headers.get("Sec-WebSocket-Key", "")
        if upgrade.lower() != "websocket" or not key:
            self._reply(400, {"error": "websocket upgrade required"})
            return

        self.send_response(101, "Switching Protocols")
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", _ws_accept_value(key))
        self.end_headers()
        self.connection.settimeout(0.5)
        _ws_client_delta(1)
        subscriptions: Dict[str, RoomSubscription] = {}
        try:
            self._ws_send({"type": "ready", "transport": "websocket"})
            while True:
                self._ws_flush_room_events(subscriptions)
                try:
                    opcode, payload = _ws_read_frame(self.rfile)
                except socket.timeout:
                    continue
                except EOFError:
                    break
                if opcode == 0x8:
                    break
                if opcode == 0x9:
                    self.wfile.write(_ws_frame(payload, opcode=0xA))
                    self.wfile.flush()
                    continue
                if opcode != 0x1:
                    self._ws_send({"type": "error", "error": f"unsupported websocket opcode: {opcode}"})
                    continue
                try:
                    message = json.loads(payload.decode("utf-8"))
                except json.JSONDecodeError:
                    self._ws_send({"type": "error", "error": "invalid websocket JSON"})
                    continue
                self._handle_ws_message(message, subscriptions)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            for room_id, sub in list(subscriptions.items()):
                sub.close()
                _transport_counter(_ws_subscribers, room_id, -1)
            _ws_client_delta(-1)

    def _handle_ws_message(self, message: Dict[str, Any], subscriptions: Dict[str, RoomSubscription]) -> None:
        action = str(message.get("action", "")).strip()
        if not action:
            self._ws_send({"type": "error", "error": "missing websocket action"})
            return

        if action == "subscribe":
            room_id = str(message.get("room_id", "")).strip()
            if not room_id:
                self._ws_send({"type": "error", "error": "room_id is required", "action": action})
                return
            room = get_room(room_id)
            if not room:
                self._ws_send({"type": "error", "error": "room not found", "room_id": room_id, "action": action})
                return
            after_id = int(message.get("after_id", 0))
            backlog_limit = int(message.get("limit", 200))
            existing = subscriptions.pop(room_id, None)
            if existing is not None:
                existing.close()
                _transport_counter(_ws_subscribers, room_id, -1)
            subscriptions[room_id] = room.subscribe(after_id=after_id, backlog_limit=backlog_limit)
            _transport_counter(_ws_subscribers, room_id, 1)
            self._ws_send(
                {
                    "type": "subscribed",
                    "room_id": room_id,
                    "latest_id": room.latest_id,
                    "transport": "websocket",
                }
            )
            return

        if action == "unsubscribe":
            room_id = str(message.get("room_id", "")).strip()
            sub = subscriptions.pop(room_id, None)
            if sub is not None:
                sub.close()
                _transport_counter(_ws_subscribers, room_id, -1)
            self._ws_send({"type": "unsubscribed", "room_id": room_id})
            return

        action_map = {
            "room_post": handle_room_post,
            "intervention_list": handle_intervention_list,
            "intervention_approve": handle_intervention_approve,
            "intervention_reject": handle_intervention_reject,
            "status": handle_status,
        }
        handler = action_map.get(action)
        if handler is None:
            self._ws_send({"type": "error", "error": f"unknown websocket action: {action}", "action": action})
            return
        payload = {k: v for k, v in message.items() if k != "action"}
        try:
            result = handler(payload)
        except Exception as exc:
            self._ws_send({"type": "error", "error": str(exc), "action": action})
            return
        self._ws_send({"type": "result", "action": action, "result": result, "ok": not _looks_like_tool_error(result)})

    def _ws_flush_room_events(self, subscriptions: Dict[str, RoomSubscription]) -> None:
        for room_id, sub in list(subscriptions.items()):
            room = get_room(room_id)
            if room is None:
                sub.close()
                subscriptions.pop(room_id, None)
                _transport_counter(_ws_subscribers, room_id, -1)
                self._ws_send({"type": "room_closed", "room_id": room_id})
                continue
            try:
                items = sub.get(timeout=0.0, limit=100)
            except EOFError:
                subscriptions.pop(room_id, None)
                _transport_counter(_ws_subscribers, room_id, -1)
                continue
            for msg in items:
                self._ws_send({"type": "room_event", "event": _room_message_payload(room, msg)})

    def _ws_send(self, payload: Dict[str, Any]) -> None:
        frame = _ws_frame(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        self.wfile.write(frame)
        self.wfile.flush()

    def log_message(self, fmt: str, *args: Any) -> None:
        pass  # Quiet by default.


def run_server(host: str = "127.0.0.1", port: int = 3189) -> None:
    server = ThreadingHTTPServer((host, port), MCPHandler)
    print(f"[tb2-server] listening on {host}:{port}/mcp")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
