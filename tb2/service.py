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
from typing import Any, Dict, List, Optional

from .security import allow_remote_from_env, build_security_posture, validate_server_binding

_STATE_SCHEMA_VERSION = 1
_RUNTIME_PERSISTENCE_DIRECT = "memory_only"
_RUNTIME_RESTART_BEHAVIOR_DIRECT = "state_lost"
_RUNTIME_RECOVERY_SOURCE_DIRECT = "audit_history_only"
_RUNTIME_PERSISTENCE_SERVICE = "service_state_snapshot"
_RUNTIME_RESTART_BEHAVIOR_SERVICE = "best_effort_restore"
_RUNTIME_RECOVERY_SOURCE_SERVICE = "service_state_snapshot"
_DIRECT_LAUNCH_MODE = "direct"
_SERVICE_LAUNCH_MODE = "service"
_CONTINUITY_DIRECT = "process_local_only"
_CONTINUITY_FRESH = "fresh_start"
_CONTINUITY_RESTART_LOST = "restart_state_lost"
_CONTINUITY_RESTORED = "restart_restored"
_AUDIT_ENV_KEYS = (
    "TB2_AUDIT",
    "TB2_AUDIT_ALLOW_FULL_TEXT",
    "TB2_AUDIT_DIR",
    "TB2_AUDIT_MAX_BYTES",
    "TB2_AUDIT_MAX_FILES",
    "TB2_AUDIT_TEXT_MODE",
    "TB2_ALLOW_REMOTE",
)


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
    allow_remote: bool = False,
    _previous_state: Optional[Dict[str, object]] = None,
    _previous_runtime_active: bool = False,
) -> ServiceStatus:
    """Start `python -m tb2 server` as a detached background process."""
    paths = ServicePaths.discover()
    _ensure_runtime_dir(paths.root)

    previous_state = _load_state(paths.state_file) if _previous_state is None else _previous_state
    current = status_service(paths=paths)
    if current.running and not force:
        raise RuntimeError(f"tb2 service is already running (pid={current.pid})")
    if current.running and force and current.pid is not None:
        _terminate_pid(current.pid, timeout=6.0)
        if _pid_alive(current.pid):
            raise RuntimeError(f"failed to stop existing tb2 service (pid={current.pid})")

    effective_allow_remote = bool(allow_remote or allow_remote_from_env())
    validate_server_binding(host, allow_remote=effective_allow_remote)
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
    if effective_allow_remote:
        cmd.append("--allow-remote")
    env_overrides = _service_env_overrides(previous_state=previous_state)
    proc = _spawn_detached(cmd=cmd, log_file=paths.log_file, env=_launch_env(env_overrides))
    _save_state(
        paths.state_file,
        _build_state(
            pid=proc.pid,
            host=host,
            port=int(port),
            cmd=cmd,
            env_overrides=env_overrides,
            allow_remote=effective_allow_remote,
            previous_state=previous_state,
            previous_runtime_active=_previous_runtime_active,
        ),
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
    host: Optional[str] = None,
    port: Optional[int] = None,
    python_exe: Optional[str] = None,
    allow_remote: Optional[bool] = None,
) -> ServiceStatus:
    """Restart the background tb2 service."""
    paths = ServicePaths.discover()
    previous_state = _load_state(paths.state_file)
    current = status_service(paths=paths)
    previous_host = str(previous_state.get("host", current.host))
    previous_port = _as_port(previous_state.get("port"), default=current.port)
    previous_config = previous_state.get("config")
    previous_config_dict = previous_config if isinstance(previous_config, dict) else {}
    previous_allow_remote = bool(previous_config_dict.get("allow_remote", False))
    stop_service()
    return start_service(
        host=host or previous_host,
        port=previous_port if port is None else int(port),
        python_exe=python_exe,
        force=True,
        allow_remote=previous_allow_remote if allow_remote is None else bool(allow_remote),
        _previous_state=previous_state,
        _previous_runtime_active=current.running,
    )


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


def runtime_contract(*, paths: Optional[ServicePaths] = None) -> Dict[str, object]:
    p = paths or ServicePaths.discover()
    state = _load_state(p.state_file)
    runtime = state.get("runtime")
    if not isinstance(runtime, dict):
        posture = build_security_posture("127.0.0.1")
        return {
            "state_persistence": _RUNTIME_PERSISTENCE_DIRECT,
            "restart_behavior": _RUNTIME_RESTART_BEHAVIOR_DIRECT,
            "recovery_source": _RUNTIME_RECOVERY_SOURCE_DIRECT,
            "launch_mode": _DIRECT_LAUNCH_MODE,
            "snapshot_schema_version": None,
            "audit_policy_persistence": "process_env_only",
            "continuity": {
                "mode": _CONTINUITY_DIRECT,
                "runtime_restored": False,
                "previous_pid": None,
                "previous_started_at": None,
                "recovery_protocol": None,
                "restore_order": [],
                "last_recovery_at": None,
                "restored_workstream_count": 0,
                "manual_takeover_workstream_count": 0,
                "lost_workstream_count": 0,
            },
            "workstream_count": 0,
            "security_posture": posture.to_dict(),
        }
    continuity = runtime.get("continuity")
    continuity_dict = continuity if isinstance(continuity, dict) else {}
    launch_mode = str(runtime.get("launch_mode", _SERVICE_LAUNCH_MODE))
    defaults = _runtime_defaults(launch_mode)
    config = state.get("config")
    config_dict = config if isinstance(config, dict) else {}
    posture = build_security_posture(
        str(state.get("host", "127.0.0.1")),
        allow_remote=bool(config_dict.get("allow_remote", False)),
    )
    workstreams = state.get("workstreams")
    workstream_items = workstreams if isinstance(workstreams, list) else []
    restore_order = continuity_dict.get("restore_order")
    restore_order_items = [str(item) for item in restore_order] if isinstance(restore_order, list) else []
    return {
        "state_persistence": str(runtime.get("state_persistence", defaults["state_persistence"])),
        "restart_behavior": str(runtime.get("restart_behavior", defaults["restart_behavior"])),
        "recovery_source": str(runtime.get("recovery_source", defaults["recovery_source"])),
        "launch_mode": launch_mode,
        "snapshot_schema_version": _as_int(state.get("schema_version")),
        "audit_policy_persistence": str(runtime.get("audit_policy_persistence", "service_state")),
        "continuity": {
            "mode": str(continuity_dict.get("mode", _CONTINUITY_FRESH)),
            "runtime_restored": bool(continuity_dict.get("runtime_restored", False)),
            "previous_pid": _as_pid(continuity_dict.get("previous_pid")),
            "previous_started_at": _as_float(continuity_dict.get("previous_started_at")),
            "recovery_protocol": str(continuity_dict.get("recovery_protocol"))
            if continuity_dict.get("recovery_protocol")
            else None,
            "restore_order": restore_order_items,
            "last_recovery_at": _as_float(continuity_dict.get("last_recovery_at")),
            "restored_workstream_count": _as_int(continuity_dict.get("restored_workstream_count")) or 0,
            "manual_takeover_workstream_count": _as_int(continuity_dict.get("manual_takeover_workstream_count")) or 0,
            "lost_workstream_count": _as_int(continuity_dict.get("lost_workstream_count")) or 0,
        },
        "workstream_count": len(workstream_items),
        "security_posture": posture.to_dict(),
    }


def load_runtime_state(*, paths: Optional[ServicePaths] = None) -> Dict[str, object]:
    p = paths or ServicePaths.discover()
    return _load_state(p.state_file)


def persist_runtime_snapshot(
    *,
    workstreams: List[Dict[str, Any]],
    continuity: Optional[Dict[str, Any]] = None,
    paths: Optional[ServicePaths] = None,
) -> bool:
    p = paths or ServicePaths.discover()
    state = _load_state(p.state_file)
    runtime = state.get("runtime")
    if not isinstance(runtime, dict):
        return False
    if str(runtime.get("launch_mode", "")) != _SERVICE_LAUNCH_MODE:
        return False
    if _as_pid(state.get("pid")) != os.getpid():
        return False
    defaults = _runtime_defaults(_SERVICE_LAUNCH_MODE)
    runtime["state_persistence"] = defaults["state_persistence"]
    runtime["restart_behavior"] = defaults["restart_behavior"]
    runtime["recovery_source"] = defaults["recovery_source"]
    if continuity is not None:
        runtime["continuity"] = continuity
    state["runtime"] = runtime
    state["workstreams"] = workstreams
    _save_state(p.state_file, state)
    return True


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


def _spawn_detached(*, cmd: List[str], log_file: Path, env: Optional[Dict[str, str]] = None) -> subprocess.Popen:
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
                env=env,
            )

        return subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            close_fds=True,
            start_new_session=True,
            env=env,
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


def _as_int(raw: object) -> Optional[int]:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _as_float(raw: object) -> Optional[float]:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


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


def _build_state(
    *,
    pid: int,
    host: str,
    port: int,
    cmd: List[str],
    env_overrides: Dict[str, str],
    allow_remote: bool,
    previous_state: Dict[str, object],
    previous_runtime_active: bool,
) -> Dict[str, object]:
    previous_pid = _as_pid(previous_state.get("pid")) if previous_runtime_active else None
    previous_started_at = _as_float(previous_state.get("started_at")) if previous_runtime_active else None
    continuity_mode = _CONTINUITY_RESTART_LOST if previous_runtime_active else _CONTINUITY_FRESH
    return {
        "schema_version": _STATE_SCHEMA_VERSION,
        "pid": pid,
        "host": host,
        "port": int(port),
        "started_at": time.time(),
        "cmd": cmd,
        "config": {
            "env_overrides": env_overrides,
            "allow_remote": bool(allow_remote),
        },
        "runtime": {
            "launch_mode": _SERVICE_LAUNCH_MODE,
            "state_persistence": _RUNTIME_PERSISTENCE_SERVICE,
            "restart_behavior": _RUNTIME_RESTART_BEHAVIOR_SERVICE,
            "recovery_source": _RUNTIME_RECOVERY_SOURCE_SERVICE,
            "audit_policy_persistence": "service_state",
            "continuity": {
                "mode": continuity_mode,
                "runtime_restored": False,
                "previous_pid": previous_pid,
                "previous_started_at": previous_started_at,
            },
        },
        "workstreams": [],
    }


def _runtime_defaults(launch_mode: str) -> Dict[str, str]:
    if launch_mode == _SERVICE_LAUNCH_MODE:
        return {
            "state_persistence": _RUNTIME_PERSISTENCE_SERVICE,
            "restart_behavior": _RUNTIME_RESTART_BEHAVIOR_SERVICE,
            "recovery_source": _RUNTIME_RECOVERY_SOURCE_SERVICE,
        }
    return {
        "state_persistence": _RUNTIME_PERSISTENCE_DIRECT,
        "restart_behavior": _RUNTIME_RESTART_BEHAVIOR_DIRECT,
        "recovery_source": _RUNTIME_RECOVERY_SOURCE_DIRECT,
    }


def _service_env_overrides(*, previous_state: Dict[str, object]) -> Dict[str, str]:
    config = previous_state.get("config")
    config_dict = config if isinstance(config, dict) else {}
    raw_overrides = config_dict.get("env_overrides")
    previous_overrides = raw_overrides if isinstance(raw_overrides, dict) else {}
    overrides: Dict[str, str] = {}
    for key in _AUDIT_ENV_KEYS:
        current = os.environ.get(key)
        if current is not None:
            overrides[key] = current
            continue
        previous = previous_overrides.get(key)
        if isinstance(previous, str):
            overrides[key] = previous
    return overrides


def _launch_env(overrides: Dict[str, str]) -> Dict[str, str]:
    env = dict(os.environ)
    env.update(overrides)
    return env


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
