"""Shared fixtures for tb2 tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tb2.backend import TerminalBackend
from tb2.broker import BrokerConfig
from tb2.room import Room, _rooms, _rooms_lock


@pytest.fixture
def mock_backend():
    """A MagicMock implementing TerminalBackend interface."""
    backend = MagicMock(spec=TerminalBackend)
    backend.capture_both.return_value = ([], [])
    backend.capture.return_value = []
    backend.has_session.return_value = True
    backend.init_session.return_value = ("test:0.0", "test:0.1")
    backend.list_panes.return_value = [("test:0.0", "agent-A"), ("test:0.1", "agent-B")]
    return backend


@pytest.fixture
def broker_config():
    """Default BrokerConfig for testing."""
    return BrokerConfig(target_a="test:0.0", target_b="test:0.1")


@pytest.fixture
def sample_room():
    """A Room pre-populated with 5 messages."""
    room = Room("test-room", max_messages=100)
    for i in range(5):
        room.post(author="user", text=f"message {i}", kind="chat")
    return room


@pytest.fixture(autouse=True)
def clean_room_registry():
    """Ensure room registry is clean between tests."""
    yield
    with _rooms_lock:
        _rooms.clear()
