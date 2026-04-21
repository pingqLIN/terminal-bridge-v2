"""Tests for tb2.governance."""

import json
from pathlib import Path

from tb2.governance import (
    governance_order,
    governance_overlay_schema,
    governance_sample_overlay,
    load_governance_layers,
    resolve_governance,
    validate_governance_overlay,
)


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


def test_load_governance_layers_merges_json_overlay(tmp_path) -> None:
    config = tmp_path / "governance.json"
    config.write_text(json.dumps({
        "environment": {
            "wsl-tmux": {
                "preferred_backend": "pipe",
                "shell_policy": "custom-posix",
            }
        },
        "instruction_profile": {
            "approval-gate": {
                "approval_mode": "strict-required",
            }
        },
    }), encoding="utf-8")

    result = load_governance_layers(str(config))

    assert result["environment"]["wsl-tmux"]["preferred_backend"] == "pipe"
    assert result["environment"]["wsl-tmux"]["shell_policy"] == "custom-posix"
    assert result["instruction_profile"]["approval-gate"]["approval_mode"] == "strict-required"


def test_resolve_governance_uses_config_overlay(tmp_path) -> None:
    config = tmp_path / "governance.json"
    config.write_text(json.dumps({
        "model": {
            "gpt-5.4": {
                "reasoning_depth": "very-high",
            }
        }
    }), encoding="utf-8")

    result = resolve_governance(
        model="gpt-5.4",
        config_path=str(config),
    )

    assert result["config_path"] == str(config)
    assert result["effective_config"]["reasoning_depth"] == "very-high"
    assert result["provenance"]["reasoning_depth"] == {
        "layer": "model",
        "name": "gpt-5.4",
    }


def test_load_governance_layers_rejects_missing_file() -> None:
    try:
        load_governance_layers("/tmp/does-not-exist-governance.json")
    except ValueError as exc:
        assert str(exc) == "governance config not found: /tmp/does-not-exist-governance.json"
        return
    raise AssertionError("expected ValueError")


def test_load_governance_layers_rejects_invalid_json(tmp_path) -> None:
    config = tmp_path / "bad.json"
    config.write_text("{bad", encoding="utf-8")

    try:
        load_governance_layers(str(config))
    except ValueError as exc:
        assert str(exc) == f"invalid governance JSON: {config}"
        return
    raise AssertionError("expected ValueError")


def test_load_governance_layers_rejects_unknown_layer(tmp_path) -> None:
    config = tmp_path / "bad.json"
    config.write_text(json.dumps({"unknown": {"demo": {"x": 1}}}), encoding="utf-8")

    try:
        load_governance_layers(str(config))
    except ValueError as exc:
        assert str(exc) == "unknown governance layer: unknown"
        return
    raise AssertionError("expected ValueError")


def test_load_governance_layers_rejects_invalid_entry_shape(tmp_path) -> None:
    config = tmp_path / "bad.json"
    config.write_text(json.dumps({"environment": {"wsl-tmux": ["bad"]}}), encoding="utf-8")

    try:
        load_governance_layers(str(config))
    except ValueError as exc:
        assert str(exc) == "governance entry 'environment.wsl-tmux' must be an object"
        return
    raise AssertionError("expected ValueError")


def test_governance_overlay_schema_tracks_layer_order() -> None:
    schema = governance_overlay_schema()

    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert list(schema["properties"].keys()) == governance_order()


def test_governance_sample_overlay_validates() -> None:
    sample = governance_sample_overlay()

    validated = validate_governance_overlay(sample)

    assert validated["environment"]["wsl-tmux"]["preferred_backend"] == "tmux"
    assert validated["instruction_profile"]["approval-gate"]["review_mode"] == "manual"


def test_repo_sample_file_matches_exported_sample() -> None:
    path = Path(__file__).resolve().parents[1] / "examples" / "governance.layers.sample.json"
    sample = json.loads(path.read_text(encoding="utf-8"))

    assert sample == governance_sample_overlay()


def test_repo_schema_file_matches_exported_schema() -> None:
    path = Path(__file__).resolve().parents[1] / "schemas" / "governance.layers.schema.json"
    schema = json.loads(path.read_text(encoding="utf-8"))

    assert schema == governance_overlay_schema()
