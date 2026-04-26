"""Tests for extracted status aggregation helpers."""

from __future__ import annotations

from tb2.status import (
    fleet_governance_compliance_snapshot,
    orphaned_workstream_entries,
    recovery_status_snapshot,
    stale_workstream_entries,
    workstream_governance_compliance,
)


def test_orphaned_workstream_entries_only_include_orphaned_items():
    items = orphaned_workstream_entries([
        {
            "workstream_id": "ws-a",
            "bridge_id": "br-a",
            "room_id": "room-a",
            "state": "live",
            "review_mode": "auto",
            "topology": {"orphaned": True, "room_present": False, "bridge_present": False},
        },
        {
            "workstream_id": "ws-b",
            "bridge_id": "br-b",
            "room_id": "room-b",
            "state": "live",
            "review_mode": "auto",
            "topology": {"orphaned": False},
        },
    ])

    assert items == [{
        "workstream_id": "ws-a",
        "bridge_id": "br-a",
        "room_id": "room-a",
        "state": "live",
        "review_mode": "auto",
        "room_present": False,
        "bridge_present": False,
    }]


def test_stale_workstream_entries_capture_alert_codes():
    items = stale_workstream_entries([
        {
            "workstream_id": "ws-a",
            "health": {
                "state": "warn",
                "escalation": "review",
                "alerts": [{"code": "silent_stream"}, {"code": "other"}],
            },
        },
        {
            "workstream_id": "ws-b",
            "health": {
                "state": "ok",
                "escalation": "observe",
                "alerts": [{"code": "other"}],
            },
        },
    ])

    assert items == [{
        "workstream_id": "ws-a",
        "state": "warn",
        "escalation": "review",
        "alerts": ["silent_stream", "other"],
    }]


def test_recovery_status_snapshot_uses_continuity_overrides():
    payload = recovery_status_snapshot(
        [
            {"workstream_id": "ws-restored", "recovery": {"restored_from_snapshot": True}},
            {"workstream_id": "ws-live", "recovery": {"state": "live_runtime"}},
        ],
        continuity={
            "mode": "best_effort_restore",
            "runtime_restored": True,
            "restore_order": ["main", "sub"],
            "restored_workstream_count": 5,
        },
        default_protocol="local-default",
        default_restore_order=["fallback-main"],
    )

    assert payload["protocol"] == "local-default"
    assert payload["restore_order"] == ["main", "sub"]
    assert payload["runtime_restored"] is True
    assert payload["restored_count"] == 5
    assert payload["live_runtime_workstreams"] == ["ws-live"]


def test_workstream_governance_compliance_marks_critical_and_exception_issues():
    item = {
        "workstream_id": "ws-a",
        "governance": {
            "review_mode_state": {"override_active": True, "override_source": "operator"},
            "policy_state": {"overrides": {"pending_limit": {"source": "operator_exception"}}},
        },
        "health": {"state": "critical", "summary": "quota blocked"},
        "recovery": {"manual_takeover_required": True},
    }

    payload = workstream_governance_compliance(item)

    assert payload["state"] == "critical"
    assert payload["issue_count"] == 4


def test_fleet_governance_compliance_snapshot_counts_states():
    payload = fleet_governance_compliance_snapshot([
        {"workstream_id": "ws-ok", "health": {"state": "ok"}},
        {"workstream_id": "ws-warn", "health": {"state": "warn", "summary": "warn"}},
        {"workstream_id": "ws-critical", "health": {"state": "critical", "summary": "critical"}},
    ])

    assert payload["state"] == "critical"
    assert payload["total"] == 3
    assert payload["compliant"] == 1
    assert payload["exception"] == 1
    assert payload["critical"] == 1
