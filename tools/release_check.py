#!/usr/bin/env python3
"""Run the local TB2 release-readiness verification bundle."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class Check:
    name: str
    command: list[str]
    require_json: bool = False


@dataclass(frozen=True)
class Result:
    name: str
    command: list[str]
    ok: bool
    returncode: int | None
    stdout: str
    stderr: str
    error: str = ""


def run(check: Check, *, cwd: Path) -> Result:
    try:
        completed = subprocess.run(
            check.command,
            check=False,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except OSError as exc:
        return Result(check.name, check.command, False, None, "", "", str(exc))

    error = ""
    if check.require_json and completed.returncode == 0:
        try:
            json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            error = f"invalid JSON output: {exc}"

    return Result(
        check.name,
        check.command,
        completed.returncode == 0 and not error,
        completed.returncode,
        completed.stdout,
        completed.stderr,
        error,
    )


def checks(args: argparse.Namespace) -> list[Check]:
    python = str(args.python)
    items = [
        Check("diff-check", ["git", "diff", "--check"]),
        Check("doctor-json", [python, "-m", "tb2", "doctor", "--json"], require_json=True),
        Check("profiles-verbose", [python, "-m", "tb2", "profiles", "--verbose"]),
    ]
    if not args.skip_tests:
        items.append(Check("pytest", [python, "-m", "pytest", *args.pytest_args]))
    return items


def render(results: Sequence[Result]) -> str:
    lines = ["TB2 release check"]
    for result in results:
        status = "PASS" if result.ok else "FAIL"
        lines.append(f"- {status} {result.name}: {' '.join(result.command)}")
        if result.error:
            lines.append(f"  error: {result.error}")
        if not result.ok and result.stderr.strip():
            lines.append(f"  stderr: {result.stderr.strip()}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument(
        "--pytest-args",
        nargs=argparse.REMAINDER,
        default=["tests", "-q"],
        help="pytest args after this flag; default: tests -q",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    results = [run(check, cwd=Path(args.repo)) for check in checks(args)]
    print(render(results))
    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
