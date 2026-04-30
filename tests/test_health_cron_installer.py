from __future__ import annotations

import argparse
from pathlib import Path

from tools import install_tb2_health_cron as cron


def _args(tmp_path: Path, **overrides):
    data = {
        "repo": str(tmp_path),
        "python": "/usr/bin/python3",
        "unit": "tb2.service",
        "base_url": "http://127.0.0.1:3189",
        "log": str(tmp_path / "health.jsonl"),
        "cron_log": str(tmp_path / "health-cron.log"),
        "interval_minutes": 5,
        "max_bytes": 10 * 1024 * 1024,
        "max_files": 5,
        "dry_run": True,
    }
    data.update(overrides)
    return argparse.Namespace(**data)


def test_build_entry_contains_rotation_and_marker(tmp_path):
    entry = cron.build_entry(_args(tmp_path))

    assert entry.startswith("*/5 * * * * cd ")
    assert "tools/tb2_scheduled_health_check.py" in entry
    assert "--max-bytes 10485760" in entry
    assert "--max-files 5" in entry
    assert cron.MARKER in entry


def test_without_entry_preserves_unrelated_cron_lines():
    text = "\n".join([
        "17 3 */15 * * cleanup # keep",
        "*/5 * * * * old tb2 line # tb2_health_check",
    ])

    assert cron.without_entry(text) == "17 3 */15 * * cleanup # keep"


def test_install_replaces_existing_entry(monkeypatch, tmp_path):
    monkeypatch.setattr(
        cron,
        "read_crontab",
        lambda: "1 1 * * * keep\n*/5 * * * * old # tb2_health_check\n",
    )
    captured = {}
    monkeypatch.setattr(cron, "write_crontab", lambda text: captured.setdefault("text", text))

    result = cron.install(_args(tmp_path, dry_run=False))

    assert result["action"] == "install"
    assert captured["text"].count(cron.MARKER) == 1
    assert "1 1 * * * keep" in captured["text"]


def test_status_reports_installed_entries(monkeypatch):
    monkeypatch.setattr(cron, "read_crontab", lambda: "*/5 * * * * check # tb2_health_check\n")

    result = cron.status(argparse.Namespace())

    assert result["installed"] is True
    assert result["entries"] == ["*/5 * * * * check # tb2_health_check"]
