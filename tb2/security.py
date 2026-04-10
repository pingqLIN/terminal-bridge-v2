"""Security posture helpers for tb2 control surfaces."""

from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass
from typing import Any, Dict, List

_LOCAL_BIND_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
_WILDCARD_BIND_HOSTS = frozenset({"0.0.0.0", "::"})
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


def _normalize_host(raw: str) -> str:
    text = raw.strip().lower()
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
    return text or "127.0.0.1"


def allow_remote_from_env() -> bool:
    return _normalize_host(os.environ.get("TB2_ALLOW_REMOTE", "")) in _TRUE_VALUES


def bind_scope(host: str) -> str:
    text = _normalize_host(host)
    if text in _LOCAL_BIND_HOSTS:
        return "loopback"
    if text in _WILDCARD_BIND_HOSTS:
        return "wildcard"
    try:
        addr = ipaddress.ip_address(text)
    except ValueError:
        return "named-network-host"
    if addr.is_loopback:
        return "loopback"
    if addr.is_private or addr.is_link_local:
        return "private-network"
    return "public-network"


def remote_bind_ack_required(host: str) -> bool:
    return bind_scope(host) != "loopback"


@dataclass(frozen=True)
class SecurityPosture:
    host: str
    bind_scope: str
    exposure: str
    support_tier: str
    remote_requires_explicit_ack: bool
    remote_access_acknowledged: bool
    authn_mode: str
    approval_boundary: str
    origin_policy: str
    warnings: List[str]
    recommended_controls: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "host": self.host,
            "bind_scope": self.bind_scope,
            "exposure": self.exposure,
            "support_tier": self.support_tier,
            "remote_requires_explicit_ack": self.remote_requires_explicit_ack,
            "remote_access_acknowledged": self.remote_access_acknowledged,
            "authn": {
                "mode": self.authn_mode,
                "enforced": self.authn_mode != "none",
            },
            "approval_boundary": self.approval_boundary,
            "origin_policy": self.origin_policy,
            "warnings": list(self.warnings),
            "recommended_controls": list(self.recommended_controls),
        }


def build_security_posture(
    host: str,
    *,
    allow_remote: bool = False,
    authn_mode: str = "none",
) -> SecurityPosture:
    text = _normalize_host(host)
    scope = bind_scope(text)
    requires_ack = remote_bind_ack_required(text)
    acknowledged = allow_remote or allow_remote_from_env() or not requires_ack

    exposure = "loopback-only"
    support_tier = "local-first-supported"
    warnings: List[str] = []
    controls = [
        "Treat approval and intervention as workflow controls, not authorization boundaries.",
        "Keep the GUI and MCP surfaces on trusted operator paths.",
    ]

    if scope == "private-network":
        exposure = "private-network"
        support_tier = "private-network-experimental"
        warnings.append("Non-loopback bind is experimental and assumes a trusted private network.")
        controls.extend(
            [
                "Use explicit network controls such as VPN, SSH tunnel, or firewall ACLs.",
                "Avoid routing TB2 directly onto shared or unmanaged networks.",
            ]
        )
    elif scope == "wildcard":
        exposure = "wildcard-network"
        support_tier = "private-network-experimental"
        warnings.append("Wildcard bind can expose TB2 beyond the intended private-network boundary.")
        controls.extend(
            [
                "Prefer a specific private address over 0.0.0.0 or :: when possible.",
                "Confirm upstream firewall policy before allowing remote access.",
            ]
        )
    elif scope == "named-network-host":
        exposure = "named-network-host"
        support_tier = "private-network-experimental"
        warnings.append("Named non-loopback host requires operator-managed network trust verification.")
        controls.extend(
            [
                "Verify the host resolves only inside a trusted private network.",
                "Do not treat DNS naming as a security control by itself.",
            ]
        )
    elif scope == "public-network":
        exposure = "public-network"
        support_tier = "public-edge-unsupported"
        warnings.append("Public-network exposure is not a supported TB2 deployment model.")
        controls.extend(
            [
                "Do not place TB2 directly on a public internet edge.",
                "Put an authenticated remote-control layer in front if remote access is unavoidable.",
            ]
        )

    if not acknowledged and requires_ack:
        warnings.append("Remote access has not been explicitly acknowledged.")

    return SecurityPosture(
        host=text,
        bind_scope=scope,
        exposure=exposure,
        support_tier=support_tier,
        remote_requires_explicit_ack=requires_ack,
        remote_access_acknowledged=acknowledged,
        authn_mode=authn_mode,
        approval_boundary="workflow_only",
        origin_policy="localhost_only",
        warnings=warnings,
        recommended_controls=controls,
    )


def validate_server_binding(host: str, *, allow_remote: bool = False) -> None:
    posture = build_security_posture(host, allow_remote=allow_remote)
    if posture.remote_access_acknowledged:
        return
    raise RuntimeError(
        "non-loopback bind requires explicit acknowledgment via --allow-remote "
        "or TB2_ALLOW_REMOTE=1; TB2 is not a public remote control plane"
    )
