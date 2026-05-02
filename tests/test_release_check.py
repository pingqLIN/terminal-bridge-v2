from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from tools import release_check


def _args(**overrides):
    data = {
        "python": "python3",
        "skip_tests": False,
        "pytest_args": ["tests", "-q"],
    }
    data.update(overrides)
    return argparse.Namespace(**data)


def test_checks_include_release_diagnostics_and_pytest():
    items = release_check.checks(_args())

    assert [item.name for item in items] == [
        "diff-check",
        "doctor-json",
        "profiles-verbose",
        "pytest",
    ]
    assert items[1].require_json is True
    assert items[-1].command == ["python3", "-m", "pytest", "tests", "-q"]


def test_checks_can_skip_pytest():
    items = release_check.checks(_args(skip_tests=True))

    assert [item.name for item in items] == ["diff-check", "doctor-json", "profiles-verbose"]


def test_run_rejects_invalid_json(monkeypatch, tmp_path: Path):
    def fake_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(["python3"], 0, stdout="not json", stderr="")

    monkeypatch.setattr(release_check.subprocess, "run", fake_run)

    result = release_check.run(
        release_check.Check("doctor-json", ["python3", "-m", "tb2", "doctor", "--json"], require_json=True),
        cwd=tmp_path,
    )

    assert result.ok is False
    assert "invalid JSON output" in result.error


def test_render_summarizes_failures():
    text = release_check.render([
        release_check.Result("diff-check", ["git", "diff", "--check"], True, 0, "", ""),
        release_check.Result("pytest", ["python3", "-m", "pytest"], False, 1, "", "failed"),
    ])

    assert "PASS diff-check" in text
    assert "FAIL pytest" in text
    assert "stderr: failed" in text
