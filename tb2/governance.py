"""Governance layering resolver for TB2.

Provides a simulation-first resolver that merges layered governance inputs and
reports the effective configuration plus provenance. It does not mutate runtime
state.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

LayerMap = Dict[str, Dict[str, Dict[str, Any]]]
Resolution = Dict[str, Any]

_ORDER = ("base", "model", "environment", "instruction_profile")

_DEFAULTS: LayerMap = {
    "base": {
        "default": {
            "review_mode": "guarded",
            "audit_text_mode": "mask",
            "handoff_style": "narrow",
            "operator_visibility": "full",
        }
    },
    "model": {
        "gpt-5.4": {
            "reasoning_depth": "high",
            "review_cadence": "medium",
            "status_density": "compact",
        },
        "gpt-5.4-mini": {
            "reasoning_depth": "medium",
            "review_cadence": "higher",
            "status_density": "compact",
        },
        "gpt-5.3-codex": {
            "reasoning_depth": "high",
            "review_cadence": "medium",
            "tool_bias": "strong",
        },
    },
    "environment": {
        "codex-local-dev": {
            "approval_mode": "on-request",
            "network_access": "restricted",
            "runtime_posture": "local-first",
        },
        "native-windows": {
            "platform_bias": "day-to-day",
            "preferred_backend": "process",
            "shell_policy": "windows-native",
        },
        "wsl-tmux": {
            "platform_bias": "stable-collaboration",
            "preferred_backend": "tmux",
            "shell_policy": "posix",
        },
        "private-network-operator": {
            "network_posture": "private-network-experimental",
            "approval_mode": "guarded",
        },
    },
    "instruction_profile": {
        "quick-pairing": {
            "review_mode": "auto",
            "handoff_density": "high",
        },
        "approval-gate": {
            "review_mode": "manual",
            "approval_mode": "required",
        },
        "mcp-operator": {
            "operator_visibility": "transport-and-room",
            "status_density": "dense",
        },
        "diagnostics": {
            "status_density": "dense",
            "diagnostics_priority": "high",
        },
        "governance-review": {
            "review_mode": "guarded",
            "provenance_required": True,
        },
    },
}

_SAMPLE_OVERLAY: LayerMap = {
    "environment": {
        "wsl-tmux": {
            "preferred_backend": "tmux",
            "operator_visibility": "transport-and-room",
        },
        "native-windows": {
            "preferred_backend": "process",
            "platform_bias": "day-to-day",
        },
    },
    "instruction_profile": {
        "approval-gate": {
            "approval_mode": "required",
            "review_mode": "manual",
        },
        "governance-review": {
            "status_density": "dense",
            "provenance_required": True,
        },
    },
}

_SCHEMA: Dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://tb2.local/schemas/governance.layers.schema.json",
    "title": "TB2 Governance Layer Overlay",
    "description": "Optional JSON overlay that extends or overrides built-in TB2 governance layers.",
    "type": "object",
    "properties": {
        layer: {
            "type": "object",
            "description": f"Overlay entries for the '{layer}' layer.",
            "propertyNames": {
                "type": "string",
                "minLength": 1,
            },
            "additionalProperties": {
                "type": "object",
                "description": "Freeform effective-config keys merged onto the matched entry.",
            },
        }
        for layer in _ORDER
    },
    "additionalProperties": False,
}

_AUTHORITATIVE_KEYS = ("review_mode",)
_EXCEPTION_KEYS = (
    "review_mode",
    "rate_limit",
    "window_seconds",
    "streak_limit",
    "pending_warn",
    "pending_critical",
    "pending_limit",
    "silent_seconds",
)


def governance_layers() -> LayerMap:
    """Return a copy of the built-in governance layer config."""
    return deepcopy(_DEFAULTS)


def governance_overlay_schema() -> Dict[str, Any]:
    """Return the JSON schema for governance layer overlays."""
    return deepcopy(_SCHEMA)


def governance_sample_overlay() -> LayerMap:
    """Return a sample governance layer overlay."""
    return deepcopy(_SAMPLE_OVERLAY)


def governance_authoritative_keys() -> List[str]:
    """Return governance keys that Batch A treats as authoritative."""
    return list(_AUTHORITATIVE_KEYS)


def governance_exception_keys() -> List[str]:
    """Return runtime keys that can be overridden as mutable exceptions."""
    return list(_EXCEPTION_KEYS)


def governance_key_classes(*, effective_config: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    """Classify governance keys as authoritative or advisory."""
    classes: Dict[str, str] = {}
    if effective_config:
        for key in effective_config:
            classes[key] = "authoritative" if key in _AUTHORITATIVE_KEYS else "advisory"
    for key in _AUTHORITATIVE_KEYS:
        classes.setdefault(key, "authoritative")
    return classes


def governance_runtime_projection(
    effective_config: Dict[str, Any],
    provenance: Dict[str, Dict[str, str]],
) -> Dict[str, Dict[str, Any]]:
    """Project a small authoritative subset into runtime-facing controls."""
    projection: Dict[str, Dict[str, Any]] = {}
    review_mode = effective_config.get("review_mode")
    if review_mode is not None:
        state = "enforced" if str(review_mode) in {"auto", "manual"} else "advisory"
        projection["review_mode"] = {
            "value": str(review_mode),
            "state": state,
            "source": deepcopy(provenance.get("review_mode", {})),
        }
    preferred_backend = effective_config.get("preferred_backend")
    if preferred_backend is not None:
        projection["preferred_backend"] = {
            "value": str(preferred_backend),
            "state": "advisory",
            "source": deepcopy(provenance.get("preferred_backend", {})),
        }
    return projection


def load_governance_layers(path: str = "") -> LayerMap:
    """Load governance layers from built-ins plus an optional JSON overlay."""
    merged = governance_layers()
    if not path.strip():
        return merged
    try:
        overlay = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"governance config not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid governance JSON: {path}") from exc
    overlay_dict = validate_governance_overlay(overlay)
    return merge_governance_layers(merged, overlay_dict)


def governance_order() -> List[str]:
    """Return the governance override order."""
    return list(_ORDER)


def merge_governance_layers(base: LayerMap, overlay: LayerMap) -> LayerMap:
    """Merge a governance layer overlay onto a base layer map."""
    merged = deepcopy(base)
    for layer, entries in overlay.items():
        if layer not in merged:
            merged[layer] = {}
        for name, values in entries.items():
            current = merged[layer].get(name, {})
            next_values = deepcopy(values)
            merged[layer][name] = {**current, **next_values}
    return merged


def validate_governance_overlay(payload: Any) -> LayerMap:
    if not isinstance(payload, dict):
        raise ValueError("governance overlay must be a JSON object")
    validated: LayerMap = {}
    for layer, entries in payload.items():
        if layer not in _ORDER:
            raise ValueError(f"unknown governance layer: {layer}")
        if not isinstance(entries, dict):
            raise ValueError(f"governance layer '{layer}' must map names to objects")
        next_entries: Dict[str, Dict[str, Any]] = {}
        for name, values in entries.items():
            if not isinstance(name, str) or not name.strip():
                raise ValueError(f"governance layer '{layer}' contains an invalid entry name")
            if not isinstance(values, dict):
                raise ValueError(f"governance entry '{layer}.{name}' must be an object")
            next_entries[name] = deepcopy(values)
        validated[layer] = next_entries
    return validated


def resolve_governance(
    *,
    model: str = "",
    environment: str = "",
    instruction_profile: str = "",
    config_path: str = "",
    layers: Optional[LayerMap] = None,
) -> Resolution:
    """Resolve layered governance config and provenance."""
    source = load_governance_layers(config_path) if layers is None else deepcopy(layers)
    effective: Dict[str, Any] = {}
    provenance: Dict[str, Dict[str, str]] = {}
    matched: List[Dict[str, str]] = []
    missing: List[Dict[str, str]] = []
    requested = {
        "model": str(model).strip(),
        "environment": str(environment).strip(),
        "instruction_profile": str(instruction_profile).strip(),
    }

    for layer in _ORDER:
        section = source.get(layer, {})
        name = "default" if layer == "base" else requested[layer]
        if not name:
            continue
        values = section.get(name)
        if values is None:
            if layer != "base":
                missing.append({"layer": layer, "name": name})
            continue
        matched.append({"layer": layer, "name": name})
        for key, value in values.items():
            effective[key] = value
            provenance[key] = {"layer": layer, "name": name}

    return {
        "config_path": str(config_path).strip(),
        "layer_order": governance_order(),
        "requested": requested,
        "matched_layers": matched,
        "missing_layers": missing,
        "authoritative_keys": governance_authoritative_keys(),
        "exception_keys": governance_exception_keys(),
        "key_classes": governance_key_classes(effective_config=effective),
        "effective_config": effective,
        "provenance": provenance,
        "runtime_projection": governance_runtime_projection(effective, provenance),
    }
