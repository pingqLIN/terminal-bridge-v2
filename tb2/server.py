"""MCP-compatible HTTP server for TerminalBridge v2.

Provides JSON-RPC endpoints for multi-agent room-based communication
with improved efficiency: per-room locks, bounded storage, session TTL.
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, List, Optional

from .backend import TerminalBackend, TmuxBackend, TmuxError
from .diff import diff_new_lines, strip_prompt_tail
from .intervention import Action, InterventionLayer
from .profile import get_profile, list_profiles, strip_ansi
from .room import Room, cleanup_stale, create_room, delete_room, get_room, list_rooms


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
                           meta={"pane": from_pane})
            if self.auto_forward:
                parsed = profile.parse_message(ln)
                if parsed:
                    msg = self.intervention_layer.submit(from_pane, to_pane, parsed)
                    if msg.action == Action.AUTO:
                        try:
                            self.backend.send(to_pane, parsed, enter=True)
                            self.room.post(author="bridge",
                                           text=f"[forwarded {tag}->{to_pane}] {parsed}",
                                           kind="system")
                        except TmuxError as exc:
                            self.room.post(author="bridge",
                                           text=f"[forward failed {tag}->{to_pane}] {exc}",
                                           kind="system")

            time.sleep(max(0.05, self._current_poll / 1000.0))


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_bridges_lock = threading.Lock()
_bridges: Dict[str, Bridge] = {}


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


def _deliver_pending(bridge: Bridge, msg: Any) -> None:
    text = msg.edited_text if msg.edited_text else msg.text
    bridge.backend.send(msg.to_pane, text, enter=True)
    bridge.room.post(
        author="bridge",
        text=f"[approved #{msg.id} -> {msg.to_pane}] {text}",
        kind="system",
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
        "messages": [
            {"id": m.id, "author": m.author, "text": m.text, "kind": m.kind, "ts": m.ts}
            for m in msgs
        ],
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
                if deliver in ("a", "A"):
                    bridge.backend.send(bridge.pane_a, msg.text, enter=True)
                elif deliver in ("b", "B"):
                    bridge.backend.send(bridge.pane_b, msg.text, enter=True)
                elif deliver == "both":
                    bridge.backend.send(bridge.pane_a, msg.text, enter=True)
                    bridge.backend.send(bridge.pane_b, msg.text, enter=True)
            except TmuxError as exc:
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
    room = get_room(str(args.get("room_id", "")))
    if not room:
        room = create_room()
    bridge_id = args.get("bridge_id") or uuid.uuid4().hex[:12]
    pane_a = str(args["pane_a"])
    pane_b = str(args["pane_b"])
    profile_name = str(args.get("profile", "generic"))

    bridge = Bridge(
        bridge_id=bridge_id,
        backend=backend,
        room=room,
        pane_a=pane_a,
        pane_b=pane_b,
        profile_name=profile_name,
        poll_ms=int(args.get("poll_ms", 400)),
        lines=int(args.get("lines", 200)),
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
    if mid == "all" or mid is None:
        approved = bridge.intervention_layer.approve_all()
    else:
        try:
            msg_id = int(mid)
        except (TypeError, ValueError):
            return {"error": "id must be an integer or 'all'"}
        msg = bridge.intervention_layer.approve(msg_id)
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
        rejected = 1

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
            bridge.room.post(author="bridge", text=f"[interrupt -> {pane}] ^C", kind="system")
            sent.append(pane)
        except Exception as exc:
            errors.append({"pane": pane, "error": str(exc)})

    return {"bridge_id": bridge_id, "sent": sent, "errors": errors, "ok": len(errors) == 0}


def handle_list_profiles(_args: Dict[str, Any]) -> Dict[str, Any]:
    return {"profiles": list_profiles()}


def handle_status(_args: Dict[str, Any]) -> Dict[str, Any]:
    rooms = list_rooms()
    with _bridges_lock:
        bridge_ids = list(_bridges.keys())
    return {
        "rooms": [{"id": r.room_id, "messages": r.message_count, "age": time.time() - r.created_at}
                  for r in rooms],
        "bridges": bridge_ids,
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
    "status": handle_status,
}


# ---------------------------------------------------------------------------
# HTTP handler (MCP JSON-RPC)
# ---------------------------------------------------------------------------

class MCPHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            req = json.loads(body)
        except json.JSONDecodeError:
            self._reply(400, {"error": "invalid JSON"})
            return

        method = req.get("method", "")
        params = req.get("params", {})
        req_id = req.get("id")

        # MCP tools/list
        if method == "tools/list":
            tools = [{"name": name} for name in HANDLERS]
            self._reply(200, {"jsonrpc": "2.0", "id": req_id,
                              "result": {"tools": tools}})
            return

        # MCP tools/call
        if method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})
            handler = HANDLERS.get(tool_name)
            if not handler:
                self._reply(200, {"jsonrpc": "2.0", "id": req_id,
                                  "error": {"code": -32601, "message": f"unknown tool: {tool_name}"}})
                return
            try:
                result = handler(tool_args)
            except Exception as exc:
                self._reply(200, {"jsonrpc": "2.0", "id": req_id,
                                  "error": {"code": -32000, "message": str(exc)}})
                return
            self._reply(200, {"jsonrpc": "2.0", "id": req_id, "result": result})
            return

        self._reply(200, {"jsonrpc": "2.0", "id": req_id,
                          "error": {"code": -32601, "message": f"unknown method: {method}"}})

    def _reply(self, code: int, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt: str, *args: Any) -> None:
        pass  # Quiet by default.


def run_server(host: str = "127.0.0.1", port: int = 3189) -> None:
    server = HTTPServer((host, port), MCPHandler)
    print(f"[tb2-server] listening on {host}:{port}/mcp")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
