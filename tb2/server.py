"""MCP-compatible HTTP server for TerminalBridge v2.

Provides JSON-RPC endpoints for multi-agent room-based communication
with improved efficiency: per-room locks, bounded storage, session TTL.
"""

from __future__ import annotations

import base64
import ipaddress
import json
import os
import re
import socket
import subprocess
import struct
import threading
import time
from collections import deque
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import shutil
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, unquote, urlparse

from .audit import AuditTrail
from .backend import TerminalBackend, TmuxBackend, TmuxError
from .diff import diff_new_lines, strip_prompt_tail
from .governance import resolve_governance
from .governance import governance_authoritative_keys, governance_exception_keys
from .intervention import Action, InterventionLayer
from .osutils import default_backend_name
from .profile import get_profile, list_profiles, strip_ansi
from .security import build_security_posture, validate_server_binding
from .sidepanel import (
    SidepanelRuntime,
    health_payload as _sidepanel_health_contract,
    message_payload as _sidepanel_message_payload,
    read_tail_if_exists as _read_tail_if_exists,
    read_text_if_exists as _read_text_if_exists,
    render_live_log as _sidepanel_render_live_log,
    render_prompt as _sidepanel_render_prompt,
    run_paths as _sidepanel_run_paths,
    runtime_from_env,
)
from .support import doctor_report
from .gui import build_gui_html
from .room import Room, RoomMessage, RoomSubscription, cleanup_stale, create_room, delete_room, get_room, list_rooms, validate_room_id
from .service import (
    _CONTINUITY_RESTART_LOST,
    _CONTINUITY_RESTORED,
    load_runtime_state,
    persist_runtime_snapshot,
    runtime_contract,
)
from .workstream import (
    BackendSpec,
    WorkstreamRecord,
    default_workstream_policy,
    normalize_workstream_policy,
    validate_workstream_id,
    validate_workstream_tier,
    workstream_recovery_protocol,
    workstream_restore_order,
)


# ---------------------------------------------------------------------------
# Bridge worker
# ---------------------------------------------------------------------------

class Bridge:
    def __init__(self, bridge_id: str, backend: TmuxBackend, room: Room,
                 pane_a: str, pane_b: str, *,
                 workstream_id: Optional[str] = None,
                 backend_spec: Optional[BackendSpec] = None,
                 profile_name: str = "generic",
                 poll_ms: int = 400, lines: int = 200,
                 auto_forward: bool = False, intervention: bool = False,
                 restored: bool = False,
                 last_activity_at: Optional[float] = None,
                 policy: Optional[Dict[str, Any]] = None,
                 governance: Optional[Dict[str, Any]] = None,
                 operator_review_paused: bool = False,
                 tier: str = "main",
                 parent_workstream_id: Optional[str] = None):
        self.workstream_id = workstream_id or bridge_id
        self.bridge_id = bridge_id
        self.backend = backend
        self.backend_spec = backend_spec or BackendSpec(kind=default_backend_name())
        self.room = room
        self.pane_a = pane_a
        self.pane_b = pane_b
        self.profile_name = profile_name
        self.poll_ms = poll_ms
        self.lines = lines
        self.auto_forward = auto_forward
        self._intervention_default = intervention
        self._operator_review_paused = operator_review_paused
        self.policy = normalize_workstream_policy(policy, poll_ms=poll_ms)
        self.governance = dict(governance or {})
        self.tier = validate_workstream_tier(tier)
        self.parent_workstream_id = parent_workstream_id
        self.intervention_layer = InterventionLayer(active=intervention or operator_review_paused)
        self.stop = threading.Event()
        self.prev_a: list = []
        self.prev_b: list = []
        self.forwarded_recent = deque(maxlen=80)
        self._auto_forward_times = deque(maxlen=64)
        self._auto_forward_streak = 0
        self._auto_forward_guard_reason = ""
        self._pending_quota_reason = ""
        # Adaptive polling
        self._current_poll: float = float(poll_ms)
        self._min_poll: float = 100.0
        self._max_poll: float = 3000.0
        self.state = "restored" if restored else "live"
        self.last_activity_at = float(last_activity_at if last_activity_at is not None else time.time())

    def worker(self) -> None:
        profile = get_profile(self.profile_name)
        try:
            self.prev_a, self.prev_b = self.backend.capture_both(
                self.pane_a, self.pane_b, self.lines)
            self.prev_a = strip_prompt_tail(self.prev_a, profile.prompt_patterns)
            self.prev_b = strip_prompt_tail(self.prev_b, profile.prompt_patterns)
        except TmuxError:
            return

        while not self.stop.is_set():
            try:
                curr_a, curr_b = self.backend.capture_both(
                    self.pane_a, self.pane_b, self.lines)
            except TmuxError:
                break

            curr_a = strip_prompt_tail(curr_a, profile.prompt_patterns)
            curr_b = strip_prompt_tail(curr_b, profile.prompt_patterns)

            new_a = diff_new_lines(self.prev_a, curr_a)
            new_b = diff_new_lines(self.prev_b, curr_b)
            self.prev_a = curr_a
            self.prev_b = curr_b

            # Adaptive backoff
            if new_a or new_b:
                self._current_poll = self._min_poll
            else:
                self._current_poll = min(self._current_poll * 1.5, self._max_poll)

            self._process_new_lines("A", self.pane_a, self.pane_b, new_a, profile)
            self._process_new_lines("B", self.pane_b, self.pane_a, new_b, profile)
            if self.stop.wait(timeout=self._current_poll / 1000.0):
                break

    def _process_new_lines(self, tag: str, from_pane: str, to_pane: str,
                           new_lines: list, profile: Any) -> None:
        source_role = "pane_a" if tag == "A" else "pane_b"
        activity_seen = False
        for ln in new_lines:
            if not ln.strip():
                continue
            activity_seen = True
            text = strip_ansi(ln) if profile.strip_ansi else ln
            _post_room_message(
                self.room,
                author=tag,
                text=text,
                kind="terminal",
                meta={"pane": from_pane, "bridge_id": self.bridge_id},
                source_type="terminal",
                source_role=source_role,
                trusted=False,
            )
            if self.auto_forward:
                parsed = profile.parse_message(ln)
                if parsed:
                    fp = (tag, parsed)
                    if fp in self.forwarded_recent:
                        continue
                    self.forwarded_recent.append(fp)
                    self._arm_pending_quota_guard(tag, from_pane, to_pane, parsed)
                    if self._pending_quota_reason:
                        _sync_workstream_from_bridge(self)
                        continue
                    self._arm_auto_forward_guard(tag, from_pane, to_pane, parsed)
                    msg = self.intervention_layer.submit(from_pane, to_pane, parsed)
                    _audit(
                        "intervention.submitted",
                        bridge_id=self.bridge_id,
                        room_id=self.room.room_id,
                        pending_id=msg.id,
                        from_pane=from_pane,
                        to_pane=to_pane,
                        text=parsed,
                        action=msg.action.value,
                    )
                    if msg.action == Action.AUTO:
                        try:
                            self.backend.send(to_pane, parsed, enter=True)
                            self._record_auto_forward()
                            _post_room_message(
                                self.room,
                                author="bridge",
                                text=f"[forwarded {tag}->{to_pane}] {parsed}",
                                kind="system",
                                meta={"bridge_id": self.bridge_id, "to_pane": to_pane},
                                source_type="bridge",
                                source_role="automation",
                                trusted=True,
                            )
                        except TmuxError as exc:
                            self._reset_auto_forward_guard()
                            _post_room_message(
                                self.room,
                                author="bridge",
                                text=f"[forward failed {tag}->{to_pane}] {exc}",
                                kind="system",
                                meta={"bridge_id": self.bridge_id, "to_pane": to_pane},
                                source_type="bridge",
                                source_role="automation",
                                trusted=True,
                            )
                        _sync_workstream_from_bridge(self)
                    else:
                        self._reset_auto_forward_guard()
                        _post_room_message(
                            self.room,
                            author="bridge",
                            text=f"[pending #{msg.id} {tag}->{to_pane}] {parsed}",
                            kind="intervention",
                            meta={
                                "bridge_id": self.bridge_id,
                                "pending_id": msg.id,
                                "from_pane": from_pane,
                                "to_pane": to_pane,
                            },
                            source_type="bridge",
                            source_role="intervention",
                            trusted=True,
                        )
                        _sync_workstream_from_bridge(self)
        if activity_seen:
            self.last_activity_at = time.time()
            _set_workstream(_bridge_workstream_record(self))

    def _arm_auto_forward_guard(self, tag: str, from_pane: str, to_pane: str, text: str) -> None:
        if self.intervention_layer.active:
            return
        reason = self._next_auto_forward_guard_reason()
        if not reason:
            return
        self.intervention_layer.pause()
        self._auto_forward_guard_reason = reason
        self._reset_auto_forward_guard()
        _audit(
            "bridge.guard_blocked",
            bridge_id=self.bridge_id,
            room_id=self.room.room_id,
            from_pane=from_pane,
            to_pane=to_pane,
            reason=reason,
            text=text,
        )
        _post_room_message(
            self.room,
            author="bridge",
            text=f"[auto-forward paused {tag}->{to_pane}] {reason}; intervention enabled",
            kind="intervention",
            meta={
                "bridge_id": self.bridge_id,
                "from_pane": from_pane,
                "to_pane": to_pane,
                "guard_reason": reason,
                "guard_text": text,
            },
            source_type="bridge",
            source_role="safety",
            trusted=True,
        )

    def _next_pending_quota_reason(self) -> str:
        pending_limit = int(self.policy["pending_limit"])
        pending_count = len(self.intervention_layer.list_pending())
        if pending_count >= pending_limit:
            return f"pending quota exceeded: {pending_count}/{pending_limit} queued handoffs"
        return ""

    def _arm_pending_quota_guard(self, tag: str, from_pane: str, to_pane: str, text: str) -> None:
        reason = self._next_pending_quota_reason()
        if not reason:
            return
        if self._pending_quota_reason == reason:
            return
        self.intervention_layer.pause()
        self._pending_quota_reason = reason
        pending_limit = int(self.policy["pending_limit"])
        pending_count = len(self.intervention_layer.list_pending())
        _audit(
            "workstream.quota_blocked",
            workstream_id=self.workstream_id,
            bridge_id=self.bridge_id,
            room_id=self.room.room_id,
            pending_count=pending_count,
            pending_limit=pending_limit,
            from_pane=from_pane,
            to_pane=to_pane,
            text=text,
        )
        _post_room_message(
            self.room,
            author="bridge",
            text=f"[quota paused {tag}->{to_pane}] {reason}; operator intervention required",
            kind="intervention",
            meta={
                "bridge_id": self.bridge_id,
                "from_pane": from_pane,
                "to_pane": to_pane,
                "quota_reason": reason,
                "pending_count": pending_count,
                "pending_limit": pending_limit,
            },
            source_type="bridge",
            source_role="safety",
            trusted=True,
        )

    def _next_auto_forward_guard_reason(self) -> str:
        now = time.time()
        while self._auto_forward_times and now - self._auto_forward_times[0] > float(self.policy["window_seconds"]):
            self._auto_forward_times.popleft()
        if len(self._auto_forward_times) >= int(self.policy["rate_limit"]):
            return (
                f"rate limit exceeded: {len(self._auto_forward_times)} auto-forwards "
                f"in {float(self.policy['window_seconds']):.1f}s"
            )
        if self._auto_forward_streak >= int(self.policy["streak_limit"]):
            return f"circuit breaker tripped after {self._auto_forward_streak} consecutive auto-forwards"
        return ""

    def _record_auto_forward(self) -> None:
        now = time.time()
        while self._auto_forward_times and now - self._auto_forward_times[0] > float(self.policy["window_seconds"]):
            self._auto_forward_times.popleft()
        self._auto_forward_times.append(now)
        self._auto_forward_streak += 1

    def _reset_auto_forward_guard(self) -> None:
        self._auto_forward_times.clear()
        self._auto_forward_streak = 0

    def rearm_auto_forward_guard(self) -> None:
        self._auto_forward_guard_reason = ""
        self._reset_auto_forward_guard()
        self._pending_quota_reason = ""
        if not self._intervention_default and not self._operator_review_paused:
            self.intervention_layer.resume()

    def review_mode(self) -> str:
        if self._intervention_default:
            return "manual"
        if self._operator_review_paused:
            return "paused"
        if self._auto_forward_guard_reason or self._pending_quota_reason:
            return "guarded"
        return "auto"

    def pause_review(self) -> None:
        self._operator_review_paused = True
        self.intervention_layer.pause()

    def resume_review(self) -> None:
        self._operator_review_paused = False
        if self._intervention_default or self._auto_forward_guard_reason or self._pending_quota_reason:
            self.intervention_layer.pause()
            return
        self.intervention_layer.resume()

    def update_policy(self, payload: Dict[str, Any]) -> None:
        self.policy = normalize_workstream_policy(payload, poll_ms=self.poll_ms, base=self.policy)

    def auto_forward_guard(self) -> Dict[str, Any]:
        return {
            "blocked": self.intervention_layer.active and bool(self._auto_forward_guard_reason or self._pending_quota_reason),
            "guard_reason": self._auto_forward_guard_reason or self._pending_quota_reason or None,
            "rate_limit": int(self.policy["rate_limit"]),
            "window_seconds": float(self.policy["window_seconds"]),
            "streak_limit": int(self.policy["streak_limit"]),
            "pending_limit": int(self.policy["pending_limit"]),
            "quota_reason": self._pending_quota_reason or None,
            "review_mode": self.review_mode(),
        }


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_bridges_lock = threading.Lock()
_bridges: Dict[str, Bridge] = {}
_workstreams_lock = threading.Lock()
_workstreams: Dict[str, WorkstreamRecord] = {}

_transport_lock = threading.Lock()
_sse_subscribers: Dict[str, int] = {}
_ws_subscribers: Dict[str, int] = {}
_ws_clients = 0
_server_context: Dict[str, Any] = {
    "host": "127.0.0.1",
    "port": 3189,
    "allow_remote": False,
}

_MAX_BODY_BYTES = 4 * 1024 * 1024
_HTTP_READ_TIMEOUT_SECONDS = 5.0
_MAX_STREAM_LIMIT = 1000
_MAX_CAPTURE_LINES = 5000
_MAX_POLL_MS = 60000
_LOCAL_ORIGIN_HOSTS = {"127.0.0.1", "localhost", "::1"}
_EXTENSION_ORIGIN_SCHEMES = {"chrome-extension", "moz-extension", "edge-extension"}
_BRIDGE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_AUTO_FORWARD_MAX_PER_WINDOW = 6
_AUTO_FORWARD_WINDOW_SECONDS = 3.0
_AUTO_FORWARD_STREAK_LIMIT = 20
_HEALTH_SEVERITY_ORDER = {"ok": 0, "warn": 1, "critical": 2}
_HEALTH_ESCALATION_ORDER = {"observe": 0, "review": 1, "intervene": 2}


# ---------------------------------------------------------------------------
# Cleanup daemon
# ---------------------------------------------------------------------------

def _cleanup_daemon() -> None:
    while True:
        time.sleep(300)  # every 5 min
        cleanup_stale(ttl_seconds=3600)
        # Also stop bridges whose rooms are gone
        with _bridges_lock:
            stale = [bid for bid, b in _bridges.items() if get_room(b.room.room_id) is None]
            for bid in stale:
                _bridges[bid].stop.set()
                bridge = _bridges.pop(bid)
                _drop_workstream(bridge.workstream_id)


_cleanup_thread = threading.Thread(target=_cleanup_daemon, daemon=True)
_cleanup_thread.start()


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

_backend_cache: Dict[Tuple[str, str, str, str], TerminalBackend] = {}
_backend_cache_lock = threading.Lock()
_audit_trail = AuditTrail.from_env()


def _parse_int(
    raw: Any,
    *,
    name: str,
    default: Optional[int] = None,
    minimum: Optional[int] = None,
    maximum: Optional[int] = None,
) -> int:
    if raw in (None, ""):
        if default is not None:
            value = default
        else:
            raise ValueError(f"{name} is required")
    else:
        try:
            value = int(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be an integer") from exc
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} must be <= {maximum}")
    return value


def _validate_bridge_id(raw: Any) -> str:
    bridge_id = str(raw).strip()
    if not _BRIDGE_ID_RE.fullmatch(bridge_id):
        raise ValueError("invalid bridge_id")
    return bridge_id


def _origin_allowed(origin: str) -> bool:
    text = origin.strip()
    if not text:
        return True
    parsed = urlparse(text)
    if parsed.scheme in _EXTENSION_ORIGIN_SCHEMES:
        return str(_server_context.get("host", "127.0.0.1")) in _LOCAL_ORIGIN_HOSTS
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").lower()
    return host in _LOCAL_ORIGIN_HOSTS


def _sidepanel_request_allowed(origin: str, client_host: str) -> bool:
    try:
        client_is_loopback = ipaddress.ip_address(client_host).is_loopback
    except ValueError:
        client_is_loopback = client_host in _LOCAL_ORIGIN_HOSTS
    if not client_is_loopback:
        return False
    return not origin.strip() or _origin_allowed(origin)


def _server_security_payload() -> Dict[str, Any]:
    return build_security_posture(
        str(_server_context.get("host", "127.0.0.1")),
        allow_remote=bool(_server_context.get("allow_remote", False)),
    ).to_dict()


def _make_backend(args: Dict[str, Any]) -> TerminalBackend:
    """Get or create a backend instance. Cached by backend configuration."""
    kind = str(args.get("backend") or default_backend_name())
    backend_id = str(args.get("backend_id", "default"))
    shell = str(args.get("shell", "")) if kind in {"process", "pipe"} else ""
    distro = str(args.get("distro", "")) if kind == "tmux" else ""
    key = (kind, backend_id, shell, distro)

    with _backend_cache_lock:
        if key in _backend_cache:
            return _backend_cache[key]

        if kind == "process":
            from .process_backend import ProcessBackend
            b: TerminalBackend = ProcessBackend(shell=shell)
        elif kind == "pipe":
            from .pipe_backend import PipeBackend
            b = PipeBackend(shell=shell)
        else:
            kwargs = {}
            if distro:
                kwargs["distro"] = distro
            b = TmuxBackend(**kwargs)

        _backend_cache[key] = b
        return b


def _get_bridge(bridge_id: str) -> Optional[Bridge]:
    with _bridges_lock:
        return _bridges.get(bridge_id)


def _set_workstream(record: WorkstreamRecord) -> None:
    record.updated_at = time.time()
    with _workstreams_lock:
        _workstreams[record.workstream_id] = record


def _get_workstream(workstream_id: str) -> Optional[WorkstreamRecord]:
    with _workstreams_lock:
        return _workstreams.get(workstream_id)


def _drop_workstream(workstream_id: str) -> None:
    with _workstreams_lock:
        _workstreams.pop(workstream_id, None)


def _workstream_children(parent_workstream_id: str) -> List[WorkstreamRecord]:
    with _workstreams_lock:
        return sorted(
            [record for record in _workstreams.values() if record.parent_workstream_id == parent_workstream_id],
            key=lambda item: item.workstream_id,
        )


def _workstream_descendants(parent_workstream_id: str) -> List[WorkstreamRecord]:
    descendants: List[WorkstreamRecord] = []
    queue = list(_workstream_children(parent_workstream_id))
    while queue:
        record = queue.pop(0)
        descendants.append(record)
        queue.extend(_workstream_children(record.workstream_id))
    return descendants


def _validate_dependency_update(
    *,
    record: Optional[WorkstreamRecord],
    workstream_id: str,
    tier: str,
    parent_workstream_id: Optional[str],
) -> Tuple[str, Optional[str]]:
    normalized_tier = validate_workstream_tier(tier)
    normalized_parent = validate_workstream_id(parent_workstream_id) if parent_workstream_id else None
    children = _workstream_children(workstream_id)
    if children and normalized_tier != "main":
        raise ValueError("cannot demote main workstream while dependent sub workstreams still exist")
    if normalized_tier == "main" and normalized_parent is not None:
        raise ValueError("main workstream cannot declare parent_workstream_id")
    if normalized_tier == "sub" and normalized_parent is None:
        raise ValueError("sub workstream requires parent_workstream_id")
    if normalized_parent == workstream_id:
        raise ValueError("workstream cannot depend on itself")
    if normalized_parent is None:
        if record is not None and record.tier != "main" and children:
            raise ValueError("cannot clear dependency while sub workstream still has descendants")
        return normalized_tier, None

    parent = _get_workstream(normalized_parent)
    if parent is None:
        raise ValueError(f"parent workstream not found: {normalized_parent}")
    if parent.tier != "main":
        raise ValueError("parent workstream must have tier=main")
    ancestor_id = parent.parent_workstream_id
    while ancestor_id:
        if ancestor_id == workstream_id:
            raise ValueError("dependency cycle detected")
        ancestor = _get_workstream(ancestor_id)
        if ancestor is None:
            break
        ancestor_id = ancestor.parent_workstream_id
    return normalized_tier, normalized_parent


def _runtime_health_alert(
    code: str,
    *,
    severity: str,
    summary: str,
    escalation: str,
    detail: Optional[str] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "code": code,
        "severity": severity,
        "summary": summary,
        "escalation": escalation,
    }
    if detail:
        payload["detail"] = detail
    return payload


def _merge_health_alerts(health: Dict[str, Any], extra_alerts: List[Dict[str, Any]]) -> Dict[str, Any]:
    alerts = list(health.get("alerts", []))
    seen = {str(item.get("code", "")) for item in alerts}
    for item in extra_alerts:
        code = str(item.get("code", ""))
        if code in seen:
            continue
        alerts.append(item)
        seen.add(code)

    severity = "ok"
    escalation = "observe"
    for alert in alerts:
        alert_severity = str(alert.get("severity", "ok"))
        alert_escalation = str(alert.get("escalation", "observe"))
        if _HEALTH_SEVERITY_ORDER.get(alert_severity, 0) > _HEALTH_SEVERITY_ORDER.get(severity, 0):
            severity = alert_severity
        if _HEALTH_ESCALATION_ORDER.get(alert_escalation, 0) > _HEALTH_ESCALATION_ORDER.get(escalation, 0):
            escalation = alert_escalation

    merged = dict(health)
    merged["alerts"] = alerts
    merged["alert_count"] = len(alerts)
    merged["state"] = severity
    merged["escalation"] = escalation
    merged["summary"] = alerts[0]["summary"] if alerts else "healthy"
    return merged


def _room_has_bridge_history(room: Room) -> bool:
    if room.message_count <= 0:
        return False
    for message in room.poll(after_id=0, limit=room.message_count):
        if message.source_type in {"terminal", "bridge"}:
            return True
        if str(message.meta.get("bridge_id", "")).strip():
            return True
    return False


def _room_has_runtime_references(room_id: str) -> bool:
    with _workstreams_lock:
        if any(record.room_id == room_id for record in _workstreams.values()):
            return True
    with _bridges_lock:
        return any(bridge.room.room_id == room_id for bridge in _bridges.values())


def _decorate_workstream_status_payload(
    record: WorkstreamRecord,
    *,
    active_bridge_ids: Optional[set[str]] = None,
) -> Dict[str, Any]:
    payload = record.to_status_payload()
    if active_bridge_ids is None:
        with _bridges_lock:
            bridge_ids = {bridge.bridge_id for bridge in _bridges.values()}
    else:
        bridge_ids = active_bridge_ids
    room_present = get_room(record.room_id) is not None
    bridge_present = record.bridge_id in bridge_ids
    orphaned = (not room_present) or (record.bridge_active and not bridge_present)
    payload["topology"] = {
        "room_present": room_present,
        "bridge_present": bridge_present,
        "orphaned": orphaned,
    }
    child_ids = [item.workstream_id for item in _workstream_children(record.workstream_id)]
    dependency_blockers: List[str] = []
    payload["dependency"] = {
        "tier": record.tier,
        "parent_workstream_id": record.parent_workstream_id,
        "child_workstream_ids": child_ids,
        "child_count": len(child_ids),
        "blocked": False,
        "blocking_reasons": dependency_blockers,
    }
    if orphaned:
        detail = []
        if not room_present:
            detail.append("room missing")
        if record.bridge_active and not bridge_present:
            detail.append("bridge missing")
        payload["health"] = _merge_health_alerts(
            dict(payload["health"]),
            [
                _runtime_health_alert(
                    "orphaned_workstream",
                    severity="critical",
                    summary="workstream topology is orphaned from active runtime",
                    escalation="intervene",
                    detail=", ".join(detail) or None,
                )
            ],
        )
    if record.tier == "sub":
        if not record.parent_workstream_id:
            dependency_blockers.append("sub workstream missing parent")
            payload["health"] = _merge_health_alerts(
                dict(payload["health"]),
                [
                    _runtime_health_alert(
                        "parent_missing",
                        severity="critical",
                        summary="sub workstream parent is missing",
                        escalation="intervene",
                    )
                ],
            )
        else:
            parent = _get_workstream(record.parent_workstream_id)
            if parent is None:
                dependency_blockers.append("parent workstream missing")
                payload["health"] = _merge_health_alerts(
                    dict(payload["health"]),
                    [
                        _runtime_health_alert(
                            "parent_missing",
                            severity="critical",
                            summary=f"parent workstream missing: {record.parent_workstream_id}",
                            escalation="intervene",
                        )
                    ],
                )
            else:
                parent_health = parent.health_payload()
                if parent_health["state"] == "critical":
                    dependency_blockers.append(f"parent unhealthy: {record.parent_workstream_id}")
                    payload["health"] = _merge_health_alerts(
                        dict(payload["health"]),
                        [
                            _runtime_health_alert(
                                "dependency_blocked",
                                severity="critical",
                                summary=f"parent workstream requires intervention: {record.parent_workstream_id}",
                                escalation="intervene",
                            )
                        ],
                    )
                elif parent.review_mode == "paused":
                    dependency_blockers.append(f"parent review paused: {record.parent_workstream_id}")
                    payload["health"] = _merge_health_alerts(
                        dict(payload["health"]),
                        [
                            _runtime_health_alert(
                                "dependency_blocked",
                                severity="warn",
                                summary=f"parent workstream review is paused: {record.parent_workstream_id}",
                                escalation="review",
                            )
                        ],
                    )
    payload["dependency"]["blocked"] = bool(dependency_blockers)
    return payload


def _fleet_reconciliation_snapshot(
    *,
    rooms: Optional[List[Room]] = None,
    workstream_payloads: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    runtime_rooms = rooms if rooms is not None else list_rooms()
    with _bridges_lock:
        active_bridges = list(_bridges.values())
        active_bridge_ids = {bridge.bridge_id for bridge in active_bridges}
    payloads = workstream_payloads if workstream_payloads is not None else _workstream_status_payloads(active_bridge_ids=active_bridge_ids)
    bound_room_ids = {
        str(item["room_id"])
        for item in payloads
        if str(item.get("room_id", "")).strip()
    } | {
        bridge.room.room_id
        for bridge in active_bridges
        if bridge.room.room_id
    }
    orphaned_rooms = [
        {
            "room_id": room.room_id,
            "messages": room.message_count,
            "age_seconds": round(max(0.0, time.time() - room.created_at), 3),
            "last_active_age_seconds": round(max(0.0, time.time() - room.last_active), 3),
        }
        for room in runtime_rooms
        if room.room_id not in bound_room_ids and _room_has_bridge_history(room)
    ]
    orphaned_workstreams = [
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
    stale_workstreams = [
        {
            "workstream_id": str(item["workstream_id"]),
            "state": str(item["health"]["state"]),
            "escalation": str(item["health"]["escalation"]),
            "alerts": [str(alert.get("code", "")) for alert in item["health"].get("alerts", [])],
        }
        for item in payloads
        if any(
            str(alert.get("code", "")) in {
                "silent_stream",
                "pending_backlog",
                "quota_blocked",
                "restore_failed",
                "orphaned_workstream",
                "parent_missing",
                "dependency_blocked",
            }
            for alert in item["health"].get("alerts", [])
        )
    ]
    return {
        "orphaned_rooms": orphaned_rooms,
        "orphaned_workstreams": orphaned_workstreams,
        "stale_workstreams": stale_workstreams,
    }


def _recovery_status_snapshot(
    workstream_payloads: List[Dict[str, Any]],
    *,
    continuity: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    continuity_dict = continuity if isinstance(continuity, dict) else {}
    protocol = str(continuity_dict.get("recovery_protocol") or workstream_recovery_protocol())
    restore_order = continuity_dict.get("restore_order")
    restore_order_items = [str(item) for item in restore_order] if isinstance(restore_order, list) else workstream_restore_order()
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
        "protocol": protocol,
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


def _bridge_workstream_record(bridge: Bridge, *, restore_error: Optional[str] = None) -> WorkstreamRecord:
    snapshot = bridge.intervention_layer.snapshot()
    pending = snapshot.get("pending")
    return WorkstreamRecord(
        workstream_id=bridge.workstream_id,
        bridge_id=bridge.bridge_id,
        room_id=bridge.room.room_id,
        pane_a=bridge.pane_a,
        pane_b=bridge.pane_b,
        profile=bridge.profile_name,
        auto_forward=bridge.auto_forward,
        intervention=bridge.intervention_layer.active,
        poll_ms=bridge.poll_ms,
        lines=bridge.lines,
        backend=bridge.backend_spec,
        state=bridge.state,
        pending=list(pending) if isinstance(pending, list) else [],
        auto_forward_guard=bridge.auto_forward_guard(),
        policy=dict(bridge.policy),
        review_mode=bridge.review_mode(),
        governance=dict(bridge.governance),
        tier=bridge.tier,
        parent_workstream_id=bridge.parent_workstream_id,
        restore_error=restore_error,
        last_activity_at=bridge.last_activity_at,
    )


def _workstream_status_payloads(*, active_bridge_ids: Optional[set[str]] = None) -> List[Dict[str, Any]]:
    with _workstreams_lock:
        records = list(_workstreams.values())
    return [
        _decorate_workstream_status_payload(record, active_bridge_ids=active_bridge_ids)
        for record in sorted(records, key=lambda item: item.workstream_id)
    ]


def _sync_workstream_from_bridge(bridge: Bridge, *, restore_error: Optional[str] = None) -> None:
    _set_workstream(_bridge_workstream_record(bridge, restore_error=restore_error))
    _persist_workstream_snapshot()


def _persist_workstream_snapshot(continuity: Optional[Dict[str, Any]] = None) -> None:
    persist_runtime_snapshot(
        workstreams=[record.to_snapshot_payload() for record in _workstream_records()],
        continuity=continuity,
    )


def _workstream_records() -> List[WorkstreamRecord]:
    with _workstreams_lock:
        return list(_workstreams.values())


def _restore_workstreams_from_service_state() -> None:
    state = load_runtime_state()
    runtime = state.get("runtime")
    if not isinstance(runtime, dict):
        return
    if str(runtime.get("launch_mode", "")) != "service":
        return
    if state.get("pid") != os.getpid():
        return
    snapshots = state.get("workstreams")
    if not isinstance(snapshots, list) or not snapshots:
        return

    restored_any = False
    restored_count = 0
    manual_takeover_count = 0
    for item in snapshots:
        if not isinstance(item, dict):
            continue
        try:
            record = WorkstreamRecord.from_snapshot(item)
        except Exception:
            continue
        room = create_room(record.room_id)
        backend = _make_backend(record.backend.to_backend_args())
        try:
            backend.capture_both(record.pane_a, record.pane_b, record.lines)
        except Exception as exc:
            record.state = "degraded"
            record.restore_error = str(exc)
            _set_workstream(record)
            manual_takeover_count += 1
            continue

        bridge = Bridge(
            record.bridge_id,
            backend,
            room,
            record.pane_a,
            record.pane_b,
            workstream_id=record.workstream_id,
            backend_spec=record.backend,
            profile_name=record.profile,
            poll_ms=record.poll_ms,
            lines=record.lines,
            auto_forward=record.auto_forward,
            intervention=record.intervention,
            restored=True,
            last_activity_at=record.last_activity_at,
            policy=record.policy,
            governance=record.governance,
            operator_review_paused=record.review_mode == "paused",
            tier=record.tier,
            parent_workstream_id=record.parent_workstream_id,
        )
        _refresh_bridge_governance_review_mode_state(bridge)
        _refresh_bridge_governance_policy_state(bridge)
        bridge._auto_forward_guard_reason = str(record.auto_forward_guard.get("guard_reason") or "")
        bridge._pending_quota_reason = str(record.auto_forward_guard.get("quota_reason") or "")
        if bridge._pending_quota_reason and bridge._auto_forward_guard_reason == bridge._pending_quota_reason:
            bridge._auto_forward_guard_reason = ""
        if bridge._auto_forward_guard_reason or bridge._pending_quota_reason:
            bridge.intervention_layer.pause()
        bridge.intervention_layer.restore({
            "active": record.intervention,
            "counter": max([int(msg.get("id", 0)) for msg in record.pending if isinstance(msg, dict)] + [0]),
            "pending": record.pending,
        })
        with _bridges_lock:
            _bridges[bridge.bridge_id] = bridge
        t = threading.Thread(target=bridge.worker, daemon=True, name=f"bridge-{bridge.bridge_id}")
        t.start()
        _set_workstream(_bridge_workstream_record(bridge))
        restored_any = True
        restored_count += 1

    continuity = dict(runtime.get("continuity", {})) if isinstance(runtime.get("continuity"), dict) else {}
    continuity["recovery_protocol"] = workstream_recovery_protocol()
    continuity["restore_order"] = workstream_restore_order()
    continuity["last_recovery_at"] = time.time()
    continuity["restored_workstream_count"] = restored_count
    continuity["manual_takeover_workstream_count"] = manual_takeover_count
    continuity["lost_workstream_count"] = manual_takeover_count
    if restored_any and continuity.get("mode") == _CONTINUITY_RESTART_LOST:
        continuity["mode"] = _CONTINUITY_RESTORED
        continuity["runtime_restored"] = True
    _persist_workstream_snapshot(continuity if continuity else None)


def _bridge_detail(bridge: Bridge) -> Dict[str, Any]:
    return {
        "workstream_id": bridge.workstream_id,
        "bridge_id": bridge.bridge_id,
        "room_id": bridge.room.room_id,
        "pane_a": bridge.pane_a,
        "pane_b": bridge.pane_b,
        "profile": bridge.profile_name,
        "auto_forward": bridge.auto_forward,
        "intervention": bridge.intervention_layer.active,
        "pending_count": len(bridge.intervention_layer.list_pending()),
        "auto_forward_guard": bridge.auto_forward_guard(),
        "policy": dict(bridge.policy),
        "review_mode": bridge.review_mode(),
        "governance": dict(bridge.governance),
        "tier": bridge.tier,
        "parent_workstream_id": bridge.parent_workstream_id,
        "backend": bridge.backend_spec.to_dict(),
        "poll_ms": bridge.poll_ms,
        "lines": bridge.lines,
        "state": bridge.state,
    }


def _resolve_bridge(args: Dict[str, Any]) -> Tuple[Optional[str], Optional[Bridge], Optional[Dict[str, Any]]]:
    requested_workstream_id = str(args.get("workstream_id", "") or "").strip()
    if requested_workstream_id:
        try:
            requested_workstream_id = validate_workstream_id(requested_workstream_id)
        except ValueError as exc:
            return None, None, {"error": str(exc)}
        record = _get_workstream(requested_workstream_id)
        if record is None:
            return None, None, {"error": f"workstream not found: {requested_workstream_id}"}
        bridge = _get_bridge(record.bridge_id)
        if bridge:
            return bridge.bridge_id, bridge, None
        return None, None, {
            "error": f"workstream {requested_workstream_id} has no active bridge",
            "workstream": record.to_status_payload(),
        }

    requested_bridge_id = str(args.get("bridge_id", "") or "").strip()
    if requested_bridge_id:
        try:
            requested_bridge_id = _validate_bridge_id(requested_bridge_id)
        except ValueError as exc:
            return None, None, {"error": str(exc)}
        bridge = _get_bridge(requested_bridge_id)
        if bridge:
            return requested_bridge_id, bridge, None
        return None, None, {"error": "bridge not found"}

    requested_room_id = str(args.get("room_id", "") or "").strip()
    if requested_room_id:
        try:
            requested_room_id = validate_room_id(requested_room_id)
        except ValueError as exc:
            return None, None, {"error": str(exc)}
    with _bridges_lock:
        items = list(_bridges.items())

    if requested_room_id:
        matches = [(bridge_id, bridge) for bridge_id, bridge in items if bridge.room.room_id == requested_room_id]
        if not matches:
            return None, None, {"error": f"no active bridge for room {requested_room_id}"}
        if len(matches) == 1:
            bridge_id, bridge = matches[0]
            return bridge_id, bridge, None
        return None, None, {
            "error": f"multiple active bridges for room {requested_room_id}; provide bridge_id",
            "room_id": requested_room_id,
            "bridge_candidates": [_bridge_detail(bridge) for _, bridge in matches],
        }

    if len(items) == 1:
        bridge_id, bridge = items[0]
        return bridge_id, bridge, None

    if not items:
        return None, None, {"error": "bridge_id required: no active bridges"}

    return None, None, {
        "error": "bridge_id required: multiple active bridges",
        "bridge_candidates": [_bridge_detail(bridge) for _, bridge in items],
    }


def _pending_to_dict(msg: Any) -> Dict[str, Any]:
    return {
        "id": msg.id,
        "from_pane": msg.from_pane,
        "to_pane": msg.to_pane,
        "text": msg.text,
        "action": msg.action.value,
        "edited_text": msg.edited_text,
        "created_at": msg.created_at,
    }


def _room_message_payload(room: Room, msg: RoomMessage) -> Dict[str, Any]:
    meta = dict(msg.meta)
    bridge_id = meta.get("bridge_id")
    return {
        "event_id": f"{room.room_id}:{msg.id}",
        "id": msg.id,
        "room_id": room.room_id,
        "bridge_id": bridge_id,
        "author": msg.author,
        "source": {
            "type": msg.source_type,
            "role": msg.source_role,
            "trusted": msg.trusted,
        },
        "source_type": msg.source_type,
        "source_role": msg.source_role,
        "trusted": msg.trusted,
        "text": msg.text,
        "kind": msg.kind,
        "meta": meta,
        "created_at": msg.ts,
        "ts": msg.ts,
    }


def _audit(event: str, **payload: Any) -> None:
    _audit_trail.write(event, payload)


def _post_room_message(
    room: Room,
    author: str,
    text: str,
    kind: str = "chat",
    meta: Optional[Dict[str, Any]] = None,
    *,
    source_type: str = "client",
    source_role: str = "external",
    trusted: bool = False,
) -> RoomMessage:
    msg = room.post(
        author=author,
        text=text,
        kind=kind,
        meta=meta,
        source_type=source_type,
        source_role=source_role,
        trusted=trusted,
    )
    _audit("room.message", room_id=room.room_id, message=_room_message_payload(room, msg))
    return msg


def _transport_counter(store: Dict[str, int], room_id: str, delta: int) -> None:
    with _transport_lock:
        next_value = store.get(room_id, 0) + delta
        if next_value <= 0:
            store.pop(room_id, None)
        else:
            store[room_id] = next_value


def _ws_client_delta(delta: int) -> None:
    global _ws_clients
    with _transport_lock:
        _ws_clients = max(0, _ws_clients + delta)


def _transport_snapshot() -> Dict[str, Any]:
    with _transport_lock:
        sse = dict(_sse_subscribers)
        ws = dict(_ws_subscribers)
        ws_clients = _ws_clients
    room_ids = sorted(set(sse) | set(ws))
    return {
        "sse_subscribers": sum(sse.values()),
        "websocket_clients": ws_clients,
        "rooms": [
            {
                "room_id": room_id,
                "sse": sse.get(room_id, 0),
                "websocket": ws.get(room_id, 0),
                "total": sse.get(room_id, 0) + ws.get(room_id, 0),
            }
            for room_id in room_ids
        ],
    }


def _deliver_pending(bridge: Bridge, msg: Any) -> None:
    text = msg.edited_text if msg.edited_text else msg.text
    bridge.backend.send(msg.to_pane, text, enter=True)
    bridge.last_activity_at = time.time()
    _post_room_message(
        bridge.room,
        author="bridge",
        text=f"[approved #{msg.id} -> {msg.to_pane}] {text}",
        kind="intervention",
        meta={"bridge_id": bridge.bridge_id, "pending_id": msg.id, "to_pane": msg.to_pane},
        source_type="bridge",
        source_role="intervention",
        trusted=True,
    )


def _maybe_rearm_auto_forward_guard(bridge: Bridge) -> None:
    changed = False
    pending_count = len(bridge.intervention_layer.list_pending())
    guard = bridge.auto_forward_guard()
    quota_reason = str(guard.get("quota_reason") or "").strip()
    if quota_reason and pending_count < int(guard["pending_limit"]):
        bridge._pending_quota_reason = ""
        _audit(
            "workstream.quota_rearmed",
            workstream_id=bridge.workstream_id,
            bridge_id=bridge.bridge_id,
            room_id=bridge.room.room_id,
            pending_count=pending_count,
            pending_limit=int(guard["pending_limit"]),
        )
        changed = True

    guard = bridge.auto_forward_guard()
    if guard["blocked"] and bridge._auto_forward_guard_reason and pending_count == 0:
        bridge.rearm_auto_forward_guard()
        _audit("bridge.guard_rearmed", bridge_id=bridge.bridge_id, room_id=bridge.room.room_id)
        changed = True
    elif changed and not bridge._intervention_default and not bridge._operator_review_paused and not bridge._auto_forward_guard_reason:
        bridge.intervention_layer.resume()

    if changed:
        _sync_workstream_from_bridge(bridge)


def _remove_workstream_runtime(
    record: WorkstreamRecord,
    *,
    cleanup_room: bool,
) -> Dict[str, Any]:
    bridge_removed = False
    with _bridges_lock:
        bridge = _bridges.pop(record.bridge_id, None)
    if bridge is not None:
        bridge.stop.set()
        bridge_removed = True
        _audit("bridge.stopped", bridge_id=bridge.bridge_id, room_id=bridge.room.room_id)
    _drop_workstream(record.workstream_id)

    room_deleted = False
    if cleanup_room and not _room_has_runtime_references(record.room_id):
        room_deleted = delete_room(record.room_id)

    _audit(
        "workstream.stopped",
        workstream_id=record.workstream_id,
        bridge_id=record.bridge_id,
        room_id=record.room_id,
        bridge_stopped=bridge_removed,
        workstream_removed=True,
        room_deleted=room_deleted,
        cleanup_room=cleanup_room,
    )
    _persist_workstream_snapshot()
    return {
        "workstream_id": record.workstream_id,
        "bridge_id": record.bridge_id,
        "room_id": record.room_id,
        "bridge_stopped": bridge_removed,
        "workstream_removed": True,
        "room_deleted": room_deleted,
    }


def handle_terminal_init(args: Dict[str, Any]) -> Dict[str, Any]:
    backend = _make_backend(args)
    session = str(args.get("session", "tb2"))
    a, b = backend.init_session(session)
    _audit("terminal.session_init", session=session, pane_a=a, pane_b=b)
    return {"session": session, "pane_a": a, "pane_b": b}


def handle_terminal_capture(args: Dict[str, Any]) -> Dict[str, Any]:
    backend = _make_backend(args)
    target = str(args["target"])
    try:
        lines = _parse_int(args.get("lines"), name="lines", default=200, minimum=1, maximum=_MAX_CAPTURE_LINES)
    except ValueError as exc:
        return {"error": str(exc)}
    captured = backend.capture(target, lines)
    return {"lines": captured, "count": len(captured)}


def handle_terminal_send(args: Dict[str, Any]) -> Dict[str, Any]:
    backend = _make_backend(args)
    target = str(args["target"])
    text = str(args["text"])
    enter = bool(args.get("enter", False))
    backend.send(target, text, enter=enter)
    _audit("terminal.sent", target=target, text=text, enter=enter)
    return {"ok": True}


def handle_room_create(args: Dict[str, Any]) -> Dict[str, Any]:
    room_id = args.get("room_id")
    try:
        requested_room_id = str(room_id) if room_id is not None else None
        existing = bool(get_room(requested_room_id)) if requested_room_id else False
        room = create_room(requested_room_id)
    except ValueError as exc:
        return {"error": str(exc)}
    _audit("room.created", room_id=room.room_id, existing=existing)
    return {"room_id": room.room_id}


def handle_room_poll(args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        room_id = validate_room_id(str(args["room_id"]))
        after_id = _parse_int(args.get("after_id"), name="after_id", default=0, minimum=0)
        limit = _parse_int(args.get("limit"), name="limit", default=50, minimum=1, maximum=_MAX_STREAM_LIMIT)
    except ValueError as exc:
        return {"error": str(exc)}
    room = get_room(room_id)
    if not room:
        return {"error": "room not found"}
    msgs = room.poll(after_id=after_id, limit=limit)
    return {
        "messages": [_room_message_payload(room, m) for m in msgs],
        "latest_id": room.latest_id,
    }


def handle_room_post(args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        room_id = validate_room_id(str(args["room_id"]))
    except ValueError as exc:
        return {"error": str(exc)}
    room = get_room(room_id)
    if not room:
        return {"error": "room not found"}
    msg = _post_room_message(
        room,
        author=str(args.get("author", "user")),
        text=str(args["text"]),
        kind=str(args.get("kind", "chat")),
        source_type="client",
        source_role="external",
        trusted=False,
    )
    # Optionally deliver to a bridge pane
    deliver = args.get("deliver")
    deliver_error = None
    if deliver:
        bridge_id, bridge, error = _resolve_bridge(args)
        if error:
            deliver_error = str(error["error"])
        elif bridge:
            try:
                if bridge.room.room_id != room.room_id:
                    deliver_error = (
                        f"bridge {bridge_id} belongs to room {bridge.room.room_id}, not {room.room_id}"
                    )
                elif deliver in ("a", "A"):
                    bridge.backend.send(bridge.pane_a, msg.text, enter=True)
                    bridge.last_activity_at = time.time()
                    _sync_workstream_from_bridge(bridge)
                elif deliver in ("b", "B"):
                    bridge.backend.send(bridge.pane_b, msg.text, enter=True)
                    bridge.last_activity_at = time.time()
                    _sync_workstream_from_bridge(bridge)
                elif str(deliver).lower() == "both":
                    bridge.backend.send(bridge.pane_a, msg.text, enter=True)
                    bridge.backend.send(bridge.pane_b, msg.text, enter=True)
                    bridge.last_activity_at = time.time()
                    _sync_workstream_from_bridge(bridge)
                else:
                    deliver_error = "deliver must be one of: a, b, both"
            except Exception as exc:
                deliver_error = str(exc)
    result: Dict[str, Any] = {"id": msg.id}
    _audit(
        "operator.room_post",
        room_id=room.room_id,
        message_id=msg.id,
        author=msg.author,
        kind=msg.kind,
        deliver=str(deliver).lower() if deliver else None,
        deliver_error=deliver_error,
    )
    if deliver_error:
        result["deliver_error"] = deliver_error
    return result


def handle_bridge_start(args: Dict[str, Any]) -> Dict[str, Any]:
    import uuid
    backend_args = dict(args)
    backend_args["backend"] = str(args.get("backend") or default_backend_name())
    backend_spec = BackendSpec.from_args(backend_args)
    backend = _make_backend(backend_args)
    pane_a = str(args["pane_a"])
    pane_b = str(args["pane_b"])
    try:
        requested_room_id = str(args.get("room_id", "")).strip()
        if requested_room_id:
            requested_room_id = validate_room_id(requested_room_id)
        requested_bridge_id = str(args.get("bridge_id", "")).strip()
        if requested_bridge_id:
            requested_bridge_id = _validate_bridge_id(requested_bridge_id)
        requested_workstream_id = str(args.get("workstream_id", "")).strip()
        if requested_workstream_id:
            requested_workstream_id = validate_workstream_id(requested_workstream_id)
        requested_parent_workstream_id = str(args.get("parent_workstream_id", "") or "").strip()
        if requested_parent_workstream_id:
            requested_parent_workstream_id = validate_workstream_id(requested_parent_workstream_id)
        poll_ms = _parse_int(args.get("poll_ms"), name="poll_ms", default=400, minimum=10, maximum=_MAX_POLL_MS)
        lines = _parse_int(args.get("lines"), name="lines", default=200, minimum=1, maximum=_MAX_CAPTURE_LINES)
    except ValueError as exc:
        return {"error": str(exc)}
    reusable_record = _get_workstream(requested_workstream_id) if requested_workstream_id else None
    if reusable_record and reusable_record.bridge_active:
        active_bridge = _get_bridge(reusable_record.bridge_id)
        if active_bridge is not None and active_bridge.backend is backend and active_bridge.pane_a == pane_a and active_bridge.pane_b == pane_b:
            _audit(
                "bridge.start_existing",
                workstream_id=reusable_record.workstream_id,
                bridge_id=active_bridge.bridge_id,
                room_id=active_bridge.room.room_id,
                pane_a=pane_a,
                pane_b=pane_b,
                reason="workstream_reused",
            )
            return {
                "workstream_id": reusable_record.workstream_id,
                "bridge_id": active_bridge.bridge_id,
                "room_id": active_bridge.room.room_id,
                "tier": reusable_record.tier,
                "parent_workstream_id": reusable_record.parent_workstream_id,
                "existing": True,
            }
        return {"error": f"workstream_id already exists: {requested_workstream_id}"}
    if reusable_record and not requested_room_id:
        requested_room_id = reusable_record.room_id
    bridge_id = requested_bridge_id or (reusable_record.bridge_id if reusable_record else uuid.uuid4().hex[:12])
    workstream_id = requested_workstream_id or (reusable_record.workstream_id if reusable_record else bridge_id)
    profile_name = str(args.get("profile", "generic"))
    requested_tier = str(args.get("tier", reusable_record.tier if reusable_record else "main"))
    try:
        tier, parent_workstream_id = _validate_dependency_update(
            record=reusable_record,
            workstream_id=workstream_id,
            tier=requested_tier,
            parent_workstream_id=requested_parent_workstream_id or (reusable_record.parent_workstream_id if reusable_record else None),
        )
    except ValueError as exc:
        return {"error": str(exc)}

    with _bridges_lock:
        if requested_bridge_id and requested_bridge_id in _bridges:
            existing = _bridges[requested_bridge_id]
            if existing.backend is backend and existing.pane_a == pane_a and existing.pane_b == pane_b:
                if requested_room_id and existing.room.room_id != requested_room_id:
                    _audit(
                        "bridge.start_conflict",
                        bridge_id=requested_bridge_id,
                        room_id=existing.room.room_id,
                        pane_a=pane_a,
                        pane_b=pane_b,
                        requested_room_id=requested_room_id,
                        reason="bridge_id_room_mismatch",
                    )
                    return {
                        "error": (
                            f"bridge_id {requested_bridge_id} already maps to room "
                            f"{existing.room.room_id}, not {requested_room_id}"
                        )
                    }
                _audit(
                    "bridge.start_existing",
                    workstream_id=existing.workstream_id,
                    bridge_id=existing.bridge_id,
                    room_id=existing.room.room_id,
                    pane_a=pane_a,
                    pane_b=pane_b,
                    reason="bridge_id_reused",
                )
                return {
                    "workstream_id": existing.workstream_id,
                    "bridge_id": existing.bridge_id,
                    "room_id": existing.room.room_id,
                    "tier": existing.tier,
                    "parent_workstream_id": existing.parent_workstream_id,
                    "existing": True,
                }
            _audit(
                "bridge.start_conflict",
                workstream_id=existing.workstream_id,
                bridge_id=requested_bridge_id,
                room_id=existing.room.room_id,
                pane_a=pane_a,
                pane_b=pane_b,
                reason="bridge_id_exists",
            )
            return {"error": f"bridge_id already exists: {requested_bridge_id}"}

        for existing in _bridges.values():
            if existing.backend is not backend:
                continue
            if existing.pane_a != pane_a or existing.pane_b != pane_b:
                continue
            if requested_room_id and existing.room.room_id != requested_room_id:
                _audit(
                    "bridge.start_conflict",
                    bridge_id=existing.bridge_id,
                    room_id=existing.room.room_id,
                    pane_a=pane_a,
                    pane_b=pane_b,
                    requested_room_id=requested_room_id,
                    reason="pane_pair_room_conflict",
                )
                return {
                    "error": (
                        f"pane pair already bridged by {existing.bridge_id} "
                        f"in room {existing.room.room_id}; stop it first"
                    )
                }
            _audit(
                "bridge.start_existing",
                workstream_id=existing.workstream_id,
                bridge_id=existing.bridge_id,
                room_id=existing.room.room_id,
                pane_a=pane_a,
                pane_b=pane_b,
                reason="pane_pair_existing",
            )
            return {
                "workstream_id": existing.workstream_id,
                "bridge_id": existing.bridge_id,
                "room_id": existing.room.room_id,
                "tier": existing.tier,
                "parent_workstream_id": existing.parent_workstream_id,
                "existing": True,
            }

    try:
        backend.capture_both(pane_a, pane_b, lines)
    except Exception as exc:
        _audit(
            "bridge.start_failed",
            workstream_id=workstream_id,
            bridge_id=bridge_id,
            room_id=requested_room_id or None,
            pane_a=pane_a,
            pane_b=pane_b,
            profile=profile_name,
            reason="preflight_failed",
            error=str(exc),
        )
        return {"error": f"bridge preflight failed: {exc}"}
    room = create_room(requested_room_id) if requested_room_id else create_room()
    if reusable_record:
        _drop_workstream(reusable_record.workstream_id)

    governance = _resolve_workstream_governance(backend_spec=backend_spec, args=args)
    auto_forward_enabled = bool(args.get("auto_forward", False))
    intervention_enabled = bool(args.get("intervention", False))
    operator_review_paused = reusable_record.review_mode == "paused" if reusable_record else False
    auto_forward_enabled, intervention_enabled, operator_review_paused, applied_controls = _apply_governance_start_controls(
        governance=governance,
        auto_forward=auto_forward_enabled,
        intervention=intervention_enabled,
        operator_review_paused=operator_review_paused,
    )
    governance_snapshot = _workstream_governance_snapshot(
        governance=governance,
        poll_ms=poll_ms,
        applied_controls=applied_controls,
    )

    bridge = Bridge(
        bridge_id=bridge_id,
        backend=backend,
        room=room,
        pane_a=pane_a,
        pane_b=pane_b,
        workstream_id=workstream_id,
        backend_spec=backend_spec,
        profile_name=profile_name,
        poll_ms=poll_ms,
        lines=lines,
        auto_forward=auto_forward_enabled,
        intervention=intervention_enabled,
        policy=reusable_record.policy if reusable_record else None,
        governance=governance_snapshot,
        operator_review_paused=operator_review_paused,
        tier=tier,
        parent_workstream_id=parent_workstream_id,
    )
    _refresh_bridge_governance_review_mode_state(bridge)
    _refresh_bridge_governance_policy_state(bridge)
    with _bridges_lock:
        _bridges[bridge_id] = bridge
    _set_workstream(_bridge_workstream_record(bridge))
    t = threading.Thread(target=bridge.worker, daemon=True, name=f"bridge-{bridge_id}")
    t.start()
    _audit(
        "bridge.started",
        workstream_id=workstream_id,
        bridge_id=bridge_id,
        room_id=room.room_id,
        pane_a=pane_a,
        pane_b=pane_b,
        profile=profile_name,
        auto_forward=bridge.auto_forward,
        intervention=bridge.intervention_layer.active,
        governance=bridge.governance,
        tier=bridge.tier,
        parent_workstream_id=bridge.parent_workstream_id,
    )
    _persist_workstream_snapshot()
    return {
        "workstream_id": workstream_id,
        "bridge_id": bridge_id,
        "room_id": room.room_id,
        "tier": bridge.tier,
        "parent_workstream_id": bridge.parent_workstream_id,
    }


def handle_bridge_stop(args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        bridge_id = _validate_bridge_id(args["bridge_id"])
    except ValueError as exc:
        return {"error": str(exc)}
    with _bridges_lock:
        bridge = _bridges.pop(bridge_id, None)
    if bridge:
        bridge.stop.set()
        _drop_workstream(bridge.workstream_id)
        _audit("bridge.stopped", bridge_id=bridge_id, room_id=bridge.room.room_id)
        _persist_workstream_snapshot()
        return {"ok": True}
    return {"error": "bridge not found"}


def handle_intervention_list(args: Dict[str, Any]) -> Dict[str, Any]:
    bridge_id, bridge, error = _resolve_bridge(args)
    if error:
        return error
    if not bridge or not bridge_id:
        return {"error": "bridge not found"}
    pending = bridge.intervention_layer.list_pending()
    return {
        "bridge_id": bridge_id,
        "pending": [_pending_to_dict(msg) for msg in pending],
        "count": len(pending),
    }


def handle_intervention_approve(args: Dict[str, Any]) -> Dict[str, Any]:
    bridge_id, bridge, error = _resolve_bridge(args)
    if error:
        return error
    if not bridge or not bridge_id:
        return {"error": "bridge not found"}

    mid = args.get("id", "all")
    edited_text = args.get("edited_text")
    if edited_text is not None and mid in ("all", None):
        return {"error": "edited_text requires a specific pending message id"}
    if mid == "all" or mid is None:
        approved = bridge.intervention_layer.approve_all()
    else:
        try:
            msg_id = int(mid)
        except (TypeError, ValueError):
            return {"error": "id must be an integer or 'all'"}
        msg = bridge.intervention_layer.approve(msg_id, edited_text=str(edited_text) if edited_text is not None else None)
        if not msg:
            return {"error": f"pending message {msg_id} not found"}
        approved = [msg]

    delivered: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    for msg in approved:
        try:
            _deliver_pending(bridge, msg)
            delivered.append({"id": msg.id, "to_pane": msg.to_pane})
        except Exception as exc:
            errors.append({"id": msg.id, "error": str(exc)})
    _maybe_rearm_auto_forward_guard(bridge)
    _audit(
        "intervention.approved",
        bridge_id=bridge_id,
        room_id=bridge.room.room_id,
        approved=len(approved),
        delivered=delivered,
        errors=errors,
        remaining=len(bridge.intervention_layer.list_pending()),
    )
    _sync_workstream_from_bridge(bridge)

    return {
        "bridge_id": bridge_id,
        "approved": len(approved),
        "delivered": delivered,
        "errors": errors,
        "remaining": len(bridge.intervention_layer.list_pending()),
    }


def handle_intervention_reject(args: Dict[str, Any]) -> Dict[str, Any]:
    bridge_id, bridge, error = _resolve_bridge(args)
    if error:
        return error
    if not bridge or not bridge_id:
        return {"error": "bridge not found"}

    mid = args.get("id", "all")
    if mid == "all" or mid is None:
        rejected = bridge.intervention_layer.reject_all()
    else:
        try:
            msg_id = int(mid)
        except (TypeError, ValueError):
            return {"error": "id must be an integer or 'all'"}
        msg = bridge.intervention_layer.reject(msg_id)
        if not msg:
            return {"error": f"pending message {msg_id} not found"}
        _post_room_message(
            bridge.room,
            author="bridge",
            text=f"[rejected #{msg.id}] {msg.text}",
            kind="intervention",
            meta={"bridge_id": bridge.bridge_id, "pending_id": msg.id, "to_pane": msg.to_pane},
            source_type="bridge",
            source_role="intervention",
            trusted=True,
        )
        rejected = 1
    if rejected and (mid == "all" or mid is None):
        _post_room_message(
            bridge.room,
            author="bridge",
            text=f"[rejected {rejected} pending message(s)]",
            kind="intervention",
            meta={"bridge_id": bridge.bridge_id},
            source_type="bridge",
            source_role="intervention",
            trusted=True,
        )
    if rejected:
        bridge.last_activity_at = time.time()
    _maybe_rearm_auto_forward_guard(bridge)
    _audit(
        "intervention.rejected",
        bridge_id=bridge_id,
        room_id=bridge.room.room_id,
        rejected=rejected,
        remaining=len(bridge.intervention_layer.list_pending()),
    )
    _sync_workstream_from_bridge(bridge)

    return {
        "bridge_id": bridge_id,
        "rejected": rejected,
        "remaining": len(bridge.intervention_layer.list_pending()),
    }


def handle_workstream_list(_args: Dict[str, Any]) -> Dict[str, Any]:
    workstreams = _workstream_status_payloads()
    reconciliation = _fleet_reconciliation_snapshot(workstream_payloads=workstreams)
    return {
        "workstreams": workstreams,
        "count": len(workstreams),
        "reconciliation": reconciliation,
    }


def handle_workstream_get(args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        workstream_id = validate_workstream_id(str(args["workstream_id"]))
    except (KeyError, ValueError) as exc:
        return {"error": str(exc)}
    record = _get_workstream(workstream_id)
    if record is None:
        return {"error": f"workstream not found: {workstream_id}"}
    return {"workstream": _decorate_workstream_status_payload(record)}


def handle_workstream_pause_review(args: Dict[str, Any]) -> Dict[str, Any]:
    bridge_id, bridge, error = _resolve_bridge(args)
    if error:
        return error
    if not bridge or not bridge_id:
        return {"error": "bridge not found"}
    previous_mode = bridge.review_mode()
    bridge.pause_review()
    _set_bridge_governance_review_override(
        bridge,
        active=previous_mode == "auto",
        mode="paused" if previous_mode == "auto" else None,
        reason="operator_pause_review" if previous_mode == "auto" else None,
    )
    bridge.last_activity_at = time.time()
    _audit(
        "workstream.review_paused",
        workstream_id=bridge.workstream_id,
        bridge_id=bridge_id,
        room_id=bridge.room.room_id,
        governance=bridge.governance,
    )
    _sync_workstream_from_bridge(bridge)
    return {"workstream": _decorate_workstream_status_payload(_bridge_workstream_record(bridge))}


def handle_workstream_resume_review(args: Dict[str, Any]) -> Dict[str, Any]:
    bridge_id, bridge, error = _resolve_bridge(args)
    if error:
        return error
    if not bridge or not bridge_id:
        return {"error": "bridge not found"}
    if bridge.parent_workstream_id:
        parent = _get_workstream(bridge.parent_workstream_id)
        if parent is None:
            return {"error": f"parent workstream missing: {bridge.parent_workstream_id}"}
        parent_health = parent.health_payload()
        if parent.review_mode == "paused":
            return {"error": f"cannot resume sub workstream while parent review is paused: {bridge.parent_workstream_id}"}
        if parent_health["state"] == "critical":
            return {"error": f"cannot resume sub workstream while parent requires intervention: {bridge.parent_workstream_id}"}
    pending_count = len(bridge.intervention_layer.list_pending())
    if pending_count:
        return {"error": f"cannot resume review with {pending_count} pending item(s)", "pending_count": pending_count}
    bridge.resume_review()
    _set_bridge_governance_review_override(
        bridge,
        active=False,
        mode=None,
        reason=None,
    )
    bridge.last_activity_at = time.time()
    _audit(
        "workstream.review_resumed",
        workstream_id=bridge.workstream_id,
        bridge_id=bridge_id,
        room_id=bridge.room.room_id,
        governance=bridge.governance,
    )
    _sync_workstream_from_bridge(bridge)
    return {"workstream": _decorate_workstream_status_payload(_bridge_workstream_record(bridge))}


def handle_workstream_update_policy(args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        workstream_id = validate_workstream_id(str(args["workstream_id"]))
    except (KeyError, ValueError) as exc:
        return {"error": str(exc)}
    payload = {
        key: args.get(key)
        for key in ("rate_limit", "window_seconds", "streak_limit", "pending_warn", "pending_critical", "pending_limit", "silent_seconds")
        if key in args
    }
    if not payload:
        return {"error": "policy update requires at least one policy field"}
    record = _get_workstream(workstream_id)
    if record is None:
        return {"error": f"workstream not found: {workstream_id}"}
    bridge = _get_bridge(record.bridge_id)
    try:
        if bridge is not None:
            bridge.update_policy(payload)
            _refresh_bridge_governance_policy_state(bridge, reason="workstream_update_policy")
            bridge.last_activity_at = time.time()
            _audit(
                "workstream.policy_updated",
                workstream_id=bridge.workstream_id,
                bridge_id=bridge.bridge_id,
                room_id=bridge.room.room_id,
                policy=dict(bridge.policy),
                governance=bridge.governance,
            )
            _sync_workstream_from_bridge(bridge)
            return {"workstream": _decorate_workstream_status_payload(_bridge_workstream_record(bridge))}
        record.policy = normalize_workstream_policy(payload, poll_ms=record.poll_ms, base=record.policy)
    except ValueError as exc:
        return {"error": str(exc)}
    state = dict(_governance_policy_state(record.governance))
    baseline = dict(state.get("baseline", {})) if isinstance(state.get("baseline"), dict) else default_workstream_policy(poll_ms=record.poll_ms)
    baseline_source = dict(state.get("baseline_source", {})) if isinstance(state.get("baseline_source"), dict) else {key: "runtime_default" for key in baseline}
    overrides: Dict[str, Dict[str, Any]] = {}
    for key, value in record.policy.items():
        baseline_value = baseline.get(key)
        if baseline_value == value:
            continue
        overrides[key] = {
            "value": value,
            "source": "operator_exception",
            "reason": "workstream_update_policy",
            "baseline_value": baseline_value,
            "baseline_source": baseline_source.get(key, "runtime_default"),
        }
    record.governance["policy_state"] = {
        "baseline": baseline,
        "baseline_source": baseline_source,
        "effective": dict(record.policy),
        "overrides": overrides,
    }
    record.governance["decision_trace"] = _governance_decision_trace(record.governance)
    record.updated_at = time.time()
    _set_workstream(record)
    _persist_workstream_snapshot()
    return {"workstream": _decorate_workstream_status_payload(record)}


def handle_workstream_update_dependency(args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        workstream_id = validate_workstream_id(str(args["workstream_id"]))
    except (KeyError, ValueError) as exc:
        return {"error": str(exc)}
    record = _get_workstream(workstream_id)
    if record is None:
        return {"error": f"workstream not found: {workstream_id}"}

    requested_tier = str(args.get("tier", record.tier))
    requested_parent = args.get("parent_workstream_id", record.parent_workstream_id)
    try:
        tier, parent_workstream_id = _validate_dependency_update(
            record=record,
            workstream_id=workstream_id,
            tier=requested_tier,
            parent_workstream_id=str(requested_parent).strip() if requested_parent not in (None, "") else None,
        )
    except ValueError as exc:
        return {"error": str(exc)}

    record.tier = tier
    record.parent_workstream_id = parent_workstream_id
    bridge = _get_bridge(record.bridge_id)
    if bridge is not None:
        bridge.tier = tier
        bridge.parent_workstream_id = parent_workstream_id
        record = _bridge_workstream_record(bridge)
    _set_workstream(record)
    _persist_workstream_snapshot()
    _audit(
        "workstream.dependency_updated",
        workstream_id=record.workstream_id,
        bridge_id=record.bridge_id,
        room_id=record.room_id,
        tier=record.tier,
        parent_workstream_id=record.parent_workstream_id,
    )
    return {"workstream": _decorate_workstream_status_payload(record)}


def handle_workstream_stop(args: Dict[str, Any]) -> Dict[str, Any]:
    cleanup_room = bool(args.get("cleanup_room", False))
    cascade = bool(args.get("cascade", False))
    requested_workstream_id = str(args.get("workstream_id", "") or "").strip()
    if requested_workstream_id:
        try:
            requested_workstream_id = validate_workstream_id(requested_workstream_id)
        except ValueError as exc:
            return {"error": str(exc)}
        record = _get_workstream(requested_workstream_id)
        if record is None:
            return {"error": f"workstream not found: {requested_workstream_id}"}
    else:
        bridge_id, bridge, error = _resolve_bridge(args)
        if error:
            return error
        if not bridge or not bridge_id:
            return {"error": "bridge not found"}
        record = _get_workstream(bridge.workstream_id)
        if record is None:
            record = _bridge_workstream_record(bridge)

    descendants = _workstream_descendants(record.workstream_id)
    if descendants and not cascade:
        return {
            "error": f"cannot stop workstream with {len(descendants)} dependent sub workstream(s); set cascade=true",
            "dependency_children": [item.workstream_id for item in descendants],
        }
    removed = [
        _remove_workstream_runtime(item, cleanup_room=cleanup_room)
        for item in reversed(descendants)
    ]
    removed.append(_remove_workstream_runtime(record, cleanup_room=cleanup_room))
    return {
        **removed[-1],
        "cascade": cascade,
        "removed": removed,
    }


def handle_fleet_reconcile(args: Dict[str, Any]) -> Dict[str, Any]:
    apply_changes = bool(args.get("apply", False))
    rooms = list_rooms()
    workstreams = _workstream_status_payloads()
    reconciliation = _fleet_reconciliation_snapshot(rooms=rooms, workstream_payloads=workstreams)
    deleted_rooms: List[str] = []
    dropped_workstreams: List[str] = []

    if apply_changes:
        for item in reconciliation["orphaned_rooms"]:
            room_id = str(item["room_id"])
            if _room_has_runtime_references(room_id):
                continue
            if delete_room(room_id):
                deleted_rooms.append(room_id)
        for item in reconciliation["orphaned_workstreams"]:
            workstream_id = str(item["workstream_id"])
            record = _get_workstream(workstream_id)
            if record is None:
                continue
            _drop_workstream(workstream_id)
            dropped_workstreams.append(workstream_id)
        if deleted_rooms or dropped_workstreams:
            _persist_workstream_snapshot()

    _audit(
        "fleet.reconciled",
        apply=apply_changes,
        orphaned_rooms=[item["room_id"] for item in reconciliation["orphaned_rooms"]],
        orphaned_workstreams=[item["workstream_id"] for item in reconciliation["orphaned_workstreams"]],
        stale_workstreams=[item["workstream_id"] for item in reconciliation["stale_workstreams"]],
        deleted_rooms=deleted_rooms,
        dropped_workstreams=dropped_workstreams,
    )
    return {
        **reconciliation,
        "apply": apply_changes,
        "deleted_rooms": deleted_rooms,
        "dropped_workstreams": dropped_workstreams,
    }


def handle_terminal_interrupt(args: Dict[str, Any]) -> Dict[str, Any]:
    bridge_id, bridge, error = _resolve_bridge(args)
    if error:
        return error
    if not bridge or not bridge_id:
        return {"error": "bridge not found"}

    target = args.get("target", "both")
    panes: List[str]
    if target in ("a", "A"):
        panes = [bridge.pane_a]
    elif target in ("b", "B"):
        panes = [bridge.pane_b]
    elif target in ("both", "all", None):
        panes = [bridge.pane_a, bridge.pane_b]
    else:
        panes = [str(target)]

    sent: List[str] = []
    errors: List[Dict[str, str]] = []
    for pane in panes:
        try:
            bridge.backend.send(pane, "\x03", enter=False)
            bridge.last_activity_at = time.time()
            _post_room_message(
                bridge.room,
                author="bridge",
                text=f"[interrupt -> {pane}] ^C",
                kind="system",
                meta={"bridge_id": bridge.bridge_id, "pane": pane},
                source_type="bridge",
                source_role="control",
                trusted=True,
            )
            sent.append(pane)
        except Exception as exc:
            errors.append({"pane": pane, "error": str(exc)})
    _audit(
        "operator.interrupt",
        bridge_id=bridge_id,
        room_id=bridge.room.room_id,
        target=str(target),
        sent=sent,
        errors=errors,
    )

    return {"bridge_id": bridge_id, "sent": sent, "errors": errors, "ok": len(errors) == 0}


def handle_list_profiles(_args: Dict[str, Any]) -> Dict[str, Any]:
    return {"profiles": list_profiles()}


def handle_doctor(args: Dict[str, Any]) -> Dict[str, Any]:
    distro = args.get("distro")
    return doctor_report(distro=str(distro) if distro else None)


def handle_governance_resolve(args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return resolve_governance(
            model=str(args.get("model", "") or ""),
            environment=str(args.get("environment", "") or ""),
            instruction_profile=str(args.get("instruction_profile", "") or ""),
            config_path=str(args.get("config_path", "") or ""),
        )
    except ValueError as exc:
        return {"error": str(exc)}


def _inside_wsl_runtime() -> bool:
    try:
        return "microsoft" in Path("/proc/version").read_text(encoding="utf-8").lower()
    except OSError:
        return False


def _governance_environment_for_backend(backend_spec: BackendSpec) -> str:
    if os.name == "nt":
        return "native-windows"
    if backend_spec.kind == "tmux" and _inside_wsl_runtime():
        return "wsl-tmux"
    return "codex-local-dev"


def _governance_instruction_profile_for_start(args: Dict[str, Any]) -> str:
    explicit = str(args.get("instruction_profile", "") or "").strip()
    if explicit:
        return explicit
    if bool(args.get("intervention", False)):
        return "approval-gate"
    if bool(args.get("auto_forward", False)):
        return "quick-pairing"
    return ""


def _resolve_workstream_governance(
    *,
    backend_spec: BackendSpec,
    args: Dict[str, Any],
) -> Dict[str, Any]:
    return resolve_governance(
        model=str(args.get("model", "") or ""),
        environment=_governance_environment_for_backend(backend_spec),
        instruction_profile=_governance_instruction_profile_for_start(args),
        config_path=str(args.get("governance_config_path", "") or ""),
    )


def _apply_governance_start_controls(
    *,
    governance: Dict[str, Any],
    auto_forward: bool,
    intervention: bool,
    operator_review_paused: bool,
) -> Tuple[bool, bool, bool, Dict[str, Dict[str, Any]]]:
    projection = dict(governance.get("runtime_projection", {})) if isinstance(governance.get("runtime_projection"), dict) else {}
    applied: Dict[str, Dict[str, Any]] = {}
    review_mode_projection = projection.get("review_mode")
    if not isinstance(review_mode_projection, dict):
        return auto_forward, intervention, operator_review_paused, applied
    state = str(review_mode_projection.get("state", "advisory"))
    desired = str(review_mode_projection.get("value", "")).strip()
    if state != "enforced" or desired not in {"auto", "manual"}:
        return auto_forward, intervention, operator_review_paused, applied
    if desired == "manual":
        applied["review_mode"] = {
            "state": "enforced",
            "value": "manual",
            "reason": "governance_authoritative_projection",
        }
        return auto_forward, True, False, applied
    applied["review_mode"] = {
        "state": "enforced",
        "value": "auto",
        "reason": "governance_authoritative_projection",
    }
    return auto_forward, False, False, applied


def _workstream_governance_snapshot(
    *,
    governance: Dict[str, Any],
    poll_ms: int = 400,
    applied_controls: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    projection = dict(governance.get("runtime_projection", {})) if isinstance(governance.get("runtime_projection"), dict) else {}
    review_mode_projection = projection.get("review_mode") if isinstance(projection.get("review_mode"), dict) else {}
    projection_state = str(review_mode_projection.get("state", "") or "")
    baseline_review_mode = str(review_mode_projection.get("value", "") or "") if projection_state == "enforced" else ""
    effective_config = dict(governance.get("effective_config", {})) if isinstance(governance.get("effective_config"), dict) else {}
    baseline_policy = default_workstream_policy(poll_ms=poll_ms)
    for key in governance_exception_keys():
        if key == "review_mode":
            continue
        if key in effective_config:
            baseline_policy[key] = effective_config[key]
    snapshot = {
        "requested": dict(governance.get("requested", {})) if isinstance(governance.get("requested"), dict) else {},
        "matched_layers": list(governance.get("matched_layers", [])) if isinstance(governance.get("matched_layers"), list) else [],
        "missing_layers": list(governance.get("missing_layers", [])) if isinstance(governance.get("missing_layers"), list) else [],
        "authoritative_keys": list(governance.get("authoritative_keys", governance_authoritative_keys())),
        "exception_keys": list(governance.get("exception_keys", governance_exception_keys())),
        "key_classes": dict(governance.get("key_classes", {})) if isinstance(governance.get("key_classes"), dict) else {},
        "runtime_projection": projection,
        "applied_controls": dict(applied_controls or {}),
        "effective_config": effective_config,
        "provenance": dict(governance.get("provenance", {})) if isinstance(governance.get("provenance"), dict) else {},
        "review_mode_state": {
            "baseline": baseline_review_mode,
            "baseline_source": "governance" if baseline_review_mode else "runtime_default",
            "effective": baseline_review_mode,
            "effective_source": "governance" if baseline_review_mode else "runtime_default",
            "override_active": False,
            "override_mode": None,
            "override_reason": None,
        },
        "policy_state": {
            "baseline": baseline_policy,
            "baseline_source": {
                key: ("governance" if key in effective_config else "runtime_default")
                for key in baseline_policy
            },
            "effective": dict(baseline_policy),
            "overrides": {},
        },
    }
    snapshot["decision_trace"] = _governance_decision_trace(snapshot)
    return snapshot


def _governance_review_mode_state(governance: Dict[str, Any]) -> Dict[str, Any]:
    state = governance.get("review_mode_state")
    if isinstance(state, dict):
        return state
    return {
        "baseline": "",
        "baseline_source": "runtime_default",
        "effective": "",
        "effective_source": "runtime_default",
        "override_active": False,
        "override_mode": None,
        "override_reason": None,
    }


def _refresh_bridge_governance_review_mode_state(bridge: Bridge) -> None:
    state = dict(_governance_review_mode_state(bridge.governance))
    baseline = str(state.get("baseline", "") or "")
    override_active = bool(state.get("override_active", False))
    override_mode = state.get("override_mode")
    effective = bridge.review_mode()
    if override_active and override_mode == "paused":
        state["effective"] = effective
        state["effective_source"] = "operator_override"
    elif baseline:
        state["effective"] = effective
        state["effective_source"] = "governance"
        state["override_active"] = False
        state["override_mode"] = None
        state["override_reason"] = None
    else:
        state["effective"] = effective
        state["effective_source"] = "runtime_default"
    bridge.governance["review_mode_state"] = state
    bridge.governance["decision_trace"] = _governance_decision_trace(bridge.governance)


def _set_bridge_governance_review_override(
    bridge: Bridge,
    *,
    active: bool,
    mode: Optional[str],
    reason: Optional[str],
) -> None:
    state = dict(_governance_review_mode_state(bridge.governance))
    state["override_active"] = active
    state["override_mode"] = mode if active else None
    state["override_reason"] = reason if active else None
    bridge.governance["review_mode_state"] = state
    _refresh_bridge_governance_review_mode_state(bridge)


def _governance_policy_state(governance: Dict[str, Any]) -> Dict[str, Any]:
    state = governance.get("policy_state")
    if isinstance(state, dict):
        return state
    baseline = default_workstream_policy(poll_ms=400)
    return {
        "baseline": baseline,
        "baseline_source": {key: "runtime_default" for key in baseline},
        "effective": dict(baseline),
        "overrides": {},
    }


def _refresh_bridge_governance_policy_state(bridge: Bridge, *, reason: str = "") -> None:
    state = dict(_governance_policy_state(bridge.governance))
    baseline = dict(state.get("baseline", {})) if isinstance(state.get("baseline"), dict) else {}
    baseline_source = dict(state.get("baseline_source", {})) if isinstance(state.get("baseline_source"), dict) else {}
    overrides: Dict[str, Dict[str, Any]] = {}
    for key, value in bridge.policy.items():
        baseline_value = baseline.get(key)
        if baseline_value == value:
            continue
        overrides[key] = {
            "value": value,
            "source": "operator_exception",
            "reason": reason or "workstream_update_policy",
            "baseline_value": baseline_value,
            "baseline_source": baseline_source.get(key, "runtime_default"),
        }
    state["effective"] = dict(bridge.policy)
    state["overrides"] = overrides
    bridge.governance["policy_state"] = state
    bridge.governance["decision_trace"] = _governance_decision_trace(bridge.governance)


def _governance_decision_trace(governance: Dict[str, Any]) -> List[Dict[str, Any]]:
    trace: List[Dict[str, Any]] = []
    review_state = _governance_review_mode_state(governance)
    effective_review_mode = str(review_state.get("effective", "") or "")
    effective_review_source = str(review_state.get("effective_source", "") or "runtime_default")
    if effective_review_mode:
        trace.append({
            "kind": "review_mode",
            "state": "override" if bool(review_state.get("override_active", False)) else "baseline",
            "effective": effective_review_mode,
            "source": effective_review_source,
            "baseline": review_state.get("baseline"),
            "baseline_source": review_state.get("baseline_source"),
            "reason": review_state.get("override_reason") if bool(review_state.get("override_active", False)) else None,
        })
    policy_state = _governance_policy_state(governance)
    baseline = dict(policy_state.get("baseline", {})) if isinstance(policy_state.get("baseline"), dict) else {}
    overrides = dict(policy_state.get("overrides", {})) if isinstance(policy_state.get("overrides"), dict) else {}
    for key in sorted(overrides):
        entry = overrides.get(key)
        if not isinstance(entry, dict):
            continue
        trace.append({
            "kind": "policy",
            "key": key,
            "state": "override",
            "value": entry.get("value"),
            "source": entry.get("source", "operator_exception"),
            "reason": entry.get("reason"),
            "baseline_value": entry.get("baseline_value", baseline.get(key)),
            "baseline_source": entry.get("baseline_source", "runtime_default"),
        })
    return trace


def _status_governance_snapshot() -> Dict[str, Any]:
    environment = "codex-local-dev"
    if os.name == "nt":
        environment = "native-windows"
    elif _inside_wsl_runtime():
        environment = "wsl-tmux"
    return resolve_governance(
        environment=environment,
        instruction_profile="mcp-operator",
    )


def handle_audit_recent(args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        limit = _parse_int(args.get("limit"), name="limit", default=50, minimum=1, maximum=200)
        workstream_id = str(args.get("workstream_id", "") or "").strip() or None
        if workstream_id is not None:
            workstream_id = validate_workstream_id(workstream_id)
        room_id = str(args.get("room_id", "") or "").strip() or None
        if room_id is not None:
            room_id = validate_room_id(room_id)
        bridge_id = str(args.get("bridge_id", "") or "").strip() or None
        if bridge_id is not None:
            bridge_id = _validate_bridge_id(bridge_id)
    except ValueError as exc:
        return {"error": str(exc)}
    if workstream_id is not None:
        record = _get_workstream(workstream_id)
        if record is None:
            return {"error": f"workstream not found: {workstream_id}"}
        if room_id is None:
            room_id = record.room_id
    event = str(args.get("event", "") or "").strip() or None
    events = _audit_trail.recent(
        limit=limit,
        room_id=room_id,
        bridge_id=bridge_id,
        event=event,
    )
    return {
        "events": events,
        "count": len(events),
        "audit": _audit_trail.describe(),
        "scope": {
            "workstream_id": workstream_id,
            "room_id": room_id,
            "bridge_id": bridge_id,
            "event": event,
        },
    }


def _workstream_governance_compliance(item: Dict[str, Any]) -> Dict[str, Any]:
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

    if any(issue["severity"] == "critical" for issue in issues):
        state = "critical"
    elif issues:
        state = "exception"
    else:
        state = "compliant"
    return {
        "workstream_id": item.get("workstream_id"),
        "state": state,
        "issue_count": len(issues),
        "issues": issues,
    }


def _fleet_governance_compliance_snapshot(workstreams: List[Dict[str, Any]]) -> Dict[str, Any]:
    items = [_workstream_governance_compliance(item) for item in workstreams]
    critical = sum(1 for item in items if item["state"] == "critical")
    exception = sum(1 for item in items if item["state"] == "exception")
    if critical:
        state = "critical"
    elif exception:
        state = "exception"
    else:
        state = "compliant"
    return {
        "state": state,
        "total": len(items),
        "compliant": sum(1 for item in items if item["state"] == "compliant"),
        "exception": exception,
        "critical": critical,
        "issue_count": sum(int(item["issue_count"]) for item in items),
        "workstreams": items,
    }


def handle_status(_args: Dict[str, Any]) -> Dict[str, Any]:
    rooms = list_rooms()
    with _bridges_lock:
        bridge_ids = list(_bridges.keys())
        bridge_details = [_bridge_detail(bridge) for bridge in _bridges.values()]
        active_bridge_ids = {bridge["bridge_id"] for bridge in bridge_details if str(bridge.get("bridge_id", "")).strip()}
    workstreams = _workstream_status_payloads(active_bridge_ids=active_bridge_ids)
    reconciliation = _fleet_reconciliation_snapshot(rooms=rooms, workstream_payloads=workstreams)
    runtime = runtime_contract()
    recovery = _recovery_status_snapshot(workstreams, continuity=runtime.get("continuity"))
    transports = _transport_snapshot()
    transport_by_room = {item["room_id"]: item for item in transports["rooms"]}
    governance_review_overrides = sum(
        1
        for item in workstreams
        if bool(item.get("governance", {}).get("review_mode_state", {}).get("override_active"))
    )
    governance_policy_override_total = sum(
        len(item.get("governance", {}).get("policy_state", {}).get("overrides", {}))
        for item in workstreams
        if isinstance(item.get("governance", {}).get("policy_state", {}).get("overrides"), dict)
    )
    governance_compliance = _fleet_governance_compliance_snapshot(workstreams)
    return {
        "rooms": [{"id": r.room_id, "messages": r.message_count, "age": time.time() - r.created_at,
                   "subscribers": transport_by_room.get(
                       r.room_id,
                       {"room_id": r.room_id, "sse": 0, "websocket": 0, "total": 0},
                   )}
                  for r in rooms],
        "bridges": bridge_ids,
        "bridge_details": bridge_details,
        "workstreams": [
            {
                **item,
                "subscribers": transport_by_room.get(
                    item["room_id"],
                    {"room_id": item["room_id"], "sse": 0, "websocket": 0, "total": 0},
                ),
            }
            for item in workstreams
        ],
        "fleet": {
            "count": len(workstreams),
            "live": sum(1 for item in workstreams if item["state"] == "live"),
            "restored": sum(1 for item in workstreams if item["state"] == "restored"),
            "degraded": sum(1 for item in workstreams if item["state"] == "degraded"),
            "manual_takeover": sum(1 for item in workstreams if bool(item.get("recovery", {}).get("manual_takeover_required"))),
            "pending": sum(int(item["pending_count"]) for item in workstreams),
            "healthy": sum(1 for item in workstreams if item["health"]["state"] == "ok"),
            "warn": sum(1 for item in workstreams if item["health"]["state"] == "warn"),
            "critical": sum(1 for item in workstreams if item["health"]["state"] == "critical"),
            "alerts": sum(int(item["health"]["alert_count"]) for item in workstreams),
            "review": sum(1 for item in workstreams if item["health"]["escalation"] == "review"),
            "intervene": sum(1 for item in workstreams if item["health"]["escalation"] == "intervene"),
            "governance_review_overrides": governance_review_overrides,
            "governance_policy_overrides": governance_policy_override_total,
            "governance_exceptions": governance_review_overrides + governance_policy_override_total,
            "governance_compliance_state": governance_compliance["state"],
            "governance_compliant": governance_compliance["compliant"],
            "governance_exception": governance_compliance["exception"],
            "governance_critical": governance_compliance["critical"],
            "orphaned_rooms": len(reconciliation["orphaned_rooms"]),
            "orphaned_workstreams": len(reconciliation["orphaned_workstreams"]),
            "stale_workstreams": len(reconciliation["stale_workstreams"]),
        },
        "reconciliation": reconciliation,
        "recovery": recovery,
        "transports": transports,
        "audit": _audit_trail.describe(),
        "runtime": runtime,
        "security": _server_security_payload(),
        "governance": _status_governance_snapshot(),
        "governance_compliance": governance_compliance,
    }


HANDLERS = {
    "workstream_list": handle_workstream_list,
    "workstream_get": handle_workstream_get,
    "workstream_pause_review": handle_workstream_pause_review,
    "workstream_resume_review": handle_workstream_resume_review,
    "workstream_update_policy": handle_workstream_update_policy,
    "workstream_update_dependency": handle_workstream_update_dependency,
    "workstream_stop": handle_workstream_stop,
    "fleet_reconcile": handle_fleet_reconcile,
    "terminal_init": handle_terminal_init,
    "terminal_capture": handle_terminal_capture,
    "terminal_send": handle_terminal_send,
    "terminal_interrupt": handle_terminal_interrupt,
    "room_create": handle_room_create,
    "room_poll": handle_room_poll,
    "room_post": handle_room_post,
    "bridge_start": handle_bridge_start,
    "bridge_stop": handle_bridge_stop,
    "intervention_list": handle_intervention_list,
    "intervention_approve": handle_intervention_approve,
    "intervention_reject": handle_intervention_reject,
    "list_profiles": handle_list_profiles,
    "doctor": handle_doctor,
    "governance_resolve": handle_governance_resolve,
    "audit_recent": handle_audit_recent,
    "status": handle_status,
}

TOOL_DESCRIPTIONS = {
    "workstream_list": "List workstreams with health, policy, and escalation state.",
    "workstream_get": "Return one workstream with health, policy, and escalation state.",
    "workstream_pause_review": "Pause auto-forward review state for a workstream.",
    "workstream_resume_review": "Resume auto-forward review state for a workstream when no pending items remain.",
    "workstream_update_policy": "Update per-workstream governance policy such as rate limits and silent thresholds.",
    "workstream_update_dependency": "Update main/sub dependency metadata for a workstream.",
    "workstream_stop": "Stop a workstream runtime and optionally clean up its room.",
    "fleet_reconcile": "Report or apply stale/orphan runtime reconciliation across rooms and workstreams.",
    "terminal_init": "Create a terminal session with pane A and pane B.",
    "terminal_capture": "Capture recent lines from a target pane.",
    "terminal_send": "Send text to a target pane.",
    "terminal_interrupt": "Send Ctrl+C to one or both panes of a bridge.",
    "room_create": "Create a chat room buffer.",
    "room_poll": "Poll room messages after a cursor id.",
    "room_post": "Post a message to a room and optionally deliver to pane(s).",
    "bridge_start": "Start background bridge worker between two panes.",
    "bridge_stop": "Stop a running bridge worker.",
    "intervention_list": "List pending human-review messages.",
    "intervention_approve": "Approve pending message(s) for delivery.",
    "intervention_reject": "Reject pending message(s).",
    "list_profiles": "List available parsing profiles.",
    "doctor": "Report local backend support and first-class CLI compatibility.",
    "governance_resolve": "Resolve layered governance config into matched layers, effective config, and provenance.",
    "audit_recent": "Return recent persisted audit events for rooms, bridges, and operator actions.",
    "status": "Return active rooms and bridge ids.",
}

_DEFAULT_TOOL_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {},
    "additionalProperties": True,
}

_BRIDGE_RESOLUTION_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "workstream_id": {
            "type": "string",
            "description": "Preferred fleet-safe target identifier for a workstream.",
        },
        "bridge_id": {
            "type": "string",
            "description": "Explicit bridge id. Optional when room_id or a single active bridge can resolve the target.",
        },
        "room_id": {
            "type": "string",
            "description": "Optional room id fallback when bridge_id is unknown.",
        },
    },
    "additionalProperties": True,
}

_TOOL_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "bridge_start": {
        "type": "object",
        "properties": {
            "pane_a": {"type": "string"},
            "pane_b": {"type": "string"},
            "room_id": {"type": "string"},
            "bridge_id": {"type": "string"},
            "workstream_id": {"type": "string"},
            "tier": {"type": "string", "enum": ["main", "sub"]},
            "parent_workstream_id": {"type": "string"},
            "backend": {"type": "string"},
            "backend_id": {"type": "string"},
            "shell": {"type": "string"},
            "distro": {"type": "string"},
            "profile": {"type": "string"},
            "model": {"type": "string"},
            "instruction_profile": {"type": "string"},
            "governance_config_path": {"type": "string"},
            "auto_forward": {"type": "boolean"},
            "intervention": {"type": "boolean"},
            "poll_ms": {"type": "integer", "minimum": 10, "maximum": _MAX_POLL_MS},
            "lines": {"type": "integer", "minimum": 1, "maximum": _MAX_CAPTURE_LINES},
        },
        "required": ["pane_a", "pane_b"],
        "additionalProperties": False,
    },
    "workstream_list": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
    "workstream_get": {
        "type": "object",
        "properties": {
            "workstream_id": {"type": "string"},
        },
        "required": ["workstream_id"],
        "additionalProperties": False,
    },
    "workstream_pause_review": {
        "type": "object",
        "properties": {
            **_BRIDGE_RESOLUTION_SCHEMA["properties"],
        },
        "additionalProperties": False,
    },
    "workstream_resume_review": {
        "type": "object",
        "properties": {
            **_BRIDGE_RESOLUTION_SCHEMA["properties"],
        },
        "additionalProperties": False,
    },
    "workstream_update_policy": {
        "type": "object",
        "properties": {
            "workstream_id": {"type": "string"},
            "rate_limit": {"type": "integer", "minimum": 1},
            "window_seconds": {"type": "number", "minimum": 0.5},
            "streak_limit": {"type": "integer", "minimum": 1},
            "pending_warn": {"type": "integer", "minimum": 0},
            "pending_critical": {"type": "integer", "minimum": 0},
            "pending_limit": {"type": "integer", "minimum": 1},
            "silent_seconds": {"type": "number", "minimum": 5},
        },
        "required": ["workstream_id"],
        "additionalProperties": False,
    },
    "workstream_update_dependency": {
        "type": "object",
        "properties": {
            "workstream_id": {"type": "string"},
            "tier": {"type": "string", "enum": ["main", "sub"]},
            "parent_workstream_id": {"type": "string"},
        },
        "required": ["workstream_id"],
        "additionalProperties": False,
    },
    "workstream_stop": {
        "type": "object",
        "properties": {
            **_BRIDGE_RESOLUTION_SCHEMA["properties"],
            "cascade": {"type": "boolean"},
            "cleanup_room": {"type": "boolean"},
        },
        "additionalProperties": False,
    },
    "fleet_reconcile": {
        "type": "object",
        "properties": {
            "apply": {"type": "boolean"},
        },
        "additionalProperties": False,
    },
    "room_post": {
        "type": "object",
        "properties": {
            "room_id": {"type": "string"},
            "author": {"type": "string"},
            "text": {"type": "string"},
            "kind": {"type": "string"},
            "deliver": {"type": "string", "enum": ["a", "b", "both"]},
            "workstream_id": {
                "type": "string",
                "description": "Optional fleet-safe target identifier for delivery.",
            },
            "bridge_id": {
                "type": "string",
                "description": "Optional when room_id already identifies a single active bridge.",
            },
        },
        "required": ["room_id", "text"],
        "additionalProperties": True,
    },
    "intervention_list": _BRIDGE_RESOLUTION_SCHEMA,
    "intervention_approve": {
        "type": "object",
        "properties": {
            **_BRIDGE_RESOLUTION_SCHEMA["properties"],
            "id": {
                "description": "Pending message id or 'all'.",
                "oneOf": [{"type": "integer"}, {"type": "string", "enum": ["all"]}],
            },
            "edited_text": {"type": "string"},
        },
        "additionalProperties": True,
    },
    "intervention_reject": {
        "type": "object",
        "properties": {
            **_BRIDGE_RESOLUTION_SCHEMA["properties"],
            "id": {
                "description": "Pending message id or 'all'.",
                "oneOf": [{"type": "integer"}, {"type": "string", "enum": ["all"]}],
            },
        },
        "additionalProperties": True,
    },
    "terminal_interrupt": {
        "type": "object",
        "properties": {
            **_BRIDGE_RESOLUTION_SCHEMA["properties"],
            "target": {
                "type": "string",
                "description": "Interrupt target: a, b, both, or a raw pane id.",
            },
        },
        "additionalProperties": True,
    },
    "status": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
    "audit_recent": {
        "type": "object",
        "properties": {
            "workstream_id": {"type": "string"},
            "room_id": {"type": "string"},
            "bridge_id": {"type": "string"},
            "event": {"type": "string"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 200},
        },
        "additionalProperties": False,
    },
    "governance_resolve": {
        "type": "object",
        "properties": {
            "model": {"type": "string"},
            "environment": {"type": "string"},
            "instruction_profile": {"type": "string"},
            "config_path": {"type": "string"},
        },
        "additionalProperties": False,
    },
}

SERVER_INFO = {"name": "terminal-bridge-v2", "version": "0.2.0"}
LATEST_PROTOCOL_VERSION = "2025-11-25"
@dataclass
class SidepanelRoomState:
    backend: TerminalBackend
    pane_a: str
    pane_b: str
    room_id: str
    session: str
    pending: bool = False
    mode: str = "tb2-codex"
    output_path: str = ""
    log_path: str = ""
    run_id: str = ""
    preview_text: str = ""
    process: Optional[subprocess.Popen[str]] = None


_sidepanel_lock = threading.RLock()
_sidepanel_rooms: Dict[str, SidepanelRoomState] = {}
_sidepanel_probe_cache: Dict[str, Any] = {"checked_at": 0.0, "detail": "", "ok": None}
_SIDEPANEL_PROBE_TTL_SECONDS = 5.0


def _sidepanel_runtime() -> SidepanelRuntime:
    return runtime_from_env(os.environ, which=shutil.which, home=Path.home())


def _sidepanel_backend_ready(*, force: bool = False) -> Tuple[bool, str]:
    with _sidepanel_lock:
        checked_at = float(_sidepanel_probe_cache.get("checked_at", 0.0) or 0.0)
        ok = _sidepanel_probe_cache.get("ok")
        detail = str(_sidepanel_probe_cache.get("detail", "") or "")
        if not force and ok is not None and time.time() - checked_at <= _SIDEPANEL_PROBE_TTL_SECONDS:
            return bool(ok), detail
    session = "sp-health-probe"
    backend = None
    try:
        backend = _make_backend({
            "backend": default_backend_name(),
            "backend_id": "sidepanel-health-probe",
        })
        backend.init_session(session)
        backend.kill_session(session)
        ok = True
        detail = ""
    except Exception as exc:
        ok = False
        detail = str(exc)
    with _sidepanel_lock:
        _sidepanel_probe_cache["checked_at"] = time.time()
        _sidepanel_probe_cache["ok"] = ok
        _sidepanel_probe_cache["detail"] = detail
    return ok, detail


def _sidepanel_health_payload() -> Dict[str, Any]:
    runtime = _sidepanel_runtime()
    backend_ready, backend_detail = _sidepanel_backend_ready()
    with _sidepanel_lock:
        room_count = len(_sidepanel_rooms)
    return _sidepanel_health_contract(
        runtime,
        backend_ready=backend_ready,
        backend_detail=backend_detail,
        room_count=room_count,
    )


def _sidepanel_finalize_run(room_id: str, run_id: str, proc: subprocess.Popen[str], log_file: Any) -> None:
    try:
        proc.wait()
    finally:
        try:
            log_file.close()
        except OSError:
            pass

    with _sidepanel_lock:
        state = _sidepanel_rooms.get(room_id)
        if state is None or state.run_id != run_id:
            return
        output_path = state.output_path
        log_path = state.log_path
        provider = _sidepanel_runtime().provider
        session = state.session
        state.pending = False
        state.process = None
        state.preview_text = ""
        state.run_id = ""
        state.log_path = ""
        state.output_path = ""
    room = get_room(room_id)
    if room is None:
        return
    text = _read_text_if_exists(output_path) or _read_text_if_exists(log_path) or "Codex completed without a final message."
    _post_room_message(
        room,
        author="assistant",
        text=text,
        kind="chat",
        meta={
            "provider": provider,
            "session": session,
            "streamKey": run_id,
            "replace": True,
            "final": True,
            "sidepanelRole": "assistant",
        },
        source_type="sidepanel",
        source_role="assistant",
        trusted=True,
    )


def _sidepanel_room_state(room_id: str) -> Optional[SidepanelRoomState]:
    with _sidepanel_lock:
        return _sidepanel_rooms.get(room_id)


def _sidepanel_create_room() -> Dict[str, Any]:
    room = create_room()
    existing = _sidepanel_room_state(room.room_id)
    if existing is not None:
        return {"ok": True, "roomId": existing.room_id}
    backend_args = {
        "backend": default_backend_name(),
        "backend_id": f"sidepanel-{room.room_id}",
    }
    backend = _make_backend(backend_args)
    session = f"sp-{room.room_id}"
    pane_a, pane_b = backend.init_session(session)
    with _sidepanel_lock:
        _sidepanel_rooms[room.room_id] = SidepanelRoomState(
            backend=backend,
            pane_a=pane_a,
            pane_b=pane_b,
            room_id=room.room_id,
            session=session,
        )
    return {"ok": True, "roomId": room.room_id}


def _sidepanel_create_room_response() -> Tuple[int, Dict[str, Any]]:
    try:
        result = _sidepanel_create_room()
        with _sidepanel_lock:
            _sidepanel_probe_cache["checked_at"] = time.time()
            _sidepanel_probe_cache["ok"] = True
            _sidepanel_probe_cache["detail"] = ""
        return 200, result
    except Exception as exc:
        with _sidepanel_lock:
            _sidepanel_probe_cache["checked_at"] = time.time()
            _sidepanel_probe_cache["ok"] = False
            _sidepanel_probe_cache["detail"] = str(exc)
        return 503, {
            "ok": False,
            "error": f"failed to initialize TB2 room session: {exc}",
        }


def _sidepanel_poll_response(room_id: str, after_id: Any) -> Tuple[int, Dict[str, Any]]:
    try:
        normalized_room_id = validate_room_id(room_id)
        cursor = _parse_int(after_id, name="afterId", default=0, minimum=0)
    except ValueError as exc:
        return 400, {"ok": False, "error": str(exc)}
    room = get_room(normalized_room_id)
    state = _sidepanel_room_state(normalized_room_id)
    if room is None or state is None:
        return 404, {"ok": False, "error": "room not found", "roomId": normalized_room_id}
    if state.pending and state.log_path:
        preview = _read_tail_if_exists(state.log_path)
        if preview and preview != state.preview_text:
            with _sidepanel_lock:
                current = _sidepanel_rooms.get(normalized_room_id)
                if current is not None and current.run_id == state.run_id:
                    current.preview_text = preview
            _post_room_message(
                room,
                author="bridge",
                text=_sidepanel_render_live_log(preview),
                kind="system",
                meta={
                    "provider": _sidepanel_runtime().provider,
                    "session": state.session,
                    "streamKey": state.run_id,
                    "replace": True,
                    "final": False,
                    "sidepanelRole": "system",
                },
                source_type="sidepanel",
                source_role="bridge",
                trusted=True,
            )
    messages = room.poll(after_id=cursor, limit=_MAX_STREAM_LIMIT)
    return 200, {
        "ok": True,
        "roomId": normalized_room_id,
        "latestId": room.latest_id,
        "messages": [_sidepanel_message_payload(item) for item in messages],
    }


def _sidepanel_message_response(payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    prompt = str(payload.get("prompt", "")).strip()
    room_id = str(payload.get("roomId", "")).strip()
    mode = str(payload.get("mode", "tb2-codex")).strip() or "tb2-codex"
    if not prompt:
        return 400, {"ok": False, "error": "prompt is required"}
    try:
        normalized_room_id = validate_room_id(room_id)
    except ValueError as exc:
        return 400, {"ok": False, "error": str(exc)}
    room = get_room(normalized_room_id)
    state = _sidepanel_room_state(normalized_room_id)
    if room is None or state is None:
        return 404, {"ok": False, "error": "room not found", "roomId": normalized_room_id}
    if state.pending:
        return 409, {
            "ok": False,
            "error": "room already has a pending prompt",
            "roomId": normalized_room_id,
        }
    runtime = _sidepanel_runtime()
    if not runtime.codex_available:
        return 503, {
            "ok": False,
            "error": "codex CLI not found in PATH",
            "roomId": normalized_room_id,
        }
    run_id, log_path, output_path = _sidepanel_run_paths(normalized_room_id)
    command = [
        runtime.codex_path,
        "exec",
        "--skip-git-repo-check",
        "--sandbox",
        "workspace-write",
        "-C",
        runtime.workdir,
        "--output-last-message",
        output_path,
        "-",
    ]
    prompt_text = _sidepanel_render_prompt(room, prompt)
    try:
        log_file = open(log_path, "w", encoding="utf-8")
    except OSError as exc:
        return 503, {
            "ok": False,
            "error": f"failed to prepare codex log file: {exc}",
            "roomId": normalized_room_id,
        }

    try:
        proc = subprocess.Popen(
            command,
            cwd=runtime.workdir,
            stdin=subprocess.PIPE,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
        )
    except OSError as exc:
        try:
            log_file.close()
        except OSError:
            pass
        return 503, {
            "ok": False,
            "error": f"failed to start codex exec: {exc}",
            "roomId": normalized_room_id,
        }
    if proc.stdin is not None:
        proc.stdin.write(prompt_text)
        proc.stdin.close()
    user = _post_room_message(
        room,
        author="user",
        text=prompt,
        kind="chat",
        meta={
            "mode": mode,
            "provider": runtime.provider,
            "session": state.session,
            "sidepanelRole": "user",
        },
        source_type="client",
        source_role="sidepanel",
        trusted=False,
    )
    with _sidepanel_lock:
        current = _sidepanel_rooms.get(normalized_room_id)
        if current is None:
            current = state
            _sidepanel_rooms[normalized_room_id] = current
        current.pending = True
        current.mode = mode
        current.process = proc
        current.run_id = run_id
        current.log_path = log_path
        current.output_path = output_path
        current.preview_text = ""
    thread = threading.Thread(
        target=_sidepanel_finalize_run,
        args=(normalized_room_id, run_id, proc, log_file),
        daemon=True,
        name=f"sidepanel-{run_id}",
    )
    thread.start()
    return 202, {
        "ok": True,
        "provider": runtime.provider,
        "roomId": normalized_room_id,
        "latestId": user.id,
        "text": "Prompt accepted. Poll the room for Codex output.",
    }


def _tool_specs() -> List[Dict[str, Any]]:
    tools: List[Dict[str, Any]] = []
    for name in HANDLERS:
        tools.append({
            "name": name,
            "description": TOOL_DESCRIPTIONS.get(name, name),
            "inputSchema": _TOOL_SCHEMAS.get(name, _DEFAULT_TOOL_SCHEMA),
        })
    return tools


def _as_tool_text(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    try:
        return json.dumps(payload, ensure_ascii=False, indent=2)
    except TypeError:
        return str(payload)


def _as_structured_content(payload: Any) -> Dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    return {"result": payload}


def _tool_call_result(payload: Any, *, is_error: bool = False) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "content": [{"type": "text", "text": _as_tool_text(payload)}],
        "structuredContent": _as_structured_content(payload),
    }
    if is_error:
        result["isError"] = True
    return result


def _looks_like_tool_error(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    err = payload.get("error")
    return isinstance(err, str) and bool(err.strip())


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload).encode("utf-8")


def _parse_room_stream_request(path: str, query: str) -> Tuple[Optional[str], int, int, Optional[str]]:
    if not path.startswith("/rooms/") or not path.endswith("/stream"):
        return None, 0, 0, None
    raw_room_id = unquote(path[len("/rooms/"):-len("/stream")]).strip("/")
    params = parse_qs(query)
    try:
        room_id = validate_room_id(raw_room_id)
        after_id = _parse_int(params.get("after_id", ["0"])[0], name="after_id", default=0, minimum=0)
        backlog_limit = _parse_int(
            params.get("limit", ["200"])[0],
            name="limit",
            default=200,
            minimum=1,
            maximum=_MAX_STREAM_LIMIT,
        )
    except ValueError as exc:
        return raw_room_id, 0, 0, str(exc)
    return room_id, after_id, backlog_limit, None


def _sse_bytes(event_name: str, payload: Dict[str, Any], *, event_id: Optional[str] = None) -> bytes:
    lines: List[str] = []
    if event_id:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event_name}")
    data = json.dumps(payload, ensure_ascii=False)
    for line in data.splitlines():
        lines.append(f"data: {line}")
    lines.append("")
    lines.append("")
    return "\n".join(lines).encode("utf-8")


def _ws_accept_value(key: str) -> str:
    guid = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
    digest = hashlib.sha1((key + guid).encode("utf-8")).digest()
    return base64.b64encode(digest).decode("ascii")


def _ws_read_exact(stream: Any, size: int) -> bytes:
    chunks: List[bytes] = []
    remaining = size
    while remaining > 0:
        chunk = stream.read(remaining)
        if not chunk:
            raise EOFError("websocket closed")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _ws_read_frame(stream: Any) -> Tuple[int, bytes]:
    header = _ws_read_exact(stream, 2)
    first, second = header[0], header[1]
    opcode = first & 0x0F
    masked = (second & 0x80) != 0
    length = second & 0x7F
    if length == 126:
        length = struct.unpack("!H", _ws_read_exact(stream, 2))[0]
    elif length == 127:
        length = struct.unpack("!Q", _ws_read_exact(stream, 8))[0]
    mask = _ws_read_exact(stream, 4) if masked else b""
    payload = _ws_read_exact(stream, length) if length else b""
    if masked:
        payload = bytes(byte ^ mask[idx % 4] for idx, byte in enumerate(payload))
    return opcode, payload


def _ws_frame(payload: bytes, *, opcode: int = 0x1) -> bytes:
    header = bytearray([0x80 | (opcode & 0x0F)])
    length = len(payload)
    if length < 126:
        header.append(length)
    elif length < 65536:
        header.append(126)
        header.extend(struct.pack("!H", length))
    else:
        header.append(127)
        header.extend(struct.pack("!Q", length))
    return bytes(header) + payload


def _handle_get_path(path: str) -> Tuple[int, str, bytes]:
    if path in ("", "/", "/ui", "/index.html"):
        html = build_gui_html("/mcp").encode("utf-8")
        return 200, "text/html; charset=utf-8", html

    if path == "/healthz":
        return 200, "application/json", _json_bytes({"ok": True, "security": _server_security_payload()})

    if path == "/mcp":
        return 200, "application/json", _json_bytes({
            "ok": True,
            "service": "terminal-bridge-v2",
            "endpoint": "/mcp",
            "ui": "/",
            "rooms_stream": "/rooms/{room_id}/stream",
            "websocket": "/ws",
            "security": _server_security_payload(),
        })

    return 404, "application/json", _json_bytes({
        "error": "not found",
        "path": path,
    })


def _handle_sidepanel_get(parsed: Any) -> Optional[Tuple[int, Dict[str, Any]]]:
    path = parsed.path
    if path == "/health":
        return 200, _sidepanel_health_payload()
    if path != "/v1/tb2/poll":
        return None
    query = parse_qs(parsed.query)
    room_id = query.get("roomId", [""])[0]
    after_id = query.get("afterId", ["0"])[0]
    return _sidepanel_poll_response(room_id, after_id)


def _handle_sidepanel_post(path: str, payload: Dict[str, Any]) -> Optional[Tuple[int, Dict[str, Any]]]:
    if path == "/v1/tb2/rooms":
        return _sidepanel_create_room_response()
    if path == "/v1/tb2/message":
        return _sidepanel_message_response(payload)
    return None


# ---------------------------------------------------------------------------
# HTTP handler (MCP JSON-RPC)
# ---------------------------------------------------------------------------

class MCPHandler(BaseHTTPRequestHandler):
    def _sanitize_header_value(self, value: str) -> str:
        """Remove CR/LF to prevent HTTP response splitting in header values."""
        return value.replace("\r", "").replace("\n", "")

    def _write_cors_headers(self) -> None:
        headers = getattr(self, "headers", None)
        if headers is None:
            return
        origin = headers.get("Origin", "").strip()
        if not origin or not _origin_allowed(origin):
            return
        safe_origin = self._sanitize_header_value(origin)
        self.send_header("Access-Control-Allow-Origin", safe_origin)
        self.send_header("Access-Control-Allow-Headers", "content-type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Vary", "Origin")

    def do_OPTIONS(self) -> None:
        origin = self.headers.get("Origin", "")
        path = urlparse(self.path).path
        if path in {"/health", "/v1/tb2/poll", "/v1/tb2/rooms", "/v1/tb2/message"}:
            allowed = _sidepanel_request_allowed(origin, self.client_address[0])
        else:
            allowed = _origin_allowed(origin)
        if not allowed:
            self._reply(403, {"error": "forbidden origin"})
            return
        self._reply_empty(204)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        room_id, after_id, backlog_limit, stream_error = _parse_room_stream_request(path, parsed.query)
        if room_id is not None:
            if not _origin_allowed(self.headers.get("Origin", "")):
                self._reply(403, {"error": "forbidden origin"})
                return
            if stream_error:
                self._reply(400, {"error": stream_error})
                return
            self._serve_room_sse(room_id, after_id=after_id, backlog_limit=backlog_limit)
            return
        sidepanel = _handle_sidepanel_get(parsed)
        if sidepanel is not None:
            if not _sidepanel_request_allowed(self.headers.get("Origin", ""), self.client_address[0]):
                self._reply(403, {"ok": False, "error": "forbidden sidepanel origin"})
                return
            code, body = sidepanel
            self._reply(code, body)
            return
        if path == "/ws":
            if not _origin_allowed(self.headers.get("Origin", "")):
                self._reply(403, {"error": "forbidden origin"})
                return
            self._serve_websocket()
            return
        code, content_type, body = _handle_get_path(path)
        self._reply_raw(code, content_type, body)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        origin = self.headers.get("Origin", "")
        if path == "/v1/tb2/rooms":
            if not _sidepanel_request_allowed(origin, self.client_address[0]):
                self._reply(403, {"ok": False, "error": "forbidden sidepanel origin"})
                return
            code, body = _sidepanel_create_room_response()
            self._reply(code, body)
            return
        if path == "/v1/tb2/message":
            if not _sidepanel_request_allowed(origin, self.client_address[0]):
                self._reply(403, {"ok": False, "error": "forbidden sidepanel origin"})
                return
        elif not _origin_allowed(origin):
            self._reply(403, {"error": "forbidden origin"})
            return
        if path not in {"/mcp", "/v1/tb2/message"}:
            self._reply(404, {"error": "not found", "path": path})
            return
        raw_length = self.headers.get("Content-Length")
        try:
            length = _parse_int(raw_length, name="Content-Length", minimum=0)
        except ValueError as exc:
            self._reply(400, {"error": str(exc)})
            return
        if length > _MAX_BODY_BYTES:
            self._reply(413, {"error": "request too large", "max_bytes": _MAX_BODY_BYTES})
            return
        try:
            self.connection.settimeout(_HTTP_READ_TIMEOUT_SECONDS)
            body = self.rfile.read(length)
        except socket.timeout:
            self._reply(408, {"error": "request body read timed out"})
            return
        except OSError:
            self._reply(400, {"error": "failed to read request body"})
            return
        if len(body) != length:
            self._reply(400, {"error": "incomplete request body"})
            return
        try:
            req = json.loads(body)
        except json.JSONDecodeError:
            self._reply(400, {"error": "invalid JSON"})
            return
        if path == "/v1/tb2/message":
            if not isinstance(req, dict):
                self._reply(400, {"ok": False, "error": "invalid JSON object"})
                return
            code, payload = _sidepanel_message_response(req)
            self._reply(code, payload)
            return

        # JSON-RPC batch support
        if isinstance(req, list):
            responses: List[Dict[str, Any]] = []
            for item in req:
                if not isinstance(item, dict):
                    responses.append({
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {"code": -32600, "message": "invalid request"},
                    })
                    continue
                res = self._handle_rpc(item)
                if res is not None:
                    responses.append(res)
            if responses:
                self._reply(200, responses)
            else:
                self._reply_empty(202)
            return

        if not isinstance(req, dict):
            self._reply(200, {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32600, "message": "invalid request"},
            })
            return

        response = self._handle_rpc(req)
        if response is None:
            self._reply_empty(202)
            return
        self._reply(200, response)

    def _handle_rpc(self, req: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        method = str(req.get("method", ""))
        params = req.get("params", {})
        req_id = req.get("id")
        is_notification = "id" not in req
        if not isinstance(params, dict):
            params = {}

        # MCP initialize handshake
        if method == "initialize":
            protocol = str(params.get("protocolVersion", LATEST_PROTOCOL_VERSION))
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": protocol,
                    "capabilities": {
                        "tools": {"listChanged": False},
                        "resources": {},
                        "prompts": {},
                    },
                    "serverInfo": SERVER_INFO,
                },
            }

        # MCP lifecycle notification
        if method == "notifications/initialized":
            if is_notification:
                return None
            return {"jsonrpc": "2.0", "id": req_id, "result": {}}

        # MCP ping
        if method == "ping":
            return {"jsonrpc": "2.0", "id": req_id, "result": {}}

        # MCP tools/list
        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": _tool_specs()}}

        # MCP tools/call
        if method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})
            if not isinstance(tool_name, str) or not tool_name:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32602, "message": "tools/call requires a non-empty string name"},
                }
            if not isinstance(tool_args, dict):
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32602, "message": "tools/call arguments must be an object"},
                }
            handler = HANDLERS.get(tool_name)
            if not handler:
                payload = {"error": f"unknown tool: {tool_name}", "tool": tool_name}
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": _tool_call_result(payload, is_error=True),
                }
            try:
                payload = handler(tool_args)
            except Exception as exc:
                payload = {"error": str(exc), "tool": tool_name}
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": _tool_call_result(payload, is_error=True),
                }
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": _tool_call_result(payload, is_error=_looks_like_tool_error(payload)),
            }

        # Optional lists for clients that probe server capabilities
        if method == "resources/list":
            return {"jsonrpc": "2.0", "id": req_id, "result": {"resources": []}}
        if method == "prompts/list":
            return {"jsonrpc": "2.0", "id": req_id, "result": {"prompts": []}}

        # Ignore unknown notifications to avoid noisy disconnects.
        if is_notification:
            return None
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"unknown method: {method}"},
        }

    def _reply(self, code: int, body: Any) -> None:
        data = json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self._write_cors_headers()
        self.end_headers()
        self.wfile.write(data)

    def _reply_raw(self, code: int, content_type: str, body: bytes) -> None:
        self.send_response(code)
        safe_content_type = self._sanitize_header_value(content_type)
        self.send_header("Content-Type", safe_content_type)
        self.send_header("Content-Length", str(len(body)))
        self._write_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _reply_empty(self, code: int) -> None:
        self.send_response(code)
        self.send_header("Content-Length", "0")
        self._write_cors_headers()
        self.end_headers()

    def _serve_room_sse(self, room_id: str, *, after_id: int, backlog_limit: int) -> None:
        room = get_room(room_id)
        if not room:
            self._reply(404, {"error": "room not found", "room_id": room_id})
            return

        last_event_id = self.headers.get("Last-Event-ID", "").strip()
        if last_event_id and ":" in last_event_id:
            _, _, tail = last_event_id.rpartition(":")
            if tail.isdigit():
                after_id = max(after_id, int(tail))

        try:
            sub = room.subscribe(after_id=after_id, backlog_limit=backlog_limit)
        except RuntimeError:
            self._reply(410, {"error": "room closed", "room_id": room_id})
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        self.wfile.flush()
        _transport_counter(_sse_subscribers, room_id, 1)
        try:
            ready = {
                "type": "ready",
                "room_id": room_id,
                "latest_id": room.latest_id,
                "transport": "sse",
            }
            self.wfile.write(_sse_bytes("ready", ready))
            self.wfile.flush()
            while True:
                try:
                    items = sub.get(timeout=15.0, limit=100)
                except EOFError:
                    break
                if not items:
                    self.wfile.write(b": keep-alive\n\n")
                    self.wfile.flush()
                    continue
                for msg in items:
                    payload = _room_message_payload(room, msg)
                    self.wfile.write(_sse_bytes("room", payload, event_id=payload["event_id"]))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            sub.close()
            _transport_counter(_sse_subscribers, room_id, -1)

    def _serve_websocket(self) -> None:
        upgrade = self.headers.get("Upgrade", "")
        key = self.headers.get("Sec-WebSocket-Key", "")
        if upgrade.lower() != "websocket" or not key:
            self._reply(400, {"error": "websocket upgrade required"})
            return

        self.send_response(101, "Switching Protocols")
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", _ws_accept_value(key))
        self.end_headers()
        self.connection.settimeout(0.5)
        _ws_client_delta(1)
        subscriptions: Dict[str, RoomSubscription] = {}
        try:
            self._ws_send({"type": "ready", "transport": "websocket"})
            while True:
                self._ws_flush_room_events(subscriptions)
                try:
                    opcode, payload = _ws_read_frame(self.rfile)
                except socket.timeout:
                    continue
                except EOFError:
                    break
                if opcode == 0x8:
                    break
                if opcode == 0x9:
                    self.wfile.write(_ws_frame(payload, opcode=0xA))
                    self.wfile.flush()
                    continue
                if opcode != 0x1:
                    self._ws_send({"type": "error", "error": f"unsupported websocket opcode: {opcode}"})
                    continue
                try:
                    message = json.loads(payload.decode("utf-8"))
                except json.JSONDecodeError:
                    self._ws_send({"type": "error", "error": "invalid websocket JSON"})
                    continue
                self._handle_ws_message(message, subscriptions)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            for room_id, sub in list(subscriptions.items()):
                sub.close()
                _transport_counter(_ws_subscribers, room_id, -1)
            _ws_client_delta(-1)

    def _handle_ws_message(self, message: Dict[str, Any], subscriptions: Dict[str, RoomSubscription]) -> None:
        action = str(message.get("action", "")).strip()
        if not action:
            self._ws_send({"type": "error", "error": "missing websocket action"})
            return

        if action == "subscribe":
            room_id = str(message.get("room_id", "")).strip()
            if not room_id:
                self._ws_send({"type": "error", "error": "room_id is required", "action": action})
                return
            try:
                room_id = validate_room_id(room_id)
                after_id = _parse_int(message.get("after_id"), name="after_id", default=0, minimum=0)
                backlog_limit = _parse_int(
                    message.get("limit"),
                    name="limit",
                    default=200,
                    minimum=1,
                    maximum=_MAX_STREAM_LIMIT,
                )
            except ValueError as exc:
                self._ws_send({"type": "error", "error": str(exc), "action": action})
                return
            room = get_room(room_id)
            if not room:
                self._ws_send({"type": "error", "error": "room not found", "room_id": room_id, "action": action})
                return
            existing = subscriptions.pop(room_id, None)
            if existing is not None:
                existing.close()
                _transport_counter(_ws_subscribers, room_id, -1)
            subscriptions[room_id] = room.subscribe(after_id=after_id, backlog_limit=backlog_limit)
            _transport_counter(_ws_subscribers, room_id, 1)
            self._ws_send(
                {
                    "type": "subscribed",
                    "room_id": room_id,
                    "latest_id": room.latest_id,
                    "transport": "websocket",
                }
            )
            return

        if action == "unsubscribe":
            room_id = str(message.get("room_id", "")).strip()
            sub = subscriptions.pop(room_id, None)
            if sub is not None:
                sub.close()
                _transport_counter(_ws_subscribers, room_id, -1)
            self._ws_send({"type": "unsubscribed", "room_id": room_id})
            return

        action_map = {
            "room_post": handle_room_post,
            "intervention_list": handle_intervention_list,
            "intervention_approve": handle_intervention_approve,
            "intervention_reject": handle_intervention_reject,
            "status": handle_status,
        }
        handler = action_map.get(action)
        if handler is None:
            self._ws_send({"type": "error", "error": f"unknown websocket action: {action}", "action": action})
            return
        payload = {k: v for k, v in message.items() if k != "action"}
        try:
            result = handler(payload)
        except Exception as exc:
            self._ws_send({"type": "error", "error": str(exc), "action": action})
            return
        self._ws_send({"type": "result", "action": action, "result": result, "ok": not _looks_like_tool_error(result)})

    def _ws_flush_room_events(self, subscriptions: Dict[str, RoomSubscription]) -> None:
        for room_id, sub in list(subscriptions.items()):
            room = get_room(room_id)
            if room is None:
                sub.close()
                subscriptions.pop(room_id, None)
                _transport_counter(_ws_subscribers, room_id, -1)
                self._ws_send({"type": "room_closed", "room_id": room_id})
                continue
            try:
                items = sub.get(timeout=0.0, limit=100)
            except EOFError:
                subscriptions.pop(room_id, None)
                _transport_counter(_ws_subscribers, room_id, -1)
                continue
            for msg in items:
                self._ws_send({"type": "room_event", "event": _room_message_payload(room, msg)})

    def _ws_send(self, payload: Dict[str, Any]) -> None:
        frame = _ws_frame(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        self.wfile.write(frame)
        self.wfile.flush()

    def log_message(self, fmt: str, *args: Any) -> None:
        pass  # Quiet by default.


def run_server(host: str = "127.0.0.1", port: int = 3189, *, allow_remote: bool = False) -> None:
    validate_server_binding(host, allow_remote=allow_remote)
    _server_context["host"] = host
    _server_context["port"] = int(port)
    _server_context["allow_remote"] = bool(allow_remote)
    _restore_workstreams_from_service_state()
    server = ThreadingHTTPServer((host, port), MCPHandler)
    print(f"[tb2-server] listening on {host}:{port}/mcp")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
