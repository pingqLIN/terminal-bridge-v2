from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools import tb2_scheduled_health_check as health


def test_build_report_accepts_ready_runtime(monkeypatch, tmp_path):
    def fake_url(url: str, *, timeout: float):
        if url.endswith("/health"):
            return {
                "ok": True,
                "status": 200,
                "payload": {
                    "ok": True,
                    "ready": True,
                    "codexAvailable": True,
                    "backendReady": True,
                },
                "error": "",
            }
        return {"ok": True, "status": 200, "payload": {"ok": True}, "error": ""}

    monkeypatch.setattr(health, "read_json_url", fake_url)
    monkeypatch.setattr(
        health,
        "check_doctor",
        lambda python, repo: {
            "ok": True,
            "command": {},
            "payload": {"readiness": {"backend": "ready", "clients": "ready", "transport": "ready"}},
            "error": "",
        },
    )
    monkeypatch.setattr(
        health,
        "check_systemd",
        lambda unit: {"unit": unit, "active": {"stdout": "active"}, "enabled": {"stdout": "enabled"}, "ok": True},
    )

    report = health.build_report(
        argparse.Namespace(
            base_url="http://127.0.0.1:3189/",
            unit="tb2.service",
            repo=str(tmp_path),
            python="python3",
            timeout=5.0,
            skip_systemd=False,
        )
    )

    assert report["ok"] is True
    assert report["issues"] == []


def test_build_report_flags_core_runtime_failures(monkeypatch, tmp_path):
    monkeypatch.setattr(
        health,
        "read_json_url",
        lambda url, *, timeout: {"ok": True, "status": 200, "payload": {"ok": False}, "error": ""},
    )
    monkeypatch.setattr(
        health,
        "check_doctor",
        lambda python, repo: {"ok": False, "command": {}, "payload": {}, "error": "bad"},
    )
    monkeypatch.setattr(
        health,
        "check_systemd",
        lambda unit: {"unit": unit, "active": {"stdout": "failed"}, "enabled": {"stdout": "enabled"}, "ok": False},
    )

    report = health.build_report(
        argparse.Namespace(
            base_url="http://127.0.0.1:3189",
            unit="tb2.service",
            repo=str(tmp_path),
            python="python3",
            timeout=5.0,
            skip_systemd=False,
        )
    )

    assert report["ok"] is False
    assert "systemd unit tb2.service is not active" in report["issues"]
    assert "/health ok=false" in report["issues"]
    assert "doctor readiness is not ready" in report["issues"]


def test_append_log_writes_jsonl(tmp_path):
    path = tmp_path / "tb2" / "health.jsonl"
    health.append_log(path, {"ok": True, "issues": []})

    assert json.loads(path.read_text(encoding="utf-8")) == {"ok": True, "issues": []}


def test_check_doctor_keeps_command_summary_without_stdout(monkeypatch, tmp_path):
    monkeypatch.setattr(
        health,
        "run",
        lambda args, *, cwd=None, timeout=15.0: {
            "ok": True,
            "returncode": 0,
            "stdout": json.dumps({"readiness": {"backend": "ready", "clients": "ready", "transport": "ready"}}),
            "stderr": "",
            "args": args,
        },
    )

    report = health.check_doctor("python3", tmp_path)

    assert report["ok"] is True
    assert "stdout" not in report["command"]
