"""Operating-system defaults shared across tb2 backends and CLI entry points."""

from __future__ import annotations

import importlib.util
import os
import platform
import shutil
from typing import List

_WINDOWS_CONSOLE_SHELLS = {
    "cmd",
    "cmd.exe",
    "powershell",
    "powershell.exe",
    "pwsh",
    "pwsh.exe",
}


def is_windows() -> bool:
    return platform.system() == "Windows"


def is_macos() -> bool:
    return platform.system() == "Darwin"


def _shell_name(shell: str) -> str:
    return os.path.basename(shell).lower()


def process_backend_available() -> bool:
    if not is_windows():
        return True
    return importlib.util.find_spec("winpty") is not None


def tmux_backend_available() -> bool:
    if is_windows():
        return shutil.which("wsl") is not None
    return shutil.which("tmux") is not None


def default_backend_name() -> str:
    if is_windows():
        if process_backend_available():
            return "process"
        if tmux_backend_available():
            return "tmux"
        return "pipe"
    if tmux_backend_available():
        return "tmux"
    return "process"


def default_shell() -> str:
    override = os.environ.get("TB2_SHELL")
    if override:
        return override

    if is_windows():
        for candidate in ("pwsh", "powershell.exe"):
            resolved = shutil.which(candidate)
            if resolved:
                return resolved
        return os.environ.get("COMSPEC", "cmd.exe")

    override = os.environ.get("SHELL")
    if override:
        return override

    for candidate in ("/bin/bash", "/bin/zsh", "/bin/sh"):
        if os.path.exists(candidate):
            return candidate
    return shutil.which("sh") or "sh"


def shell_argv(shell: str) -> List[str]:
    if _shell_name(shell) in {"pwsh", "pwsh.exe", "powershell", "powershell.exe"}:
        return [shell, "-NoLogo", "-NoProfile"]
    return [shell]


def default_shell_argv() -> List[str]:
    return shell_argv(default_shell())


def shell_enter_sequence(shell: str = "", *, pty: bool = False) -> str:
    name = _shell_name(shell or default_shell())
    if name in _WINDOWS_CONSOLE_SHELLS:
        return "\r\n"
    if pty:
        return "\r"
    return "\n"


def command_runner_shell() -> str:
    """Portable POSIX shell for one-shot helper commands."""
    return "sh"
