"""Improved diff algorithm for detecting new terminal output.

Replaces the O(n^2) diff_new_lines from MVP with hash-based O(n).
"""

from __future__ import annotations

from typing import List, Tuple


def diff_new_lines(prev: List[str], curr: List[str]) -> List[str]:
    """Return lines in *curr* that are new compared to *prev*.

    Uses hash-based suffix matching — O(n) average case instead of O(n^2).
    """
    if not prev:
        return curr
    if not curr:
        return []

    # Hash each line for fast comparison.
    prev_hashes = [hash(ln) for ln in prev]
    curr_hashes = [hash(ln) for ln in curr]

    max_k = min(len(prev), len(curr))

    # Find the largest k where the last k lines of prev appear somewhere in curr.
    # Start from max_k downward — first match wins.
    for k in range(max_k, 0, -1):
        suffix_hashes = prev_hashes[-k:]

        # Scan curr from end to find where this suffix starts.
        for i in range(len(curr) - k, -1, -1):
            if curr_hashes[i: i + k] == suffix_hashes:
                # Verify with actual strings to avoid hash collisions.
                if curr[i: i + k] == prev[-k:]:
                    return curr[i + k:]

        # Early exit: if k is large and no match, smaller k won't help for stable diffs.
        if k < max_k // 2:
            break

    return curr


def strip_prompt_tail(lines: List[str], prompt_patterns: List[str] | None = None) -> List[str]:
    """Strip trailing prompt line(s) for cleaner diffs.

    If *prompt_patterns* provided (regex list), uses those.
    Otherwise falls back to simple heuristic.
    """
    if not lines:
        return lines

    import re

    last = lines[-1].rstrip()
    if not last:
        return lines[:-1]

    if prompt_patterns:
        for pat in prompt_patterns:
            if re.search(pat, last):
                return lines[:-1]
        return lines

    # Default heuristic: common shell/chat prompts.
    if last.endswith(("$", "#", ">", ">")):
        return lines[:-1]

    return lines
