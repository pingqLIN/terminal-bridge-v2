from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from tb2.workflow_observation.adapters import verify_source_observation
from tb2.workflow_observation.config import resolve_config, validators
from tb2.workflow_observation.model import Model, Rejection
from tb2.workflow_observation.normalize import normalize_tag
from tb2.workflow_observation.reducer import reduce_observation
from tb2.workflow_observation.storage import ObservationJournal
from tests.workflow_observation_driver import SyntheticVerifier, run

FIXTURES = Path(__file__).parent / "fixtures" / "observation"
SCENARIOS = json.loads((FIXTURES / "scenarios.json").read_text(encoding="utf-8"))
STRUCTURAL = json.loads((FIXTURES / "structural.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", STRUCTURAL, ids=lambda case: case["id"])
def test_structural(case):
    assert validators()[case["schema"].removesuffix(".schema.json")].is_valid(case["data"]) is case["valid"]


@pytest.mark.parametrize("case", SCENARIOS, ids=lambda case: case["id"])
def test_conformance(case):
    result = run(case["input"])
    assert result == run(case["input"])
    for state in result["states"].values():
        validators()["state"].validate(state)
    validators()["projection"].validate(result["projection"])
    for assertion in case["assertions"]:
        value = result
        for part in assertion["path"].split("/")[1:]:
            part = part.replace("~1", "/").replace("~0", "~")
            value = value[int(part)] if isinstance(value, list) else value[part]
        assert value == assertion["equals"], assertion["path"]


def observation():
    step = SCENARIOS[1]["input"]["steps"][0]
    return verify_source_observation(step["event"], SyntheticVerifier(step["testContext"]), resolve_config())


def test_normalization_and_defaults():
    assert normalize_tag("RUNNING", "legacy-agent-task", "task")["code"] == "EXECUTING"
    assert normalize_tag("RUNNING", "native", "gate")["code"] == "RUNNING"
    assert normalize_tag("PASS", "native", "unknown")["domain"] == "unknown"
    with pytest.raises(ValueError):
        resolve_config({"autoDispatch": True})


@pytest.mark.parametrize("field,value", [("testContext", {"sourceBound": True}), ("pid", 123), ("raw", "secret-marker"), ("command", "echo secret-marker")])
def test_reject_before_authority_resolution(field, value):
    event = copy.deepcopy(SCENARIOS[1]["input"]["steps"][0]["event"])
    event[field] = value
    result = verify_source_observation(event, object(), resolve_config())
    assert result == Rejection("INVALID_INPUT")
    assert "secret-marker" not in repr(result)


def test_replay_duplicate_and_corrupt_checkpoint(tmp_path):
    with ObservationJournal(tmp_path, resolve_config()) as journal:
        journal.append(observation())
        journal.checkpoint()
        (tmp_path / "checkpoint.json").write_text("broken", encoding="utf-8")
        restored = journal.load()
        assert reduce_observation(restored, observation()) == "DUPLICATE"
        assert {"code": "CHECKPOINT_CORRUPT"} in restored.diagnostics


def test_journal_partial_tail_and_middle_corruption(tmp_path):
    with ObservationJournal(tmp_path, resolve_config()) as journal:
        journal.append(observation())
        with (tmp_path / "events.jsonl").open("ab") as stream:
            stream.write(b'{"partial"')
        model = journal.load()
        assert model.states["t-main:a-1"]["lifecycle"] == "EXECUTING"
        assert {"code": "JOURNAL_TRUNCATED"} in model.diagnostics
        with pytest.raises(RuntimeError, match="NOT_WRITABLE"):
            journal.append(observation())
    (tmp_path / "events.jsonl").write_bytes(b'{}\n')
    with pytest.raises(RuntimeError, match="JOURNAL_CORRUPT"):
        ObservationJournal(tmp_path, resolve_config()).load()


def test_single_writer_and_failed_replace(tmp_path, monkeypatch):
    with ObservationJournal(tmp_path, resolve_config()) as journal:
        journal.append(observation())
        journal.checkpoint()
        before = (tmp_path / "checkpoint.json").read_bytes()
        with pytest.raises(RuntimeError, match="WRITER_BUSY"):
            with ObservationJournal(tmp_path, resolve_config()):
                pass
        def fail_replace(*_args):
            raise OSError("simulated failure")
        monkeypatch.setattr("tb2.workflow_observation.storage.os.replace", fail_replace)
        with pytest.raises(OSError):
            journal.checkpoint()
        assert (tmp_path / "checkpoint.json").read_bytes() == before
        assert journal.load().states["t-main:a-1"]["lifecycle"] == "EXECUTING"


def test_consumed_semantic_rejection_does_not_deadlock():
    request = copy.deepcopy(SCENARIOS[1]["input"])
    first = request["steps"][0]
    first["testContext"]["contractHashVerified"] = False
    second = copy.deepcopy(first)
    second["event"]["eventId"] = "next-event"
    second["event"]["source"]["sequence"] = 2
    second["testContext"]["contractHashVerified"] = True
    request["steps"].append(second)
    result = run(request)
    assert [item["code"] for item in result["outcomes"]] == ["CONTRACT_HASH_MISMATCH", "ACCEPTED"]
    assert result["states"]["t-main:a-1"]["lifecycle"] == "EXECUTING"


def test_capacity_never_projects_complete():
    from tb2.workflow_observation.projection import project_goal
    model = Model(config=resolve_config())
    reduce_observation(model, observation())
    model.diagnostics.append({"code": "CAPACITY_EXCEEDED"})
    projection = project_goal(model, "p-demo", "g-main", "2026-09-11T02:00:00.000Z", "LIVE", model.config)
    assert projection["sourceStatus"] == "PARTIAL"
    assert projection["mainline"]["status"] == "UNKNOWN"
