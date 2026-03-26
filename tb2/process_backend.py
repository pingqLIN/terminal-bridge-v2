"""Process-based backend — no terminal multiplexer needed.

Works on Windows (ConPTY via pywinpty), Linux, and macOS by spawning
child processes with pseudo-terminal I/O.  Output is streamed directly
instead of screen-scraped, giving <1ms latency.

Dependencies:
  - pywinpty (Windows): pip install pywinpty
  - pty (Linux/macOS): stdlib
"""

from __future__ import annotations

import os
import platform
import re
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional, Tuple

from .backend import TerminalBackend
from .osutils import default_shell_argv, shell_argv, shell_enter_sequence

# Strip ANSI escape sequences + OSC sequences from PTY output.
_ANSI_RE = re.compile(r"""
    \x1b\[[0-9;]*[a-zA-Z]   |  # CSI sequences (colors, cursor)
    \x1b\][^\x07\x1b]*(?:\x07|\x1b\\)  |  # OSC sequences (title, etc)
    \x1b\[?\??[0-9;]*[a-zA-Z]  |  # Private mode set/reset
    \r                          # Carriage returns
""", re.VERBOSE)

_IS_WINDOWS = platform.system() == "Windows"


@dataclass
class PaneBuffer:
    """Ring buffer that accumulates output lines from a process."""

    lines: Deque[str] = field(default_factory=lambda: deque(maxlen=5000))
    lock: threading.Lock = field(default_factory=threading.Lock)
    _partial: str = field(default="")

    def feed(self, data: str) -> List[str]:
        """Feed raw data, split into lines, return new complete lines."""
        new_lines: List[str] = []
        with self.lock:
            self._partial += data
            while "\n" in self._partial:
                line, self._partial = self._partial.split("\n", 1)
                cleaned = _ANSI_RE.sub("", line)
                if cleaned:  # skip empty lines from stripped sequences
                    self.lines.append(cleaned)
                    new_lines.append(cleaned)
        return new_lines

    def get_recent(self, n: int = 200) -> List[str]:
        with self.lock:
            items = list(self.lines)
            return items[-n:] if len(items) > n else items


@dataclass
class ManagedProcess:
    """A child process with its I/O threads and output buffer."""

    name: str
    proc: object  # subprocess.Popen or winpty.PTY
    buffer: PaneBuffer
    reader_thread: Optional[threading.Thread] = None
    write_fn: object = None  # callable(text: str) -> None
    alive: bool = True


@dataclass
class SpawnSpec:
    """Spawn settings for one agent process."""

    argv: List[str]
    cwd: Optional[str] = None
    env: Optional[Dict[str, str]] = None
    profile: str = "generic"


class ProcessBackend(TerminalBackend):
    """Spawn and manage child processes directly.

    On Windows: uses pywinpty (ConPTY) for full TUI support.
    On Linux/macOS: uses stdlib pty for pseudo-terminal.
    """

    def __init__(self, *, shell: str = ""):
        if not shell:
            self.shell_argv = default_shell_argv()
        else:
            self.shell_argv = shell_argv(shell)
        self.shell = self.shell_argv[0]
        self._procs: Dict[str, ManagedProcess] = {}
        self._lock = threading.Lock()

    # -- TerminalBackend implementation ------------------------------------

    def init_session(self, session: str) -> Tuple[str, str]:
        target_a = f"{session}:a"
        target_b = f"{session}:b"
        self._spawn(target_a, self._default_spawn_spec())
        self._spawn(target_b, self._default_spawn_spec())
        return target_a, target_b

    def has_session(self, session: str) -> bool:
        with self._lock:
            return any(k.startswith(f"{session}:") for k in self._procs)

    def list_panes(self, session: Optional[str] = None) -> List[Tuple[str, str]]:
        with self._lock:
            result = []
            for key, mp in self._procs.items():
                if session and not key.startswith(f"{session}:"):
                    continue
                status = "alive" if mp.alive else "dead"
                result.append((key, f"{mp.name} ({status})"))
            return result

    def capture(self, target: str, lines: int = 200) -> List[str]:
        mp = self._get(target)
        return mp.buffer.get_recent(lines)

    def capture_both(self, target_a: str, target_b: str, lines: int = 200) -> Tuple[List[str], List[str]]:
        # Direct memory access — no subprocess needed!
        return self.capture(target_a, lines), self.capture(target_b, lines)

    def send(self, target: str, text: str, enter: bool = False) -> None:
        mp = self._get(target)
        payload = text + (shell_enter_sequence(self.shell, pty=True) if enter else "")
        mp.write_fn(payload)

    def kill_session(self, session: str) -> None:
        with self._lock:
            keys = [k for k in self._procs if k.startswith(f"{session}:")]
        for key in keys:
            self._kill(key)

    def spawn_agent(self, target: str, spec: SpawnSpec) -> str:
        """Spawn one pane/process with a custom command."""
        if not spec.argv:
            raise ValueError("spawn spec argv must not be empty")
        with self._lock:
            if target in self._procs:
                raise RuntimeError(f"target already exists: {target}")
        self._spawn(target, spec)
        return target

    # -- internal ----------------------------------------------------------

    def _get(self, target: str) -> ManagedProcess:
        with self._lock:
            mp = self._procs.get(target)
        if not mp:
            raise RuntimeError(f"process not found: {target}")
        return mp

    def _default_spawn_spec(self) -> SpawnSpec:
        return SpawnSpec(argv=list(self.shell_argv))

    @staticmethod
    def _merge_env(spec: SpawnSpec) -> Optional[Dict[str, str]]:
        if spec.env is None:
            return None
        merged = os.environ.copy()
        for key, value in spec.env.items():
            merged[str(key)] = str(value)
        return merged

    def _spawn(self, target: str, spec: Optional[SpawnSpec] = None) -> ManagedProcess:
        spec = spec or self._default_spawn_spec()
        if not spec.argv:
            raise ValueError("spawn spec argv must not be empty")
        buf = PaneBuffer()

        if _IS_WINDOWS:
            mp = self._spawn_winpty(target, buf, spec)
        else:
            mp = self._spawn_pty(target, buf, spec)

        with self._lock:
            self._procs[target] = mp
        return mp

    def _spawn_pty(self, target: str, buf: PaneBuffer, spec: SpawnSpec) -> ManagedProcess:
        """Unix: use stdlib pty for pseudo-terminal."""
        import pty

        env = self._merge_env(spec)
        master_fd, slave_fd = pty.openpty()
        proc = subprocess.Popen(
            spec.argv,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            preexec_fn=os.setsid,
            close_fds=True,
            cwd=spec.cwd,
            env=env,
        )
        os.close(slave_fd)

        def write_fn(text: str) -> None:
            os.write(master_fd, text.encode("utf-8"))

        def reader() -> None:
            try:
                while True:
                    data = os.read(master_fd, 4096)
                    if not data:
                        break
                    buf.feed(data.decode("utf-8", errors="replace"))
            except OSError:
                pass
            finally:
                mp.alive = False

        mp = ManagedProcess(
            name=target,
            proc=proc,
            buffer=buf,
            write_fn=write_fn,
        )
        t = threading.Thread(target=reader, daemon=True, name=f"reader-{target}")
        t.start()
        mp.reader_thread = t
        return mp

    def _spawn_winpty(self, target: str, buf: PaneBuffer, spec: SpawnSpec) -> ManagedProcess:
        """Windows: use pywinpty ConPTY."""
        try:
            from winpty import PtyProcess
        except ImportError:
            raise RuntimeError(
                "pywinpty is required on Windows. Install with: pip install pywinpty"
            )

        env = self._merge_env(spec)
        cmdline = subprocess.list2cmdline(spec.argv)
        spawn_kwargs: Dict[str, object] = {}
        if spec.cwd:
            spawn_kwargs["cwd"] = spec.cwd
        if env is not None:
            spawn_kwargs["env"] = env
        try:
            proc = PtyProcess.spawn(cmdline, **spawn_kwargs)
        except TypeError:
            proc = PtyProcess.spawn(cmdline)

        def write_fn(text: str) -> None:
            proc.write(text)

        def reader() -> None:
            try:
                while proc.isalive():
                    data = proc.read(4096)
                    if data:
                        buf.feed(data)
                    else:
                        time.sleep(0.01)
            except Exception:
                pass
            finally:
                mp.alive = False

        mp = ManagedProcess(
            name=target,
            proc=proc,
            buffer=buf,
            write_fn=write_fn,
        )
        t = threading.Thread(target=reader, daemon=True, name=f"reader-{target}")
        t.start()
        mp.reader_thread = t
        return mp

    def _kill(self, target: str) -> None:
        with self._lock:
            mp = self._procs.pop(target, None)
        if not mp:
            return
        mp.alive = False
        proc = mp.proc
        if hasattr(proc, "terminate"):
            try:
                proc.terminate()
            except Exception:
                pass
        elif hasattr(proc, "close"):
            try:
                proc.close()
            except Exception:
                pass
