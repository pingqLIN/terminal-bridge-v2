"""Tests for tb2.server — MCP handler functions."""

from unittest.mock import MagicMock, patch

import pytest

import tb2.server as server_mod
from tb2.room import create_room, get_room


@pytest.fixture(autouse=True)
def clean_server_state():
    """Clean server-level registries between tests."""
    yield
    with server_mod._bridges_lock:
        for b in server_mod._bridges.values():
            b.stop.set()
        server_mod._bridges.clear()
    with server_mod._backend_cache_lock:
        server_mod._backend_cache.clear()


class TestMakeBackend:
    def test_tmux_default(self):
        from tb2.backend import TmuxBackend
        b = server_mod._make_backend({"backend": "tmux"})
        assert isinstance(b, TmuxBackend)

    def test_process_backend(self):
        from tb2.process_backend import ProcessBackend
        b = server_mod._make_backend({"backend": "process"})
        assert isinstance(b, ProcessBackend)

    def test_pipe_backend(self):
        from tb2.pipe_backend import PipeBackend
        b = server_mod._make_backend({"backend": "pipe"})
        assert isinstance(b, PipeBackend)

    def test_caching(self):
        b1 = server_mod._make_backend({"backend": "tmux", "backend_id": "cached"})
        b2 = server_mod._make_backend({"backend": "tmux", "backend_id": "cached"})
        assert b1 is b2

    def test_different_ids(self):
        b1 = server_mod._make_backend({"backend": "tmux", "backend_id": "a"})
        b2 = server_mod._make_backend({"backend": "tmux", "backend_id": "b"})
        assert b1 is not b2


class TestRoomHandlers:
    def test_room_create(self):
        result = server_mod.handle_room_create({"room_id": "test-r"})
        assert result["room_id"] == "test-r"
        assert get_room("test-r") is not None

    def test_room_poll(self):
        room = create_room("poll-test")
        room.post(author="a", text="hello")
        result = server_mod.handle_room_poll({"room_id": "poll-test", "after_id": 0})
        assert len(result["messages"]) == 1
        assert result["messages"][0]["text"] == "hello"

    def test_room_poll_not_found(self):
        result = server_mod.handle_room_poll({"room_id": "nope"})
        assert "error" in result

    def test_room_poll_invalid_params(self):
        create_room("bad-params")
        result = server_mod.handle_room_poll({"room_id": "bad-params", "after_id": "abc"})
        assert "error" in result

    def test_room_post(self):
        create_room("post-test")
        result = server_mod.handle_room_post({
            "room_id": "post-test",
            "author": "user",
            "text": "hello",
        })
        assert "id" in result

    def test_room_post_not_found(self):
        result = server_mod.handle_room_post({"room_id": "nope", "text": "hello"})
        assert "error" in result


class TestTerminalHandlers:
    @patch.object(server_mod, "_make_backend")
    def test_terminal_init(self, mock_factory):
        mock_backend = MagicMock()
        mock_backend.init_session.return_value = ("sess:0.0", "sess:0.1")
        mock_factory.return_value = mock_backend

        result = server_mod.handle_terminal_init({"session": "sess"})
        assert result["pane_a"] == "sess:0.0"
        assert result["pane_b"] == "sess:0.1"

    @patch.object(server_mod, "_make_backend")
    def test_terminal_capture(self, mock_factory):
        mock_backend = MagicMock()
        mock_backend.capture.return_value = ["line1", "line2"]
        mock_factory.return_value = mock_backend

        result = server_mod.handle_terminal_capture({"target": "test:0.0"})
        assert result["count"] == 2

    @patch.object(server_mod, "_make_backend")
    def test_terminal_send(self, mock_factory):
        mock_backend = MagicMock()
        mock_factory.return_value = mock_backend

        result = server_mod.handle_terminal_send({
            "target": "test:0.0",
            "text": "echo hello",
            "enter": True,
        })
        assert result["ok"] is True
        mock_backend.send.assert_called_once_with("test:0.0", "echo hello", enter=True)


class TestProfileHandlers:
    def test_list_profiles(self):
        result = server_mod.handle_list_profiles({})
        assert "generic" in result["profiles"]
        assert "codex" in result["profiles"]


class TestStatusHandler:
    def test_status(self):
        create_room("status-test")
        result = server_mod.handle_status({})
        assert "rooms" in result
        assert "bridges" in result
        room_ids = [r["id"] for r in result["rooms"]]
        assert "status-test" in room_ids


class TestBridgeHandlers:
    @patch.object(server_mod, "_make_backend")
    def test_bridge_start_stop(self, mock_factory):
        mock_backend = MagicMock()
        mock_backend.capture_both.return_value = ([], [])
        mock_factory.return_value = mock_backend

        room = create_room("bridge-test")
        result = server_mod.handle_bridge_start({
            "pane_a": "test:a",
            "pane_b": "test:b",
            "room_id": "bridge-test",
            "bridge_id": "br1",
        })
        assert result["bridge_id"] == "br1"

        stop_result = server_mod.handle_bridge_stop({"bridge_id": "br1"})
        assert stop_result["ok"] is True

    def test_bridge_stop_not_found(self):
        result = server_mod.handle_bridge_stop({"bridge_id": "nope"})
        assert "error" in result


class TestInterventionHandlers:
    @patch.object(server_mod, "_make_backend")
    def test_intervention_list(self, mock_factory):
        mock_backend = MagicMock()
        mock_backend.capture_both.return_value = ([], [])
        mock_factory.return_value = mock_backend

        create_room("int-test")
        server_mod.handle_bridge_start({
            "pane_a": "t:a", "pane_b": "t:b",
            "room_id": "int-test", "bridge_id": "br-int",
            "intervention": True,
        })

        result = server_mod.handle_intervention_list({"bridge_id": "br-int"})
        assert result["count"] == 0

        # Clean up
        server_mod.handle_bridge_stop({"bridge_id": "br-int"})

    def test_intervention_list_not_found(self):
        result = server_mod.handle_intervention_list({"bridge_id": "nope"})
        assert "error" in result

    def test_intervention_approve_not_found(self):
        result = server_mod.handle_intervention_approve({"bridge_id": "nope"})
        assert "error" in result

    def test_intervention_reject_not_found(self):
        result = server_mod.handle_intervention_reject({"bridge_id": "nope"})
        assert "error" in result

    def test_terminal_interrupt_not_found(self):
        result = server_mod.handle_terminal_interrupt({"bridge_id": "nope"})
        assert "error" in result
