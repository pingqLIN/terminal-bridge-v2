"""Broker loop — the heart of TerminalBridge v2.

Polls two panes, detects new output, optionally forwards messages,
and accepts human commands.  Supports tool profiles and human intervention.
"""

from __future__ import annotations

import queue
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, List, Optional, Tuple

from .backend import TerminalBackend
from .diff import diff_new_lines, strip_prompt_tail
from .intervention import Action, InterventionLayer, PendingMessage
from .profile import ToolProfile, get_profile, strip_ansi


@dataclass
class BrokerConfig:
    target_a: str
    target_b: str
    profile: str = "generic"
    poll_ms: int = 400
    capture_lines: int = 200
    auto_forward: bool = False
    intervention: bool = False  # start with human review off

    # Exponential backoff
    min_poll_ms: int = 100
    max_poll_ms: int = 3000
    backoff_factor: float = 1.5


@dataclass
class BrokerState:
    prev_a: List[str] = field(default_factory=list)
    prev_b: List[str] = field(default_factory=list)
    current_poll_ms: float = 400.0
    forwarded_recent: Deque[Tuple[str, str]] = field(default_factory=lambda: deque(maxlen=80))


def _print_help() -> None:
    print("\n".join([
        "",
        "Commands:",
        "  /a <text>        send to pane A",
        "  /b <text>        send to pane B",
        "  /both <text>     send to both panes",
        "  /auto on|off     toggle MSG: auto-forward",
        "  /pause           enable human review of forwards",
        "  /resume          disable human review (auto-pass)",
        "  /pending         list pending messages",
        "  /approve [id|all] approve pending message(s)",
        "  /reject [id|all]  reject pending message(s)",
        "  /edit <id> <text> edit and approve a pending message",
        "  /profile [name]  show or switch tool profile",
        "  /status          show broker status",
        "  /help            show this help",
        "  /quit            exit broker",
        "",
    ]))


def broker_loop(backend: TerminalBackend, cfg: BrokerConfig) -> int:
    """Run the interactive broker. Returns exit code."""

    profile = get_profile(cfg.profile)
    intervention = InterventionLayer(active=cfg.intervention)
    state = BrokerState(current_poll_ms=float(cfg.poll_ms))

    # Stdin reader thread.
    input_q: queue.Queue[str] = queue.Queue()
    stop = threading.Event()

    def _stdin_reader() -> None:
        while not stop.is_set():
            try:
                line = sys.stdin.readline()
            except Exception:
                break
            if not line:
                break
            input_q.put(line.rstrip("\r\n"))

    t = threading.Thread(target=_stdin_reader, daemon=True)
    t.start()

    # Prime captures.
    try:
        state.prev_a, state.prev_b = backend.capture_both(
            cfg.target_a, cfg.target_b, cfg.capture_lines)
        state.prev_a = strip_prompt_tail(state.prev_a, profile.prompt_patterns)
        state.prev_b = strip_prompt_tail(state.prev_b, profile.prompt_patterns)
    except Exception as exc:
        print(f"[broker] init capture failed: {exc}", file=sys.stderr)
        return 2

    _print_help()
    print(f"[broker] A={cfg.target_a}  B={cfg.target_b}  profile={profile.name}  "
          f"auto={'on' if cfg.auto_forward else 'off'}  "
          f"intervention={'on' if intervention.active else 'off'}")

    def _show_new(tag: str, lines: List[str]) -> None:
        for ln in lines:
            if not ln.strip():
                continue
            display = strip_ansi(ln) if profile.strip_ansi else ln
            print(f"{tag}| {display}")

    def _deliver(msg: PendingMessage) -> None:
        """Actually send a message to target pane."""
        text = msg.edited_text if msg.edited_text else msg.text
        backend.send(msg.to_pane, text, enter=True)
        print(f"[broker] delivered #{msg.id} -> {msg.to_pane}: {text}")

    def _maybe_forward(from_tag: str, from_target: str, to_target: str, new_lines: List[str]) -> None:
        if not cfg.auto_forward:
            return
        for ln in new_lines:
            parsed = profile.parse_message(ln)
            if not parsed:
                continue
            fp = (from_tag, parsed)
            if fp in state.forwarded_recent:
                continue
            state.forwarded_recent.append(fp)

            msg = intervention.submit(from_target, to_target, parsed)
            if msg.action == Action.AUTO:
                _deliver(msg)
            else:
                print(f"[pending] #{msg.id} {from_tag}->{to_target}: {parsed}  (use /approve {msg.id})")

    def _process_pending() -> None:
        """Auto-deliver approved/edited messages."""
        # This is called each loop iteration to flush anything the user approved.
        pass  # Delivery happens inline in command handlers below.

    while True:
        # 1) Poll panes (single subprocess call).
        try:
            curr_a, curr_b = backend.capture_both(
                cfg.target_a, cfg.target_b, cfg.capture_lines)
        except Exception as exc:
            print(f"[broker] capture error: {exc}", file=sys.stderr)
            return 2

        curr_a = strip_prompt_tail(curr_a, profile.prompt_patterns)
        curr_b = strip_prompt_tail(curr_b, profile.prompt_patterns)

        new_a = diff_new_lines(state.prev_a, curr_a)
        new_b = diff_new_lines(state.prev_b, curr_b)
        state.prev_a = curr_a
        state.prev_b = curr_b

        # Adaptive polling: backoff when idle, reset on activity.
        if new_a or new_b:
            state.current_poll_ms = float(cfg.min_poll_ms)
        else:
            state.current_poll_ms = min(
                state.current_poll_ms * cfg.backoff_factor,
                float(cfg.max_poll_ms),
            )

        if new_a:
            _show_new("A", new_a)
            _maybe_forward("A", cfg.target_a, cfg.target_b, new_a)
        if new_b:
            _show_new("B", new_b)
            _maybe_forward("B", cfg.target_b, cfg.target_a, new_b)

        # 2) Handle user input.
        try:
            while True:
                line = input_q.get_nowait()
                if not line:
                    continue

                if line.startswith("/quit"):
                    stop.set()
                    return 0

                if line.startswith("/help"):
                    _print_help()
                    continue

                if line.startswith("/status"):
                    pending = intervention.list_pending()
                    print(f"[status] profile={profile.name} auto={'on' if cfg.auto_forward else 'off'} "
                          f"intervention={'on' if intervention.active else 'off'} "
                          f"pending={len(pending)} poll={int(state.current_poll_ms)}ms")
                    continue

                if line.startswith("/auto"):
                    parts = line.split(None, 2)
                    if len(parts) >= 2 and parts[1].lower() in ("on", "off"):
                        cfg.auto_forward = parts[1].lower() == "on"
                        print(f"[broker] auto={'on' if cfg.auto_forward else 'off'}")
                    else:
                        print("[broker] usage: /auto on|off")
                    continue

                if line.startswith("/pause"):
                    intervention.pause()
                    print("[broker] intervention ON — forwards will queue for review")
                    continue

                if line.startswith("/resume"):
                    approved = intervention.approve_all()
                    for m in approved:
                        _deliver(m)
                    intervention.resume()
                    print(f"[broker] intervention OFF — {len(approved)} pending delivered")
                    continue

                if line.startswith("/pending"):
                    pending = intervention.list_pending()
                    if not pending:
                        print("[pending] (empty)")
                    for m in pending:
                        age = time.time() - m.created_at
                        print(f"  #{m.id} [{age:.0f}s ago] {m.from_pane}->{m.to_pane}: {m.text}")
                    continue

                if line.startswith("/approve"):
                    parts = line.split(None, 2)
                    if len(parts) < 2:
                        print("[broker] usage: /approve <id|all>")
                        continue
                    if parts[1] == "all":
                        approved = intervention.approve_all()
                        for m in approved:
                            _deliver(m)
                        print(f"[broker] approved {len(approved)} messages")
                    else:
                        try:
                            mid = int(parts[1])
                        except ValueError:
                            print("[broker] invalid id")
                            continue
                        m = intervention.approve(mid)
                        if m:
                            _deliver(m)
                        else:
                            print(f"[broker] #{mid} not found or already resolved")
                    continue

                if line.startswith("/reject"):
                    parts = line.split(None, 2)
                    if len(parts) < 2:
                        print("[broker] usage: /reject <id|all>")
                        continue
                    if parts[1] == "all":
                        n = intervention.reject_all()
                        print(f"[broker] rejected {n} messages")
                    else:
                        try:
                            mid = int(parts[1])
                        except ValueError:
                            print("[broker] invalid id")
                            continue
                        m = intervention.reject(mid)
                        if m:
                            print(f"[broker] rejected #{mid}")
                        else:
                            print(f"[broker] #{mid} not found")
                    continue

                if line.startswith("/edit"):
                    parts = line.split(None, 2)
                    if len(parts) < 3:
                        print("[broker] usage: /edit <id> <new text>")
                        continue
                    try:
                        mid = int(parts[1])
                    except ValueError:
                        print("[broker] invalid id")
                        continue
                    m = intervention.edit(mid, parts[2])
                    if m:
                        _deliver(m)
                    else:
                        print(f"[broker] #{mid} not found")
                    continue

                if line.startswith("/profile"):
                    parts = line.split(None, 2)
                    if len(parts) >= 2:
                        profile = get_profile(parts[1])
                        cfg.profile = profile.name
                        print(f"[broker] profile switched to: {profile.name}")
                    else:
                        print(f"[broker] current profile: {profile.name}")
                    continue

                if line.startswith("/both "):
                    msg = line[len("/both "):]
                    backend.send(cfg.target_a, msg, enter=True)
                    backend.send(cfg.target_b, msg, enter=True)
                    print(f"[you] -> both: {msg}")
                    continue

                if line.startswith("/a "):
                    msg = line[len("/a "):]
                    backend.send(cfg.target_a, msg, enter=True)
                    print(f"[you] -> A: {msg}")
                    continue

                if line.startswith("/b "):
                    msg = line[len("/b "):]
                    backend.send(cfg.target_b, msg, enter=True)
                    print(f"[you] -> B: {msg}")
                    continue

                # Default: send to A.
                backend.send(cfg.target_a, line, enter=True)
                print(f"[you] -> A: {line}")

        except queue.Empty:
            pass

        time.sleep(max(0.05, state.current_poll_ms / 1000.0))
