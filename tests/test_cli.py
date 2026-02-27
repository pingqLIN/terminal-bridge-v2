"""Tests for tb2.cli — CLI argument parsing and backend factory."""

from unittest.mock import MagicMock, patch

import pytest

from tb2.cli import build_parser, _create_backend, cmd_gui, main


class TestBuildParser:
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

    def test_gui_defaults(self):
        p = build_parser()
        args = p.parse_args(["gui"])
        assert args.host == "127.0.0.1"
        assert args.port == 3189
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
        assert args.force is False

    def test_service_logs_defaults(self):
        p = build_parser()
        args = p.parse_args(["service", "logs"])
        assert args.cmd == "service"
        assert args.service_cmd == "logs"
        assert args.lines == 120


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


class TestGuiCommand:
    @patch("tb2.server.run_server")
    @patch("webbrowser.open")
    def test_cmd_gui_no_browser(self, mock_open, mock_run_server):
        p = build_parser()
        args = p.parse_args(["gui", "--host", "127.0.0.1", "--port", "3199", "--no-browser"])
        result = cmd_gui(MagicMock(), args)
        assert result == 0
        mock_run_server.assert_called_once_with(host="127.0.0.1", port=3199)
        mock_open.assert_not_called()


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
        mock_start.assert_called_once_with(host="127.0.0.1", port=3199, python_exe="", force=False)

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
        mock_restart.assert_called_once_with(host="127.0.0.1", port=3200, python_exe="")

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
