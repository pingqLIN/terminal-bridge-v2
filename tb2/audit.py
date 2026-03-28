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
    ):
        self.root = root.expanduser().resolve() if root else None
        self.file = self.root / "events.jsonl" if self.root else None
        self.max_bytes = max(max_bytes, 1024)
        self.max_files = max(max_files, 1)
        self.text_mode = _text_mode(text_mode)
        self._lock = threading.Lock()
        self._last_error = ""

    @classmethod
    def from_env(cls) -> "AuditTrail":
        env_root = os.environ.get("TB2_AUDIT_DIR")
        if env_root:
            return cls(Path(env_root), text_mode=_text_mode(os.environ.get("TB2_AUDIT_TEXT_MODE")))
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
            text_mode=_text_mode(os.environ.get("TB2_AUDIT_TEXT_MODE")),
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
                "keys": list(_TEXT_REDACTION_KEYS),
                "fields": list(_TEXT_REDACTION_KEYS),
                "stores_raw_text": self.text_mode == "full",
                "stores_masked_placeholders": self.text_mode == "mask",
                "stores_hash_fingerprint": True,
                "stores_text_metadata": True,
            },
            "last_error": self._last_error or None,
        }

    def write(self, event: str, payload: Dict[str, Any]) -> bool:
        if not self.file or not event.strip():
            return False
        entry = {
            "ts": time.time(),
            "event": event,
            **_sanitize_audit_value(payload, text_mode=self.text_mode),
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


def _sanitize_audit_dict(payload: Dict[str, Any], *, text_mode: str) -> Dict[str, Any]:
    sanitized: Dict[str, Any] = {}
    for key, value in payload.items():
        if key in _TEXT_REDACTION_KEYS and isinstance(value, str):
            summary = _text_summary(value, text_mode=text_mode)
            sanitized[key] = value if text_mode == "full" else ("[redacted]" if text_mode == "mask" else None)
            sanitized[f"{key}_redacted"] = summary["redacted"]
            sanitized[f"{key}_length"] = summary["length"]
            sanitized[f"{key}_lines"] = summary["lines"]
            sanitized[f"{key}_mode"] = summary["mode"]
            sanitized[f"{key}_sha256"] = summary["sha256"]
            continue
        sanitized[key] = _sanitize_audit_value(value, text_mode=text_mode)
    return sanitized


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
    clean_payload = _sanitize_audit_value(payload or {}, text_mode=trail.text_mode)
    entry: Dict[str, Any] = {
        "ts": time.time(),
        "event": str(event),
        "room_id": room_id,
        "bridge_id": bridge_id,
        "payload": clean_payload,
    }
    if trail.write(str(event), {"room_id": room_id, "bridge_id": bridge_id, "payload": clean_payload}):
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
