import json
from pathlib import Path


def _sample() -> dict:
    path = Path(__file__).resolve().parents[1] / "examples" / "tb2-execution-evidence.sample.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_execution_evidence_sample_preserves_tb2_boundary() -> None:
    sample = _sample()

    assert sample["export_type"] == "tb2_execution_evidence"
    assert sample["normalized_audit_report"] is False
    assert "external-audit-orchestrator owns packet schemas and normalized reports" in sample["boundary"]
    assert "audit_packet" not in sample
    assert "reviewer_requests" not in sample
    assert "expected_output_schema" not in sample
    assert "normalized_report" not in sample


def test_execution_evidence_sample_exposes_adapter_inputs() -> None:
    sample = _sample()

    assert sample["workstream_id"] == "review-main"
    assert sample["bridge_id"] == "review-bridge"
    assert sample["room_id"] == "review-room"
    assert sample["workstream"]["backend"]["kind"] == "process"
    assert sample["messages"][0]["kind"] == "review_request"
    assert sample["messages"][0]["source"]["type"] == "client"
    assert sample["messages"][0]["source"]["trusted"] is False
    assert sample["audit_events"][0]["event"] == "operator.room_post"
    assert sample["audit"]["redaction"]["stores_raw_text"] is False


def test_execution_evidence_sample_uses_sample_paths_only() -> None:
    sample = _sample()

    assert sample["audit"]["root"].startswith("/sample/")
    assert sample["audit"]["file"].startswith("/sample/")
