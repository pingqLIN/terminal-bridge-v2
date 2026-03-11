"""Human intervention layer.

Provides a pending-forward queue so auto-forwarded messages can be
reviewed, edited, or cancelled before delivery.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Deque, Dict, List, Optional


class Action(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    EDITED = "edited"
    REJECTED = "rejected"
    AUTO = "auto"  # bypass queue (when intervention is off)


@dataclass
class PendingMessage:
    id: int
    from_pane: str
    to_pane: str
    text: str
    action: Action = Action.PENDING
    edited_text: Optional[str] = None
    created_at: float = field(default_factory=time.time)


class InterventionLayer:
    """Queue for human review of auto-forwarded messages.

    When *active*, messages go into pending queue.
    When *inactive*, messages pass through immediately (Action.AUTO).
    """

    def __init__(self, *, active: bool = False):
        self.active = active
        self._lock = threading.Lock()
        self._counter = 0
        self._pending: Deque[PendingMessage] = deque(maxlen=200)
        self._history: Deque[PendingMessage] = deque(maxlen=500)

    def submit(self, from_pane: str, to_pane: str, text: str) -> PendingMessage:
        """Submit a message for review (or auto-pass if intervention inactive)."""
        with self._lock:
            self._counter += 1
            msg = PendingMessage(
                id=self._counter,
                from_pane=from_pane,
                to_pane=to_pane,
                text=text,
                action=Action.PENDING if self.active else Action.AUTO,
            )
            if self.active:
                self._pending.append(msg)
            else:
                self._history.append(msg)
            return msg

    def list_pending(self) -> List[PendingMessage]:
        with self._lock:
            return [m for m in self._pending if m.action == Action.PENDING]

    def approve(self, msg_id: int, edited_text: Optional[str] = None) -> Optional[PendingMessage]:
        return self._resolve(msg_id, Action.APPROVED, edited_text=edited_text)

    def reject(self, msg_id: int) -> Optional[PendingMessage]:
        return self._resolve(msg_id, Action.REJECTED)

    def edit(self, msg_id: int, new_text: str) -> Optional[PendingMessage]:
        with self._lock:
            for msg in self._pending:
                if msg.id == msg_id and msg.action == Action.PENDING:
                    msg.action = Action.EDITED
                    msg.edited_text = new_text
                    self._pending.remove(msg)
                    self._history.append(msg)
                    return msg
        return None

    def approve_all(self) -> List[PendingMessage]:
        with self._lock:
            approved = []
            while self._pending:
                msg = self._pending.popleft()
                if msg.action == Action.PENDING:
                    msg.action = Action.APPROVED
                    approved.append(msg)
                self._history.append(msg)
            return approved

    def reject_all(self) -> int:
        with self._lock:
            count = 0
            while self._pending:
                msg = self._pending.popleft()
                if msg.action == Action.PENDING:
                    msg.action = Action.REJECTED
                    count += 1
                self._history.append(msg)
            return count

    def pause(self) -> None:
        self.active = True

    def resume(self) -> None:
        self.active = False

    def _resolve(
        self,
        msg_id: int,
        action: Action,
        *,
        edited_text: Optional[str] = None,
    ) -> Optional[PendingMessage]:
        with self._lock:
            for msg in self._pending:
                if msg.id == msg_id and msg.action == Action.PENDING:
                    if edited_text is not None:
                        msg.action = Action.EDITED
                        msg.edited_text = edited_text
                    else:
                        msg.action = action
                    self._pending.remove(msg)
                    self._history.append(msg)
                    return msg
        return None
