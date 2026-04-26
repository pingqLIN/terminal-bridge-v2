#!/usr/bin/env python3
"""Manage durable repo-local state for time-boxed project-development-loop runs."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List


def run(args: List[str]) -> Dict[str, Any]:
    try:
        completed = subprocess.run(
            args,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except OSError as exc:
        return {"ok": False, "error": str(exc), "args": args}
    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
        "args": args,
    }


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_text() -> str:
    return now_utc().isoformat()


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def git_snapshot() -> Dict[str, Any]:
    return {
        "branch": run(["git", "branch", "--show-current"]),
        "head": run(["git", "rev-parse", "HEAD"]),
        "status": run(["git", "status", "--short", "--branch"]),
        "upstream": run(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"]),
    }


def event_payload(state: Dict[str, Any], *, event_type: str, summary: str) -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "timestamp": now_text(),
        "event_type": event_type,
        "summary": summary,
        "cwd": str(Path.cwd()),
        "pid": os.getpid(),
        "state": state,
        "git": git_snapshot(),
    }


def init_state(args: argparse.Namespace) -> int:
    state_dir = Path(args.state_dir)
    state_path = state_dir / "state.json"
    if state_path.exists() and not args.force:
        raise SystemExit(f"state already exists: {state_path}")
    started_at = now_utc()
    deadline_at = started_at + timedelta(hours=args.duration_hours)
    git = git_snapshot()
    state = {
        "schema_version": 1,
        "label": args.label,
        "status": "active",
        "repo_root": str(Path.cwd()),
        "started_at": started_at.isoformat(),
        "deadline_at": deadline_at.isoformat(),
        "duration_hours": args.duration_hours,
        "baseline_branch": git["branch"]["stdout"],
        "baseline_commit": git["head"]["stdout"],
        "active_batch": {
            "name": args.batch,
            "goal": args.goal,
            "started_at": started_at.isoformat(),
        },
        "last_checkpoint": {
            "name": args.checkpoint,
            "at": started_at.isoformat(),
            "summary": args.summary,
        },
        "next_action": args.next_action,
    }
    write_json(state_path, state)
    append_jsonl(state_dir / "history.jsonl", event_payload(state, event_type="init", summary=args.summary))
    return 0


def checkpoint_state(args: argparse.Namespace) -> int:
    state_dir = Path(args.state_dir)
    state_path = state_dir / "state.json"
    state = read_json(state_path)
    if args.batch:
        state["active_batch"] = {
            "name": args.batch,
            "goal": args.goal,
            "started_at": now_text(),
        }
    state["last_checkpoint"] = {
        "name": args.checkpoint,
        "at": now_text(),
        "summary": args.summary,
    }
    if args.next_action:
        state["next_action"] = args.next_action
    write_json(state_path, state)
    append_jsonl(state_dir / "history.jsonl", event_payload(state, event_type="checkpoint", summary=args.summary))
    return 0


def complete_state(args: argparse.Namespace) -> int:
    state_dir = Path(args.state_dir)
    state_path = state_dir / "state.json"
    state = read_json(state_path)
    state["status"] = "complete"
    state["completed_at"] = now_text()
    state["last_checkpoint"] = {
        "name": args.checkpoint,
        "at": state["completed_at"],
        "summary": args.summary,
    }
    if args.next_action:
        state["next_action"] = args.next_action
    write_json(state_path, state)
    append_jsonl(state_dir / "history.jsonl", event_payload(state, event_type="complete", summary=args.summary))
    return 0


def show_state(args: argparse.Namespace) -> int:
    state_path = Path(args.state_dir) / "state.json"
    print(json.dumps(read_json(state_path), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--state-dir", required=True)
    init_parser.add_argument("--label", required=True)
    init_parser.add_argument("--duration-hours", type=float, required=True)
    init_parser.add_argument("--batch", required=True)
    init_parser.add_argument("--goal", required=True)
    init_parser.add_argument("--summary", required=True)
    init_parser.add_argument("--next-action", required=True)
    init_parser.add_argument("--checkpoint", default="preExecution")
    init_parser.add_argument("--force", action="store_true")
    init_parser.set_defaults(func=init_state)

    checkpoint_parser = subparsers.add_parser("checkpoint")
    checkpoint_parser.add_argument("--state-dir", required=True)
    checkpoint_parser.add_argument("--checkpoint", required=True)
    checkpoint_parser.add_argument("--summary", required=True)
    checkpoint_parser.add_argument("--next-action")
    checkpoint_parser.add_argument("--batch")
    checkpoint_parser.add_argument("--goal")
    checkpoint_parser.set_defaults(func=checkpoint_state)

    complete_parser = subparsers.add_parser("complete")
    complete_parser.add_argument("--state-dir", required=True)
    complete_parser.add_argument("--summary", required=True)
    complete_parser.add_argument("--next-action")
    complete_parser.add_argument("--checkpoint", default="finalReview")
    complete_parser.set_defaults(func=complete_state)

    show_parser = subparsers.add_parser("show")
    show_parser.add_argument("--state-dir", required=True)
    show_parser.set_defaults(func=show_state)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
