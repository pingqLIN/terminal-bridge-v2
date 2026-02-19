"""Tests for tb2.pipe_backend — PipeBackend with mocked subprocess."""

from unittest.mock import MagicMock, patch
import subprocess

import pytest

from tb2.pipe_backend import PipeBackend, _LineBuffer


class TestLineBuffer:
    def test_append_and_recent(self):
        buf = _LineBuffer()
        buf.append("line1")
        buf.append("line2")
        assert buf.recent(10) == ["line1", "line2"]

    def test_recent_limit(self):
        buf = _LineBuffer()
        for i in range(10):
            buf.append(f"line{i}")
        assert len(buf.recent(3)) == 3
        assert buf.recent(3) == ["line7", "line8", "line9"]

    def test_empty_buffer(self):
        buf = _LineBuffer()
        assert buf.recent() == []


class TestPipeBackend:
    @patch("tb2.pipe_backend.subprocess.Popen")
    @patch("tb2.pipe_backend.threading.Thread")
    def test_init_session(self, mock_thread, mock_popen):
        mock_proc = MagicMock()
        mock_proc.stdout.__iter__ = MagicMock(return_value=iter([]))
        mock_popen.return_value = mock_proc
        mock_thread.return_value = MagicMock()

        backend = PipeBackend(shell="/bin/bash")
        a, b = backend.init_session("test")
        assert a == "test:a"
        assert b == "test:b"
        assert mock_popen.call_count == 2

    @patch("tb2.pipe_backend.subprocess.Popen")
    @patch("tb2.pipe_backend.threading.Thread")
    def test_has_session(self, mock_thread, mock_popen):
        mock_popen.return_value = MagicMock()
        mock_thread.return_value = MagicMock()

        backend = PipeBackend(shell="/bin/bash")
        backend.init_session("demo")
        assert backend.has_session("demo") is True
        assert backend.has_session("other") is False

    @patch("tb2.pipe_backend.subprocess.Popen")
    @patch("tb2.pipe_backend.threading.Thread")
    def test_list_panes(self, mock_thread, mock_popen):
        mock_popen.return_value = MagicMock()
        mock_thread.return_value = MagicMock()

        backend = PipeBackend(shell="/bin/bash")
        backend.init_session("demo")
        panes = backend.list_panes("demo")
        assert len(panes) == 2

    def test_capture_not_found(self):
        backend = PipeBackend(shell="/bin/bash")
        with pytest.raises(RuntimeError, match="process not found"):
            backend.capture("nonexistent")

    @patch("tb2.pipe_backend.subprocess.Popen")
    @patch("tb2.pipe_backend.threading.Thread")
    def test_send(self, mock_thread, mock_popen):
        mock_stdin = MagicMock()
        mock_proc = MagicMock()
        mock_proc.stdin = mock_stdin
        mock_popen.return_value = mock_proc
        mock_thread.return_value = MagicMock()

        backend = PipeBackend(shell="/bin/bash")
        backend.init_session("test")
        backend.send("test:a", "echo hello", enter=True)
        mock_stdin.write.assert_called_with("echo hello\n")
        mock_stdin.flush.assert_called()

    @patch("tb2.pipe_backend.subprocess.Popen")
    @patch("tb2.pipe_backend.threading.Thread")
    def test_kill_session(self, mock_thread, mock_popen):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc
        mock_thread.return_value = MagicMock()

        backend = PipeBackend(shell="/bin/bash")
        backend.init_session("test")
        backend.kill_session("test")
        assert mock_proc.terminate.call_count == 2
