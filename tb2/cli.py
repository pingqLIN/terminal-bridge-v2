"""CLI entry point for TerminalBridge v2.

Usage:
    python -m tb2 init [--session NAME]
    python -m tb2 list [--session NAME]
    python -m tb2 capture --target TARGET [--lines N]
    python -m tb2 send --target TARGET --text TEXT [--enter]
    python -m tb2 room {watch,post,pending,approve,reject} [...]
    python -m tb2 broker --a TARGET --b TARGET [--profile NAME] [--auto] [--intervention]
    python -m tb2 service {start,stop,status,restart,logs,audit} [...]
    python -m tb2 gui [--host ADDR] [--port PORT] [--no-browser]
    python -m tb2 profiles [--verbose]
    python -m tb2 doctor [--json]
    python -m tb2 governance resolve [--model NAME] [--environment NAME] [--instruction-profile NAME] [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Sequence

from .backend import TmuxBackend, TmuxError
from .broker import BrokerConfig, broker_loop
from .governance import resolve_governance
from .governance import governance_overlay_schema, governance_sample_overlay
from .osutils import default_backend_name
from .profile import list_profiles
from .support import doctor_report, profile_rows, render_doctor


def cmd_init(backend: TmuxBackend, args: argparse.Namespace) -> int:
    a, b = backend.init_session(args.session)
    print("OK")
    print(f"session: {args.session}")
    print(f"pane A:  {a}")
    print(f"pane B:  {b}")
    if isinstance(backend, TmuxBackend):
        print(f"\nAttach:  tmux attach -t {args.session}")
    else:
        print("\nNext:    use `tb2 capture`, `tb2 send`, `tb2 broker`, or the GUI/service flow")
    return 0


def cmd_list(backend: TmuxBackend, args: argparse.Namespace) -> int:
    panes = backend.list_panes(args.session)
    for target, title in panes:
        print(f"{target}\t{title}" if title else target)
    return 0


def cmd_capture(backend: TmuxBackend, args: argparse.Namespace) -> int:
    lines = backend.capture(args.target, args.lines)
    for ln in lines:
        print(ln)
    return 0


def cmd_send(backend: TmuxBackend, args: argparse.Namespace) -> int:
    backend.send(args.target, args.text, enter=args.enter)
    return 0


def cmd_broker(backend: TmuxBackend, args: argparse.Namespace) -> int:
    cfg = BrokerConfig(
        target_a=args.a,
        target_b=args.b,
        profile=args.profile,
        poll_ms=args.poll_ms,
        capture_lines=args.lines,
        auto_forward=args.auto,
        intervention=args.intervention,
    )
    return broker_loop(backend, cfg)


def cmd_profiles(_backend: TmuxBackend, args: argparse.Namespace) -> int:
    if not args.verbose:
        for name in list_profiles():
            print(f"  {name}")
        return 0

    for row in profile_rows():
        print(f"{row['profile']}\t{row['tool']}\t{row['support']}\t{row['recommended_backend']}")
    return 0


def cmd_server(_backend: TmuxBackend, args: argparse.Namespace) -> int:
    from .server import run_server
    run_server(host=args.host, port=args.port, allow_remote=bool(args.allow_remote))
    return 0


def cmd_gui(_backend: TmuxBackend, args: argparse.Namespace) -> int:
    import threading
    import webbrowser
    from .server import run_server

    url = f"http://{args.host}:{args.port}/"
    print(f"GUI: {url}")
    if not args.no_browser:
        timer = threading.Timer(0.6, lambda: webbrowser.open(url))
        timer.daemon = True
        timer.start()

    run_server(host=args.host, port=args.port, allow_remote=bool(args.allow_remote))
    return 0


def cmd_service(_backend: TmuxBackend, args: argparse.Namespace) -> int:
    from .audit import tail_events
    from .service import restart_service, start_service, status_service, stop_service, tail_log

    if args.service_cmd == "start":
        st = start_service(
            host=args.host,
            port=args.port,
            python_exe=args.python,
            force=args.force,
            allow_remote=bool(args.allow_remote),
        )
        print(json.dumps({"action": "start", **st.to_dict()}, ensure_ascii=False))
        return 0

    if args.service_cmd == "stop":
        st = stop_service(timeout=float(args.timeout))
        print(json.dumps({"action": "stop", **st.to_dict()}, ensure_ascii=False))
        return 0

    if args.service_cmd == "restart":
        st = restart_service(
            host=args.host,
            port=args.port,
            python_exe=args.python,
            allow_remote=args.allow_remote,
        )
        print(json.dumps({"action": "restart", **st.to_dict()}, ensure_ascii=False))
        return 0

    if args.service_cmd == "logs":
        for line in tail_log(lines=int(args.lines)):
            print(line)
        return 0

    if args.service_cmd == "audit":
        for item in tail_events(
            limit=int(args.lines),
            room_id=str(args.room_id),
            bridge_id=str(args.bridge_id),
            event=str(args.event),
        ):
            print(json.dumps(item, ensure_ascii=False))
        return 0

    st = status_service()
    print(json.dumps({"action": "status", **st.to_dict()}, ensure_ascii=False))
    return 0


def cmd_doctor(_backend: TmuxBackend, args: argparse.Namespace) -> int:
    report = doctor_report(distro=args.distro)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    print(render_doctor(report))
    return 0


def cmd_governance(_backend: TmuxBackend, args: argparse.Namespace) -> int:
    if args.governance_cmd == "schema":
        print(json.dumps(governance_overlay_schema(), ensure_ascii=False, indent=2))
        return 0
    if args.governance_cmd == "sample":
        print(json.dumps(governance_sample_overlay(), ensure_ascii=False, indent=2))
        return 0
    try:
        result = resolve_governance(
            model=args.model,
            environment=args.environment,
            instruction_profile=args.instruction_profile,
            config_path=args.config,
        )
    except ValueError as exc:
        if args.json:
            print(json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2))
            return 1
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    print("matched_layers:")
    for item in result["matched_layers"]:
        print(f"  - {item['layer']}: {item['name']}")
    if result["missing_layers"]:
        print("missing_layers:")
        for item in result["missing_layers"]:
            print(f"  - {item['layer']}: {item['name']}")
    print("effective_config:")
    print(json.dumps(result["effective_config"], ensure_ascii=False, indent=2))
    print("provenance:")
    print(json.dumps(result["provenance"], ensure_ascii=False, indent=2))
    return 0


def _server_root(raw: str) -> str:
    text = raw.strip().rstrip("/")
    if text.endswith("/mcp"):
        text = text[:-4]
    return text or "http://127.0.0.1:3189"


def _tool_url(server: str) -> str:
    return _server_root(server) + "/mcp"


def _tool_error_text(result: dict) -> str:
    message = str(result.get("error", "tool call failed"))
    candidates = result.get("bridge_candidates")
    if not isinstance(candidates, list) or not candidates:
        return message
    labels = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        bridge_id = str(item.get("bridge_id", "")).strip()
        room_id = str(item.get("room_id", "")).strip()
        if bridge_id and room_id:
            labels.append(f"{bridge_id} ({room_id})")
        elif bridge_id:
            labels.append(bridge_id)
    if not labels:
        return message
    return message + " | candidates: " + ", ".join(labels)


def _tool_call(server: str, name: str, arguments: dict) -> dict:
    body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        _tool_url(server),
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    result = payload["result"]["structuredContent"]
    if isinstance(result, dict) and isinstance(result.get("error"), str):
        raise RuntimeError(_tool_error_text(result))
    return result


def _stream_url(server: str, room_id: str, *, after_id: int = 0, limit: int = 200) -> str:
    encoded_room = urllib.parse.quote(room_id, safe="")
    query = urllib.parse.urlencode({"after_id": after_id, "limit": limit})
    return f"{_server_root(server)}/rooms/{encoded_room}/stream?{query}"


def _format_room_event(event: dict) -> str:
    kind = event.get("kind", "chat")
    author = event.get("author", "?")
    text = event.get("text", "")
    room_id = event.get("room_id", "")
    event_id = event.get("id", "?")
    return f"[{room_id} #{event_id} {kind}] {author}: {text}"


def _watch_room_sse(server: str, room_id: str, *, after_id: int = 0, limit: int = 200) -> int:
    req = urllib.request.Request(
        _stream_url(server, room_id, after_id=after_id, limit=limit),
        headers={"Accept": "text/event-stream"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        event_name = "message"
        data_lines = []
        for raw_line in resp:
            line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
            if not line:
                if data_lines:
                    payload = json.loads("\n".join(data_lines))
                    if event_name == "room":
                        print(_format_room_event(payload))
                    elif event_name != "ready":
                        print(json.dumps(payload, ensure_ascii=False))
                    data_lines = []
                    event_name = "message"
                continue
            if line.startswith(":"):
                continue
            if line.startswith("event:"):
                event_name = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data_lines.append(line.split(":", 1)[1].lstrip())
    return 0


def _watch_room_poll(server: str, room_id: str, *, after_id: int = 0, interval: float = 1.0) -> int:
    cursor = after_id
    while True:
        result = _tool_call(server, "room_poll", {"room_id": room_id, "after_id": cursor, "limit": 200})
        messages = result.get("messages", [])
        for item in messages:
            print(_format_room_event(item))
            cursor = max(cursor, int(item.get("id", 0) or 0))
        time.sleep(max(0.2, interval))


def cmd_room_watch(_backend: TmuxBackend, args: argparse.Namespace) -> int:
    if args.transport == "poll":
        return _watch_room_poll(args.server, args.room_id, after_id=args.after_id, interval=args.poll_interval)
    try:
        return _watch_room_sse(args.server, args.room_id, after_id=args.after_id, limit=args.limit)
    except (urllib.error.URLError, TimeoutError, OSError, RuntimeError) as exc:
        if args.transport == "sse":
            raise RuntimeError(f"SSE room watch failed: {exc}")
        print(f"[tb2 room] SSE unavailable, falling back to room_poll: {exc}", file=sys.stderr)
        return _watch_room_poll(args.server, args.room_id, after_id=args.after_id, interval=args.poll_interval)


def cmd_room_post(_backend: TmuxBackend, args: argparse.Namespace) -> int:
    payload = {
        "room_id": args.room_id,
        "author": args.author,
        "text": args.text,
    }
    if args.deliver:
        payload["deliver"] = args.deliver
    if args.bridge_id:
        payload["bridge_id"] = args.bridge_id
    print(json.dumps(_tool_call(args.server, "room_post", payload), ensure_ascii=False))
    return 0


def _room_bridge_payload(args: argparse.Namespace) -> dict:
    payload = {}
    if args.bridge_id:
        payload["bridge_id"] = args.bridge_id
    if getattr(args, "room_id", ""):
        payload["room_id"] = args.room_id
    return payload


def cmd_room_pending(_backend: TmuxBackend, args: argparse.Namespace) -> int:
    print(json.dumps(_tool_call(args.server, "intervention_list", _room_bridge_payload(args)), ensure_ascii=False))
    return 0


def cmd_room_approve(_backend: TmuxBackend, args: argparse.Namespace) -> int:
    if not args.all and args.msg_id is None:
        raise RuntimeError("approve requires --id or --all")
    if args.all and args.text:
        raise RuntimeError("approve --text only works with a single --id")
    payload = {**_room_bridge_payload(args), "id": "all" if args.all else args.msg_id}
    if args.text:
        payload["edited_text"] = args.text
    print(json.dumps(_tool_call(args.server, "intervention_approve", payload), ensure_ascii=False))
    return 0


def cmd_room_reject(_backend: TmuxBackend, args: argparse.Namespace) -> int:
    if not args.all and args.msg_id is None:
        raise RuntimeError("reject requires --id or --all")
    payload = {**_room_bridge_payload(args), "id": "all" if args.all else args.msg_id}
    print(json.dumps(_tool_call(args.server, "intervention_reject", payload), ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    _default_backend = default_backend_name()

    p = argparse.ArgumentParser(prog="tb2", description="TerminalBridge v2 — universal CLI LLM bridge")
    p.add_argument("--backend", choices=["tmux", "process", "pipe"], default=_default_backend,
                   help=f"terminal backend (default: {_default_backend})")
    p.add_argument("--distro", default=None, help="WSL distro (tmux backend only)")
    p.add_argument("--use-wsl", action="store_true", default=None, help="force WSL mode (tmux backend only)")

    sub = p.add_subparsers(dest="cmd", required=True)

    # init
    s = sub.add_parser("init", help="create a two-pane session")
    s.add_argument("--session", default="tb2", help="session name (default: tb2)")
    s.set_defaults(fn=cmd_init)

    # list
    s = sub.add_parser("list", help="list panes")
    s.add_argument("--session", default=None)
    s.set_defaults(fn=cmd_list)

    # capture
    s = sub.add_parser("capture", help="capture pane text")
    s.add_argument("--target", required=True)
    s.add_argument("--lines", type=int, default=200)
    s.set_defaults(fn=cmd_capture)

    # send
    s = sub.add_parser("send", help="send text to pane")
    s.add_argument("--target", required=True)
    s.add_argument("--text", required=True)
    s.add_argument("--enter", action="store_true")
    s.set_defaults(fn=cmd_send)

    # room operator CLI
    s = sub.add_parser("room", help="watch or control a room via the tb2 server")
    s.add_argument("--server", default="http://127.0.0.1:3189", help="tb2 server root URL or MCP endpoint")
    rs = s.add_subparsers(dest="room_cmd", required=True)

    r_watch = rs.add_parser("watch", help="watch a room stream")
    r_watch.add_argument("--room-id", required=True)
    r_watch.add_argument("--transport", choices=["auto", "sse", "poll"], default="auto")
    r_watch.add_argument("--after-id", type=int, default=0)
    r_watch.add_argument("--limit", type=int, default=200)
    r_watch.add_argument("--poll-interval", type=float, default=1.0)
    r_watch.set_defaults(fn=cmd_room_watch)

    r_post = rs.add_parser("post", help="post a message into a room")
    r_post.add_argument("--room-id", required=True)
    r_post.add_argument("--text", required=True)
    r_post.add_argument("--author", default="human")
    r_post.add_argument("--deliver", choices=["a", "b", "both"], default=None)
    r_post.add_argument("--bridge-id", default="")
    r_post.set_defaults(fn=cmd_room_post)

    r_pending = rs.add_parser("pending", help="list pending intervention items")
    r_pending.add_argument("--bridge-id", default="")
    r_pending.add_argument("--room-id", default="", help="resolve the active bridge from a room when possible")
    r_pending.set_defaults(fn=cmd_room_pending)

    r_approve = rs.add_parser("approve", help="approve one or all pending messages")
    r_approve.add_argument("--bridge-id", default="")
    r_approve.add_argument("--room-id", default="", help="resolve the active bridge from a room when possible")
    r_approve.add_argument("--id", dest="msg_id", type=int, default=None)
    r_approve.add_argument("--all", action="store_true")
    r_approve.add_argument("--text", default="", help="optional edited text for a single approval")
    r_approve.set_defaults(fn=cmd_room_approve)

    r_reject = rs.add_parser("reject", help="reject one or all pending messages")
    r_reject.add_argument("--bridge-id", default="")
    r_reject.add_argument("--room-id", default="", help="resolve the active bridge from a room when possible")
    r_reject.add_argument("--id", dest="msg_id", type=int, default=None)
    r_reject.add_argument("--all", action="store_true")
    r_reject.set_defaults(fn=cmd_room_reject)

    # broker
    s = sub.add_parser("broker", help="interactive broker with monitoring")
    s.add_argument("--a", required=True, help="pane A target")
    s.add_argument("--b", required=True, help="pane B target")
    s.add_argument("--profile", default="generic", help="tool profile name")
    s.add_argument("--lines", type=int, default=200)
    s.add_argument("--poll-ms", type=int, default=400)
    s.add_argument("--auto", action="store_true", help="enable MSG: auto-forward")
    s.add_argument("--intervention", action="store_true", help="start with human review on")
    s.set_defaults(fn=cmd_broker)

    # profiles
    s = sub.add_parser("profiles", help="list available tool profiles")
    s.add_argument("--verbose", action="store_true", help="show support matrix and recommended backends")
    s.set_defaults(fn=cmd_profiles)

    # doctor
    s = sub.add_parser("doctor", help="check local backend and supported CLI compatibility")
    s.add_argument("--json", action="store_true", help="emit machine-readable JSON report")
    s.set_defaults(fn=cmd_doctor)

    # governance
    s = sub.add_parser("governance", help="resolve layered governance config")
    gs = s.add_subparsers(dest="governance_cmd", required=True)

    g_resolve = gs.add_parser("resolve", help="resolve governance layers into effective config")
    g_resolve.add_argument("--model", default="", help="model or agent profile name")
    g_resolve.add_argument("--environment", default="", help="execution environment name")
    g_resolve.add_argument("--instruction-profile", default="", help="instruction profile or preset name")
    g_resolve.add_argument("--config", default="", help="optional governance layer JSON overlay path")
    g_resolve.add_argument("--json", action="store_true", help="emit machine-readable JSON report")
    g_resolve.set_defaults(fn=cmd_governance)
    g_schema = gs.add_parser("schema", help="print the governance overlay JSON schema")
    g_schema.set_defaults(fn=cmd_governance)
    g_sample = gs.add_parser("sample", help="print a sample governance overlay JSON document")
    g_sample.set_defaults(fn=cmd_governance)

    # server
    s = sub.add_parser("server", help="start MCP HTTP server")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=3189)
    s.add_argument("--allow-remote", action="store_true", help="explicitly acknowledge non-loopback bind risk")
    s.set_defaults(fn=cmd_server)

    # gui
    s = sub.add_parser("gui", help="start web GUI server")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=3189)
    s.add_argument("--allow-remote", action="store_true", help="explicitly acknowledge non-loopback bind risk")
    s.add_argument("--no-browser", action="store_true", help="do not open browser automatically")
    s.set_defaults(fn=cmd_gui)

    # service manager
    s = sub.add_parser("service", help="manage tb2 server as a background service")
    ss = s.add_subparsers(dest="service_cmd", required=True)

    s_start = ss.add_parser("start", help="start detached tb2 server")
    s_start.add_argument("--host", default="127.0.0.1")
    s_start.add_argument("--port", type=int, default=3189)
    s_start.add_argument("--python", default="", help="python executable to launch")
    s_start.add_argument("--allow-remote", action="store_true", help="explicitly acknowledge non-loopback bind risk")
    s_start.add_argument("--force", action="store_true", help="stop existing instance first")
    s_start.set_defaults(fn=cmd_service)

    s_stop = ss.add_parser("stop", help="stop detached tb2 server")
    s_stop.add_argument("--timeout", type=float, default=8.0, help="graceful stop timeout in seconds")
    s_stop.set_defaults(fn=cmd_service)

    s_status = ss.add_parser("status", help="show detached tb2 server status")
    s_status.set_defaults(fn=cmd_service)

    s_restart = ss.add_parser("restart", help="restart detached tb2 server")
    s_restart.add_argument("--host", default=None)
    s_restart.add_argument("--port", type=int, default=None)
    s_restart.add_argument("--python", default="", help="python executable to launch")
    s_restart.add_argument("--allow-remote", action="store_true", default=None, help="explicitly acknowledge non-loopback bind risk")
    s_restart.set_defaults(fn=cmd_service)

    s_logs = ss.add_parser("logs", help="show service logs")
    s_logs.add_argument("--lines", type=int, default=120)
    s_logs.set_defaults(fn=cmd_service)

    s_audit = ss.add_parser("audit", help="show persisted audit trail events")
    s_audit.add_argument("--lines", type=int, default=120)
    s_audit.add_argument("--room-id", default="")
    s_audit.add_argument("--bridge-id", default="")
    s_audit.add_argument("--event", default="")
    s_audit.set_defaults(fn=cmd_service)

    return p


def _create_backend(args: argparse.Namespace):
    """Factory: create the right backend based on --backend flag."""
    if args.backend == "process":
        from .process_backend import ProcessBackend
        return ProcessBackend()

    if args.backend == "pipe":
        from .pipe_backend import PipeBackend
        return PipeBackend()

    # Default: tmux
    kwargs = {}
    if args.distro:
        kwargs["distro"] = args.distro
    if args.use_wsl is not None:
        kwargs["use_wsl"] = args.use_wsl
    return TmuxBackend(**kwargs)


def main(argv: Sequence[str] | None = None) -> int:
    p = build_parser()
    args = p.parse_args(list(argv) if argv is not None else None)

    backend = None
    if args.cmd in {"init", "list", "capture", "send", "broker"}:
        backend = _create_backend(args)

    try:
        return int(args.fn(backend, args))
    except KeyboardInterrupt:
        return 130
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except TmuxError as exc:
        print(str(exc), file=sys.stderr)
        return 2
