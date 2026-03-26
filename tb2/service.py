"""Cross-platform service manager for tb2 MCP server.

Provides a minimal, dependency-free process manager for:
  - start / stop / restart
  - status
  - log tail

Security defaults:
  - host defaults to 127.0.0.1
  - no shell invocation
  - state directory is user-scoped
"""

from __future__ import annotations

import errno
import json
import os
import platform
import signal
import subprocess
import sys
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass(frozen=True)
class ServicePaths:
    """Filesystem paths used by the service manager."""

    root: Path
    state_file: Path
    log_file: Path

    @staticmethod
    def discover() -> "ServicePaths":
        root = _state_root()
        return ServicePaths(
            root=root,
            state_file=root / "server.state.json",
            log_file=root / "server.log",
        )


@dataclass(frozen=True)
class ServiceStatus:
    """Status snapshot of the managed tb2 server."""

    running: bool
    pid: Optional[int]
    host: str
    port: int
    state_file: str
    log_file: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "running": self.running,
            "pid": self.pid,
            "host": self.host,
            "port": self.port,
            "state_file": self.state_file,
            "log_file": self.log_file,
        }


def start_service(
    *,
    host: str = "127.0.0.1",
    port: int = 3189,
    python_exe: Optional[str] = None,
    force: bool = False,
) -> ServiceStatus:
    """Start `python -m tb2 server` as a detached background process."""
    paths = ServicePaths.discover()
    _ensure_runtime_dir(paths.root)

    current = status_service(paths=paths)
    if current.running and not force:
        raise RuntimeError(f"tb2 service is already running (pid={current.pid})")
    if current.running and force and current.pid is not None:
        _terminate_pid(current.pid, timeout=6.0)
        if _pid_alive(current.pid):
            raise RuntimeError(f"failed to stop existing tb2 service (pid={current.pid})")

    cmd = [
        python_exe or sys.executable,
        "-m",
        "tb2",
        "server",
        "--host",
        host,
        "--port",
        str(port),
    ]
    proc = _spawn_detached(cmd=cmd, log_file=paths.log_file)
    _save_state(
        paths.state_file,
        {
            "pid": proc.pid,
            "host": host,
            "port": int(port),
            "started_at": time.time(),
            "cmd": cmd,
        },
    )

    time.sleep(0.25)
    if proc.poll() is not None:
        _clear_state(paths.state_file)
        raise RuntimeError("tb2 service exited immediately, check log file")
    return status_service(paths=paths)


def stop_service(*, timeout: float = 8.0) -> ServiceStatus:
    """Stop the background tb2 service if running."""
    paths = ServicePaths.discover()
    st = status_service(paths=paths)
    if not st.running or st.pid is None:
        _clear_state(paths.state_file)
        return ServiceStatus(
            running=False,
            pid=None,
            host=st.host,
            port=st.port,
            state_file=st.state_file,
            log_file=st.log_file,
        )

    _terminate_pid(st.pid, timeout=timeout)
    _clear_state(paths.state_file)
    return ServiceStatus(
        running=False,
        pid=None,
        host=st.host,
        port=st.port,
        state_file=st.state_file,
        log_file=st.log_file,
    )


def restart_service(
    *,
    host: str = "127.0.0.1",
    port: int = 3189,
    python_exe: Optional[str] = None,
) -> ServiceStatus:
    """Restart the background tb2 service."""
    stop_service()
    return start_service(host=host, port=port, python_exe=python_exe, force=True)


def status_service(*, paths: Optional[ServicePaths] = None) -> ServiceStatus:
    """Read and validate current service state."""
    p = paths or ServicePaths.discover()
    state = _load_state(p.state_file)
    pid = _as_pid(state.get("pid"))
    host = str(state.get("host", "127.0.0.1"))
    port = _as_port(state.get("port"), default=3189)
    running = bool(pid is not None and _pid_alive(pid))
    if not running and state:
        _clear_state(p.state_file)
    return ServiceStatus(
        running=running,
        pid=pid if running else None,
        host=host,
        port=port,
        state_file=str(p.state_file),
        log_file=str(p.log_file),
    )


def tail_log(*, lines: int = 120) -> List[str]:
    """Return the last N lines from service log."""
    paths = ServicePaths.discover()
    if not paths.log_file.exists():
        return []
    cap = max(1, int(lines))
    with paths.log_file.open("r", encoding="utf-8", errors="replace") as handle:
        return [line.rstrip("\n") for line in deque(handle, maxlen=cap)]


def _state_root() -> Path:
    env_root = os.environ.get("TB2_STATE_DIR")
    if env_root:
        return Path(env_root).expanduser().resolve()

    if platform.system() == "Windows":
        local_app = os.environ.get("LOCALAPPDATA")
        if local_app:
            return Path(local_app) / "tb2"
        return Path.home() / "AppData" / "Local" / "tb2"

    xdg_state = os.environ.get("XDG_STATE_HOME")
    if xdg_state:
        return Path(xdg_state) / "tb2"

    if platform.system() == "Darwin":
        return _macos_state_root()

    return _legacy_state_root()


def _legacy_state_root() -> Path:
    return Path.home() / ".local" / "state" / "tb2"


def _macos_state_root() -> Path:
    root = Path.home() / "Library" / "Application Support" / "tb2"
    legacy = _legacy_state_root()
    if _has_state_files(root):
        return root
    if _has_state_files(legacy):
        return legacy
    return root


def _has_state_files(root: Path) -> bool:
    return any((root / name).exists() for name in ("server.state.json", "server.log"))


def _ensure_runtime_dir(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        os.chmod(root, 0o700)


def _spawn_detached(*, cmd: List[str], log_file: Path) -> subprocess.Popen:
    _ensure_runtime_dir(log_file.parent)
    with log_file.open("a", encoding="utf-8", buffering=1) as log:
        if os.name == "nt":
            flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                flags |= subprocess.CREATE_NO_WINDOW
            return subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                close_fds=True,
                creationflags=flags,
            )

        return subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            close_fds=True,
            start_new_session=True,
        )


def _as_pid(raw: object) -> Optional[int]:
    try:
        pid = int(raw)
    except (TypeError, ValueError):
        return None
    return pid if pid > 0 else None


def _as_port(raw: object, *, default: int) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError as exc:
        if exc.errno == errno.EPERM:
            return True
        return False
    return True


def _terminate_pid(pid: int, *, timeout: float) -> None:
    if os.name == "nt":
        _terminate_windows(pid, timeout=timeout)
        return
    _terminate_posix(pid, timeout=timeout)


def _terminate_posix(pid: int, *, timeout: float) -> None:
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return
    if _wait_pid_exit(pid, timeout=timeout):
        return
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        return
    _wait_pid_exit(pid, timeout=1.0)


def _terminate_windows(pid: int, *, timeout: float) -> None:
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass
    if _wait_pid_exit(pid, timeout=timeout):
        return

    subprocess.run(
        ["taskkill", "/PID", str(pid), "/T", "/F"],
        check=False,
        capture_output=True,
        text=True,
    )
    _wait_pid_exit(pid, timeout=1.0)


def _wait_pid_exit(pid: int, *, timeout: float) -> bool:
    deadline = time.time() + max(0.1, timeout)
    while time.time() < deadline:
        if not _pid_alive(pid):
            return True
        time.sleep(0.2)
    return not _pid_alive(pid)


def _load_state(path: Path) -> Dict[str, object]:
    if not path.exists():
        return {}
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return {}
    if isinstance(data, dict):
        return data
    return {}


def _save_state(path: Path, data: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")
    temp.replace(path)
    if os.name != "nt":
        os.chmod(path, 0o600)


def _clear_state(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return
    except OSError:
        return
