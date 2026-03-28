"""Room-based messaging with bounded storage and cursor-based polling.

Replaces the unbounded list from MVP with a deque + binary search poll.
"""

from __future__ import annotations

import threading
import time
from bisect import bisect_right
from collections import deque
from dataclasses import dataclass, field
import re
from typing import Any, Deque, Dict, List, Optional

from .audit import record_event

_ROOM_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def validate_room_id(room_id: str) -> str:
    rid = str(room_id).strip()
    if not _ROOM_ID_RE.fullmatch(rid):
        raise ValueError("invalid room_id")
    return rid


@dataclass
class RoomMessage:
    id: int
    author: str
    text: str
    kind: str = "chat"       # chat | terminal | system
    source_type: str = "client"
    source_role: str = "external"
    trusted: bool = False
    meta: Dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)


class RoomSubscription:
    """Cursor-aware live subscription for a room."""

    def __init__(self, room: "Room", sub_id: int, queue: Deque[RoomMessage]):
        self._room = room
        self._sub_id = sub_id
        self._queue = queue
        self._closed = False

    def get(self, *, timeout: Optional[float] = None, limit: int = 100) -> List[RoomMessage]:
        with self._room._cv:
            if self._closed or self._room._closed:
                raise EOFError("subscription closed")

            deadline = None if timeout is None else (time.time() + max(0.0, timeout))
            while not self._queue:
                if self._closed or self._room._closed:
                    raise EOFError("subscription closed")
                if deadline is not None:
                    remaining = deadline - time.time()
                    if remaining <= 0:
                        return []
                    self._room._cv.wait(remaining)
                else:
                    self._room._cv.wait()

            items: List[RoomMessage] = []
            while self._queue and len(items) < limit:
                items.append(self._queue.popleft())
            self._room.last_active = time.time()
            return items

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._room._remove_subscription(self._sub_id)


class Room:
    """Bounded message room with O(log n) cursor-based polling."""

    def __init__(self, room_id: str, *, max_messages: int = 2000):
        self.room_id = room_id
        self.max_messages = max_messages
        self.created_at = time.time()
        self.last_active = time.time()
        self._lock = threading.Lock()
        self._cv = threading.Condition(self._lock)
        self._counter = 0
        self._messages: Deque[RoomMessage] = deque(maxlen=max_messages)
        self._ids: Deque[int] = deque(maxlen=max_messages)  # parallel id index
        self._subscriptions: Dict[int, Deque[RoomMessage]] = {}
        self._subscription_counter = 0
        self._closed = False

    def post(
        self,
        author: str,
        text: str,
        kind: str = "chat",
        meta: Optional[Dict[str, Any]] = None,
        *,
        source_type: str = "client",
        source_role: str = "external",
        trusted: bool = False,
    ) -> RoomMessage:
        with self._cv:
            self._counter += 1
            msg = RoomMessage(
                id=self._counter,
                author=author,
                text=text,
                kind=kind,
                source_type=source_type,
                source_role=source_role,
                trusted=trusted,
                meta=meta or {},
            )
            self._messages.append(msg)
            self._ids.append(msg.id)
            for queue in self._subscriptions.values():
                queue.append(msg)
            self.last_active = time.time()
            self._cv.notify_all()
            record_event(
                "room.message_posted",
                room_id=self.room_id,
                bridge_id=str(msg.meta.get("bridge_id", "")).strip() or None,
                payload={
                    "id": msg.id,
                    "author": msg.author,
                    "text": msg.text,
                    "kind": msg.kind,
                    "source_type": msg.source_type,
                    "source_role": msg.source_role,
                    "trusted": msg.trusted,
                    "meta": dict(msg.meta),
                    "created_at": msg.ts,
                },
            )
            return msg

    def poll(self, *, after_id: int = 0, limit: int = 50) -> List[RoomMessage]:
        """Return messages with id > after_id, up to *limit*.

        Uses binary search on the id index for O(log n) lookup.
        """
        with self._lock:
            msgs = self._poll_locked(after_id=after_id, limit=limit)
            self.last_active = time.time()
            return msgs

    def subscribe(
        self,
        *,
        after_id: int = 0,
        backlog_limit: int = 200,
        max_queue: int = 400,
    ) -> RoomSubscription:
        with self._cv:
            if self._closed:
                raise RuntimeError("room closed")
            self._subscription_counter += 1
            sub_id = self._subscription_counter
            queue: Deque[RoomMessage] = deque(maxlen=max_queue)
            for msg in self._poll_locked(after_id=after_id, limit=backlog_limit):
                queue.append(msg)
            self._subscriptions[sub_id] = queue
            self.last_active = time.time()
            return RoomSubscription(self, sub_id, queue)

    def close(self) -> None:
        with self._cv:
            self._closed = True
            self._subscriptions.clear()
            self._cv.notify_all()

    @property
    def message_count(self) -> int:
        return len(self._messages)

    @property
    def latest_id(self) -> int:
        with self._lock:
            return self._counter

    @property
    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subscriptions)

    def _poll_locked(self, *, after_id: int, limit: int) -> List[RoomMessage]:
        if not self._ids:
            return []
        ids_list = list(self._ids)
        idx = bisect_right(ids_list, after_id)
        msgs = list(self._messages)
        return msgs[idx: idx + limit]

    def _remove_subscription(self, sub_id: int) -> None:
        with self._cv:
            self._subscriptions.pop(sub_id, None)
            self._cv.notify_all()


# ---------------------------------------------------------------------------
# Room registry with TTL cleanup
# ---------------------------------------------------------------------------

_rooms_lock = threading.Lock()
_rooms: Dict[str, Room] = {}


def create_room(room_id: Optional[str] = None, *, max_messages: int = 2000) -> Room:
    import uuid
    rid = validate_room_id(room_id) if room_id else uuid.uuid4().hex[:12]
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
            _rooms.pop(rid).close()
        return len(stale)


def delete_room(room_id: str) -> bool:
    with _rooms_lock:
        room = _rooms.pop(room_id, None)
    if room is None:
        return False
    room.close()
    return True
