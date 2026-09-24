"""Trusted receiver boundary, not an HTTP/MCP ingestion interface.

Verifier implementations are application-owned capabilities, never JSON options.
Evidence resolution must bind the exact task, attempt, contract, kind and executor.
"""
from __future__ import annotations

import json
from typing import Protocol

from .config import validators
from .model import Record, Rejection, VerifiedObservation


class SourceVerifier(Protocol):
    def source_bound(self, event: Record) -> bool: ...
    def contract_bound(self, event: Record) -> bool: ...
    def evidence_verified(self, event: Record, reference: Record) -> bool: ...
    def writer_bound(self, event: Record) -> bool: ...
    def runtime_bound(self, event: Record) -> bool: ...


def verify_source_observation(event: Record, verifier: SourceVerifier, config: Record,
                              received_at: str | None = None) -> VerifiedObservation | Rejection:
    """Validate/privacy-filter before invoking even a trusted resolver.

    received_at is assigned by the local receiver. Offline replay may retain the
    original trusted receipt time; live integrations must pass their own time.
    """
    try:
        encoded = json.dumps(event, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError, RecursionError):
        return Rejection("INVALID_INPUT")
    if len(encoded.encode("utf-8")) > config["eventMaxBytes"] or not isinstance(event, dict):
        return Rejection("INVALID_INPUT")
    if event.get("schemaVersion") != "0.1.0":
        return Rejection("UNSUPPORTED_SCHEMA_VERSION")
    event = json.loads(encoded)
    if received_at is not None:
        event["receivedAt"] = received_at
    if not validators()["event"].is_valid(event):
        return Rejection("INVALID_INPUT")
    kind = event["type"]
    producer = event["source"]["producerKind"]
    if not verifier.source_bound(event):
        return Rejection("UNVERIFIED_SOURCE")
    if kind == "task.snapshot.observed" and producer != "taskcontracts":
        return Rejection("UNVERIFIED_SOURCE")
    if kind.startswith("relation.") and not verifier.writer_bound(event):
        return Rejection("UNVERIFIED_GRAPH_WRITER")
    if kind == "runtime.observed" and not verifier.runtime_bound(event):
        return Rejection("UNVERIFIED_SOURCE")
    error = None
    if kind != "tag.observed" and not verifier.contract_bound(event):
        error = "CONTRACT_HASH_MISMATCH"
    payload = event["payload"]
    if error is None and kind == "task.snapshot.observed":
        lifecycle = payload["lifecycle"]
        acceptance = payload["acceptanceRef"]
        binding = payload["executionBinding"]
        if lifecycle == "COMPLETE" and (not acceptance or acceptance["kind"] != "acceptance"
                                        or not verifier.evidence_verified(event, acceptance)):
            error = "UNVERIFIED_ACCEPTANCE"
        if error is None and lifecycle in {"EXECUTING", "VERIFYING", "COMPLETE"}:
            if (not binding or binding["handoffAckRef"]["kind"] != "executor_ack"
                    or binding["preflightRef"]["kind"] != "preflight"
                    or not verifier.evidence_verified(event, binding["handoffAckRef"])
                    or not verifier.evidence_verified(event, binding["preflightRef"])):
                error = "EXECUTION_BINDING_REQUIRED"
    if error is None and kind.startswith("relation."):
        reference = payload.get("relation", payload)["evidenceRef"]
        if not verifier.evidence_verified(event, reference):
            error = "UNVERIFIED_GRAPH_WRITER"
    return VerifiedObservation(json.dumps(event, sort_keys=True, separators=(",", ":")), error)
