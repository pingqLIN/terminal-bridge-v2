"""Governance layering resolver for TB2.

Provides a simulation-first resolver that merges layered governance inputs and
reports the effective configuration plus provenance. It does not mutate runtime
state.
"""

from __future__ import annotations

from copy import deepcopy
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


def governance_layers() -> LayerMap:
    """Return a copy of the built-in governance layer config."""
    return deepcopy(_DEFAULTS)


def governance_order() -> List[str]:
    """Return the governance override order."""
    return list(_ORDER)


def resolve_governance(
    *,
    model: str = "",
    environment: str = "",
    instruction_profile: str = "",
    layers: Optional[LayerMap] = None,
) -> Resolution:
    """Resolve layered governance config and provenance."""
    source = governance_layers() if layers is None else deepcopy(layers)
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
        "layer_order": governance_order(),
        "requested": requested,
        "matched_layers": matched,
        "missing_layers": missing,
        "effective_config": effective,
        "provenance": provenance,
    }
