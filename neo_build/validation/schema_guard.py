from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Tuple


def _has_path(obj: Mapping[str, Any], path: List[str]) -> Tuple[bool, Optional[Any]]:
    cur: Any = obj
    for p in path:
        if not isinstance(cur, Mapping) or p not in cur:
            return False, None
        cur = cur[p]
    return True, cur


def _val_summary(val: Any) -> str:
    s = str(val)
    return s if len(s) <= 120 else s[:117] + "..."


def check_mutual_exclusion(v3_like_payload: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Return list of conflict objects when legacy and v3 fields coexist for the same concept.

    Concepts and their legacy/v3 indicators:
      - Context/Role: legacy.sector|role|regulators × role.*|context.*|sector_profile.regulatory
      - Persona: legacy.traits|attributes|voice × persona.*|brand.voice.*
      - Tooling: legacy.tools|capabilities|human_gate × capabilities_tools.*
      - Memory: legacy.memory.* × memory.*
      - Governance/KPI: legacy.kpi.* × governance_eval.gates.*
    """

    conflicts: List[Dict[str, Any]] = []
    legacy = v3_like_payload.get("legacy") if isinstance(v3_like_payload, Mapping) else None
    if not isinstance(legacy, Mapping):
        return conflicts

    # Context/Role
    leg_keys = [("legacy.sector", legacy.get("sector")),
                ("legacy.role", legacy.get("role")),
                ("legacy.regulators", legacy.get("regulators"))]
    v3_candidates = [
        ("role.function_code", _has_path(v3_like_payload, ["role", "function_code"])) ,
        ("role.role_code", _has_path(v3_like_payload, ["role", "role_code"])) ,
        ("context.naics", _has_path(v3_like_payload, ["context", "naics"])) ,
        ("sector_profile.regulatory", _has_path(v3_like_payload, ["sector_profile", "regulatory"]))
    ]
    if any(v is not None for _, v in leg_keys) and any(found for _, (found, _) in v3_candidates):
        legacy_path, legacy_val = next(((k, v) for k, v in leg_keys if v is not None), ("legacy", None))
        v3_path, (_, v3_val) = next(((k, t) for k, t in v3_candidates if t[0]), ("role", (True, None)))
        conflicts.append({
            "code": "DUPLICATE_LEGACY_V3_CONFLICT",
            "legacy_path": legacy_path,
            "v3_path": v3_path,
            "got_legacy": _val_summary(legacy_val),
            "got_v3": _val_summary(v3_val),
            "hint": "Remove legacy fields or provide legacy-only payload for auto-migration.",
        })

    # Persona
    leg_persona = [("legacy.traits", legacy.get("traits")), ("legacy.attributes", legacy.get("attributes")), ("legacy.voice", legacy.get("voice"))]
    v3_persona = [("persona", _has_path(v3_like_payload, ["persona"])) , ("brand.voice", _has_path(v3_like_payload, ["brand", "voice"]))]
    if any(v is not None for _, v in leg_persona) and any(found for _, (found, _) in v3_persona):
        legacy_path, legacy_val = next(((k, v) for k, v in leg_persona if v is not None), ("legacy", None))
        v3_path, (_, v3_val) = next(((k, t) for k, t in v3_persona if t[0]), ("persona", (True, None)))
        conflicts.append({
            "code": "DUPLICATE_LEGACY_V3_CONFLICT",
            "legacy_path": legacy_path,
            "v3_path": v3_path,
            "got_legacy": _val_summary(legacy_val),
            "got_v3": _val_summary(v3_val),
            "hint": "Remove legacy fields or provide legacy-only payload for auto-migration.",
        })

    # Tooling
    leg_tooling = [("legacy.tools", legacy.get("tools")), ("legacy.capabilities", legacy.get("capabilities")), ("legacy.human_gate", legacy.get("human_gate"))]
    v3_tooling = [("capabilities_tools", _has_path(v3_like_payload, ["capabilities_tools"]))]
    if any(v is not None for _, v in leg_tooling) and any(found for _, (found, _) in v3_tooling):
        legacy_path, legacy_val = next(((k, v) for k, v in leg_tooling if v is not None), ("legacy", None))
        v3_path, (_, v3_val) = next(((k, t) for k, t in v3_tooling if t[0]), ("capabilities_tools", (True, None)))
        conflicts.append({
            "code": "DUPLICATE_LEGACY_V3_CONFLICT",
            "legacy_path": legacy_path,
            "v3_path": v3_path,
            "got_legacy": _val_summary(legacy_val),
            "got_v3": _val_summary(v3_val),
            "hint": "Remove legacy fields or provide legacy-only payload for auto-migration.",
        })

    # Memory
    leg_memory = legacy.get("memory") if isinstance(legacy.get("memory"), Mapping) else None
    if isinstance(leg_memory, Mapping) and ("memory" in v3_like_payload):
        conflicts.append({
            "code": "DUPLICATE_LEGACY_V3_CONFLICT",
            "legacy_path": "legacy.memory",
            "v3_path": "memory",
            "got_legacy": _val_summary(leg_memory),
            "got_v3": _val_summary(v3_like_payload.get("memory")),
            "hint": "Remove legacy fields or provide legacy-only payload for auto-migration.",
        })

    # Governance/KPI
    leg_kpi = legacy.get("kpi") if isinstance(legacy.get("kpi"), Mapping) else None
    v3_gates = v3_like_payload.get("governance_eval") if isinstance(v3_like_payload.get("governance_eval"), Mapping) else None
    if isinstance(leg_kpi, Mapping) and isinstance(v3_gates, Mapping) and isinstance(v3_gates.get("gates"), Mapping):
        conflicts.append({
            "code": "DUPLICATE_LEGACY_V3_CONFLICT",
            "legacy_path": "legacy.kpi",
            "v3_path": "governance_eval.gates",
            "got_legacy": _val_summary(leg_kpi),
            "got_v3": _val_summary(v3_gates.get("gates")),
            "hint": "Remove legacy fields or provide legacy-only payload for auto-migration.",
        })

    return conflicts

