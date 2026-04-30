#!/usr/bin/env python3
"""Read the TB2 scheduled health-check alert marker."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def read_marker(path: Path) -> dict:
    if not path.exists():
        return {
            "schema_version": 1,
            "installed": False,
            "ok": True,
            "active": False,
            "path": str(path),
            "summary": "No TB2 health alert marker is present.",
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "schema_version": 1,
            "installed": True,
            "ok": False,
            "active": True,
            "path": str(path),
            "summary": "TB2 health alert marker is not valid JSON.",
            "error": str(exc),
        }
    if isinstance(payload, dict):
        payload.setdefault("installed", True)
        payload.setdefault("path", str(path))
        return payload
    return {
        "schema_version": 1,
        "installed": True,
        "ok": False,
        "active": True,
        "path": str(path),
        "summary": "TB2 health alert marker does not contain a JSON object.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cmd", choices=["status"])
    parser.add_argument("--alert", default=str(Path.home() / ".local/state/tb2/health-check.alert.json"))
    args = parser.parse_args()

    print(json.dumps(read_marker(Path(args.alert)), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
