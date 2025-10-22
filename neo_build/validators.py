"""Validation and gate evaluation helpers for built repos."""

from __future__ import annotations

from typing import Any, Dict, Mapping

from .contracts import KPI_TARGETS, REQUIRED_ALERTS, REQUIRED_EVENTS, REQUIRED_HUMAN_GATE_ACTIONS


def compute_effective_autonomy(preferences: Mapping[str, Any] | None, routing_defaults: Mapping[str, Any] | None) -> float:
    sliders = (preferences or {}).get("sliders", {}) if isinstance(preferences, Mapping) else {}
    autonomy = float(sliders.get("autonomy", 0)) / 100.0
    rd_default = 0.28
    if routing_defaults and isinstance(routing_defaults, Mapping):
        try:
            rd_default = float(routing_defaults.get("autonomy_default", rd_default))
        except Exception:
            pass
    return min(autonomy, rd_default)


def human_gate_actions(actions: list[str] | None) -> list[str]:
    actions = list(actions or [])
    for req in REQUIRED_HUMAN_GATE_ACTIONS:
        if req not in actions:
            actions.append(req)
    return actions


def observability_spec(existing: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    spec = {"events": list(REQUIRED_EVENTS), "alerts": list(REQUIRED_ALERTS)}
    if isinstance(existing, Mapping):
        # Coerce legacy dict/list formats
        ev = existing.get("events")
        if isinstance(ev, list):
            merged = list(dict.fromkeys(list(ev) + REQUIRED_EVENTS))
            spec["events"] = merged
        al = existing.get("alerts")
        if isinstance(al, list):
            merged = list(dict.fromkeys(list(al) + REQUIRED_ALERTS))
            spec["alerts"] = merged
    return spec


def kpi_targets_sync() -> Dict[str, float]:
    return dict(KPI_TARGETS)


def preferences_flow_flags(collaboration_mode: str | None) -> Dict[str, bool]:
    mode = (collaboration_mode or "").strip()
    flags = {
        "planner_builder_evaluator": False,
        "auto_plan_step": True,
    }
    if mode == "Planner-Builder-Evaluator":
        flags["planner_builder_evaluator"] = True
    if mode in ("Solo", "Advisory"):
        flags["auto_plan_step"] = False
    return flags


def integrity_report(profile: Mapping[str, Any], packs: Mapping[str, Any]) -> Dict[str, Any]:
    """Build a light integrity summary across packs for optional emission."""

    out: Dict[str, Any] = {"status": "ok", "checks": {}}
    # Check KPI sync
    desired = kpi_targets_sync()
    k11 = ((packs.get("11_Workflow-Pack_v2.json") or {}).get("gates") or {}).get("kpi_targets")
    k14 = (packs.get("14_KPI+Evaluation-Framework_v2.json") or {}).get("targets")
    k17 = ((packs.get("17_Lifecycle-Pack_v2.json") or {}).get("gates") or {}).get("kpi_targets")
    out["checks"]["kpi_sync"] = (k11 == desired) and (k14 == desired) and (k17 == desired)
    # Observability
    obs = packs.get("15_Observability+Telemetry_Spec_v2.json") or {}
    ev = set(obs.get("events", []))
    al = set(obs.get("alerts", []))
    out["checks"]["observability"] = set(REQUIRED_EVENTS).issubset(ev) and set(REQUIRED_ALERTS).issubset(al)
    # Owners present
    owners = ((packs.get("09_Agent-Manifests_Catalog_v2.json") or {}).get("owners") or [])
    out["checks"]["owners_present"] = isinstance(owners, list) and len(owners) > 0
    # Identity cross-ref: agent_id present and consistent
    mapping = ((packs.get("06_Role-Recipes_Index_v2.json") or {}).get("mapping") or {})
    agent_id_06 = mapping.get("agent_id")
    agents = ((packs.get("09_Agent-Manifests_Catalog_v2.json") or {}).get("agents") or [])
    agent_id_09 = agents[0].get("agent_id") if isinstance(agents, list) and agents else None
    out["checks"]["agent_id_consistent"] = bool(agent_id_06) and agent_id_06 == agent_id_09
    return out
