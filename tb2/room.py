"""Room-based messaging with bounded storage and cursor-based polling.

Replaces the unbounded list from MVP with a deque + binary search poll.
"""

from __future__ import annotations

import threading
import time
from bisect import bisect_right
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional


@dataclass
class RoomMessage:
    id: int
    author: str
    text: str
    kind: str = "chat"       # chat | terminal | system
    meta: Dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)


class Room:
    """Bounded message room with O(log n) cursor-based polling."""

    def __init__(self, room_id: str, *, max_messages: int = 2000):
        self.room_id = room_id
        self.max_messages = max_messages
        self.created_at = time.time()
        self.last_active = time.time()
        self._lock = threading.Lock()
        self._counter = 0
        self._messages: Deque[RoomMessage] = deque(maxlen=max_messages)
        self._ids: Deque[int] = deque(maxlen=max_messages)  # parallel id index

    def post(self, author: str, text: str, kind: str = "chat",
             meta: Optional[Dict[str, Any]] = None) -> RoomMessage:
        with self._lock:
            self._counter += 1
            msg = RoomMessage(
                id=self._counter,
                author=author,
                text=text,
                kind=kind,
                meta=meta or {},
            )
            self._messages.append(msg)
            self._ids.append(msg.id)
            self.last_active = time.time()
            return msg

    def poll(self, *, after_id: int = 0, limit: int = 50) -> List[RoomMessage]:
        """Return messages with id > after_id, up to *limit*.

        Uses binary search on the id index for O(log n) lookup.
        """
        with self._lock:
            if not self._ids:
                return []
            ids_list = list(self._ids)
            idx = bisect_right(ids_list, after_id)
            msgs = list(self._messages)
            return msgs[idx: idx + limit]

    @property
    def message_count(self) -> int:
        return len(self._messages)

    @property
    def latest_id(self) -> int:
        with self._lock:
            return self._counter


# ---------------------------------------------------------------------------
# Room registry with TTL cleanup
# ---------------------------------------------------------------------------

_rooms_lock = threading.Lock()
_rooms: Dict[str, Room] = {}


def create_room(room_id: Optional[str] = None, *, max_messages: int = 2000) -> Room:
    import uuid
    rid = room_id or uuid.uuid4().hex[:12]
    with _rooms_lock:
        if rid in _rooms:
            return _rooms[rid]
        room = Room(rid, max_messages=max_messages)
        _rooms[rid] = room
        return room


def get_room(room_id: str) -> Optional[Room]:
    with _rooms_lock:
        return _rooms.get(room_id)


def list_rooms() -> List[Room]:
    with _rooms_lock:
        return list(_rooms.values())


def cleanup_stale(ttl_seconds: float = 3600) -> int:
    """Remove rooms idle for longer than *ttl_seconds*. Returns count removed."""
    now = time.time()
    with _rooms_lock:
        stale = [rid for rid, r in _rooms.items() if now - r.last_active > ttl_seconds]
        for rid in stale:
            del _rooms[rid]
        return len(stale)


def delete_room(room_id: str) -> bool:
    with _rooms_lock:
        return _rooms.pop(room_id, None) is not None
