"""Pure deterministic workflow graph projection."""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Dict, List, Tuple

from .model import Model, Record


_TERMINAL = {"COMPLETE", "FAILED", "CANCELLED"}
_ACTIVE = {"DISPATCHED", "ACKNOWLEDGED", "TASK_MATERIALIZED", "PREFLIGHT_RUNNING", "EXECUTING", "VERIFYING", "BLOCKED"}


def _parse_utc(value: str) -> datetime:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z", value):
        raise ValueError("expected UTC RFC 3339 timestamp")
    stamp = datetime.fromisoformat(value[:-1] + "+00:00")
    if stamp.tzinfo is None or stamp.microsecond % 1000:
        raise ValueError("expected UTC RFC 3339 timestamp with millisecond precision")
    return stamp.astimezone(timezone.utc)


def _task_ref(state: Record) -> Record:
    context = state["context"]
    return {"kind": "task", "taskId": context["taskId"], "attemptId": context["attemptId"]}


def _scope(state: Record, project_id: str, goal_id: str) -> bool:
    context = state.get("context", {})
    return context.get("projectId") == project_id and context.get("goalId") == goal_id


def _runtime(state: Record, as_of: datetime) -> Tuple[str, str]:
    runtime = state.get("runtime", {})
    status = runtime.get("reportedStatus", "UNKNOWN")
    observed_at = runtime.get("lastObservedAt")
    lease_ms = runtime.get("leaseMs")
    if status in ("UNKNOWN", "STOPPED") or observed_at is None or lease_ms is None:
        return status if status in ("UNKNOWN", "STOPPED") else "UNKNOWN", ""
    if status == "STALE":
        return "STALE", ""
    try:
        observed = _parse_utc(observed_at)
    except (TypeError, ValueError):
        return "UNKNOWN", "INVALID_RUNTIME_TIMESTAMP"
    elapsed = (as_of - observed).total_seconds() * 1000
    if elapsed < 0:
        return "UNKNOWN", "CLOCK_REGRESSION"
    if elapsed >= lease_ms:
        return "STALE", ""
    return status, ""


def _next_actions(model: Model, states: List[Record], graph_complete: bool, source_status: str) -> List[Record]:
    by_key = {f"{state['context']['taskId']}:{state['context']['attemptId']}": state for state in states}
    action_by_key: Dict[str, Tuple[str, str]] = {}
    blocked_edges = [edge for edge in model.relations.values() if edge.get("kind") == "blocked_by"]
    resume_edges = [edge for edge in model.relations.values() if edge.get("kind") == "resumes_to"]

    for key, state in by_key.items():
        context = state["context"]
        if state.get("decision", "NONE") in ("REQUIRED", "EXPIRED", "REJECTED"):
            action_by_key[key] = ("REQUEST_DECISION", "DECISION_REQUIRED")
        if state.get("lifecycle") != "BLOCKED":
            continue
        deps = [edge for edge in blocked_edges if edge.get("from", {}).get("kind") == "task" and f"{edge['from']['taskId']}:{edge['from']['attemptId']}" == key]
        if deps and action_by_key.get(key, ("", ""))[0] != "REQUEST_DECISION":
            action_by_key[key] = ("WAIT_DEPENDENCY", "BLOCKED_PREREQUISITE")

    for edge in resume_edges:
        source = edge.get("from", {})
        target = edge.get("to", {})
        source_key = f"{source.get('taskId', '')}:{source.get('attemptId', '')}"
        target_key = f"{target.get('taskId', '')}:{target.get('attemptId', '')}"
        blocked = by_key.get(target_key)
        repair = by_key.get(source_key)
        if blocked is None or repair is None or blocked.get("lifecycle") != "BLOCKED":
            continue
        if source_status != "LIVE" or not graph_complete or blocked.get("authorityStatus") != "VERIFIED" or repair.get("authorityStatus") != "VERIFIED":
            continue
        if blocked.get("gate", "NOT_RUN") == "FAIL" or blocked.get("review") in ("REVISION_REQUIRED", "REJECTED"):
            continue
        if blocked.get("decision", "NONE") in ("REQUIRED", "EXPIRED", "REJECTED"):
            action_by_key[target_key] = ("REQUEST_DECISION", "DECISION_REQUIRED")
            continue
        inverse = any(
            edge.get("from", {}).get("kind") == "task"
            and edge.get("to", {}).get("kind") == "task"
            and f"{edge['from']['taskId']}:{edge['from']['attemptId']}" == target_key
            and f"{edge['to']['taskId']}:{edge['to']['attemptId']}" == source_key
            for edge in blocked_edges
        )
        if not inverse:
            continue
        prerequisites = [
            item for item in model.relations.values()
            if item.get("kind") in ("blocked_by", "depends_on")
            and item.get("from", {}).get("kind") == "task"
            and f"{item['from']['taskId']}:{item['from']['attemptId']}" == target_key
        ]
        if not prerequisites:
            continue
        if any(
            f"{item['to'].get('taskId', '')}:{item['to'].get('attemptId', '')}" not in by_key
            or by_key[f"{item['to']['taskId']}:{item['to']['attemptId']}"].get("lifecycle") != "COMPLETE"
            or not any(ref.get("kind") == "acceptance" for ref in by_key[f"{item['to']['taskId']}:{item['to']['attemptId']}"].get("evidenceRefs", []))
            for item in prerequisites
        ):
            action_by_key[target_key] = ("WAIT_DEPENDENCY", "PREREQUISITE_INCOMPLETE")
            continue
        if repair.get("lifecycle") == "COMPLETE" and any(ref.get("kind") == "acceptance" for ref in repair.get("evidenceRefs", [])):
            current = action_by_key.get(target_key, ("", ""))[0]
            if current != "REQUEST_DECISION":
                action_by_key[target_key] = ("ELIGIBLE_FOR_RESUME", "RESUME_PREREQUISITES_COMPLETE")

    for key, state in by_key.items():
        if state.get("lifecycle") == "COMPLETE" and not any(ref.get("kind") == "acceptance" for ref in state.get("evidenceRefs", [])):
            action_by_key[key] = ("VERIFY_COMPLETION", "ACCEPTANCE_UNAVAILABLE")

    actions = []
    for key, (kind, reason) in action_by_key.items():
        if key not in by_key:
            continue
        actions.append({"taskRef": _task_ref(by_key[key]), "kind": kind, "reasonCode": reason, "executable": False})
    return sorted(actions, key=lambda row: (row["taskRef"]["taskId"], row["taskRef"]["attemptId"], row["kind"]))[:128]


def project_goal(model: Model, project_id: str, goal_id: str, as_of: str, source_status: str, config: Record) -> Record:
    """Return the schema-shaped projection without mutating the model."""
    moment = _parse_utc(as_of)
    states = [state for state in model.states.values() if _scope(state, project_id, goal_id)]
    states.sort(key=lambda state: (state["context"]["taskId"], state["context"]["attemptId"]))
    visible_keys = {f"{state['context']['taskId']}:{state['context']['attemptId']}" for state in states}
    edges = [
        edge for edge in model.relations.values()
        if edge.get("projectId") == project_id and edge.get("goalId") == goal_id
        and all(key is None or key in visible_keys for key in (
            f"{edge['from']['taskId']}:{edge['from']['attemptId']}" if edge["from"].get("kind") == "task" else None,
            f"{edge['to']['taskId']}:{edge['to']['attemptId']}" if edge["to"].get("kind") == "task" else None,
        ))
    ]
    edges.sort(key=lambda edge: edge["relationId"])
    unresolved = sorted(
        relation_id for relation_id, edge in model.pending.items()
        if edge.get("projectId") == project_id and edge.get("goalId") == goal_id
    )
    graph_error_codes = {
        "DEPENDENCY_CYCLE", "HIERARCHY_CYCLE", "MULTIPLE_PARENTS", "SELF_DEPENDENCY",
        "CROSS_SCOPE_RELATION", "STALE_RELATION_REVISION", "RELATION_REVISION_CONFLICT",
    }
    graph_complete = (
        not unresolved
        and all(state.get("authorityStatus") == "VERIFIED" for state in states)
        and not any(state.get("dataQuality") in ("INCOMPLETE", "CONFLICT", "UNAVAILABLE") for state in states)
        and not any(row.get("code") in graph_error_codes for row in model.diagnostics)
    )

    nodes = []
    attention: Dict[Tuple[str, str, str], Record] = {}
    all_evidence: Dict[str, Record] = {}
    active = []
    lifecycle_counts: Dict[str, int] = {}
    for state in states:
        context = state["context"]
        key = f"{context['taskId']}:{context['attemptId']}"
        lifecycle = state.get("lifecycle", "UNKNOWN")
        lifecycle_counts[lifecycle] = lifecycle_counts.get(lifecycle, 0) + 1
        owner = state.get("ownerAgentId")
        runtime_badge, runtime_error = _runtime(state, moment)
        quality = state.get("dataQuality", "UNAVAILABLE")
        nodes.append({
            "ref": _task_ref(state),
            "lifecycle": lifecycle,
            "ownerAgentId": owner,
            "runtimeBadge": runtime_badge,
            "dataQuality": quality,
        })
        if lifecycle in _ACTIVE:
            active.append((context["taskId"], context["attemptId"], owner))
        if runtime_error:
            attention[(context["taskId"], context["attemptId"], runtime_error)] = {"taskRef": _task_ref(state), "code": runtime_error, "severity": "WARNING"}
        if quality in ("INCOMPLETE", "CONFLICT", "UNAVAILABLE"):
            code = "DATA_" + quality
            attention[(context["taskId"], context["attemptId"], code)] = {"taskRef": _task_ref(state), "code": code, "severity": "ACTION_REQUIRED" if quality == "CONFLICT" else "WARNING"}
        for ref in state.get("evidenceRefs", []):
            evidence_id = ref.get("evidenceId")
            if evidence_id:
                all_evidence[evidence_id] = ref

    for diagnostic in model.diagnostics:
        task_ref = diagnostic.get("taskRef")
        code = diagnostic.get("code", "")
        if isinstance(task_ref, dict) and code and task_ref.get("kind") == "task":
            task_id, attempt_id = task_ref.get("taskId", ""), task_ref.get("attemptId", "")
            if task_id and attempt_id:
                attention[(task_id, attempt_id, code)] = {
                    "taskRef": {"kind": "task", "taskId": task_id, "attemptId": attempt_id},
                    "code": code,
                    "severity": "ACTION_REQUIRED" if code.endswith("CONFLICT") or code.endswith("CYCLE") else "WARNING",
                }
    attention_rows = sorted(attention.values(), key=lambda row: (row["taskRef"]["taskId"], row["taskRef"]["attemptId"], row["code"]))[:128]

    observed_complete = bool(states) and all(state.get("lifecycle") == "COMPLETE" and state.get("authorityStatus") == "VERIFIED" and any(ref.get("kind") == "acceptance" for ref in state.get("evidenceRefs", [])) for state in states)
    if not states:
        status = "UNKNOWN"
    elif observed_complete:
        status = "OBSERVED_TASKS_COMPLETE"
    elif lifecycle_counts.get("BLOCKED", 0) == len(states):
        status = "BLOCKED"
    elif len(lifecycle_counts) > 1 and any(lifecycle in _ACTIVE or lifecycle in _TERMINAL for lifecycle in lifecycle_counts):
        status = "MIXED"
    elif lifecycle_counts.get("BLOCKED", 0):
        status = "BLOCKED"
    elif lifecycle_counts.get("FAILED", 0) == len(states):
        status = "FAILED"
    elif lifecycle_counts.get("CANCELLED", 0) == len(states):
        status = "CANCELLED"
    elif lifecycle_counts.get("VERIFYING", 0):
        status = "VERIFYING"
    elif any(lifecycle in _ACTIVE for lifecycle in lifecycle_counts):
        status = "RUNNING"
    elif lifecycle_counts.get("COMPLETE", 0):
        status = "UNKNOWN"
    else:
        status = "WAITING"

    owners = sorted({owner for _, _, owner in active if owner})
    bounded = (len(active) > 128 or len(owners) > 128 or len(nodes) > 512
               or len(edges) > 2048 or len(unresolved) > 2048
               or len(all_evidence) > 256 or len(attention) > 128
               or any(row.get("code") in {"CAPACITY_EXCEEDED", "GAP_WINDOW_EXCEEDED"} for row in model.diagnostics))
    if bounded:
        source_status, status, graph_complete = "PARTIAL", "UNKNOWN", False
        nodes = [dict(node, dataQuality="INCOMPLETE") for node in nodes]
    mainline = {
        "activeTaskIds": sorted({task_id for task_id, _, _ in active})[:128],
        "ownerAgentIds": owners[:128],
        "status": status,
    }
    return {
        "schemaVersion": "0.1.0",
        "projectId": project_id,
        "goalId": goal_id,
        "asOf": as_of,
        "sourceCursor": model.cursor,
        "sourceStatus": source_status,
        "mainline": mainline,
        "attention": attention_rows,
        "workflow": {"nodes": nodes[:512], "edges": edges[:2048], "unresolvedRelationIds": unresolved[:2048]},
        "nextActions": _next_actions(model, states, graph_complete, source_status),
        "details": {"evidenceRefs": [all_evidence[key] for key in sorted(all_evidence)[:256]], "settingsLevel": 3, "rawTerminalIncluded": False},
    }
