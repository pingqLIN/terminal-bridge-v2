"""Tests for tb2.diff — diff_new_lines and strip_prompt_tail."""

from tb2.diff import diff_new_lines, strip_prompt_tail


class TestDiffNewLines:
    def test_empty_prev_returns_all_curr(self):
        assert diff_new_lines([], ["a", "b"]) == ["a", "b"]

    def test_empty_curr_returns_empty(self):
        assert diff_new_lines(["a"], []) == []

    def test_both_empty(self):
        assert diff_new_lines([], []) == []

    def test_identical_returns_empty(self):
        lines = ["hello", "world"]
        assert diff_new_lines(lines, lines) == []

    def test_new_lines_appended(self):
        prev = ["line1", "line2"]
        curr = ["line1", "line2", "line3", "line4"]
        assert diff_new_lines(prev, curr) == ["line3", "line4"]

    def test_single_new_line(self):
        prev = ["$ echo hello", "hello"]
        curr = ["$ echo hello", "hello", "$ echo world", "world"]
        result = diff_new_lines(prev, curr)
        assert "world" in result

    def test_completely_different(self):
        prev = ["aaa", "bbb"]
        curr = ["xxx", "yyy"]
        assert diff_new_lines(prev, curr) == ["xxx", "yyy"]

    def test_partial_overlap(self):
        prev = ["a", "b", "c"]
        curr = ["b", "c", "d"]
        assert diff_new_lines(prev, curr) == ["d"]

    def test_large_window_small_overlap(self):
        prev = [f"line-{i}" for i in range(200)]
        curr = [f"line-{i}" for i in range(195, 395)]
        assert diff_new_lines(prev, curr) == [f"line-{i}" for i in range(200, 395)]


class TestStripPromptTail:
    def test_empty_list(self):
        assert strip_prompt_tail([]) == []

    def test_strips_dollar_prompt(self):
        lines = ["output", "user@host:~$"]
        assert strip_prompt_tail(lines) == ["output"]

    def test_strips_hash_prompt(self):
        lines = ["output", "root@host:#"]
        assert strip_prompt_tail(lines) == ["output"]

    def test_strips_angle_prompt(self):
        lines = ["output", ">"]
        assert strip_prompt_tail(lines) == ["output"]

    def test_no_prompt_keeps_all(self):
        lines = ["output", "more output"]
        assert strip_prompt_tail(lines) == ["output", "more output"]

    def test_custom_patterns(self):
        lines = ["output", "aider> "]
        result = strip_prompt_tail(lines, prompt_patterns=[r"aider>\s*$"])
        assert result == ["output"]

    def test_custom_pattern_no_match(self):
        lines = ["output", "some text"]
        result = strip_prompt_tail(lines, prompt_patterns=[r"aider>\s*$"])
        assert result == ["output", "some text"]

    def test_strips_blank_tail(self):
        lines = ["output", "   "]
        assert strip_prompt_tail(lines) == ["output"]
