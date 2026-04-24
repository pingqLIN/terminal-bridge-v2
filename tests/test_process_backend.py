"""Tests for tb2.process_backend — ProcessBackend, PaneBuffer, SpawnSpec."""

from collections import deque
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from tb2.process_backend import PaneBuffer, ProcessBackend, SpawnSpec, ManagedProcess, _ANSI_RE


class TestPaneBuffer:
    def test_feed_complete_lines(self):
        buf = PaneBuffer()
        result = buf.feed("hello\nworld\n")
        assert result == ["hello", "world"]

    def test_feed_partial_line(self):
        buf = PaneBuffer()
        result = buf.feed("partial")
        assert result == []
        result = buf.feed(" line\n")
        assert result == ["partial line"]

    def test_feed_strips_ansi(self):
        buf = PaneBuffer()
        result = buf.feed("\x1b[31mred text\x1b[0m\n")
        assert result == ["red text"]

    def test_get_recent(self):
        buf = PaneBuffer()
        buf.feed("line1\nline2\nline3\n")
        assert buf.get_recent(2) == ["line2", "line3"]

    def test_get_recent_all(self):
        buf = PaneBuffer()
        buf.feed("a\nb\n")
        assert buf.get_recent(100) == ["a", "b"]

    def test_ring_buffer_bounded(self):
        buf = PaneBuffer(lines=deque(maxlen=3))
        buf.feed("1\n2\n3\n4\n5\n")
        assert buf.get_recent(10) == ["3", "4", "5"]


class TestSpawnSpec:
    def test_defaults(self):
        spec = SpawnSpec(argv=["/bin/bash"])
        assert spec.cwd is None
        assert spec.env is None
        assert spec.profile == "generic"

    def test_with_env(self):
        spec = SpawnSpec(argv=["python3"], env={"FOO": "bar"})
        assert spec.env == {"FOO": "bar"}


class TestAnsiRegex:
    def test_strips_csi(self):
        assert _ANSI_RE.sub("", "\x1b[31mred\x1b[0m") == "red"

    def test_strips_carriage_return(self):
        assert _ANSI_RE.sub("", "hello\rworld") == "helloworld"

    def test_no_ansi(self):
        assert _ANSI_RE.sub("", "plain text") == "plain text"


def _make_managed_process(target="test:a"):
    """Helper to create a ManagedProcess without real subprocess."""
    buf = PaneBuffer()
    proc = MagicMock()
    proc.poll.return_value = None
    return ManagedProcess(
        name=target,
        proc=proc,
        buffer=buf,
        write_fn=MagicMock(),
    )


class TestProcessBackend:
    @patch("tb2.process_backend.default_shell_argv", return_value=["pwsh", "-NoLogo", "-NoProfile"])
    def test_default_shell(self, mock_default_shell):
        backend = ProcessBackend()
        assert backend.shell == "pwsh"
        assert backend.shell_argv == ["pwsh", "-NoLogo", "-NoProfile"]
        mock_default_shell.assert_called_once_with()

    def test_explicit_powershell_adds_flags(self):
        backend = ProcessBackend(shell="pwsh")
        assert backend.shell == "pwsh"
        assert backend.shell_argv == ["pwsh", "-NoLogo", "-NoProfile"]

    def test_init_session(self):
        backend = ProcessBackend(shell="/bin/bash")
        # Mock _spawn to avoid real process creation
        backend._spawn = MagicMock(side_effect=lambda t, s: _make_managed_process(t))
        a, b = backend.init_session("test")
        assert a == "test:a"
        assert b == "test:b"
        assert backend._spawn.call_count == 2

    def test_init_session_is_idempotent(self):
        backend = ProcessBackend(shell="/bin/bash")

        def mock_spawn(target, spec):
            mp = _make_managed_process(target)
            backend._procs[target] = mp
            return mp

        backend._spawn = MagicMock(side_effect=mock_spawn)
        assert backend.init_session("demo") == ("demo:a", "demo:b")
        assert backend.init_session("demo") == ("demo:a", "demo:b")
        assert backend._spawn.call_count == 2

    def test_init_session_respawns_dead_process(self):
        backend = ProcessBackend(shell="/bin/bash")
        dead = _make_managed_process("demo:a")
        dead.alive = False
        backend._procs["demo:a"] = dead
        spawned = []

        def mock_spawn(target, spec):
            mp = _make_managed_process(target)
            backend._procs[target] = mp
            spawned.append(target)
            return mp

        backend._spawn = MagicMock(side_effect=mock_spawn)
        assert backend.init_session("demo") == ("demo:a", "demo:b")
        assert spawned == ["demo:a", "demo:b"]

    def test_has_session(self):
        backend = ProcessBackend(shell="/bin/bash")
        def mock_spawn(t, s):
            mp = _make_managed_process(t)
            backend._procs[t] = mp
            return mp
        backend._spawn = mock_spawn
        backend.init_session("demo")
        assert backend.has_session("demo") is True
        assert backend.has_session("other") is False

    def test_has_session_prunes_dead_process(self):
        backend = ProcessBackend(shell="/bin/bash")
        dead = _make_managed_process("demo:a")
        dead.alive = False
        backend._procs["demo:a"] = dead

        assert backend.has_session("demo") is False
        assert "demo:a" not in backend._procs

    def test_list_panes(self):
        backend = ProcessBackend(shell="/bin/bash")
        def mock_spawn(t, s):
            mp = _make_managed_process(t)
            backend._procs[t] = mp
            return mp
        backend._spawn = mock_spawn
        backend.init_session("demo")
        panes = backend.list_panes("demo")
        assert len(panes) == 2

    def test_list_panes_omits_dead_process(self):
        backend = ProcessBackend(shell="/bin/bash")
        dead = _make_managed_process("demo:a")
        dead.alive = False
        backend._procs["demo:a"] = dead

        assert backend.list_panes("demo") == []
        assert "demo:a" not in backend._procs

    def test_capture(self):
        backend = ProcessBackend(shell="/bin/bash")
        mp = _make_managed_process("test:a")
        mp.buffer.feed("line1\nline2\n")
        backend._procs["test:a"] = mp
        lines = backend.capture("test:a")
        assert lines == ["line1", "line2"]

    def test_capture_not_found(self):
        backend = ProcessBackend(shell="/bin/bash")
        with pytest.raises(RuntimeError, match="process not found"):
            backend.capture("nonexistent")

    @patch("tb2.process_backend.shell_enter_sequence", return_value="\r")
    def test_send(self, mock_enter):
        backend = ProcessBackend(shell="/bin/bash")
        mp = _make_managed_process("test:a")
        backend._procs["test:a"] = mp
        backend.send("test:a", "hello", enter=True)
        mp.write_fn.assert_called_once_with("hello\r")
        mock_enter.assert_called_once_with("/bin/bash", pty=True)

    def test_capture_both(self):
        backend = ProcessBackend(shell="/bin/bash")
        mp_a = _make_managed_process("test:a")
        mp_b = _make_managed_process("test:b")
        mp_a.buffer.feed("from_a\n")
        mp_b.buffer.feed("from_b\n")
        backend._procs["test:a"] = mp_a
        backend._procs["test:b"] = mp_b
        a, b = backend.capture_both("test:a", "test:b")
        assert a == ["from_a"]
        assert b == ["from_b"]

    def test_spawn_agent_empty_argv(self):
        backend = ProcessBackend(shell="/bin/bash")
        with pytest.raises(ValueError, match="argv must not be empty"):
            backend.spawn_agent("test:c", SpawnSpec(argv=[]))

    def test_spawn_agent_duplicate(self):
        backend = ProcessBackend(shell="/bin/bash")
        backend._procs["test:a"] = _make_managed_process("test:a")
        with pytest.raises(RuntimeError, match="target already exists"):
            backend.spawn_agent("test:a", SpawnSpec(argv=["python3"]))

    def test_merge_env_none(self):
        spec = SpawnSpec(argv=["test"])
        assert ProcessBackend._merge_env(spec) is None

    @patch.dict("os.environ", {"EXISTING": "val"}, clear=True)
    def test_merge_env_with_custom(self):
        spec = SpawnSpec(argv=["test"], env={"NEW": "custom"})
        merged = ProcessBackend._merge_env(spec)
        assert merged["EXISTING"] == "val"
        assert merged["NEW"] == "custom"

    def test_kill_session(self):
        backend = ProcessBackend(shell="/bin/bash")
        mp_a = _make_managed_process("test:a")
        mp_b = _make_managed_process("test:b")
        backend._procs["test:a"] = mp_a
        backend._procs["test:b"] = mp_b
        backend._kill = MagicMock()
        backend.kill_session("test")
        assert backend._kill.call_count == 2

    @patch("tb2.process_backend.threading.Thread")
    def test_spawn_winpty_uses_argv_list(self, mock_thread):
        backend = ProcessBackend(shell="C:\\Program Files\\PowerShell\\7\\pwsh.EXE")
        spec = SpawnSpec(argv=[
            "C:\\Program Files\\PowerShell\\7\\pwsh.EXE",
            "-NoLogo",
            "-NoProfile",
        ])
        fake_proc = MagicMock()
        fake_proc.isalive.return_value = False
        fake_spawn = MagicMock(return_value=fake_proc)

        with patch.dict(
            "sys.modules",
            {"winpty": SimpleNamespace(PtyProcess=SimpleNamespace(spawn=fake_spawn))},
        ):
            managed = backend._spawn_winpty("demo:a", PaneBuffer(), spec)

        fake_spawn.assert_called_once_with(list(spec.argv))
        assert managed.proc is fake_proc
        mock_thread.assert_called_once()
