from copy import deepcopy

from tb2.workflow_observation.model import Model, empty_state
from tb2.workflow_observation.projection import project_goal
from tb2.workflow_observation.relations import apply_relation, refresh_relations


def _state(task: str, lifecycle: str = "EXECUTING", **values: object) -> dict:
    state = empty_state({"projectId": "p", "goalId": "g", "taskId": task, "attemptId": "a1"})
    state.update({"lifecycle": lifecycle, "authorityStatus": "VERIFIED"})
    state.update(values)
    return state


def _relation(relation_id: str, kind: str, source: str, target: str, revision: int = 1) -> dict:
    return {
        "schemaVersion": "0.1.0",
        "relationId": relation_id,
        "projectId": "p",
        "goalId": "g",
        "relationRevision": revision,
        "kind": kind,
        "from": {"kind": "task", "taskId": source, "attemptId": "a1"},
        "to": {"kind": "task", "taskId": target, "attemptId": "a1"},
        "evidenceRef": {"evidenceId": f"ev-{relation_id}", "sha256": "a" * 64, "kind": "checkpoint"},
    }


def _event(rel: dict, event_type: str = "relation.upserted") -> dict:
    payload = {"relation": rel} if event_type == "relation.upserted" else {
        "relationId": rel["relationId"],
        "relationRevision": rel["relationRevision"],
        "evidenceRef": rel["evidenceRef"],
    }
    return {
        "type": event_type,
        "context": {"projectId": "p", "goalId": "g", "taskId": rel["from"]["taskId"], "attemptId": rel["from"]["attemptId"]},
        "payload": payload,
    }


def _model(*tasks: str) -> Model:
    model = Model()
    model.states.update({f"{task}:a1": _state(task) for task in tasks})
    return model


def test_unresolved_edge_activates_after_endpoint_arrives() -> None:
    model = _model("a")
    rel = _relation("r1", "depends_on", "a", "b")

    assert apply_relation(model, _event(rel)) == "UNRESOLVED_RELATION"
    assert "r1" in model.pending
    model.states["b:a1"] = _state("b", "COMPLETE")
    refresh_relations(model)

    assert model.pending == {}
    assert model.relations == {"r1": rel}


def test_dependency_cycle_checks_union_of_depends_and_blocked_edges() -> None:
    model = _model("a", "b")
    first = _relation("r1", "depends_on", "a", "b")
    second = _relation("r2", "blocked_by", "b", "a")

    assert apply_relation(model, _event(first)) == "ACCEPTED"
    assert apply_relation(model, _event(second)) == "DEPENDENCY_CYCLE"
    assert "r2" not in model.relations


def test_blocked_by_and_resumes_to_pair_is_not_a_cycle() -> None:
    model = _model("repair", "main")
    blocked = _relation("r-block", "blocked_by", "main", "repair")
    resumes = _relation("r-resume", "resumes_to", "repair", "main")

    assert apply_relation(model, _event(blocked)) == "ACCEPTED"
    assert apply_relation(model, _event(resumes)) == "ACCEPTED"
    assert set(model.relations) == {"r-block", "r-resume"}


def test_removal_tombstone_blocks_old_upsert() -> None:
    model = _model("a", "b")
    rel = _relation("r1", "depends_on", "a", "b")
    removed = _relation("r1", "depends_on", "a", "b", revision=2)

    assert apply_relation(model, _event(rel)) == "ACCEPTED"
    assert apply_relation(model, _event(removed, "relation.removed")) == "ACCEPTED"
    assert apply_relation(model, _event(removed, "relation.removed")) == "ACCEPTED"
    assert apply_relation(model, _event(rel)) == "STALE_RELATION_REVISION"
    assert "r1" not in model.relations


def test_projection_is_sorted_read_only_and_uses_explicit_as_of_for_lease() -> None:
    model = _model("b", "a")
    model.cursor = 4
    for state in model.states.values():
        state["ownerAgentId"] = "agent-1"
        state["runtime"] = {"reportedStatus": "ONLINE", "lastObservedAt": "2026-09-11T00:00:00.000Z", "leaseMs": 1000}
    before = deepcopy(model.__dict__)

    projection = project_goal(model, "p", "g", "2026-09-11T00:00:01.000Z", "LIVE", {})

    assert [node["ref"]["taskId"] for node in projection["workflow"]["nodes"]] == ["a", "b"]
    assert [node["runtimeBadge"] for node in projection["workflow"]["nodes"]] == ["STALE", "STALE"]
    assert projection["mainline"]["ownerAgentIds"] == ["agent-1"]
    assert projection["details"]["rawTerminalIncluded"] is False
    assert model.__dict__ == before


def test_clock_regression_projects_unknown_runtime_with_attention() -> None:
    model = _model("a")
    model.states["a:a1"]["runtime"] = {
        "reportedStatus": "ONLINE", "lastObservedAt": "2026-09-11T00:00:01.000Z", "leaseMs": 1000,
    }

    projection = project_goal(model, "p", "g", "2026-09-11T00:00:00.000Z", "LIVE", {})

    assert projection["workflow"]["nodes"][0]["runtimeBadge"] == "UNKNOWN"
    assert projection["attention"][0]["code"] == "CLOCK_REGRESSION"


def test_resume_candidate_is_never_executable_and_requires_verified_acceptance() -> None:
    model = _model("repair", "main")
    repair = model.states["repair:a1"]
    repair.update({"lifecycle": "COMPLETE", "evidenceRefs": [{"evidenceId": "accept", "sha256": "b" * 64, "kind": "acceptance"}]})
    model.states["main:a1"]["lifecycle"] = "BLOCKED"
    model.states["main:a1"]["dataQuality"] = "CONSISTENT"
    assert apply_relation(model, _event(_relation("r-block", "blocked_by", "main", "repair"))) == "ACCEPTED"
    assert apply_relation(model, _event(_relation("r-resume", "resumes_to", "repair", "main"))) == "ACCEPTED"

    projection = project_goal(model, "p", "g", "2026-09-11T00:00:00.000Z", "LIVE", {})

    candidate = next(item for item in projection["nextActions"] if item["taskRef"]["taskId"] == "main")
    assert candidate["kind"] == "ELIGIBLE_FOR_RESUME"
    assert candidate["executable"] is False


def test_resume_candidate_requires_live_source_and_inverse_blocked_edge() -> None:
    model = _model("repair", "main")
    model.states["repair:a1"].update({
        "lifecycle": "COMPLETE",
        "evidenceRefs": [{"evidenceId": "accept", "sha256": "b" * 64, "kind": "acceptance"}],
    })
    model.states["main:a1"]["lifecycle"] = "BLOCKED"
    assert apply_relation(model, _event(_relation("r-resume", "resumes_to", "repair", "main"))) == "ACCEPTED"

    stale = project_goal(model, "p", "g", "2026-09-11T00:00:00.000Z", "STALE", {})
    assert not any(item["kind"] == "ELIGIBLE_FOR_RESUME" for item in stale["nextActions"])

    live = project_goal(model, "p", "g", "2026-09-11T00:00:00.000Z", "LIVE", {})
    assert not any(item["kind"] == "ELIGIBLE_FOR_RESUME" for item in live["nextActions"])


def test_pending_dependency_suppresses_resume_candidate() -> None:
    model = _model("repair", "main")
    model.states["repair:a1"].update({
        "lifecycle": "COMPLETE",
        "evidenceRefs": [{"evidenceId": "accept", "sha256": "b" * 64, "kind": "acceptance"}],
    })
    model.states["main:a1"]["lifecycle"] = "BLOCKED"
    for rel in (
        _relation("r-block", "blocked_by", "main", "repair"),
        _relation("r-resume", "resumes_to", "repair", "main"),
    ):
        assert apply_relation(model, _event(rel)) == "ACCEPTED"
    assert apply_relation(model, _event(_relation("r-dep", "depends_on", "main", "missing"))) == "UNRESOLVED_RELATION"

    projection = project_goal(model, "p", "g", "2026-09-11T00:00:00.000Z", "LIVE", {})

    candidate = next(item for item in projection["nextActions"] if item["taskRef"]["taskId"] == "main")
    assert candidate["kind"] == "WAIT_DEPENDENCY"


def test_relation_diagnostic_is_projected_only_with_attributed_task_ref() -> None:
    model = _model("main")
    event = _event(_relation("r-cycle", "depends_on", "main", "main"))
    assert apply_relation(model, event) == "SELF_DEPENDENCY"

    projection = project_goal(model, "p", "g", "2026-09-11T00:00:00.000Z", "LIVE", {})

    assert projection["attention"][0]["taskRef"]["taskId"] == "main"
    assert projection["attention"][0]["code"] == "SELF_DEPENDENCY"


def test_relation_writer_context_must_match_endpoint_and_existing_relation_scope() -> None:
    model = _model("a", "b")
    rel = _relation("r1", "depends_on", "a", "b")
    event = _event(rel)
    event["context"]["taskId"] = "unrelated"
    assert apply_relation(model, event) == "CROSS_SCOPE_RELATION"
    assert "r1" not in model.relations

    assert apply_relation(model, _event(rel)) == "ACCEPTED"
    removed = _event(_relation("r1", "depends_on", "a", "b", revision=2), "relation.removed")
    removed["context"]["projectId"] = "other-project"
    assert apply_relation(model, removed) == "CROSS_SCOPE_RELATION"
    assert "r1" in model.relations


def test_diagnostic_without_task_binding_is_not_fabricated_into_attention() -> None:
    model = _model("a")
    model.diagnostics.append({"code": "DEPENDENCY_CYCLE", "relationId": "r-unbound"})

    projection = project_goal(model, "p", "g", "2026-09-11T00:00:00.000Z", "LIVE", {})

    assert projection["attention"] == []
