"""Read-only TaskContracts snapshot inspection for the TB2 observation core.

This adapter deliberately reports verified source metadata without converting
TaskContracts lifecycle into a TB2 event. TaskContracts has no attempt identity
and does not provide all evidence bindings required by the TB2 snapshot schema.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from types import ModuleType
from typing import cast

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")
_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")
_STATUSES = {"READY", "RUNNING", "BLOCKED", "PASS", "FAILED", "SUPERSEDED"}
_SNAPSHOT_FILES = ("TASK.json", "CONTRACT.sha256", "STATE.json", "events.jsonl")
_LIMITATIONS = [
    "ATTEMPT_ID_UNAVAILABLE",
    "TASKCONTRACTS_STATUS_NOT_MAPPED_TO_TB2_LIFECYCLE",
    "EXECUTION_BINDING_UNAVAILABLE",
    "ACCEPTANCE_REFERENCE_UNAVAILABLE",
    "REVIEW_AND_DECISION_DIMENSIONS_UNAVAILABLE",
]


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _snapshot_digest(task_dir: Path) -> tuple[str, ...]:
    digests = []
    for name in _SNAPSHOT_FILES:
        path = task_dir / name
        digests.append(_file_digest(path) if path.is_file() else "MISSING")
    return tuple(digests)


def _load_verifier(path: Path, expected_digest: str | None = None) -> ModuleType:
    """Load only the operator-selected local verifier module."""
    verifier_path = path.expanduser().resolve(strict=True)
    if not verifier_path.is_file() or verifier_path.name != "task_contract.py":
        raise ValueError("VERIFIER_PATH_INVALID")
    name = "_tb2_taskcontracts_verifier_" + hashlib.sha256(str(verifier_path).encode()).hexdigest()[:16]
    module = ModuleType(name)
    module.__file__ = str(verifier_path)
    sys.modules[name] = module
    try:
        source = verifier_path.read_bytes()
        if expected_digest is not None and hashlib.sha256(source).hexdigest() != expected_digest:
            raise ValueError("VERIFIER_CHANGED")
        exec(compile(source, str(verifier_path), "exec"), module.__dict__)
    except Exception:
        sys.modules.pop(name, None)
        raise ValueError("VERIFIER_LOAD_FAILED") from None
    if not callable(getattr(module, "inspect", None)) or not callable(getattr(module, "canonical_sha256", None)):
        sys.modules.pop(name, None)
        raise ValueError("VERIFIER_API_UNSUPPORTED")
    return module


def _task_id(value: object) -> str | None:
    if isinstance(value, str) and _ID.fullmatch(value):
        return value
    return None


def _safe_result(code: str, as_of: str | None, retries: int) -> dict[str, object]:
    return {
        "status": code,
        "observedAt": as_of,
        "event": None,
        "limitations": list(_LIMITATIONS),
        "retryCount": retries,
    }


def observe_task(
    task_dir: Path,
    project: Path,
    verifier: Path,
    project_id: str,
    goal_id: str,
    as_of: str,
    *,
    max_retries: int = 3,
) -> dict[str, object]:
    """Verify and summarize one canonical task without exposing task prose.

    ``verifier`` is an operator-selected local TaskContracts verifier path. It
    is never read from an event or any other producer input. ``as_of`` is the
    caller's explicit UTC receiver time; this function never reads the clock.
    """
    if not isinstance(as_of, str) or not _UTC.fullmatch(as_of):
        return _safe_result("INVALID_AS_OF", None, 0)
    try:
        datetime.strptime(as_of, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError:
        return _safe_result("INVALID_AS_OF", None, 0)
    try:
        if not isinstance(project_id, str) or not _ID.fullmatch(project_id):
            return _safe_result("INVALID_SCOPE_ID", as_of, 0)
        if not isinstance(goal_id, str) or not _ID.fullmatch(goal_id):
            return _safe_result("INVALID_SCOPE_ID", as_of, 0)
        task_path = Path(task_dir).expanduser().resolve(strict=True)
        project_path = Path(project).expanduser().resolve(strict=True)
        verifier_path = Path(verifier).expanduser().resolve(strict=True)
        verifier_digest = _file_digest(verifier_path)
        module = _load_verifier(verifier_path, verifier_digest)
        if verifier_digest != _file_digest(verifier_path):
            return _safe_result("VERIFIER_CHANGED", as_of, 0)
    except (OSError, TypeError, ValueError):
        return _safe_result("SOURCE_UNAVAILABLE", as_of, 0)

    if not isinstance(max_retries, int) or isinstance(max_retries, bool) or not 1 <= max_retries <= 5:
        return _safe_result("INVALID_RETRY_LIMIT", as_of, 0)
    for retry in range(max_retries):
        try:
            before = _snapshot_digest(task_path)
            contract, state, issues = module.inspect(task_path, project_path)
            contract_hash = module.canonical_sha256(task_path / "TASK.json")
            after = _snapshot_digest(task_path)
            if verifier_digest != _file_digest(verifier_path):
                return _safe_result("VERIFIER_CHANGED", as_of, retry)
            if before != after:
                continue
            if issues:
                return _safe_result("VERIFIER_REJECTED", as_of, retry)
            if not isinstance(contract, dict) or not isinstance(state, dict):
                return _safe_result("VERIFIER_RESULT_INVALID", as_of, retry)
            contract = cast(dict[str, object], contract)
            state = cast(dict[str, object], state)
            task_id = _task_id(contract.get("task_id"))
            canonical_status = state.get("status")
            if task_id is None:
                return _safe_result("UNSAFE_TASK_ID", as_of, retry)
            if not isinstance(canonical_status, str) or canonical_status not in _STATUSES:
                return _safe_result("VERIFIER_RESULT_INVALID", as_of, retry)
            revision = state.get("revision")
            if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
                revision = None
            if not isinstance(contract_hash, str) or not re.fullmatch(r"[a-f0-9]{64}", contract_hash):
                return _safe_result("VERIFIER_RESULT_INVALID", as_of, retry)
            return {
                "status": "VERIFIED_SOURCE_SNAPSHOT",
                "observedAt": as_of,
                "scope": {"projectId": project_id, "goalId": goal_id},
                "taskId": task_id,
                "schemaVersion": contract.get("schema_version"),
                "canonicalStatus": canonical_status,
                "authorityRevision": revision,
                "contractSha256": contract_hash,
                "sourceContext": {
                    "producerKind": "taskcontracts",
                    "verification": "TASKCONTRACT_INSPECT_PASSED",
                },
                "event": None,
                "limitations": list(_LIMITATIONS),
                "retryCount": retry,
            }
        except Exception:
            return _safe_result("SOURCE_UNAVAILABLE", as_of, retry)
    return _safe_result("TORN_READ", as_of, max_retries)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", required=True, type=Path, help="canonical TaskContracts task directory")
    parser.add_argument("--project", required=True, type=Path, help="canonical TaskContracts project root")
    parser.add_argument("--verifier", required=True, type=Path, help="trusted local task_contract.py selected by the operator")
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--goal-id", required=True)
    parser.add_argument("--as-of", required=True, help="explicit UTC receiver time: YYYY-MM-DDTHH:MM:SS.mmmZ")
    args = parser.parse_args(argv)
    result = observe_task(args.task, args.project, args.verifier, args.project_id, args.goal_id, args.as_of)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "VERIFIED_SOURCE_SNAPSHOT" else 2


if __name__ == "__main__":
    raise SystemExit(main())
