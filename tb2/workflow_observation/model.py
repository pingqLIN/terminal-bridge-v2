"""Pure in-memory records. Canonical task authority remains outside TB2."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Union

JSON = Union[None, bool, int, str, List["JSON"], Dict[str, "JSON"]]
Record = Dict[str, JSON]


@dataclass(frozen=True)
class VerifiedObservation:
    """Receiver-owned, immutable encoded event. Never deserialize from live input."""

    encoded: str
    semantic_error: str | None = None


@dataclass(frozen=True)
class Rejection:
    code: str


@dataclass
class Model:
    config: Record = field(default_factory=dict)
    states: Dict[str, Record] = field(default_factory=dict)
    relations: Dict[str, Record] = field(default_factory=dict)
    pending: Dict[str, Record] = field(default_factory=dict)
    tombstones: Dict[str, Record] = field(default_factory=dict)
    cursor: int = 0
    diagnostics: List[Record] = field(default_factory=list)
    fingerprints: Dict[str, str] = field(default_factory=dict)
    slots: Dict[str, Dict[int, str]] = field(default_factory=dict)
    highwater: Dict[str, int] = field(default_factory=dict)
    buffered: Dict[str, Dict[int, VerifiedObservation]] = field(default_factory=dict)
    snapshots: Dict[str, str] = field(default_factory=dict)


def key(context: Record) -> str:
    return str(context["taskId"]) + ":" + str(context["attemptId"])


def empty_state(context: Record) -> Record:
    return {
        "schemaVersion": "0.1.0", "context": dict(context), "lifecycle": "UNKNOWN",
        "authorityStatus": "UNVERIFIED", "authorityRevision": None, "contractRef": None,
        "ownerAgentId": None, "gate": "NOT_RUN", "decision": "NONE", "review": "NOT_REQUESTED",
        "reportedTags": [], "evidenceRefs": [],
        "runtime": {"reportedStatus": "UNKNOWN", "lastObservedAt": None, "leaseMs": None},
        "lastAcceptedEventId": None, "lastObservedAt": None, "dataQuality": "CONSISTENT",
    }
