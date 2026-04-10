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
_WORKSTREAM_TIER_VALUES = {"main", "sub"}
_SEVERITY_ORDER = {"ok": 0, "warn": 1, "critical": 2}
_ESCALATION_ORDER = {"observe": 0, "review": 1, "intervene": 2}
_DEFAULT_RATE_LIMIT = 6
_DEFAULT_WINDOW_SECONDS = 3.0
_DEFAULT_STREAK_LIMIT = 20
_DEFAULT_PENDING_WARN_THRESHOLD = 3
_DEFAULT_PENDING_CRITICAL_THRESHOLD = 8
_DEFAULT_PENDING_LIMIT = 12


def validate_workstream_id(workstream_id: str) -> str:
    value = str(workstream_id).strip()
    if not _WORKSTREAM_ID_RE.fullmatch(value):
        raise ValueError("invalid workstream_id")
    return value


def validate_workstream_tier(tier: str) -> str:
    value = str(tier).strip().lower() or "main"
    if value not in _WORKSTREAM_TIER_VALUES:
        raise ValueError("invalid workstream tier")
    return value


def _health_alert(
    code: str,
    *,
    severity: str,
    summary: str,
    escalation: str,
    detail: Optional[str] = None,
) -> Dict[str, Any]:
    payload = {
        "code": code,
        "severity": severity,
        "summary": summary,
        "escalation": escalation,
    }
    if detail:
        payload["detail"] = detail
    return payload


def default_workstream_policy(*, poll_ms: int) -> Dict[str, Any]:
    base_silent = max(30.0, (float(poll_ms) / 1000.0) * 25.0)
    return {
        "rate_limit": _DEFAULT_RATE_LIMIT,
        "window_seconds": _DEFAULT_WINDOW_SECONDS,
        "streak_limit": _DEFAULT_STREAK_LIMIT,
        "pending_warn": _DEFAULT_PENDING_WARN_THRESHOLD,
        "pending_critical": _DEFAULT_PENDING_CRITICAL_THRESHOLD,
        "pending_limit": _DEFAULT_PENDING_LIMIT,
        "silent_seconds": min(300.0, base_silent),
    }


def normalize_workstream_policy(
    payload: Optional[Dict[str, Any]],
    *,
    poll_ms: int,
    base: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    merged = default_workstream_policy(poll_ms=poll_ms)
    if base:
        merged.update(base)
    raw = payload or {}
    if "rate_limit" in raw and raw["rate_limit"] is not None:
        merged["rate_limit"] = int(raw["rate_limit"])
    if "window_seconds" in raw and raw["window_seconds"] is not None:
        merged["window_seconds"] = float(raw["window_seconds"])
    if "streak_limit" in raw and raw["streak_limit"] is not None:
        merged["streak_limit"] = int(raw["streak_limit"])
    if "pending_warn" in raw and raw["pending_warn"] is not None:
        merged["pending_warn"] = int(raw["pending_warn"])
    if "pending_critical" in raw and raw["pending_critical"] is not None:
        merged["pending_critical"] = int(raw["pending_critical"])
    if "pending_limit" in raw and raw["pending_limit"] is not None:
        merged["pending_limit"] = int(raw["pending_limit"])
    if "silent_seconds" in raw and raw["silent_seconds"] is not None:
        merged["silent_seconds"] = float(raw["silent_seconds"])

    if int(merged["rate_limit"]) < 1:
        raise ValueError("rate_limit must be >= 1")
    if float(merged["window_seconds"]) < 0.5:
        raise ValueError("window_seconds must be >= 0.5")
    if int(merged["streak_limit"]) < 1:
        raise ValueError("streak_limit must be >= 1")
    if int(merged["pending_warn"]) < 0:
        raise ValueError("pending_warn must be >= 0")
    if int(merged["pending_critical"]) < int(merged["pending_warn"]):
        raise ValueError("pending_critical must be >= pending_warn")
    if int(merged["pending_limit"]) < int(merged["pending_critical"]):
        raise ValueError("pending_limit must be >= pending_critical")
    if float(merged["silent_seconds"]) < 5.0:
        raise ValueError("silent_seconds must be >= 5")

    return {
        "rate_limit": int(merged["rate_limit"]),
        "window_seconds": float(merged["window_seconds"]),
        "streak_limit": int(merged["streak_limit"]),
        "pending_warn": int(merged["pending_warn"]),
        "pending_critical": int(merged["pending_critical"]),
        "pending_limit": int(merged["pending_limit"]),
        "silent_seconds": float(merged["silent_seconds"]),
    }


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
    policy: Dict[str, Any] = field(default_factory=dict)
    review_mode: str = "auto"
    tier: str = "main"
    parent_workstream_id: Optional[str] = None
    restore_error: Optional[str] = None
    last_activity_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    @property
    def bridge_active(self) -> bool:
        return self.state in {"live", "restored"}

    def silent_threshold_seconds(self) -> float:
        if self.policy.get("silent_seconds") is not None:
            return float(self.policy["silent_seconds"])
        base = max(30.0, (float(self.poll_ms) / 1000.0) * 25.0)
        return min(300.0, base)

    def health_payload(self, *, now: Optional[float] = None) -> Dict[str, Any]:
        current_time = float(now if now is not None else time.time())
        age_seconds = max(0.0, current_time - float(self.last_activity_at))
        silent_threshold = self.silent_threshold_seconds()
        alerts: List[Dict[str, Any]] = []

        if self.state == "degraded":
            alerts.append(
                _health_alert(
                    "restore_failed",
                    severity="critical",
                    summary="restore failed; workstream degraded",
                    escalation="intervene",
                    detail=self.restore_error,
                )
            )

        guard_blocked = bool(self.auto_forward_guard.get("blocked"))
        guard_reason = str(self.auto_forward_guard.get("guard_reason") or "").strip()
        if guard_blocked:
            alerts.append(
                _health_alert(
                    "guard_blocked",
                    severity="warn",
                    summary="auto-forward guard is blocking delivery",
                    escalation="review",
                    detail=guard_reason or None,
                )
            )

        pending_count = len(self.pending)
        quota_reason = str(self.auto_forward_guard.get("quota_reason") or "").strip()
        pending_limit = int(self.policy.get("pending_limit", _DEFAULT_PENDING_LIMIT))
        if quota_reason:
            quota_severity = "critical" if pending_count >= pending_limit else "warn"
            quota_escalation = "intervene" if quota_severity == "critical" else "review"
            alerts.append(
                _health_alert(
                    "quota_blocked",
                    severity=quota_severity,
                    summary=quota_reason,
                    escalation=quota_escalation,
                )
            )

        pending_warn = int(self.policy.get("pending_warn", _DEFAULT_PENDING_WARN_THRESHOLD))
        pending_critical = int(self.policy.get("pending_critical", _DEFAULT_PENDING_CRITICAL_THRESHOLD))
        if pending_count >= pending_critical:
            alerts.append(
                _health_alert(
                    "pending_backlog",
                    severity="critical",
                    summary=f"pending review backlog is high ({pending_count})",
                    escalation="intervene",
                )
            )
        elif pending_count >= pending_warn:
            alerts.append(
                _health_alert(
                    "pending_backlog",
                    severity="warn",
                    summary=f"pending review backlog is building ({pending_count})",
                    escalation="review",
                )
            )

        if self.review_mode == "paused":
            alerts.append(
                _health_alert(
                    "review_paused",
                    severity="warn",
                    summary="review is paused by operator policy",
                    escalation="observe",
                )
            )

        if self.bridge_active and age_seconds >= silent_threshold:
            severity = "critical" if age_seconds >= silent_threshold * 2.0 else "warn"
            escalation = "intervene" if severity == "critical" else "review"
            alerts.append(
                _health_alert(
                    "silent_stream",
                    severity=severity,
                    summary=f"no workstream activity for {int(age_seconds)}s",
                    escalation=escalation,
                    detail=f"threshold {int(silent_threshold)}s",
                )
            )

        severity = "ok"
        escalation = "observe"
        for alert in alerts:
            if _SEVERITY_ORDER[alert["severity"]] > _SEVERITY_ORDER[severity]:
                severity = str(alert["severity"])
            if _ESCALATION_ORDER[alert["escalation"]] > _ESCALATION_ORDER[escalation]:
                escalation = str(alert["escalation"])
        summary = alerts[0]["summary"] if alerts else "healthy"

        return {
            "state": severity,
            "summary": summary,
            "alerts": alerts,
            "alert_count": len(alerts),
            "escalation": escalation,
            "last_activity_at": self.last_activity_at,
            "last_activity_age_seconds": round(age_seconds, 3),
            "silent_threshold_seconds": round(silent_threshold, 3),
        }

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
            "policy": dict(self.policy),
            "review_mode": self.review_mode,
            "tier": self.tier,
            "parent_workstream_id": self.parent_workstream_id,
            "backend": self.backend.to_dict(),
            "poll_ms": self.poll_ms,
            "lines": self.lines,
            "state": self.state,
            "bridge_active": self.bridge_active,
            "restore_error": self.restore_error,
            "last_activity_at": self.last_activity_at,
            "health": self.health_payload(),
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
            policy=normalize_workstream_policy(
                dict(payload.get("policy", {})) if isinstance(payload.get("policy"), dict) else {},
                poll_ms=int(payload.get("poll_ms", 400)),
            ),
            review_mode=str(payload.get("review_mode", "auto")),
            tier=validate_workstream_tier(str(payload.get("tier", "main"))),
            parent_workstream_id=validate_workstream_id(str(payload.get("parent_workstream_id")))
            if payload.get("parent_workstream_id")
            else None,
            restore_error=str(payload.get("restore_error")) if payload.get("restore_error") is not None else None,
            last_activity_at=float(payload.get("last_activity_at", payload.get("updated_at", time.time()))),
            updated_at=float(payload.get("updated_at", time.time())),
        )
