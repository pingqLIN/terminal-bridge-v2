"""Tests for tb2.audit retention and recent event behavior."""

from __future__ import annotations

import json

from tb2.audit import AuditTrail, append_audit_event


def test_audit_trail_rotates_when_file_exceeds_max_bytes(tmp_path):
    trail = AuditTrail(tmp_path, max_bytes=1024, max_files=3)

    for idx in range(8):
        ok = trail.write("event", {"index": idx, "blob": "x" * 420})
        assert ok is True

    assert (tmp_path / "events.jsonl").exists()
    assert (tmp_path / "events.jsonl.1").exists()
    assert (tmp_path / "events.jsonl.2").exists()
    assert not (tmp_path / "events.jsonl.3").exists()


def test_audit_trail_recent_reads_across_rotated_files(tmp_path):
    trail = AuditTrail(tmp_path, max_bytes=1024, max_files=4)

    for idx in range(7):
        trail.write("event", {"index": idx, "blob": "x" * 420})

    recent = trail.recent(limit=3)

    assert [item["index"] for item in recent] == [4, 5, 6]


def test_audit_trail_describe_includes_retention_settings(tmp_path):
    trail = AuditTrail(tmp_path, max_bytes=2048, max_files=6)

    desc = trail.describe()

    assert desc["enabled"] is True
    assert desc["max_bytes"] == 2048
    assert desc["max_files"] == 6
    assert desc["redaction"]["mode"] == "mask"
    assert "text" in desc["redaction"]["fields"]
    assert "text" in desc["redaction"]["keys"]
    assert desc["redaction"]["stores_raw_text"] is False
    assert desc["redaction"]["stores_masked_placeholders"] is True
    assert desc["redaction"]["stores_hash_fingerprint"] is True
    assert desc["redaction"]["stores_text_metadata"] is True


def test_audit_trail_rotation_keeps_newest_entries(tmp_path):
    trail = AuditTrail(tmp_path, max_bytes=1024, max_files=2)

    for idx in range(6):
        trail.write("event", {"index": idx, "blob": "x" * 420})

    lines = []
    for name in ("events.jsonl", "events.jsonl.1"):
        path = tmp_path / name
        if not path.exists():
            continue
        lines.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines())

    assert any(item["index"] == 5 for item in lines)


def test_audit_trail_mask_mode_redacts_nested_text_fields(tmp_path):
    trail = AuditTrail(tmp_path, text_mode="mask")

    trail.write(
        "event",
        {
            "text": "secret",
            "nested": {"edited_text": "reword me"},
            "items": [{"guard_text": "sensitive"}],
        },
    )

    [item] = trail.recent(limit=1)

    assert item["text"] == "[redacted]"
    assert item["text_redacted"] is True
    assert item["text_length"] == 6
    assert item["text_lines"] == 1
    assert item["text_mode"] == "mask"
    assert len(item["text_sha256"]) == 16
    assert item["nested"]["edited_text"] == "[redacted]"
    assert item["nested"]["edited_text_redacted"] is True
    assert item["nested"]["edited_text_mode"] == "mask"
    assert len(item["nested"]["edited_text_sha256"]) == 16
    assert item["items"][0]["guard_text"] == "[redacted]"
    assert item["items"][0]["guard_text_mode"] == "mask"
    assert len(item["items"][0]["guard_text_sha256"]) == 16


def test_audit_trail_drop_mode_removes_text_content(tmp_path):
    trail = AuditTrail(tmp_path, text_mode="drop")

    trail.write("event", {"text": "secret\nline-2"})

    [item] = trail.recent(limit=1)

    assert item["text"] is None
    assert item["text_redacted"] is True
    assert item["text_length"] == 13
    assert item["text_lines"] == 2
    assert item["text_mode"] == "drop"
    assert len(item["text_sha256"]) == 16


def test_audit_trail_full_mode_keeps_text_content(tmp_path):
    trail = AuditTrail(tmp_path, text_mode="full")

    trail.write("event", {"text": "secret"})

    [item] = trail.recent(limit=1)

    assert item["text"] == "secret"
    assert item["text_redacted"] is False
    assert item["text_length"] == 6
    assert item["text_lines"] == 1
    assert item["text_mode"] == "full"
    assert len(item["text_sha256"]) == 16


def test_audit_trail_from_env_honors_text_mode_for_custom_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("TB2_AUDIT_DIR", str(tmp_path))
    monkeypatch.setenv("TB2_AUDIT_TEXT_MODE", "drop")

    trail = AuditTrail.from_env()

    assert trail.text_mode == "drop"


def test_audit_trail_redacts_top_level_and_nested_text_fields(tmp_path):
    trail = AuditTrail(tmp_path)

    trail.write(
        "room.message",
        {
            "room_id": "room-a",
            "message": {
                "text": "ship secret payload",
                "meta": {"guard_text": "do not persist"},
            },
        },
    )
    trail.write(
        "terminal.sent",
        {
            "target": "pane-a",
            "text": "export API_KEY=secret",
            "enter": True,
        },
    )

    recent = trail.recent(limit=2)
    room_event = recent[0]
    send_event = recent[1]
    raw = (tmp_path / "events.jsonl").read_text(encoding="utf-8")

    assert room_event["message"]["text"] == "[redacted]"
    assert room_event["message"]["text_redacted"] is True
    assert room_event["message"]["text_length"] == 19
    assert room_event["message"]["text_mode"] == "mask"
    assert room_event["message"]["meta"]["guard_text"] == "[redacted]"
    assert room_event["message"]["meta"]["guard_text_redacted"] is True
    assert room_event["message"]["meta"]["guard_text_mode"] == "mask"
    assert send_event["text"] == "[redacted]"
    assert send_event["text_redacted"] is True
    assert send_event["text_length"] == 21
    assert send_event["text_mode"] == "mask"
    assert "ship secret payload" not in raw
    assert "do not persist" not in raw
    assert "export API_KEY=secret" not in raw


def test_append_audit_event_returns_sanitized_payload(tmp_path, monkeypatch):
    monkeypatch.setenv("TB2_AUDIT_DIR", str(tmp_path))

    entry = append_audit_event(
        "room.message_posted",
        room_id="room-a",
        payload={"text": "sensitive", "meta": {"guard_text": "hidden"}},
    )

    assert entry["payload"]["text"] == "[redacted]"
    assert entry["payload"]["text_redacted"] is True
    assert entry["payload"]["text_mode"] == "mask"
    assert len(entry["payload"]["text_sha256"]) == 16
    assert entry["payload"]["meta"]["guard_text"] == "[redacted]"
    assert entry["payload"]["meta"]["guard_text_redacted"] is True
    assert len(entry["payload"]["meta"]["guard_text_sha256"]) == 16

    raw = (tmp_path / "events.jsonl").read_text(encoding="utf-8")
    assert "sensitive" not in raw
    assert "hidden" not in raw


def test_audit_trail_redacts_text_fields_recursively(tmp_path):
    trail = AuditTrail(tmp_path)

    trail.write(
        "event",
        {
            "text": "root secret",
            "message": {
                "text": "nested secret",
                "meta": {
                    "guard_text": "guard secret",
                },
            },
            "payload": {
                "edited_text": "edited secret",
            },
            "items": [
                {"text": "list secret"},
            ],
        },
    )

    recent = trail.recent(limit=1)
    item = recent[0]
    raw = (tmp_path / "events.jsonl").read_text(encoding="utf-8")

    assert "root secret" not in raw
    assert "nested secret" not in raw
    assert "guard secret" not in raw
    assert "edited secret" not in raw
    assert "list secret" not in raw
    assert item["text"] == "[redacted]"
    assert item["text_redacted"] is True
    assert item["text_length"] == len("root secret")
    assert item["text_mode"] == "mask"
    assert len(item["text_sha256"]) == 16
    assert item["message"]["text"] == "[redacted]"
    assert item["message"]["text_redacted"] is True
    assert item["message"]["text_mode"] == "mask"
    assert len(item["message"]["text_sha256"]) == 16
    assert item["message"]["meta"]["guard_text"] == "[redacted]"
    assert item["message"]["meta"]["guard_text_mode"] == "mask"
    assert len(item["message"]["meta"]["guard_text_sha256"]) == 16
    assert item["payload"]["edited_text"] == "[redacted]"
    assert item["payload"]["edited_text_mode"] == "mask"
    assert len(item["payload"]["edited_text_sha256"]) == 16
    assert item["items"][0]["text"] == "[redacted]"
    assert item["items"][0]["text_mode"] == "mask"
    assert len(item["items"][0]["text_sha256"]) == 16
