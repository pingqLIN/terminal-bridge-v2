"""Tests for pure sidepanel adapter helpers."""

from __future__ import annotations

from pathlib import Path

from tb2.room import create_room
from tb2.sidepanel import (
    SidepanelRuntime,
    health_payload,
    host_platform_name,
    read_tail_if_exists,
    render_prompt,
    run_paths,
)


def test_host_platform_name_detects_wsl(tmp_path):
    version = tmp_path / "version"
    version.write_text("Linux version 5.15.0 Microsoft", encoding="utf-8")

    assert host_platform_name(os_name="posix", proc_version_path=version) == "wsl"


def test_health_payload_appends_backend_failure_detail():
    runtime = SidepanelRuntime(
        codex_available=False,
        codex_path="codex",
        host_platform="posix",
        provider="local-tb2-codex-bridge",
        workdir="/tmp",
    )

    payload = health_payload(runtime, backend_ready=False, backend_detail="backend missing", room_count=2)

    assert payload["ready"] is False
    assert payload["roomCount"] == 2
    assert "backend missing" in payload["note"]


def test_render_prompt_skips_partial_stream_preview():
    room = create_room("sidepanel-prompt")
    room.post(author="user", text="first", kind="chat", meta={"sidepanelRole": "user"})
    room.post(
        author="bridge",
        text="partial",
        kind="system",
        meta={"sidepanelRole": "system", "streamKey": "abc", "final": False},
    )
    room.post(author="assistant", text="done", kind="chat", meta={"sidepanelRole": "assistant"})

    prompt = render_prompt(room, "latest")

    assert "USER:\nfirst" in prompt
    assert "ASSISTANT:\ndone" in prompt
    assert "partial" not in prompt
    assert "USER:\nlatest" in prompt


def test_run_paths_use_expected_names(tmp_path):
    run_id, log_path, output_path = run_paths("room-1", now=123.0, tempdir=tmp_path)

    assert run_id
    assert Path(log_path).name == f"tb2-sidepanel-room-1-{run_id}.log"
    assert Path(output_path).name == f"tb2-sidepanel-room-1-{run_id}.out"


def test_read_tail_if_exists_limits_output(tmp_path):
    target = tmp_path / "tail.txt"
    target.write_text("0123456789", encoding="utf-8")

    assert read_tail_if_exists(str(target), limit=4) == "6789"
