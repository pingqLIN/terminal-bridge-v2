"""Workstream metadata and snapshot helpers.

Formalizes the pair-based runtime model as a first-class workstream object
that can be surfaced in status payloads and persisted for service recovery.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


_WORKSTREAM_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def validate_workstream_id(workstream_id: str) -> str:
    value = str(workstream_id).strip()
    if not _WORKSTREAM_ID_RE.fullmatch(value):
        raise ValueError("invalid workstream_id")
    return value


@dataclass(frozen=True)
class BackendSpec:
    kind: str
    backend_id: str = "default"
    shell: str = ""
    distro: str = ""

    @classmethod
    def from_args(cls, args: Dict[str, Any]) -> "BackendSpec":
        kind = str(args.get("backend") or "process")
        backend_id = str(args.get("backend_id", "default"))
        shell = str(args.get("shell", "")) if kind in {"process", "pipe"} else ""
        distro = str(args.get("distro", "")) if kind == "tmux" else ""
        return cls(kind=kind, backend_id=backend_id, shell=shell, distro=distro)

    def to_backend_args(self) -> Dict[str, str]:
        payload = {
            "backend": self.kind,
            "backend_id": self.backend_id,
        }
        if self.shell:
            payload["shell"] = self.shell
        if self.distro:
            payload["distro"] = self.distro
        return payload

    def to_dict(self) -> Dict[str, str]:
        return {
            "kind": self.kind,
            "backend_id": self.backend_id,
            "shell": self.shell,
            "distro": self.distro,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "BackendSpec":
        return cls(
            kind=str(payload.get("kind", "process")),
            backend_id=str(payload.get("backend_id", "default")),
            shell=str(payload.get("shell", "")),
            distro=str(payload.get("distro", "")),
        )


@dataclass
class WorkstreamRecord:
    workstream_id: str
    bridge_id: str
    room_id: str
    pane_a: str
    pane_b: str
    profile: str
    auto_forward: bool
    intervention: bool
    poll_ms: int
    lines: int
    backend: BackendSpec
    state: str = "live"
    pending: List[Dict[str, Any]] = field(default_factory=list)
    auto_forward_guard: Dict[str, Any] = field(default_factory=dict)
    restore_error: Optional[str] = None
    updated_at: float = field(default_factory=time.time)

    @property
    def bridge_active(self) -> bool:
        return self.state in {"live", "restored"}

    def to_status_payload(self) -> Dict[str, Any]:
        return {
            "workstream_id": self.workstream_id,
            "bridge_id": self.bridge_id,
            "room_id": self.room_id,
            "pane_a": self.pane_a,
            "pane_b": self.pane_b,
            "profile": self.profile,
            "auto_forward": self.auto_forward,
            "intervention": self.intervention,
            "pending_count": len(self.pending),
            "pending": list(self.pending),
            "auto_forward_guard": dict(self.auto_forward_guard),
            "backend": self.backend.to_dict(),
            "poll_ms": self.poll_ms,
            "lines": self.lines,
            "state": self.state,
            "bridge_active": self.bridge_active,
            "restore_error": self.restore_error,
            "updated_at": self.updated_at,
        }

    def to_snapshot_payload(self) -> Dict[str, Any]:
        payload = self.to_status_payload()
        payload["captured_at"] = time.time()
        return payload

    @classmethod
    def from_snapshot(cls, payload: Dict[str, Any]) -> "WorkstreamRecord":
        return cls(
            workstream_id=validate_workstream_id(str(payload["workstream_id"])),
            bridge_id=str(payload["bridge_id"]),
            room_id=str(payload["room_id"]),
            pane_a=str(payload["pane_a"]),
            pane_b=str(payload["pane_b"]),
            profile=str(payload.get("profile", "generic")),
            auto_forward=bool(payload.get("auto_forward", False)),
            intervention=bool(payload.get("intervention", False)),
            poll_ms=int(payload.get("poll_ms", 400)),
            lines=int(payload.get("lines", 200)),
            backend=BackendSpec.from_dict(dict(payload.get("backend", {}))),
            state=str(payload.get("state", "live")),
            pending=list(payload.get("pending", [])),
            auto_forward_guard=dict(payload.get("auto_forward_guard", {})),
            restore_error=str(payload.get("restore_error")) if payload.get("restore_error") is not None else None,
            updated_at=float(payload.get("updated_at", time.time())),
        )
