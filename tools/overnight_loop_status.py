#!/usr/bin/env python3
"""Write durable status snapshots for unattended project-development-loop runs."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from datetime import datetime, timezone
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


def snapshot(label: str) -> Dict[str, Any]:
    status = run(["git", "status", "--short", "--branch"])
    head = run(["git", "rev-parse", "--short", "HEAD"])
    upstream = run(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
    codex_processes = run(["bash", "-lc", "ps -eo pid,comm,args | grep -Ei '[c]odex|[c]laude|[g]emini' || true"])
    return {
        "schema_version": 1,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "label": label,
        "pid": os.getpid(),
        "cwd": str(Path.cwd()),
        "git": {
            "status": status,
            "head": head,
            "upstream": upstream,
        },
        "machine_monitoring": {
            "ai_processes": codex_processes,
            "token_usage": {
                "available": False,
                "reason": "No stable repo-local API exposes whole-machine model token usage; record process evidence and keep batch width conservative.",
            },
        },
    }


def append_snapshot(path: Path, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(snapshot(label), ensure_ascii=False, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", default=".tb2-overnight/latest")
    parser.add_argument("--label", default="overnight-maintenance")
    parser.add_argument("--interval-seconds", type=int, default=1800)
    parser.add_argument("--iterations", type=int, default=1)
    args = parser.parse_args()

    if args.interval_seconds < 30:
        raise SystemExit("--interval-seconds must be at least 30")
    if args.iterations < 1:
        raise SystemExit("--iterations must be at least 1")

    output = Path(args.state_dir) / "status.jsonl"
    for index in range(args.iterations):
        append_snapshot(output, f"{args.label}:{index + 1}")
        if index + 1 < args.iterations:
            time.sleep(args.interval_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())