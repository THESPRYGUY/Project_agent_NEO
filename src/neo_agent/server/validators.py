"""Schema loading and validation helpers for agent profile builds."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_DIR = PROJECT_ROOT / "schemas"


@dataclass(slots=True)
class ValidationIssue:
    path: str
    message: str
    code: str

    def to_dict(self) -> Dict[str, str]:
        return {"path": self.path, "msg": self.message, "code": self.code}


_MB_TI_PATTERN = re.compile(r"^[ei][ns][tf][jp]$", re.IGNORECASE)
_ALLOWED_TOP_LEVEL = {
    "Strategic Functions",
    "Sector Domains",
    "Technical Domains",
    "Support Domains",
}
_SECTOR_SUBDOMAIN_EXEMPT = "Multi-Sector SME Overlay"
_TRAIT_KEYS = {
    "detail_oriented",
    "collaborative",
    "proactive",
    "strategic",
    "empathetic",
    "experimental",
    "efficient",
}
_CAPABILITIES = {
    "reasoning_planning",
    "data_rag",
    "orchestration",
    "analysis_modeling",
    "communication_reporting",
    "risk_safety_compliance",
    "quality_evaluation",
}
_CONNECTOR_SCOPES: Dict[str, set[str]] = {
    "email": {"read/*", "send:internal", "send:external"},
    "calendar": {"read/*", "write:holds", "write:events"},
    "make": {"run:scenario", "manage:scenario"},
    "notion": {"read:db/*", "write:tasks", "write:pages"},
    "gdrive": {"read:folders/*", "write:reports", "write:any"},
    "sharepoint": {"read:policies/*", "write:reports", "write:libraries"},
    "github": {"repo:read", "repo:write", "repo:admin"},
}
_GOV_STORAGE = {"kv", "vector", "none"}
_GOV_RETENTION = {"default_365", "episodic_180"}
_GOV_RESIDENCY = {"auto", "ca", "us", "eu"}
_OPS_ENV = {"dev", "staging", "prod"}
_COMM_STYLE = {
    "formal",
    "conversational",
    "executive_brief",
    "technical_deep",
}
_COLLAB_MODE = {"solo", "cross_functional", "pair_build", "review_first"}
_PREV_PROVENANCE = {"manual", "preset_applied", "preset_edited"}
_TRAIT_PROVENANCE = {"manual", "mbti_suggested", "mbti_suggested+edited"}


def _load_schema(name: str) -> Dict[str, Any]:
    path = SCHEMA_DIR / name
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_profile_schema() -> Dict[str, Any]:
    return _load_schema("profile.schema.json")


def load_build_options_schema() -> Dict[str, Any]:
    return _load_schema("build_options.schema.json")


def _normalize_tags(tags: Iterable[Any]) -> List[str]:
    normalized: List[str] = []
    for value in tags:
        if not isinstance(value, str):
            continue
        candidate = value.strip().lower().replace(" ", "-")
        candidate = re.sub(r"[^a-z0-9\-]", "", candidate)
        if candidate and candidate not in normalized:
            normalized.append(candidate)
    return normalized


def _validate_naics(node: Mapping[str, Any], path: str) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    required = {"code", "title", "level", "version", "path"}
    if not required.issubset(node.keys()):
        issues.append(ValidationIssue(path, "NAICS node missing required fields.", "E_SCHEMA_NAICS_MISSING"))
        return issues
    level = node.get("level")
    if level not in {2, 3, 4, 5, 6}:
        issues.append(ValidationIssue(path + ".level", "NAICS level must be between 2 and 6.", "E_SCHEMA_NAICS_LEVEL"))
    version = node.get("version")
    if version != "NAICS 2022 v1.0":
        issues.append(ValidationIssue(path + ".version", "NAICS version must be 'NAICS 2022 v1.0'.", "E_SCHEMA_NAICS_VERSION"))
    code = node.get("code")
    if not isinstance(code, str) or not code.isdigit():
        issues.append(ValidationIssue(path + ".code", "NAICS code must be numeric string.", "E_SCHEMA_NAICS_CODE"))
    path_list = node.get("path")
    if not isinstance(path_list, list) or not path_list:
        issues.append(ValidationIssue(path + ".path", "NAICS path must be non-empty list.", "E_SCHEMA_NAICS_PATH"))
    return issues


def validate_profile(profile: Mapping[str, Any] | None) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not isinstance(profile, Mapping):
        return [ValidationIssue("$", "Profile payload must be an object.", "E_SCHEMA_INVALID_PROFILE")]

    persona = profile.get("persona", {})
    if not isinstance(persona, Mapping):
        issues.append(ValidationIssue("$.persona", "Persona must be an object.", "E_SCHEMA_PERSONA"))
    else:
        name = persona.get("name", "").strip() if isinstance(persona.get("name"), str) else ""
        if not name:
            issues.append(ValidationIssue("$.persona.name", "Persona name required.", "E_SCHEMA_PERSONA_NAME"))
        mbti = persona.get("mbti")
        if mbti and not _MB_TI_PATTERN.fullmatch(str(mbti)):
            issues.append(ValidationIssue("$.persona.mbti", "MBTI must match canonical pattern.", "E_SCHEMA_PERSONA_MBTI"))

    domain = profile.get("domain")
    if not isinstance(domain, Mapping):
        issues.append(ValidationIssue("$.domain", "Domain must be an object.", "E_SCHEMA_DOMAIN_TYPE"))
    else:
        top_level = domain.get("topLevel")
        if top_level not in _ALLOWED_TOP_LEVEL:
            issues.append(ValidationIssue("$.domain.topLevel", "Top level domain invalid.", "E_SCHEMA_DOMAIN_TOP"))
        subdomain = domain.get("subdomain")
        if not isinstance(subdomain, str) or not subdomain:
            issues.append(ValidationIssue("$.domain.subdomain", "Subdomain required.", "E_SCHEMA_DOMAIN_SUB"))
        tags = domain.get("tags", [])
        if not isinstance(tags, Iterable):
            issues.append(ValidationIssue("$.domain.tags", "Tags must be iterable.", "E_SCHEMA_DOMAIN_TAGS"))
        else:
            tags_list = list(tags)
            normalized = _normalize_tags(tags_list)
            if len(normalized) != len(tags_list) or normalized != tags_list:
                issues.append(ValidationIssue("$.domain.tags", "Tags must be kebab-case unique strings.", "E_SCHEMA_DOMAIN_TAGS_NORMALIZED"))
        if top_level == "Sector Domains" and subdomain != _SECTOR_SUBDOMAIN_EXEMPT:
            naics = domain.get("naics")
            if not isinstance(naics, Mapping):
                issues.append(ValidationIssue("$.domain.naics", "NAICS selection required for sector domain.", "E_SCHEMA_NAICS_REQUIRED"))
            else:
                issues.extend(_validate_naics(naics, "$.domain.naics"))

    toolsets = profile.get("toolsets")
    if not isinstance(toolsets, Mapping):
        issues.append(ValidationIssue("$.toolsets", "Toolsets must be an object.", "E_SCHEMA_TOOLSETS"))
    else:
        capabilities = toolsets.get("capabilities", [])
        if not isinstance(capabilities, list) or not capabilities:
            issues.append(ValidationIssue("$.toolsets.capabilities", "At least one capability required.", "E_SCHEMA_TOOLSETS_CAPS"))
        else:
            for cap in capabilities:
                if cap not in _CAPABILITIES:
                    issues.append(ValidationIssue("$.toolsets.capabilities", f"Unknown capability: {cap}", "E_SCHEMA_TOOLSETS_CAPS"))
        connectors = toolsets.get("connectors", [])
        if isinstance(connectors, list):
            for idx, connector in enumerate(connectors):
                if not isinstance(connector, Mapping):
                    issues.append(ValidationIssue(f"$.toolsets.connectors[{idx}]", "Connector must be object.", "E_SCHEMA_CONNECTOR_TYPE"))
                    continue
                name = connector.get("name")
                if name not in _CONNECTOR_SCOPES:
                    issues.append(ValidationIssue(f"$.toolsets.connectors[{idx}].name", "Connector name invalid.", "E_SCHEMA_CONNECTOR_NAME"))
                    continue
                scopes = connector.get("scopes", [])
                if not isinstance(scopes, list) or not scopes:
                    issues.append(ValidationIssue(f"$.toolsets.connectors[{idx}].scopes", "Connector scopes required.", "E_SCHEMA_CONNECTOR_SCOPES"))
                else:
                    for scope in scopes:
                        if scope not in _CONNECTOR_SCOPES[name]:
                            issues.append(ValidationIssue(f"$.toolsets.connectors[{idx}].scopes", f"Invalid scope: {scope}", "E_SCHEMA_CONNECTOR_SCOPES"))
        governance = toolsets.get("governance", {})
        if governance:
            storage = governance.get("storage")
            if storage not in _GOV_STORAGE:
                issues.append(ValidationIssue("$.toolsets.governance.storage", "Invalid storage option.", "E_SCHEMA_GOV_STORAGE"))
            redaction = governance.get("redaction", [])
            if redaction != ["mask_pii", "never_store_secrets"]:
                issues.append(ValidationIssue("$.toolsets.governance.redaction", "Redaction must include mandatory flags.", "E_SCHEMA_GOV_REDACTION"))
            retention = governance.get("retention")
            if retention not in _GOV_RETENTION:
                issues.append(ValidationIssue("$.toolsets.governance.retention", "Invalid retention value.", "E_SCHEMA_GOV_RETENTION"))
            residency = governance.get("data_residency")
            if residency not in _GOV_RESIDENCY:
                issues.append(ValidationIssue("$.toolsets.governance.data_residency", "Invalid data residency value.", "E_SCHEMA_GOV_RESIDENCY"))
        ops = toolsets.get("ops", {})
        if ops:
            env = ops.get("env")
            if env not in _OPS_ENV:
                issues.append(ValidationIssue("$.toolsets.ops.env", "Invalid ops environment.", "E_SCHEMA_OPS_ENV"))
            latency = ops.get("latency_slo_ms")
            cost = ops.get("cost_budget_usd")
            if not isinstance(latency, (int, float)) or latency < 0:
                issues.append(ValidationIssue("$.toolsets.ops.latency_slo_ms", "Latency must be >= 0.", "E_SCHEMA_OPS_LATENCY"))
            if not isinstance(cost, (int, float)) or cost < 0:
                issues.append(ValidationIssue("$.toolsets.ops.cost_budget_usd", "Cost budget must be >= 0.", "E_SCHEMA_OPS_COST"))

    traits = profile.get("traits")
    if not isinstance(traits, Mapping):
        issues.append(ValidationIssue("$.traits", "Traits envelope required.", "E_SCHEMA_TRAITS"))
    else:
        provenance = traits.get("provenance")
        if provenance not in _TRAIT_PROVENANCE:
            issues.append(ValidationIssue("$.traits.provenance", "Traits provenance invalid.", "E_SCHEMA_TRAITS_PROVENANCE"))
        payload = traits.get("traits")
        if not isinstance(payload, Mapping):
            issues.append(ValidationIssue("$.traits.traits", "Traits map required.", "E_SCHEMA_TRAITS_VALUES"))
        else:
            for key in _TRAIT_KEYS:
                value = payload.get(key)
                if not isinstance(value, int) or value < 0 or value > 100:
                    issues.append(ValidationIssue(f"$.traits.traits.{key}", "Trait must be integer 0..100.", "E_SCHEMA_TRAITS_RANGE"))

    preferences = profile.get("preferences")
    if not isinstance(preferences, Mapping):
        issues.append(ValidationIssue("$.preferences", "Preferences payload required.", "E_SCHEMA_PREFS"))
    else:
        for field in ("autonomy", "confidence", "collaboration"):
            value = preferences.get(field)
            if not isinstance(value, int) or value < 0 or value > 100 or value % 5 != 0:
                issues.append(ValidationIssue(f"$.preferences.{field}", "Preference sliders must be 0-100 in steps of 5.", "E_SCHEMA_PREFS_SLIDER"))
        if preferences.get("comm_style") not in _COMM_STYLE:
            issues.append(ValidationIssue("$.preferences.comm_style", "Invalid communication style.", "E_SCHEMA_PREFS_COMM"))
        if preferences.get("collab_mode") not in _COLLAB_MODE:
            issues.append(ValidationIssue("$.preferences.collab_mode", "Invalid collaboration mode.", "E_SCHEMA_PREFS_COLLAB"))
        provenance = preferences.get("provenance")
        if provenance not in _PREV_PROVENANCE:
            issues.append(ValidationIssue("$.preferences.provenance", "Preferences provenance invalid.", "E_SCHEMA_PREFS_PROVENANCE"))
        knobs = preferences.get("prefs_knobs")
        if not isinstance(knobs, Mapping):
            issues.append(ValidationIssue("$.preferences.prefs_knobs", "Derived knobs required.", "E_SCHEMA_PREFS_KNOBS"))

    return issues


def validate_build_options(options: Mapping[str, Any] | None) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not isinstance(options, Mapping):
        return [ValidationIssue("$", "Options payload must be an object.", "E_SCHEMA_INVALID_OPTIONS")]
    include_examples = options.get("include_examples")
    if include_examples not in {True, False}:
        issues.append(ValidationIssue("$.include_examples", "include_examples must be boolean.", "E_SCHEMA_OPTIONS_FLAG"))
    git_init = options.get("git_init")
    if git_init not in {True, False}:
        issues.append(ValidationIssue("$.git_init", "git_init must be boolean.", "E_SCHEMA_OPTIONS_FLAG"))
    zip_flag = options.get("zip")
    if zip_flag not in {True, False}:
        issues.append(ValidationIssue("$.zip", "zip must be boolean.", "E_SCHEMA_OPTIONS_FLAG"))
    overwrite = options.get("overwrite")
    if overwrite not in {"safe", "force", "abort"}:
        issues.append(ValidationIssue("$.overwrite", "overwrite policy invalid.", "E_SCHEMA_OPTIONS_OVERWRITE"))
    return issues
