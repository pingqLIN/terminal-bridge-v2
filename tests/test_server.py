"""Tests for tb2.server — MCP handler functions."""

import io
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import threading
from unittest.mock import MagicMock, patch
import urllib.request

import pytest

import tb2.server as server_mod
from tb2.audit import AuditTrail
from tb2.room import create_room, get_room, list_rooms


def _extract_gui_function(html: str, name: str) -> str:
    marker = f"function {name}("
    start = html.find(marker)
    if start < 0:
        raise AssertionError(f"missing gui function: {name}")
    body_start = html.find("{", start)
    if body_start < 0:
        raise AssertionError(f"missing gui function body: {name}")
    depth = 0
    for idx in range(body_start, len(html)):
        char = html[idx]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return html[start : idx + 1]
    raise AssertionError(f"unterminated gui function: {name}")


def _run_gui_function(html: str, name: str, expression: str):
    function_src = _extract_gui_function(html, name)
    script = """
const messages = {
  'cards.auditEnabled': 'Audit trail is writing to {file}.',
  'cards.auditDisabled': 'Audit trail is disabled.',
  'cards.auditRedaction': 'Persisted text fields are redacted ({mode}).',
  'cards.auditRedactionRequested': 'Requested redaction mode is {requested}; effective mode is {mode}.',
  'cards.auditRedactionFullWarning': 'Warning: full mode stores raw text in durable audit entries.',
  'cards.auditRedactionFullBlocked': 'Full mode was requested but is blocked until {env}=1 is set.',
  'cards.auditError': 'Audit trail error: {error}',
  'cards.auditScope': 'Scope: {scope} · event: {event} · limit: {limit}',
  'cards.auditDestinationFallback': 'configured destination',
  'cards.statusBadgeGuarded': 'Guard blocked',
  'cards.statusBadgeReady': 'Bridge ready',
  'cards.statusBadgePending': 'Pending {count}',
  'cards.statusBadgeTransport': 'Subs {total} (sse {sse} / ws {websocket})',
  'cards.statusBadgeTransportIdle': 'Subscribers idle',
  'cards.statusBadgeAuditOn': 'Audit on',
  'cards.statusBadgeAuditOff': 'Audit off',
  'cards.statusBadgeAuditRaw': 'Audit raw text',
  'cards.statusBadgeAuditRawBlocked': 'Audit raw blocked',
  'cards.statusBadgeSecurity': 'Security {tier}',
  'cards.statusBadgeHealth': 'Health {state}',
  'cards.statusBadgeEscalation': 'Escalation {mode}',
  'cards.statusBadgeGovernance': 'Governance {name}',
  'cards.statusBadgeReviewMode': 'Review {mode}',
  'cards.statusBadgeBackend': 'Preferred backend {backend}',
  'cards.governanceSummary': 'Governance {layers}',
  'cards.governanceSummaryEmpty': 'No governance layers matched.',
  'fleet.healthOk': 'healthy',
  'fleet.healthWarn': 'warn',
  'fleet.healthCritical': 'critical',
  'fleet.escalateReview': 'review',
  'fleet.escalateIntervene': 'intervene'
};
function t(path) {
  return messages[path] || path;
}
function format(path, values) {
  return t(path).replace(/\\{(\\w+)\\}/g, (_, key) => String((values && values[key]) ?? ''));
}
function governancePrimaryName() {
  return '';
}
function governanceEffective() {
  return '';
}
""" + function_src + "\nconst result = " + expression + ";\nconsole.log(JSON.stringify(result));\n"
    done = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(done.stdout)


@pytest.fixture(autouse=True)
def clean_server_state():
    """Clean server-level registries between tests."""
    yield
    with server_mod._bridges_lock:
        for b in server_mod._bridges.values():
            b.stop.set()
        server_mod._bridges.clear()
    with server_mod._sidepanel_lock:
        for item in server_mod._sidepanel_rooms.values():
            proc = item.process
            if proc is None:
                continue
            try:
                if proc.poll() is None:
                    proc.terminate()
            except Exception:
                pass
        server_mod._sidepanel_rooms.clear()
        server_mod._sidepanel_probe_cache.update({"checked_at": 0.0, "detail": "", "ok": None})
    with server_mod._workstreams_lock:
        server_mod._workstreams.clear()
    with server_mod._backend_cache_lock:
        server_mod._backend_cache.clear()


class TestMakeBackend:
    @patch("tb2.server.default_backend_name", return_value="process")
    def test_default_backend_follows_platform_policy(self, mock_default):
        from tb2.process_backend import ProcessBackend
        b = server_mod._make_backend({})
        assert isinstance(b, ProcessBackend)
        mock_default.assert_called_once_with()

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

    def test_process_backend_cache_includes_shell(self):
        b1 = server_mod._make_backend({"backend": "process", "backend_id": "same", "shell": "/bin/bash"})
        b2 = server_mod._make_backend({"backend": "process", "backend_id": "same", "shell": "/bin/sh"})
        assert b1 is not b2

    def test_tmux_backend_cache_includes_distro(self):
        b1 = server_mod._make_backend({"backend": "tmux", "backend_id": "same", "distro": "Ubuntu"})
        b2 = server_mod._make_backend({"backend": "tmux", "backend_id": "same", "distro": "Debian"})
        assert b1 is not b2

    def test_backend_cache_avoids_colon_collision(self):
        b1 = server_mod._make_backend({"backend": "process", "backend_id": "a:b", "shell": "c"})
        b2 = server_mod._make_backend({"backend": "process", "backend_id": "a", "shell": "b:c"})
        assert b1 is not b2


class TestRoomHandlers:
    def test_room_create(self):
        result = server_mod.handle_room_create({"room_id": "test-r"})
        assert result["room_id"] == "test-r"
        assert get_room("test-r") is not None

    def test_room_create_rejects_invalid_id(self):
        result = server_mod.handle_room_create({"room_id": "bad room"})
        assert result["error"] == "invalid room_id"

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
        assert result["error"] == "after_id must be an integer"

    def test_room_post(self):
        create_room("post-test")
        result = server_mod.handle_room_post({
            "room_id": "post-test",
            "author": "user",
            "text": "hello",
        })
        assert "id" in result

    def test_room_poll_includes_machine_readable_source_fields(self):
        create_room("source-post")
        server_mod.handle_room_post({
            "room_id": "source-post",
            "author": "human-operator",
            "text": "hello",
        })

        result = server_mod.handle_room_poll({"room_id": "source-post", "after_id": 0})

        assert result["messages"][0]["author"] == "human-operator"
        assert result["messages"][0]["source"]["type"] == "client"
        assert result["messages"][0]["source"]["role"] == "external"
        assert result["messages"][0]["source"]["trusted"] is False
        assert result["messages"][0]["source_type"] == "client"
        assert result["messages"][0]["source_role"] == "external"
        assert result["messages"][0]["trusted"] is False

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


class DummyPipe:
    def __init__(self):
        self.buffer = ""
        self.closed = False

    def write(self, text: str) -> None:
        self.buffer += text

    def close(self) -> None:
        self.closed = True


class DummyProc:
    def __init__(self):
        self.stdin = DummyPipe()
        self.returncode = None

    def poll(self):
        return self.returncode

    def wait(self):
        self.returncode = 0
        return 0

    def terminate(self) -> None:
        self.returncode = -15


class DummyThread:
    def __init__(self, *, target=None, args=(), **_kwargs):
        self.target = target
        self.args = args
        self.started = False

    def start(self) -> None:
        self.started = True


class TestSidepanelCompat:
    @patch.object(server_mod, "_make_backend")
    def test_sidepanel_create_room_response_surfaces_backend_failure(self, mock_factory):
        mock_factory.side_effect = FileNotFoundError("backend missing")

        code, payload = server_mod._sidepanel_create_room_response()

        assert code == 503
        assert payload["ok"] is False
        assert "failed to initialize TB2 room session" in payload["error"]

    @patch.object(server_mod, "_make_backend")
    def test_sidepanel_create_room_initializes_session(self, mock_factory):
        mock_backend = MagicMock()
        mock_backend.init_session.return_value = ("sp-room:a", "sp-room:b")
        mock_factory.return_value = mock_backend

        result = server_mod._sidepanel_create_room()

        assert result["ok"] is True
        room_id = result["roomId"]
        assert get_room(room_id) is not None
        state = server_mod._sidepanel_room_state(room_id)
        assert state is not None
        assert state.session == f"sp-{room_id}"
        assert state.pane_a == "sp-room:a"
        assert state.pane_b == "sp-room:b"

    def test_sidepanel_health_reports_expected_contract(self, monkeypatch):
        monkeypatch.setattr(server_mod.shutil, "which", lambda name: "/usr/bin/codex" if name == "codex" else None)
        monkeypatch.setattr(server_mod, "_sidepanel_backend_ready", lambda force=False: (True, ""))

        payload = server_mod._sidepanel_health_payload()

        assert payload["ok"] is True
        assert payload["ready"] is True
        assert payload["bridgeMode"] == "tb2-codex"
        assert payload["provider"] == "local-tb2-codex-bridge"
        assert payload["codexAvailable"] is True
        assert payload["backendReady"] is True
        assert payload["tb2RuntimeInstalled"] is True
        assert "streaming log previews" in payload["note"]

    @patch.object(server_mod, "_make_backend")
    def test_sidepanel_message_poll_and_finalize_flow(self, mock_factory, monkeypatch, tmp_path):
        mock_backend = MagicMock()
        mock_backend.init_session.return_value = ("sp-flow:a", "sp-flow:b")
        mock_factory.return_value = mock_backend
        monkeypatch.setattr(server_mod.shutil, "which", lambda name: "/usr/bin/codex" if name == "codex" else None)
        monkeypatch.setenv("TB2_SIDEPANEL_WORKDIR", str(tmp_path))

        proc = DummyProc()
        monkeypatch.setattr(server_mod.subprocess, "Popen", lambda *args, **kwargs: proc)
        monkeypatch.setattr(server_mod.threading, "Thread", DummyThread)

        created = server_mod._sidepanel_create_room()
        room_id = created["roomId"]

        code, accepted = server_mod._sidepanel_message_response({
            "roomId": room_id,
            "prompt": "Summarize this tab",
            "mode": "tb2-codex",
        })

        assert code == 202
        assert accepted["ok"] is True
        state = server_mod._sidepanel_room_state(room_id)
        assert state is not None
        assert state.pending is True
        assert "Summarize this tab" in proc.stdin.buffer

        log_path = state.log_path
        output_path = state.output_path
        assert log_path
        assert output_path

        Path(log_path).write_text("partial output", encoding="utf-8")
        first_code, first_poll = server_mod._sidepanel_poll_response(room_id, 0)

        assert first_code == 200
        assert first_poll["messages"][0]["role"] == "user"
        assert first_poll["messages"][1]["role"] == "system"
        assert first_poll["messages"][1]["meta"]["streamKey"] == state.run_id
        assert first_poll["messages"][1]["meta"]["replace"] is True
        assert first_poll["messages"][1]["meta"]["final"] is False

        Path(output_path).write_text("Final assistant answer", encoding="utf-8")
        server_mod._sidepanel_finalize_run(room_id, state.run_id, proc, open(log_path, "a", encoding="utf-8"))

        second_code, second_poll = server_mod._sidepanel_poll_response(room_id, first_poll["latestId"])

        assert second_code == 200
        assert len(second_poll["messages"]) == 1
        assert second_poll["messages"][0]["role"] == "assistant"
        assert second_poll["messages"][0]["text"] == "Final assistant answer"
        assert second_poll["messages"][0]["meta"]["streamKey"] == first_poll["messages"][1]["meta"]["streamKey"]
        assert second_poll["messages"][0]["meta"]["final"] is True

    @patch.object(server_mod, "_make_backend")
    def test_sidepanel_message_response_surfaces_launch_failure_without_posting_user_message(self, mock_factory, monkeypatch, tmp_path):
        mock_backend = MagicMock()
        mock_backend.init_session.return_value = ("sp-fail:a", "sp-fail:b")
        mock_factory.return_value = mock_backend
        monkeypatch.setattr(server_mod.shutil, "which", lambda name: "/usr/bin/codex" if name == "codex" else None)
        monkeypatch.setenv("TB2_SIDEPANEL_WORKDIR", str(tmp_path))
        monkeypatch.setattr(server_mod.subprocess, "Popen", MagicMock(side_effect=OSError("spawn failed")))

        room_id = server_mod._sidepanel_create_room()["roomId"]
        code, payload = server_mod._sidepanel_message_response({
            "roomId": room_id,
            "prompt": "Will this fail?",
        })

        assert code == 503
        assert payload["ok"] is False
        room = get_room(room_id)
        assert room is not None
        assert room.latest_id == 0

    def test_origin_allows_extension_scheme_on_loopback(self):
        server_mod._server_context["host"] = "127.0.0.1"

        assert server_mod._origin_allowed("chrome-extension://abcdefghijklmnop")
        assert server_mod._sidepanel_request_allowed("chrome-extension://abcdefghijklmnop", "127.0.0.1") is True
        assert server_mod._sidepanel_request_allowed("", "127.0.0.1") is True
        assert server_mod._sidepanel_request_allowed("", "10.0.0.5") is False
        assert server_mod._sidepanel_request_allowed("chrome-extension://abcdefghijklmnop", "10.0.0.5") is False

    @patch.object(server_mod, "_make_backend")
    def test_sidepanel_rejects_new_prompt_until_previous_run_finalizes(self, mock_factory, monkeypatch, tmp_path):
        mock_backend = MagicMock()
        mock_backend.init_session.return_value = ("sp-race:a", "sp-race:b")
        mock_factory.return_value = mock_backend
        monkeypatch.setattr(server_mod.shutil, "which", lambda name: "/usr/bin/codex" if name == "codex" else None)
        monkeypatch.setenv("TB2_SIDEPANEL_WORKDIR", str(tmp_path))
        monkeypatch.setattr(server_mod.threading, "Thread", DummyThread)

        proc = DummyProc()
        monkeypatch.setattr(server_mod.subprocess, "Popen", lambda *args, **kwargs: proc)

        room_id = server_mod._sidepanel_create_room()["roomId"]
        first_code, _first = server_mod._sidepanel_message_response({
            "roomId": room_id,
            "prompt": "first prompt",
        })
        assert first_code == 202

        proc.returncode = 0
        second_code, second = server_mod._sidepanel_message_response({
            "roomId": room_id,
            "prompt": "second prompt",
        })

        assert second_code == 409
        assert second["error"] == "room already has a pending prompt"

    @patch.object(server_mod, "_make_backend")
    def test_sidepanel_http_routes_work_on_loopback(self, mock_factory, monkeypatch):
        mock_backend = MagicMock()
        mock_backend.init_session.return_value = ("sp-http:a", "sp-http:b")
        mock_factory.return_value = mock_backend
        monkeypatch.setattr(server_mod.shutil, "which", lambda name: "/usr/bin/codex" if name == "codex" else None)
        monkeypatch.setattr(server_mod, "_sidepanel_backend_ready", lambda force=False: (True, ""))

        server = server_mod.ThreadingHTTPServer(("127.0.0.1", 0), server_mod.MCPHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_address[1]
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as resp:
                health = json.loads(resp.read().decode("utf-8"))
            req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/tb2/rooms", data=b"", method="POST")
            with urllib.request.urlopen(req, timeout=5) as resp:
                created = json.loads(resp.read().decode("utf-8"))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2.0)

        assert health["ok"] is True
        assert health["ready"] is True
        assert created["ok"] is True
        assert get_room(created["roomId"]) is not None


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

    def test_governance_resolve(self, tmp_path):
        config = tmp_path / "governance.json"
        config.write_text(json.dumps({
            "environment": {
                "wsl-tmux": {
                    "preferred_backend": "pipe",
                }
            }
        }), encoding="utf-8")
        result = server_mod.handle_governance_resolve({
            "environment": "wsl-tmux",
            "config_path": str(config),
        })
        assert result["effective_config"]["preferred_backend"] == "pipe"
        assert result["config_path"] == str(config)

    def test_governance_resolve_invalid_config(self, tmp_path):
        config = tmp_path / "governance.json"
        config.write_text(json.dumps({
            "unknown": {
                "demo": {"x": 1},
            }
        }), encoding="utf-8")
        result = server_mod.handle_governance_resolve({
            "config_path": str(config),
        })
        assert result["error"] == "unknown governance layer: unknown"


class TestStatusHandler:
    @patch.object(server_mod, "_make_backend")
    def test_status(self, mock_factory):
        mock_backend = MagicMock()
        mock_backend.capture_both.return_value = ([], [])
        mock_factory.return_value = mock_backend
        create_room("status-test")
        server_mod.handle_bridge_start({
            "pane_a": "status:a",
            "pane_b": "status:b",
            "room_id": "status-test",
            "bridge_id": "status-bridge",
            "workstream_id": "main-flow",
            "profile": "codex",
            "auto_forward": True,
            "intervention": True,
        })
        result = server_mod.handle_status({})
        assert "rooms" in result
        assert "bridges" in result
        assert "bridge_details" in result
        assert "audit" in result
        assert "runtime" in result
        assert result["audit"]["enabled"] is False
        assert result["audit"]["redaction"]["mode"] == "mask"
        assert "text" in result["audit"]["redaction"]["fields"]
        assert result["audit"]["redaction"]["requested_mode"] == "mask"
        assert result["audit"]["redaction"]["stores_raw_text"] is False
        assert result["audit"]["redaction"]["stores_masked_placeholders"] is True
        assert result["audit"]["redaction"]["stores_hash_fingerprint"] is True
        assert result["audit"]["redaction"]["raw_text_opt_in_blocked"] is False
        assert result["runtime"]["state_persistence"] == "memory_only"
        assert result["runtime"]["restart_behavior"] == "state_lost"
        assert result["runtime"]["recovery_source"] == "audit_history_only"
        assert result["runtime"]["launch_mode"] == "direct"
        assert result["runtime"]["snapshot_schema_version"] is None
        assert result["runtime"]["audit_policy_persistence"] == "process_env_only"
        assert result["runtime"]["continuity"]["mode"] == "process_local_only"
        assert result["runtime"]["continuity"]["runtime_restored"] is False
        assert result["governance"]["requested"]["instruction_profile"] == "mcp-operator"
        assert result["governance"]["layer_order"] == [
            "base",
            "model",
            "environment",
            "instruction_profile",
        ]
        assert any(item["layer"] == "base" for item in result["governance"]["matched_layers"])
        assert result["governance"]["effective_config"]["review_mode"] in {"guarded", "manual", "auto"}
        assert result["governance"]["authoritative_keys"] == ["review_mode"]
        assert "review_mode" in result["workstreams"][0]["governance"]["authoritative_keys"]
        assert result["workstreams"][0]["governance"]["key_classes"]["review_mode"] == "authoritative"
        assert result["workstreams"][0]["governance"]["policy_state"]["overrides"] == {}
        room_ids = [r["id"] for r in result["rooms"]]
        assert "status-test" in room_ids
        assert result["bridges"] == ["status-bridge"]
        assert result["bridge_details"][0]["room_id"] == "status-test"
        assert result["bridge_details"][0]["workstream_id"] == "main-flow"
        assert result["bridge_details"][0]["profile"] == "codex"
        assert result["bridge_details"][0]["review_mode"] == "manual"
        assert result["bridge_details"][0]["tier"] == "main"
        assert result["bridge_details"][0]["policy"]["rate_limit"] == 6
        assert result["workstreams"][0]["workstream_id"] == "main-flow"
        assert result["workstreams"][0]["bridge_active"] is True
        assert result["workstreams"][0]["review_mode"] == "manual"
        assert result["workstreams"][0]["policy"]["silent_seconds"] == 30.0
        assert result["workstreams"][0]["policy"]["pending_limit"] == 12
        assert result["workstreams"][0]["health"]["state"] == "ok"
        assert result["workstreams"][0]["dependency"]["tier"] == "main"
        assert result["workstreams"][0]["dependency"]["child_count"] == 0
        assert result["fleet"]["count"] == 1
        assert result["fleet"]["live"] == 1
        assert result["fleet"]["healthy"] == 1
        assert result["fleet"]["alerts"] == 0
        assert result["fleet"]["governance_review_overrides"] == 0
        assert result["fleet"]["governance_policy_overrides"] == 0
        assert result["fleet"]["governance_exceptions"] == 0
        assert result["fleet"]["orphaned_rooms"] == 0
        assert result["fleet"]["orphaned_workstreams"] == 0
        assert result["fleet"]["stale_workstreams"] == 0
        server_mod.handle_bridge_stop({"bridge_id": "status-bridge"})

    @patch.object(server_mod, "_make_backend")
    def test_status_detects_silent_workstream_health(self, mock_factory):
        mock_backend = MagicMock()
        mock_backend.capture_both.return_value = ([], [])
        mock_factory.return_value = mock_backend
        server_mod.handle_bridge_start({
            "pane_a": "silent:a",
            "pane_b": "silent:b",
            "room_id": "silent-room",
            "bridge_id": "silent-bridge",
            "workstream_id": "silent-main",
        })
        bridge = server_mod._get_bridge("silent-bridge")
        assert bridge is not None
        bridge.last_activity_at -= 1000.0
        server_mod._set_workstream(server_mod._bridge_workstream_record(bridge))

        result = server_mod.handle_status({})

        assert result["workstreams"][0]["health"]["state"] == "critical"
        assert result["workstreams"][0]["health"]["alerts"][0]["code"] == "silent_stream"
        assert result["fleet"]["critical"] == 1
        assert result["fleet"]["intervene"] == 1
        assert result["fleet"]["stale_workstreams"] == 1
        server_mod.handle_bridge_stop({"bridge_id": "silent-bridge"})

    @patch.object(server_mod, "_make_backend")
    def test_status_marks_sub_workstream_dependency_blocked_when_parent_is_critical(self, mock_factory):
        mock_backend = MagicMock()
        mock_backend.capture_both.return_value = ([], [])
        mock_factory.return_value = mock_backend
        server_mod.handle_bridge_start({
            "pane_a": "dep:main:a",
            "pane_b": "dep:main:b",
            "room_id": "dep-main-room",
            "bridge_id": "dep-main-bridge",
            "workstream_id": "dep-main",
        })
        server_mod.handle_bridge_start({
            "pane_a": "dep:sub:a",
            "pane_b": "dep:sub:b",
            "room_id": "dep-sub-room",
            "bridge_id": "dep-sub-bridge",
            "workstream_id": "dep-sub",
            "tier": "sub",
            "parent_workstream_id": "dep-main",
        })
        parent = server_mod._get_bridge("dep-main-bridge")
        assert parent is not None
        parent.last_activity_at -= 1000.0
        server_mod._set_workstream(server_mod._bridge_workstream_record(parent))

        result = server_mod.handle_status({})
        sub = next(item for item in result["workstreams"] if item["workstream_id"] == "dep-sub")

        assert sub["dependency"]["tier"] == "sub"
        assert sub["dependency"]["parent_workstream_id"] == "dep-main"
        assert sub["dependency"]["blocked"] is True
        assert "parent unhealthy: dep-main" in sub["dependency"]["blocking_reasons"]
        assert any(alert["code"] == "dependency_blocked" for alert in sub["health"]["alerts"])
        stale_ids = {item["workstream_id"] for item in result["reconciliation"]["stale_workstreams"]}
        assert "dep-sub" in stale_ids

        server_mod.handle_bridge_stop({"bridge_id": "dep-sub-bridge"})
        server_mod.handle_bridge_stop({"bridge_id": "dep-main-bridge"})

    def test_status_reports_orphaned_workstream_reconciliation(self):
        server_mod._set_workstream(
            server_mod.WorkstreamRecord(
                workstream_id="orphan-main",
                bridge_id="orphan-bridge",
                room_id="missing-room",
                pane_a="orph:a",
                pane_b="orph:b",
                profile="generic",
                auto_forward=True,
                intervention=False,
                poll_ms=400,
                lines=200,
                backend=server_mod.BackendSpec(kind="process", backend_id="orphan"),
                state="live",
            )
        )

        result = server_mod.handle_status({})

        assert result["fleet"]["orphaned_workstreams"] == 1
        assert result["fleet"]["stale_workstreams"] == 1
        assert result["workstreams"][0]["topology"]["orphaned"] is True
        assert result["workstreams"][0]["health"]["alerts"][-1]["code"] == "orphaned_workstream"
        assert result["reconciliation"]["orphaned_workstreams"][0]["workstream_id"] == "orphan-main"

    def test_status_surfaces_service_runtime_metadata(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TB2_STATE_DIR", str(tmp_path))
        state = tmp_path / "server.state.json"
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "runtime": {
                        "launch_mode": "service",
                        "audit_policy_persistence": "service_state",
                        "continuity": {
                            "mode": "restart_state_lost",
                            "runtime_restored": False,
                            "previous_pid": 2468,
                            "previous_started_at": 12.5,
                        },
                    },
                }
            ),
            encoding="utf-8",
        )

        result = server_mod.handle_status({})

        assert result["runtime"]["launch_mode"] == "service"
        assert result["runtime"]["snapshot_schema_version"] == 1
        assert result["runtime"]["audit_policy_persistence"] == "service_state"
        assert result["runtime"]["continuity"]["mode"] == "restart_state_lost"
        assert result["runtime"]["continuity"]["previous_pid"] == 2468
        assert result["runtime"]["continuity"]["previous_started_at"] == 12.5

    def test_status_reports_blocked_full_text_opt_in(self, tmp_path, monkeypatch):
        trail = AuditTrail(tmp_path, text_mode="full")
        monkeypatch.setattr(server_mod, "_audit_trail", trail)

        result = server_mod.handle_status({})

        assert result["audit"]["redaction"]["mode"] == "mask"
        assert result["audit"]["redaction"]["requested_mode"] == "full"
        assert result["audit"]["redaction"]["stores_raw_text"] is False
        assert result["audit"]["redaction"]["raw_text_opt_in_required"] is True
        assert result["audit"]["redaction"]["raw_text_opt_in_acknowledged"] is False
        assert result["audit"]["redaction"]["raw_text_opt_in_blocked"] is True
        assert result["audit"]["redaction"]["raw_text_opt_in_env"] == "TB2_AUDIT_ALLOW_FULL_TEXT"
        assert result["security"]["support_tier"] == "local-first-supported"

    @patch.object(server_mod, "_make_backend")
    def test_bridge_start_applies_authoritative_governance_review_mode(self, mock_factory):
        mock_backend = MagicMock()
        mock_backend.capture_both.return_value = ([], [])
        mock_factory.return_value = mock_backend

        started = server_mod.handle_bridge_start({
            "pane_a": "gov:a",
            "pane_b": "gov:b",
            "room_id": "gov-room",
            "bridge_id": "gov-bridge",
            "workstream_id": "gov-main",
            "instruction_profile": "approval-gate",
            "intervention": False,
        })

        assert started["workstream_id"] == "gov-main"
        workstream = server_mod.handle_workstream_get({"workstream_id": "gov-main"})["workstream"]
        assert workstream["review_mode"] == "manual"
        assert workstream["intervention"] is True
        assert workstream["governance"]["requested"]["instruction_profile"] == "approval-gate"
        assert workstream["governance"]["runtime_projection"]["review_mode"]["state"] == "enforced"
        assert workstream["governance"]["applied_controls"]["review_mode"]["value"] == "manual"

        server_mod.handle_bridge_stop({"bridge_id": "gov-bridge"})


class TestAuditTrail:
    @patch.object(server_mod, "_make_backend")
    def test_audit_trail_records_bridge_room_and_operator_events(self, mock_factory, tmp_path, monkeypatch):
        mock_backend = MagicMock()
        mock_backend.capture_both.return_value = ([], [])
        mock_factory.return_value = mock_backend
        monkeypatch.setenv("TB2_AUDIT_DIR", str(tmp_path))
        monkeypatch.setattr(server_mod, "_audit_trail", AuditTrail(tmp_path))
        room_id = "audit-room-events"

        server_mod.handle_room_create({"room_id": room_id})
        server_mod.handle_bridge_start({
            "pane_a": "audit:a",
            "pane_b": "audit:b",
            "room_id": room_id,
            "bridge_id": "audit-bridge",
        })
        server_mod.handle_room_post({
            "room_id": room_id,
            "author": "human-operator",
            "text": "ship it",
            "deliver": "a",
            "bridge_id": "audit-bridge",
        })
        server_mod.handle_terminal_interrupt({"bridge_id": "audit-bridge", "target": "a"})
        server_mod.handle_bridge_stop({"bridge_id": "audit-bridge"})

        events = [
            json.loads(line)["event"]
            for line in (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        assert "room.created" in events
        assert "bridge.started" in events
        assert "room.message_posted" in events
        assert "operator.room_post" in events


class TestWorkstreamHandlers:
    @patch.object(server_mod, "_make_backend")
    def test_workstream_list_and_get_surface_policy_and_review_mode(self, mock_factory):
        mock_backend = MagicMock()
        mock_backend.capture_both.return_value = ([], [])
        mock_factory.return_value = mock_backend

        server_mod.handle_bridge_start({
            "pane_a": "ws:list:a",
            "pane_b": "ws:list:b",
            "room_id": "ws-list-room",
            "bridge_id": "ws-list-bridge",
            "workstream_id": "ws-list-main",
            "auto_forward": True,
        })

        listed = server_mod.handle_workstream_list({})
        detail = server_mod.handle_workstream_get({"workstream_id": "ws-list-main"})

        assert listed["count"] == 1
        assert listed["workstreams"][0]["workstream_id"] == "ws-list-main"
        assert listed["workstreams"][0]["review_mode"] == "auto"
        assert listed["workstreams"][0]["policy"]["rate_limit"] == 6
        assert listed["workstreams"][0]["policy"]["pending_limit"] == 12
        assert listed["workstreams"][0]["dependency"]["tier"] == "main"
        assert detail["workstream"]["workstream_id"] == "ws-list-main"
        assert detail["workstream"]["policy"]["pending_warn"] == 3
        assert detail["workstream"]["dependency"]["child_count"] == 0

        server_mod.handle_bridge_stop({"bridge_id": "ws-list-bridge"})

    @patch.object(server_mod, "_make_backend")
    def test_intervention_list_resolves_workstream_id(self, mock_factory):
        mock_backend = MagicMock()
        mock_backend.capture_both.return_value = ([], [])
        mock_factory.return_value = mock_backend

        create_room("ws-room")
        started = server_mod.handle_bridge_start({
            "pane_a": "ws:a",
            "pane_b": "ws:b",
            "room_id": "ws-room",
            "bridge_id": "ws-bridge",
            "workstream_id": "ws-main",
            "intervention": True,
        })

        result = server_mod.handle_intervention_list({"workstream_id": "ws-main"})

        assert started["workstream_id"] == "ws-main"
        assert result["bridge_id"] == "ws-bridge"
        server_mod.handle_bridge_stop({"bridge_id": "ws-bridge"})

    @patch.object(server_mod, "_make_backend")
    def test_status_reports_governance_exception_summary(self, mock_factory):
        mock_backend = MagicMock()
        mock_backend.capture_both.return_value = ([], [])
        mock_factory.return_value = mock_backend

        server_mod.handle_bridge_start({
            "pane_a": "ws:summary:a",
            "pane_b": "ws:summary:b",
            "room_id": "ws-summary-room",
            "bridge_id": "ws-summary-bridge",
            "workstream_id": "ws-summary-main",
            "auto_forward": True,
        })

        server_mod.handle_workstream_pause_review({"workstream_id": "ws-summary-main"})
        server_mod.handle_workstream_update_policy({
            "workstream_id": "ws-summary-main",
            "rate_limit": 2,
            "silent_seconds": 45,
        })
        result = server_mod.handle_status({})

        assert result["fleet"]["governance_review_overrides"] == 1
        assert result["fleet"]["governance_policy_overrides"] == 2
        assert result["fleet"]["governance_exceptions"] == 3
        workstream = next(item for item in result["workstreams"] if item["workstream_id"] == "ws-summary-main")
        trace = workstream["governance"]["decision_trace"]
        assert any(item["kind"] == "review_mode" and item["state"] == "override" for item in trace)
        assert any(item["kind"] == "policy" and item["key"] == "rate_limit" for item in trace)
        assert any(item["kind"] == "policy" and item["key"] == "silent_seconds" for item in trace)

        server_mod.handle_bridge_stop({"bridge_id": "ws-summary-bridge"})

    @patch.object(server_mod, "_make_backend")
    def test_workstream_pause_and_resume_review(self, mock_factory, tmp_path, monkeypatch):
        mock_backend = MagicMock()
        mock_backend.capture_both.return_value = ([], [])
        mock_factory.return_value = mock_backend
        monkeypatch.setenv("TB2_AUDIT_DIR", str(tmp_path))
        monkeypatch.setattr(server_mod, "_audit_trail", AuditTrail(tmp_path))

        server_mod.handle_bridge_start({
            "pane_a": "ws:pause:a",
            "pane_b": "ws:pause:b",
            "room_id": "ws-pause-room",
            "bridge_id": "ws-pause-bridge",
            "workstream_id": "ws-pause-main",
            "auto_forward": True,
        })

        paused = server_mod.handle_workstream_pause_review({"workstream_id": "ws-pause-main"})
        resumed = server_mod.handle_workstream_resume_review({"workstream_id": "ws-pause-main"})
        audit = server_mod.handle_audit_recent({
            "workstream_id": "ws-pause-main",
            "limit": 10,
        })

        assert paused["workstream"]["review_mode"] == "paused"
        assert paused["workstream"]["governance"]["review_mode_state"]["baseline"] == "auto"
        assert paused["workstream"]["governance"]["review_mode_state"]["override_active"] is True
        assert paused["workstream"]["governance"]["review_mode_state"]["effective_source"] == "operator_override"
        assert paused["workstream"]["governance"]["decision_trace"][0]["kind"] == "review_mode"
        assert paused["workstream"]["governance"]["decision_trace"][0]["state"] == "override"
        assert paused["workstream"]["governance"]["decision_trace"][0]["reason"] == "operator_pause_review"
        assert paused["workstream"]["health"]["alerts"][0]["code"] == "review_paused"
        assert resumed["workstream"]["review_mode"] == "auto"
        assert resumed["workstream"]["governance"]["review_mode_state"]["override_active"] is False
        assert resumed["workstream"]["governance"]["review_mode_state"]["effective_source"] == "governance"
        assert resumed["workstream"]["governance"]["decision_trace"][0]["state"] == "baseline"
        assert [item["event"] for item in audit["events"] if item["event"].startswith("workstream.review_")] == [
            "workstream.review_paused",
            "workstream.review_resumed",
        ]

        server_mod.handle_bridge_stop({"bridge_id": "ws-pause-bridge"})

    @patch.object(server_mod, "_make_backend")
    def test_workstream_resume_review_rejects_pending_queue(self, mock_factory):
        mock_backend = MagicMock()
        mock_backend.capture_both.return_value = ([], [])
        mock_factory.return_value = mock_backend

        server_mod.handle_bridge_start({
            "pane_a": "ws:pending:a",
            "pane_b": "ws:pending:b",
            "room_id": "ws-pending-room",
            "bridge_id": "ws-pending-bridge",
            "workstream_id": "ws-pending-main",
            "intervention": True,
        })
        bridge = server_mod._get_bridge("ws-pending-bridge")
        assert bridge is not None
        bridge.intervention_layer.submit("ws:pending:a", "ws:pending:b", "echo hold")
        paused = server_mod.handle_workstream_pause_review({"workstream_id": "ws-pending-main"})
        resumed = server_mod.handle_workstream_resume_review({"workstream_id": "ws-pending-main"})

        assert paused["workstream"]["review_mode"] == "manual"
        assert resumed["error"] == "cannot resume review with 1 pending item(s)"
        assert resumed["pending_count"] == 1

        server_mod.handle_bridge_stop({"bridge_id": "ws-pending-bridge"})

    @patch.object(server_mod, "_make_backend")
    def test_governance_manual_review_mode_survives_pause_resume_without_override(self, mock_factory):
        mock_backend = MagicMock()
        mock_backend.capture_both.return_value = ([], [])
        mock_factory.return_value = mock_backend

        server_mod.handle_bridge_start({
            "pane_a": "ws:gov:a",
            "pane_b": "ws:gov:b",
            "room_id": "ws-gov-room",
            "bridge_id": "ws-gov-bridge",
            "workstream_id": "ws-gov-main",
            "instruction_profile": "approval-gate",
        })

        paused = server_mod.handle_workstream_pause_review({"workstream_id": "ws-gov-main"})
        resumed = server_mod.handle_workstream_resume_review({"workstream_id": "ws-gov-main"})

        assert paused["workstream"]["review_mode"] == "manual"
        assert paused["workstream"]["governance"]["review_mode_state"]["baseline"] == "manual"
        assert paused["workstream"]["governance"]["review_mode_state"]["override_active"] is False
        assert paused["workstream"]["governance"]["review_mode_state"]["effective_source"] == "governance"
        assert resumed["workstream"]["review_mode"] == "manual"
        assert resumed["workstream"]["governance"]["review_mode_state"]["override_active"] is False
        assert resumed["workstream"]["governance"]["review_mode_state"]["effective_source"] == "governance"

        server_mod.handle_bridge_stop({"bridge_id": "ws-gov-bridge"})

    @patch.object(server_mod, "_make_backend")
    def test_workstream_resume_review_respects_parent_dependency_state(self, mock_factory):
        mock_backend = MagicMock()
        mock_backend.capture_both.return_value = ([], [])
        mock_factory.return_value = mock_backend

        server_mod.handle_bridge_start({
            "pane_a": "ws:parent:a",
            "pane_b": "ws:parent:b",
            "room_id": "ws-parent-room",
            "bridge_id": "ws-parent-bridge",
            "workstream_id": "ws-parent-main",
        })
        server_mod.handle_bridge_start({
            "pane_a": "ws:child:a",
            "pane_b": "ws:child:b",
            "room_id": "ws-child-room",
            "bridge_id": "ws-child-bridge",
            "workstream_id": "ws-child-sub",
            "tier": "sub",
            "parent_workstream_id": "ws-parent-main",
        })

        server_mod.handle_workstream_pause_review({"workstream_id": "ws-parent-main"})
        paused_parent = server_mod.handle_workstream_resume_review({"workstream_id": "ws-child-sub"})
        assert paused_parent["error"] == "cannot resume sub workstream while parent review is paused: ws-parent-main"

        server_mod.handle_workstream_resume_review({"workstream_id": "ws-parent-main"})
        parent = server_mod._get_bridge("ws-parent-bridge")
        assert parent is not None
        parent.last_activity_at -= 1000.0
        server_mod._set_workstream(server_mod._bridge_workstream_record(parent))

        critical_parent = server_mod.handle_workstream_resume_review({"workstream_id": "ws-child-sub"})
        assert critical_parent["error"] == "cannot resume sub workstream while parent requires intervention: ws-parent-main"

        server_mod.handle_bridge_stop({"bridge_id": "ws-child-bridge"})
        server_mod.handle_bridge_stop({"bridge_id": "ws-parent-bridge"})

    @patch.object(server_mod, "_make_backend")
    def test_workstream_update_policy_updates_live_bridge(self, mock_factory, tmp_path, monkeypatch):
        mock_backend = MagicMock()
        mock_backend.capture_both.return_value = ([], [])
        mock_factory.return_value = mock_backend
        monkeypatch.setenv("TB2_AUDIT_DIR", str(tmp_path))
        monkeypatch.setattr(server_mod, "_audit_trail", AuditTrail(tmp_path))

        server_mod.handle_bridge_start({
            "pane_a": "ws:policy:a",
            "pane_b": "ws:policy:b",
            "room_id": "ws-policy-room",
            "bridge_id": "ws-policy-bridge",
            "workstream_id": "ws-policy-main",
        })

        updated = server_mod.handle_workstream_update_policy({
            "workstream_id": "ws-policy-main",
            "rate_limit": 2,
            "pending_warn": 1,
            "pending_critical": 2,
            "pending_limit": 4,
            "silent_seconds": 45,
        })
        audit = server_mod.handle_audit_recent({
            "workstream_id": "ws-policy-main",
            "event": "workstream.policy_updated",
            "limit": 5,
        })
        bridge = server_mod._get_bridge("ws-policy-bridge")

        assert bridge is not None
        assert updated["workstream"]["policy"]["rate_limit"] == 2
        assert updated["workstream"]["policy"]["pending_warn"] == 1
        assert updated["workstream"]["policy"]["pending_critical"] == 2
        assert updated["workstream"]["policy"]["pending_limit"] == 4
        assert updated["workstream"]["policy"]["silent_seconds"] == 45.0
        assert bridge.policy["rate_limit"] == 2
        assert audit["count"] == 1
        assert audit["events"][0]["policy"]["rate_limit"] == 2
        assert updated["workstream"]["governance"]["policy_state"]["effective"]["rate_limit"] == 2
        assert updated["workstream"]["governance"]["policy_state"]["overrides"]["rate_limit"]["source"] == "operator_exception"
        assert updated["workstream"]["governance"]["policy_state"]["overrides"]["rate_limit"]["reason"] == "workstream_update_policy"
        assert audit["events"][0]["governance"]["policy_state"]["overrides"]["rate_limit"]["value"] == 2
        policy_trace = [item for item in updated["workstream"]["governance"]["decision_trace"] if item["kind"] == "policy"]
        assert any(item["key"] == "rate_limit" and item["value"] == 2 for item in policy_trace)

        server_mod.handle_bridge_stop({"bridge_id": "ws-policy-bridge"})

    @patch.object(server_mod, "_make_backend")
    def test_workstream_quota_guard_blocks_new_handoffs_and_rearms(self, mock_factory, tmp_path, monkeypatch):
        mock_backend = MagicMock()
        mock_backend.capture_both.return_value = ([], [])
        mock_factory.return_value = mock_backend
        monkeypatch.setenv("TB2_AUDIT_DIR", str(tmp_path))
        monkeypatch.setattr(server_mod, "_audit_trail", AuditTrail(tmp_path))

        server_mod.handle_bridge_start({
            "pane_a": "ws:quota:a",
            "pane_b": "ws:quota:b",
            "room_id": "ws-quota-room",
            "bridge_id": "ws-quota-bridge",
            "workstream_id": "ws-quota-main",
            "auto_forward": True,
        })
        server_mod.handle_workstream_update_policy({
            "workstream_id": "ws-quota-main",
            "pending_warn": 1,
            "pending_critical": 1,
            "pending_limit": 1,
        })
        bridge = server_mod._get_bridge("ws-quota-bridge")
        assert bridge is not None
        bridge.intervention_layer.restore({
            "active": False,
            "counter": 1,
            "pending": [
                {
                    "id": 1,
                    "from_pane": bridge.pane_a,
                    "to_pane": bridge.pane_b,
                    "text": "echo seed backlog",
                    "action": "pending",
                    "edited_text": None,
                    "created_at": 1.0,
                }
            ],
        })

        profile = server_mod.get_profile("generic")
        bridge._process_new_lines("A", bridge.pane_a, bridge.pane_b, ["MSG: echo overflow"], profile)

        detail = server_mod.handle_workstream_get({"workstream_id": "ws-quota-main"})
        pending = server_mod.handle_intervention_list({"workstream_id": "ws-quota-main"})
        audit = server_mod.handle_audit_recent({
            "workstream_id": "ws-quota-main",
            "limit": 20,
        })

        assert pending["count"] == 1
        assert detail["workstream"]["review_mode"] == "guarded"
        assert detail["workstream"]["auto_forward_guard"]["blocked"] is True
        assert detail["workstream"]["auto_forward_guard"]["pending_limit"] == 1
        assert detail["workstream"]["auto_forward_guard"]["quota_reason"] == "pending quota exceeded: 1/1 queued handoffs"
        assert any(alert["code"] == "quota_blocked" for alert in detail["workstream"]["health"]["alerts"])
        assert any(item["event"] == "workstream.quota_blocked" for item in audit["events"])

        server_mod.handle_intervention_reject({"workstream_id": "ws-quota-main", "id": 1})
        rearmed = server_mod.handle_workstream_get({"workstream_id": "ws-quota-main"})
        audit = server_mod.handle_audit_recent({
            "workstream_id": "ws-quota-main",
            "limit": 20,
        })

        assert rearmed["workstream"]["review_mode"] == "auto"
        assert rearmed["workstream"]["auto_forward_guard"]["blocked"] is False
        assert rearmed["workstream"]["auto_forward_guard"]["quota_reason"] is None
        assert any(item["event"] == "workstream.quota_rearmed" for item in audit["events"])

        server_mod.handle_bridge_stop({"bridge_id": "ws-quota-bridge"})

    def test_workstream_update_policy_updates_inactive_record(self):
        record = server_mod.WorkstreamRecord(
            workstream_id="ws-offline-main",
            bridge_id="ws-offline-bridge",
            room_id="ws-offline-room",
            pane_a="ws:offline:a",
            pane_b="ws:offline:b",
            profile="generic",
            auto_forward=True,
            intervention=False,
            poll_ms=400,
            lines=200,
            backend=server_mod.BackendSpec(kind="process", backend_id="offline"),
            state="degraded",
            policy={"rate_limit": 4, "window_seconds": 3.0, "streak_limit": 20, "pending_warn": 3, "pending_critical": 8, "silent_seconds": 30.0},
        )
        server_mod._set_workstream(record)

        updated = server_mod.handle_workstream_update_policy({
            "workstream_id": "ws-offline-main",
            "silent_seconds": 90,
        })

        assert updated["workstream"]["policy"]["silent_seconds"] == 90.0
        assert updated["workstream"]["bridge_active"] is False
        assert updated["workstream"]["governance"]["policy_state"]["overrides"]["silent_seconds"]["value"] == 90.0
        policy_trace = [item for item in updated["workstream"]["governance"]["decision_trace"] if item["kind"] == "policy"]
        assert any(item["key"] == "silent_seconds" and item["value"] == 90.0 for item in policy_trace)

    def test_workstream_update_policy_requires_fields(self):
        server_mod._set_workstream(
            server_mod.WorkstreamRecord(
                workstream_id="ws-empty-policy",
                bridge_id="ws-empty-bridge",
                room_id="ws-empty-room",
                pane_a="ws:empty:a",
                pane_b="ws:empty:b",
                profile="generic",
                auto_forward=False,
                intervention=False,
                poll_ms=400,
                lines=200,
                backend=server_mod.BackendSpec(kind="process", backend_id="empty"),
                state="degraded",
            )
        )

        result = server_mod.handle_workstream_update_policy({"workstream_id": "ws-empty-policy"})

        assert result["error"] == "policy update requires at least one policy field"

    @patch.object(server_mod, "_make_backend")
    def test_bridge_start_enforces_main_sub_dependency_rules(self, mock_factory):
        mock_backend = MagicMock()
        mock_backend.capture_both.return_value = ([], [])
        mock_factory.return_value = mock_backend

        server_mod.handle_bridge_start({
            "pane_a": "ws:dep:main:a",
            "pane_b": "ws:dep:main:b",
            "room_id": "ws-dep-main-room",
            "bridge_id": "ws-dep-main-bridge",
            "workstream_id": "ws-dep-main",
        })
        missing_parent = server_mod.handle_bridge_start({
            "pane_a": "ws:dep:sub:a",
            "pane_b": "ws:dep:sub:b",
            "room_id": "ws-dep-sub-room",
            "bridge_id": "ws-dep-sub-bridge",
            "workstream_id": "ws-dep-sub",
            "tier": "sub",
        })
        valid_sub = server_mod.handle_bridge_start({
            "pane_a": "ws:dep:sub:a",
            "pane_b": "ws:dep:sub:b",
            "room_id": "ws-dep-sub-room",
            "bridge_id": "ws-dep-sub-bridge",
            "workstream_id": "ws-dep-sub",
            "tier": "sub",
            "parent_workstream_id": "ws-dep-main",
        })
        nested_sub = server_mod.handle_bridge_start({
            "pane_a": "ws:dep:sub2:a",
            "pane_b": "ws:dep:sub2:b",
            "room_id": "ws-dep-sub2-room",
            "bridge_id": "ws-dep-sub2-bridge",
            "workstream_id": "ws-dep-sub2",
            "tier": "sub",
            "parent_workstream_id": "ws-dep-sub",
        })

        assert missing_parent["error"] == "sub workstream requires parent_workstream_id"
        assert valid_sub["tier"] == "sub"
        assert valid_sub["parent_workstream_id"] == "ws-dep-main"
        assert nested_sub["error"] == "parent workstream must have tier=main"

        server_mod.handle_bridge_stop({"bridge_id": "ws-dep-sub-bridge"})
        server_mod.handle_bridge_stop({"bridge_id": "ws-dep-main-bridge"})

    @patch.object(server_mod, "_make_backend")
    def test_workstream_update_dependency_reparents_live_sub_workstream(self, mock_factory, tmp_path, monkeypatch):
        mock_backend = MagicMock()
        mock_backend.capture_both.return_value = ([], [])
        mock_factory.return_value = mock_backend
        monkeypatch.setenv("TB2_AUDIT_DIR", str(tmp_path))
        monkeypatch.setattr(server_mod, "_audit_trail", AuditTrail(tmp_path))

        server_mod.handle_bridge_start({
            "pane_a": "ws:main1:a",
            "pane_b": "ws:main1:b",
            "room_id": "ws-main1-room",
            "bridge_id": "ws-main1-bridge",
            "workstream_id": "ws-main-1",
        })
        server_mod.handle_bridge_start({
            "pane_a": "ws:main2:a",
            "pane_b": "ws:main2:b",
            "room_id": "ws-main2-room",
            "bridge_id": "ws-main2-bridge",
            "workstream_id": "ws-main-2",
        })
        server_mod.handle_bridge_start({
            "pane_a": "ws:sub:a",
            "pane_b": "ws:sub:b",
            "room_id": "ws-sub-room",
            "bridge_id": "ws-sub-bridge",
            "workstream_id": "ws-sub-1",
            "tier": "sub",
            "parent_workstream_id": "ws-main-1",
        })

        updated = server_mod.handle_workstream_update_dependency({
            "workstream_id": "ws-sub-1",
            "tier": "sub",
            "parent_workstream_id": "ws-main-2",
        })
        main_one = server_mod.handle_workstream_get({"workstream_id": "ws-main-1"})
        main_two = server_mod.handle_workstream_get({"workstream_id": "ws-main-2"})
        audit = server_mod.handle_audit_recent({
            "workstream_id": "ws-sub-1",
            "event": "workstream.dependency_updated",
            "limit": 5,
        })
        bridge = server_mod._get_bridge("ws-sub-bridge")

        assert bridge is not None
        assert updated["workstream"]["tier"] == "sub"
        assert updated["workstream"]["parent_workstream_id"] == "ws-main-2"
        assert bridge.parent_workstream_id == "ws-main-2"
        assert main_one["workstream"]["dependency"]["child_count"] == 0
        assert main_two["workstream"]["dependency"]["child_workstream_ids"] == ["ws-sub-1"]
        assert audit["count"] == 1
        assert audit["events"][0]["parent_workstream_id"] == "ws-main-2"

        server_mod.handle_bridge_stop({"bridge_id": "ws-sub-bridge"})
        server_mod.handle_bridge_stop({"bridge_id": "ws-main2-bridge"})
        server_mod.handle_bridge_stop({"bridge_id": "ws-main1-bridge"})

    @patch.object(server_mod, "_make_backend")
    def test_workstream_stop_stops_active_bridge_and_cleans_room(self, mock_factory, tmp_path, monkeypatch):
        mock_backend = MagicMock()
        mock_backend.capture_both.return_value = ([], [])
        mock_factory.return_value = mock_backend
        monkeypatch.setenv("TB2_AUDIT_DIR", str(tmp_path))
        monkeypatch.setattr(server_mod, "_audit_trail", AuditTrail(tmp_path))

        server_mod.handle_bridge_start({
            "pane_a": "ws:stop:a",
            "pane_b": "ws:stop:b",
            "room_id": "ws-stop-room",
            "bridge_id": "ws-stop-bridge",
            "workstream_id": "ws-stop-main",
        })

        result = server_mod.handle_workstream_stop({
            "workstream_id": "ws-stop-main",
            "cleanup_room": True,
        })
        audit = server_mod.handle_audit_recent({
            "event": "workstream.stopped",
            "limit": 5,
        })

        assert result["bridge_stopped"] is True
        assert result["workstream_removed"] is True
        assert result["room_deleted"] is True
        assert server_mod._get_bridge("ws-stop-bridge") is None
        assert server_mod._get_workstream("ws-stop-main") is None
        assert get_room("ws-stop-room") is None
        assert audit["count"] == 1
        assert audit["events"][0]["workstream_id"] == "ws-stop-main"

    def test_workstream_stop_removes_inactive_record(self):
        create_room("ws-offline-stop-room")
        server_mod._set_workstream(
            server_mod.WorkstreamRecord(
                workstream_id="ws-offline-stop",
                bridge_id="ws-offline-stop-bridge",
                room_id="ws-offline-stop-room",
                pane_a="ws:offline-stop:a",
                pane_b="ws:offline-stop:b",
                profile="generic",
                auto_forward=False,
                intervention=False,
                poll_ms=400,
                lines=200,
                backend=server_mod.BackendSpec(kind="process", backend_id="offline-stop"),
                state="degraded",
            )
        )

        result = server_mod.handle_workstream_stop({
            "workstream_id": "ws-offline-stop",
            "cleanup_room": True,
        })

        assert result["bridge_stopped"] is False
        assert result["workstream_removed"] is True
        assert result["room_deleted"] is True
        assert server_mod._get_workstream("ws-offline-stop") is None
        assert get_room("ws-offline-stop-room") is None

    @patch.object(server_mod, "_make_backend")
    def test_workstream_stop_requires_cascade_for_dependents(self, mock_factory):
        mock_backend = MagicMock()
        mock_backend.capture_both.return_value = ([], [])
        mock_factory.return_value = mock_backend

        server_mod.handle_bridge_start({
            "pane_a": "ws:tree:main:a",
            "pane_b": "ws:tree:main:b",
            "room_id": "ws-tree-main-room",
            "bridge_id": "ws-tree-main-bridge",
            "workstream_id": "ws-tree-main",
        })
        server_mod.handle_bridge_start({
            "pane_a": "ws:tree:sub1:a",
            "pane_b": "ws:tree:sub1:b",
            "room_id": "ws-tree-sub1-room",
            "bridge_id": "ws-tree-sub1-bridge",
            "workstream_id": "ws-tree-sub-1",
            "tier": "sub",
            "parent_workstream_id": "ws-tree-main",
        })
        server_mod.handle_bridge_start({
            "pane_a": "ws:tree:sub2:a",
            "pane_b": "ws:tree:sub2:b",
            "room_id": "ws-tree-sub2-room",
            "bridge_id": "ws-tree-sub2-bridge",
            "workstream_id": "ws-tree-sub-2",
            "tier": "sub",
            "parent_workstream_id": "ws-tree-main",
        })

        blocked = server_mod.handle_workstream_stop({"workstream_id": "ws-tree-main"})
        cascaded = server_mod.handle_workstream_stop({
            "workstream_id": "ws-tree-main",
            "cascade": True,
        })

        assert blocked["error"] == "cannot stop workstream with 2 dependent sub workstream(s); set cascade=true"
        assert blocked["dependency_children"] == ["ws-tree-sub-1", "ws-tree-sub-2"]
        assert cascaded["cascade"] is True
        assert {item["workstream_id"] for item in cascaded["removed"]} == {
            "ws-tree-main",
            "ws-tree-sub-1",
            "ws-tree-sub-2",
        }
        assert server_mod._get_workstream("ws-tree-main") is None
        assert server_mod._get_workstream("ws-tree-sub-1") is None
        assert server_mod._get_workstream("ws-tree-sub-2") is None

    def test_fleet_reconcile_reports_and_applies_orphan_cleanup(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TB2_AUDIT_DIR", str(tmp_path))
        monkeypatch.setattr(server_mod, "_audit_trail", AuditTrail(tmp_path))

        orphan_room = create_room("orphan-room")
        orphan_room.post(
            author="bridge",
            text="[forwarded]",
            kind="system",
            meta={"bridge_id": "orphan-bridge"},
            source_type="bridge",
            source_role="automation",
            trusted=True,
        )
        server_mod._set_workstream(
            server_mod.WorkstreamRecord(
                workstream_id="orphan-workstream",
                bridge_id="orphan-bridge",
                room_id="missing-room",
                pane_a="orph:a",
                pane_b="orph:b",
                profile="generic",
                auto_forward=True,
                intervention=False,
                poll_ms=400,
                lines=200,
                backend=server_mod.BackendSpec(kind="process", backend_id="orphan"),
                state="live",
            )
        )

        preview = server_mod.handle_fleet_reconcile({})
        applied = server_mod.handle_fleet_reconcile({"apply": True})
        audit = server_mod.handle_audit_recent({"event": "fleet.reconciled", "limit": 5})

        assert preview["apply"] is False
        assert preview["orphaned_rooms"][0]["room_id"] == "orphan-room"
        assert preview["orphaned_workstreams"][0]["workstream_id"] == "orphan-workstream"
        assert applied["apply"] is True
        assert applied["deleted_rooms"] == ["orphan-room"]
        assert applied["dropped_workstreams"] == ["orphan-workstream"]
        assert get_room("orphan-room") is None
        assert server_mod._get_workstream("orphan-workstream") is None
        assert audit["count"] == 2

    @patch.object(server_mod, "_make_backend")
    def test_restore_workstreams_from_service_state(self, mock_factory, tmp_path, monkeypatch):
        mock_backend = MagicMock()
        mock_backend.capture_both.return_value = ([], [])
        mock_factory.return_value = mock_backend
        monkeypatch.setenv("TB2_STATE_DIR", str(tmp_path))
        state = tmp_path / "server.state.json"
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "pid": os.getpid(),
                    "runtime": {
                        "launch_mode": "service",
                        "continuity": {
                            "mode": "restart_state_lost",
                            "runtime_restored": False,
                        },
                    },
                    "workstreams": [
                        {
                            "workstream_id": "restored-main",
                            "bridge_id": "restored-bridge",
                            "room_id": "restored-room",
                            "pane_a": "restore:a",
                            "pane_b": "restore:b",
                            "profile": "generic",
                            "auto_forward": False,
                            "intervention": True,
                            "poll_ms": 400,
                            "lines": 200,
                            "backend": {
                                "kind": "process",
                                "backend_id": "restored-backend",
                                "shell": "",
                                "distro": "",
                            },
                            "pending": [
                                {
                                    "id": 1,
                                    "from_pane": "restore:a",
                                    "to_pane": "restore:b",
                                    "text": "echo RESTORE",
                                    "action": "pending",
                                    "edited_text": None,
                                    "created_at": 1.0,
                                }
                            ],
                            "auto_forward_guard": {
                                "blocked": True,
                                "guard_reason": "rate limit exceeded",
                                "rate_limit": 2,
                                "window_seconds": 5.0,
                                "streak_limit": 9,
                            },
                            "policy": {
                                "rate_limit": 2,
                                "window_seconds": 5.0,
                                "streak_limit": 9,
                                "pending_warn": 1,
                                "pending_critical": 2,
                                "silent_seconds": 45.0,
                            },
                            "review_mode": "paused",
                            "state": "live",
                            "bridge_active": True,
                            "restore_error": None,
                            "updated_at": 1.0,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        server_mod._restore_workstreams_from_service_state()
        result = server_mod.handle_status({})

        assert result["runtime"]["continuity"]["mode"] == "restart_restored"
        assert result["runtime"]["continuity"]["runtime_restored"] is True
        assert result["runtime"]["continuity"]["recovery_protocol"] == "ordered_restore_v1"
        assert result["runtime"]["continuity"]["restore_order"] == [
            "workstream_metadata",
            "room_metadata",
            "bridge_worker",
            "pending_interventions",
            "health_state",
        ]
        assert result["runtime"]["continuity"]["restored_workstream_count"] == 1
        assert result["runtime"]["continuity"]["manual_takeover_workstream_count"] == 0
        assert result["workstreams"][0]["workstream_id"] == "restored-main"
        assert result["workstreams"][0]["state"] == "restored"
        assert result["workstreams"][0]["pending_count"] == 1
        assert result["workstreams"][0]["review_mode"] == "manual"
        assert result["workstreams"][0]["policy"]["rate_limit"] == 2
        assert result["workstreams"][0]["auto_forward_guard"]["guard_reason"] == "rate limit exceeded"
        assert result["workstreams"][0]["recovery"]["state"] == "restored"
        assert result["workstreams"][0]["recovery"]["restored_from_snapshot"] is True
        assert result["recovery"]["restored_count"] == 1
        assert result["recovery"]["restored_workstreams"] == ["restored-main"]
        assert result["recovery"]["manual_takeover_workstreams"] == []

        server_mod.handle_bridge_stop({"bridge_id": "restored-bridge"})

    @patch.object(server_mod, "_make_backend")
    def test_restore_workstreams_marks_manual_takeover_when_backend_probe_fails(self, mock_factory, tmp_path, monkeypatch):
        mock_backend = MagicMock()
        mock_backend.capture_both.side_effect = RuntimeError("capture failed")
        mock_factory.return_value = mock_backend
        monkeypatch.setenv("TB2_STATE_DIR", str(tmp_path))
        state = tmp_path / "server.state.json"
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "pid": os.getpid(),
                    "runtime": {
                        "launch_mode": "service",
                        "continuity": {
                            "mode": "restart_state_lost",
                            "runtime_restored": False,
                        },
                    },
                    "workstreams": [
                        {
                            "workstream_id": "degraded-main",
                            "bridge_id": "degraded-bridge",
                            "room_id": "degraded-room",
                            "pane_a": "restore:a",
                            "pane_b": "restore:b",
                            "profile": "generic",
                            "auto_forward": False,
                            "intervention": False,
                            "poll_ms": 400,
                            "lines": 200,
                            "backend": {
                                "kind": "process",
                                "backend_id": "degraded-backend",
                                "shell": "",
                                "distro": "",
                            },
                            "pending": [],
                            "policy": {
                                "rate_limit": 2,
                                "window_seconds": 5.0,
                                "streak_limit": 9,
                                "pending_warn": 1,
                                "pending_critical": 2,
                                "pending_limit": 3,
                                "silent_seconds": 45.0,
                            },
                            "review_mode": "auto",
                            "state": "live",
                            "bridge_active": True,
                            "restore_error": None,
                            "updated_at": 1.0,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        server_mod._restore_workstreams_from_service_state()
        result = server_mod.handle_status({})

        assert result["runtime"]["continuity"]["mode"] == "restart_state_lost"
        assert result["runtime"]["continuity"]["runtime_restored"] is False
        assert result["runtime"]["continuity"]["restored_workstream_count"] == 0
        assert result["runtime"]["continuity"]["manual_takeover_workstream_count"] == 1
        assert result["runtime"]["continuity"]["lost_workstream_count"] == 1
        assert result["workstreams"][0]["workstream_id"] == "degraded-main"
        assert result["workstreams"][0]["state"] == "degraded"
        assert result["workstreams"][0]["restore_error"] == "capture failed"
        assert result["workstreams"][0]["recovery"]["state"] == "manual_takeover"
        assert result["workstreams"][0]["recovery"]["manual_takeover_required"] is True
        assert result["recovery"]["manual_takeover_count"] == 1
        assert result["recovery"]["manual_takeover_workstreams"] == ["degraded-main"]
        assert result["recovery"]["lost_count"] == 1

    @patch.object(server_mod, "_make_backend")
    def test_audit_trail_records_intervention_approval(self, mock_factory, tmp_path, monkeypatch):
        mock_backend = MagicMock()
        mock_backend.capture_both.return_value = ([], [])
        mock_factory.return_value = mock_backend
        monkeypatch.setenv("TB2_AUDIT_DIR", str(tmp_path))
        monkeypatch.setattr(server_mod, "_audit_trail", AuditTrail(tmp_path))

        server_mod.handle_room_create({"room_id": "audit-review"})
        server_mod.handle_bridge_start({
            "pane_a": "review:a",
            "pane_b": "review:b",
            "room_id": "audit-review",
            "bridge_id": "audit-review-bridge",
            "intervention": True,
        })
        bridge = server_mod._get_bridge("audit-review-bridge")
        assert bridge is not None
        msg = bridge.intervention_layer.submit(bridge.pane_a, bridge.pane_b, "echo ok")

        result = server_mod.handle_intervention_approve({
            "bridge_id": "audit-review-bridge",
            "id": msg.id,
        })

        assert result["approved"] == 1
        lines = [
            json.loads(line)
            for line in (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        approved = [item for item in lines if item["event"] == "intervention.approved"]
        assert approved
        assert approved[-1]["approved"] == 1
        assert approved[-1]["remaining"] == 0

    @patch.object(server_mod, "_make_backend")
    def test_audit_recent_filters_persisted_events(self, mock_factory, tmp_path, monkeypatch):
        mock_backend = MagicMock()
        mock_backend.capture_both.return_value = ([], [])
        mock_factory.return_value = mock_backend
        monkeypatch.setenv("TB2_AUDIT_DIR", str(tmp_path))
        monkeypatch.setattr(server_mod, "_audit_trail", AuditTrail(tmp_path))
        room_id = "audit-room-recent"

        server_mod.handle_room_create({"room_id": room_id})
        server_mod.handle_bridge_start({
            "pane_a": "audit:a",
            "pane_b": "audit:b",
            "room_id": room_id,
            "bridge_id": "audit-bridge",
        })
        server_mod.handle_room_post({
            "room_id": room_id,
            "author": "human-operator",
            "text": "ship it",
            "deliver": "a",
            "bridge_id": "audit-bridge",
        })

        result = server_mod.handle_audit_recent({
            "room_id": room_id,
            "event": "operator.room_post",
            "limit": 5,
        })

        assert result["count"] == 1
        assert result["audit"]["enabled"] is True
        assert result["audit"]["redaction"]["mode"] == "mask"
        assert result["audit"]["redaction"]["stores_raw_text"] is False
        assert result["events"][0]["event"] == "operator.room_post"
        assert result["events"][0]["message_id"] == 1

    @patch.object(server_mod, "_make_backend")
    def test_audit_recent_resolves_workstream_id(self, mock_factory, tmp_path, monkeypatch):
        mock_backend = MagicMock()
        mock_backend.capture_both.return_value = ([], [])
        mock_factory.return_value = mock_backend
        monkeypatch.setenv("TB2_AUDIT_DIR", str(tmp_path))
        monkeypatch.setattr(server_mod, "_audit_trail", AuditTrail(tmp_path))

        server_mod.handle_bridge_start({
            "pane_a": "ws:a",
            "pane_b": "ws:b",
            "room_id": "ws-audit-room",
            "bridge_id": "ws-audit-bridge",
            "workstream_id": "ws-audit-main",
        })
        server_mod.handle_room_post({
            "room_id": "ws-audit-room",
            "author": "human-operator",
            "text": "review this",
        })

        result = server_mod.handle_audit_recent({
            "workstream_id": "ws-audit-main",
            "event": "operator.room_post",
            "limit": 5,
        })

        assert result["count"] == 1
        assert result["scope"]["workstream_id"] == "ws-audit-main"
        assert result["scope"]["room_id"] == "ws-audit-room"
        assert result["events"][0]["event"] == "operator.room_post"

    @patch.object(server_mod, "_make_backend")
    def test_audit_recent_masks_room_terminal_and_intervention_text(self, mock_factory, tmp_path, monkeypatch):
        mock_backend = MagicMock()
        mock_backend.capture_both.return_value = ([], [])
        mock_factory.return_value = mock_backend
        monkeypatch.setenv("TB2_AUDIT_DIR", str(tmp_path))
        monkeypatch.setattr(server_mod, "_audit_trail", AuditTrail(tmp_path))
        room_id = "audit-redaction-room"

        server_mod.handle_room_create({"room_id": room_id})
        server_mod.handle_room_post({
            "room_id": room_id,
            "author": "human-operator",
            "text": "ship it now",
        })
        server_mod.handle_terminal_send({
            "target": "audit:redaction",
            "text": "TOKEN=12345",
            "enter": True,
        })
        server_mod.handle_bridge_start({
            "pane_a": "audit:a",
            "pane_b": "audit:b",
            "room_id": room_id,
            "bridge_id": "audit-redaction-bridge",
            "auto_forward": True,
            "intervention": True,
        })
        bridge = server_mod._get_bridge("audit-redaction-bridge")
        assert bridge is not None
        profile = server_mod.get_profile("generic")
        bridge._process_new_lines(
            "A",
            "audit:a",
            "audit:b",
            ["MSG:echo TOKEN=12345"],
            profile,
        )

        result = server_mod.handle_audit_recent({"limit": 10})
        raw = (tmp_path / "events.jsonl").read_text(encoding="utf-8")
        room_event = next(item for item in result["events"] if item["event"] == "room.message")
        posted_event = next(item for item in result["events"] if item["event"] == "room.message_posted")
        sent_event = next(item for item in result["events"] if item["event"] == "terminal.sent")
        submitted_event = next(item for item in result["events"] if item["event"] == "intervention.submitted")

        assert "ship it now" not in raw
        assert "TOKEN=12345" not in raw
        assert result["audit"]["redaction"]["mode"] == "mask"
        assert room_event["message"]["text"] == "[redacted]"
        assert room_event["message"]["text_redacted"] is True
        assert room_event["message"]["text_mode"] == "mask"
        assert posted_event["payload"]["text"] == "[redacted]"
        assert posted_event["payload"]["text_redacted"] is True
        assert posted_event["payload"]["text_mode"] == "mask"
        assert sent_event["text"] == "[redacted]"
        assert sent_event["text_redacted"] is True
        assert sent_event["text_mode"] == "mask"
        assert submitted_event["text"] == "[redacted]"
        assert submitted_event["text_redacted"] is True
        assert submitted_event["text_mode"] == "mask"

    def test_audit_recent_covers_guard_and_reject_lifecycle_events(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TB2_AUDIT_DIR", str(tmp_path))
        monkeypatch.setattr(server_mod, "_audit_trail", AuditTrail(tmp_path))
        room = create_room("audit-guard-review")
        bridge = server_mod.Bridge(
            bridge_id="audit-guard-bridge",
            backend=MagicMock(),
            room=room,
            pane_a="audit:a",
            pane_b="audit:b",
            auto_forward=True,
        )
        with server_mod._bridges_lock:
            server_mod._bridges[bridge.bridge_id] = bridge

        profile = server_mod.get_profile("generic")
        with patch.object(server_mod.time, "time", return_value=100.0):
            bridge._process_new_lines(
                "A",
                "audit:a",
                "audit:b",
                [f"MSG:echo {i}" for i in range(7)],
                profile,
            )

        pending = bridge.intervention_layer.list_pending()
        assert len(pending) == 1

        result = server_mod.handle_intervention_reject({
            "bridge_id": bridge.bridge_id,
            "id": pending[0].id,
        })

        assert result["rejected"] == 1
        guard_blocked = server_mod.handle_audit_recent({
            "bridge_id": bridge.bridge_id,
            "event": "bridge.guard_blocked",
            "limit": 5,
        })
        guard_rearmed = server_mod.handle_audit_recent({
            "bridge_id": bridge.bridge_id,
            "event": "bridge.guard_rearmed",
            "limit": 5,
        })
        rejected = server_mod.handle_audit_recent({
            "bridge_id": bridge.bridge_id,
            "event": "intervention.rejected",
            "limit": 5,
        })

        assert guard_blocked["count"] == 1
        assert guard_blocked["events"][0]["reason"] == "[redacted]"
        assert guard_blocked["events"][0]["reason_redacted"] is True
        assert guard_blocked["events"][0]["reason_mode"] == "mask"
        assert guard_rearmed["count"] == 1
        assert rejected["count"] == 1
        assert rejected["events"][0]["rejected"] == 1
        assert rejected["events"][0]["remaining"] == 0

    @patch.object(server_mod, "_make_backend")
    def test_audit_recent_covers_bridge_start_existing_conflict_and_failure(self, mock_factory, tmp_path, monkeypatch):
        mock_backend = MagicMock()
        mock_backend.capture_both.return_value = ([], [])
        mock_factory.return_value = mock_backend
        monkeypatch.setenv("TB2_AUDIT_DIR", str(tmp_path))
        monkeypatch.setattr(server_mod, "_audit_trail", AuditTrail(tmp_path))

        first = server_mod.handle_bridge_start({
            "pane_a": "audit:a",
            "pane_b": "audit:b",
            "room_id": "audit-room-a",
            "bridge_id": "audit-bridge-a",
        })
        assert first["bridge_id"] == "audit-bridge-a"

        existing = server_mod.handle_bridge_start({
            "pane_a": "audit:a",
            "pane_b": "audit:b",
            "room_id": "audit-room-a",
        })
        assert existing["existing"] is True

        conflict = server_mod.handle_bridge_start({
            "pane_a": "audit:a",
            "pane_b": "audit:b",
            "room_id": "audit-room-b",
        })
        assert "pane pair already bridged" in conflict["error"]

        mock_backend.capture_both.side_effect = RuntimeError("capture failed")
        failed = server_mod.handle_bridge_start({
            "pane_a": "audit:c",
            "pane_b": "audit:d",
            "room_id": "audit-room-c",
        })
        assert failed["error"] == "bridge preflight failed: capture failed"

        existing_events = server_mod.handle_audit_recent({
            "event": "bridge.start_existing",
            "limit": 5,
        })
        conflict_events = server_mod.handle_audit_recent({
            "event": "bridge.start_conflict",
            "limit": 5,
        })
        failed_events = server_mod.handle_audit_recent({
            "event": "bridge.start_failed",
            "limit": 5,
        })

        assert existing_events["count"] == 1
        assert existing_events["events"][0]["reason"] == "pane_pair_existing"
        assert conflict_events["count"] == 1
        assert conflict_events["events"][0]["reason"] == "pane_pair_room_conflict"
        assert failed_events["count"] == 1
        assert failed_events["events"][0]["reason"] == "preflight_failed"
        assert failed_events["events"][0]["reason_mode"] == "code"
        assert failed_events["events"][0]["error"] == "[redacted]"
        assert failed_events["events"][0]["error_redacted"] is True


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
    def test_bridge_start_rejects_invalid_room_id(self, mock_factory):
        mock_backend = MagicMock()
        mock_backend.capture_both.return_value = ([], [])
        mock_factory.return_value = mock_backend

        result = server_mod.handle_bridge_start({
            "pane_a": "test:a",
            "pane_b": "test:b",
            "room_id": "bad room",
        })
        assert result["error"] == "invalid room_id"

    @patch.object(server_mod, "_make_backend")
    def test_bridge_start_rejects_invalid_bridge_id(self, mock_factory):
        mock_backend = MagicMock()
        mock_backend.capture_both.return_value = ([], [])
        mock_factory.return_value = mock_backend

        result = server_mod.handle_bridge_start({
            "pane_a": "test:a",
            "pane_b": "test:b",
            "bridge_id": "bad bridge",
        })
        assert result["error"] == "invalid bridge_id"

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
    def test_bridge_start_same_panes_does_not_create_extra_room(self, mock_factory):
        mock_backend = MagicMock()
        mock_backend.capture_both.return_value = ([], [])
        mock_factory.return_value = mock_backend

        first = server_mod.handle_bridge_start({
            "pane_a": "test:a",
            "pane_b": "test:b",
            "room_id": "same-room",
            "bridge_id": "br-first",
        })
        before = sorted(room.room_id for room in list_rooms())

        second = server_mod.handle_bridge_start({
            "pane_a": "test:a",
            "pane_b": "test:b",
        })
        after = sorted(room.room_id for room in list_rooms())

        assert second["existing"] is True
        assert second["bridge_id"] == first["bridge_id"]
        assert after == before

        server_mod.handle_bridge_stop({"bridge_id": "br-first"})

    @patch.object(server_mod, "_make_backend")
    def test_bridge_start_same_panes_without_room_id_does_not_create_orphan_room(self, mock_factory):
        mock_backend = MagicMock()
        mock_backend.capture_both.return_value = ([], [])
        mock_factory.return_value = mock_backend

        first = server_mod.handle_bridge_start({
            "pane_a": "test:a",
            "pane_b": "test:b",
            "bridge_id": "br-auto-room",
        })
        before = {room.room_id for room in server_mod.list_rooms()}

        second = server_mod.handle_bridge_start({
            "pane_a": "test:a",
            "pane_b": "test:b",
        })
        after = {room.room_id for room in server_mod.list_rooms()}

        assert second["existing"] is True
        assert second["bridge_id"] == first["bridge_id"]
        assert after == before

        server_mod.handle_bridge_stop({"bridge_id": "br-auto-room"})

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
    def test_bridge_start_existing_bridge_id_rejects_conflicting_room(self, mock_factory):
        mock_backend = MagicMock()
        mock_backend.capture_both.return_value = ([], [])
        mock_factory.return_value = mock_backend

        server_mod.handle_bridge_start({
            "pane_a": "test:a",
            "pane_b": "test:b",
            "room_id": "room-a",
            "bridge_id": "br-room-match",
        })
        result = server_mod.handle_bridge_start({
            "pane_a": "test:a",
            "pane_b": "test:b",
            "room_id": "room-b",
            "bridge_id": "br-room-match",
        })

        assert result["error"] == "bridge_id br-room-match already maps to room room-a, not room-b"

        server_mod.handle_bridge_stop({"bridge_id": "br-room-match"})

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
        assert get_room("broken-room") is None

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

    def test_bridge_process_new_lines_adds_machine_readable_sources(self):
        backend = MagicMock()
        room = create_room("bridge-source")
        bridge = server_mod.Bridge(
            bridge_id="br-source",
            backend=backend,
            room=room,
            pane_a="test:a",
            pane_b="test:b",
            auto_forward=True,
        )

        profile = server_mod.get_profile("generic")
        bridge._process_new_lines("A", "test:a", "test:b", ["MSG:echo HELLO"], profile)
        messages = [server_mod._room_message_payload(room, msg) for msg in room.poll(after_id=0, limit=10)]

        assert messages[0]["source_type"] == "terminal"
        assert messages[0]["source_role"] == "pane_a"
        assert messages[0]["trusted"] is False
        assert messages[1]["source_type"] == "bridge"
        assert messages[1]["source_role"] == "automation"
        assert messages[1]["trusted"] is True
        assert messages[1]["source"]["trusted"] is True

    def test_bridge_auto_forward_breaker_switches_to_intervention(self):
        backend = MagicMock()
        room = create_room("bridge-breaker")
        bridge = server_mod.Bridge(
            bridge_id="br-breaker",
            backend=backend,
            room=room,
            pane_a="test:a",
            pane_b="test:b",
            auto_forward=True,
        )

        profile = server_mod.get_profile("generic")
        with patch.object(server_mod.time, "time", return_value=100.0):
            bridge._process_new_lines(
                "A",
                "test:a",
                "test:b",
                [f"MSG:echo {i}" for i in range(7)],
                profile,
            )

        assert backend.send.call_count == server_mod._AUTO_FORWARD_MAX_PER_WINDOW
        with patch.object(server_mod.time, "time", return_value=100.0):
            detail = server_mod._bridge_detail(bridge)
        assert detail["auto_forward_guard"]["blocked"] is True
        assert detail["auto_forward_guard"]["guard_reason"] is not None
        assert detail["pending_count"] == 1
        messages = [server_mod._room_message_payload(room, msg) for msg in room.poll(after_id=0, limit=50)]
        breaker = [msg for msg in messages if msg["meta"].get("guard_reason")]
        assert len(breaker) == 1
        assert breaker[0]["source_role"] == "safety"
        pending = [msg for msg in messages if msg["kind"] == "intervention" and msg["meta"].get("pending_id")]
        assert len(pending) == 1

    def test_bridge_auto_forward_breaker_uses_pending_queue_after_trip(self):
        backend = MagicMock()
        room = create_room("bridge-breaker-reset")
        bridge = server_mod.Bridge(
            bridge_id="br-breaker-reset",
            backend=backend,
            room=room,
            pane_a="test:a",
            pane_b="test:b",
            auto_forward=True,
        )

        profile = server_mod.get_profile("generic")
        with patch.object(server_mod.time, "time", return_value=100.0):
            bridge._process_new_lines(
                "A",
                "test:a",
                "test:b",
                [f"MSG:echo {i}" for i in range(7)],
                profile,
            )
        bridge._process_new_lines("A", "test:a", "test:b", ["MSG:echo again"], profile)

        assert backend.send.call_count == server_mod._AUTO_FORWARD_MAX_PER_WINDOW
        assert bridge.intervention_layer.active is True
        assert len(bridge.intervention_layer.list_pending()) == 2

    def test_bridge_auto_forward_breaker_rearms_after_review(self):
        backend = MagicMock()
        room = create_room("bridge-breaker-rearm")
        bridge = server_mod.Bridge(
            bridge_id="br-breaker-rearm",
            backend=backend,
            room=room,
            pane_a="test:a",
            pane_b="test:b",
            auto_forward=True,
        )
        with server_mod._bridges_lock:
            server_mod._bridges[bridge.bridge_id] = bridge

        profile = server_mod.get_profile("generic")
        with patch.object(server_mod.time, "time", return_value=100.0):
            bridge._process_new_lines(
                "A",
                "test:a",
                "test:b",
                [f"MSG:echo {i}" for i in range(7)],
                profile,
            )

        pending = bridge.intervention_layer.list_pending()
        assert len(pending) == 1

        result = server_mod.handle_intervention_approve({
            "bridge_id": bridge.bridge_id,
            "id": pending[0].id,
        })

        assert result["approved"] == 1
        assert bridge.intervention_layer.active is False
        assert bridge.auto_forward_guard()["blocked"] is False

        bridge._process_new_lines("A", "test:a", "test:b", ["MSG:echo rearmed"], profile)

        assert backend.send.call_count == server_mod._AUTO_FORWARD_MAX_PER_WINDOW + 2

    def test_bridge_auto_forward_streak_limit_switches_to_intervention(self):
        backend = MagicMock()
        room = create_room("bridge-streak")
        bridge = server_mod.Bridge(
            bridge_id="br-streak",
            backend=backend,
            room=room,
            pane_a="test:a",
            pane_b="test:b",
            auto_forward=True,
        )
        bridge._auto_forward_streak = server_mod._AUTO_FORWARD_STREAK_LIMIT

        profile = server_mod.get_profile("generic")
        bridge._process_new_lines("A", "test:a", "test:b", ["MSG:echo streak"], profile)

        assert backend.send.call_count == 0
        assert bridge.intervention_layer.active is True
        detail = server_mod._bridge_detail(bridge)
        assert "consecutive auto-forwards" in detail["auto_forward_guard"]["guard_reason"]

    def test_bridge_worker_waits_once_per_cycle(self):
        backend = MagicMock()
        backend.capture_both.side_effect = [
            ([], []),
            (["MSG:echo HELLO", "plain"], []),
            server_mod.TmuxError("stop"),
        ]
        room = create_room("bridge-sleep")
        bridge = server_mod.Bridge(
            bridge_id="br-sleep",
            backend=backend,
            room=room,
            pane_a="test:a",
            pane_b="test:b",
            auto_forward=False,
            poll_ms=400,
        )
        bridge.stop.wait = MagicMock(return_value=False)

        bridge.worker()

        bridge.stop.wait.assert_called_once_with(timeout=0.1)

    def test_bridge_worker_backoff_when_idle(self):
        backend = MagicMock()
        backend.capture_both.side_effect = [
            ([], []),
            ([], []),
            ([], []),
        ]
        room = create_room("bridge-backoff")
        bridge = server_mod.Bridge(
            bridge_id="br-backoff",
            backend=backend,
            room=room,
            pane_a="test:a",
            pane_b="test:b",
            auto_forward=False,
            poll_ms=400,
        )
        bridge.stop.wait = MagicMock(side_effect=[False, True])

        bridge.worker()

        waits = [call.kwargs["timeout"] for call in bridge.stop.wait.call_args_list]
        assert waits == [0.6, 0.9]


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

    @patch.object(server_mod, "_make_backend")
    def test_intervention_list_resolves_single_bridge_without_id(self, mock_factory):
        mock_backend = MagicMock()
        mock_backend.capture_both.return_value = ([], [])
        mock_factory.return_value = mock_backend

        create_room("single-int")
        server_mod.handle_bridge_start({
            "pane_a": "single:a",
            "pane_b": "single:b",
            "room_id": "single-int",
            "bridge_id": "br-single",
            "intervention": True,
        })

        result = server_mod.handle_intervention_list({})
        assert result["bridge_id"] == "br-single"
        assert result["count"] == 0

    @patch.object(server_mod, "_make_backend")
    def test_intervention_list_resolves_bridge_from_room(self, mock_factory):
        mock_backend = MagicMock()
        mock_backend.capture_both.return_value = ([], [])
        mock_factory.return_value = mock_backend

        create_room("room-int")
        server_mod.handle_bridge_start({
            "pane_a": "room:a",
            "pane_b": "room:b",
            "room_id": "room-int",
            "bridge_id": "br-room-int",
            "intervention": True,
        })

        result = server_mod.handle_intervention_list({"room_id": "room-int"})
        assert result["bridge_id"] == "br-room-int"

    @patch.object(server_mod, "_make_backend")
    def test_intervention_list_requires_disambiguation_with_multiple_bridges(self, mock_factory):
        mock_backend = MagicMock()
        mock_backend.capture_both.return_value = ([], [])
        mock_factory.return_value = mock_backend

        create_room("multi-a")
        create_room("multi-b")
        server_mod.handle_bridge_start({
            "pane_a": "multi:a",
            "pane_b": "multi:b",
            "room_id": "multi-a",
            "bridge_id": "br-multi-a",
            "intervention": True,
        })
        server_mod.handle_bridge_start({
            "pane_a": "multi:c",
            "pane_b": "multi:d",
            "room_id": "multi-b",
            "bridge_id": "br-multi-b",
            "intervention": True,
        })

        result = server_mod.handle_intervention_list({})
        assert result["error"] == "bridge_id required: multiple active bridges"
        assert len(result["bridge_candidates"]) == 2

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

    @patch.object(server_mod, "_make_backend")
    def test_terminal_interrupt_resolves_bridge_from_room(self, mock_factory):
        mock_backend = MagicMock()
        mock_backend.capture_both.return_value = ([], [])
        mock_factory.return_value = mock_backend

        create_room("interrupt-room")
        server_mod.handle_bridge_start({
            "pane_a": "i:a",
            "pane_b": "i:b",
            "room_id": "interrupt-room",
            "bridge_id": "br-interrupt",
            "intervention": True,
        })

        result = server_mod.handle_terminal_interrupt({"room_id": "interrupt-room", "target": "a"})
        assert result["bridge_id"] == "br-interrupt"
        assert result["sent"] == ["i:a"]
        mock_backend.send.assert_called_with("i:a", "\x03", enter=False)


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

    def test_tools_list_exposes_bridge_resolution_schema(self):
        result = self._rpc({"jsonrpc": "2.0", "id": 13, "method": "tools/list", "params": {}})
        tools = {tool["name"]: tool for tool in result["result"]["tools"]}
        bridge_start = tools["bridge_start"]["inputSchema"]
        assert bridge_start["required"] == ["pane_a", "pane_b"]
        assert bridge_start["properties"]["tier"]["enum"] == ["main", "sub"]
        assert bridge_start["properties"]["parent_workstream_id"]["type"] == "string"
        workstream_get = tools["workstream_get"]["inputSchema"]
        assert workstream_get["required"] == ["workstream_id"]
        pause = tools["workstream_pause_review"]["inputSchema"]
        assert pause["properties"]["workstream_id"]["type"] == "string"
        resume = tools["workstream_resume_review"]["inputSchema"]
        assert resume["properties"]["bridge_id"]["type"] == "string"
        update_policy = tools["workstream_update_policy"]["inputSchema"]
        assert update_policy["required"] == ["workstream_id"]
        assert update_policy["properties"]["silent_seconds"]["minimum"] == 5
        assert update_policy["properties"]["pending_limit"]["minimum"] == 1
        update_dependency = tools["workstream_update_dependency"]["inputSchema"]
        assert update_dependency["properties"]["tier"]["enum"] == ["main", "sub"]
        workstream_stop = tools["workstream_stop"]["inputSchema"]
        assert workstream_stop["properties"]["cleanup_room"]["type"] == "boolean"
        assert workstream_stop["properties"]["cascade"]["type"] == "boolean"
        fleet_reconcile = tools["fleet_reconcile"]["inputSchema"]
        assert fleet_reconcile["properties"]["apply"]["type"] == "boolean"
        intervention_list = tools["intervention_list"]["inputSchema"]
        assert intervention_list["properties"]["bridge_id"]["type"] == "string"
        assert intervention_list["properties"]["room_id"]["type"] == "string"
        approve = tools["intervention_approve"]["inputSchema"]
        assert "id" in approve["properties"]
        assert "edited_text" in approve["properties"]
        audit_recent = tools["audit_recent"]["inputSchema"]
        assert audit_recent["properties"]["workstream_id"]["type"] == "string"
        assert audit_recent["properties"]["event"]["type"] == "string"
        assert audit_recent["properties"]["limit"]["maximum"] == 200
        governance_resolve = tools["governance_resolve"]["inputSchema"]
        assert governance_resolve["properties"]["model"]["type"] == "string"
        assert governance_resolve["properties"]["config_path"]["type"] == "string"

    @patch.object(server_mod, "_make_backend")
    def test_tools_call_workstream_list_returns_structured_payload(self, mock_factory):
        mock_backend = MagicMock()
        mock_backend.capture_both.return_value = ([], [])
        mock_factory.return_value = mock_backend
        server_mod.handle_bridge_start({
            "pane_a": "rpc:a",
            "pane_b": "rpc:b",
            "room_id": "rpc-room",
            "bridge_id": "rpc-bridge",
            "workstream_id": "rpc-main",
        })

        result = self._rpc({
            "jsonrpc": "2.0",
            "id": 15,
            "method": "tools/call",
            "params": {"name": "workstream_list", "arguments": {}},
        })

        tool_result = result["result"]
        assert tool_result["structuredContent"]["count"] == 1
        assert tool_result["structuredContent"]["workstreams"][0]["workstream_id"] == "rpc-main"
        assert tool_result["structuredContent"]["workstreams"][0]["dependency"]["tier"] == "main"
        assert tool_result["structuredContent"]["reconciliation"]["orphaned_rooms"] == []
        assert tool_result.get("isError") is not True

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

    def test_tools_call_governance_resolve_returns_resolution(self, tmp_path):
        config = tmp_path / "governance.json"
        config.write_text(json.dumps({
            "instruction_profile": {
                "approval-gate": {
                    "approval_mode": "strict-required",
                }
            }
        }), encoding="utf-8")

        result = self._rpc({
            "jsonrpc": "2.0",
            "id": 16,
            "method": "tools/call",
            "params": {
                "name": "governance_resolve",
                "arguments": {
                    "environment": "wsl-tmux",
                    "instruction_profile": "approval-gate",
                    "config_path": str(config),
                },
            },
        })

        tool_result = result["result"]["structuredContent"]
        assert tool_result["effective_config"]["preferred_backend"] == "tmux"
        assert tool_result["effective_config"]["approval_mode"] == "strict-required"
        assert tool_result["provenance"]["approval_mode"] == {
            "layer": "instruction_profile",
            "name": "approval-gate",
        }

    def test_tools_call_governance_resolve_returns_error(self, tmp_path):
        config = tmp_path / "governance.json"
        config.write_text(json.dumps({
            "unknown": {
                "demo": {"x": 1},
            }
        }), encoding="utf-8")

        result = self._rpc({
            "jsonrpc": "2.0",
            "id": 17,
            "method": "tools/call",
            "params": {
                "name": "governance_resolve",
                "arguments": {
                    "config_path": str(config),
                },
            },
        })

        tool_result = result["result"]
        assert tool_result["structuredContent"]["error"] == "unknown governance layer: unknown"
        assert tool_result["isError"] is True

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
        assert "Terminal Bridge" in html
        assert "Host, Guest, and Human operator workflow" in html
        assert "/mcp" in html
        assert 'data-lang="en"' in html
        assert 'data-lang="zh-TW"' in html
        assert 'data-layout-mode="wide"' in html
        assert 'data-layout-mode="stacked"' in html
        assert "快速配對" in html
        assert "Handoff Radar" in html
        assert "Quiet Loop" in html
        assert "Mission Control" in html
        assert "bridge_candidates" in html

    def test_gui_html_surfaces_audit_panel(self):
        html = server_mod.build_gui_html("/mcp")
        assert 'id="refresh-audit"' in html
        assert 'id="audit-box"' in html
        assert 'id="audit-note"' in html
        assert 'id="audit-event"' in html
        assert 'id="audit-limit"' in html
        assert "audit_recent" in html
        assert "bridge.start_conflict" in html
        assert "bridge.start_failed" in html

    def test_gui_html_surfaces_remediation_controls(self):
        html = server_mod.build_gui_html("/mcp")
        assert 'id="pause-review"' in html
        assert 'id="resume-review"' in html
        assert 'id="stop-workstream"' in html
        assert 'id="reconcile-fleet"' in html
        assert "async function pauseReview()" in html
        assert "async function resumeReview()" in html
        assert "async function stopWorkstream()" in html
        assert "async function reconcileFleet()" in html
        assert "tool('workstream_pause_review'" in html
        assert "tool('workstream_resume_review'" in html
        assert "tool('workstream_stop'" in html
        assert "tool('fleet_reconcile'" in html
        assert "$('pause-review').onclick = () => run(pauseReview);" in html
        assert "$('resume-review').onclick = () => run(resumeReview);" in html
        assert "$('stop-workstream').onclick = () => run(stopWorkstream);" in html
        assert "$('reconcile-fleet').onclick = () => run(reconcileFleet);" in html

    def test_gui_html_wires_audit_filters_to_refresh(self):
        html = server_mod.build_gui_html("/mcp")
        assert "$('audit-event').onchange = () => run(refreshAudit);" in html
        assert "$('audit-limit').onchange = () => run(refreshAudit);" in html
        assert "if (event) args.event = event;" in html
        assert "cards.auditRedaction" in html
        assert "cards.auditRedactionRequested" in html
        assert "cards.auditRedactionFullWarning" in html
        assert "cards.auditRedactionFullBlocked" in html
        assert "audit.redaction && audit.redaction.stores_raw_text" in html
        assert "audit.redaction && audit.redaction.raw_text_opt_in_blocked" in html
        assert "audit.redaction.requested_mode !== audit.redaction.mode" in html

    def test_gui_html_refreshes_status_after_review_actions(self):
        html = server_mod.build_gui_html("/mcp")
        assert "async function refreshReviewState()" in html
        assert "await refreshReviewState();" in html
        assert "await refreshAudit();" in html
        assert ".then(() => refreshReviewState())" in html

    def test_gui_html_clears_stale_bridge_state_after_stop(self):
        html = server_mod.build_gui_html("/mcp")
        assert "function clearBridgeState()" in html
        assert "$('bridge-id').value = '';" in html
        assert "fillPending([]);" in html
        assert "clearBridgeState();" in html
        assert "function isInactiveBridgeError(message)" in html
        assert "message === 'bridge not found'" in html
        assert "message.startsWith('no active bridge for room ')" in html

    def test_gui_html_refreshes_audit_after_operator_actions(self):
        html = server_mod.build_gui_html("/mcp")
        assert html.count("await refreshAudit();") >= 3

    def test_gui_html_surfaces_pending_review_detail(self):
        html = server_mod.build_gui_html("/mcp")
        assert 'id="pending-detail"' in html
        assert "function renderPendingDetail()" in html
        assert "state.pendingItems = Array.isArray(items) ? items : [];" in html
        assert "$('pending-select').onchange = () => renderPendingDetail();" in html

    def test_gui_html_surfaces_workstream_fleet(self):
        html = server_mod.build_gui_html("/mcp")
        assert 'id="workstream-list"' in html
        assert 'id="fleet-summary-meta"' in html
        assert "function renderWorkstreamFleet(status)" in html
        assert "const recovery = status && status.recovery ? status.recovery : null;" in html
        assert "const manualTakeover = Number(recovery.manual_takeover_count || 0) || 0;" in html
        assert "selectedWorkstreamId:" in html
        assert "if (workstreamId) args.workstream_id = workstreamId;" in html

    def test_gui_html_surfaces_status_summary_badges(self):
        html = server_mod.build_gui_html("/mcp")
        assert 'id="status-badges"' in html
        assert 'id="status-governance"' in html
        assert "function renderStatusSummary(status)" in html
        assert "function statusSummaryLabels(status, detail, subscribers)" in html
        assert "function workstreamDependencyLabel(detail)" in html
        assert "function workstreamDependencyBlocker(detail)" in html
        assert "function governanceMatchedLayers(status)" in html
        assert "function governanceSummaryText(status)" in html
        assert "function governancePrimaryName(status)" in html
        assert "cards.statusBadgeAuditRaw" in html
        assert "cards.statusBadgeAuditRawBlocked" in html
        assert "cards.statusBadgeSecurity" in html
        assert "cards.statusBadgeHealth" in html
        assert "cards.statusBadgeEscalation" in html
        assert "cards.statusBadgeGovernance" in html
        assert "cards.statusBadgeReviewMode" in html
        assert "cards.statusBadgeBackend" in html
        assert "cards.governanceSummary" in html
        assert "cards.inspectTileGovernance" in html
        assert "active.auto_forward_guard && active.auto_forward_guard.quota_reason" in html
        assert "workstreamDependencyBlocker(active)" in html
        assert "cards.inspectTileDependency" in html
        assert "status.audit.redaction && status.audit.redaction.raw_text_opt_in_blocked" in html
        assert "status.audit.redaction && status.audit.redaction.stores_raw_text" in html
        assert "format('cards.statusBadgePending'" in html
        assert "if (governance) governance.textContent = governanceSummaryText(status);" in html
        assert "renderStatusSummary(res);" in html

    @pytest.mark.skipif(shutil.which("node") is None, reason="node is required for GUI behavior tests")
    def test_gui_behavior_formats_blocked_audit_note(self):
        html = server_mod.build_gui_html("/mcp")

        note = _run_gui_function(
            html,
            "auditNoteText",
            """auditNoteText(
              {
                enabled: true,
                file: '/tmp/events.jsonl',
                redaction: {
                  mode: 'mask',
                  requested_mode: 'full',
                  raw_text_opt_in_blocked: true,
                  raw_text_opt_in_env: 'TB2_AUDIT_ALLOW_FULL_TEXT',
                  stores_raw_text: false
                }
              },
              'room-a',
              'all events',
              '12'
            )""",
        )

        assert "Audit trail is writing to /tmp/events.jsonl." in note
        assert "Persisted text fields are redacted (mask)." in note
        assert "Requested redaction mode is full; effective mode is mask." in note
        assert "Full mode was requested but is blocked until TB2_AUDIT_ALLOW_FULL_TEXT=1 is set." in note
        assert "Warning: full mode stores raw text in durable audit entries." not in note
        assert "Scope: room-a" in note

    @pytest.mark.skipif(shutil.which("node") is None, reason="node is required for GUI behavior tests")
    def test_gui_behavior_formats_blocked_audit_status_badges(self):
        html = server_mod.build_gui_html("/mcp")

        labels = _run_gui_function(
            html,
            "statusSummaryLabels",
            """statusSummaryLabels(
              {
                audit: {
                  enabled: true,
                  redaction: {
                    raw_text_opt_in_blocked: true,
                    stores_raw_text: false
                  }
                },
                security: {
                  support_tier: 'private-network-experimental'
                }
              },
              {
                health: {
                  state: 'critical',
                  escalation: 'intervene'
                },
                pending_count: 2,
                auto_forward_guard: { blocked: true }
              },
              {
                total: 1,
                sse: 0,
                websocket: 1
              }
            )""",
        )

        assert "Guard blocked" in labels
        assert "Pending 2" in labels
        assert "Subs 1 (sse 0 / ws 1)" in labels
        assert "Audit on" in labels
        assert "Audit raw blocked" in labels
        assert "Security private-network-experimental" in labels
        assert "Health critical" in labels
        assert "Escalation intervene" in labels
        assert "Audit raw text" not in labels

    @patch("tb2.gui.default_backend_name", return_value="tmux")
    def test_gui_html_marks_platform_default_backend(self, mock_default):
        html = server_mod.build_gui_html("/mcp")
        assert '<option value="tmux" selected>tmux</option>' in html
        mock_default.assert_called_once_with()

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
        assert payload["security"]["support_tier"] == "local-first-supported"

    def test_get_unknown_path(self):
        code, content_type, body = server_mod._handle_get_path("/missing")
        assert code == 404
        assert content_type == "application/json"
        payload = json.loads(body.decode("utf-8"))
        assert payload["error"] == "not found"


class TestHttpReplies:
    def test_reply_raw_sanitizes_header_value(self):
        handler = server_mod.MCPHandler.__new__(server_mod.MCPHandler)
        handler.wfile = MagicMock()
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()

        handler._reply_raw(200, "text/plain\r\nX-Evil: yes", b"ok")

        handler.send_response.assert_called_once_with(200)
        handler.send_header.assert_any_call("Content-Type", "text/plainX-Evil: yes")
        handler.send_header.assert_any_call("Content-Length", "2")
        handler.end_headers.assert_called_once_with()
        handler.wfile.write.assert_called_once_with(b"ok")


class TestValidationHelpers:
    def test_origin_allowed_accepts_localhost(self):
        assert server_mod._origin_allowed("http://127.0.0.1:3189")
        assert server_mod._origin_allowed("https://localhost")
        assert server_mod._origin_allowed("")

    def test_origin_allowed_rejects_non_local(self):
        assert not server_mod._origin_allowed("https://evil.example")
        assert not server_mod._origin_allowed("null")

    def test_run_server_rejects_non_loopback_without_ack(self):
        with pytest.raises(RuntimeError, match="non-loopback bind requires explicit acknowledgment"):
            server_mod.run_server(host="0.0.0.0", port=3189)

    def test_parse_room_stream_request_rejects_invalid_params(self):
        room_id, after_id, limit, error = server_mod._parse_room_stream_request(
            "/rooms/bad room/stream",
            "after_id=abc&limit=200",
        )
        assert room_id == "bad room"
        assert after_id == 0
        assert limit == 0
        assert error == "invalid room_id"

    def test_parse_room_stream_request_accepts_valid_params(self):
        room_id, after_id, limit, error = server_mod._parse_room_stream_request(
            "/rooms/demo-room/stream",
            "after_id=4&limit=20",
        )
        assert room_id == "demo-room"
        assert after_id == 4
        assert limit == 20
        assert error is None


class TestHttpRequestHandling:
    def test_do_get_room_stream_rejects_forbidden_origin(self):
        handler = server_mod.MCPHandler.__new__(server_mod.MCPHandler)
        handler.path = "/rooms/demo-room/stream"
        handler.headers = {"Origin": "https://evil.example"}
        handler._reply = MagicMock()
        handler._serve_room_sse = MagicMock()

        handler.do_GET()

        handler._reply.assert_called_once_with(403, {"error": "forbidden origin"})
        handler._serve_room_sse.assert_not_called()

    def test_do_get_websocket_rejects_forbidden_origin(self):
        handler = server_mod.MCPHandler.__new__(server_mod.MCPHandler)
        handler.path = "/ws"
        handler.headers = {"Origin": "https://evil.example"}
        handler._reply = MagicMock()
        handler._serve_websocket = MagicMock()

        handler.do_GET()

        handler._reply.assert_called_once_with(403, {"error": "forbidden origin"})
        handler._serve_websocket.assert_not_called()

    def test_do_post_requires_content_length(self):
        handler = server_mod.MCPHandler.__new__(server_mod.MCPHandler)
        handler.path = "/mcp"
        handler.headers = {}
        handler.rfile = io.BytesIO(b"{}")
        handler.connection = MagicMock()
        handler._reply = MagicMock()

        handler.do_POST()

        handler._reply.assert_called_once_with(400, {"error": "Content-Length is required"})

    def test_do_post_rejects_forbidden_origin(self):
        handler = server_mod.MCPHandler.__new__(server_mod.MCPHandler)
        handler.path = "/mcp"
        handler.headers = {"Origin": "https://evil.example", "Content-Length": "2"}
        handler.rfile = io.BytesIO(b"{}")
        handler.connection = MagicMock()
        handler._reply = MagicMock()

        handler.do_POST()

        handler._reply.assert_called_once_with(403, {"error": "forbidden origin"})

    def test_do_post_rejects_large_body(self):
        handler = server_mod.MCPHandler.__new__(server_mod.MCPHandler)
        handler.path = "/mcp"
        handler.headers = {"Content-Length": str(server_mod._MAX_BODY_BYTES + 1)}
        handler.rfile = io.BytesIO(b"")
        handler.connection = MagicMock()
        handler._reply = MagicMock()

        handler.do_POST()

        handler._reply.assert_called_once_with(
            413,
            {"error": "request too large", "max_bytes": server_mod._MAX_BODY_BYTES},
        )

    def test_do_post_times_out_on_slow_body(self):
        handler = server_mod.MCPHandler.__new__(server_mod.MCPHandler)
        handler.path = "/mcp"
        handler.headers = {"Content-Length": "2"}
        handler.rfile = MagicMock()
        handler.rfile.read.side_effect = socket.timeout()
        handler.connection = MagicMock()
        handler._reply = MagicMock()

        handler.do_POST()

        handler.connection.settimeout.assert_called_once_with(server_mod._HTTP_READ_TIMEOUT_SECONDS)
        handler._reply.assert_called_once_with(408, {"error": "request body read timed out"})

    def test_do_post_rejects_incomplete_body(self):
        handler = server_mod.MCPHandler.__new__(server_mod.MCPHandler)
        handler.path = "/mcp"
        handler.headers = {"Content-Length": "2"}
        handler.rfile = io.BytesIO(b"{")
        handler.connection = MagicMock()
        handler._reply = MagicMock()

        handler.do_POST()

        handler.connection.settimeout.assert_called_once_with(server_mod._HTTP_READ_TIMEOUT_SECONDS)
        handler._reply.assert_called_once_with(400, {"error": "incomplete request body"})


class TestWebsocketValidation:
    def test_subscribe_rejects_invalid_after_id(self):
        handler = server_mod.MCPHandler.__new__(server_mod.MCPHandler)
        handler._ws_send = MagicMock()

        handler._handle_ws_message(
            {"action": "subscribe", "room_id": "demo-room", "after_id": "abc"},
            {},
        )

        handler._ws_send.assert_called_once_with(
            {"type": "error", "error": "after_id must be an integer", "action": "subscribe"}
        )
