"""Tests for tb2.cli — CLI argument parsing and backend factory."""

from unittest.mock import MagicMock, patch

import pytest

from tb2.cli import build_parser, _create_backend, main


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

    def test_backend_choices(self):
        p = build_parser()
        args = p.parse_args(["--backend", "process", "init"])
        assert args.backend == "process"

    def test_invalid_backend(self):
        p = build_parser()
        with pytest.raises(SystemExit):
            p.parse_args(["--backend", "invalid", "init"])


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
