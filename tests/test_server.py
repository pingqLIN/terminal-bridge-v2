"""Tests for tb2.server — MCP handler functions."""

import json
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

    @patch.object(server_mod, "_make_backend")
    def test_room_post_rejects_cross_room_delivery(self, mock_factory):
        mock_backend = MagicMock()
        mock_backend.capture_both.return_value = ([], [])
        mock_factory.return_value = mock_backend

        create_room("room-a")
        create_room("room-b")
        server_mod.handle_bridge_start({
            "pane_a": "test:a",
            "pane_b": "test:b",
            "room_id": "room-a",
            "bridge_id": "br-room",
        })

        result = server_mod.handle_room_post({
            "room_id": "room-b",
            "author": "user",
            "text": "hello",
            "deliver": "a",
            "bridge_id": "br-room",
        })
        assert result["deliver_error"] == "bridge br-room belongs to room room-a, not room-b"
        mock_backend.send.assert_not_called()

        server_mod.handle_bridge_stop({"bridge_id": "br-room"})

    @patch.object(server_mod, "_make_backend")
    def test_room_post_rejects_invalid_deliver_target(self, mock_factory):
        mock_backend = MagicMock()
        mock_backend.capture_both.return_value = ([], [])
        mock_factory.return_value = mock_backend

        create_room("post-invalid")
        server_mod.handle_bridge_start({
            "pane_a": "test:a",
            "pane_b": "test:b",
            "room_id": "post-invalid",
            "bridge_id": "br-invalid",
        })
        result = server_mod.handle_room_post({
            "room_id": "post-invalid",
            "author": "user",
            "text": "hello",
            "deliver": "sideways",
            "bridge_id": "br-invalid",
        })
        assert result["deliver_error"] == "deliver must be one of: a, b, both"

        server_mod.handle_bridge_stop({"bridge_id": "br-invalid"})


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

    @patch("tb2.server.doctor_report")
    def test_doctor(self, mock_doctor):
        mock_doctor.return_value = {"platform": "Windows", "recommended_backend": "process"}
        result = server_mod.handle_doctor({"distro": "Ubuntu"})
        assert result["platform"] == "Windows"
        mock_doctor.assert_called_once_with(distro="Ubuntu")


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

    @patch.object(server_mod, "_make_backend")
    def test_bridge_start_honors_requested_room_id(self, mock_factory):
        mock_backend = MagicMock()
        mock_backend.capture_both.return_value = ([], [])
        mock_factory.return_value = mock_backend

        result = server_mod.handle_bridge_start({
            "pane_a": "test:a",
            "pane_b": "test:b",
            "room_id": "wanted-room",
            "bridge_id": "br-room-id",
        })
        assert result["room_id"] == "wanted-room"
        assert get_room("wanted-room") is not None

        server_mod.handle_bridge_stop({"bridge_id": "br-room-id"})

    @patch.object(server_mod, "_make_backend")
    def test_bridge_start_same_panes_is_idempotent(self, mock_factory):
        mock_backend = MagicMock()
        mock_backend.capture_both.return_value = ([], [])
        mock_factory.return_value = mock_backend

        first = server_mod.handle_bridge_start({
            "pane_a": "test:a",
            "pane_b": "test:b",
            "room_id": "same-room",
            "bridge_id": "br-first",
        })
        second = server_mod.handle_bridge_start({
            "pane_a": "test:a",
            "pane_b": "test:b",
            "room_id": "same-room",
        })
        assert second["existing"] is True
        assert second["bridge_id"] == first["bridge_id"]
        with server_mod._bridges_lock:
            assert len(server_mod._bridges) == 1

        server_mod.handle_bridge_stop({"bridge_id": "br-first"})

    @patch.object(server_mod, "_make_backend")
    def test_bridge_start_same_panes_conflicting_room_errors(self, mock_factory):
        mock_backend = MagicMock()
        mock_backend.capture_both.return_value = ([], [])
        mock_factory.return_value = mock_backend

        server_mod.handle_bridge_start({
            "pane_a": "test:a",
            "pane_b": "test:b",
            "room_id": "room-a",
            "bridge_id": "br-conflict",
        })
        result = server_mod.handle_bridge_start({
            "pane_a": "test:a",
            "pane_b": "test:b",
            "room_id": "room-b",
        })
        assert "pane pair already bridged" in result["error"]

        server_mod.handle_bridge_stop({"bridge_id": "br-conflict"})

    @patch.object(server_mod, "_make_backend")
    def test_bridge_start_preflight_failure_returns_error(self, mock_factory):
        mock_backend = MagicMock()
        mock_backend.capture_both.side_effect = RuntimeError("capture failed")
        mock_factory.return_value = mock_backend

        result = server_mod.handle_bridge_start({
            "pane_a": "test:a",
            "pane_b": "test:b",
            "room_id": "broken-room",
        })
        assert result["error"] == "bridge preflight failed: capture failed"

    def test_bridge_process_new_lines_deduplicates_forwarded_messages(self):
        backend = MagicMock()
        room = create_room("bridge-dedupe")
        bridge = server_mod.Bridge(
            bridge_id="br-dedupe",
            backend=backend,
            room=room,
            pane_a="test:a",
            pane_b="test:b",
            auto_forward=True,
        )

        profile = server_mod.get_profile("generic")
        bridge._process_new_lines(
            "A",
            "test:a",
            "test:b",
            [
                "C:\\work>echo MSG:echo HELLO",
                "MSG:echo HELLO",
            ],
            profile,
        )

        backend.send.assert_called_once_with("test:b", "echo HELLO", enter=True)


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

    @patch.object(server_mod, "_make_backend")
    def test_intervention_approve_supports_edited_text(self, mock_factory):
        mock_backend = MagicMock()
        mock_backend.capture_both.return_value = ([], [])
        mock_factory.return_value = mock_backend

        create_room("int-edit")
        server_mod.handle_bridge_start({
            "pane_a": "t:a",
            "pane_b": "t:b",
            "room_id": "int-edit",
            "bridge_id": "br-edit",
            "intervention": True,
            "auto_forward": True,
        })
        bridge = server_mod._get_bridge("br-edit")
        pending = bridge.intervention_layer.submit("t:a", "t:b", "echo OLD")

        result = server_mod.handle_intervention_approve({
            "bridge_id": "br-edit",
            "id": pending.id,
            "edited_text": "echo NEW",
        })

        assert result["approved"] == 1
        mock_backend.send.assert_called_with("t:b", "echo NEW", enter=True)

        server_mod.handle_bridge_stop({"bridge_id": "br-edit"})


class TestMCPProtocol:
    def _rpc(self, req):
        handler = server_mod.MCPHandler.__new__(server_mod.MCPHandler)
        return handler._handle_rpc(req)

    def test_initialize(self):
        result = self._rpc({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-05",
                "capabilities": {},
                "clientInfo": {"name": "pytest", "version": "1.0"},
            },
        })
        assert result["result"]["serverInfo"]["name"] == "terminal-bridge-v2"
        assert result["result"]["protocolVersion"] == "2025-11-05"

    def test_initialize_echoes_client_protocol(self):
        result = self._rpc({
            "jsonrpc": "2.0",
            "id": 9,
            "method": "initialize",
            "params": {"protocolVersion": "2025-11-25"},
        })
        assert result["result"]["protocolVersion"] == "2025-11-25"

    def test_ping(self):
        result = self._rpc({"jsonrpc": "2.0", "id": 2, "method": "ping", "params": {}})
        assert result["result"] == {}

    def test_notifications_initialized_is_ignored_without_id(self):
        result = self._rpc({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        assert result is None

    def test_tools_list_has_mcp_shape(self):
        result = self._rpc({"jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {}})
        tools = result["result"]["tools"]
        assert isinstance(tools, list)
        assert tools
        tool0 = tools[0]
        assert "name" in tool0
        assert "description" in tool0
        assert "inputSchema" in tool0

    def test_tools_call_returns_mcp_content_shape(self):
        result = self._rpc({
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {"name": "list_profiles", "arguments": {}},
        })
        tool_result = result["result"]
        assert "content" in tool_result
        assert isinstance(tool_result["content"], list)
        assert tool_result["content"]
        assert tool_result["content"][0]["type"] == "text"
        assert "structuredContent" in tool_result
        assert "profiles" in tool_result["structuredContent"]
        assert tool_result.get("isError") is not True

    def test_tools_call_doctor_returns_report(self):
        result = self._rpc({
            "jsonrpc": "2.0",
            "id": 14,
            "method": "tools/call",
            "params": {"name": "doctor", "arguments": {}},
        })
        tool_result = result["result"]["structuredContent"]
        assert "backends" in tool_result
        assert "clients" in tool_result

    def test_tools_call_unknown_tool_uses_is_error(self):
        result = self._rpc({
            "jsonrpc": "2.0",
            "id": 11,
            "method": "tools/call",
            "params": {"name": "missing_tool", "arguments": {}},
        })
        tool_result = result["result"]
        assert tool_result["isError"] is True
        assert "unknown tool" in tool_result["structuredContent"]["error"]

    def test_tools_call_handler_error_payload_sets_is_error(self):
        result = self._rpc({
            "jsonrpc": "2.0",
            "id": 12,
            "method": "tools/call",
            "params": {"name": "bridge_stop", "arguments": {"bridge_id": "nope"}},
        })
        tool_result = result["result"]
        assert tool_result["isError"] is True
        assert tool_result["structuredContent"]["error"] == "bridge not found"

    def test_tools_call_rejects_non_object_arguments(self):
        result = self._rpc({
            "jsonrpc": "2.0",
            "id": 13,
            "method": "tools/call",
            "params": {"name": "status", "arguments": []},
        })
        assert result["error"]["code"] == -32602

    def test_unknown_notification_is_ignored(self):
        result = self._rpc({"jsonrpc": "2.0", "method": "notifications/custom", "params": {}})
        assert result is None


class TestGuiRouting:
    def test_gui_html_has_endpoint(self):
        html = server_mod.build_gui_html("/mcp")
        assert "Host, Guest, and Human operator workflow" in html
        assert "MCP /mcp" in html

    def test_get_root_returns_html(self):
        code, content_type, body = server_mod._handle_get_path("/")
        assert code == 200
        assert content_type.startswith("text/html")
        assert b"Host, Guest, and Human operator workflow" in body

    def test_get_mcp_returns_json(self):
        code, content_type, body = server_mod._handle_get_path("/mcp")
        assert code == 200
        assert content_type == "application/json"
        payload = json.loads(body.decode("utf-8"))
        assert payload["ok"] is True
        assert payload["endpoint"] == "/mcp"

    def test_get_unknown_path(self):
        code, content_type, body = server_mod._handle_get_path("/missing")
        assert code == 404
        assert content_type == "application/json"
        payload = json.loads(body.decode("utf-8"))
        assert payload["error"] == "not found"
