"""Tests for tb2.governance."""

from tb2.governance import governance_order, resolve_governance


def test_governance_order_is_stable() -> None:
    assert governance_order() == ["base", "model", "environment", "instruction_profile"]


def test_resolve_governance_merges_in_layer_order() -> None:
    result = resolve_governance(
        model="gpt-5.4",
        environment="codex-local-dev",
        instruction_profile="approval-gate",
    )

    assert result["matched_layers"] == [
        {"layer": "base", "name": "default"},
        {"layer": "model", "name": "gpt-5.4"},
        {"layer": "environment", "name": "codex-local-dev"},
        {"layer": "instruction_profile", "name": "approval-gate"},
    ]
    assert result["effective_config"]["reasoning_depth"] == "high"
    assert result["effective_config"]["network_access"] == "restricted"
    assert result["effective_config"]["review_mode"] == "manual"
    assert result["effective_config"]["approval_mode"] == "required"
    assert result["provenance"]["review_mode"] == {
        "layer": "instruction_profile",
        "name": "approval-gate",
    }


def test_resolve_governance_reports_missing_layers() -> None:
    result = resolve_governance(
        model="missing-model",
        environment="wsl-tmux",
        instruction_profile="missing-profile",
    )

    assert result["matched_layers"] == [
        {"layer": "base", "name": "default"},
        {"layer": "environment", "name": "wsl-tmux"},
    ]
    assert result["missing_layers"] == [
        {"layer": "model", "name": "missing-model"},
        {"layer": "instruction_profile", "name": "missing-profile"},
    ]
    assert result["effective_config"]["preferred_backend"] == "tmux"
