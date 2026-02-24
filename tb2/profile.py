"""Tool profiles for different CLI LLM tools.

Each profile describes how a specific CLI tool behaves so the broker
can detect prompts, parse messages, and handle escape sequences.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ToolProfile:
    """Describes the I/O behaviour of a CLI LLM tool."""

    name: str
    prompt_patterns: List[str] = field(default_factory=lambda: [r"\$\s*$", r"#\s*$", r">\s*$"])
    msg_prefix: str = "MSG:"
    strip_ansi: bool = False
    capture_lines: int = 200

    # Compiled patterns (populated on first use).
    _compiled: List[re.Pattern] = field(default_factory=list, repr=False, compare=False)

    def _ensure_compiled(self) -> None:
        if not self._compiled and self.prompt_patterns:
            self._compiled = [re.compile(p) for p in self.prompt_patterns]

    def is_prompt(self, line: str) -> bool:
        """Return True if *line* looks like a waiting-for-input prompt."""
        self._ensure_compiled()
        s = line.rstrip()
        if not s:
            return True
        return any(p.search(s) for p in self._compiled)

    def parse_message(self, line: str) -> Optional[str]:
        """If *line* contains a forwarding message, return its content."""
        s = line.lstrip()
        want = self.msg_prefix + " "
        if not s.startswith(want):
            return None
        msg = s[len(want):].strip()
        return msg or None


# ---------------------------------------------------------------------------
# Built-in profiles
# ---------------------------------------------------------------------------

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


BUILTIN_PROFILES: Dict[str, ToolProfile] = {
    "generic": ToolProfile(
        name="generic",
        prompt_patterns=[r"\$\s*$", r"#\s*$", r">\s*$"],
    ),
    "codex": ToolProfile(
        name="codex",
        prompt_patterns=[r"›\s*$", r">\s*$", r"\$\s*$"],
        msg_prefix="MSG:",
    ),
    "claude-code": ToolProfile(
        name="claude-code",
        prompt_patterns=[r">\s*$", r"claude>\s*$", r"\$\s*$"],
        msg_prefix="MSG:",
    ),
    "aider": ToolProfile(
        name="aider",
        prompt_patterns=[r"aider>\s*$", r">\s*$"],
        msg_prefix="MSG:",
        strip_ansi=True,
    ),
    "llama": ToolProfile(
        name="llama",
        prompt_patterns=[r">\s*$", r"llama>\s*$"],
        msg_prefix="MSG:",
    ),
    "gemini": ToolProfile(
        name="gemini",
        prompt_patterns=[r">\s*$", r"gemini>\s*$", r"✦\s*$"],
        msg_prefix="MSG:",
        strip_ansi=True,
    ),
    "acpx": ToolProfile(
        name="acpx",
        prompt_patterns=[r"\$\s*$", r"#\s*$", r">\s*$"],
        msg_prefix="MSG:",
        strip_ansi=True,
    ),
}


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_registry: Dict[str, ToolProfile] = dict(BUILTIN_PROFILES)


def register_profile(profile: ToolProfile) -> None:
    _registry[profile.name] = profile


def get_profile(name: str) -> ToolProfile:
    if name not in _registry:
        return _registry["generic"]
    return _registry[name]


def list_profiles() -> List[str]:
    return sorted(_registry.keys())
