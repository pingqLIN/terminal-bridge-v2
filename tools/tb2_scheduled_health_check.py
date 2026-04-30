#!/usr/bin/env python3
"""Scheduled TB2 health check for systemd timer or cron use."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


def run(args: list[str], *, cwd: Path | None = None, timeout: float = 15.0) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            args,
            check=False,
            cwd=str(cwd) if cwd else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "ok": False,
            "returncode": None,
            "stdout": "",
            "stderr": str(exc),
            "args": args,
        }
    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
        "args": args,
    }


def read_json_url(url: str, *, timeout: float) -> dict[str, Any]:
    try:
        with urlopen(url, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return {
                "ok": 200 <= int(response.status) < 300,
                "status": int(response.status),
                "payload": json.loads(body),
                "error": "",
            }
    except HTTPError as exc:
        return {"ok": False, "status": exc.code, "payload": {}, "error": str(exc)}
    except (OSError, URLError, json.JSONDecodeError) as exc:
        return {"ok": False, "status": None, "payload": {}, "error": str(exc)}


def check_systemd(unit: str) -> dict[str, Any]:
    active = run(["systemctl", "is-active", unit], timeout=8.0)
    enabled = run(["systemctl", "is-enabled", unit], timeout=8.0)
    return {
        "unit": unit,
        "active": active,
        "enabled": enabled,
        "ok": active["stdout"] == "active",
    }


def check_doctor(python: str, repo: Path) -> dict[str, Any]:
    result = run([python, "-m", "tb2", "doctor", "--json"], cwd=repo, timeout=30.0)
    command = {
        "args": result["args"],
        "ok": result["ok"],
        "returncode": result["returncode"],
        "stderr": result["stderr"],
    }
    if not result["ok"]:
        return {"ok": False, "command": command, "payload": {}, "error": "doctor command failed"}
    try:
        payload = json.loads(str(result["stdout"]))
    except json.JSONDecodeError as exc:
        return {"ok": False, "command": command, "payload": {}, "error": str(exc)}

    readiness = payload.get("readiness", {}) if isinstance(payload.get("readiness"), dict) else {}
    ok = (
        readiness.get("backend") == "ready"
        and readiness.get("clients") == "ready"
        and readiness.get("transport") == "ready"
    )
    return {"ok": ok, "command": command, "payload": payload, "error": ""}


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    base = str(args.base_url).rstrip("/")
    health = read_json_url(base + "/health", timeout=float(args.timeout))
    healthz = read_json_url(base + "/healthz", timeout=float(args.timeout))
    doctor = check_doctor(str(args.python), Path(args.repo))
    systemd = None if args.skip_systemd else check_systemd(str(args.unit))

    issues: list[str] = []
    if systemd and not systemd["ok"]:
        issues.append(f"systemd unit {args.unit} is not active")
    if not health["ok"]:
        issues.append("/health request failed")
    if health["ok"]:
        payload = health.get("payload", {})
        if not payload.get("ok"):
            issues.append("/health ok=false")
        if not payload.get("ready"):
            issues.append("/health ready=false")
        if payload.get("codexAvailable") is False:
            issues.append("/health codexAvailable=false")
        if payload.get("backendReady") is False:
            issues.append("/health backendReady=false")
    if not healthz["ok"] or healthz.get("payload", {}).get("ok") is not True:
        issues.append("/healthz request failed or ok=false")
    if not doctor["ok"]:
        issues.append("doctor readiness is not ready")

    return {
        "schema_version": 1,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ok": not issues,
        "issues": issues,
        "target": {
            "base_url": base,
            "unit": None if args.skip_systemd else str(args.unit),
            "repo": str(Path(args.repo)),
        },
        "checks": {
            "systemd": systemd,
            "health": health,
            "healthz": healthz,
            "doctor": doctor,
        },
    }


def append_log(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rotate_log(path, max_bytes=int(report.get("_max_bytes", 0)), max_files=int(report.get("_max_files", 0)))
    report.pop("_max_bytes", None)
    report.pop("_max_files", None)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(report, ensure_ascii=False, sort_keys=True) + "\n")


def rotate_log(path: Path, *, max_bytes: int, max_files: int) -> None:
    if max_bytes <= 0 or max_files <= 0 or not path.exists():
        return
    if path.stat().st_size < max_bytes:
        return

    for index in range(max_files, 0, -1):
        current = path.with_name(f"{path.name}.{index}")
        target = path.with_name(f"{path.name}.{index + 1}")
        if not current.exists():
            continue
        if index == max_files:
            current.unlink()
            continue
        current.replace(target)
    path.replace(path.with_name(f"{path.name}.1"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:3189")
    parser.add_argument("--unit", default="tb2.service")
    parser.add_argument("--repo", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--log", default="")
    parser.add_argument("--max-bytes", type=int, default=10 * 1024 * 1024)
    parser.add_argument("--max-files", type=int, default=5)
    parser.add_argument("--skip-systemd", action="store_true")
    args = parser.parse_args()

    report = build_report(args)
    if args.log:
        report["_max_bytes"] = int(args.max_bytes)
        report["_max_files"] = int(args.max_files)
        append_log(Path(args.log), report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
