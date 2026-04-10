"""Tests for tb2.service."""

from __future__ import annotations

import json
import os
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

    monkeypatch.setattr(service, "_spawn_detached", lambda cmd, log_file, env=None: _Proc())
    monkeypatch.setattr(service, "_pid_alive", lambda pid: pid == 23456)

    st = service.start_service(host="127.0.0.1", port=3190)
    saved = json.loads(Path(st.state_file).read_text(encoding="utf-8"))
    assert st.running is True
    assert st.pid == 23456
    assert st.port == 3190
    assert Path(st.state_file).exists()
    assert saved["schema_version"] == 1
    assert saved["runtime"]["launch_mode"] == "service"
    assert saved["runtime"]["continuity"]["mode"] == "fresh_start"
    assert saved["runtime"]["audit_policy_persistence"] == "service_state"
    assert saved["config"]["env_overrides"] == {}


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

    def _start(
        *,
        host: str,
        port: int,
        python_exe,
        force: bool,
        allow_remote: bool = False,
        _previous_state=None,
        _previous_runtime_active=False,
    ):
        calls["start"] = True
        assert host == "127.0.0.1"
        assert port == 3201
        assert force is True
        assert allow_remote is False
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
    monkeypatch.setattr(service, "_spawn_detached", lambda cmd, log_file, env=None: _Proc())

    st = service.restart_service(host="127.0.0.1", port=3190)

    saved = json.loads(state.read_text(encoding="utf-8"))
    assert st.running is True
    assert st.pid == 3579
    assert st.port == 3190
    assert saved["pid"] == 3579
    assert saved["host"] == "127.0.0.1"
    assert saved["port"] == 3190
    assert saved["runtime"]["continuity"]["mode"] == "restart_state_lost"
    assert saved["runtime"]["continuity"]["previous_pid"] == 2468
    assert saved["runtime"]["continuity"]["runtime_restored"] is False
    assert "rooms" not in saved
    assert "bridges" not in saved
    assert "pending_interventions" not in saved


def test_restart_service_reuses_previous_binding_when_args_omitted(monkeypatch):
    calls = {}

    monkeypatch.setattr(
        service,
        "_load_state",
        lambda path: {"host": "0.0.0.0", "port": 4567, "config": {"allow_remote": True}},
    )
    monkeypatch.setattr(
        service,
        "status_service",
        lambda *, paths=None: service.ServiceStatus(True, 2468, "0.0.0.0", 4567, "/tmp/s", "/tmp/l"),
    )
    monkeypatch.setattr(
        service,
        "stop_service",
        lambda: service.ServiceStatus(False, None, "0.0.0.0", 4567, "/tmp/s", "/tmp/l"),
    )

    def _start(
        *,
        host: str,
        port: int,
        python_exe,
        force: bool,
        allow_remote: bool = False,
        _previous_state=None,
        _previous_runtime_active=False,
    ):
        calls["host"] = host
        calls["port"] = port
        calls["force"] = force
        calls["allow_remote"] = allow_remote
        calls["previous_state"] = _previous_state
        calls["previous_runtime_active"] = _previous_runtime_active
        return service.ServiceStatus(True, 3579, host, port, "/tmp/s", "/tmp/l")

    monkeypatch.setattr(service, "start_service", _start)

    st = service.restart_service()

    assert st.host == "0.0.0.0"
    assert st.port == 4567
    assert calls["host"] == "0.0.0.0"
    assert calls["port"] == 4567
    assert calls["force"] is True
    assert calls["allow_remote"] is True
    assert calls["previous_runtime_active"] is True
    assert calls["previous_state"] == {"host": "0.0.0.0", "port": 4567, "config": {"allow_remote": True}}


def test_restart_service_preserves_audit_env_overrides(tmp_path, monkeypatch):
    monkeypatch.setenv("TB2_STATE_DIR", str(tmp_path))
    state = tmp_path / "server.state.json"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(
        json.dumps(
            {
                "pid": 2468,
                "host": "127.0.0.1",
                "port": 3189,
                "started_at": 123.0,
                "config": {
                    "env_overrides": {
                        "TB2_AUDIT": "1",
                        "TB2_AUDIT_DIR": "/tmp/tb2-audit",
                        "TB2_AUDIT_TEXT_MODE": "mask",
                    }
                },
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
    seen = {}

    def _alive(pid: int) -> bool:
        if pid == 2468:
            return alive["old"]
        return pid == 3579

    def _term(pid: int, timeout: float):
        alive["old"] = False

    def _spawn(*, cmd, log_file, env=None):
        seen["env"] = dict(env or {})
        return _Proc()

    monkeypatch.delenv("TB2_AUDIT", raising=False)
    monkeypatch.delenv("TB2_AUDIT_DIR", raising=False)
    monkeypatch.delenv("TB2_AUDIT_TEXT_MODE", raising=False)
    monkeypatch.setattr(service, "_pid_alive", _alive)
    monkeypatch.setattr(service, "_terminate_pid", _term)
    monkeypatch.setattr(service, "_spawn_detached", _spawn)

    st = service.restart_service(host="127.0.0.1", port=3190)

    saved = json.loads(state.read_text(encoding="utf-8"))
    assert st.running is True
    assert seen["env"]["TB2_AUDIT"] == "1"
    assert seen["env"]["TB2_AUDIT_DIR"] == "/tmp/tb2-audit"
    assert seen["env"]["TB2_AUDIT_TEXT_MODE"] == "mask"
    assert saved["config"]["env_overrides"]["TB2_AUDIT"] == "1"
    assert saved["config"]["env_overrides"]["TB2_AUDIT_DIR"] == "/tmp/tb2-audit"
    assert saved["runtime"]["audit_policy_persistence"] == "service_state"


def test_restart_service_treats_stale_state_as_fresh_start(tmp_path, monkeypatch):
    monkeypatch.setenv("TB2_STATE_DIR", str(tmp_path))
    state = tmp_path / "server.state.json"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(
        json.dumps(
            {
                "pid": 2468,
                "host": "0.0.0.0",
                "port": 4567,
                "started_at": 123.0,
                "config": {
                    "allow_remote": True,
                    "env_overrides": {
                        "TB2_AUDIT": "1",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    class _Proc:
        pid = 3579

        @staticmethod
        def poll():
            return None

    seen = {}

    def _alive(pid: int) -> bool:
        return pid == 3579

    def _spawn(*, cmd, log_file, env=None):
        seen["env"] = dict(env or {})
        return _Proc()

    monkeypatch.setattr(service, "_pid_alive", _alive)
    monkeypatch.setattr(service, "_spawn_detached", _spawn)

    st = service.restart_service()

    saved = json.loads(state.read_text(encoding="utf-8"))
    assert st.running is True
    assert st.host == "0.0.0.0"
    assert st.port == 4567
    assert seen["env"]["TB2_AUDIT"] == "1"
    assert saved["runtime"]["continuity"]["mode"] == "fresh_start"
    assert saved["runtime"]["continuity"]["previous_pid"] is None
    assert saved["runtime"]["continuity"]["previous_started_at"] is None


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
    monkeypatch.setattr(service, "_spawn_detached", lambda cmd, log_file, env=None: _Proc())

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

    monkeypatch.setattr(service, "_spawn_detached", lambda cmd, log_file, env=None: _DeadProc())
    monkeypatch.setattr(service, "_pid_alive", lambda pid: False)

    with pytest.raises(RuntimeError):
        service.start_service(host="127.0.0.1", port=3190)

    state = tmp_path / "server.state.json"
    assert not state.exists()

def test_runtime_contract_defaults_to_direct_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("TB2_STATE_DIR", str(tmp_path))

    runtime = service.runtime_contract()

    assert runtime["state_persistence"] == "memory_only"
    assert runtime["restart_behavior"] == "state_lost"
    assert runtime["recovery_source"] == "audit_history_only"
    assert runtime["launch_mode"] == "direct"
    assert runtime["snapshot_schema_version"] is None
    assert runtime["audit_policy_persistence"] == "process_env_only"
    assert runtime["continuity"]["mode"] == "process_local_only"
    assert runtime["continuity"]["runtime_restored"] is False


def test_runtime_contract_tolerates_invalid_schema_version(tmp_path, monkeypatch):
    monkeypatch.setenv("TB2_STATE_DIR", str(tmp_path))
    state = tmp_path / "server.state.json"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(
        json.dumps(
            {
                "schema_version": "oops",
                "runtime": {
                    "launch_mode": "service",
                },
            }
        ),
        encoding="utf-8",
    )

    runtime = service.runtime_contract()

    assert runtime["launch_mode"] == "service"
    assert runtime["snapshot_schema_version"] is None


def test_runtime_contract_reads_service_state_metadata(tmp_path, monkeypatch):
    monkeypatch.setenv("TB2_STATE_DIR", str(tmp_path))
    state = tmp_path / "server.state.json"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "pid": 2468,
                "host": "127.0.0.1",
                "port": 3189,
                "runtime": {
                    "launch_mode": "service",
                    "audit_policy_persistence": "service_state",
                    "continuity": {
                        "mode": "restart_state_lost",
                        "runtime_restored": False,
                        "previous_pid": 1357,
                        "previous_started_at": 12.5,
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    runtime = service.runtime_contract()

    assert runtime["launch_mode"] == "service"
    assert runtime["snapshot_schema_version"] == 1
    assert runtime["audit_policy_persistence"] == "service_state"
    assert runtime["continuity"]["mode"] == "restart_state_lost"
    assert runtime["continuity"]["previous_pid"] == 1357
    assert runtime["continuity"]["previous_started_at"] == 12.5
    assert runtime["state_persistence"] == "service_state_snapshot"
    assert runtime["restart_behavior"] == "best_effort_restore"
    assert runtime["recovery_source"] == "service_state_snapshot"
    assert runtime["workstream_count"] == 0
    assert runtime["security_posture"]["support_tier"] == "local-first-supported"


def test_runtime_contract_counts_persisted_workstreams(tmp_path, monkeypatch):
    monkeypatch.setenv("TB2_STATE_DIR", str(tmp_path))
    state = tmp_path / "server.state.json"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "pid": os.getpid(),
                "runtime": {
                    "launch_mode": "service",
                    "continuity": {
                        "mode": "restart_restored",
                        "runtime_restored": True,
                    },
                },
                "workstreams": [{"workstream_id": "main-flow"}],
            }
        ),
        encoding="utf-8",
    )

    runtime = service.runtime_contract()

    assert runtime["workstream_count"] == 1
    assert runtime["continuity"]["mode"] == "restart_restored"
    assert runtime["continuity"]["runtime_restored"] is True


def test_persist_runtime_snapshot_updates_service_state(tmp_path, monkeypatch):
    monkeypatch.setenv("TB2_STATE_DIR", str(tmp_path))
    state = tmp_path / "server.state.json"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "pid": os.getpid(),
                "runtime": {
                    "launch_mode": "service",
                    "continuity": {
                        "mode": "restart_state_lost",
                        "runtime_restored": False,
                    },
                },
                "workstreams": [],
            }
        ),
        encoding="utf-8",
    )

    ok = service.persist_runtime_snapshot(
        workstreams=[{"workstream_id": "main-flow", "room_id": "room-a"}],
        continuity={
            "mode": "restart_restored",
            "runtime_restored": True,
            "previous_pid": 1234,
            "previous_started_at": 12.5,
        },
    )

    saved = json.loads(state.read_text(encoding="utf-8"))
    assert ok is True
    assert saved["runtime"]["state_persistence"] == "service_state_snapshot"
    assert saved["runtime"]["continuity"]["mode"] == "restart_restored"
    assert saved["runtime"]["continuity"]["runtime_restored"] is True
    assert saved["workstreams"][0]["workstream_id"] == "main-flow"


def test_start_service_rejects_non_loopback_without_allow_remote(tmp_path, monkeypatch):
    monkeypatch.setenv("TB2_STATE_DIR", str(tmp_path))

    with pytest.raises(RuntimeError, match="non-loopback bind requires explicit acknowledgment"):
        service.start_service(host="0.0.0.0", port=3190)


def test_runtime_contract_reads_remote_allowance_from_service_state(tmp_path, monkeypatch):
    monkeypatch.setenv("TB2_STATE_DIR", str(tmp_path))
    state = tmp_path / "server.state.json"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "pid": 2468,
                "host": "10.0.0.5",
                "port": 3189,
                "config": {
                    "allow_remote": True,
                    "env_overrides": {},
                },
                "runtime": {
                    "launch_mode": "service",
                },
            }
        ),
        encoding="utf-8",
    )

    runtime = service.runtime_contract()

    assert runtime["security_posture"]["bind_scope"] == "private-network"
    assert runtime["security_posture"]["remote_access_acknowledged"] is True
