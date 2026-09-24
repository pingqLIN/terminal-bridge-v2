from __future__ import annotations

import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest


def _verifier_path() -> Path:
    configured = os.environ.get("TB2_TASKCONTRACTS_VERIFIER")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2] / "TaskContracts-Automation" / "scripts" / "task_contract.py"


def _write_fixture(root: Path, verifier_path: Path, status: str = "BLOCKED") -> tuple[Path, Path]:
    project = root / "project"
    task = project / "task"
    task.mkdir(parents=True)
    contract = {
        "schema_version": "1.0",
        "task_id": "demo-task",
        "project": {"project_id": "demo-project", "expected_root": str(project),
                    "git": {"required": False, "remote": None, "baseline_commit": None}},
        "task_type": "development",
        "objective": "PRIVATE_OBJECTIVE_MUST_NOT_LEAK",
        "authority": {"kind": "user-direct", "source_ref": "fixture", "issued_at": "2026-01-01T00:00:00Z", "supersedes": None},
        "baseline": {"description": "fixture", "required_inputs": []},
        "allowed_actions": [{"id": "inspect", "action": "Inspect fixture"}],
        "forbidden_actions": ["Do not execute"],
        "hard_gates": [],
        "acceptance": [{"id": "accept", "criterion": "fixture only"}],
        "artifacts": {"root": str(task), "expected": []},
    }
    state = {
        "schema_version": "1.0", "task_id": "demo-task", "status": status,
        "current_state": "PRIVATE_STATE_MUST_NOT_LEAK", "next_action_id": "inspect",
        "next_action": "Inspect fixture", "blocker": "fixture blocker" if status == "BLOCKED" else None,
        "resume_from": None, "last_verified": None, "last_verified_commit": None,
        "artifact_path": None, "updated_at": "2026-01-01T00:00:00Z",
    }
    task_json = json.dumps(contract, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    (task / "TASK.json").write_bytes(task_json)
    (task / "CONTRACT.sha256").write_text(hashlib.sha256(task_json).hexdigest() + "\n", encoding="ascii")
    (task / "STATE.json").write_text(json.dumps(state), encoding="utf-8")
    (task / "events.jsonl").write_text("", encoding="utf-8")
    return task, project


def test_observe_task_uses_real_inspector_and_returns_redacted_non_event(tmp_path: Path) -> None:
    verifier = _verifier_path()
    if not verifier.is_file():
        pytest.skip("Set TB2_TASKCONTRACTS_VERIFIER to an approved task_contract.py")
    task, project = _write_fixture(tmp_path, verifier)

    module = importlib.import_module("tb2.workflow_observation.taskcontracts")
    result = module.observe_task(task, project, verifier, "demo-project", "demo-goal", "2026-09-24T00:00:00.000Z")

    encoded = json.dumps(result)
    assert result["status"] == "VERIFIED_SOURCE_SNAPSHOT"
    assert result["canonicalStatus"] == "BLOCKED"
    assert result["authorityRevision"] is None
    assert result["event"] is None
    assert "ATTEMPT_ID_UNAVAILABLE" in result["limitations"]
    assert "PRIVATE_OBJECTIVE_MUST_NOT_LEAK" not in encoded
    assert "PRIVATE_STATE_MUST_NOT_LEAK" not in encoded
    assert str(task) not in encoded


def test_observe_task_rejects_bad_seal_without_leaking_verifier_messages(tmp_path: Path) -> None:
    verifier = _verifier_path()
    if not verifier.is_file():
        pytest.skip("Set TB2_TASKCONTRACTS_VERIFIER to an approved task_contract.py")
    task, project = _write_fixture(tmp_path, verifier)
    (task / "CONTRACT.sha256").write_text("0" * 64, encoding="ascii")

    module = importlib.import_module("tb2.workflow_observation.taskcontracts")
    result = module.observe_task(task, project, verifier, "demo-project", "demo-goal", "2026-09-24T00:00:00.000Z")

    assert result["status"] == "VERIFIER_REJECTED"
    assert result["event"] is None
    assert str(task) not in json.dumps(result)


def test_observe_task_retries_a_changed_source_snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    verifier = _verifier_path()
    if not verifier.is_file():
        pytest.skip("Set TB2_TASKCONTRACTS_VERIFIER to an approved task_contract.py")
    task, project = _write_fixture(tmp_path, verifier)
    module = importlib.import_module("tb2.workflow_observation.taskcontracts")
    actual_loader = module._load_verifier
    original = actual_loader(verifier)
    calls = 0

    def inspect_once_then_change(task_dir: Path, project_dir: Path) -> tuple[dict, dict, list]:
        nonlocal calls
        result = original.inspect(task_dir, project_dir)
        calls += 1
        if calls == 1:
            state = json.loads((task / "STATE.json").read_text(encoding="utf-8"))
            state["status"] = "FAILED"
            state["blocker"] = None
            (task / "STATE.json").write_text(json.dumps(state), encoding="utf-8")
        return result

    monkeypatch.setattr(module, "_load_verifier", lambda _path, _digest=None: SimpleNamespace(
        inspect=inspect_once_then_change, canonical_sha256=original.canonical_sha256))
    result = module.observe_task(task, project, verifier, "demo-project", "demo-goal", "2026-09-24T00:00:00.000Z")

    assert result["status"] == "VERIFIED_SOURCE_SNAPSHOT"
    assert result["canonicalStatus"] == "FAILED"
    assert result["retryCount"] == 1


def test_taskcontracts_module_cli_emits_only_sanitized_result(tmp_path: Path) -> None:
    verifier = _verifier_path()
    if not verifier.is_file():
        pytest.skip("Set TB2_TASKCONTRACTS_VERIFIER to an approved task_contract.py")
    task, project = _write_fixture(tmp_path, verifier)
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "-m", "tb2.workflow_observation.taskcontracts", "--task", str(task),
         "--project", str(project), "--verifier", str(verifier), "--project-id", "demo-project",
         "--goal-id", "demo-goal", "--as-of", "2026-09-24T00:00:00.000Z"],
        cwd=root, capture_output=True, text=True, check=False,
    )

    assert result.returncode == 0
    assert json.loads(result.stdout)["status"] == "VERIFIED_SOURCE_SNAPSHOT"
    assert "PRIVATE_OBJECTIVE_MUST_NOT_LEAK" not in result.stdout
    assert "PRIVATE_STATE_MUST_NOT_LEAK" not in result.stdout
    assert str(task) not in result.stdout
    assert result.stderr == ""
