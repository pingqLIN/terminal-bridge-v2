"""Compatibility matrix and local environment checks for tb2."""

from __future__ import annotations

import importlib.util
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any, Dict, List, Sequence, Tuple

from .osutils import default_backend_name


@dataclass(frozen=True)
class ClientSpec:
    """First-class or community CLI client support metadata."""

    name: str
    profile: str
    command: str
    version_args: Tuple[str, ...]
    support: str
    backend_windows: str
    backend_posix: str
    notes: str


CLIENTS: Tuple[ClientSpec, ...] = (
    ClientSpec(
        name="OpenAI Codex CLI",
        profile="codex",
        command="codex",
        version_args=("--version",),
        support="full",
        backend_windows="process",
        backend_posix="tmux",
        notes="Best interactive host/guest pairing for Codex-driven sessions.",
    ),
    ClientSpec(
        name="Claude Code CLI",
        profile="claude-code",
        command="claude",
        version_args=("--version",),
        support="full",
        backend_windows="process",
        backend_posix="tmux",
        notes="Recommended for long-running review or implementation sessions.",
    ),
    ClientSpec(
        name="Gemini CLI",
        profile="gemini",
        command="gemini",
        version_args=("--version",),
        support="full",
        backend_windows="process",
        backend_posix="tmux",
        notes="Good fit for drafting, broad ideation, and bulk text generation.",
    ),
    ClientSpec(
        name="Aider",
        profile="aider",
        command="aider",
        version_args=("--version",),
        support="full",
        backend_windows="process",
        backend_posix="tmux",
        notes="Works well for repo-aware editing; pipe backend is fine for non-interactive runs.",
    ),
    ClientSpec(
        name="llama.cpp / Ollama-style shell",
        profile="llama",
        command="ollama",
        version_args=("--version",),
        support="community",
        backend_windows="process",
        backend_posix="tmux",
        notes="Profile is available, but prompt/output conventions vary by wrapper.",
    ),
)


def _default_distro() -> str:
    return os.environ.get("TERMBRIDGE_WSL_DISTRO", "Ubuntu")


def _trim(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    return lines[0]


def _run(argv: Sequence[str]) -> tuple[bool, str]:
    try:
        cp = subprocess.run(
            list(argv),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)

    output = _trim(cp.stdout) or _trim(cp.stderr)
    if cp.returncode == 0:
        return True, output or "ok"
    return False, output or f"exit code {cp.returncode}"


def _probe_cmd(name: str, argv: Sequence[str]) -> Dict[str, Any]:
    path = shutil.which(name)
    if not path:
        return {"available": False, "detail": "not found in PATH", "path": ""}
    ok, detail = _run((path, *tuple(argv[1:])))
    return {
        "available": ok,
        "detail": detail if detail else path,
        "path": path,
    }


def _probe_tmux(distro: str) -> Dict[str, Any]:
    if platform.system() == "Windows":
        wsl = shutil.which("wsl")
        if not wsl:
            return {
                "name": "tmux",
                "available": False,
                "detail": "wsl.exe not found; tmux backend unavailable on native Windows",
            }
        ok, detail = _run(("wsl", "-d", distro, "--", "tmux", "-V"))
        return {
            "name": "tmux",
            "available": ok,
            "detail": f"{distro}: {detail}",
        }

    probe = _probe_cmd("tmux", ("tmux", "-V"))
    return {
        "name": "tmux",
        "available": probe["available"],
        "detail": probe["detail"],
    }


def _probe_process() -> Dict[str, Any]:
    if platform.system() != "Windows":
        return {
            "name": "process",
            "available": True,
            "detail": "pty backend available via Python stdlib",
        }
    mod = importlib.util.find_spec("winpty")
    if mod is not None:
        return {
            "name": "process",
            "available": True,
            "detail": "pywinpty installed",
        }
    return {
        "name": "process",
        "available": False,
        "detail": 'missing pywinpty; install with `pip install -e ".[windows]"`',
    }


def _probe_pipe() -> Dict[str, Any]:
    return {
        "name": "pipe",
        "available": True,
        "detail": "plain subprocess stdin/stdout backend available",
    }


def profile_rows() -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = [
        {
            "profile": "generic",
            "tool": "Generic shell / unknown CLI",
            "support": "baseline",
            "recommended_backend": "process on Windows, tmux on Linux/macOS",
            "notes": "Fallback profile when no tool-specific prompt rules are known.",
        }
    ]
    for spec in CLIENTS:
        rows.append(
            {
                "profile": spec.profile,
                "tool": spec.name,
                "support": spec.support,
                "recommended_backend": (
                    f"{spec.backend_windows} on Windows, {spec.backend_posix} on Linux/macOS"
                ),
                "notes": spec.notes,
            }
        )
    return rows


def doctor_report(*, distro: str | None = None) -> Dict[str, Any]:
    distro_name = distro or _default_distro()
    backends = [
        _probe_tmux(distro_name),
        _probe_process(),
        _probe_pipe(),
    ]
    clients = []
    for spec in CLIENTS:
        probe = _probe_cmd(spec.command, (spec.command, *spec.version_args))
        clients.append(
            {
                "name": spec.name,
                "profile": spec.profile,
                "support": spec.support,
                "command": spec.command,
                "available": probe["available"],
                "detail": probe["detail"],
                "path": probe["path"],
                "recommended_backend": (
                    spec.backend_windows if platform.system() == "Windows" else spec.backend_posix
                ),
                "notes": spec.notes,
            }
        )

    recommended = [client for client in clients if client["support"] == "full" and client["available"]]
    suggested = default_backend_name()
    return {
        "platform": platform.system(),
        "python": platform.python_version(),
        "distro": distro_name,
        "backends": backends,
        "transports": [
            {"name": "sse", "available": True, "detail": "room stream over HTTP text/event-stream"},
            {"name": "websocket", "available": True, "detail": "bidirectional room control over /ws"},
            {"name": "room_poll", "available": True, "detail": "cursor-based fallback for scripted clients"},
        ],
        "clients": clients,
        "profiles": profile_rows(),
        "recommended_backend": suggested,
        "recommended_clients": [client["profile"] for client in recommended],
    }


def render_doctor(report: Dict[str, Any]) -> str:
    lines = [
        f"platform: {report['platform']}",
        f"python:   {report['python']}",
        f"default backend: {report['recommended_backend']}",
        "",
        "Backends:",
    ]
    for item in report["backends"]:
        state = "OK" if item["available"] else "MISS"
        lines.append(f"  - {item['name']}: {state}  {item['detail']}")

    lines.append("")
    lines.append("Transports:")
    for item in report.get("transports", []):
        state = "OK" if item["available"] else "MISS"
        lines.append(f"  - {item['name']}: {state}  {item['detail']}")

    lines.append("")
    lines.append("Supported CLI tools:")
    for item in report["clients"]:
        state = "OK" if item["available"] else "MISS"
        tag = "full" if item["support"] == "full" else "community"
        lines.append(
            f"  - {item['profile']}: {state} [{tag}] "
            f"backend={item['recommended_backend']}  {item['detail']}"
        )

    if report["recommended_clients"]:
        lines.append("")
        lines.append(
            "Ready-to-use profiles: " + ", ".join(report["recommended_clients"])
        )
    return "\n".join(lines)
