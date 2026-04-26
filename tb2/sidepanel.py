"""Pure helpers for the TB2 sidepanel compatibility adapter."""

from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import gettempdir
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

from .room import Room, RoomMessage


@dataclass(frozen=True)
class SidepanelRuntime:
    codex_available: bool
    codex_path: str
    host_platform: str
    provider: str
    workdir: str


def host_platform_name(*, os_name: Optional[str] = None, proc_version_path: Optional[Path] = None) -> str:
    current_os = os.name if os_name is None else os_name
    if current_os == "nt":
        return "windows"
    version_path = Path("/proc/version") if proc_version_path is None else proc_version_path
    if version_path.exists():
        try:
            text = version_path.read_text(encoding="utf-8").lower()
        except OSError:
            text = ""
        if "microsoft" in text:
            return "wsl"
    return "posix"


def runtime_from_env(
    environ: Mapping[str, str],
    *,
    which: Callable[[str], Optional[str]],
    home: Path,
) -> SidepanelRuntime:
    codex_path = str(environ.get("TB2_SIDEPANEL_CODEX", "")).strip() or str(which("codex") or "")
    workdir = str(environ.get("TB2_SIDEPANEL_WORKDIR", "")).strip() or str(home)
    return SidepanelRuntime(
        codex_available=bool(codex_path),
        codex_path=codex_path or "codex",
        host_platform=host_platform_name(),
        provider="local-tb2-codex-bridge",
        workdir=workdir,
    )


def health_payload(
    runtime: SidepanelRuntime,
    *,
    backend_ready: bool,
    backend_detail: str,
    room_count: int,
) -> Dict[str, Any]:
    note = (
        "Sidepanel compatibility uses TB2 rooms plus one-shot Codex exec subprocess runs. "
        "Recent room transcript is wrapped into each prompt, and poll returns streaming log previews "
        "followed by the final assistant message."
    )
    if backend_detail:
        note = note + f" Backend bootstrap check failed: {backend_detail}"
    return {
        "ok": True,
        "ready": runtime.codex_available and backend_ready,
        "provider": runtime.provider,
        "bridgeMode": "tb2-codex",
        "codexAvailable": runtime.codex_available,
        "tb2RuntimeInstalled": True,
        "backendReady": backend_ready,
        "roomCount": room_count,
        "note": note,
        "hostPlatform": runtime.host_platform,
        "runtimeCodexPath": runtime.codex_path,
        "runtimeWorkdir": runtime.workdir,
    }


def iso_timestamp(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def message_role(msg: RoomMessage) -> str:
    role = str(msg.meta.get("sidepanelRole", "")).strip()
    if role in {"user", "assistant", "system"}:
        return role
    if msg.author == "assistant" or msg.source_role == "assistant":
        return "assistant"
    if msg.kind in {"system", "intervention"} or msg.author == "bridge":
        return "system"
    return "user"


def message_payload(msg: RoomMessage) -> Dict[str, Any]:
    return {
        "id": msg.id,
        "role": message_role(msg),
        "text": msg.text,
        "created_at": iso_timestamp(msg.ts),
        "meta": dict(msg.meta),
    }


def render_prompt(room: Room, prompt: str) -> str:
    after_id = max(0, room.latest_id - 12)
    transcript = []
    for item in room.poll(after_id=after_id, limit=12):
        if item.meta.get("streamKey") and item.meta.get("final") is False:
            continue
        transcript.append(f"{message_role(item).upper()}:\n{item.text}")
    transcript.append(f"USER:\n{prompt}")
    return "\n\n".join(
        [
            "You are continuing a browser side panel terminal conversation.",
            "Use the room transcript below as context and answer the latest user message.",
            "\n\n".join(transcript),
        ]
    )


def render_live_log(text: str) -> str:
    return "Streaming bridge log:\n" + text


def run_paths(room_id: str, *, now: Optional[float] = None, tempdir: Optional[Path] = None) -> Tuple[str, str, str]:
    seed = time.time() if now is None else now
    run_id = hashlib.sha1(f"{room_id}:{seed}".encode("utf-8")).hexdigest()[:12]
    root = Path(gettempdir()) if tempdir is None else tempdir
    return (
        run_id,
        str(root / f"tb2-sidepanel-{room_id}-{run_id}.log"),
        str(root / f"tb2-sidepanel-{room_id}-{run_id}.out"),
    )


def read_text_if_exists(path: str) -> str:
    if not path:
        return ""
    target = Path(path)
    if not target.exists():
        return ""
    try:
        return target.read_text(encoding="utf-8", errors="ignore").strip()
    except OSError:
        return ""


def read_tail_if_exists(path: str, *, limit: int = 4000) -> str:
    text = read_text_if_exists(path)
    return text[-limit:].strip() if text else ""
