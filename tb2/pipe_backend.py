"""Pipe-based backend — simplest fallback for non-interactive tools.

Uses plain subprocess stdin/stdout pipes.  No pseudo-terminal, so TUI
apps won't work, but batch/JSON-mode tools (e.g. `codex --quiet`,
`aider --yes`) work fine.

Zero dependencies beyond stdlib.  Works on all platforms.
"""

from __future__ import annotations

import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional, Tuple

from .backend import TerminalBackend
from .osutils import default_shell_argv, shell_argv, shell_enter_sequence


@dataclass
class _LineBuffer:
    lines: Deque[str] = field(default_factory=lambda: deque(maxlen=5000))
    lock: threading.Lock = field(default_factory=threading.Lock)

    def append(self, line: str) -> None:
        with self.lock:
            self.lines.append(line)

    def recent(self, n: int = 200) -> List[str]:
        with self.lock:
            items = list(self.lines)
            return items[-n:] if len(items) > n else items


@dataclass
class _ManagedProc:
    target: str
    proc: subprocess.Popen
    buf: _LineBuffer
    alive: bool = True


class PipeBackend(TerminalBackend):
    """Subprocess pipe backend — no PTY, no multiplexer.

    Best for tools that don't need a real terminal:
      - codex --quiet
      - aider --yes
      - Any tool with JSON/line output
    """

    def __init__(self, *, shell: str = ""):
        if not shell:
            self.shell_argv = default_shell_argv()
        else:
            self.shell_argv = shell_argv(shell)
        self.shell = self.shell_argv[0]
        self._procs: Dict[str, _ManagedProc] = {}
        self._lock = threading.Lock()

    def init_session(self, session: str) -> Tuple[str, str]:
        a = f"{session}:a"
        b = f"{session}:b"
        self._spawn(a)
        self._spawn(b)
        return a, b

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
                result.append((key, f"pipe ({status})"))
            return result

    def capture(self, target: str, lines: int = 200) -> List[str]:
        mp = self._get(target)
        return mp.buf.recent(lines)

    def capture_both(self, target_a: str, target_b: str, lines: int = 200) -> Tuple[List[str], List[str]]:
        return self.capture(target_a, lines), self.capture(target_b, lines)

    def send(self, target: str, text: str, enter: bool = False) -> None:
        mp = self._get(target)
        if not mp.proc.stdin:
            raise RuntimeError(f"stdin not available for {target}")
        payload = text + (shell_enter_sequence(self.shell) if enter else "")
        mp.proc.stdin.write(payload)
        mp.proc.stdin.flush()

    def kill_session(self, session: str) -> None:
        with self._lock:
            keys = [k for k in self._procs if k.startswith(f"{session}:")]
        for key in keys:
            with self._lock:
                mp = self._procs.pop(key, None)
            if mp and mp.proc.poll() is None:
                mp.proc.terminate()

    def _get(self, target: str) -> _ManagedProc:
        with self._lock:
            mp = self._procs.get(target)
        if not mp:
            raise RuntimeError(f"process not found: {target}")
        return mp

    def _spawn(self, target: str) -> None:
        buf = _LineBuffer()
        proc = subprocess.Popen(
            list(self.shell_argv),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,  # line-buffered
        )

        def reader() -> None:
            try:
                for line in proc.stdout:
                    buf.append(line.rstrip("\n\r"))
            except Exception:
                pass
            finally:
                mp.alive = False

        mp = _ManagedProc(target=target, proc=proc, buf=buf)
        t = threading.Thread(target=reader, daemon=True, name=f"pipe-{target}")
        t.start()

        with self._lock:
            self._procs[target] = mp
