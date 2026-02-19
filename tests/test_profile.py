"""Tests for tb2.profile — ToolProfile, registry, strip_ansi."""

import pytest

from tb2.profile import (
    BUILTIN_PROFILES,
    ToolProfile,
    get_profile,
    list_profiles,
    register_profile,
    strip_ansi,
)


class TestToolProfile:
    def test_is_prompt_dollar(self):
        p = BUILTIN_PROFILES["generic"]
        assert p.is_prompt("user@host:~$ ")
        assert p.is_prompt("$ ")

    def test_is_prompt_empty_line(self):
        p = BUILTIN_PROFILES["generic"]
        assert p.is_prompt("")
        assert p.is_prompt("   ")

    def test_is_prompt_codex(self):
        p = BUILTIN_PROFILES["codex"]
        assert p.is_prompt("› ")

    def test_is_prompt_claude_code(self):
        p = BUILTIN_PROFILES["claude-code"]
        assert p.is_prompt("claude> ")

    def test_is_prompt_aider(self):
        p = BUILTIN_PROFILES["aider"]
        assert p.is_prompt("aider> ")

    def test_is_prompt_gemini(self):
        p = BUILTIN_PROFILES["gemini"]
        assert p.is_prompt("✦ ")

    def test_is_prompt_not_prompt(self):
        p = BUILTIN_PROFILES["generic"]
        assert not p.is_prompt("hello world")

    def test_parse_message_with_prefix(self):
        p = ToolProfile(name="test", msg_prefix="MSG:")
        assert p.parse_message("MSG: hello world") == "hello world"

    def test_parse_message_no_match(self):
        p = ToolProfile(name="test", msg_prefix="MSG:")
        assert p.parse_message("regular text") is None

    def test_parse_message_empty_content(self):
        p = ToolProfile(name="test", msg_prefix="MSG:")
        assert p.parse_message("MSG: ") is None

    def test_parse_message_leading_space(self):
        p = ToolProfile(name="test", msg_prefix="MSG:")
        assert p.parse_message("  MSG: hello") == "hello"

    def test_lazy_compilation(self):
        p = ToolProfile(name="test", prompt_patterns=[r"\$\s*$"])
        assert p._compiled == []
        p.is_prompt("$ ")
        assert len(p._compiled) == 1


class TestStripAnsi:
    def test_strips_color_codes(self):
        assert strip_ansi("\x1b[31mred\x1b[0m") == "red"

    def test_strips_bold(self):
        assert strip_ansi("\x1b[1mbold\x1b[22m") == "bold"

    def test_no_ansi(self):
        assert strip_ansi("plain text") == "plain text"

    def test_empty(self):
        assert strip_ansi("") == ""


class TestRegistry:
    def test_builtin_profiles_exist(self):
        names = list_profiles()
        assert "generic" in names
        assert "codex" in names
        assert "claude-code" in names
        assert "aider" in names
        assert "llama" in names
        assert "gemini" in names

    def test_get_unknown_returns_generic(self):
        p = get_profile("nonexistent")
        assert p.name == "generic"

    def test_get_known(self):
        p = get_profile("codex")
        assert p.name == "codex"

    def test_register_custom(self):
        custom = ToolProfile(name="my-tool", prompt_patterns=[r"my-tool>\s*$"])
        register_profile(custom)
        assert get_profile("my-tool").name == "my-tool"
        assert "my-tool" in list_profiles()

    def test_list_profiles_sorted(self):
        names = list_profiles()
        assert names == sorted(names)
