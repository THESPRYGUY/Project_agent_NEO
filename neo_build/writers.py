"""Writers for the deterministic 20-pack agent repository.

Each writer function receives the parsed intake ``profile`` and a target
``out_dir`` and returns a dictionary of the pack payload used for integrity
reporting.
"""

from __future__ import annotations

import uuid
import os
from pathlib import Path
import json
import shutil
from copy import deepcopy
from functools import lru_cache
from typing import Any, Dict, List, Mapping, Tuple

from .contracts import (
    CANONICAL_PACK_FILENAMES,
    KPI_TARGETS,
    REQUIRED_ALERTS,
    REQUIRED_EVENTS,
)
from .ssot import canonical_industry_from_naics
from .utils import json_write
from .scaffolder import get_contract_mode, enrich_packs
from .schemas import required_keys_map
from .validators import (
    compute_effective_autonomy,
    human_gate_actions,
    observability_spec,
    kpi_targets_sync,
    preferences_flow_flags,
)
from neo_agent.writer import normalise_pii_flags

CONTRACT_MODE = os.getenv("NEO_CONTRACT_MODE", "scaffold").strip().lower()
if CONTRACT_MODE not in {"full", "preview"}:
    CONTRACT_MODE = "scaffold"
CONTRACT_FULL = CONTRACT_MODE == "full"

REPO_ROOT = Path(__file__).resolve().parents[1]
BASE_TEMPLATE_DIRS = [
    REPO_ROOT / "generated_repos" / "agent-build-007-2-1-1",
    REPO_ROOT / "canon",
]
EVALUATION_SETS_DIR = REPO_ROOT / "evaluation_sets"
EVAL_SET_FILENAME = "strategy_eval_suite_v1.json"


def _deep_merge_dicts(
    base: Mapping[str, Any] | None, incoming: Mapping[str, Any] | None
) -> Dict[str, Any]:
    if not isinstance(base, Mapping):
        base = {}
    result: Dict[str, Any] = {k: deepcopy(v) for k, v in base.items()}
    if not isinstance(incoming, Mapping):
        return result
    for key, value in incoming.items():
        if isinstance(value, Mapping) and isinstance(result.get(key), Mapping):
            result[key] = _deep_merge_dicts(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


@lru_cache(maxsize=None)
def _load_base_pack_template(filename: str) -> Dict[str, Any]:
    merged: Dict[str, Any] = {}
    for base_dir in BASE_TEMPLATE_DIRS:
        path = base_dir / filename
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        merged = _deep_merge_dicts(merged, data)
    return merged


def _pack_template(filename: str) -> Dict[str, Any]:
    base = _load_base_pack_template(filename)
    if not base:
        return {}
    return deepcopy(base)


def _attach_agent_meta(payload: Dict[str, Any], agent_id: str) -> Dict[str, Any]:
    if not agent_id:
        return payload
    meta = payload.get("meta")
    if not isinstance(meta, dict):
        meta = {}
        payload["meta"] = meta
    meta["agent_id"] = agent_id
    return payload


_AGENT_STRATEGY_DEFAULTS: Dict[str, Dict[str, str]] | None = None
_CANONICAL_AGENT_CARDS: List[Dict[str, Any]] | None = None
_STRATEGY_INVOCATION_BLOCK: List[Dict[str, Any]] | None = None
STRATEGY_INVOCATION_SCHEMA_VERSION = "1.1.0"
STRATEGY_INVOCATION_KPI_DEFAULTS = {"PRI_min": 0.95, "HAL_max": 0.02, "AUD_min": 0.9}
STRATEGY_INVOCATION_FIELDS = [
    "timestamp",
    "event_type",
    "schema_version",
    "agent_id",
    "run_id",
    "workflow_id",
    "workflow_run_id",
    "correlation_id",
    "task_id",
    "footprint_id",
    "scenario_id",
    "strategy_profile",
    "strategy_chain",
    "task_type",
    "risk_tier",
    "token_count",
    "tokens_input",
    "tokens_output",
    "latency_ms",
    "pri_score",
    "hal_score",
    "aud_score",
    "kpi_targets",
    "safety_flags",
    "hitl_required",
    "hitl_applied",
    "hitl_actor",
    "status",
]
STRATEGY_INVOCATION_REQUIRED_FIELDS = [
    "timestamp",
    "event_type",
    "schema_version",
    "agent_id",
    "run_id",
    "workflow_id",
    "workflow_run_id",
    "correlation_id",
    "task_id",
    "footprint_id",
    "scenario_id",
    "strategy_profile",
    "strategy_chain",
    "task_type",
    "risk_tier",
    "kpi_targets",
    "hitl_required",
    "hitl_applied",
    "status",
]
STRATEGY_INVOCATION_OPTIONAL_FIELDS = [
    "token_count",
    "tokens_input",
    "tokens_output",
    "latency_ms",
    "pri_score",
    "hal_score",
    "aud_score",
    "safety_flags",
    "hitl_actor",
]
STRATEGY_INVOCATION_NOTES = [
    "Required fields: timestamp, event_type, schema_version, agent_id, run_id, workflow_id, workflow_run_id, correlation_id, task_id, footprint_id, scenario_id, strategy_profile, strategy_chain, task_type, risk_tier, kpi_targets, hitl_required, hitl_applied, status.",
    "Optional fields: token_count, tokens_input, tokens_output, latency_ms, pri_score, hal_score, aud_score, safety_flags, hitl_actor (MUST be null unless hitl_applied=true).",
    "KPI thresholds are tracked only inside kpi_targets (PRI_min, HAL_max, AUD_min).",
    "HITL semantics must align with advisory_pending, completed_non_hitl, and completed_hitl cases.",
]
STRATEGY_INVOCATION_METRICS = [
    "strategy_invocations",
    "pri_score",
    "hal_score",
    "aud_score",
    "token_count",
    "latency_ms",
    "hitl_activation_rate",
]


def _agent_strategy_defaults() -> Dict[str, Dict[str, str]]:
    global _AGENT_STRATEGY_DEFAULTS
    if _AGENT_STRATEGY_DEFAULTS is not None:
        return _AGENT_STRATEGY_DEFAULTS
    defaults: Dict[str, Dict[str, str]] = {}
    path = REPO_ROOT / "canon" / "09_Agent-Manifests_Catalog_v2.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        _AGENT_STRATEGY_DEFAULTS = {}
        return _AGENT_STRATEGY_DEFAULTS
    agents = data.get("agents", [])
    if isinstance(agents, list):
        for entry in agents:
            if not isinstance(entry, dict):
                continue
            agent_id = entry.get("agent_id")
            if not isinstance(agent_id, str):
                continue
            defaults[agent_id] = {
                "strategy_profile": entry.get("strategy_profile"),
                "risk_tier": entry.get("risk_tier"),
            }
    _AGENT_STRATEGY_DEFAULTS = defaults
    return _AGENT_STRATEGY_DEFAULTS


def _canonical_agent_cards() -> List[Dict[str, Any]]:
    global _CANONICAL_AGENT_CARDS
    if _CANONICAL_AGENT_CARDS is not None:
        return [deepcopy(card) for card in _CANONICAL_AGENT_CARDS]
    path = REPO_ROOT / "canon" / "09_Agent-Manifests_Catalog_v2.json"
    cards: List[Dict[str, Any]] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        _CANONICAL_AGENT_CARDS = []
        return []
    for entry in data.get("agents", []):
        if isinstance(entry, dict):
            cards.append(entry)
    _CANONICAL_AGENT_CARDS = cards
    return [deepcopy(card) for card in cards]


def _strategy_invocation_block(agent_id: str | None = None) -> List[Dict[str, Any]]:
    """Return a normalized strategy_invocation payload mirrored from canon."""

    global _STRATEGY_INVOCATION_BLOCK
    if _STRATEGY_INVOCATION_BLOCK is not None:
        template_block = deepcopy(_STRATEGY_INVOCATION_BLOCK)
    else:
        template = _load_base_pack_template("15_Observability+Telemetry_Spec_v2.json")
        reference = template.get("strategy_invocation")
        if isinstance(reference, list) and reference:
            _STRATEGY_INVOCATION_BLOCK = reference
            template_block = deepcopy(reference)
        else:
            block = [
                {
                    "name": "strategy_invocation",
                    "description": "Telemetry contract for each strategy invocation (strategy-aware run).",
                    "fields": list(STRATEGY_INVOCATION_FIELDS),
                    "metrics": list(STRATEGY_INVOCATION_METRICS),
                }
            ]
            _STRATEGY_INVOCATION_BLOCK = block
            template_block = deepcopy(block)

    normalized: List[Dict[str, Any]] = []
    for entry in template_block:
        normalized.append(_ensure_strategy_invocation_entry(entry, agent_id))
    return normalized


def _ensure_strategy_invocation_entry(
    entry: Mapping[str, Any] | None, agent_id: str | None
) -> Dict[str, Any]:
    candidate = deepcopy(entry or {})
    candidate.setdefault("name", "strategy_invocation")
    candidate["event_type"] = "strategy_invocation"
    schema_version = str(
        candidate.get("schema_version") or STRATEGY_INVOCATION_SCHEMA_VERSION
    )
    candidate["schema_version"] = schema_version

    notes = candidate.get("notes")
    if not isinstance(notes, list):
        notes = []
    merged_notes = _dedupe_preserve_order(
        [str(note).strip() for note in notes if isinstance(note, str)]
        + STRATEGY_INVOCATION_NOTES
    )
    candidate["notes"] = merged_notes

    fields = candidate.get("fields")
    if not isinstance(fields, list):
        fields = []
    candidate["fields"] = _dedupe_preserve_order(fields + STRATEGY_INVOCATION_FIELDS)

    required_fields = candidate.get("required_fields")
    if not isinstance(required_fields, list):
        required_fields = []
    candidate["required_fields"] = _dedupe_preserve_order(
        required_fields + STRATEGY_INVOCATION_REQUIRED_FIELDS
    )

    optional_fields = candidate.get("optional_fields")
    if not isinstance(optional_fields, list):
        optional_fields = []
    candidate["optional_fields"] = _dedupe_preserve_order(
        optional_fields + STRATEGY_INVOCATION_OPTIONAL_FIELDS
    )

    metrics = candidate.get("metrics")
    if not isinstance(metrics, list):
        metrics = []
    candidate["metrics"] = _dedupe_preserve_order(metrics + STRATEGY_INVOCATION_METRICS)

    candidate["kpi_targets"] = _normalize_kpi_targets(candidate.get("kpi_targets"))
    candidate["hitl_semantics"] = _normalize_hitl_semantics(
        candidate.get("hitl_semantics")
    )

    template_examples = (
        [ex for ex in candidate.get("examples", []) if isinstance(ex, Mapping)] or []
    )
    resolved_agent_id = (
        str(agent_id).strip()
        if isinstance(agent_id, str) and agent_id.strip()
        else _first_agent_id(template_examples)
        or "agent.UNSPECIFIED"
    )
    candidate["examples"] = _canonical_strategy_examples(
        resolved_agent_id, schema_version, candidate["kpi_targets"]
    )
    return candidate


def _normalize_kpi_targets(payload: Mapping[str, Any] | None) -> Dict[str, float]:
    normalized = dict(STRATEGY_INVOCATION_KPI_DEFAULTS)
    if isinstance(payload, Mapping):
        for key in ("PRI_min", "HAL_max", "AUD_min"):
            value = payload.get(key)
            if isinstance(value, (int, float)):
                normalized[key] = float(value)
    return normalized


def _normalize_hitl_semantics(
    payload: Mapping[str, Any] | None
) -> Dict[str, Dict[str, Any]]:
    fallback = {
        "advisory_pending": {
            "hitl_actor": None,
            "hitl_applied": False,
            "hitl_required": True,
            "status": "hitl_pending",
        },
        "completed_non_hitl": {
            "hitl_actor": None,
            "hitl_applied": False,
            "hitl_required": False,
            "status": "completed",
        },
        "completed_hitl": {
            "hitl_actor": "regulatory_counsel",
            "hitl_applied": True,
            "hitl_required": True,
            "status": "completed",
        },
    }
    semantics: Dict[str, Dict[str, Any]] = {}
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            if isinstance(value, Mapping):
                semantics[key] = dict(value)
    for key, defaults in fallback.items():
        merged = semantics.get(key, {})
        for field, default_value in defaults.items():
            merged.setdefault(field, default_value)
        semantics[key] = merged
    return semantics


def _first_agent_id(examples: List[Mapping[str, Any]] | None) -> str | None:
    if not examples:
        return None
    for example in examples:
        candidate = example.get("agent_id")
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def _canonical_strategy_examples(
    agent_id: str, schema_version: str, kpi_targets: Mapping[str, Any]
) -> List[Dict[str, Any]]:
    kpi_payload = {
        "PRI_min": float(kpi_targets.get("PRI_min", STRATEGY_INVOCATION_KPI_DEFAULTS["PRI_min"])),
        "HAL_max": float(kpi_targets.get("HAL_max", STRATEGY_INVOCATION_KPI_DEFAULTS["HAL_max"])),
        "AUD_min": float(kpi_targets.get("AUD_min", STRATEGY_INVOCATION_KPI_DEFAULTS["AUD_min"])),
    }

    def enrich(payload: Dict[str, Any]) -> Dict[str, Any]:
        example = deepcopy(payload)
        example["agent_id"] = agent_id
        example["event_type"] = "strategy_invocation"
        example["schema_version"] = schema_version
        example["kpi_targets"] = dict(kpi_payload)
        flags = example.get("safety_flags")
        if not isinstance(flags, Mapping):
            flags = {"disinfo_filtered": True, "persona_debate_used": False}
        else:
            normalized_flags = dict(flags)
            normalized_flags.setdefault("disinfo_filtered", True)
            flags = normalized_flags
        example["safety_flags"] = flags
        if example.get("hitl_applied") is False:
            example["hitl_actor"] = None
        if not example.get("correlation_id"):
            example["correlation_id"] = f"corr_{example.get('run_id', 'strategy')}"
        return example

    return [
        enrich(
            {
                "run_id": "run_hce_drac_internal_advisory",
                "workflow_id": "wf_drac_internal_advisory",
                "workflow_run_id": "wf_run_drac_internal_advisory_01",
                "correlation_id": "corr_drac_internal_advisory_2025Q4",
                "timestamp": "2025-09-12T18:52:28Z",
                "task_id": "task_internal_advisory",
                "footprint_id": "fp_drac_internal_advisory_001",
                "scenario_id": "drac_internal_advisory",
                "strategy_profile": "analysis_medium_internal",
                "strategy_chain": [
                    "ReActPattern_v1",
                    "TariffCompare_v1",
                    "HallucinationCheck_v1",
                ],
                "task_type": "internal_pricing_review",
                "risk_tier": "medium",
                "token_count": None,
                "tokens_input": None,
                "tokens_output": None,
                "latency_ms": None,
                "pri_score": None,
                "hal_score": None,
                "aud_score": None,
                "hitl_required": True,
                "hitl_applied": False,
                "hitl_actor": None,
                "status": "hitl_pending",
                "safety_flags": {
                    "disinfo_filtered": True,
                    "persona_debate_used": False,
                },
            }
        ),
        enrich(
            {
                "run_id": "run_hce_drac_pricing_case_2025Q4",
                "workflow_id": "wf_drac_pricing_case",
                "workflow_run_id": "wf_run_drac_pricing_case_07",
                "correlation_id": "corr_drac_pricing_case_2025Q4",
                "timestamp": "2025-10-14T15:11:00Z",
                "task_id": "task_pricing_case_summary",
                "footprint_id": "fp_drac_pricing_case_002",
                "scenario_id": "drac_pricing_case",
                "strategy_profile": "analysis_medium_internal",
                "strategy_chain": [
                    "CAPEConversation_v1",
                    "TariffCompare_v1",
                    "CertaintyReporter_v1",
                    "HallucinationCheck_v1",
                ],
                "task_type": "pricing_update",
                "risk_tier": "medium",
                "token_count": 1520,
                "tokens_input": 8800,
                "tokens_output": 1620,
                "latency_ms": 5800,
                "pri_score": 0.96,
                "hal_score": 0.009,
                "aud_score": 0.94,
                "hitl_required": False,
                "hitl_applied": False,
                "hitl_actor": None,
                "status": "completed",
                "safety_flags": {
                    "disinfo_filtered": True,
                    "persona_debate_used": False,
                    "pii_redaction": "selectors_only",
                },
            }
        ),
        enrich(
            {
                "run_id": "run_hce_drac_board_brief_v1",
                "workflow_id": "wf_drac_board_brief",
                "workflow_run_id": "wf_run_drac_board_brief_02",
                "correlation_id": "corr_drac_board_brief_2025",
                "timestamp": "2025-10-20T09:41:00Z",
                "task_id": "task_board_brief",
                "footprint_id": "fp_drac_board_brief_003",
                "scenario_id": "drac_board_brief",
                "strategy_profile": "analysis_medium_internal",
                "strategy_chain": [
                    "PlannerScaffold_v1",
                    "ReActPattern_v1",
                    "DisinfoFilter_v1",
                    "HallucinationCheck_v1",
                    "CertaintyReporter_v1",
                ],
                "task_type": "board_brief",
                "risk_tier": "medium",
                "token_count": 1710,
                "tokens_input": 9100,
                "tokens_output": 1280,
                "latency_ms": 6400,
                "pri_score": 0.97,
                "hal_score": 0.008,
                "aud_score": 0.95,
                "hitl_required": True,
                "hitl_applied": True,
                "hitl_actor": "regulatory_counsel",
                "status": "completed",
                "safety_flags": {
                    "disinfo_filtered": True,
                    "persona_debate_used": True,
                },
            }
        ),
    ]


def _dedupe_preserve_order(values: List[Any]) -> List[Any]:
    seen: set[Any] = set()
    result: List[Any] = []
    for value in values:
        key = value
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def _get(mapping: Mapping[str, Any] | None, key: str, default: Any = None) -> Any:
    if not isinstance(mapping, Mapping):
        return default
    return mapping.get(key, default)


def _dget(mapping: Mapping[str, Any] | None, path: str, default: Any = None) -> Any:
    cur: Any = mapping
    for part in path.split("."):
        if not isinstance(cur, Mapping):
            return default
        cur = cur.get(part)
    return cur if cur is not None else default


def _profile_sections(
    profile: Mapping[str, Any]
) -> Tuple[dict, dict, dict, dict, dict, dict, dict]:
    identity = _get(profile, "identity", {}) or {}
    role_profile = _get(profile, "role_profile", {}) or {}
    sector_profile = _get(profile, "sector_profile", {}) or {}
    capabilities_tools = _get(profile, "capabilities_tools", {}) or {}
    memory = _get(profile, "memory", {}) or {}
    governance_eval = _get(profile, "governance_eval", {}) or {}
    preferences = _get(profile, "preferences", {}) or {}
    return (
        identity,
        role_profile,
        sector_profile,
        capabilities_tools,
        memory,
        governance_eval,
        preferences,
    )


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
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    packs: Dict[str, Any] = {}

    def persist(filename: str, payload: Dict[str, Any]) -> None:
        packs[filename] = payload
        json_write(out_dir / filename, payload)


    (
        identity,
        role_profile,
        sector_profile,
        capabilities_tools,
        memory,
        governance_eval,
        preferences,
    ) = _profile_sections(profile)
    agent = _get(profile, "agent", {}) or {}
    agent_id = str(_get(identity, "agent_id", ""))
    naics = _naics_summary(profile)
    eff_autonomy = compute_effective_autonomy(
        preferences, _get(profile, "routing_defaults", {})
    )
    files = list(CANONICAL_PACK_FILENAMES)
    kpi_targets = kpi_targets_sync()
    governance_data = governance_eval or {}
    governance_pii_flags = normalise_pii_flags(
        _get(governance_data, "pii_flags", []) or []
    )
    privacy_pii_flags = normalise_pii_flags(
        _dget(profile, "privacy.pii_flags", governance_pii_flags) or []
    )
    owners_from_identity = (
        list((_get(identity, "owners") or [])) if isinstance(identity, Mapping) else []
    )

    # 01 README + Directory Map
    p01 = _attach_agent_meta(
        _pack_template("01_README+Directory-Map_v2.json"), agent_id
    )
    p01["version"] = p01.get("version", 2)
    p01["files"] = files
    persist("01_README+Directory-Map_v2.json", p01)

    # 02 Global Instructions
    p02 = _attach_agent_meta(
        _pack_template("02_Global-Instructions_v2.json"), agent_id
    )
    p02.setdefault("context", {})["naics"] = naics
    p02["effective_autonomy"] = eff_autonomy
    refs = p02.setdefault("references", {})
    refs["reasoning_schema"] = "16_Reasoning-Footprints_Schema_v1.json"
    refs["memory_schema"] = "08_Memory-Schema_v2.json"
    p02["store_raw_cot"] = False
    p02.setdefault("safety", {})["regulatory"] = list(
        _get(sector_profile, "regulatory", []) or []
    )
    p02.setdefault("observability", {})["kpi_targets"] = kpi_targets
    persist("02_Global-Instructions_v2.json", p02)

    # 03 Operating Rules
    hg = human_gate_actions(
        _get(_get(capabilities_tools, "human_gate", {}), "actions", [])
    )
    base_roles = list(_dget(profile, "governance.rbac.roles", []) or [])
    if owners_from_identity:
        defaults = _owners()
        triad_cf = {d.casefold() for d in defaults}
        seen: set[str] = set()
        uniq: List[str] = []
        for owner in owners_from_identity:
            s = str(owner).strip()
            k = s.casefold()
            if s and k not in seen:
                seen.add(k)
                uniq.append(s)
        extra = sorted(
            [o for o in uniq if o.casefold() not in triad_cf],
            key=str.casefold,
        )
        roles_out = list(defaults) + extra
    else:
        roles_out = base_roles
    p03 = _attach_agent_meta(
        _pack_template("03_Operating-Rules_v2.json"), agent_id
    )
    p03.setdefault("human_gate", {})["actions"] = hg
    p03.setdefault("escalation", {}).setdefault("human_gate", {})["actions"] = hg
    p03.setdefault("rbac", {})["roles"] = roles_out
    gates = p03.setdefault("gates", {})
    gates["activation"] = [
        f"PRI>={KPI_TARGETS.get('PRI_min')}",
        f"HAL<={KPI_TARGETS.get('HAL_max')}",
        f"AUD>={KPI_TARGETS.get('AUD_min')}",
    ]
    gates["effective_autonomy"] = eff_autonomy
    packs["03_Operating-Rules_v2.json"] = p03
    (out_dir / "03_Operating-Rules_v2.json").write_text(
        json.dumps(p03, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    # 04 Governance + Risk Register
    classification_default = _get(
        governance_data,
        "classification_default",
        "confidential",
    )
    p04 = _attach_agent_meta(
        _pack_template("04_Governance+Risk-Register_v2.json"), agent_id
    )
    p04["classification_default"] = classification_default
    p04["risk_register_tags"] = list(
        _get(governance_data, "risk_register_tags", []) or []
    )
    p04["pii_flags"] = governance_pii_flags
    p04["regulators"] = list(_get(sector_profile, "regulatory", []) or [])
    policy = p04.setdefault("policy", {})
    policy["classification_default"] = _dget(
        profile,
        "governance.policy.classification_default",
        classification_default,
    )
    policy["no_impersonation"] = bool(_get(identity, "no_impersonation", True))
    p04.setdefault("frameworks", {})["regulators"] = list(
        _dget(
            profile,
            "compliance.regulators",
            _get(sector_profile, "regulatory", []),
        )
        or []
    )
    persist("04_Governance+Risk-Register_v2.json", p04)

    # 05 Safety + Privacy
    p05 = _attach_agent_meta(
        _pack_template("05_Safety+Privacy_Guardrails_v2.json"), agent_id
    )
    p05["no_impersonation"] = bool(_get(identity, "no_impersonation", True))
    p05["pii_mask_on_ingest"] = True
    p05.setdefault("privacy_policies", {})["pii_flags"] = privacy_pii_flags
    persist("05_Safety+Privacy_Guardrails_v2.json", p05)

    # 06 Role Recipes Index
    primary_role_code = str(
        _dget(profile, "role.primary.code", _get(role_profile, "archetype", ""))
    )
    p06 = _attach_agent_meta(
        _pack_template("06_Role-Recipes_Index_v2.json"), agent_id
    )
    p06["role_recipe_ref"] = str(_get(role_profile, "role_recipe_ref", ""))
    p06["objectives"] = list(_get(role_profile, "objectives", []) or [])
    p06["role_title"] = str(_get(role_profile, "role_title", ""))
    p06["archetype"] = str(_get(role_profile, "archetype", ""))
    mapping = p06.setdefault("mapping", {})
    mapping["primary_role_code"] = primary_role_code
    mapping["agent_id"] = agent_id
    p06["roles_index"] = [
        {
            "code": str(_get(role_profile, "archetype", "")) or primary_role_code,
            "title": str(
                _dget(profile, "role.title", _get(role_profile, "role_title", ""))
            ),
            "objectives": list(_get(role_profile, "objectives", []) or []),
        }
    ]
    persist("06_Role-Recipes_Index_v2.json", p06)

    # 07 Subagent Role Recipes
    flags = preferences_flow_flags(_get(preferences, "collaboration_mode", ""))
    p07 = _attach_agent_meta(
        _pack_template("07_Subagent_Role-Recipes_v2.json"), agent_id
    )
    p07["planner_builder_evaluator"] = flags["planner_builder_evaluator"]
    p07["auto_plan_step"] = flags["auto_plan_step"]
    persist("07_Subagent_Role-Recipes_v2.json", p07)

    # 08 Memory Schema
    retention_days = min(int(_get(memory, "retention_days", 180) or 180), 180)
    p08 = _attach_agent_meta(
        _pack_template("08_Memory-Schema_v2.json"), agent_id
    )
    episodic = p08.setdefault("retention", {}).setdefault("episodic", {})
    episodic["retention_days"] = retention_days
    p08["memory_scopes"] = list(_get(memory, "memory_scopes", []) or [])
    p08["initial_memory_packs"] = list(
        _get(memory, "initial_memory_packs", []) or []
    )
    p08["optional_packs"] = list(_get(memory, "optional_packs", []) or [])
    p08["scopes"] = list(
        _dget(profile, "memory.scopes", _get(memory, "memory_scopes", [])) or []
    )
    packs_block = p08.setdefault("packs", {})
    packs_block["initial"] = list(
        _dget(
            profile,
            "memory.packs.initial",
            _get(memory, "initial_memory_packs", []),
        )
        or []
    )
    packs_block["optional"] = list(
        _dget(profile, "memory.packs.optional", _get(memory, "optional_packs", []))
        or []
    )
    p08.setdefault("sync", {})["allowed_sources"] = list(
        _dget(
            profile,
            "memory.sync.allowed_sources",
            _get(memory, "data_sources", []),
        )
        or []
    )
    persist("08_Memory-Schema_v2.json", p08)

    # 09 Agent Manifests Catalog
    owners = owners_from_identity or _owners()
    selected_role_title = str(_dget(profile, "role.role_title", "")).strip()
    if not selected_role_title:
        selected_role_title = str(_get(role_profile, "role_title", "")).strip()
    if not selected_role_title:
        selected_role_title = str(_dget(profile, "role.title", "")).strip()
    p09 = _attach_agent_meta(
        _pack_template("09_Agent-Manifests_Catalog_v2.json"), agent_id
    )
    p09["owners"] = owners
    summary = p09.setdefault("summary", {})
    summary["sector"] = _get(sector_profile, "sector", "")
    summary["region"] = list(_get(sector_profile, "region", []) or [])
    summary["languages"] = list(_get(sector_profile, "languages", []) or [])
    summary["regulators"] = list(_get(sector_profile, "regulatory", []) or [])
    summary["naics"] = naics
    canonical_agents = _canonical_agent_cards()
    existing_agents = p09.get("agents")
    agent_entry: Dict[str, Any] = {}
    trailing_agents: List[Dict[str, Any]] = []
    normalized_agent_id = str(agent_id).strip()
    if canonical_agents:
        matched = False
        for card in canonical_agents:
            if not isinstance(card, Mapping):
                continue
            copy = deepcopy(card)
            canonical_id = str(copy.get("agent_id", "")).strip()
            if not matched and normalized_agent_id and canonical_id == normalized_agent_id:
                agent_entry = copy
                matched = True
                continue
            trailing_agents.append(copy)
        if not agent_entry:
            template_card = canonical_agents[0]
            if isinstance(template_card, Mapping):
                agent_entry = deepcopy(template_card)
    elif isinstance(existing_agents, list) and existing_agents:
        template_card = next(
            (card for card in existing_agents if isinstance(card, Mapping)), {}
        )
        if isinstance(template_card, Mapping):
            agent_entry = deepcopy(template_card)
        trailing_agents = [
            deepcopy(card)
            for card in existing_agents
            if isinstance(card, Mapping) and card is not template_card
        ]
    if not agent_entry:
        agent_entry = {}
    p09["agents"] = [agent_entry] + trailing_agents
    agent_entry["display_name"] = str(
        _get(identity, "display_name", _get(agent, "name", ""))
    )
    agent_entry["owners"] = owners
    agent_entry["agent_id"] = agent_id
    agent_entry["role_title"] = selected_role_title
    strategy_defaults = _agent_strategy_defaults()
    for card in p09.get("agents", []):
        if not isinstance(card, dict):
            continue
        defaults = strategy_defaults.get(str(card.get("agent_id", ""))) or {}
        card["strategy_profile"] = (
            defaults.get("strategy_profile") or card.get("strategy_profile") or "analysis_medium_internal"
        )
        card["risk_tier"] = (
            defaults.get("risk_tier") or card.get("risk_tier") or "medium"
        )
    persist("09_Agent-Manifests_Catalog_v2.json", p09)

    # 10 Prompt Pack
    p10 = _attach_agent_meta(_pack_template("10_Prompt-Pack_v2.json"), agent_id)
    persist("10_Prompt-Pack_v2.json", p10)

    # 11 Workflow Pack
    p11 = _attach_agent_meta(_pack_template("11_Workflow-Pack_v2.json"), agent_id)
    workflow_gates = p11.setdefault("gates", {})
    workflow_gates["kpi_targets"] = kpi_targets
    workflow_gates["effective_autonomy"] = eff_autonomy
    persona_defaults = {
        "persona": _dget(
            profile, "persona.mbti", _get(agent, "persona", "")
        ),
        "tone": _dget(profile, "persona.tone", ""),
    }
    p11.setdefault("defaults", {}).update(
        {k: v for k, v in persona_defaults.items() if v}
    )
    persist("11_Workflow-Pack_v2.json", p11)

    # 12 Tool + Data Registry
    connectors: List[Dict[str, Any]] = []
    for connector in _get(capabilities_tools, "tool_connectors", []) or []:
        if not isinstance(connector, Mapping):
            continue
        name = str(connector.get("name", "")).strip()
        enabled = bool(connector.get("enabled", False))
        scopes = list(connector.get("scopes", []) or [])
        secret = str(connector.get("secret_ref", "") or "").strip()
        if name == "clm":
            name = "sharepoint"
        if name == "dms":
            name = "gdrive"
        if not name:
            name = "placeholder"
            enabled = False
            scopes = ["read"]
        if not scopes:
            scopes = ["read"]
        if not secret or "SET_ME" in secret.upper():
            secret = f"secret_manager:{name}"
        connectors.append(
            {
                "name": name,
                "enabled": enabled,
                "scopes": scopes,
                "secret_ref": secret,
            }
        )
    p12 = _attach_agent_meta(
        _pack_template("12_Tool+Data-Registry_v2.json"), agent_id
    )
    p12["connectors"] = connectors
    persist("12_Tool+Data-Registry_v2.json", p12)

    # 13 Knowledge Graph + RAG Config
    p13 = _attach_agent_meta(
        _pack_template("13_Knowledge-Graph+RAG_Config_v2.json"), agent_id
    )
    p13["indexes"] = list(_get(memory, "data_sources", []) or [])
    persist("13_Knowledge-Graph+RAG_Config_v2.json", p13)

    # 14 KPI + Evaluation Framework
    p14 = _attach_agent_meta(
        _pack_template("14_KPI+Evaluation-Framework_v2.json"), agent_id
    )
    p14["targets"] = kpi_targets
    refs = p14.setdefault("refs", {})
    eval_sets = refs.get("evaluation_sets")
    eval_path = "evaluation_sets/strategy_eval_suite_v1.json"
    if isinstance(eval_sets, list):
        if eval_path not in eval_sets:
            eval_sets.append(eval_path)
    else:
        refs["evaluation_sets"] = [eval_path]
    persist("14_KPI+Evaluation-Framework_v2.json", p14)

    # 15 Observability + Telemetry
    p15 = _attach_agent_meta(
        _pack_template("15_Observability+Telemetry_Spec_v2.json"), agent_id
    )
    events_value = p15.get("events")
    if not isinstance(events_value, list):
        events_value = []
        p15["events"] = events_value
    event_names: set[str] = set()
    for item in events_value:
        if isinstance(item, str):
            event_names.add(item)
        elif isinstance(item, Mapping):
            name = item.get("name")
            if isinstance(name, str):
                event_names.add(name)
    for required_event in REQUIRED_EVENTS:
        if required_event not in event_names:
            events_value.append({"name": required_event})
    alerts_value = p15.get("alerts")
    if isinstance(alerts_value, dict):
        bucket = alerts_value.setdefault("baseline_alerts", [])
        if not isinstance(bucket, list):
            bucket = list(bucket)  # defensive if someone used tuple
            alerts_value["baseline_alerts"] = bucket
        alert_names = {str(item) for item in bucket if isinstance(item, str)}
        for required_alert in REQUIRED_ALERTS:
            if required_alert not in alert_names:
                bucket.append(required_alert)
    else:
        if not isinstance(alerts_value, list):
            alerts_value = []
            p15["alerts"] = alerts_value
        alert_names = {str(item) for item in alerts_value if isinstance(item, str)}
        for required_alert in REQUIRED_ALERTS:
            if required_alert not in alert_names:
                alerts_value.append(required_alert)
    rate = _dget(profile, "telemetry.sampling.rate", None)
    if rate is not None:
        p15.setdefault("sampling", {})["rate"] = float(rate)
    sinks = _dget(profile, "telemetry.sinks", None)
    if isinstance(sinks, list):
        p15["sinks"] = list(sinks)
    strategy = _dget(profile, "telemetry.pii_redaction.strategy", None)
    if strategy:
        p15.setdefault("pii_redaction", {})["strategy"] = strategy
    p15["strategy_invocation"] = _strategy_invocation_block(agent_id)
    persist("15_Observability+Telemetry_Spec_v2.json", p15)

    # 16 Reasoning Footprints Schema
    p16 = _attach_agent_meta(
        _pack_template("16_Reasoning-Footprints_Schema_v1.json"), agent_id
    )
    p16["store_raw_cot"] = False
    persist("16_Reasoning-Footprints_Schema_v1.json", p16)

    # 17 Lifecycle Pack
    p17 = _attach_agent_meta(
        _pack_template("17_Lifecycle-Pack_v2.json"), agent_id
    )
    lifecycle_gates = p17.setdefault("gates", {})
    lifecycle_gates["kpi_targets"] = kpi_targets
    lifecycle_gates["activation"] = [
        f"PRI>={KPI_TARGETS.get('PRI_min')}",
        f"HAL<={KPI_TARGETS.get('HAL_max')}",
        f"AUD>={KPI_TARGETS.get('AUD_min')}",
    ]
    lifecycle_gates["effective_autonomy"] = eff_autonomy
    p17["stages"] = [str(_dget(profile, "lifecycle.stage", "dev"))]
    persist("17_Lifecycle-Pack_v2.json", p17)

    # 18 Reporting Pack
    p18 = _attach_agent_meta(
        _pack_template("18_Reporting-Pack_v2.json"), agent_id
    )
    persist("18_Reporting-Pack_v2.json", p18)

    # 19 SME-Domain Overlay
    p19 = _attach_agent_meta(
        _pack_template("19_Overlay-Pack_SME-Domain_v1.json"), agent_id
    )
    canonical_industry = str(_get(sector_profile, "canonical_industry", "")).strip()
    if not canonical_industry:
        canonical_industry = canonical_industry_from_naics(naics)
    display_industry = str(_get(sector_profile, "industry", "")).strip()
    industry_source = str(_get(sector_profile, "industry_source", "")).strip()
    if not display_industry:
        display_industry = canonical_industry
        industry_source = industry_source or "naics_lineage"
    else:
        industry_source = industry_source or "manual"
    p19.update(
        {
            "sector": _get(sector_profile, "sector", ""),
            "canonical_industry": canonical_industry,
            "industry": display_industry,
            "industry_source": industry_source,
            "region": list(_get(sector_profile, "region", []) or []),
            "regulators": list(_get(sector_profile, "regulatory", []) or []),
            "naics": naics,
            "refs": {
                "sector": _get(sector_profile, "sector", ""),
                "region": list(_get(sector_profile, "region", []) or []),
                "regulators": list(_get(sector_profile, "regulatory", []) or []),
            },
        }
    )
    sme_payload = write_sme_overlay(
        p19, out_dir / "19_Overlay-Pack_SME-Domain_v1.json"
    )
    packs["19_Overlay-Pack_SME-Domain_v1.json"] = sme_payload

    # 20 Enterprise Overlay
    p20 = _attach_agent_meta(
        _pack_template("20_Overlay-Pack_Enterprise_v1.json"), agent_id
    )
    persist("20_Overlay-Pack_Enterprise_v1.json", p20)

    # Ship evaluation set
    eval_src = EVALUATION_SETS_DIR / EVAL_SET_FILENAME
    if eval_src.is_file():
        eval_dest_dir = out_dir / "evaluation_sets"
        eval_dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(eval_src, eval_dest_dir / EVAL_SET_FILENAME)

    # Contract scaffolder: enrich in 'full' mode after minimal writes
    try:
        mode = get_contract_mode()
    except Exception:
        mode = "preview"
    if mode == "full":
        enriched = enrich_packs(profile, packs)
        for fname, payload in enriched.items():
            packs[fname] = payload
            if fname == "03_Operating-Rules_v2.json":
                (out_dir / fname).write_text(
                    json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True)
                    + "\n",
                    encoding="utf-8",
                    newline="\n",
                )
            else:
                json_write(out_dir / fname, payload)

    schema_requirements = required_keys_map()
    for fname, required in schema_requirements.items():
        payload = packs.get(fname)
        if not isinstance(payload, dict):
            continue
        expected_keys = sorted(set(required))
        if payload.get("schema_keys") != expected_keys:
            payload["schema_keys"] = expected_keys
            if fname == "03_Operating-Rules_v2.json":
                (out_dir / fname).write_text(
                    json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True)
                    + "\n",
                    encoding="utf-8",
                    newline="\n",
                )
            else:
                json_write(out_dir / fname, payload)

    manifest = packs.get("09_Agent-Manifests_Catalog_v2.json")
    if isinstance(manifest, dict):
        manifest_path = out_dir / "09_Agent-Manifests_Catalog_v2.json"
        strategy_defaults = _agent_strategy_defaults()
        agents_list = manifest.get("agents", [])
        if isinstance(agents_list, list):
            target_entry = None
            for card in agents_list:
                if isinstance(card, dict) and card.get("agent_id") == agent_id:
                    target_entry = card
                    break
            if target_entry is None:
                template_card = agents_list[0] if agents_list else {}
                target_entry = deepcopy(template_card) if isinstance(template_card, Mapping) else {}
                target_entry["agent_id"] = agent_id
                target_entry["display_name"] = str(
                    _get(identity, "display_name", _get(agent, "name", ""))
                )
                target_entry["owners"] = owners
                target_entry["role_title"] = selected_role_title
                agents_list.insert(0, target_entry)
        updated = False
        if isinstance(agents_list, list):
            for card in agents_list:
                if not isinstance(card, dict):
                    continue
                defaults = strategy_defaults.get(str(card.get("agent_id", ""))) or {}
                strategy_value = (
                    card.get("strategy_profile")
                    or defaults.get("strategy_profile")
                    or "analysis_medium_internal"
                )
                risk_value = (
                    card.get("risk_tier")
                    or defaults.get("risk_tier")
                    or "medium"
                )
                if card.get("strategy_profile") != strategy_value:
                    card["strategy_profile"] = strategy_value
                    updated = True
                if card.get("risk_tier") != risk_value:
                    card["risk_tier"] = risk_value
                    updated = True
        if updated:
            json_write(manifest_path, manifest)

    return packs


def write_sme_overlay(payload: Mapping[str, Any], out_path: Path | str) -> Dict[str, Any]:
    """Persist the SME overlay ensuring canonical/industry/source fields are populated."""
    enriched: Dict[str, Any] = dict(payload or {})
    naics = enriched.get("naics", {}) or {}
    canonical = str(enriched.get("canonical_industry") or "").strip()
    if not canonical:
        canonical = canonical_industry_from_naics(naics)
        enriched["canonical_industry"] = canonical
    display = str(enriched.get("industry") or "").strip()
    if display:
        enriched["industry"] = display
        enriched["industry_source"] = enriched.get("industry_source") or "manual"
    else:
        enriched["industry"] = canonical
        enriched["industry_source"] = "naics_lineage"
    json_write(Path(out_path), enriched)
    return enriched


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
    (out_dir / "README.md").write_text(
        "\n".join(readme_lines) + "\n", encoding="utf-8", newline="\n"
    )

    # neo_agent_config.json (minimal)
    cfg = {
        "agent": {
            "id": str(_get(identity, "agent_id", "") or uuid.uuid4().hex[:8]),
            "display_name": str(
                _get(identity, "display_name", _get(agent, "name", ""))
                or "Unnamed Agent"
            ),
        },
    }
    json_write(out_dir / "neo_agent_config.json", cfg)

    # Packs
    packs = write_all_packs(profile, out_dir)
    # Persist _last_build.json pointer for SoT consumers
    try:
        from datetime import datetime
        import hashlib
        import io
        import json as _json
        import zipfile

        out_dir_path = Path(out_dir)
        identity = _get(profile, "identity", {}) or {}
        agent_meta = _get(profile, "agent", {}) or {}
        agent_id = str(
            identity.get("agent_id")
            or agent_meta.get("name")
            or out_dir_path.parent.name
            or "agent"
        ).strip()
        timestamp = out_dir_path.name or "latest"
        file_count = len(list(out_dir_path.glob("*.json"))) + len(
            list(out_dir_path.glob("*.md"))
        )
        schema_version = str(_get(profile, "schema_version") or "2.1.1")

        excluded_names = {"_last_build.json", ".DS_Store", "contract_report.json"}
        excluded_dirs = {"__pycache__", ".pytest_cache", ".git", "spec_preview"}
        rels: list[Path] = []
        for path in out_dir_path.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(out_dir_path)
            parts = rel.parts
            if any(part.startswith(".") for part in parts):
                continue
            if any(part in excluded_dirs for part in parts):
                continue
            if rel.name in excluded_names:
                continue
            rels.append(rel)
        rels = sorted(rels, key=lambda r: str(r).replace("\\", "/"))
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for rel in rels:
                data = (out_dir_path / rel).read_bytes()
                info = zipfile.ZipInfo(str(rel).replace("\\", "/"))
                info.date_time = (1980, 1, 1, 0, 0, 0)
                info.compress_type = zipfile.ZIP_DEFLATED
                zf.writestr(info, data)
        zip_hash = hashlib.sha256(buf.getvalue()).hexdigest()

        payload = {
            "schema_version": schema_version,
            "agent_id": agent_id,
            "outdir": str(out_dir_path.resolve()),
            "files": file_count,
            "ts": timestamp,
            "zip_hash": zip_hash,
            "status": "complete",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        build_id = payload.get("ts") or payload.get("timestamp")
        if build_id:
            payload["build_id"] = build_id
        commit_hint = _get(profile, "commit") or _get(profile, "build_commit") or None
        if commit_hint:
            payload["commit"] = str(commit_hint)

        try:
            out_root = out_dir_path.parents[1]
        except IndexError:
            out_root = out_dir_path.parent
        if out_root:
            out_root.mkdir(parents=True, exist_ok=True)
            (out_root / "_last_build.json").write_text(
                _json.dumps(payload, indent=2), encoding="utf-8"
            )
    except Exception:
        pass
    return packs
