"""Minimal append-only audit trail for operator-facing TB2 events."""

from __future__ import annotations

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


class AuditTrail:
    def __init__(self, root: Optional[Path] = None):
        self.root = root.expanduser().resolve() if root else None
        self.file = self.root / "events.jsonl" if self.root else None
        self._lock = threading.Lock()
        self._last_error = ""

    @classmethod
    def from_env(cls) -> "AuditTrail":
        env_root = os.environ.get("TB2_AUDIT_DIR")
        if env_root:
            return cls(Path(env_root))
        raw_enabled = os.environ.get("TB2_AUDIT", "")
        if raw_enabled.strip().lower() in _FALSE_VALUES:
            return cls()
        return cls(_state_root() / "audit")

    def enabled(self) -> bool:
        return self.file is not None

    def describe(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled(),
            "root": str(self.root) if self.root else None,
            "file": str(self.file) if self.file else None,
            "last_error": self._last_error or None,
        }

    def write(self, event: str, payload: Dict[str, Any]) -> bool:
        if not self.file or not event.strip():
            return False
        entry = {
            "ts": time.time(),
            "event": event,
            **payload,
        }
        try:
            text = json.dumps(entry, ensure_ascii=False, sort_keys=True)
            with self._lock:
                _runtime_dir(self.root)
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
            with self.file.open("r", encoding="utf-8", errors="replace") as handle:
                lines: Deque[str] = deque(handle, maxlen=scan)

        items: List[Dict[str, Any]] = []
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
                break
        items.reverse()
        return items


def record_event(
    event: str,
    *,
    room_id: Optional[str] = None,
    bridge_id: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> bool:
    return _trail.write(
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
    entry: Dict[str, Any] = {
        "ts": time.time(),
        "event": str(event),
        "room_id": room_id,
        "bridge_id": bridge_id,
        "payload": payload or {},
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
