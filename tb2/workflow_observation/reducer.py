"""Deterministic event intake; no clock, filesystem, network or execution effects."""
from __future__ import annotations

import hashlib
import json

from .model import Model, Record, VerifiedObservation, empty_state, key
from .normalize import DOMAINS


def diagnostic(model: Model, code: str, event: Record) -> str:
    item = {"code": code, "eventId": event["eventId"]}
    if item not in model.diagnostics:
        model.diagnostics.append(item)
    if code.endswith("CONFLICT"):
        state = model.states.get(key(event["context"]))
        if state:
            state["dataQuality"] = "CONFLICT"
    return code


def _apply(model: Model, observation: VerifiedObservation) -> str:
    from .relations import apply_relation, refresh_relations

    event = json.loads(observation.encoded)
    if observation.semantic_error:
        return diagnostic(model, observation.semantic_error, event)
    if event["type"].startswith("relation."):
        code = apply_relation(model, event)
        if code != "ACCEPTED":
            diagnostic(model, code, event)
        return code
    identity = key(event["context"])
    state = model.states.get(identity)
    if state and state["context"] != event["context"]:
        return diagnostic(model, "CROSS_SCOPE_RELATION", event)
    if state is None and len(model.states) >= model.config.get("maxRetainedTasks", 500):
        return diagnostic(model, "CAPACITY_EXCEEDED", event)
    state = state or empty_state(event["context"])
    payload = event["payload"]
    code = "ACCEPTED"
    if event["type"] == "task.snapshot.observed":
        revision = state["authorityRevision"]
        snapshot = json.dumps({"payload": payload, "contractRef": event["contractRef"]}, sort_keys=True)
        if revision is not None:
            if payload["authorityRevision"] < revision:
                return diagnostic(model, "STALE_AUTHORITY_REVISION", event)
            if payload["authorityRevision"] == revision:
                if model.snapshots[identity] == snapshot:
                    return "DUPLICATE"
                return diagnostic(model, "AUTHORITY_REVISION_CONFLICT", event)
            if state["contractRef"] != event["contractRef"]:
                return diagnostic(model, "CONTRACT_HASH_MISMATCH", event)
            if state["lifecycle"] in {"COMPLETE", "FAILED", "CANCELLED"} and payload["lifecycle"] != state["lifecycle"]:
                return diagnostic(model, "TERMINAL_REOPEN_REQUIRES_NEW_ATTEMPT", event)
        for field in ("lifecycle", "authorityRevision", "ownerAgentId", "gate", "decision", "review", "evidenceRefs"):
            state[field] = payload[field]
        references = ([payload["acceptanceRef"]] if payload["acceptanceRef"] else []) + payload["evidenceRefs"]
        state["evidenceRefs"] = list({json.dumps(ref, sort_keys=True): ref for ref in references}.values())[:32]
        state["authorityStatus"] = "VERIFIED"
        state["contractRef"] = event["contractRef"]
        model.snapshots[identity] = snapshot
    if event["type"] == "tag.observed":
        tag = payload["tag"]
        # Producer's recognized bit cannot change the vocabulary.
        known = tag["code"] in DOMAINS.get(tag["domain"], [])
        tag["recognized"] = known
        if tag not in state["reportedTags"]:
            state["reportedTags"] = (state["reportedTags"] + [tag])[-16:]
        if not known:
            code = diagnostic(model, "UNKNOWN_TAG", event)
    if event["type"] == "runtime.observed":
        state["runtime"] = {"reportedStatus": payload["status"], "lastObservedAt": event["receivedAt"], "leaseMs": payload["leaseMs"]}
    state["lastAcceptedEventId"] = event["eventId"]
    state["lastObservedAt"] = event["receivedAt"]
    model.states[identity] = state
    refresh_relations(model)
    return code


def reduce_observation(model: Model, observation: VerifiedObservation) -> str:
    if not isinstance(observation, VerifiedObservation):
        raise TypeError("VERIFIED_OBSERVATION_REQUIRED")
    event = json.loads(observation.encoded)
    source = event["source"]
    stream = ":".join(source[field] for field in ("producerId", "streamId", "producerBootId"))
    sequence = source["sequence"]
    fingerprint = hashlib.sha256(json.dumps({k: v for k, v in event.items() if k != "receivedAt"}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    known = model.fingerprints.get(event["eventId"])
    if known is not None:
        return "DUPLICATE" if known == fingerprint else diagnostic(model, "EVENT_ID_CONFLICT", event)
    if sequence in model.slots.get(stream, {}):
        return diagnostic(model, "SOURCE_SEQUENCE_CONFLICT", event)
    highwater = model.highwater.get(stream, 0)
    if sequence <= highwater:
        return diagnostic(model, "STALE_SOURCE_SEQUENCE", event)
    pending = model.buffered.setdefault(stream, {})
    if sequence > highwater + 1 and len(pending) >= model.config.get("reorderWindowEvents", 64):
        return diagnostic(model, "GAP_WINDOW_EXCEEDED", event)
    model.fingerprints[event["eventId"]] = fingerprint
    model.slots.setdefault(stream, {})[sequence] = fingerprint
    model.cursor += 1
    pending[sequence] = observation
    code = "BUFFERED_GAP"
    while model.highwater.get(stream, 0) + 1 in pending:
        next_sequence = model.highwater.get(stream, 0) + 1
        outcome = _apply(model, pending.pop(next_sequence))
        model.highwater[stream] = next_sequence
        if next_sequence == sequence:
            code = outcome
    gaps = {key(json.loads(item.encoded)["context"]) for items in model.buffered.values() for item in items.values()}
    for identity, state in model.states.items():
        if state["dataQuality"] != "CONFLICT":
            state["dataQuality"] = "INCOMPLETE" if identity in gaps else "CONSISTENT"
    if code == "BUFFERED_GAP":
        diagnostic(model, code, event)
    return code
