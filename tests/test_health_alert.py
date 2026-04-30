from __future__ import annotations

import json

from tools import tb2_health_alert as alert


def test_read_marker_reports_absent_alert(tmp_path):
    result = alert.read_marker(tmp_path / "missing.json")

    assert result["ok"] is True
    assert result["active"] is False
    assert result["installed"] is False


def test_read_marker_returns_existing_object(tmp_path):
    path = tmp_path / "alert.json"
    path.write_text(json.dumps({"ok": False, "active": True}), encoding="utf-8")

    result = alert.read_marker(path)

    assert result["ok"] is False
    assert result["active"] is True
    assert result["installed"] is True


def test_read_marker_flags_invalid_json(tmp_path):
    path = tmp_path / "alert.json"
    path.write_text("{", encoding="utf-8")

    result = alert.read_marker(path)

    assert result["ok"] is False
    assert result["active"] is True
    assert "not valid JSON" in result["summary"]
