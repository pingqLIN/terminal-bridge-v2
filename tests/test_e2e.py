"""End-to-end integration tests requiring real tmux."""

import json
import shutil
import socket
import subprocess
import threading
import time
import urllib.request

import pytest

from tb2.backend import TmuxBackend, TmuxError


pytestmark = pytest.mark.e2e

TMUX_AVAILABLE = shutil.which("tmux") is not None
skip_no_tmux = pytest.mark.skipif(not TMUX_AVAILABLE, reason="tmux not installed")


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


@pytest.fixture
def tmux_session():
    """Create a real tmux session and clean up after."""
    backend = TmuxBackend(use_wsl=False)
    session = "tb2_e2e_test"
    # Kill any leftover session
    try:
        backend.kill_session(session)
    except TmuxError:
        pass
    a, b = backend.init_session(session)
    yield backend, session, a, b
    backend.kill_session(session)


@skip_no_tmux
class TestTmuxE2E:
    def test_init_and_list(self, tmux_session):
        backend, session, a, b = tmux_session
        assert backend.has_session(session)
        panes = backend.list_panes(session)
        # Filter to only our session's panes
        session_panes = [p for p in panes if p[0].startswith(session)]
        assert len(session_panes) == 2

    def test_send_and_capture(self, tmux_session):
        backend, session, a, b = tmux_session
        backend.send(a, "echo tb2_test_marker", enter=True)
        time.sleep(0.5)
        lines = backend.capture(a)
        assert any("tb2_test_marker" in ln for ln in lines)

    def test_capture_both(self, tmux_session):
        backend, session, a, b = tmux_session
        backend.send(a, "echo pane_a_marker", enter=True)
        backend.send(b, "echo pane_b_marker", enter=True)
        time.sleep(0.5)
        lines_a, lines_b = backend.capture_both(a, b)
        assert any("pane_a_marker" in ln for ln in lines_a)
        assert any("pane_b_marker" in ln for ln in lines_b)


@skip_no_tmux
class TestMCPServerE2E:
    def _rpc(self, port, method, params):
        body = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params,
        }).encode()
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/mcp",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())

    def test_server_tools_list(self):
        from tb2.server import run_server
        port = _free_port()

        server_thread = threading.Thread(
            target=run_server, args=("127.0.0.1", port), daemon=True
        )
        server_thread.start()
        for _ in range(10):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=0.5):
                    break
            except Exception:
                time.sleep(0.1)

        result = self._rpc(port, "tools/list", {})
        tools = result["result"]["tools"]
        names = [t["name"] for t in tools]
        assert "terminal_init" in names
        assert "room_create" in names
        assert "status" in names
