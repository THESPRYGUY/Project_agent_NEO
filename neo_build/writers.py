"""Writers for the deterministic 20-pack agent repository.

Each writer function receives the parsed intake ``profile`` and a target
``out_dir`` and returns a dictionary of the pack payload used for integrity
reporting.
"""

from __future__ import annotations

import uuid
from pathlib import Path
import json
from typing import Any, Dict, List, Mapping, Tuple

from .contracts import (
    CANONICAL_PACK_FILENAMES,
    KPI_TARGETS,
)
from .utils import json_write, deep_sorted
from .validators import (
    compute_effective_autonomy,
    human_gate_actions,
    observability_spec,
    kpi_targets_sync,
    preferences_flow_flags,
)


def _get(mapping: Mapping[str, Any] | None, key: str, default: Any = None) -> Any:
    if not isinstance(mapping, Mapping):
        return default
    return mapping.get(key, default)


def _dget(mapping: Mapping[str, Any] | None, path: str, default: Any = None) -> Any:
    cur: Any = mapping
    for part in path.split('.'):
        if not isinstance(cur, Mapping):
            return default
        cur = cur.get(part)
    return cur if cur is not None else default


def _profile_sections(profile: Mapping[str, Any]) -> Tuple[dict, dict, dict, dict, dict, dict, dict]:
    identity = _get(profile, "identity", {}) or {}
    role_profile = _get(profile, "role_profile", {}) or {}
    sector_profile = _get(profile, "sector_profile", {}) or {}
    capabilities_tools = _get(profile, "capabilities_tools", {}) or {}
    memory = _get(profile, "memory", {}) or {}
    governance_eval = _get(profile, "governance_eval", {}) or {}
    preferences = _get(profile, "preferences", {}) or {}
    return identity, role_profile, sector_profile, capabilities_tools, memory, governance_eval, preferences


def _naics_summary(profile: Mapping[str, Any]) -> dict:
    na = _get(profile, "classification", {})
    if isinstance(na, Mapping):
        na = _get(na, "naics", {})
    if not isinstance(na, Mapping) or not na:
        na = _get(profile, "naics", {})
    if not isinstance(na, Mapping):
        na = {}
    return {
        "code": str(_get(na, "code", "")),
        "title": str(_get(na, "title", "")),
        "level": _get(na, "level", None),
        "lineage": list(_get(na, "lineage", []) or []),
    }


def _owners() -> List[str]:
    return ["CAIO", "CPA", "TeamLead"]


def write_all_packs(profile: Mapping[str, Any], out_dir: Path) -> Dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)

    packs: Dict[str, Any] = {}

    identity, role_profile, sector_profile, capabilities_tools, memory, governance_eval, preferences = _profile_sections(profile)

    # 01 README+Directory Map
    files = list(CANONICAL_PACK_FILENAMES)
    readme_map = {"version": 2, "files": files}
    packs["01_README+Directory-Map_v2.json"] = readme_map
    json_write(out_dir / "01_README+Directory-Map_v2.json", readme_map)

    # 02 Global Instructions
    naics = _naics_summary(profile)
    eff_autonomy = compute_effective_autonomy(preferences, _get(profile, "routing_defaults", {}))
    gi = {
        "version": 2,
        "context": {"naics": naics},
        "references": {"reasoning_schema": "16_Reasoning-Footprints_Schema_v1.json", "memory_schema": "08_Memory-Schema_v2.json"},
        "effective_autonomy": eff_autonomy,
        "store_raw_cot": False,
        # Sprint-1: carry derived regulators into 02 for downstream parity checks
        "safety": {"regulatory": list(_get(sector_profile, "regulatory", []) or [])},
    }
    # Add observability.kpi_targets for explicit 02↔14 parity checks
    try:
        gi["observability"] = {"kpi_targets": kpi_targets_sync()}
    except Exception:
        gi["observability"] = {"kpi_targets": {}}
    packs["02_Global-Instructions_v2.json"] = gi
    json_write(out_dir / "02_Global-Instructions_v2.json", gi)

    # 03 Operating Rules
    hg = human_gate_actions(_get(_get(capabilities_tools, "human_gate", {}), "actions", []))
    # Sprint-3.1: RBAC owners propagation (additive) when identity.owners present
    base_roles = list(_dget(profile, "governance.rbac.roles", []) or [])
    owners_from_identity = list((_get(identity, "owners") or [])) if isinstance(identity, Mapping) else []
    if owners_from_identity:
        # Canonical deterministic order: defaults triad first, then owners sorted (casefold), unique
        defaults = _owners()
        triad_cf = {d.casefold() for d in defaults}
        # unique owners by casefold
        seen: set[str] = set()
        uniq_owners: List[str] = []
        for o in owners_from_identity:
            s = str(o)
            k = s.casefold()
            if s and k not in seen:
                seen.add(k)
                uniq_owners.append(s)
        sorted_owners = sorted([o for o in uniq_owners if o.casefold() not in triad_cf], key=str.casefold)
        roles_out: List[str] = list(defaults) + sorted_owners
    else:
        # leave defaults unchanged
        roles_out = base_roles

    orules = {
        "version": 2,
        "human_gate": {"actions": hg},
        "rbac": {"roles": roles_out},
        # Sprint-4: include activation gate strings for explicit parity checks
        "gates": {
            "activation": [
                f"PRI>={KPI_TARGETS.get('PRI_min')}",
                f"HAL<={KPI_TARGETS.get('HAL_max')}",
                f"AUD>={KPI_TARGETS.get('AUD_min')}",
            ]
        },
    }
    packs["03_Operating-Rules_v2.json"] = orules
    # Preserve canonical list ordering for RBAC roles (do not deep-sort lists)
    (out_dir / "03_Operating-Rules_v2.json").write_text(
        json.dumps(orules, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    # 04 Governance + Risk Register
    gro = {
        "version": 2,
        "classification_default": _get(_get(profile, "governance_eval", {}), "classification_default", "confidential"),
        "risk_register_tags": list(_get(_get(profile, "governance_eval", {}), "risk_register_tags", []) or []),
        "pii_flags": list(_get(_get(profile, "governance_eval", {}), "pii_flags", []) or []),
        "regulators": list(_get(sector_profile, "regulatory", []) or []),
        # v3 nested targets
        "policy": {
            "classification_default": _dget(profile, "governance.policy.classification_default", _get(_get(profile, "governance_eval", {}), "classification_default", "confidential")),
            "no_impersonation": bool(_get(identity, "no_impersonation", True)),
        },
        "frameworks": {
            "regulators": list(_dget(profile, "compliance.regulators", _get(sector_profile, "regulatory", [])) or []),
        },
    }
    packs["04_Governance+Risk-Register_v2.json"] = gro
    json_write(out_dir / "04_Governance+Risk-Register_v2.json", gro)

    # 05 Safety + Privacy
    sp = {
        "version": 2,
        "no_impersonation": bool(_get(identity, "no_impersonation", True)),
        "pii_mask_on_ingest": True,
        # v3 targets
        "privacy_policies": {
            "pii_flags": list(_dget(profile, "privacy.pii_flags", _get(_get(profile, "governance_eval", {}), "pii_flags", [])) or []),
        },
    }
    packs["05_Safety+Privacy_Guardrails_v2.json"] = sp
    json_write(out_dir / "05_Safety+Privacy_Guardrails_v2.json", sp)

    # 06 Role Recipes Index
    primary_role_code = str(_dget(profile, "role.primary.code", _get(role_profile, "archetype", "")))
    rri = {
        "version": 2,
        "role_recipe_ref": str(_get(role_profile, "role_recipe_ref", "")),
        "objectives": list(_get(role_profile, "objectives", []) or []),
        "role_title": str(_get(role_profile, "role_title", "")),
        "archetype": str(_get(role_profile, "archetype", "")),
        # v3 targets
        "mapping": {
            "primary_role_code": primary_role_code,
            "agent_id": str(_get(identity, "agent_id", "")),
        },
        "roles_index": [{
            "code": str(_get(role_profile, "archetype", "")) or primary_role_code,
            "title": str(_dget(profile, "role.title", _get(role_profile, "role_title", ""))),
            "objectives": list(_get(role_profile, "objectives", []) or []),
        }],
    }
    packs["06_Role-Recipes_Index_v2.json"] = rri
    json_write(out_dir / "06_Role-Recipes_Index_v2.json", rri)

    # 07 Subagent Role Recipes (flow flags)
    flags = preferences_flow_flags(_get(preferences, "collaboration_mode", ""))
    srr = {"version": 2, "planner_builder_evaluator": flags["planner_builder_evaluator"], "auto_plan_step": flags["auto_plan_step"], "recipes": []}
    packs["07_Subagent_Role-Recipes_v2.json"] = srr
    json_write(out_dir / "07_Subagent_Role-Recipes_v2.json", srr)

    # 08 Memory Schema
    retention_days = min(int(_get(memory, "retention_days", 180) or 180), 180)
    ms = {
        "id": "memory_schema_v2",
        "version": 2,
        "principles": {"redact_pii": True},
        "retention": {"episodic": {"retention_days": retention_days}},
        "memory_scopes": list(_get(memory, "memory_scopes", []) or []),
        "initial_memory_packs": list(_get(memory, "initial_memory_packs", []) or []),
        "optional_packs": list(_get(memory, "optional_packs", []) or []),
        # v3 targets
        "scopes": list(_dget(profile, "memory.scopes", _get(memory, "memory_scopes", [])) or []),
        "packs": {"initial": list(_dget(profile, "memory.packs.initial", _get(memory, "initial_memory_packs", [])) or []), "optional": list(_dget(profile, "memory.packs.optional", _get(memory, "optional_packs", [])) or [])},
        "sync": {"allowed_sources": list(_dget(profile, "memory.sync.allowed_sources", _get(memory, "data_sources", [])) or [])},
    }
    packs["08_Memory-Schema_v2.json"] = ms
    json_write(out_dir / "08_Memory-Schema_v2.json", ms)

    # 09 Agent Manifests Catalog
    owners_from_identity = list((_get(identity, "owners") or [])) if isinstance(identity, Mapping) else []
    owners = owners_from_identity or _owners()
    # Selected role title precedence: role.role_title -> role_profile.role_title -> first_non_empty(06.roles_index[*].title)
    selected_role_title = str(_dget(profile, "role.role_title", "")).strip()
    if not selected_role_title:
        selected_role_title = str(_get(role_profile, "role_title", "")).strip()
    if not selected_role_title:
        try:
            titles = [str(x.get("title", "")).strip() for x in (rri.get("roles_index") or [])]
            selected_role_title = next((t for t in titles if t), "")
        except Exception:
            selected_role_title = ""

    amc = {
        "version": 2,
        "owners": owners,
        "summary": {
            "sector": _get(sector_profile, "sector", ""),
            "region": list(_get(sector_profile, "region", []) or []),
            "languages": list(_get(sector_profile, "languages", []) or []),
            "regulators": list(_get(sector_profile, "regulatory", []) or []),
            "naics": naics,
        },
        # v3 target agents list
        "agents": [
            {
                "display_name": str(_get(identity, "display_name", _get(_get(profile, "agent", {}), "name", ""))),
                "owners": owners,
                "agent_id": str(_get(identity, "agent_id", "")),
                "role_title": selected_role_title,
            }
        ],
    }
    packs["09_Agent-Manifests_Catalog_v2.json"] = amc
    json_write(out_dir / "09_Agent-Manifests_Catalog_v2.json", amc)

    # 10 Prompt Pack (minimal stub)
    pp = {"version": 2, "prompts": []}
    packs["10_Prompt-Pack_v2.json"] = pp
    json_write(out_dir / "10_Prompt-Pack_v2.json", pp)

    # 11 Workflow Pack with KPI gates
    gates = {"kpi_targets": kpi_targets_sync(), "effective_autonomy": eff_autonomy}
    persona_defaults = {"persona": _dget(profile, "persona.mbti", _get(_get(profile, "agent", {}), "persona", "")), "tone": _dget(profile, "persona.tone", "")}
    wp = {"version": 2, "name": "DefaultFlow", "gates": gates, "defaults": persona_defaults}
    packs["11_Workflow-Pack_v2.json"] = wp
    json_write(out_dir / "11_Workflow-Pack_v2.json", wp)

    # 12 Tool + Data Registry
    connectors = []
    for c in list(_get(_get(capabilities_tools, "tool_connectors", {}), "", [])):
        # Defensive: if incorrect structure sneaks in
        pass
    # Preferred detailed connectors structure
    for c in _get(capabilities_tools, "tool_connectors", []) or []:
        if isinstance(c, Mapping):
            name = str(c.get("name", "")).strip()
            enabled = bool(c.get("enabled", False))
            scopes = list(c.get("scopes", []) or [])
            secret = str(c.get("secret_ref", "SET_ME"))
            # Alias mapping
            if name == "clm":
                name = "sharepoint"
            if name == "dms":
                name = "gdrive"
            if not name:
                name = "placeholder"
                enabled = False
                scopes = ["read"]
                secret = "SET_ME"
            connectors.append({"name": name, "enabled": enabled, "scopes": scopes, "secret_ref": secret})
    tr = {"version": 2, "connectors": connectors}
    packs["12_Tool+Data-Registry_v2.json"] = tr
    json_write(out_dir / "12_Tool+Data-Registry_v2.json", tr)

    # 13 Knowledge Graph + RAG Config
    indexes = list(_get(memory, "data_sources", []) or [])
    kr = {"version": 2, "default_index": "default", "indexes": indexes}
    packs["13_Knowledge-Graph+RAG_Config_v2.json"] = kr
    json_write(out_dir / "13_Knowledge-Graph+RAG_Config_v2.json", kr)

    # 14 KPI + Evaluation Framework
    k14 = {"version": 2, "targets": kpi_targets_sync()}
    packs["14_KPI+Evaluation-Framework_v2.json"] = k14
    json_write(out_dir / "14_KPI+Evaluation-Framework_v2.json", k14)

    # 15 Observability + Telemetry
    obs = observability_spec()
    obs["version"] = 2
    # v3 telemetry targets
    rate = _dget(profile, "telemetry.sampling.rate", None)
    if rate is not None:
        obs["sampling"] = {"rate": float(rate)}
    sinks = _dget(profile, "telemetry.sinks", None)
    if isinstance(sinks, list):
        obs["sinks"] = list(sinks)
    strategy = _dget(profile, "telemetry.pii_redaction.strategy", None)
    if strategy:
        obs["pii_redaction"] = {"strategy": strategy}
    packs["15_Observability+Telemetry_Spec_v2.json"] = obs
    json_write(out_dir / "15_Observability+Telemetry_Spec_v2.json", obs)

    # 16 Reasoning Footprints Schema
    rf = {"version": 1, "store_raw_cot": False}
    packs["16_Reasoning-Footprints_Schema_v1.json"] = rf
    json_write(out_dir / "16_Reasoning-Footprints_Schema_v1.json", rf)

    # 17 Lifecycle Pack
    lc = {
        "version": 2,
        "gates": {
            "kpi_targets": kpi_targets_sync(),
            "activation": [
                f"PRI>={KPI_TARGETS.get('PRI_min')}",
                f"HAL<={KPI_TARGETS.get('HAL_max')}",
                f"AUD>={KPI_TARGETS.get('AUD_min')}",
            ],
            "rollback": True,
            "effective_autonomy": eff_autonomy,
        },
        "stages": [str(_dget(profile, "lifecycle.stage", "dev"))],
    }
    packs["17_Lifecycle-Pack_v2.json"] = lc
    json_write(out_dir / "17_Lifecycle-Pack_v2.json", lc)

    # 18 Reporting Pack with default field spec
    rp = {"version": 2, "templates": [
        {
            "id": "default",
            "name": "Default Template",
            "fields": ["ID", "Title", "PolicyRef", "Severity", "Owner", "Status", "Remediation", "LastUpdated"],
        }
    ]}
    packs["18_Reporting-Pack_v2.json"] = rp
    json_write(out_dir / "18_Reporting-Pack_v2.json", rp)

    # 19 SME-Domain Overlay
    od = {
        "version": 1,
        "sector": _get(sector_profile, "sector", ""),
        "industry": _get(sector_profile, "industry", ""),
        "region": list(_get(sector_profile, "region", []) or []),
        "regulators": list(_get(sector_profile, "regulatory", []) or []),
        "naics": naics,
        # Sprint-1: add refs block for canonical consumption
        "refs": {
            "sector": _get(sector_profile, "sector", ""),
            "region": list(_get(sector_profile, "region", []) or []),
            "regulators": list(_get(sector_profile, "regulatory", []) or []),
        },
    }
    packs["19_Overlay-Pack_SME-Domain_v1.json"] = od
    json_write(out_dir / "19_Overlay-Pack_SME-Domain_v1.json", od)

    # 20 Enterprise Overlay
    eo = {
        "version": 1,
        "brand_voice": "crisp, analytical, executive",
        "disclaimer": "Advisory support only; no legal advice.",
    }
    packs["20_Overlay-Pack_Enterprise_v1.json"] = eo
    json_write(out_dir / "20_Overlay-Pack_Enterprise_v1.json", eo)

    return packs


def write_repo_files(profile: Mapping[str, Any], out_dir: Path) -> Dict[str, Any]:
    """Compose README.md and neo_agent_config.json, then write packs."""

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Compose README
    agent = _get(profile, "agent", {})
    identity, role_profile, sector_profile, *_ = _profile_sections(profile)
    naics = _naics_summary(profile)

    readme_lines = [
        f"# Agent: {str(_get(identity, 'display_name') or _get(agent, 'name') or 'Unnamed Agent')}",
        "",
        "## Role",
        f"- Title: {str(_get(role_profile, 'role_title', ''))}",
        f"- Archetype: {str(_get(role_profile, 'archetype', ''))}",
        "",
        "## Sector",
        f"- Sector: {str(_get(sector_profile, 'sector', ''))}",
        f"- Region: {', '.join(_get(sector_profile, 'region', []) or [])}",
        f"- Regulators: {', '.join(_get(sector_profile, 'regulatory', []) or [])}",
        "",
        "## NAICS",
        f"- Code: {naics.get('code', '')} (level {naics.get('level', '')})",
        f"- Title: {naics.get('title', '')}",
        "",
        "## Directory Map & Narrative",
        "See 01_README+Directory-Map_v2.json for canonical file listing.",
    ]
    (out_dir / "README.md").write_text("\n".join(readme_lines) + "\n", encoding="utf-8", newline="\n")

    # neo_agent_config.json (minimal)
    cfg = {
        "agent": {
            "id": str(_get(identity, "agent_id", "") or uuid.uuid4().hex[:8]),
            "display_name": str(_get(identity, "display_name", _get(agent, "name", "")) or "Unnamed Agent"),
        },
    }
    json_write(out_dir / "neo_agent_config.json", cfg)

    # Packs
    packs = write_all_packs(profile, out_dir)
    return packs
