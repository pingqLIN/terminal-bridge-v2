"""Tests for tb2.support."""

from __future__ import annotations

from unittest.mock import patch

from tb2.support import doctor_report, profile_rows, render_doctor


class TestProfileRows:
    def test_rows_include_first_class_profiles(self):
        rows = profile_rows()
        names = [row["profile"] for row in rows]
        assert "codex" in names
        assert "claude-code" in names
        assert "gemini" in names
        assert "aider" in names


class TestDoctorReport:
    @patch("tb2.support._probe_tmux")
    @patch("tb2.support._probe_process")
    @patch("tb2.support._probe_pipe")
    @patch("tb2.support._probe_cmd")
    def test_report_shape(self, mock_cmd, mock_pipe, mock_process, mock_tmux):
        mock_tmux.return_value = {"name": "tmux", "available": True, "detail": "tmux 3.4"}
        mock_process.return_value = {"name": "process", "available": True, "detail": "pty ok"}
        mock_pipe.return_value = {"name": "pipe", "available": True, "detail": "pipe ok"}
        mock_cmd.return_value = {"available": True, "detail": "1.0.0", "path": "/tmp/tool"}

        report = doctor_report(distro="Ubuntu")

        assert report["distro"] == "Ubuntu"
        assert len(report["backends"]) == 3
        assert len(report["transports"]) == 3
        assert report["clients"]
        assert "profiles" in report
        assert "recommended_backend" in report

    def test_render_doctor_contains_sections(self):
        text = render_doctor({
            "platform": "Windows",
            "python": "3.11.0",
            "recommended_backend": "process",
            "backends": [{"name": "process", "available": True, "detail": "ok"}],
            "clients": [{
                "profile": "codex",
                "available": True,
                "support": "full",
                "recommended_backend": "process",
                "detail": "1.0.0",
            }],
            "recommended_clients": ["codex"],
        })
        assert "Backends:" in text
        assert "Transports:" in text
        assert "Supported CLI tools:" in text
        assert "Ready-to-use profiles: codex" in text
