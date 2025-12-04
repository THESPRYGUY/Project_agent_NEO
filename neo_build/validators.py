"""Validation and gate evaluation helpers for built repos."""

from __future__ import annotations

from typing import Any, Dict, Mapping, List, Set, Tuple
import os

from .gates import parse_activation_strings
from .schemas import required_keys_map

from .contracts import KPI_TARGETS, REQUIRED_ALERTS, REQUIRED_EVENTS, REQUIRED_HUMAN_GATE_ACTIONS, PACK_ID_TO_FILENAME
from .schemas import required_keys_map


_GENERIC_OBJECTIVES: Set[str] = {
    "help user",
    "help users",
    "answer questions",
    "assist with tasks",
    "assist users",
    "provide information",
    "provide info",
}


def _clean_objective_text(value: Any) -> str:
    try:
        text = " ".join(str(value).replace("\r", " ").split()).strip(" -\t")
    except Exception:
        text = ""
    return text


def objectives_from_profile(profile: Mapping[str, Any] | None) -> Tuple[list[str], str]:
    """Return (objectives, status) from a profile without leaking text elsewhere."""

    objectives: list[str] = []
    status = "missing"
    if isinstance(profile, Mapping):
        role_profile = profile.get("role_profile") if isinstance(profile.get("role_profile"), Mapping) else {}
        raw_objectives = role_profile.get("objectives") if isinstance(role_profile, Mapping) else None
        if raw_objectives is None and isinstance(profile.get("role"), Mapping):
            raw_objectives = profile.get("role", {}).get("objectives")
        if raw_objectives is None:
            raw_objectives = profile.get("objectives")
        if isinstance(raw_objectives, list):
            for entry in raw_objectives:
                cleaned = _clean_objective_text(entry)
                if cleaned:
                    objectives.append(cleaned)
        if isinstance(role_profile, Mapping):
            status = str(role_profile.get("objectives_status") or "").strip() or status
        status = str(profile.get("objectives_status") or status or "").strip() or status
    if not status:
        status = "explicit" if objectives else "missing"
    if status == "missing" and objectives:
        status = "explicit"
    return objectives, status


def is_generic_objectives(objectives: List[str]) -> bool:
    """Return True if all objectives look generic/helpdesk-like (case-insensitive)."""

    if not objectives:
        return False
    normalized: list[str] = []
    for obj in objectives:
        cleaned = _clean_objective_text(obj).lower().strip(".;")
        if not cleaned:
            continue
        normalized.append(cleaned)
    if not normalized:
        return False
    for entry in normalized:
        simple = entry.rstrip(".;")
        singular = simple[:-1] if simple.endswith("s") else simple
        if simple in _GENERIC_OBJECTIVES or singular in _GENERIC_OBJECTIVES:
            continue
        if len(simple.split()) <= 4 and any(simple.startswith(gen) or simple.endswith(gen) for gen in _GENERIC_OBJECTIVES):
            continue
        return False
    return True


def compute_effective_autonomy(preferences: Mapping[str, Any] | None, routing_defaults: Mapping[str, Any] | None) -> float:
    """Derive effective_autonomy from intake sliders with a small safety fallback."""

    sliders = (preferences or {}).get("sliders", {}) if isinstance(preferences, Mapping) else {}
    slider_val = sliders.get("autonomy")
    autonomy = None
    try:
        autonomy = float(slider_val) / 100.0
    except Exception:
        autonomy = None

    rd_default = 0.28
    if routing_defaults and isinstance(routing_defaults, Mapping):
        try:
            rd_default = float(routing_defaults.get("autonomy_default", rd_default))
        except Exception:
            pass

    if autonomy is None:
        autonomy = rd_default

    # Keep within [0,1] and prefer the explicit slider value when present
    try:
        autonomy = max(0.0, min(1.0, float(autonomy)))
    except Exception:
        autonomy = rd_default
    return autonomy


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


def _normalize_kpi_overrides(overrides: Mapping[str, Any] | None) -> Dict[str, float]:
    """Normalize user-provided KPI overrides to PRI_min/HAL_max/AUD_min keys."""

    if not isinstance(overrides, Mapping):
        return {}
    mapped = {}
    for src, dst in (
        ("PRI_min", "PRI_min"),
        ("pri_min", "PRI_min"),
        ("HAL_max", "HAL_max"),
        ("hal_max", "HAL_max"),
        ("AUD_min", "AUD_min"),
        ("aud_min", "AUD_min"),
    ):
        val = overrides.get(src)
        if val is None:
            continue
        try:
            mapped[dst] = float(val)
        except Exception:
            continue
    return mapped


def kpi_targets_sync(*, overrides: Mapping[str, Any] | None = None, profile: Mapping[str, Any] | None = None) -> Dict[str, float]:
    """Return KPI targets, allowing optional overrides from intake profile."""

    effective_overrides = overrides
    if effective_overrides is None and isinstance(profile, Mapping):
        adv = profile.get("advanced_overrides") or {}
        if isinstance(adv, Mapping):
            effective_overrides = (adv.get("overrides") or {}).get("kpi")

    targets = dict(KPI_TARGETS)
    normalized = _normalize_kpi_overrides(effective_overrides)
    targets.update(normalized)
    return targets


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
    errors = out.setdefault("errors", [])
    warnings: list[str] = out.setdefault("warnings", [])
    adv_overrides = {}
    if isinstance(profile, Mapping):
        adv_raw = profile.get("advanced_overrides") or {}
        if isinstance(adv_raw, Mapping):
            adv_overrides = adv_raw.get("overrides") or adv_raw
    adv_kpi = adv_overrides.get("kpi") if isinstance(adv_overrides, Mapping) else None

    # Objectives integrity (non-PII)
    objectives, raw_status = objectives_from_profile(profile)
    obj_status = raw_status or ("explicit" if objectives else "missing")
    has_objectives = len(objectives) > 0
    has_generic = is_generic_objectives(objectives) if has_objectives else False
    obj_warnings: list[str] = []
    if not has_objectives:
        obj_status = "missing"
        obj_warnings.append("No objectives set; agent may be underspecified.")
    if has_objectives and has_generic:
        obj_warnings.append("Objectives are generic; consider editing for more specificity.")
    out["objectives"] = {
        "status": obj_status,
        "count": len(objectives),
        "has_generic": has_generic,
        "warnings": obj_warnings,
    }
    if obj_warnings:
        warnings.extend(obj_warnings)

    # Check KPI sync
    desired = kpi_targets_sync(overrides=adv_kpi, profile=profile)
    k11 = ((packs.get("11_Workflow-Pack_v2.json") or {}).get("gates") or {}).get("kpi_targets")
    k14 = (packs.get("14_KPI+Evaluation-Framework_v2.json") or {}).get("targets")
    k17 = ((packs.get("17_Lifecycle-Pack_v2.json") or {}).get("gates") or {}).get("kpi_targets")
    out["checks"]["kpi_sync"] = (k11 == desired) and (k14 == desired) and (k17 == desired)
    # Observability
    obs = packs.get("15_Observability+Telemetry_Spec_v2.json") or {}
    raw_events = obs.get("events", [])
    ev: Set[str] = set()
    if isinstance(raw_events, list):
        for item in raw_events:
            if isinstance(item, dict):
                name = str(item.get("name") or "").strip()
                if name:
                    ev.add(name)
            elif isinstance(item, str):
                ev.add(item)
    elif isinstance(raw_events, str):
        ev.add(raw_events)
    else:
        try:
            ev.update(set(raw_events))
        except Exception:
            pass
    raw_alerts = obs.get("alerts", [])
    alerts: Set[str] = set()
    if isinstance(raw_alerts, Mapping):
        for value in raw_alerts.values():
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        alerts.add(item)
    elif isinstance(raw_alerts, list):
        for item in raw_alerts:
            if isinstance(item, str):
                alerts.add(item)
    elif isinstance(raw_alerts, str):
        alerts.add(raw_alerts)
    out["checks"]["observability"] = set(REQUIRED_EVENTS).issubset(ev) and set(REQUIRED_ALERTS).issubset(alerts)
    # Owners present
    owners = ((packs.get("09_Agent-Manifests_Catalog_v2.json") or {}).get("owners") or [])
    out["checks"]["owners_present"] = isinstance(owners, list) and len(owners) > 0
    # Identity cross-ref: agent_id present and consistent
    mapping = ((packs.get("06_Role-Recipes_Index_v2.json") or {}).get("mapping") or {})
    agent_id_06 = mapping.get("agent_id")
    agents = ((packs.get("09_Agent-Manifests_Catalog_v2.json") or {}).get("agents") or [])
    agent_id_09 = agents[0].get("agent_id") if isinstance(agents, list) and agents else None
    out["checks"]["agent_id_consistent"] = bool(agent_id_06) and agent_id_06 == agent_id_09
    # KPI Parity hardening (Sprint-4): 02/14/11 plus 03/17 activation strings
    p02 = ((packs.get("02_Global-Instructions_v2.json") or {}).get("observability") or {}).get("kpi_targets", {})
    p14 = (packs.get("14_KPI+Evaluation-Framework_v2.json") or {}).get("targets", {})
    g11 = (packs.get("11_Workflow-Pack_v2.json") or {}).get("gates", {})
    if not isinstance(g11, dict):
        g11 = {}
    p11 = dict(g11.get("kpi_targets", {}) or {})
    # p11 synonyms to compare with p02
    if "HAL_max" not in p11 and "hallucination_max" in p11:
        p11["HAL_max"] = p11.get("hallucination_max")
    if "AUD_min" not in p11 and "audit_min" in p11:
        p11["AUD_min"] = p11.get("audit_min")
    if "PRI_min" not in p11 and "PRI_min" in p14:
        p11["PRI_min"] = p11.get("PRI_min")

    act03 = (((packs.get("03_Operating-Rules_v2.json") or {}).get("gates") or {}).get("activation") or [])
    act17 = (((packs.get("17_Lifecycle-Pack_v2.json") or {}).get("gates") or {}).get("activation") or [])
    p03 = parse_activation_strings(act03)
    p17 = parse_activation_strings(act17)

    def _eq(a: Mapping[str, Any] | None, b: Mapping[str, Any] | None) -> bool:
        a = dict(a or {})
        b = dict(b or {})
        keys = ("PRI_min", "HAL_max", "AUD_min")
        # Null-safe: all keys must exist in both
        if not all(k in a for k in keys):
            return False
        if not all(k in b for k in keys):
            return False
        return a.get("PRI_min") == b.get("PRI_min") and a.get("HAL_max") == b.get("HAL_max") and a.get("AUD_min") == b.get("AUD_min")

    parity = {
        "02_vs_14": _eq(p02, p14),
        "11_vs_02": (p11.get("PRI_min") == p02.get("PRI_min") and p11.get("HAL_max") == p02.get("HAL_max") and p11.get("AUD_min") == p02.get("AUD_min")),
        "03_vs_02": (p03.get("PRI_min") == p02.get("PRI_min") and p03.get("HAL_max") == p02.get("HAL_max") and p03.get("AUD_min") == p02.get("AUD_min")),
        "17_vs_02": (p17.get("PRI_min") == p02.get("PRI_min") and p17.get("HAL_max") == p02.get("HAL_max") and p17.get("AUD_min") == p02.get("AUD_min")),
    }

    def _r(v: Any) -> Any:
        try:
            if isinstance(v, (int, float)):
                return round(float(v), 4)
        except Exception:
            return v
        return v

    def _deltas(p: Mapping[str, Any], src: Mapping[str, Any]):
        out: Dict[str, Any] = {}
        for k in ("PRI_min", "HAL_max", "AUD_min"):
            pv = p.get(k)
            sv = src.get(k)
            if pv != sv:
                out[k] = (_r(pv), _r(sv))
        return out

    parity_deltas = {
        "03": _deltas(p03, p02),
        "17": _deltas(p17, p02),
        "11": _deltas(p11, p02),
        "14": _deltas(p14, p02),
    }

    out["parity"] = parity
    out["parity_deltas"] = parity_deltas
    out["parity_ok"] = bool(all(parity.values()))

    def _dget_local(mapping: Mapping[str, Any] | None, path: str, default: Any = None) -> Any:
        cur: Any = mapping
        for part in path.split("."):
            if not isinstance(cur, Mapping):
                return default
            cur = cur.get(part)
        return cur if cur is not None else default

    # Advanced overrides wiring checks
    adv_checks: list[bool] = []
    if isinstance(adv_overrides, Mapping) and adv_overrides:
        # KPI overrides must appear in packs
        if isinstance(adv_kpi, Mapping) and adv_kpi:
            kpi_applied = _eq(p02, desired)
            adv_checks.append(kpi_applied)
            if not kpi_applied:
                errors.append("advanced_overrides.kpi_not_applied")
        bias = adv_overrides.get("behavior", {}).get("bias") if isinstance(adv_overrides.get("behavior"), Mapping) else None
        focus_domains = adv_overrides.get("behavior", {}).get("focus_domains") if isinstance(adv_overrides.get("behavior"), Mapping) else None
        if bias or focus_domains:
            bias_applied = False
            strat_defaults = _dget_local(packs.get("10_Prompt-Pack_v2.json"), "strategy_defaults", {})
            if isinstance(strat_defaults, Mapping) and bias and strat_defaults.get("bias") == bias:
                bias_applied = True
            if isinstance(strat_defaults, Mapping) and focus_domains:
                fd = strat_defaults.get("focus_domains") if isinstance(strat_defaults.get("focus_domains"), list) else []
                if set(fd) >= set(focus_domains):
                    bias_applied = True
            manifest_tags = _dget_local(packs.get("09_Agent-Manifests_Catalog_v2.json"), "agents.0.tags", [])
            if isinstance(manifest_tags, list):
                if (bias and bias in manifest_tags) or (focus_domains and set(focus_domains).issubset(set(manifest_tags))):
                    bias_applied = True
            adv_checks.append(bool(bias_applied))
            if not bias_applied:
                errors.append("advanced_overrides.behavior_not_applied")
        output_defaults = adv_overrides.get("output_defaults") if isinstance(adv_overrides, Mapping) else {}
        if isinstance(output_defaults, Mapping) and output_defaults:
            contracts = _dget_local(packs.get("10_Prompt-Pack_v2.json"), "output_contracts", [])
            names = {c.get("name") for c in contracts} if isinstance(contracts, list) else set()
            needed = {"Large_Response_Template_v1", "Daily_Checklist_v1", "Weekly_Outreach_Plan_v1", "Site_Summary_v1"}
            applied = needed.issubset(names) if names else False
            adv_checks.append(applied)
            if not applied:
                errors.append("advanced_overrides.output_defaults_missing")
        style_overrides = adv_overrides.get("style") if isinstance(adv_overrides, Mapping) else {}
        if isinstance(style_overrides, Mapping) and style_overrides:
            style_defaults = _dget_local(packs.get("10_Prompt-Pack_v2.json"), "style_defaults", {})
            style_applied = isinstance(style_defaults, Mapping) and bool(style_defaults)
            adv_checks.append(style_applied)
            if not style_applied:
                errors.append("advanced_overrides.style_not_applied")
        guardrails = adv_overrides.get("guardrails") if isinstance(adv_overrides, Mapping) else {}
        if isinstance(guardrails, Mapping) and guardrails:
            guard_applied = bool(_dget_local(packs.get("05_Safety+Privacy_Guardrails_v2.json"), "guardrail_overrides", {}))
            adv_checks.append(guard_applied)
            if not guard_applied:
                errors.append("advanced_overrides.guardrails_not_applied")
    out["checks"]["advanced_overrides_applied"] = bool(all(adv_checks)) if adv_checks else True

    # effective_autonomy alignment with intake slider (±0.05 tolerance)
    slider_autonomy = None
    try:
        slider_autonomy = float(
            _dget_local(profile, "preferences.sliders.autonomy", None)  # type: ignore[arg-type]
        ) / 100.0
    except Exception:
        slider_autonomy = None
    eff_values = []
    for fname, path in (
        ("02_Global-Instructions_v2.json", "effective_autonomy"),
        ("03_Operating-Rules_v2.json", "gates.effective_autonomy"),
        ("11_Workflow-Pack_v2.json", "gates.effective_autonomy"),
        ("17_Lifecycle-Pack_v2.json", "gates.effective_autonomy"),
    ):
        eff_values.append(_dget_local(packs.get(fname), path))
    eff_values = [v for v in eff_values if isinstance(v, (int, float))]
    eff_check = True
    if slider_autonomy is not None and eff_values:
        eff_check = all(abs(v - slider_autonomy) <= 0.05 for v in eff_values)
        if not eff_check:
            errors.append("effective_autonomy_out_of_range")
    out["checks"]["effective_autonomy_alignment"] = eff_check

    # Persona propagation
    persona_intake = None
    try:
        persona_intake = (
            (_dget_local(profile, "agent.persona", None)  # type: ignore[arg-type]
             or _dget_local(profile, "persona.agent.code", None)  # type: ignore[arg-type]
             or _dget_local(profile, "persona.code", None))  # type: ignore[arg-type]
        )
    except Exception:
        persona_intake = None
    persona_ok = True
    if persona_intake:
        persona_default = _dget_local(packs.get("02_Global-Instructions_v2.json"), "defaults.persona")
        persona_ok = persona_default == persona_intake
        if not persona_ok:
            errors.append("persona_not_propagated")
    out["checks"]["persona_wired"] = persona_ok

    # Contract: required top-level keys presence per file
    missing_keys: Dict[str, list[str]] = {}
    req = required_keys_map()
    for fname, required in req.items():
        payload = packs.get(fname) if isinstance(packs, Mapping) else None
        present = set(payload.keys()) if isinstance(payload, Mapping) else set()
        miss = [k for k in required if k not in present]
        if miss:
            missing_keys[fname] = miss
    out["missing_keys"] = missing_keys
    out["contract_ok"] = (len(missing_keys) == 0)

    # Cross-reference checks (from 02_Global-Instructions_v2.json)
    crossref_errors: List[str] = []
    p02 = packs.get("02_Global-Instructions_v2.json") or {}
    try:
        if (p02.get("constraints") or {}).get("governance_file") != PACK_ID_TO_FILENAME[4]:
            crossref_errors.append("02.constraints.governance_file")
        if (p02.get("constraints") or {}).get("safety_privacy_file") != PACK_ID_TO_FILENAME[5]:
            crossref_errors.append("02.constraints.safety_privacy_file")
        if (p02.get("constraints") or {}).get("eval_framework_file") != PACK_ID_TO_FILENAME[14]:
            crossref_errors.append("02.constraints.eval_framework_file")
        if (p02.get("constraints") or {}).get("observability_file") != PACK_ID_TO_FILENAME[15]:
            crossref_errors.append("02.constraints.observability_file")
        if ((p02.get("agentic_policies") or {}).get("routing") or {}).get("workflow_pack") != PACK_ID_TO_FILENAME[11]:
            crossref_errors.append("02.agentic_policies.routing.workflow_pack")
        if ((p02.get("agentic_policies") or {}).get("routing") or {}).get("prompt_pack") != PACK_ID_TO_FILENAME[10]:
            crossref_errors.append("02.agentic_policies.routing.prompt_pack")
        if ((p02.get("agentic_policies") or {}).get("reasoning") or {}).get("footprints_spec") != PACK_ID_TO_FILENAME[16]:
            crossref_errors.append("02.agentic_policies.reasoning.footprints_spec")
        if (p02.get("go_live") or {}).get("lifecycle_pack") != PACK_ID_TO_FILENAME[17]:
            crossref_errors.append("02.go_live.lifecycle_pack")
    except Exception:
        crossref_errors.append("02.crossref_unreadable")
    out["crossref_errors"] = crossref_errors
    out["crossref_ok"] = len(crossref_errors) == 0

    # Contract: required top-level keys presence per file (repeat to keep compatibility with earlier code paths)
    missing_keys2: Dict[str, list[str]] = {}
    for fname, required in req.items():
        payload = packs.get(fname) if isinstance(packs, Mapping) else None
        present = set(payload.keys()) if isinstance(payload, Mapping) else set()
        miss = [k for k in required if k not in present]
        if miss:
            missing_keys2[fname] = miss
    out["missing_keys"] = missing_keys2
    out["contract_ok"] = (len(missing_keys2) == 0)

    # Sprint-19: Section completeness and linkage checks for 10/11/12/13/14/18/19/20
    missing_sections: Dict[str, List[str]] = {}

    def _nonempty_list(v: Any) -> bool:
        return isinstance(v, list) and len(v) > 0

    def _nonempty_dict(v: Any) -> bool:
        return isinstance(v, dict) and len(v.keys()) > 0

    # 10
    p10 = packs.get("10_Prompt-Pack_v2.json") or {}
    for sec in ("modules", "reasoning_patterns", "guardrails", "output_contracts"):
        if sec == "modules":
            ok = _nonempty_list(p10.get(sec))
        elif sec == "reasoning_patterns":
            value = p10.get(sec)
            ok = _nonempty_dict(value) or _nonempty_list(value)
        elif sec == "output_contracts":
            value = p10.get(sec)
            ok = _nonempty_list(value) or _nonempty_dict(value)
        else:
            ok = _nonempty_dict(p10.get(sec))
        if not ok:
            missing_sections.setdefault("10_Prompt-Pack_v2.json", []).append(sec)

    # 11
    p11 = packs.get("11_Workflow-Pack_v2.json") or {}
    for sec in ("micro_loops", "graphs", "engine_adapters"):
        if sec == "graphs":
            ok = _nonempty_list(p11.get(sec))
        else:
            value = p11.get(sec)
            ok = _nonempty_dict(value) or _nonempty_list(value)
        if not ok:
            missing_sections.setdefault("11_Workflow-Pack_v2.json", []).append(sec)
    if not _nonempty_dict(p11.get("rollback")):
        missing_sections.setdefault("11_Workflow-Pack_v2.json", []).append("rollback")
    if not _nonempty_dict((p11.get("gates") or {}).get("kpi_targets", {})):
        missing_sections.setdefault("11_Workflow-Pack_v2.json", []).append("gates.kpi_targets")

    # 12
    p12 = packs.get("12_Tool+Data-Registry_v2.json") or {}
    for sec in ("tools", "connectors", "datasets", "secrets", "policies"):
        val = p12.get(sec)
        if sec in ("policies",):
            ok = _nonempty_dict(val)
        else:
            ok = _nonempty_list(val)
        if not ok:
            missing_sections.setdefault("12_Tool+Data-Registry_v2.json", []).append(sec)
    # secrets names only (no values)
    bad_secret = False
    for s in p12.get("secrets", []) or []:
        if isinstance(s, dict):
            if any(k in s for k in ("value", "token", "password", "secret")):
                bad_secret = True
    if bad_secret:
        missing_sections.setdefault("12_Tool+Data-Registry_v2.json", []).append("secrets:no_values")

    # 13
    p13 = packs.get("13_Knowledge-Graph+RAG_Config_v2.json") or {}
    for sec in ("indices", "chunking", "retrievers", "rerankers", "embeddings", "data_quality", "update_policy"):
        val = p13.get(sec)
        ok = _nonempty_list(val) if sec in ("indices", "retrievers", "rerankers") else _nonempty_dict(val)
        if not ok:
            missing_sections.setdefault("13_Knowledge-Graph+RAG_Config_v2.json", []).append(sec)

    # 14
    p14full = packs.get("14_KPI+Evaluation-Framework_v2.json") or {}
    for sec in ("metrics", "eval_pipelines", "reports", "eval_cases"):
        if not _nonempty_list(p14full.get(sec)):
            missing_sections.setdefault("14_KPI+Evaluation-Framework_v2.json", []).append(sec)

    # 18
    p18 = packs.get("18_Reporting-Pack_v2.json") or {}
    for sec in ("outputs", "publishing", "schedule"):
        val = p18.get(sec)
        ok = _nonempty_list(val) if sec == "outputs" else _nonempty_dict(val)
        if not ok:
            missing_sections.setdefault("18_Reporting-Pack_v2.json", []).append(sec)
    if not _nonempty_list(p18.get("templates")):
        missing_sections.setdefault("18_Reporting-Pack_v2.json", []).append("templates")

    # 19
    p19 = packs.get("19_Overlay-Pack_SME-Domain_v1.json") or {}
    for sec in ("policies", "datasets", "prompts", "eval_cases"):
        val = p19.get(sec)
        ok = _nonempty_dict(val) if sec == "policies" else _nonempty_list(val)
        if not ok:
            missing_sections.setdefault("19_Overlay-Pack_SME-Domain_v1.json", []).append(sec)

    # 20
    p20 = packs.get("20_Overlay-Pack_Enterprise_v1.json") or {}
    for sec in ("refs", "policies", "brand", "legal", "stakeholders", "escalations"):
        val = p20.get(sec)
        if sec == "stakeholders":
            ok = _nonempty_list(val)
        elif sec == "policies":
            ok = _nonempty_list(val) or _nonempty_dict(val)
        else:
            ok = _nonempty_dict(val)
        if not ok:
            missing_sections.setdefault("20_Overlay-Pack_Enterprise_v1.json", []).append(sec)

    # Linkage checks
    linkage_errors: List[str] = []
    # 10↔11: module IDs referenced by 11.graphs exist in 10.modules
    module_ids: Set[str] = set()
    try:
        for m in (p10.get("modules") or []):
            mid = str(m.get("id") or "").strip()
            if mid:
                module_ids.add(mid)
        for g in (p11.get("graphs") or []):
            for n in (g.get("nodes") or []):
                mid = str(n.get("module_id") or "").strip()
                if mid and mid not in module_ids:
                    linkage_errors.append(f"11.nodes.module_id_missing:{mid}")
    except Exception:
        pass

    # 18↔15: reporting fields exist with matching types
    det_fields = set((packs.get("15_Observability+Telemetry_Spec_v2.json") or {}).get("decision_event_fields", []) or [])
    det_types = dict((packs.get("15_Observability+Telemetry_Spec_v2.json") or {}).get("decision_event_field_types", {}) or {})
    try:
        used: Set[str] = set()
        for tpl in (p18.get("templates") or []):
            for f in (tpl.get("fields") or []):
                used.add(str(f))
        for f in used:
            if f not in det_fields:
                linkage_errors.append(f"18.fields.unknown:{f}")
                out.setdefault("errors", []).append(
                    f"18_Reporting-Pack_v2.json: template field '{f}' not declared in 15.decision_event_fields"
                )
            else:
                t = det_types.get(f)
                if t not in {"string", "number", "boolean"}:
                    linkage_errors.append(f"18.fields.type_invalid:{f}")
                    out.setdefault("errors", []).append(
                        f"15_Observability+Telemetry_Spec_v2.json: decision_event_field_types['{f}'] must be string|number|boolean"
                    )
    except Exception:
        pass

    # 12/13 resolution: tools referenced by 11 exist; retriever/index names resolve from 10→13
    tool_names = {str(t.get("name")).strip() for t in (p12.get("tools") or []) if isinstance(t, dict)}
    try:
        for g in (p11.get("graphs") or []):
            for n in (g.get("nodes") or []):
                t = str(n.get("tool") or "").strip()
                if t and t not in tool_names:
                    linkage_errors.append(f"11.nodes.tool_missing:{t}")
    except Exception:
        pass
    retrievers = {str(r.get("name")).strip(): str(r.get("index")).strip() for r in (p13.get("retrievers") or []) if isinstance(r, dict)}
    indices = {str(x.get("name")).strip() for x in (p13.get("indices") or []) if isinstance(x, dict)}
    try:
        for m in (p10.get("modules") or []):
            rv = str(m.get("retriever") or "").strip()
            if rv:
                if rv not in retrievers:
                    linkage_errors.append(f"10.modules.retriever_missing:{rv}")
                else:
                    idx = retrievers.get(rv)
                    if idx and idx not in indices:
                        linkage_errors.append(f"13.indices.missing:{idx}")
    except Exception:
        pass

    # 15 types discipline: every declared field has a valid type
    if det_fields:
        for f in det_fields:
            t = det_types.get(f)
            if t not in {"string", "number", "boolean"}:
                out.setdefault("errors", []).append(
                    f"15_Observability+Telemetry_Spec_v2.json: decision_event_field_types['{f}'] must be string|number|boolean"
                )

    if linkage_errors:
        out["linkage_errors"] = linkage_errors

    out["missing_sections"] = missing_sections
    out["packs_complete"] = (len(missing_sections) == 0)
    for pack, vals in missing_sections.items():
        if isinstance(vals, list):
            for sec in vals:
                warnings.append(f"{pack}:{sec}")

    # Secrets guard: names-only — fail if any non-empty secret values present
    if p12.get("secrets"):
        for s in p12.get("secrets") or []:
            if isinstance(s, dict):
                for bad in ("value", "token", "password", "secret"):
                    if bad in s and s.get(bad):
                        out.setdefault("errors", []).append(
                            "12_Tool+Data-Registry_v2.json: secrets must not include values; store names only"
                        )
                        break

    # schema_keys sorted equality is enforced by scaffolder in full mode; do not error here to keep overlays green

    # Contract: required top-level keys presence per file
    missing_keys: Dict[str, list[str]] = {}
    req = required_keys_map()
    for fname, required in req.items():
        payload = packs.get(fname) if isinstance(packs, Mapping) else None
        present = set(payload.keys()) if isinstance(payload, Mapping) else set()
        miss = [k for k in required if k not in present]
        if miss:
            missing_keys[fname] = miss
    out["missing_keys"] = missing_keys
    out["contract_ok"] = (len(missing_keys) == 0)

    # Optional failure gate via env
    try:
        fail_on_parity = str(os.environ.get("FAIL_ON_PARITY", "false")).lower() in ("1","true","yes")
        if fail_on_parity and not all(parity.values()):
            out.setdefault("errors", []).append("parity_failed")
    except Exception:
        pass

    if warnings:
        deduped: list[str] = []
        seen: set[str] = set()
        for w in warnings:
            if w in seen:
                continue
            seen.add(w)
            deduped.append(w)
        out["warnings"] = deduped

    if errors:
        out["status"] = "error"

    return out


def attach_integrity_to_reporting_pack(
    report: Mapping[str, Any] | None, packs: Mapping[str, Any]
) -> Dict[str, Any] | None:
    """Return updated Reporting Pack payload with integrity snapshot embedded."""

    if not isinstance(packs, dict):
        return None
    payload = packs.get("18_Reporting-Pack_v2.json")
    if not isinstance(payload, Mapping):
        return None
    updated: Dict[str, Any] = dict(payload)
    exec_brief = updated.get("exec_brief") if isinstance(updated.get("exec_brief"), Mapping) else {}
    exec_brief = dict(exec_brief or {})
    objectives_block = {}
    if isinstance(report, Mapping):
        obj = report.get("objectives") if isinstance(report.get("objectives"), Mapping) else {}
        objectives_block = {
            "status": (obj or {}).get("status") or "missing",
            "count": int((obj or {}).get("count") or 0),
            "has_generic": bool((obj or {}).get("has_generic")),
            "warnings": list((obj or {}).get("warnings") or []),
        }
    exec_brief["integrity_snapshot"] = {
        "status": (report or {}).get("status", "ok") if isinstance(report, Mapping) else "ok",
        "packs_complete": bool((report or {}).get("packs_complete")) if isinstance(report, Mapping) else False,
        "errors": list((report or {}).get("errors") or []) if isinstance(report, Mapping) else [],
        "warnings": list((report or {}).get("warnings") or []) if isinstance(report, Mapping) else [],
        "parity": (report or {}).get("parity") if isinstance(report, Mapping) else {},
        "objectives": objectives_block or {"status": "missing", "count": 0, "has_generic": False, "warnings": []},
    }
    updated["exec_brief"] = exec_brief
    packs["18_Reporting-Pack_v2.json"] = updated
    return updated
