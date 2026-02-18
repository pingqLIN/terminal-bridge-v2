"""Terminal backend abstraction.

Decouples all terminal operations behind an ABC so broker/server
never touch tmux (or any multiplexer) directly.
"""

from __future__ import annotations

import os
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class TerminalBackend(ABC):
    """Interface every terminal backend must implement."""

    @abstractmethod
    def init_session(self, session: str) -> Tuple[str, str]:
        """Create a session with two panes. Return (pane_a, pane_b) targets."""

    @abstractmethod
    def has_session(self, session: str) -> bool:
        """Check whether *session* exists."""

    @abstractmethod
    def list_panes(self, session: Optional[str] = None) -> List[Tuple[str, str]]:
        """Return [(target, title), …] for panes."""

    @abstractmethod
    def capture(self, target: str, lines: int = 200) -> List[str]:
        """Capture the last *lines* visible lines from *target* pane."""

    @abstractmethod
    def capture_both(self, target_a: str, target_b: str, lines: int = 200) -> Tuple[List[str], List[str]]:
        """Capture two panes in one round-trip when possible."""

    @abstractmethod
    def send(self, target: str, text: str, enter: bool = False) -> None:
        """Send *text* to *target*, optionally followed by Enter."""

    @abstractmethod
    def kill_session(self, session: str) -> None:
        """Destroy a session."""


# ---------------------------------------------------------------------------
# tmux backend (WSL-aware)
# ---------------------------------------------------------------------------

DEFAULT_DISTRO = os.environ.get("TERMBRIDGE_WSL_DISTRO", "Ubuntu")
_SEPARATOR = "---TB2-PANE-SEP---"


class TmuxError(RuntimeError):
    pass


def _is_wsl() -> bool:
    """Detect whether we are running *inside* WSL."""
    try:
        with open("/proc/version", "r") as f:
            return "microsoft" in f.read().lower()
    except OSError:
        return False


_INSIDE_WSL = _is_wsl()


class TmuxBackend(TerminalBackend):
    """tmux backend — works both inside WSL (direct) and from Windows (via wsl.exe)."""

    def __init__(self, *, use_wsl: Optional[bool] = None, distro: str = DEFAULT_DISTRO):
        if use_wsl is None:
            # Auto-detect: if we're already inside WSL, call tmux directly.
            self.use_wsl = not _INSIDE_WSL
        else:
            self.use_wsl = use_wsl
        self.distro = distro

    # -- low-level helpers --------------------------------------------------

    def _tmux(self, args: Sequence[str], *, check: bool = True, capture: bool = True) -> str:
        if self.use_wsl:
            cmd = ["wsl", "-d", self.distro, "--", "tmux", *args]
        else:
            cmd = ["tmux", *args]

        try:
            cp = subprocess.run(cmd, check=False, text=True, capture_output=capture,
                                encoding="utf-8", errors="replace")
        except FileNotFoundError as exc:
            binary = "wsl.exe" if self.use_wsl else "tmux"
            raise TmuxError(f"{binary} not found") from exc

        if check and cp.returncode != 0:
            detail = ((cp.stderr or "") + (cp.stdout or "")).strip() or f"rc={cp.returncode}"
            raise TmuxError(f"tmux {' '.join(args)} failed: {detail}")

        return (cp.stdout or "") if capture else ""

    @staticmethod
    def _trim_blank_tail(lines: List[str]) -> List[str]:
        while lines and not lines[-1].strip():
            lines.pop()
        return lines

    @staticmethod
    def _escape(text: str) -> str:
        return text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\\n")

    # -- public API ---------------------------------------------------------

    def has_session(self, session: str) -> bool:
        try:
            self._tmux(["has-session", "-t", session])
            return True
        except TmuxError:
            return False

    def init_session(self, session: str) -> Tuple[str, str]:
        if not self.has_session(session):
            self._tmux(["new-session", "-d", "-s", session, "-n", "main"])
            self._tmux(["split-window", "-h", "-t", f"{session}:0"])
            self._tmux(["select-pane", "-t", f"{session}:0.0", "-T", "agent-A"])
            self._tmux(["select-pane", "-t", f"{session}:0.1", "-T", "agent-B"])
            self._tmux(["set-option", "-t", session, "-g", "allow-rename", "off"])
        return f"{session}:0.0", f"{session}:0.1"

    def list_panes(self, session: Optional[str] = None) -> List[Tuple[str, str]]:
        fmt = "#{session_name}:#{window_index}.#{pane_index}\t#{pane_title}"
        args = ["list-panes", "-a", "-F", fmt]
        if session:
            args.extend(["-t", session])
        out = self._tmux(args)
        result: List[Tuple[str, str]] = []
        for line in out.splitlines():
            if not line.strip():
                continue
            parts = line.split("\t", 1)
            result.append((parts[0].strip(), parts[1].strip() if len(parts) > 1 else ""))
        return result

    def capture(self, target: str, lines: int = 200) -> List[str]:
        out = self._tmux(["capture-pane", "-p", "-J", "-t", target, "-S", str(-abs(lines))])
        return self._trim_blank_tail(out.splitlines())

    def capture_both(self, target_a: str, target_b: str, lines: int = 200) -> Tuple[List[str], List[str]]:
        """Capture two panes in a single subprocess call."""
        start = str(-abs(lines))
        # Use a shell one-liner so we only spawn one process.
        script = (
            f"tmux capture-pane -p -J -t {target_a} -S {start}; "
            f"echo '{_SEPARATOR}'; "
            f"tmux capture-pane -p -J -t {target_b} -S {start}"
        )
        if self.use_wsl:
            cmd = ["wsl", "-d", self.distro, "--", "bash", "-c", script]
        else:
            cmd = ["bash", "-c", script]

        cp = subprocess.run(cmd, check=False, text=True, capture_output=True,
                            encoding="utf-8", errors="replace")
        if cp.returncode != 0:
            # Fallback to two separate calls.
            return self.capture(target_a, lines), self.capture(target_b, lines)

        raw = cp.stdout or ""
        parts = raw.split(_SEPARATOR, 1)
        a_lines = self._trim_blank_tail(parts[0].splitlines()) if parts else []
        b_lines = self._trim_blank_tail(parts[1].splitlines()) if len(parts) > 1 else []
        return a_lines, b_lines

    def send(self, target: str, text: str, enter: bool = False) -> None:
        safe = self._escape(text)
        # Combine text + Enter into a single send-keys call.
        keys: List[str] = []
        if safe:
            keys.append(safe)
        if enter:
            keys.append("Enter")
        if keys:
            self._tmux(["send-keys", "-t", target, *keys])

    def kill_session(self, session: str) -> None:
        self._tmux(["kill-session", "-t", session], check=False)
