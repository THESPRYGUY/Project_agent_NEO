"""Adapter: upgrade a legacy intake payload to v3 schema.

Converts existing Project NEO intake payloads into the consolidated v3 shape
used to populate the GEN2/GEN3 20-pack repository deterministically.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping


def _get(obj: Mapping[str, Any] | None, key: str, default: Any = None) -> Any:
    if not isinstance(obj, Mapping):
        return default
    return obj.get(key, default)


def upgrade(legacy: Mapping[str, Any]) -> Dict[str, Any]:
    """Return a v3-shaped payload derived from ``legacy``.

    - Pulls from legacy blocks (identity, role_profile, sector_profile, etc.)
    - Provides sensible defaults where fields are missing
    - Does not mutate the input mapping
    """

    out: Dict[str, Any] = {"meta": {"version": "v3-intake", "purpose": "adapter"}}

    agent = _get(legacy, "agent", {}) or {}
    identity = _get(legacy, "identity", {}) or {}
    role_profile = _get(legacy, "role_profile", {}) or {}
    sector_profile = _get(legacy, "sector_profile", {}) or {}
    capabilities = _get(legacy, "capabilities_tools", {}) or {}
    memory = _get(legacy, "memory", {}) or {}
    governance_eval = _get(legacy, "governance_eval", {}) or {}

    # Agent profile
    out["agent_profile"] = {"name": _get(agent, "name", "Custom Project NEO Agent"), "version": _get(agent, "version", "1.0.0")}

    # Identity
    out["identity"] = {
        "agent_id": _get(identity, "agent_id", ""),
        "display_name": _get(identity, "display_name", _get(agent, "name", "")),
        "owners": list(_get(identity, "owners", []) or []),
        "no_impersonation": bool(_get(identity, "no_impersonation", True)),
    }

    # Governance policy + RBAC
    out["governance"] = {
        "rbac": {"roles": list(_get(_get(legacy, "governance", {}), "rbac", {}).get("roles", []) or [])},
        "policy": {
            "no_impersonation": bool(_get(identity, "no_impersonation", True)),
            "classification_default": _get(governance_eval, "classification_default", "confidential"),
        },
    }

    # Role mapping
    role_code = _get(_get(legacy, "role", {}), "code", "")
    out["role"] = {
        "primary": {"code": role_code},
        "title": _get(role_profile, "role_title", _get(_get(legacy, "role", {}), "title", "")),
        "recipe_ref": _get(role_profile, "role_recipe_ref", ""),
        "objectives": list(_get(role_profile, "objectives", []) or []),
    }

    # Domain & NAICS
    naics = _get(_get(legacy, "classification", {}), "naics", _get(legacy, "naics", {})) or {}
    out["domain"] = {"naics": {"code": _get(naics, "code", "")}, "region": list(_get(sector_profile, "region", []) or [])}

    # Persona profile
    mbti = _get(_get(legacy, "agent", {}), "persona", "") or _get(_get(legacy, "persona", {}), "mbti", "") or "ENTJ"
    out["persona"] = {
        "mbti": mbti,
        "tone": _get(_get(legacy, "persona", {}), "tone", "crisp, analytical, executive"),
        "collaboration_mode": _get(_get(legacy, "persona", {}), "collaboration_mode", "Solo"),
    }

    # Toolset selector
    connectors = list(_get(capabilities, "tool_connectors", []) or [])
    out["tools"] = {
        "connectors": connectors,
        "human_gate_actions": list(_get(_get(capabilities, "human_gate", {}), "actions", []) or []),
    }

    # Memory schema selector
    out["memory"] = {
        "scopes": list(_get(memory, "memory_scopes", []) or []),
        "packs": {
            "initial": list(_get(memory, "initial_memory_packs", []) or []),
            "optional": list(_get(memory, "optional_packs", []) or []),
        },
        "sync": {"allowed_sources": list(_get(memory, "data_sources", []) or [])},
    }

    # Compliance & safety profile
    out["compliance"] = {
        "risk_tier": _get(sector_profile, "risk_tier", ""),
        "regulators": list(_get(sector_profile, "regulatory", []) or []),
    }
    out["privacy"] = {
        "pii_flags": list(_get(governance_eval, "pii_flags", []) or []),
        "classification_default": _get(governance_eval, "classification_default", "confidential"),
    }

    # Lifecycle & KPI gates (defaults; actual targets remain system constants)
    out["lifecycle"] = {"stage": _get(_get(legacy, "lifecycle", {}), "stage", "dev")}
    out["kpi"] = {"targets": _get(_get(legacy, "kpi", {}), "targets", {})}

    # Observability & telemetry
    telemetry = _get(_get(legacy, "telemetry", {}), "sampling", {})
    out["telemetry"] = {
        "sampling": {"rate": float(_get(telemetry, "rate", 1.0) or 1.0)},
        "sinks": list(_get(_get(legacy, "telemetry", {}), "sinks", []) or []),
        "pii_redaction": {"strategy": _get(_get(legacy, "telemetry", {}), "pii_redaction", {}).get("strategy", "mask")},
    }

    return out

