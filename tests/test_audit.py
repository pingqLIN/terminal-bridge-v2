"""Tests for tb2.audit retention and recent event behavior."""

from __future__ import annotations

import json

from tb2.audit import AuditTrail


def test_audit_trail_rotates_when_file_exceeds_max_bytes(tmp_path):
    trail = AuditTrail(tmp_path, max_bytes=1024, max_files=3)

    for idx in range(8):
        ok = trail.write("event", {"index": idx, "text": "x" * 420})
        assert ok is True

    assert (tmp_path / "events.jsonl").exists()
    assert (tmp_path / "events.jsonl.1").exists()
    assert (tmp_path / "events.jsonl.2").exists()
    assert not (tmp_path / "events.jsonl.3").exists()


def test_audit_trail_recent_reads_across_rotated_files(tmp_path):
    trail = AuditTrail(tmp_path, max_bytes=1024, max_files=4)

    for idx in range(7):
        trail.write("event", {"index": idx, "text": "x" * 420})

    recent = trail.recent(limit=3)

    assert [item["index"] for item in recent] == [4, 5, 6]


def test_audit_trail_describe_includes_retention_settings(tmp_path):
    trail = AuditTrail(tmp_path, max_bytes=2048, max_files=6)

    desc = trail.describe()

    assert desc["enabled"] is True
    assert desc["max_bytes"] == 2048
    assert desc["max_files"] == 6


def test_audit_trail_rotation_keeps_newest_entries(tmp_path):
    trail = AuditTrail(tmp_path, max_bytes=1024, max_files=2)

    for idx in range(6):
        trail.write("event", {"index": idx, "text": "x" * 420})

    lines = []
    for name in ("events.jsonl", "events.jsonl.1"):
        path = tmp_path / name
        if not path.exists():
            continue
        lines.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines())

    assert any(item["index"] == 5 for item in lines)
