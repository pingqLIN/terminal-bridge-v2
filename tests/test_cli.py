"""Tests for tb2.cli — CLI argument parsing and backend factory."""

import json
from unittest.mock import MagicMock, patch

import pytest

from tb2.cli import (
    _create_backend,
    _tool_call,
    build_parser,
    cmd_doctor,
    cmd_gui,
    cmd_init,
    cmd_room_approve,
    cmd_room_pending,
    cmd_room_reject,
    main,
)


class TestBuildParser:
    @patch("tb2.cli.default_backend_name", return_value="process")
    def test_default_backend_uses_platform_policy(self, mock_default):
        p = build_parser()
        args = p.parse_args(["init"])
        assert args.backend == "process"
        mock_default.assert_called_once_with()

    def test_init_defaults(self):
        p = build_parser()
        args = p.parse_args(["init"])
        assert args.cmd == "init"
        assert args.session == "tb2"

    def test_init_custom_session(self):
        p = build_parser()
        args = p.parse_args(["init", "--session", "demo"])
        assert args.session == "demo"

    def test_capture_requires_target(self):
        p = build_parser()
        with pytest.raises(SystemExit):
            p.parse_args(["capture"])

    def test_send_requires_target_and_text(self):
        p = build_parser()
        with pytest.raises(SystemExit):
            p.parse_args(["send", "--target", "test:0.0"])

    def test_broker_args(self):
        p = build_parser()
        args = p.parse_args([
            "broker", "--a", "test:0.0", "--b", "test:0.1",
            "--profile", "codex", "--auto", "--intervention",
        ])
        assert args.a == "test:0.0"
        assert args.b == "test:0.1"
        assert args.profile == "codex"
        assert args.auto is True
        assert args.intervention is True

    def test_server_defaults(self):
        p = build_parser()
        args = p.parse_args(["server"])
        assert args.host == "127.0.0.1"
        assert args.port == 3189
        assert args.allow_remote is False

    def test_gui_defaults(self):
        p = build_parser()
        args = p.parse_args(["gui"])
        assert args.host == "127.0.0.1"
        assert args.port == 3189
        assert args.allow_remote is False
        assert args.no_browser is False

    def test_backend_choices(self):
        p = build_parser()
        args = p.parse_args(["--backend", "process", "init"])
        assert args.backend == "process"

    def test_invalid_backend(self):
        p = build_parser()
        with pytest.raises(SystemExit):
            p.parse_args(["--backend", "invalid", "init"])

    def test_service_start_defaults(self):
        p = build_parser()
        args = p.parse_args(["service", "start"])
        assert args.cmd == "service"
        assert args.service_cmd == "start"
        assert args.host == "127.0.0.1"
        assert args.port == 3189
        assert args.allow_remote is False
        assert args.force is False

    def test_service_logs_defaults(self):
        p = build_parser()
        args = p.parse_args(["service", "logs"])
        assert args.cmd == "service"
        assert args.service_cmd == "logs"
        assert args.lines == 120

    def test_service_audit_defaults(self):
        p = build_parser()
        args = p.parse_args(["service", "audit"])
        assert args.cmd == "service"
        assert args.service_cmd == "audit"
        assert args.lines == 120
        assert args.room_id == ""
        assert args.bridge_id == ""
        assert args.event == ""

    def test_profiles_verbose_flag(self):
        p = build_parser()
        args = p.parse_args(["profiles", "--verbose"])
        assert args.cmd == "profiles"
        assert args.verbose is True

    def test_doctor_json_flag(self):
        p = build_parser()
        args = p.parse_args(["doctor", "--json"])
        assert args.cmd == "doctor"
        assert args.json is True

    def test_room_watch_args(self):
        p = build_parser()
        args = p.parse_args(["room", "watch", "--room-id", "demo-room"])
        assert args.cmd == "room"
        assert args.room_cmd == "watch"
        assert args.room_id == "demo-room"
        assert args.transport == "auto"

    def test_room_approve_args(self):
        p = build_parser()
        args = p.parse_args(["room", "approve", "--bridge-id", "br-1", "--id", "7", "--text", "edited"])
        assert args.cmd == "room"
        assert args.room_cmd == "approve"
        assert args.bridge_id == "br-1"
        assert args.msg_id == 7
        assert args.text == "edited"

    def test_room_pending_room_id_args(self):
        p = build_parser()
        args = p.parse_args(["room", "pending", "--room-id", "demo-room"])
        assert args.cmd == "room"
        assert args.room_cmd == "pending"
        assert args.bridge_id == ""
        assert args.room_id == "demo-room"


class TestRoomCommands:
    @patch("tb2.cli._tool_call")
    def test_cmd_room_pending_uses_room_id(self, mock_tool):
        mock_tool.return_value = {"count": 0}
        args = build_parser().parse_args(["room", "pending", "--room-id", "demo-room"])
        result = cmd_room_pending(MagicMock(), args)
        assert result == 0
        mock_tool.assert_called_once_with(
            "http://127.0.0.1:3189",
            "intervention_list",
            {"room_id": "demo-room"},
        )

    @patch("tb2.cli._tool_call")
    def test_cmd_room_approve_uses_room_id(self, mock_tool):
        mock_tool.return_value = {"approved": 1}
        args = build_parser().parse_args(["room", "approve", "--room-id", "demo-room", "--id", "7"])
        result = cmd_room_approve(MagicMock(), args)
        assert result == 0
        mock_tool.assert_called_once_with(
            "http://127.0.0.1:3189",
            "intervention_approve",
            {"room_id": "demo-room", "id": 7},
        )

    @patch("tb2.cli._tool_call")
    def test_cmd_room_reject_uses_bridge_id_when_present(self, mock_tool):
        mock_tool.return_value = {"rejected": 1}
        args = build_parser().parse_args(["room", "reject", "--bridge-id", "br-1", "--id", "7"])
        result = cmd_room_reject(MagicMock(), args)
        assert result == 0
        mock_tool.assert_called_once_with(
            "http://127.0.0.1:3189",
            "intervention_reject",
            {"bridge_id": "br-1", "id": 7},
        )


class TestToolCall:
    @patch("tb2.cli.urllib.request.urlopen")
    def test_tool_call_surfaces_bridge_candidates_in_error(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {
                "result": {
                    "structuredContent": {
                        "error": "bridge resolution requires a bridge_id or room_id",
                        "bridge_candidates": [
                            {"bridge_id": "br-a", "room_id": "room-a"},
                            {"bridge_id": "br-b", "room_id": "room-b"},
                        ],
                    }
                }
            }
        ).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        with pytest.raises(RuntimeError, match=r"candidates: br-a \(room-a\), br-b \(room-b\)"):
            _tool_call("http://127.0.0.1:3189", "intervention_list", {})


class TestCreateBackend:
    def test_tmux_backend(self):
        p = build_parser()
        args = p.parse_args(["--backend", "tmux", "init"])
        backend = _create_backend(args)
        from tb2.backend import TmuxBackend
        assert isinstance(backend, TmuxBackend)

    def test_process_backend(self):
        p = build_parser()
        args = p.parse_args(["--backend", "process", "init"])
        backend = _create_backend(args)
        from tb2.process_backend import ProcessBackend
        assert isinstance(backend, ProcessBackend)

    def test_pipe_backend(self):
        p = build_parser()
        args = p.parse_args(["--backend", "pipe", "init"])
        backend = _create_backend(args)
        from tb2.pipe_backend import PipeBackend
        assert isinstance(backend, PipeBackend)

    def test_tmux_with_distro(self):
        p = build_parser()
        args = p.parse_args(["--backend", "tmux", "--distro", "Debian", "init"])
        backend = _create_backend(args)
        assert backend.distro == "Debian"


class TestMain:
    @patch("tb2.cli._create_backend")
    def test_keyboard_interrupt(self, mock_factory):
        mock_backend = MagicMock()
        mock_factory.return_value = mock_backend
        # Make the fn raise KeyboardInterrupt
        mock_backend.init_session.side_effect = KeyboardInterrupt
        p = build_parser()
        args = p.parse_args(["init"])
        args.fn = lambda b, a: (_ for _ in ()).throw(KeyboardInterrupt)
        with patch("tb2.cli.build_parser", return_value=p):
            with patch.object(p, "parse_args", return_value=args):
                result = main(["init"])
        assert result == 130

    @patch("tb2.cli._create_backend")
    def test_runtime_error(self, mock_factory):
        mock_factory.return_value = MagicMock()
        p = build_parser()
        args = p.parse_args(["service", "status"])
        args.fn = lambda b, a: (_ for _ in ()).throw(RuntimeError("boom"))
        with patch("tb2.cli.build_parser", return_value=p):
            with patch.object(p, "parse_args", return_value=args):
                result = main(["service", "status"])
        assert result == 3

    @patch("tb2.cli._create_backend")
    def test_room_command_skips_backend_creation(self, mock_factory):
        p = build_parser()
        args = p.parse_args(["room", "pending", "--bridge-id", "br-1"])
        args.fn = lambda b, a: 0
        with patch("tb2.cli.build_parser", return_value=p):
            with patch.object(p, "parse_args", return_value=args):
                result = main(["room", "pending", "--bridge-id", "br-1"])
        assert result == 0
        mock_factory.assert_not_called()


class TestGuiCommand:
    @patch("tb2.server.run_server")
    @patch("webbrowser.open")
    def test_cmd_gui_no_browser(self, mock_open, mock_run_server):
        p = build_parser()
        args = p.parse_args(["gui", "--host", "127.0.0.1", "--port", "3199", "--no-browser"])
        result = cmd_gui(MagicMock(), args)
        assert result == 0
        mock_run_server.assert_called_once_with(host="127.0.0.1", port=3199, allow_remote=False)
        mock_open.assert_not_called()


class TestInitCommand:
    def test_cmd_init_for_process_backend_prints_generic_next_step(self, capsys):
        backend = MagicMock()
        backend.init_session.return_value = ("demo:a", "demo:b")
        args = build_parser().parse_args(["--backend", "process", "init", "--session", "demo"])
        result = cmd_init(backend, args)
        out = capsys.readouterr().out
        assert result == 0
        assert "tmux attach" not in out
        assert "tb2 capture" in out


class TestDoctorCommand:
    @patch("tb2.cli.doctor_report")
    def test_cmd_doctor_json(self, mock_report, capsys):
        mock_report.return_value = {"platform": "Windows"}
        p = build_parser()
        args = p.parse_args(["doctor", "--json"])
        result = cmd_doctor(MagicMock(), args)
        out = capsys.readouterr().out
        assert result == 0
        assert '"platform": "Windows"' in out

    @patch("tb2.cli.render_doctor")
    @patch("tb2.cli.doctor_report")
    def test_cmd_doctor_text(self, mock_report, mock_render, capsys):
        mock_report.return_value = {"platform": "Windows"}
        mock_render.return_value = "doctor text"
        p = build_parser()
        args = p.parse_args(["doctor"])
        result = cmd_doctor(MagicMock(), args)
        out = capsys.readouterr().out
        assert result == 0
        assert "doctor text" in out


class TestServiceCommand:
    @patch("tb2.service.start_service")
    def test_service_start_dispatch(self, mock_start):
        p = build_parser()
        args = p.parse_args(["service", "start", "--host", "127.0.0.1", "--port", "3199"])
        mock_start.return_value.to_dict.return_value = {
            "running": True,
            "pid": 1234,
            "host": "127.0.0.1",
            "port": 3199,
            "state_file": "/tmp/state.json",
            "log_file": "/tmp/server.log",
        }
        result = args.fn(MagicMock(), args)
        assert result == 0
        mock_start.assert_called_once_with(host="127.0.0.1", port=3199, python_exe="", force=False, allow_remote=False)

    @patch("tb2.service.stop_service")
    def test_service_stop_dispatch(self, mock_stop):
        p = build_parser()
        args = p.parse_args(["service", "stop", "--timeout", "3.5"])
        mock_stop.return_value.to_dict.return_value = {
            "running": False,
            "pid": None,
            "host": "127.0.0.1",
            "port": 3189,
            "state_file": "/tmp/state.json",
            "log_file": "/tmp/server.log",
        }
        result = args.fn(MagicMock(), args)
        assert result == 0
        mock_stop.assert_called_once_with(timeout=3.5)

    @patch("tb2.service.restart_service")
    def test_service_restart_dispatch(self, mock_restart):
        p = build_parser()
        args = p.parse_args(["service", "restart", "--host", "127.0.0.1", "--port", "3200"])
        mock_restart.return_value.to_dict.return_value = {
            "running": True,
            "pid": 7,
            "host": "127.0.0.1",
            "port": 3200,
            "state_file": "/tmp/state.json",
            "log_file": "/tmp/server.log",
        }
        result = args.fn(MagicMock(), args)
        assert result == 0
        mock_restart.assert_called_once_with(host="127.0.0.1", port=3200, python_exe="", allow_remote=None)

    @patch("tb2.service.restart_service")
    def test_service_restart_dispatch_preserves_previous_binding_when_omitted(self, mock_restart):
        p = build_parser()
        args = p.parse_args(["service", "restart"])
        mock_restart.return_value.to_dict.return_value = {
            "running": True,
            "pid": 7,
            "host": "127.0.0.1",
            "port": 3189,
            "state_file": "/tmp/state.json",
            "log_file": "/tmp/server.log",
        }
        result = args.fn(MagicMock(), args)
        assert result == 0
        mock_restart.assert_called_once_with(host=None, port=None, python_exe="", allow_remote=None)

    @patch("tb2.service.tail_log")
    def test_service_logs_dispatch(self, mock_tail, capsys):
        p = build_parser()
        args = p.parse_args(["service", "logs", "--lines", "2"])
        mock_tail.return_value = ["line-a", "line-b"]
        result = args.fn(MagicMock(), args)
        out = capsys.readouterr().out
        assert result == 0
        assert "line-a" in out
        assert "line-b" in out
        mock_tail.assert_called_once_with(lines=2)

    @patch("tb2.audit.tail_events")
    def test_service_audit_dispatch(self, mock_tail, capsys):
        p = build_parser()
        args = p.parse_args([
            "service",
            "audit",
            "--lines",
            "2",
            "--room-id",
            "room-a",
            "--bridge-id",
            "bridge-a",
            "--event",
            "bridge.started",
        ])
        mock_tail.return_value = [{"event": "bridge.started", "bridge_id": "bridge-a"}]
        result = args.fn(MagicMock(), args)
        out = capsys.readouterr().out
        assert result == 0
        assert "bridge.started" in out
        mock_tail.assert_called_once_with(
            limit=2,
            room_id="room-a",
            bridge_id="bridge-a",
            event="bridge.started",
        )

    @patch("tb2.service.status_service")
    def test_service_status_dispatch(self, mock_status):
        p = build_parser()
        args = p.parse_args(["service", "status"])
        mock_status.return_value.to_dict.return_value = {
            "running": True,
            "pid": 101,
            "host": "127.0.0.1",
            "port": 3189,
            "state_file": "/tmp/state.json",
            "log_file": "/tmp/server.log",
        }
        result = args.fn(MagicMock(), args)
        assert result == 0
        mock_status.assert_called_once_with()
