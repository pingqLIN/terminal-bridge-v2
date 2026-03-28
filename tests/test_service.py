"""Tests for tb2.service."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tb2 import service


def test_service_paths_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("TB2_STATE_DIR", str(tmp_path))
    paths = service.ServicePaths.discover()
    assert paths.root == tmp_path.resolve()
    assert paths.state_file == tmp_path.resolve() / "server.state.json"


def test_state_root_uses_macos_application_support(tmp_path, monkeypatch):
    monkeypatch.delenv("TB2_STATE_DIR", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    monkeypatch.setattr(service.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(service.Path, "home", staticmethod(lambda: tmp_path))
    assert service._state_root() == tmp_path / "Library" / "Application Support" / "tb2"


def test_state_root_uses_xdg_on_macos(tmp_path, monkeypatch):
    monkeypatch.delenv("TB2_STATE_DIR", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg"))
    monkeypatch.setattr(service.platform, "system", lambda: "Darwin")
    assert service._state_root() == tmp_path / "xdg" / "tb2"


def test_state_root_preserves_legacy_macos_state(tmp_path, monkeypatch):
    monkeypatch.delenv("TB2_STATE_DIR", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    monkeypatch.setattr(service.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(service.Path, "home", staticmethod(lambda: tmp_path))
    legacy = tmp_path / ".local" / "state" / "tb2"
    legacy.mkdir(parents=True, exist_ok=True)
    (legacy / "server.state.json").write_text("{}", encoding="utf-8")
    assert service._state_root() == legacy


def test_tail_log_returns_last_lines(tmp_path, monkeypatch):
    monkeypatch.setenv("TB2_STATE_DIR", str(tmp_path))
    log = tmp_path / "server.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("a\nb\nc\n", encoding="utf-8")
    assert service.tail_log(lines=2) == ["b", "c"]


def test_status_clears_stale_state(tmp_path, monkeypatch):
    monkeypatch.setenv("TB2_STATE_DIR", str(tmp_path))
    state = tmp_path / "server.state.json"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(json.dumps({"pid": 999999, "host": "127.0.0.1", "port": 3189}), encoding="utf-8")

    st = service.status_service()
    assert st.running is False
    assert st.pid is None
    assert not state.exists()


def test_start_service_writes_state(tmp_path, monkeypatch):
    monkeypatch.setenv("TB2_STATE_DIR", str(tmp_path))

    class _Proc:
        pid = 23456

        @staticmethod
        def poll():
            return None

    monkeypatch.setattr(service, "_spawn_detached", lambda cmd, log_file: _Proc())
    monkeypatch.setattr(service, "_pid_alive", lambda pid: pid == 23456)

    st = service.start_service(host="127.0.0.1", port=3190)
    assert st.running is True
    assert st.pid == 23456
    assert st.port == 3190
    assert Path(st.state_file).exists()


def test_stop_service_terminates_running_pid(tmp_path, monkeypatch):
    monkeypatch.setenv("TB2_STATE_DIR", str(tmp_path))
    state = tmp_path / "server.state.json"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(json.dumps({"pid": 43210, "host": "127.0.0.1", "port": 3189}), encoding="utf-8")

    called = {"value": False}

    def _term(pid: int, timeout: float):
        called["value"] = True
        assert pid == 43210
        assert timeout == 8.0

    monkeypatch.setattr(service, "_pid_alive", lambda pid: True)
    monkeypatch.setattr(service, "_terminate_pid", _term)

    st = service.stop_service(timeout=8.0)
    assert called["value"] is True
    assert st.running is False
    assert not state.exists()


def test_restart_service_calls_stop_then_start(monkeypatch):
    calls = {"stop": False, "start": False}

    def _stop(*, timeout: float = 8.0):
        calls["stop"] = True
        return service.ServiceStatus(False, None, "127.0.0.1", 3189, "/tmp/s", "/tmp/l")

    def _start(*, host: str, port: int, python_exe, force: bool):
        calls["start"] = True
        assert host == "127.0.0.1"
        assert port == 3201
        assert force is True
        return service.ServiceStatus(True, 1, host, port, "/tmp/s", "/tmp/l")

    monkeypatch.setattr(service, "stop_service", _stop)
    monkeypatch.setattr(service, "start_service", _start)

    st = service.restart_service(host="127.0.0.1", port=3201)
    assert calls["stop"] is True
    assert calls["start"] is True
    assert st.running is True
    assert st.port == 3201


def test_restart_service_discards_runtime_state_payload(tmp_path, monkeypatch):
    monkeypatch.setenv("TB2_STATE_DIR", str(tmp_path))
    state = tmp_path / "server.state.json"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(
        json.dumps(
            {
                "pid": 2468,
                "host": "127.0.0.1",
                "port": 3189,
                "rooms": [{"id": "room-a"}],
                "bridges": [{"id": "bridge-a"}],
                "pending_interventions": [{"id": 1}],
            }
        ),
        encoding="utf-8",
    )

    class _Proc:
        pid = 3579

        @staticmethod
        def poll():
            return None

    alive = {"old": True}

    def _alive(pid: int) -> bool:
        if pid == 2468:
            return alive["old"]
        return pid == 3579

    def _term(pid: int, timeout: float):
        assert pid == 2468
        assert timeout == 8.0
        alive["old"] = False

    monkeypatch.setattr(service, "_pid_alive", _alive)
    monkeypatch.setattr(service, "_terminate_pid", _term)
    monkeypatch.setattr(service, "_spawn_detached", lambda cmd, log_file: _Proc())

    st = service.restart_service(host="127.0.0.1", port=3190)

    saved = json.loads(state.read_text(encoding="utf-8"))
    assert st.running is True
    assert st.pid == 3579
    assert st.port == 3190
    assert saved["pid"] == 3579
    assert saved["host"] == "127.0.0.1"
    assert saved["port"] == 3190
    assert "rooms" not in saved
    assert "bridges" not in saved
    assert "pending_interventions" not in saved


def test_start_service_force_stops_existing(tmp_path, monkeypatch):
    monkeypatch.setenv("TB2_STATE_DIR", str(tmp_path))
    state = tmp_path / "server.state.json"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(json.dumps({"pid": 2468, "host": "127.0.0.1", "port": 3189}), encoding="utf-8")

    class _Proc:
        pid = 3579

        @staticmethod
        def poll():
            return None

    called = {"terminated": False}
    alive = {"old": True}

    def _alive(pid: int) -> bool:
        if pid == 2468:
            return alive["old"]
        return pid == 3579

    def _term(pid: int, timeout: float):
        called["terminated"] = True
        assert pid == 2468
        assert timeout == 6.0
        alive["old"] = False

    monkeypatch.setattr(service, "_pid_alive", _alive)
    monkeypatch.setattr(service, "_terminate_pid", _term)
    monkeypatch.setattr(service, "_spawn_detached", lambda cmd, log_file: _Proc())

    st = service.start_service(host="127.0.0.1", port=3190, force=True)
    assert called["terminated"] is True
    assert st.running is True
    assert st.pid == 3579


def test_start_service_cleans_state_when_process_exits_immediately(tmp_path, monkeypatch):
    monkeypatch.setenv("TB2_STATE_DIR", str(tmp_path))

    class _DeadProc:
        pid = 6789

        @staticmethod
        def poll():
            return 1

    monkeypatch.setattr(service, "_spawn_detached", lambda cmd, log_file: _DeadProc())
    monkeypatch.setattr(service, "_pid_alive", lambda pid: False)

    with pytest.raises(RuntimeError):
        service.start_service(host="127.0.0.1", port=3190)

    state = tmp_path / "server.state.json"
    assert not state.exists()
