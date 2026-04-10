"""Tests for tb2.server — MCP handler functions."""

import io
import json
import os
import shutil
import socket
import subprocess
from unittest.mock import MagicMock, patch

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
        room_ids = [r["id"] for r in result["rooms"]]
        assert "status-test" in room_ids
        assert result["bridges"] == ["status-bridge"]
        assert result["bridge_details"][0]["room_id"] == "status-test"
        assert result["bridge_details"][0]["workstream_id"] == "main-flow"
        assert result["bridge_details"][0]["profile"] == "codex"
        assert result["workstreams"][0]["workstream_id"] == "main-flow"
        assert result["workstreams"][0]["bridge_active"] is True
        assert result["workstreams"][0]["health"]["state"] == "ok"
        assert result["fleet"]["count"] == 1
        assert result["fleet"]["live"] == 1
        assert result["fleet"]["healthy"] == 1
        assert result["fleet"]["alerts"] == 0
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
        server_mod.handle_bridge_stop({"bridge_id": "silent-bridge"})

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
                                "blocked": False,
                                "guard_reason": None,
                                "rate_limit": 6,
                                "window_seconds": 3.0,
                                "streak_limit": 20,
                            },
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
        assert result["workstreams"][0]["workstream_id"] == "restored-main"
        assert result["workstreams"][0]["state"] == "restored"
        assert result["workstreams"][0]["pending_count"] == 1

        server_mod.handle_bridge_stop({"bridge_id": "restored-bridge"})

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
        assert "selectedWorkstreamId:" in html
        assert "if (workstreamId) args.workstream_id = workstreamId;" in html

    def test_gui_html_surfaces_status_summary_badges(self):
        html = server_mod.build_gui_html("/mcp")
        assert 'id="status-badges"' in html
        assert "function renderStatusSummary(status)" in html
        assert "function statusSummaryLabels(status, detail, subscribers)" in html
        assert "cards.statusBadgeAuditRaw" in html
        assert "cards.statusBadgeAuditRawBlocked" in html
        assert "cards.statusBadgeSecurity" in html
        assert "cards.statusBadgeHealth" in html
        assert "cards.statusBadgeEscalation" in html
        assert "status.audit.redaction && status.audit.redaction.raw_text_opt_in_blocked" in html
        assert "status.audit.redaction && status.audit.redaction.stores_raw_text" in html
        assert "format('cards.statusBadgePending'" in html
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
