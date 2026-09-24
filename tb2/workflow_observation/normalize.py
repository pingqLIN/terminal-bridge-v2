"""Domain-qualified tag mapping. Raw terminal text is never a tag."""
from __future__ import annotations

import re

from .model import Record

DOMAINS = {
    "task": "CREATED DISPATCHED ACKNOWLEDGED TASK_MATERIALIZED PREFLIGHT_RUNNING EXECUTING VERIFYING BLOCKED COMPLETE FAILED CANCELLED".split(),
    "gate": "NOT_RUN RUNNING PASS FAIL".split(),
    "decision": "NONE REQUIRED APPROVED REJECTED EXPIRED".split(),
    "runtime": "UNKNOWN ONLINE DEGRADED STALE STOPPED".split(),
    "review": "NOT_REQUESTED READY IN_REVIEW REVISION_REQUIRED ACCEPTED REJECTED".split(),
    "handoff": "CREATED DISPATCHED ACKNOWLEDGED ACK_TIMEOUT MATERIALIZATION_FAILED".split(),
}


def normalize_tag(code: str, source_vocabulary: str, source_domain: str) -> Record:
    if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", code):
        raise ValueError("INVALID_INPUT")
    if source_vocabulary == "legacy-agent-task" and source_domain == "task":
        code = {"RUNNING": "EXECUTING", "DONE": "COMPLETE"}.get(code, code)
    known = code in DOMAINS.get(source_domain, [])
    return {"schemaVersion": "0.1.0", "vocabularyVersion": "0.1.0", "domain": source_domain if known else "unknown",
            "code": code, "recognized": known}
