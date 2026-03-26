"""Tests for tb2.backend — TmuxBackend with mocked subprocess."""

from unittest.mock import MagicMock, patch, mock_open
import subprocess

import pytest

from tb2.backend import TmuxBackend, TmuxError, _SEPARATOR


@pytest.fixture
def backend():
    """TmuxBackend with WSL disabled."""
    return TmuxBackend(use_wsl=False)


@pytest.fixture
def wsl_backend():
    """TmuxBackend with WSL enabled."""
    return TmuxBackend(use_wsl=True, distro="Ubuntu")


class TestTmuxHelpers:
    def test_escape_newlines(self):
        assert TmuxBackend._escape("hello\nworld") == "hello\\nworld"

    def test_escape_carriage_return(self):
        assert TmuxBackend._escape("hello\r\nworld") == "hello\\nworld"

    def test_trim_blank_tail(self):
        lines = ["hello", "world", "", "  ", ""]
        result = TmuxBackend._trim_blank_tail(lines)
        assert result == ["hello", "world"]

    def test_trim_blank_tail_no_blanks(self):
        lines = ["hello", "world"]
        result = TmuxBackend._trim_blank_tail(lines)
        assert result == ["hello", "world"]


class TestTmuxBackendDirect:
    @patch("tb2.backend.subprocess.run")
    def test_has_session_true(self, mock_run, backend):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        assert backend.has_session("test") is True

    @patch("tb2.backend.subprocess.run")
    def test_has_session_false(self, mock_run, backend):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="no session")
        assert backend.has_session("test") is False

    @patch("tb2.backend.subprocess.run")
    def test_init_session_creates(self, mock_run, backend):
        # First has_session returns False (rc=1), then subsequent calls succeed
        mock_run.side_effect = [
            MagicMock(returncode=1, stdout="", stderr="no session"),  # has_session
            MagicMock(returncode=0, stdout="", stderr=""),  # new-session
            MagicMock(returncode=0, stdout="", stderr=""),  # split-window
            MagicMock(returncode=0, stdout="", stderr=""),  # select-pane A
            MagicMock(returncode=0, stdout="", stderr=""),  # select-pane B
            MagicMock(returncode=0, stdout="", stderr=""),  # set-option
        ]
        a, b = backend.init_session("demo")
        assert a == "demo:0.0"
        assert b == "demo:0.1"
        assert mock_run.call_count == 6

    @patch("tb2.backend.subprocess.run")
    def test_capture(self, mock_run, backend):
        mock_run.return_value = MagicMock(returncode=0, stdout="line1\nline2\n\n", stderr="")
        lines = backend.capture("test:0.0", 200)
        assert lines == ["line1", "line2"]

    @patch("tb2.backend.subprocess.run")
    def test_capture_both(self, mock_run, backend):
        sep_output = f"pane_a_line1\n{_SEPARATOR}\npane_b_line1\n"
        mock_run.return_value = MagicMock(returncode=0, stdout=sep_output, stderr="")
        a, b = backend.capture_both("test:0.0", "test:0.1")
        assert a == ["pane_a_line1"]
        # After split on separator, pane B starts with newline → first element is empty
        assert "pane_b_line1" in b
        cmd = mock_run.call_args[0][0]
        assert cmd[:2] == ["sh", "-lc"]

    @patch("tb2.backend.subprocess.run")
    def test_send_with_enter(self, mock_run, backend):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        backend.send("test:0.0", "echo hello", enter=True)
        call_args = mock_run.call_args[0][0]
        assert "send-keys" in call_args
        assert "Enter" in call_args

    @patch("tb2.backend.subprocess.run")
    def test_send_without_enter(self, mock_run, backend):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        backend.send("test:0.0", "text")
        call_args = mock_run.call_args[0][0]
        assert "Enter" not in call_args

    @patch("tb2.backend.subprocess.run")
    def test_kill_session(self, mock_run, backend):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        backend.kill_session("test")
        call_args = mock_run.call_args[0][0]
        assert "kill-session" in call_args

    @patch("tb2.backend.subprocess.run")
    def test_list_panes(self, mock_run, backend):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="test:0.0\tagent-A\ntest:0.1\tagent-B\n",
            stderr="",
        )
        panes = backend.list_panes("test")
        assert len(panes) == 2
        assert panes[0] == ("test:0.0", "agent-A")

    @patch("tb2.backend.subprocess.run")
    def test_tmux_error_on_failure(self, mock_run, backend):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error msg")
        with pytest.raises(TmuxError, match="error msg"):
            backend._tmux(["bad-command"], check=True)

    @patch("tb2.backend.subprocess.run", side_effect=FileNotFoundError)
    def test_tmux_not_found(self, mock_run, backend):
        with pytest.raises(TmuxError, match="tmux not found"):
            backend._tmux(["anything"])


class TestTmuxBackendWSL:
    @patch("tb2.backend.subprocess.run")
    def test_wsl_command_prefix(self, mock_run, wsl_backend):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        wsl_backend._tmux(["list-sessions"])
        cmd = mock_run.call_args[0][0]
        assert cmd[:2] == ["wsl", "-d"]
        assert "Ubuntu" in cmd

    @patch("tb2.backend.subprocess.run")
    def test_capture_both_uses_sh_via_wsl(self, mock_run, wsl_backend):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        wsl_backend.capture_both("test:0.0", "test:0.1")
        cmd = mock_run.call_args[0][0]
        assert cmd[:4] == ["wsl", "-d", "Ubuntu", "--"]
        assert cmd[4:6] == ["sh", "-lc"]

    @patch("tb2.backend.subprocess.run", side_effect=FileNotFoundError)
    def test_wsl_not_found(self, mock_run, wsl_backend):
        with pytest.raises(TmuxError, match="wsl.exe not found"):
            wsl_backend._tmux(["anything"])
