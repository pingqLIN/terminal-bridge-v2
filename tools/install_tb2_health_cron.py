#!/usr/bin/env python3
"""Install, remove, or inspect the TB2 scheduled health-check crontab entry."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


MARKER = "# tb2_health_check"


def run(args: list[str], *, input_text: str | None = None) -> dict[str, Any]:
    completed = subprocess.run(
        args,
        check=False,
        input=input_text,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "args": args,
    }


def read_crontab() -> str:
    result = run(["crontab", "-l"])
    if result["ok"]:
        return str(result["stdout"])
    if "no crontab for" in str(result["stderr"]).lower():
        return ""
    raise RuntimeError(str(result["stderr"]).strip() or "failed to read crontab")


def write_crontab(text: str) -> None:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as stream:
        path = Path(stream.name)
        stream.write(text)
    try:
        result = run(["crontab", str(path)])
        if not result["ok"]:
            raise RuntimeError(str(result["stderr"]).strip() or "failed to write crontab")
    finally:
        path.unlink(missing_ok=True)


def without_entry(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if MARKER not in line).strip()


def build_entry(args: argparse.Namespace) -> str:
    repo = Path(args.repo).resolve()
    interval = int(args.interval_minutes)
    if interval < 1 or interval > 59:
        raise ValueError("--interval-minutes must be between 1 and 59")

    command = (
        f"cd {repo} && {args.python} tools/tb2_scheduled_health_check.py"
        f" --unit {args.unit}"
        f" --base-url {args.base_url}"
        f" --log {args.log}"
        f" --max-bytes {int(args.max_bytes)}"
        f" --max-files {int(args.max_files)}"
        f" >> {args.cron_log} 2>&1 {MARKER}"
    )
    return f"*/{interval} * * * * {command}"


def install(args: argparse.Namespace) -> dict[str, Any]:
    entry = build_entry(args)
    base = without_entry(read_crontab())
    text = (base + "\n" + entry + "\n") if base else entry + "\n"
    if not args.dry_run:
        write_crontab(text)
    return {"action": "install", "dry_run": bool(args.dry_run), "entry": entry}


def uninstall(args: argparse.Namespace) -> dict[str, Any]:
    base = without_entry(read_crontab())
    text = base + "\n" if base else ""
    if not args.dry_run:
        write_crontab(text)
    return {"action": "uninstall", "dry_run": bool(args.dry_run), "remaining": base}


def status(_args: argparse.Namespace) -> dict[str, Any]:
    lines = [line for line in read_crontab().splitlines() if MARKER in line]
    return {"action": "status", "installed": bool(lines), "entries": lines}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    def add_common(target: argparse.ArgumentParser) -> None:
        target.add_argument("--dry-run", action="store_true")

    install_parser = sub.add_parser("install", help="install or replace the TB2 health-check cron entry")
    install_parser.add_argument("--repo", default=str(Path(__file__).resolve().parents[1]))
    install_parser.add_argument("--python", default="/usr/bin/python3")
    install_parser.add_argument("--unit", default="tb2.service")
    install_parser.add_argument("--base-url", default="http://127.0.0.1:3189")
    install_parser.add_argument("--log", default=str(Path.home() / ".local/state/tb2/health-check.jsonl"))
    install_parser.add_argument("--cron-log", default=str(Path.home() / ".local/state/tb2/health-check-cron.log"))
    install_parser.add_argument("--interval-minutes", type=int, default=5)
    install_parser.add_argument("--max-bytes", type=int, default=10 * 1024 * 1024)
    install_parser.add_argument("--max-files", type=int, default=5)
    add_common(install_parser)
    install_parser.set_defaults(fn=install)

    uninstall_parser = sub.add_parser("uninstall", help="remove the TB2 health-check cron entry")
    add_common(uninstall_parser)
    uninstall_parser.set_defaults(fn=uninstall)

    status_parser = sub.add_parser("status", help="show the TB2 health-check cron entry")
    status_parser.set_defaults(fn=status)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    print(json.dumps(args.fn(args), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
