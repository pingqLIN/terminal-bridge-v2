"""CLI entry point for TerminalBridge v2.

Usage:
    python -m tb2 init [--session NAME]
    python -m tb2 list [--session NAME]
    python -m tb2 capture --target TARGET [--lines N]
    python -m tb2 send --target TARGET --text TEXT [--enter]
    python -m tb2 broker --a TARGET --b TARGET [--profile NAME] [--auto] [--intervention]
    python -m tb2 profiles
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from .backend import TmuxBackend, TmuxError
from .broker import BrokerConfig, broker_loop
from .profile import list_profiles


def cmd_init(backend: TmuxBackend, args: argparse.Namespace) -> int:
    a, b = backend.init_session(args.session)
    print("OK")
    print(f"session: {args.session}")
    print(f"pane A:  {a}")
    print(f"pane B:  {b}")
    print(f"\nAttach:  tmux attach -t {args.session}")
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


def cmd_profiles(_backend: TmuxBackend, _args: argparse.Namespace) -> int:
    for name in list_profiles():
        print(f"  {name}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tb2", description="TerminalBridge v2 — universal CLI LLM bridge")
    p.add_argument("--distro", default=None, help="WSL distro (auto-detected if omitted)")
    p.add_argument("--use-wsl", action="store_true", default=None, help="force WSL mode")

    sub = p.add_subparsers(dest="cmd", required=True)

    # init
    s = sub.add_parser("init", help="create tmux session with 2 panes")
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
    s.set_defaults(fn=cmd_profiles)

    return p


def main(argv: Sequence[str] | None = None) -> int:
    p = build_parser()
    args = p.parse_args(list(argv) if argv is not None else None)

    kwargs = {}
    if args.distro:
        kwargs["distro"] = args.distro
    if args.use_wsl is not None:
        kwargs["use_wsl"] = args.use_wsl

    backend = TmuxBackend(**kwargs)

    try:
        return int(args.fn(backend, args))
    except KeyboardInterrupt:
        return 130
    except TmuxError as exc:
        print(str(exc), file=sys.stderr)
        return 2
