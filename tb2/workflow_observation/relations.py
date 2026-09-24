"""Deterministic graph operations for trusted workflow relation events."""

from __future__ import annotations

from typing import Dict, Iterable, Optional, Tuple

from .model import Model, Record


def _task_key(ref: Record) -> str:
    return f"{ref['taskId']}:{ref['attemptId']}"


def _endpoints(rel: Record) -> Tuple[Optional[str], Optional[str]]:
    source = rel["from"]
    target = rel["to"]
    return (
        _task_key(source) if source.get("kind") == "task" else None,
        _task_key(target) if target.get("kind") == "task" else None,
    )


def _scope_ok(model: Model, rel: Record) -> bool:
    project_id, goal_id = rel.get("projectId"), rel.get("goalId")
    for ref in (rel.get("from", {}), rel.get("to", {})):
        if ref.get("kind") == "goal" and ref.get("goalId") != goal_id:
            return False
        if ref.get("kind") == "task":
            state = model.states.get(_task_key(ref))
            if state is not None:
                context = state.get("context", {})
                if context.get("projectId") != project_id or context.get("goalId") != goal_id:
                    return False
    return True


def _cycle(edges: Iterable[Record], candidate: Record) -> bool:
    """Check hierarchy or dependency cycles after adding candidate."""
    kind = candidate["kind"]
    if kind == "parent_of":
        graph: Dict[str, list[str]] = {}
        selected = [edge for edge in edges if edge.get("kind") == kind and edge.get("relationId") != candidate.get("relationId")]
        selected.append(candidate)
        for edge in selected:
            source, target = _endpoints(edge)
            if source is not None and target is not None:
                graph.setdefault(source, []).append(target)
    elif kind in ("depends_on", "blocked_by"):
        graph = {}
        selected = [edge for edge in edges if edge.get("kind") in ("depends_on", "blocked_by") and edge.get("relationId") != candidate.get("relationId")]
        selected.append(candidate)
        for edge in selected:
            source, target = _endpoints(edge)
            if source is not None and target is not None:
                graph.setdefault(source, []).append(target)
    else:
        return False

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for child in graph.get(node, []):
            if visit(child):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in sorted(graph))


def _validate(model: Model, rel: Record) -> Tuple[str, bool]:
    kind = rel.get("kind")
    source, target = _endpoints(rel)
    if kind not in {"parent_of", "depends_on", "blocked_by", "resumes_to"}:
        return "INVALID_INPUT", False
    if source is not None and source == target:
        return "SELF_DEPENDENCY", False
    if not _scope_ok(model, rel):
        return "CROSS_SCOPE_RELATION", False
    missing = any(key is not None and key not in model.states for key in (source, target))
    if kind == "parent_of" and source is None and rel.get("from", {}).get("kind") != "goal":
        return "INVALID_INPUT", False
    if missing:
        return "UNRESOLVED_RELATION", True
    if kind == "parent_of":
        incoming = [edge for edge in model.relations.values() if edge.get("kind") == kind and edge.get("to") == rel["to"] and edge.get("relationId") != rel["relationId"]]
        if incoming:
            return "MULTIPLE_PARENTS", False
        if _cycle(model.relations.values(), rel):
            return "HIERARCHY_CYCLE", False
    if kind in ("depends_on", "blocked_by"):
        if _cycle(model.relations.values(), rel):
            return "DEPENDENCY_CYCLE", False
    return "ACCEPTED", False


def _record(model: Model, code: str, relation_id: str, context: Optional[Record] = None) -> None:
    item: Record = {"code": code, "relationId": relation_id}
    if context and context.get("taskId") and context.get("attemptId"):
        item["taskRef"] = {"kind": "task", "taskId": context["taskId"], "attemptId": context["attemptId"]}
    if item not in model.diagnostics:
        model.diagnostics.append(item)
    model.diagnostics.sort(key=lambda row: (row.get("relationId", ""), row["code"]))


def _revision_status(model: Model, rel: Record) -> str:
    relation_id = rel.get("relationId", "")
    current = model.tombstones.get(relation_id) or model.relations.get(relation_id) or model.pending.get(relation_id)
    if current is None:
        return "ACCEPTED"
    old_revision = current.get("relationRevision", 0)
    new_revision = rel.get("relationRevision", 0)
    if new_revision < old_revision:
        return "STALE_RELATION_REVISION"
    if new_revision == old_revision:
        return "ACCEPTED" if current == rel else "RELATION_REVISION_CONFLICT"
    return "ACCEPTED"


def apply_relation(model: Model, event: Record) -> str:
    """Apply a validated, trusted relation event to the in-memory graph."""
    event_type = event.get("type")
    payload = event.get("payload", {})
    relation_id = ""
    context = event.get("context", {})
    if event_type == "relation.upserted":
        rel = payload.get("relation", {})
        relation_id = rel.get("relationId", "")
        if context and (rel.get("projectId") != context.get("projectId") or rel.get("goalId") != context.get("goalId")):
            _record(model, "CROSS_SCOPE_RELATION", relation_id, context)
            return "CROSS_SCOPE_RELATION"
        if context and not any(
            ref.get("kind") == "task"
            and ref.get("taskId") == context.get("taskId")
            and ref.get("attemptId") == context.get("attemptId")
            for ref in (rel.get("from", {}), rel.get("to", {}))
        ):
            _record(model, "CROSS_SCOPE_RELATION", relation_id, context)
            return "CROSS_SCOPE_RELATION"
        prior = model.tombstones.get(relation_id) or model.relations.get(relation_id) or model.pending.get(relation_id)
        if prior and prior.get("projectId") is not None and (prior.get("projectId") != rel.get("projectId") or prior.get("goalId") != rel.get("goalId")):
            _record(model, "CROSS_SCOPE_RELATION", relation_id, context)
            return "CROSS_SCOPE_RELATION"
        revision_status = _revision_status(model, rel)
        if revision_status != "ACCEPTED":
            _record(model, revision_status, relation_id, context)
            return revision_status
        if model.tombstones.get(relation_id) == rel and relation_id not in model.relations and relation_id not in model.pending:
            return "ACCEPTED"
        code, pending = _validate(model, rel)
        if code not in ("ACCEPTED", "UNRESOLVED_RELATION"):
            _record(model, code, relation_id, context)
            return code
        model.relations.pop(relation_id, None)
        model.pending.pop(relation_id, None)
        if pending:
            model.pending[relation_id] = rel
            _record(model, code, relation_id, context)
            return code
        model.relations[relation_id] = rel
        model.tombstones[relation_id] = rel
        return "ACCEPTED"

    if event_type == "relation.removed":
        removal = payload.get("relation", payload)
        relation_id = removal.get("relationId", "")
        if context and (removal.get("projectId", context.get("projectId")) != context.get("projectId") or removal.get("goalId", context.get("goalId")) != context.get("goalId")):
            _record(model, "CROSS_SCOPE_RELATION", relation_id, context)
            return "CROSS_SCOPE_RELATION"
        prior = model.tombstones.get(relation_id) or model.relations.get(relation_id) or model.pending.get(relation_id)
        if prior and (prior.get("projectId") != context.get("projectId") or prior.get("goalId") != context.get("goalId")):
            _record(model, "CROSS_SCOPE_RELATION", relation_id, context)
            return "CROSS_SCOPE_RELATION"
        previous = model.tombstones.get(relation_id)
        if previous and "kind" not in previous and all(previous.get(field) == removal.get(field) for field in ("relationId", "relationRevision", "evidenceRef")):
            return "ACCEPTED"
        revision_status = _revision_status(model, removal)
        if revision_status != "ACCEPTED":
            _record(model, revision_status, relation_id, context)
            return revision_status
        previous = model.tombstones.get(relation_id)
        if previous == removal:
            return "ACCEPTED"
        if previous is not None and removal.get("relationRevision", 0) == previous.get("relationRevision", 0):
            _record(model, "RELATION_REVISION_CONFLICT", relation_id, context)
            return "RELATION_REVISION_CONFLICT"
        model.relations.pop(relation_id, None)
        model.pending.pop(relation_id, None)
        model.tombstones[relation_id] = {
            **removal,
            "projectId": context.get("projectId"),
            "goalId": context.get("goalId"),
        }
        return "ACCEPTED"

    return "INVALID_INPUT"


def refresh_relations(model: Model) -> None:
    """Activate newly resolvable pending edges in deterministic order."""
    for relation_id, rel in sorted(tuple(model.pending.items())):
        code, unresolved = _validate(model, rel)
        if unresolved:
            continue
        model.pending.pop(relation_id, None)
        if code == "ACCEPTED":
            model.relations[relation_id] = rel
            model.tombstones[relation_id] = rel
        else:
            _record(model, code, relation_id)
