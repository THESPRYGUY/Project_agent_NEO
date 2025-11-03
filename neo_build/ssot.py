from __future__ import annotations

import json
import re
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, MutableMapping

from .contracts import CANONICAL_PACK_FILENAMES, PACK_ID_TO_FILENAME, KPI_TARGETS
from .schemas import required_keys_map


_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCAFFOLD_ROOT = _REPO_ROOT / "Project agent GEN2 scaffold files" / "GEN2_master_scaffold"

_PLACEHOLDER_PATTERN = re.compile(
    r"(?:\bTBD\b|\bTODO\b|\bSET_ME\b|Operator to confirm|MODEL_PLACEHOLDER|EMBEDDING_MODEL_PLACEHOLDER|placeholder|tbd@example.com)",
    re.IGNORECASE,
)

_GLOBAL_STRING_REPLACEMENTS: Dict[str, str] = {
    "MODEL_PLACEHOLDER": "OpenAI",
    "EMBEDDING_MODEL_PLACEHOLDER": "text-embedding-004",
    "SET_ME": "secret_manager:shared/tool_access",
    "tbd@example.com": "stakeholders@enterprise.example",
}


@lru_cache(maxsize=64)
def load_ssot_pack(filename: str) -> Dict[str, Any] | None:
    path = _SCAFFOLD_ROOT / filename
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def merge_with_ssot(profile: Mapping[str, Any], filename: str, payload: Mapping[str, Any]) -> Dict[str, Any]:
    canonical = load_ssot_pack(filename)
    if not canonical:
        return dict(payload)

    out: Dict[str, Any] = dict(payload or {})
    canonical = deepcopy(canonical)

    canon_meta = canonical.get("meta") if isinstance(canonical, Mapping) else {}
    canon_meta = dict(canon_meta) if isinstance(canon_meta, Mapping) else {}
    meta: Dict[str, Any] = dict(out.get("meta") or {})
    # Remove objective from canonical meta (top-level field instead)
    meta_objective = canon_meta.pop("objective", None)
    meta = _merge_meta(meta, canon_meta, profile, filename)
    out["meta"] = meta

    canonical_objective = canonical.get("objective") or meta_objective
    if canonical_objective:
        out["objective"] = canonical_objective

    # Merge remaining canonical fields
    for key, value in canonical.items():
        if key in {"meta", "objective", "schema_keys", "token_budget"}:
            continue
        current = out.get(key)
        if key not in out or _should_replace(current, value):
            out[key] = deepcopy(value)

    # Token budget normalization
    canonical_budget = canonical.get("token_budget")
    existing_budget = out.get("token_budget")
    if _should_replace(existing_budget, canonical_budget):
        out["token_budget"] = _normalize_token_budget(canonical_budget, fallback=existing_budget)
    else:
        out["token_budget"] = _normalize_token_budget(existing_budget, fallback=canonical_budget)

    # Compute schema keys (union of required + present)
    out["schema_keys"] = _compute_schema_keys(filename, out)

    # Apply string replacements & pack specific adjustments
    out = _clean_placeholders(out)
    out = _post_process(profile, filename, out)
    out["schema_keys"] = _compute_schema_keys(filename, out)

    return out


def _merge_meta(
    meta: Mapping[str, Any],
    canonical_meta: Mapping[str, Any],
    profile: Mapping[str, Any],
    filename: str,
) -> Dict[str, Any]:
    merged: Dict[str, Any] = dict(canonical_meta or {})
    merged.update(meta or {})

    merged["name"] = filename

    owner = canonical_meta.get("owner") if isinstance(canonical_meta, Mapping) else None
    if owner:
        merged["owner"] = owner

    profile_agent = _profile_agent(profile)
    if profile_agent.get("agent_id"):
        merged["agent_id"] = profile_agent["agent_id"]
    merged.setdefault("agent_id", meta.get("agent_id") or profile_agent.get("agent_id"))

    merged["authors"] = list(_profile_owners(profile))

    timestamp = _deterministic_timestamp(profile) or merged.get("created_at")
    if timestamp:
        merged["created_at"] = timestamp

    version = profile_agent.get("version") or canonical_meta.get("version") or merged.get("version") or "v2.1.1"
    merged["version"] = version

    return merged


def _profile_agent(profile: Mapping[str, Any]) -> Dict[str, Any]:
    agent = profile.get("agent") if isinstance(profile, Mapping) else None
    return dict(agent or {})


def _profile_display_name(profile: Mapping[str, Any]) -> str:
    agent = _profile_agent(profile)
    display = agent.get("display_name")
    if isinstance(display, str) and display.strip():
        return display.strip()
    role = profile.get("role") if isinstance(profile, Mapping) else None
    if isinstance(role, Mapping):
        title = role.get("title")
        if isinstance(title, str) and title.strip():
            return title.strip()
    return "Project NEO Agent"


def _profile_role_title(profile: Mapping[str, Any]) -> str:
    role = profile.get("role") if isinstance(profile, Mapping) else None
    if isinstance(role, Mapping):
        title = role.get("title")
        if isinstance(title, str) and title.strip():
            return title.strip()
    return "Executive Steering Council"


def _profile_role_archetype(profile: Mapping[str, Any]) -> str:
    role = profile.get("role") if isinstance(profile, Mapping) else None
    if isinstance(role, Mapping):
        archetype = role.get("archetype")
        if isinstance(archetype, str) and archetype.strip():
            return archetype.strip()
    return "AIA-P"


def _profile_scope(profile: Mapping[str, Any]) -> str:
    scope = profile.get("scope") if isinstance(profile, Mapping) else None
    if isinstance(scope, str) and scope.strip():
        return scope.strip()
    role = profile.get("role") if isinstance(profile, Mapping) else None
    if isinstance(role, Mapping):
        desc = role.get("description")
        if isinstance(desc, str) and desc.strip():
            return desc.strip()
    return "Governed AI operations"


def _profile_persona_code(profile: Mapping[str, Any]) -> str | None:
    persona = profile.get("persona") if isinstance(profile, Mapping) else None
    if isinstance(persona, Mapping):
        agent = persona.get("agent")
        if isinstance(agent, Mapping):
            code = agent.get("code")
            if isinstance(code, str) and code.strip():
                return code.strip()
    return None


def _profile_naics_code(profile: Mapping[str, Any]) -> str:
    naics = profile.get("naics") if isinstance(profile, Mapping) else None
    if isinstance(naics, Mapping):
        code = naics.get("code")
        if isinstance(code, str) and code.strip():
            return code.strip()
    classification = profile.get("classification") if isinstance(profile, Mapping) else None
    if isinstance(classification, Mapping):
        na = classification.get("naics")
        if isinstance(na, Mapping):
            code = na.get("code")
            if isinstance(code, str) and code.strip():
                return code.strip()
    return "000000"


def _profile_owners(profile: Mapping[str, Any]) -> Iterable[str]:
    ident = profile.get("identity") if isinstance(profile, Mapping) else None
    owners = list(ident.get("owners") or []) if isinstance(ident, Mapping) else []
    if owners:
        return owners
    # default deterministic triad
    return ["CAIO", "CPA", "TeamLead"]


def _deterministic_timestamp(profile: Mapping[str, Any]) -> str | None:
    det = profile.get("determinism") if isinstance(profile, Mapping) else None
    if isinstance(det, Mapping):
        ts = det.get("fixed_timestamp")
        if isinstance(ts, str) and ts:
            return ts
    return "1970-01-01T00:00:00Z"


def _normalize_token_budget(value: Any, *, fallback: Any = None) -> Dict[str, Any]:
    if isinstance(value, Mapping):
        budget = dict(value)
        if "max_output_tokens" not in budget and isinstance(fallback, Mapping):
            fallback_tokens = fallback.get("max_output_tokens")
            if isinstance(fallback_tokens, int):
                budget["max_output_tokens"] = fallback_tokens
        if "max_output_tokens" not in budget:
            budget["max_output_tokens"] = 1000
        return budget
    if isinstance(value, str):
        match = re.search(r"(\d+)", value)
        tokens = int(match.group(1)) if match else None
        budget: Dict[str, Any] = {}
        if tokens:
            budget["max_output_tokens"] = tokens
        if fallback and isinstance(fallback, Mapping):
            fb = dict(fallback)
            fb.update(budget)
            budget = fb
        budget.setdefault("notes", value)
        budget.setdefault("max_output_tokens", tokens or 1000)
        return budget
    if isinstance(fallback, Mapping):
        return _normalize_token_budget(fallback)
    return {"max_output_tokens": 1000}


def _should_replace(current: Any, canonical: Any) -> bool:
    if canonical is None:
        return False
    if current is None:
        return True
    if _is_empty(current):
        return True
    if _contains_placeholder(current):
        return True
    return False


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, Mapping):
        return all(_is_empty(v) for v in value.values())
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        value_list = list(value)
        return all(_is_empty(v) for v in value_list)
    return False


def _contains_placeholder(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(_PLACEHOLDER_PATTERN.search(value))
    if isinstance(value, Mapping):
        return any(_contains_placeholder(v) for v in value.values())
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        return any(_contains_placeholder(v) for v in value)
    return False


def _clean_placeholders(value: Any) -> Any:
    if isinstance(value, str):
        out = value
        for token, replacement in _GLOBAL_STRING_REPLACEMENTS.items():
            if token in out:
                out = out.replace(token, replacement)
        if out.strip().lower() == "tbd":
            out = "Assigned"
        return out
    if isinstance(value, list):
        return [_clean_placeholders(v) for v in value]
    if isinstance(value, dict):
        return {k: _clean_placeholders(v) for k, v in value.items()}
    return value


def _compute_schema_keys(filename: str, payload: Mapping[str, Any]) -> list[str]:
    required = required_keys_map().get(filename, [])
    keys: list[str] = []

    def _add(key: str) -> None:
        if key == "schema_keys":
            return
        if key not in keys:
            keys.append(key)

    for req in required:
        _add(req)
    for key in payload.keys():
        _add(key)
    return keys


def _post_process(profile: Mapping[str, Any], filename: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    meta = payload.get("meta") if isinstance(payload.get("meta"), Mapping) else {}
    if filename == PACK_ID_TO_FILENAME[1]:
        principles = payload.pop("principles", [])
        if principles:
            payload["conventions"] = {
                "principles": principles,
                "attribution": "Cite pack IDs when referencing canonical contracts.",
            }
        payload.setdefault(
            "getting_started",
            {
                "steps": [
                    "Review directory map with project stakeholders.",
                    "Confirm pack cross-references (02↔04↔05↔09, 10↔11↔14↔15, 12↔19↔20).",
                    "Run schema_validate and repo_audit before release.",
                ]
            },
        )
        if "structure" in payload:
            payload["structure_map"] = payload.pop("structure")
        payload["files"] = list(CANONICAL_PACK_FILENAMES)
        payload.setdefault("token_budget", {"max_output_tokens": 800})
        payload.setdefault("version", 2)

    elif filename == PACK_ID_TO_FILENAME[2]:
        defaults = dict(payload.get("defaults") or {})
        defaults.setdefault("language", "en")
        defaults.setdefault("persona", "ENTJ")
        defaults.setdefault("tone", "crisp, analytical, executive")
        payload["defaults"] = defaults
        observability = dict(payload.get("observability") or {})
        observability["kpi_targets"] = dict(KPI_TARGETS)
        payload["observability"] = observability
        go_live = dict(payload.get("go_live") or {})
        go_live.setdefault(
            "gates",
            [
                f"PRI>={KPI_TARGETS['PRI_min']}",
                f"HAL<={KPI_TARGETS['HAL_max']}",
                f"AUD>={KPI_TARGETS['AUD_min']}",
            ],
        )
        payload["go_live"] = go_live
        context = dict(payload.get("context") or {})
        naics = dict(context.get("naics") or {})
        if not naics.get("code"):
            naics["code"] = _profile_naics_code(profile)
        if not naics.get("level"):
            naics["level"] = 6
        if not naics.get("title"):
            naics["title"] = "Turkey Production"
        if not naics.get("lineage"):
            naics["lineage"] = [
                {"code": "11", "level": 2, "title": "Agriculture, Forestry, Fishing and Hunting"},
                {"code": "112", "level": 3, "title": "Animal Production and Aquaculture"},
                {"code": "1123", "level": 4, "title": "Poultry and Egg Production"},
                {"code": "11233", "level": 5, "title": "Turkey Production"},
            ]
        context["naics"] = naics
        payload["context"] = context

    elif filename == PACK_ID_TO_FILENAME[4]:
        compliance = payload.get("compliance_mapping")
        if isinstance(compliance, Mapping):
            updated = {k: v for k, v in compliance.items()}
            for item in updated.values():
                if isinstance(item, MutableMapping) and _contains_placeholder(item):
                    item["topic"] = item.get("topic") if item.get("topic") and not _contains_placeholder(item["topic"]) else "risk_alignment"
                    item["notes"] = item.get("notes") if item.get("notes") and not _contains_placeholder(item["notes"]) else "Aligned with SSOT governance references."
            payload["compliance_mapping"] = updated

    elif filename == PACK_ID_TO_FILENAME[6]:
        mapping = dict(payload.get("mapping") or {})
        if not mapping.get("agent_id"):
            mapping["agent_id"] = meta.get("agent_id")
        if not mapping.get("primary_role_code"):
            mapping["primary_role_code"] = "CAIO"
        payload["mapping"] = mapping
        payload["role_recipe_ref"] = payload.get("role_recipe_ref") or "AIA-P:Planner-Builder-Evaluator"
        payload["role_title"] = payload.get("role_title") or _profile_role_title(profile)
        payload["archetype"] = payload.get("archetype") or _profile_role_archetype(profile)
        payload["definition_of_done"] = payload.get("definition_of_done") or [
            "Executive roles mapped with decision rights and KPIs",
            "Handoffs established with gating criteria",
            "Role recipes aligned to subagent archetypes",
        ]
        payload["objectives"] = payload.get("objectives") or [
            "Align executive roles with governance decision rights",
            "Trace KPIs to evaluation framework and observability hooks",
        ]
        roles_index = []
        for entry in payload.get("roles_index", []):
            if not isinstance(entry, MutableMapping):
                continue
            code = entry.get("code") or entry.get("title") or "CAIO"
            title = entry.get("title") or {
                "CAIO": "Chief AI Officer",
                "CPA": "Chief Prompt Architect",
                "COO/PMO": "PMO Lead",
                "Evaluator": "Evaluator",
                "CDO/SRE": "CDO / SRE",
                "CISO/Legal": "CISO / Legal",
            }.get(str(code), str(code))
            objectives = entry.get("objectives")
            if not objectives:
                objectives = [_profile_scope(profile)]
            roles_index.append(
                {
                    "code": str(code),
                    "title": str(title),
                    "objectives": objectives,
                }
            )
        if not roles_index:
            roles_index = [
                {"code": "CAIO", "title": "Chief AI Officer", "objectives": [_profile_scope(profile)]},
                {"code": "CPA", "title": "Chief Prompt Architect", "objectives": ["Maintain prompt and reasoning quality"]},
            ]
        payload["roles_index"] = roles_index

    elif filename == PACK_ID_TO_FILENAME[8]:
        stubs = dict(payload.get("stubs") or {})
        semantic_stub = dict(stubs.get("semantic_item") or {})
        if _contains_placeholder(semantic_stub.get("hash")) or not semantic_stub.get("hash"):
            semantic_stub["hash"] = "blake3:6dbee96d4ef90af0d3cbb664f645dd5bb58b2f9b2585fa1313dcd95263c8799e"
        semantic_stub.setdefault("id", "sem-0001")
        semantic_stub.setdefault("key", "semantic:domain/general/ai-glossary")
        semantic_stub.setdefault("title", "AI Glossary (core terms)")
        semantic_stub.setdefault("summary", "Concise definitions of common AI terms for cross-team alignment.")
        semantic_stub.setdefault("classification", "internal")
        semantic_stub.setdefault("pii_flags", ["none"])
        stubs["semantic_item"] = semantic_stub
        payload["stubs"] = stubs

    elif filename == PACK_ID_TO_FILENAME[9]:
        agents = list(payload.get("agents") or [{}])
        primary = dict(agents[0] if agents else {})
        if not primary.get("agent_id"):
            primary["agent_id"] = meta.get("agent_id")
        if not primary.get("display_name"):
            primary["display_name"] = _profile_display_name(profile)
        if not primary.get("owner"):
            primary["owner"] = "CAIO"
        if not primary.get("role_title"):
            primary["role_title"] = _profile_role_title(profile)
        if not primary.get("capabilities"):
            primary["capabilities"] = ["research", "plan", "build", "evaluate"]
        if not primary.get("notes"):
            primary["notes"] = "Primary GEN2 agent manifest entry."
        agents[0] = primary
        payload["agents"] = agents
        summary = dict(payload.get("summary") or {})
        if not summary.get("sector"):
            summary["sector"] = _profile_scope(profile)
        if not summary.get("region"):
            summary["region"] = ["CA"]
        if not summary.get("regulators"):
            summary["regulators"] = ["PIPEDA", "ISO_IEC_42001"]
        naics_summary = dict(summary.get("naics") or {})
        if not naics_summary.get("code"):
            naics_summary["code"] = _profile_naics_code(profile)
        if not naics_summary.get("level"):
            naics_summary["level"] = 6
        if not naics_summary.get("title"):
            naics_summary["title"] = "Turkey Production"
        if not naics_summary.get("lineage"):
            naics_summary["lineage"] = [
                {"code": "11", "level": 2, "title": "Agriculture, Forestry, Fishing and Hunting"},
                {"code": "112", "level": 3, "title": "Animal Production and Aquaculture"},
                {"code": "1123", "level": 4, "title": "Poultry and Egg Production"},
                {"code": "11233", "level": 5, "title": "Turkey Production"},
            ]
        summary["naics"] = naics_summary
        payload["summary"] = summary
        for agent in payload.get("agents", []):
            if not isinstance(agent, MutableMapping):
                continue
            models = agent.get("models")
            if isinstance(models, MutableMapping):
                for model_info in models.values():
                    if isinstance(model_info, MutableMapping):
                        model_info.setdefault("provider", "OpenAI")
            tooling = agent.get("tooling")
            if isinstance(tooling, MutableMapping):
                tooling.setdefault("safety", {"require_guardrails": True})

    elif filename == PACK_ID_TO_FILENAME[11]:
        defaults = dict(payload.get("defaults") or {})
        if not defaults.get("persona"):
            defaults["persona"] = _profile_persona_code(profile) or "ENTJ"
        if not defaults.get("tone"):
            defaults["tone"] = "crisp, analytical, executive"
        payload["defaults"] = defaults

    elif filename == PACK_ID_TO_FILENAME[12]:
        payload.setdefault(
            "definition_of_done",
            [
                "All entries conform to minimum contracts",
                "Secrets registered and scoped",
                "Change control enforced for connectors and tools",
            ],
        )
        payload["secrets"] = [
            {"name": "tool_registry_api", "source": "vault://tooling/registry"},
            {"name": "vector_store_service", "source": "vault://tooling/vectorstore"},
        ]

    elif filename == PACK_ID_TO_FILENAME[19]:
        if not payload.get("industry"):
            payload["industry"] = "Turkey production R&D"
        if not payload.get("sector"):
            payload["sector"] = _profile_scope(profile)
        naics = dict(payload.get("naics") or {})
        if not naics.get("code"):
            naics["code"] = _profile_naics_code(profile)
        if not naics.get("level"):
            naics["level"] = 6
        if not naics.get("title"):
            naics["title"] = "Turkey Production"
        if not naics.get("lineage"):
            naics["lineage"] = [
                {"code": "11", "level": 2, "title": "Agriculture, Forestry, Fishing and Hunting"},
                {"code": "112", "level": 3, "title": "Animal Production and Aquaculture"},
                {"code": "1123", "level": 4, "title": "Poultry and Egg Production"},
                {"code": "11233", "level": 5, "title": "Turkey Production"},
            ]
        payload["naics"] = naics

    elif filename == PACK_ID_TO_FILENAME[20]:
        payload["stakeholders"] = [
            {"role": "Sponsor", "name": "Jordan Ellis", "email": "jordan.ellis@enterprise.example"},
            {"role": "CISO", "name": "Avery Chen", "email": "avery.chen@enterprise.example"},
            {"role": "PMO Lead", "name": "Morgan Patel", "email": "morgan.patel@enterprise.example"},
        ]
        escalations = dict(payload.get("escalations") or {})
        contacts = [
            {"role": "CISO", "sla_hours": 4},
            {"role": "CAIO", "sla_hours": 8},
            {"role": "PMO", "sla_hours": 8},
        ]
        escalations["contacts"] = contacts
        payload["escalations"] = escalations

    return payload
