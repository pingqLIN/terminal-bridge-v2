"""Status aggregation helpers for workstream and fleet summaries."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence


def orphaned_workstream_entries(payloads: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "workstream_id": str(item["workstream_id"]),
            "bridge_id": str(item["bridge_id"]),
            "room_id": str(item["room_id"]),
            "state": str(item["state"]),
            "review_mode": str(item["review_mode"]),
            "room_present": bool(item.get("topology", {}).get("room_present", True)),
            "bridge_present": bool(item.get("topology", {}).get("bridge_present", False)),
        }
        for item in payloads
        if bool(item.get("topology", {}).get("orphaned"))
    ]


def stale_workstream_entries(payloads: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    alert_codes = {
        "silent_stream",
        "pending_backlog",
        "quota_blocked",
        "restore_failed",
        "orphaned_workstream",
        "parent_missing",
        "dependency_blocked",
    }
    return [
        {
            "workstream_id": str(item["workstream_id"]),
            "state": str(item["health"]["state"]),
            "escalation": str(item["health"]["escalation"]),
            "alerts": [str(alert.get("code", "")) for alert in item["health"].get("alerts", [])],
        }
        for item in payloads
        if any(str(alert.get("code", "")) in alert_codes for alert in item["health"].get("alerts", []))
    ]


def recovery_status_snapshot(
    workstream_payloads: Sequence[Mapping[str, Any]],
    *,
    continuity: Optional[Mapping[str, Any]],
    default_protocol: str,
    default_restore_order: Sequence[str],
) -> Dict[str, Any]:
    continuity_dict = dict(continuity) if isinstance(continuity, Mapping) else {}
    restore_order = continuity_dict.get("restore_order")
    restore_order_items = [str(item) for item in restore_order] if isinstance(restore_order, list) else [str(item) for item in default_restore_order]
    restored_ids = [
        str(item["workstream_id"])
        for item in workstream_payloads
        if bool(item.get("recovery", {}).get("restored_from_snapshot"))
    ]
    manual_takeover_ids = [
        str(item["workstream_id"])
        for item in workstream_payloads
        if bool(item.get("recovery", {}).get("manual_takeover_required"))
    ]
    live_runtime_ids = [
        str(item["workstream_id"])
        for item in workstream_payloads
        if str(item.get("recovery", {}).get("state", "")) == "live_runtime"
    ]
    restored_count = continuity_dict.get("restored_workstream_count")
    manual_takeover_count = continuity_dict.get("manual_takeover_workstream_count")
    lost_count = continuity_dict.get("lost_workstream_count")
    return {
        "protocol": str(continuity_dict.get("recovery_protocol") or default_protocol),
        "restore_order": restore_order_items,
        "continuity_mode": str(continuity_dict.get("mode", "")),
        "runtime_restored": bool(continuity_dict.get("runtime_restored", False)),
        "last_recovery_at": continuity_dict.get("last_recovery_at"),
        "restored_count": int(restored_count) if restored_count is not None else len(restored_ids),
        "restored_workstreams": restored_ids,
        "manual_takeover_count": int(manual_takeover_count) if manual_takeover_count is not None else len(manual_takeover_ids),
        "manual_takeover_workstreams": manual_takeover_ids,
        "lost_count": int(lost_count) if lost_count is not None else len(manual_takeover_ids),
        "lost_workstreams": manual_takeover_ids,
        "live_runtime_count": len(live_runtime_ids),
        "live_runtime_workstreams": live_runtime_ids,
    }


def workstream_governance_compliance(item: Mapping[str, Any]) -> Dict[str, Any]:
    governance = item.get("governance", {}) if isinstance(item.get("governance"), dict) else {}
    review_state = governance.get("review_mode_state", {}) if isinstance(governance.get("review_mode_state"), dict) else {}
    policy_state = governance.get("policy_state", {}) if isinstance(governance.get("policy_state"), dict) else {}
    policy_overrides = policy_state.get("overrides", {}) if isinstance(policy_state.get("overrides"), dict) else {}
    health = item.get("health", {}) if isinstance(item.get("health"), dict) else {}
    recovery = item.get("recovery", {}) if isinstance(item.get("recovery"), dict) else {}
    issues: List[Dict[str, Any]] = []

    if bool(review_state.get("override_active")):
        issues.append({
            "kind": "review_mode_override",
            "severity": "warn",
            "summary": "review mode is under operator override",
            "source": review_state.get("override_source", "operator_override"),
        })
    for key in sorted(policy_overrides):
        override = policy_overrides.get(key, {}) if isinstance(policy_overrides.get(key), dict) else {}
        issues.append({
            "kind": "policy_exception",
            "severity": "warn",
            "key": key,
            "summary": f"policy key {key} is overridden",
            "source": override.get("source", "operator_exception"),
        })
    if bool(recovery.get("manual_takeover_required")):
        issues.append({
            "kind": "manual_takeover",
            "severity": "critical",
            "summary": "manual takeover is required after recovery failure",
        })
    health_state = str(health.get("state", "ok"))
    if health_state == "critical":
        issues.append({
            "kind": "health_critical",
            "severity": "critical",
            "summary": str(health.get("summary", "critical workstream health")),
        })
    elif health_state == "warn":
        issues.append({
            "kind": "health_warn",
            "severity": "warn",
            "summary": str(health.get("summary", "workstream health warning")),
        })

    state = "compliant"
    if any(issue["severity"] == "critical" for issue in issues):
        state = "critical"
    elif issues:
        state = "exception"
    return {
        "workstream_id": item.get("workstream_id"),
        "state": state,
        "issue_count": len(issues),
        "issues": issues,
    }


def fleet_governance_compliance_snapshot(workstreams: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    items = [workstream_governance_compliance(item) for item in workstreams]
    critical = sum(1 for item in items if item["state"] == "critical")
    exception = sum(1 for item in items if item["state"] == "exception")
    state = "compliant"
    if critical:
        state = "critical"
    elif exception:
        state = "exception"
    return {
        "state": state,
        "total": len(items),
        "compliant": sum(1 for item in items if item["state"] == "compliant"),
        "exception": exception,
        "critical": critical,
        "issue_count": sum(int(item["issue_count"]) for item in items),
        "workstreams": items,
    }
