from __future__ import annotations

from typing import Any, Dict, Mapping, Tuple, List


def _as_list(val: Any) -> List[Any]:
    if val is None:
        return []
    if isinstance(val, list):
        return val
    return [val]


def transform(payload: Mapping[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Transform a legacy-style payload into a v3 intake payload.

    Returns (v3_payload, diagnostics) where diagnostics contains a "dropped" list
    for unknown legacy keys and a "mappings_applied" list for traceability.

    Only allow-listed legacy fields are migrated. Unknowns are dropped into diagnostics.
    The function does not mutate the input object and keeps deterministic key ordering.
    """

    legacy = payload.get("legacy") if isinstance(payload, Mapping) else None
    if not isinstance(legacy, Mapping):
        legacy = {}

    diagnostics: Dict[str, Any] = {"dropped": [], "mappings_applied": []}

    # Seed output in deterministic top-level key order
    v3: Dict[str, Any] = {}
    v3["intake_version"] = "v3.0"

    # Identity: copy through if present outside legacy (not part of legacy migration scope)
    identity = payload.get("identity") if isinstance(payload, Mapping) else None
    if isinstance(identity, Mapping):
        v3["identity"] = {
            k: identity[k]
            for k in ("agent_id", "display_name", "owners", "no_impersonation", "attribution_policy")
            if k in identity
        }

    # A) Business Context & Role
    # legacy.sector -> sector_profile.sector
    sector = legacy.get("sector")
    if sector is not None:
        v3["sector_profile"] = {"sector": sector}
        diagnostics["mappings_applied"].append("legacy.sector→sector_profile.sector")

    # legacy.role -> role.role_code
    role_code = legacy.get("role")
    # Build role object deterministically
    role_obj: Dict[str, Any] = {}
    if role_code:
        role_obj["role_code"] = role_code
        diagnostics["mappings_applied"].append("legacy.role→role.role_code")
    if role_obj:
        # we keep place for function_code/title/objectives to be augmented upstream
        v3["role"] = role_obj

    # legacy.regulators[] -> sector_profile.regulatory[] (merge)
    regs = legacy.get("regulators")
    if regs is not None:
        sp = v3.get("sector_profile") or {}
        sp = dict(sp)
        sp["regulatory"] = list(_as_list(regs))
        v3["sector_profile"] = sp
        diagnostics["mappings_applied"].append("legacy.regulators→sector_profile.regulatory[]")

    # B) Persona
    traits = legacy.get("traits")
    attributes = legacy.get("attributes")
    voice = legacy.get("voice")
    if traits is not None or attributes is not None:
        persona: Dict[str, Any] = {"traits": list({*map(str, _as_list(traits)), *map(str, _as_list(attributes))})}
        v3["persona"] = persona
        diagnostics["mappings_applied"].append("legacy.traits|attributes→persona.traits[]")
    if voice is not None:
        # Preserve shape as brand.voice.voice_traits for downstream pack 20 mapping
        brand = {"voice": {"voice_traits": list(_as_list(voice))}}
        v3["brand"] = brand
        diagnostics["mappings_applied"].append("legacy.voice→brand.voice.voice_traits[]")

    # C) Tooling
    tools = legacy.get("tools")
    caps = legacy.get("capabilities")
    human_gate = legacy.get("human_gate") if isinstance(legacy.get("human_gate"), Mapping) else {}
    if tools is not None or caps is not None or human_gate:
        ct: Dict[str, Any] = {}
        suggestions = list({*map(str, _as_list(tools)), *map(str, _as_list(caps))})
        if suggestions:
            ct["tool_suggestions"] = suggestions
            diagnostics["mappings_applied"].append("legacy.tools|capabilities→capabilities_tools.tool_suggestions[]")
        actions = human_gate.get("actions") if isinstance(human_gate, Mapping) else None
        if actions is not None:
            ct["human_gate"] = {"actions": list(_as_list(actions))}
            diagnostics["mappings_applied"].append("legacy.human_gate.actions→capabilities_tools.human_gate.actions[]")
        if ct:
            v3["capabilities_tools"] = ct

    # D) Memory
    mem = legacy.get("memory") if isinstance(legacy.get("memory"), Mapping) else {}
    mem_out: Dict[str, Any] = {}
    if isinstance(mem, Mapping):
        scopes = mem.get("scopes")
        packs = mem.get("packs")
        sources = mem.get("sources")
        if scopes is not None:
            mem_out["memory_scopes"] = list(_as_list(scopes))
            diagnostics["mappings_applied"].append("legacy.memory.scopes→memory.memory_scopes[]")
        if packs is not None:
            mem_out["initial_memory_packs"] = list(_as_list(packs))
            diagnostics["mappings_applied"].append("legacy.memory.packs→memory.initial_memory_packs[]")
        if sources is not None:
            mem_out["data_sources"] = list(_as_list(sources))
            diagnostics["mappings_applied"].append("legacy.memory.sources→memory.data_sources[]")
        if mem_out:
            v3["memory"] = mem_out

    # E) Governance & KPI targets
    kpi = legacy.get("kpi") if isinstance(legacy.get("kpi"), Mapping) else {}
    if isinstance(kpi, Mapping):
        gates = {}
        if "PRI_min" in kpi:
            gates["PRI_min"] = kpi["PRI_min"]
            diagnostics["mappings_applied"].append("legacy.kpi.PRI_min→governance_eval.gates.PRI_min")
        if "HAL_max" in kpi:
            gates["hallucination_max"] = kpi["HAL_max"]
            diagnostics["mappings_applied"].append("legacy.kpi.HAL_max→governance_eval.gates.hallucination_max")
        if "AUD_min" in kpi:
            gates["audit_min"] = kpi["AUD_min"]
            diagnostics["mappings_applied"].append("legacy.kpi.AUD_min→governance_eval.gates.audit_min")
        if gates:
            v3["governance_eval"] = {"gates": gates}

    # Context: ensure present if NAICS exists on original payload
    # (allow upstream to set context.naics; adapter does not infer it)
    if isinstance(payload.get("context"), Mapping) and "naics" in payload["context"]:
        v3["context"] = {"naics": payload["context"]["naics"]}

    # Compute dropped legacy keys (top-level under legacy)
    allowed_legacy_top = {
        "sector",
        "role",
        "regulators",
        "traits",
        "attributes",
        "voice",
        "tools",
        "capabilities",
        "human_gate",
        "memory",
        "kpi",
    }
    for k in legacy.keys():
        if k not in allowed_legacy_top:
            diagnostics["dropped"].append(f"legacy.{k}")

    return v3, diagnostics

