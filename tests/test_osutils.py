"""Tests for tb2.osutils."""

from __future__ import annotations

from unittest.mock import patch

import tb2.osutils as osutils


class TestDefaultBackendName:
    @patch("tb2.osutils.is_windows", return_value=True)
    @patch("tb2.osutils.process_backend_available", return_value=False)
    @patch("tb2.osutils.tmux_backend_available", return_value=True)
    def test_windows_falls_back_to_tmux(self, mock_tmux, mock_process, mock_windows):
        assert osutils.default_backend_name() == "tmux"
        mock_windows.assert_called_once_with()
        mock_process.assert_called_once_with()
        mock_tmux.assert_called_once_with()

    @patch("tb2.osutils.is_windows", return_value=True)
    @patch("tb2.osutils.process_backend_available", return_value=False)
    @patch("tb2.osutils.tmux_backend_available", return_value=False)
    def test_windows_falls_back_to_pipe(self, mock_tmux, mock_process, mock_windows):
        assert osutils.default_backend_name() == "pipe"
        mock_windows.assert_called_once_with()
        mock_process.assert_called_once_with()
        mock_tmux.assert_called_once_with()

    @patch("tb2.osutils.is_windows", return_value=False)
    @patch("tb2.osutils.tmux_backend_available", return_value=False)
    def test_posix_falls_back_to_process(self, mock_tmux, mock_windows):
        assert osutils.default_backend_name() == "process"
        mock_windows.assert_called_once_with()
        mock_tmux.assert_called_once_with()


class TestDefaultShell:
    @patch.dict("os.environ", {"SHELL": "/usr/bin/bash", "COMSPEC": "cmd.exe"}, clear=True)
    @patch("tb2.osutils.is_windows", return_value=True)
    @patch("tb2.osutils.shutil.which", return_value=None)
    def test_windows_ignores_shell_env(self, mock_which, mock_windows):
        assert osutils.default_shell() == "cmd.exe"
        mock_windows.assert_called_once_with()
        assert mock_which.call_count == 2


class TestShellArgv:
    def test_powershell_adds_flags(self):
        assert osutils.shell_argv("pwsh") == ["pwsh", "-NoLogo", "-NoProfile"]


class TestShellEnterSequence:
    def test_pipe_shell_uses_lf_for_posix_shells(self):
        assert osutils.shell_enter_sequence("bash") == "\n"

    def test_pty_shell_uses_cr_for_posix_shells(self):
        assert osutils.shell_enter_sequence("bash", pty=True) == "\r"

    def test_windows_console_shell_uses_crlf(self):
        assert osutils.shell_enter_sequence("cmd.exe") == "\r\n"
