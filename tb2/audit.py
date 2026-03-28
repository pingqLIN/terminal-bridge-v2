"""Minimal append-only audit trail for operator-facing TB2 events."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional


_FALSE_VALUES = {"", "0", "false", "no", "off"}
_MAX_RECENT_EVENTS = 200
_RECENT_SCAN_FACTOR = 20
_MIN_RECENT_SCAN = 400
_DEFAULT_MAX_BYTES = 5 * 1024 * 1024
_DEFAULT_MAX_FILES = 5
_DEFAULT_TEXT_MODE = "mask"
_FULL_TEXT_OPT_IN_ENV = "TB2_AUDIT_ALLOW_FULL_TEXT"
_TEXT_REDACTION_KEYS = ("edited_text", "guard_text", "text")
_TEXT_REDACTION_MODES = ("full", "mask", "drop")
AUDIT_EVENT_CATALOG = (
    "terminal.session_init",
    "terminal.sent",
    "room.created",
    "room.deleted",
    "room.cleaned_up",
    "room.message",
    "room.message_posted",
    "operator.room_post",
    "operator.interrupt",
    "bridge.start_existing",
    "bridge.start_conflict",
    "bridge.start_failed",
    "bridge.started",
    "bridge.stopped",
    "bridge.guard_blocked",
    "bridge.guard_rearmed",
    "intervention.submitted",
    "intervention.approved",
    "intervention.rejected",
)

_AUDIT_ROOM_MESSAGE_META_SCHEMA: Dict[str, Any] = {
    "bridge_id": True,
    "pending_id": True,
    "to_pane": True,
    "from_pane": True,
    "pane": True,
    "guard_reason": True,
    "guard_text": True,
}

_AUDIT_ROOM_MESSAGE_SCHEMA: Dict[str, Any] = {
    "event_id": True,
    "id": True,
    "room_id": True,
    "bridge_id": True,
    "author": True,
    "source": {
        "type": True,
        "role": True,
        "trusted": True,
    },
    "source_type": True,
    "source_role": True,
    "trusted": True,
    "text": True,
    "kind": True,
    "meta": _AUDIT_ROOM_MESSAGE_META_SCHEMA,
    "created_at": True,
    "ts": True,
}

_AUDIT_EVENT_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "terminal.session_init": {
        "session": True,
        "pane_a": True,
        "pane_b": True,
    },
    "terminal.sent": {
        "target": True,
        "text": True,
        "enter": True,
    },
    "room.created": {
        "room_id": True,
        "existing": True,
    },
    "room.deleted": {
        "room_id": True,
        "bridge_id": True,
        "payload": {
            "message_count": True,
            "last_active": True,
            "created_at": True,
        },
    },
    "room.cleaned_up": {
        "room_id": True,
        "bridge_id": True,
        "payload": {
            "message_count": True,
            "last_active": True,
            "created_at": True,
        },
    },
    "room.message": {
        "room_id": True,
        "message": _AUDIT_ROOM_MESSAGE_SCHEMA,
    },
    "room.message_posted": {
        "room_id": True,
        "bridge_id": True,
        "payload": {
            "id": True,
            "author": True,
            "text": True,
            "kind": True,
            "source_type": True,
            "source_role": True,
            "trusted": True,
            "meta": _AUDIT_ROOM_MESSAGE_META_SCHEMA,
            "created_at": True,
        },
    },
    "operator.room_post": {
        "room_id": True,
        "message_id": True,
        "author": True,
        "kind": True,
        "deliver": True,
        "deliver_error": True,
    },
    "operator.interrupt": {
        "bridge_id": True,
        "room_id": True,
        "target": True,
        "sent": [True],
        "errors": [{"pane": True, "error": True}],
    },
    "bridge.start_existing": {
        "bridge_id": True,
        "room_id": True,
        "pane_a": True,
        "pane_b": True,
        "reason": True,
    },
    "bridge.start_conflict": {
        "bridge_id": True,
        "room_id": True,
        "pane_a": True,
        "pane_b": True,
        "requested_room_id": True,
        "reason": True,
    },
    "bridge.start_failed": {
        "bridge_id": True,
        "room_id": True,
        "pane_a": True,
        "pane_b": True,
        "profile": True,
        "reason": True,
        "error": True,
    },
    "bridge.started": {
        "bridge_id": True,
        "room_id": True,
        "pane_a": True,
        "pane_b": True,
        "profile": True,
        "auto_forward": True,
        "intervention": True,
    },
    "bridge.stopped": {
        "bridge_id": True,
        "room_id": True,
    },
    "bridge.guard_blocked": {
        "bridge_id": True,
        "room_id": True,
        "from_pane": True,
        "to_pane": True,
        "reason": True,
        "text": True,
    },
    "bridge.guard_rearmed": {
        "bridge_id": True,
        "room_id": True,
    },
    "intervention.submitted": {
        "bridge_id": True,
        "room_id": True,
        "pending_id": True,
        "from_pane": True,
        "to_pane": True,
        "text": True,
        "action": True,
    },
    "intervention.approved": {
        "bridge_id": True,
        "room_id": True,
        "approved": True,
        "delivered": [{"id": True, "to_pane": True}],
        "errors": [{"id": True, "error": True}],
        "remaining": True,
    },
    "intervention.rejected": {
        "bridge_id": True,
        "room_id": True,
        "rejected": True,
        "remaining": True,
    },
}


def _state_root() -> Path:
    env_root = os.environ.get("TB2_STATE_DIR")
    if env_root:
        return Path(env_root).expanduser().resolve()

    if platform.system() == "Windows":
        local_app = os.environ.get("LOCALAPPDATA")
        if local_app:
            return Path(local_app) / "tb2"
        return Path.home() / "AppData" / "Local" / "tb2"

    xdg_state = os.environ.get("XDG_STATE_HOME")
    if xdg_state:
        return Path(xdg_state) / "tb2"

    if platform.system() == "Darwin":
        return _macos_state_root()

    return Path.home() / ".local" / "state" / "tb2"


def _macos_state_root() -> Path:
    root = Path.home() / "Library" / "Application Support" / "tb2"
    legacy = Path.home() / ".local" / "state" / "tb2"
    if _has_runtime_files(root):
        return root
    if _has_runtime_files(legacy):
        return legacy
    return root


def _has_runtime_files(root: Path) -> bool:
    return any((root / name).exists() for name in ("server.state.json", "server.log", "audit"))


def _runtime_dir(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        os.chmod(root, 0o700)


def _positive_int(raw: Optional[str], *, default: int, minimum: int) -> int:
    if raw is None or not str(raw).strip():
        return default
    try:
        value = int(str(raw).strip())
    except ValueError:
        return default
    if value < minimum:
        return default
    return value


def _text_mode(raw: Optional[str], *, default: str = _DEFAULT_TEXT_MODE) -> str:
    value = str(raw or "").strip().lower()
    if value in _TEXT_REDACTION_MODES:
        return value
    return default


def _flag_enabled(raw: Optional[str]) -> bool:
    value = str(raw or "").strip().lower()
    return bool(value) and value not in _FALSE_VALUES


def _text_summary(value: str, *, text_mode: str) -> Dict[str, Any]:
    return {
        "redacted": text_mode != "full",
        "mode": text_mode,
        "length": len(value),
        "lines": value.count("\n") + 1 if value else 0,
        "sha256": hashlib.sha256(value.encode("utf-8")).hexdigest()[:16],
    }


class AuditTrail:
    def __init__(
        self,
        root: Optional[Path] = None,
        *,
        max_bytes: int = _DEFAULT_MAX_BYTES,
        max_files: int = _DEFAULT_MAX_FILES,
        text_mode: str = _DEFAULT_TEXT_MODE,
        allow_full_text: bool = False,
    ):
        self.root = root.expanduser().resolve() if root else None
        self.file = self.root / "events.jsonl" if self.root else None
        self.max_bytes = max(max_bytes, 1024)
        self.max_files = max(max_files, 1)
        self.requested_text_mode = _text_mode(text_mode)
        self.raw_text_opt_in_acknowledged = bool(allow_full_text)
        self.text_mode = self.requested_text_mode
        if self.requested_text_mode == "full" and not self.raw_text_opt_in_acknowledged:
            self.text_mode = "mask"
        self._lock = threading.Lock()
        self._last_error = ""

    @classmethod
    def from_env(cls) -> "AuditTrail":
        env_root = os.environ.get("TB2_AUDIT_DIR")
        requested_text_mode = _text_mode(os.environ.get("TB2_AUDIT_TEXT_MODE"))
        allow_full_text = _flag_enabled(os.environ.get(_FULL_TEXT_OPT_IN_ENV))
        if env_root:
            return cls(
                Path(env_root),
                text_mode=requested_text_mode,
                allow_full_text=allow_full_text,
            )
        raw_enabled = os.environ.get("TB2_AUDIT", "")
        if raw_enabled.strip().lower() in _FALSE_VALUES:
            return cls()
        return cls(
            _state_root() / "audit",
            max_bytes=_positive_int(
                os.environ.get("TB2_AUDIT_MAX_BYTES"),
                default=_DEFAULT_MAX_BYTES,
                minimum=1024,
            ),
            max_files=_positive_int(
                os.environ.get("TB2_AUDIT_MAX_FILES"),
                default=_DEFAULT_MAX_FILES,
                minimum=1,
            ),
            text_mode=requested_text_mode,
            allow_full_text=allow_full_text,
        )

    def enabled(self) -> bool:
        return self.file is not None

    def describe(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled(),
            "root": str(self.root) if self.root else None,
            "file": str(self.file) if self.file else None,
            "max_bytes": self.max_bytes if self.enabled() else None,
            "max_files": self.max_files if self.enabled() else None,
            "redaction": {
                "mode": self.text_mode,
                "requested_mode": self.requested_text_mode,
                "keys": list(_TEXT_REDACTION_KEYS),
                "fields": list(_TEXT_REDACTION_KEYS),
                "stores_raw_text": self.text_mode == "full",
                "stores_masked_placeholders": self.text_mode == "mask",
                "stores_hash_fingerprint": True,
                "stores_text_metadata": True,
                "raw_text_opt_in_required": self.requested_text_mode == "full",
                "raw_text_opt_in_acknowledged": self.raw_text_opt_in_acknowledged,
                "raw_text_opt_in_blocked": self.requested_text_mode == "full" and not self.raw_text_opt_in_acknowledged,
                "raw_text_opt_in_env": _FULL_TEXT_OPT_IN_ENV,
            },
            "last_error": self._last_error or None,
        }

    def write(self, event: str, payload: Dict[str, Any]) -> bool:
        if not self.file or not event.strip():
            return False
        schema = _AUDIT_EVENT_SCHEMAS.get(event)
        entry = {
            "ts": time.time(),
            "event": event,
            **(
                _sanitize_event_payload(payload, schema=schema, text_mode=self.text_mode)
                if schema is not None
                else _sanitize_audit_value(payload, text_mode=self.text_mode)
            ),
        }
        try:
            text = json.dumps(entry, ensure_ascii=False, sort_keys=True)
            with self._lock:
                _runtime_dir(self.root)
                self._rotate_if_needed_locked(len(text.encode("utf-8")) + 1)
                with self.file.open("a", encoding="utf-8") as handle:
                    handle.write(text)
                    handle.write("\n")
                if os.name != "nt":
                    os.chmod(self.file, 0o600)
            self._last_error = ""
            return True
        except (OSError, TypeError, ValueError) as exc:
            self._last_error = str(exc)
            return False

    def recent(
        self,
        *,
        limit: int = 50,
        room_id: Optional[str] = None,
        bridge_id: Optional[str] = None,
        event: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if not self.file or not self.file.exists():
            return []

        cap = max(1, min(int(limit), _MAX_RECENT_EVENTS))
        scan = max(cap * _RECENT_SCAN_FACTOR, _MIN_RECENT_SCAN)
        with self._lock:
            items: List[Dict[str, Any]] = []
            for path in self._recent_paths_locked():
                with path.open("r", encoding="utf-8", errors="replace") as handle:
                    lines: Deque[str] = deque(handle, maxlen=scan)
                for raw in reversed(list(lines)):
                    text = raw.strip()
                    if not text:
                        continue
                    try:
                        item = json.loads(text)
                    except json.JSONDecodeError:
                        continue
                    if room_id and item.get("room_id") != room_id:
                        continue
                    if bridge_id and item.get("bridge_id") != bridge_id:
                        continue
                    if event and item.get("event") != event:
                        continue
                    items.append(item)
                    if len(items) >= cap:
                        items.reverse()
                        return items
        items.reverse()
        return items

    def _rotate_if_needed_locked(self, next_bytes: int) -> None:
        if not self.file or not self.file.exists():
            return
        if self.file.stat().st_size + next_bytes <= self.max_bytes:
            return
        self._rotate_locked()

    def _rotate_locked(self) -> None:
        if not self.file or not self.file.exists():
            return
        archive_count = max(self.max_files - 1, 0)
        if archive_count == 0:
            self.file.unlink()
            return
        oldest = self.file.with_name(self.file.name + f".{archive_count}")
        if oldest.exists():
            oldest.unlink()
        for idx in range(archive_count - 1, 0, -1):
            src = self.file.with_name(self.file.name + f".{idx}")
            dst = self.file.with_name(self.file.name + f".{idx + 1}")
            if src.exists():
                src.replace(dst)
        self.file.replace(self.file.with_name(self.file.name + ".1"))

    def _recent_paths_locked(self) -> List[Path]:
        if not self.file:
            return []
        paths: List[Path] = []
        if self.file.exists():
            paths.append(self.file)
        for idx in range(1, self.max_files):
            path = self.file.with_name(self.file.name + f".{idx}")
            if path.exists():
                paths.append(path)
        return paths


def _sanitize_audit_value(value: Any, *, text_mode: str) -> Any:
    if isinstance(value, dict):
        return _sanitize_audit_dict(value, text_mode=text_mode)
    if isinstance(value, list):
        return [_sanitize_audit_value(item, text_mode=text_mode) for item in value]
    return value


def _sanitize_event_payload(payload: Dict[str, Any], *, schema: Dict[str, Any], text_mode: str) -> Dict[str, Any]:
    sanitized: Dict[str, Any] = {}
    for key, subschema in schema.items():
        if key not in payload:
            continue
        value = payload[key]
        if key in _TEXT_REDACTION_KEYS and isinstance(value, str):
            sanitized.update(_sanitize_scalar_text(key, value, text_mode=text_mode))
            continue
        if subschema is True:
            sanitized[key] = _sanitize_audit_value(value, text_mode=text_mode)
            continue
        if isinstance(subschema, dict):
            if isinstance(value, dict):
                sanitized[key] = _sanitize_event_payload(value, schema=subschema, text_mode=text_mode)
            continue
        if isinstance(subschema, list) and len(subschema) == 1 and isinstance(value, list):
            item_schema = subschema[0]
            if item_schema is True:
                sanitized[key] = [_sanitize_audit_value(item, text_mode=text_mode) for item in value]
                continue
            if isinstance(item_schema, dict):
                sanitized[key] = [
                    _sanitize_event_payload(item, schema=item_schema, text_mode=text_mode)
                    for item in value
                    if isinstance(item, dict)
                ]
                continue
        sanitized[key] = _sanitize_audit_value(value, text_mode=text_mode)
    return sanitized


def _sanitize_append_payload(event: str, payload: Dict[str, Any], *, text_mode: str) -> Dict[str, Any]:
    schema = _AUDIT_EVENT_SCHEMAS.get(event)
    if schema is None:
        return _sanitize_audit_value(payload, text_mode=text_mode)
    payload_schema = schema.get("payload")
    if isinstance(payload_schema, dict):
        return _sanitize_event_payload(payload, schema=payload_schema, text_mode=text_mode)
    return _sanitize_audit_value(payload, text_mode=text_mode)


def _sanitize_audit_dict(payload: Dict[str, Any], *, text_mode: str) -> Dict[str, Any]:
    sanitized: Dict[str, Any] = {}
    for key, value in payload.items():
        if key in _TEXT_REDACTION_KEYS and isinstance(value, str):
            sanitized.update(_sanitize_scalar_text(key, value, text_mode=text_mode))
            continue
        sanitized[key] = _sanitize_audit_value(value, text_mode=text_mode)
    return sanitized


def _sanitize_scalar_text(key: str, value: str, *, text_mode: str) -> Dict[str, Any]:
    summary = _text_summary(value, text_mode=text_mode)
    return {
        key: value if text_mode == "full" else ("[redacted]" if text_mode == "mask" else None),
        f"{key}_redacted": summary["redacted"],
        f"{key}_length": summary["length"],
        f"{key}_lines": summary["lines"],
        f"{key}_mode": summary["mode"],
        f"{key}_sha256": summary["sha256"],
    }


def record_event(
    event: str,
    *,
    room_id: Optional[str] = None,
    bridge_id: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> bool:
    trail = AuditTrail.from_env()
    return trail.write(
        event,
        {
            "room_id": room_id,
            "bridge_id": bridge_id,
            "payload": payload or {},
        },
    )


def audit_log_path() -> Optional[str]:
    trail = AuditTrail.from_env()
    return str(trail.file) if trail.file else None


def append_audit_event(
    event: str,
    *,
    room_id: Optional[str] = None,
    bridge_id: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    trail = AuditTrail.from_env()
    clean_payload = _sanitize_append_payload(str(event), payload or {}, text_mode=trail.text_mode)
    entry: Dict[str, Any] = {
        "ts": time.time(),
        "event": str(event),
        "room_id": room_id,
        "bridge_id": bridge_id,
        "payload": clean_payload,
    }
    if trail.write(str(event), {"room_id": room_id, "bridge_id": bridge_id, "payload": payload or {}}):
        return entry
    return entry


def read_audit_events(
    *,
    limit: int = 120,
    room_id: str = "",
    bridge_id: str = "",
    event: str = "",
) -> List[Dict[str, Any]]:
    return AuditTrail.from_env().recent(
        limit=limit,
        room_id=room_id.strip() or None,
        bridge_id=bridge_id.strip() or None,
        event=event.strip() or None,
    )


def tail_events(
    *,
    limit: int = 120,
    room_id: str = "",
    bridge_id: str = "",
    event: str = "",
) -> List[Dict[str, Any]]:
    return read_audit_events(limit=limit, room_id=room_id, bridge_id=bridge_id, event=event)
