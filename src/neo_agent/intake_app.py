"""HTTP server for the Project NEO agent intake experience."""

from __future__ import annotations

import json
import re
from pathlib import Path
from string import Template
from typing import Any, Dict, Iterable, List, Mapping
from urllib.parse import parse_qs

from wsgiref.simple_server import make_server

from .linkedin import scrape_linkedin_profile
from .logging import get_logger
from .spec_generator import generate_agent_specs
from .server.api import ApiRouter

LOGGER = get_logger("intake")


DOMAINS = [
    "Finance",
    "Healthcare",
    "Manufacturing",
    "Technology",
    "Retail",
    "Marketing",
    "Operations",
    "Customer Support",
    "Legal",
    "Human Resources",
]

ROLES = [
    "Enterprise Analyst",
    "Automation Engineer",
    "Knowledge Manager",
    "Strategy Consultant",
    "Data Scientist",
    "Project Manager",
]

TOOLSETS = [
    "Workflow Orchestration",
    "Data Analysis",
    "Reporting",
    "Process Mining",
    "Risk Assessment",
    "Research",
    "Communication",
    "Quality Assurance",
]

COMMUNICATION_STYLES = ["Formal", "Conversational", "Concise", "Storytelling"]
COLLABORATION_MODES = ["Solo", "Pair", "Cross-Functional", "Advisory"]

TRAIT_KEYS = (
    "detail_oriented",
    "collaborative",
    "proactive",
    "strategic",
    "empathetic",
    "experimental",
    "efficient",
)

TRAIT_PROVENANCE = {"manual", "mbti_suggested", "mbti_suggested+edited"}
TRAITS_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "traits.schema.json"
MBTI_PATTERN = re.compile(r"^[ei][ns][tf][jp]$")

PREFERENCES_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2] / "schemas" / "preferences.schema.json"
)
TOOLSETS_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "toolsets.schema.json"
try:
    with PREFERENCES_SCHEMA_PATH.open("r", encoding="utf-8") as handle:
        _PREFERENCES_SCHEMA = json.load(handle)
except FileNotFoundError:  # pragma: no cover - defensive guard for packaging
    _PREFERENCES_SCHEMA = {}

COMM_STYLE_OPTIONS = set(
    _PREFERENCES_SCHEMA.get("properties", {})
    .get("comm_style", {})
    .get("enum", ["formal", "conversational", "executive_brief", "technical_deep"])
)
COLLAB_MODE_OPTIONS = set(
    _PREFERENCES_SCHEMA.get("properties", {})
    .get("collab_mode", {})
    .get("enum", ["solo", "cross_functional", "pair_build", "review_first"])
)
PREFERENCES_PROVENANCE = set(
    _PREFERENCES_SCHEMA.get("properties", {})
    .get("provenance", {})
    .get("enum", ["manual", "preset_applied", "preset_edited"])
)

TOOLSET_CAPABILITIES = {
    "reasoning_planning",
    "data_rag",
    "orchestration",
    "analysis_modeling",
    "communication_reporting",
    "risk_safety_compliance",
    "quality_evaluation",
}

TOOLSET_CAPABILITY_ORDER = [
    "reasoning_planning",
    "data_rag",
    "orchestration",
    "analysis_modeling",
    "communication_reporting",
    "risk_safety_compliance",
    "quality_evaluation",
]

TOOLSET_CONNECTOR_SCOPES: Dict[str, set[str]] = {
    "email": {"read/*", "send:internal", "send:external"},
    "calendar": {"read/*", "write:holds", "write:events"},
    "make": {"run:scenario", "manage:scenario"},
    "notion": {"read:db/*", "write:tasks", "write:pages"},
    "gdrive": {"read:folders/*", "write:reports", "write:any"},
    "sharepoint": {"read:policies/*", "write:reports", "write:libraries"},
    "github": {"repo:read", "repo:write", "repo:admin"},
}

TOOLSET_DEFAULT_CONNECTOR_SCOPES = {
    "email": {"read/*", "send:internal"},
    "calendar": {"read/*", "write:holds"},
    "make": {"run:scenario"},
    "notion": {"read:db/*", "write:tasks"},
    "gdrive": {"read:folders/*", "write:reports"},
    "sharepoint": {"read:policies/*", "write:reports"},
    "github": {"repo:read", "repo:write"},
}

TOOLSET_STORAGE_OPTIONS = {"kv", "vector", "none"}
TOOLSET_RETENTION_OPTIONS = {"default_365", "episodic_180"}
TOOLSET_RESIDENCY_OPTIONS = {"auto", "ca", "us", "eu"}
TOOLSET_ENV_OPTIONS = {"dev", "staging", "prod"}

LEGACY_TOOLSET_MAP: Dict[str, list[str]] = {
    "Workflow Orchestration": ["orchestration"],
    "Data Analysis": ["analysis_modeling", "communication_reporting"],
    "Process Mining": ["analysis_modeling", "communication_reporting"],
    "Reporting": ["analysis_modeling", "communication_reporting"],
    "Research": ["analysis_modeling", "communication_reporting"],
    "Communication": ["communication_reporting"],
    "Risk Assessment": ["risk_safety_compliance", "quality_evaluation"],
    "Quality Assurance": ["risk_safety_compliance", "quality_evaluation"],
}


def _split_csv(value: str | None) -> List[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _option_list(options: Iterable[str]) -> str:
    return "\n".join(f'<option value="{option}">{option}</option>' for option in options)


def _checkboxes(name: str, options: Iterable[str]) -> str:
    chunks = []
    for option in options:
        chunks.append(
            f'<label><input type="checkbox" name="{name}" value="{option}"> {option}</label>'
        )
    return "\n".join(chunks)


def _default_traits() -> Dict[str, Any]:
    return {
        "traits": {key: 50 for key in TRAIT_KEYS},
        "provenance": "manual",
        "version": "1.0",
    }


def _default_preferences() -> Dict[str, Any]:
    knobs, _ = _compute_preference_knobs(50, 50, 50, "formal", "solo")
    return {
        "autonomy": 50,
        "confidence": 50,
        "collaboration": 50,
        "comm_style": "formal",
        "collab_mode": "solo",
        "prefs_knobs": knobs,
        "provenance": "manual",
        "version": "1.0",
    }


def _default_toolsets_payload() -> Dict[str, Any]:
    return {
        "capabilities": ["reasoning_planning"],
        "connectors": [],
        "governance": {
            "storage": "kv",
            "redaction": ["mask_pii", "never_store_secrets"],
            "retention": "default_365",
            "data_residency": "auto",
        },
        "ops": {
            "env": "staging",
            "dry_run": True,
            "latency_slo_ms": 1200,
            "cost_budget_usd": 5.0,
        },
    }


def _normalize_mbti(candidate: str | None) -> str | None:
    if not candidate:
        return None
    normalized = candidate.strip().lower()
    return normalized if MBTI_PATTERN.fullmatch(normalized) else None


def _clamp_slider(value: Any, name: str) -> int:
    if not isinstance(value, int):
        raise ValueError(f"Preference '{name}' must be an integer.")
    if value < 0 or value > 100:
        raise ValueError(f"Preference '{name}' must be between 0 and 100.")
    if value % 5 != 0:
        raise ValueError(f"Preference '{name}' must use increments of 5.")
    return value


def _normalize_capabilities(values: Iterable[Any]) -> list[str]:
    seen: list[str] = []
    for value in values:
        if isinstance(value, str) and value in TOOLSET_CAPABILITIES and value not in seen:
            seen.append(value)
    return seen


def _sanitize_connector(payload: Mapping[str, Any]) -> Dict[str, Any]:
    name = payload.get("name")
    if not isinstance(name, str) or name not in TOOLSET_CONNECTOR_SCOPES:
        raise ValueError("Connector name is invalid.")
    scopes = payload.get("scopes", [])
    if not isinstance(scopes, (list, tuple, set)):
        raise ValueError("Connector scopes must be a list.")
    allowed = TOOLSET_CONNECTOR_SCOPES[name]
    selected = [scope for scope in scopes if isinstance(scope, str) and scope in allowed]
    if not selected:
        selected = list(TOOLSET_DEFAULT_CONNECTOR_SCOPES[name])
    instances_payload = payload.get("instances", [])
    instances: list[Dict[str, str]] = []
    if isinstance(instances_payload, (list, tuple, set)):
        for item in instances_payload:
            if not isinstance(item, Mapping):
                continue
            label = str(item.get("label", "")).strip()
            secret = str(item.get("secret_ref", "")).strip()
            if not label or not secret.startswith("vault://"):
                continue
            instances.append({"label": label, "secret_ref": secret})
    connector: Dict[str, Any] = {"name": name, "scopes": selected}
    if instances:
        connector["instances"] = instances
    return connector


def _validate_toolsets_payload(payload: Any) -> Dict[str, Any]:
    if payload is None:
        return _default_toolsets_payload()
    if not isinstance(payload, Mapping):
        raise ValueError("Toolsets payload must be an object.")

    capabilities = _normalize_capabilities(payload.get("capabilities", []))
    if not capabilities:
        raise ValueError("At least one capability must be selected.")

    connectors_payload = payload.get("connectors", [])
    connectors: list[Dict[str, Any]] = []
    if isinstance(connectors_payload, Iterable):
        for item in connectors_payload:
            if isinstance(item, Mapping):
                try:
                    connectors.append(_sanitize_connector(item))
                except ValueError:
                    continue

    governance_payload = payload.get("governance", {})
    if not isinstance(governance_payload, Mapping):
        raise ValueError("Governance payload must be an object.")
    storage = governance_payload.get("storage", "kv")
    retention = governance_payload.get("retention", "default_365")
    residency = governance_payload.get("data_residency", "auto")
    if storage not in TOOLSET_STORAGE_OPTIONS:
        raise ValueError("Storage selection is invalid.")
    if retention not in TOOLSET_RETENTION_OPTIONS:
        raise ValueError("Retention selection is invalid.")
    if residency not in TOOLSET_RESIDENCY_OPTIONS:
        raise ValueError("Data residency selection is invalid.")

    ops_payload = payload.get("ops", {})
    if not isinstance(ops_payload, Mapping):
        raise ValueError("Ops payload must be an object.")
    env = ops_payload.get("env", "staging")
    if env not in TOOLSET_ENV_OPTIONS:
        raise ValueError("Ops environment is invalid.")
    dry_run = bool(ops_payload.get("dry_run", True))
    latency = ops_payload.get("latency_slo_ms", 1200)
    cost = ops_payload.get("cost_budget_usd", 5.0)
    try:
        latency_value = float(latency)
    except (TypeError, ValueError):
        raise ValueError("Latency SLO must be numeric.")
    try:
        cost_value = float(cost)
    except (TypeError, ValueError):
        raise ValueError("Cost budget must be numeric.")
    if latency_value < 0:
        raise ValueError("Latency SLO must be zero or greater.")
    if cost_value < 0:
        raise ValueError("Cost budget must be zero or greater.")
    if env == "prod" and dry_run:
        dry_run = False

    normalized = {
        "capabilities": [
            capability
            for capability in TOOLSET_CAPABILITY_ORDER
            if capability in capabilities
        ],
        "connectors": connectors,
        "governance": {
            "storage": storage,
            "redaction": ["mask_pii", "never_store_secrets"],
            "retention": retention,
            "data_residency": residency,
        },
        "ops": {
            "env": env,
            "dry_run": dry_run,
            "latency_slo_ms": latency_value,
            "cost_budget_usd": cost_value,
        },
    }
    return normalized


def _migrate_legacy_toolsets(selected: Iterable[str], custom: Iterable[str]) -> tuple[Dict[str, Any], list[str]]:
    payload = _default_toolsets_payload()
    capabilities: set[str] = set()
    for name in selected:
        capabilities.update(LEGACY_TOOLSET_MAP.get(name, []))
    if not capabilities:
        capabilities.add("reasoning_planning")
    payload["capabilities"] = [
        capability
        for capability in TOOLSET_CAPABILITY_ORDER
        if capability in capabilities
    ]
    legacy_tags = [tag.strip() for tag in custom if tag.strip()]
    return payload, legacy_tags
def _compute_preference_knobs(
    autonomy: int,
    confidence: int,
    collaboration: int,
    comm_style: str,
    collab_mode: str,
) -> tuple[Dict[str, Any], bool]:
    if autonomy >= 80:
        confirmation_gate = "none"
    elif autonomy <= 40:
        confirmation_gate = "strict"
    else:
        confirmation_gate = "light"

    if confidence >= 80:
        rec_depth = "deep"
    elif confidence <= 40:
        rec_depth = "short"
    else:
        rec_depth = "balanced"

    if collaboration >= 80:
        handoff_freq = "high"
    elif collaboration <= 40:
        handoff_freq = "low"
    else:
        handoff_freq = "medium"

    communication = {
        "word_cap": None,
        "bulletize_default": False,
        "include_call_to_action": False,
        "allow_extended_rationale": False,
        "include_code_snippets": False,
    }

    if comm_style == "executive_brief":
        communication.update(
            {
                "word_cap": 200,
                "bulletize_default": True,
                "include_call_to_action": True,
            }
        )
    elif comm_style == "technical_deep":
        communication.update(
            {
                "allow_extended_rationale": True,
                "include_code_snippets": True,
            }
        )

    collaboration_knobs = {
        "require_pair_confirmation": collab_mode == "pair_build",
        "require_review_handoff": collab_mode == "review_first",
    }

    conflict = autonomy <= 30 and confirmation_gate == "none"
    if conflict:
        confirmation_gate = "light"

    knobs = {
        "confirmation_gate": confirmation_gate,
        "rec_depth": rec_depth,
        "handoff_freq": handoff_freq,
        "communication": communication,
        "collaboration": collaboration_knobs,
    }

    return knobs, conflict


def _validate_preferences_payload(payload: Any) -> Dict[str, Any]:
    if payload is None:
        return _default_preferences()
    if not isinstance(payload, Mapping):
        raise ValueError("Preferences payload must be an object.")

    autonomy = _clamp_slider(payload.get("autonomy", 50), "autonomy")
    confidence = _clamp_slider(payload.get("confidence", 50), "confidence")
    collaboration = _clamp_slider(payload.get("collaboration", 50), "collaboration")

    comm_style = str(payload.get("comm_style", "formal"))
    if comm_style not in COMM_STYLE_OPTIONS:
        raise ValueError("Communication style must be a supported option.")

    collab_mode = str(payload.get("collab_mode", "solo"))
    if collab_mode not in COLLAB_MODE_OPTIONS:
        raise ValueError("Collaboration mode must be a supported option.")

    provenance = payload.get("provenance", "manual")
    if provenance not in PREFERENCES_PROVENANCE:
        raise ValueError("Preferences provenance is invalid.")

    knobs, conflict = _compute_preference_knobs(
        autonomy, confidence, collaboration, comm_style, collab_mode
    )

    normalized: Dict[str, Any] = {
        "autonomy": autonomy,
        "confidence": confidence,
        "collaboration": collaboration,
        "comm_style": comm_style,
        "collab_mode": collab_mode,
        "prefs_knobs": knobs,
        "provenance": provenance,
        "version": "1.0",
    }

    if conflict:
        normalized["_conflict_blocked"] = True

    return normalized


def _validate_traits_payload(payload: Any) -> Dict[str, Any]:
    if payload is None:
        return _default_traits()
    if not isinstance(payload, Mapping):
        raise ValueError("Traits payload must be a JSON object.")

    traits = payload.get("traits")
    provenance = payload.get("provenance", "manual")
    version = payload.get("version", "1.0")
    mbti = _normalize_mbti(payload.get("mbti"))

    if version != "1.0":
        raise ValueError("Traits payload version must be '1.0'.")
    if provenance not in TRAIT_PROVENANCE:
        raise ValueError("Traits provenance is invalid.")
    if not isinstance(traits, Mapping):
        raise ValueError("Traits field must be an object.")

    normalized: Dict[str, int] = {}
    for key in TRAIT_KEYS:
        value = traits.get(key)
        if not isinstance(value, int) or value < 0 or value > 100:
            raise ValueError(f"Trait '{key}' must be an integer between 0 and 100.")
        normalized[key] = value

    normalized_payload: Dict[str, Any] = {
        "traits": normalized,
        "provenance": provenance,
        "version": "1.0",
    }
    if mbti:
        normalized_payload["mbti"] = mbti
    return normalized_payload


def _notice(message: str | None) -> str:
    if not message:
        return ""
    return f'<div class="notice"><p>{message}</p></div>'


def _summary_block(profile: Mapping[str, Any] | None, profile_path: str, spec_path: str) -> str:
    if not profile:
        return ""
    encoded = json.dumps(profile, indent=2)
    return (
        "<div class=\"summary\">"
        f"<h2>Generated Agent Profile</h2><p>Profile saved to <code>{profile_path}</code></p>"
        f"<p>Specs generated in <code>{spec_path}</code></p><pre>{encoded}</pre></div>"
    )


FORM_TEMPLATE = Template(
    """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Project NEO Agent Intake</title>
    <style>
      body { font-family: Arial, sans-serif; margin: 2rem; background-color: #f5f7fb; }
      h1 { color: #1f3c88; }
      form { background: white; padding: 2rem; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
      fieldset { border: 1px solid #dbe2ef; margin-bottom: 1.5rem; padding: 1rem; border-radius: 8px; }
      legend { font-weight: bold; color: #112d4e; }
      label { display: block; margin-top: 0.5rem; }
      select, input[type=text], input[type=url], textarea { width: 100%; padding: 0.5rem; border-radius: 6px; border: 1px solid #ccc; }
      .options { display: flex; flex-wrap: wrap; gap: 0.5rem; }
      .options label { display: flex; align-items: center; gap: 0.3rem; background: #eef2fb; padding: 0.4rem 0.6rem; border-radius: 6px; cursor: pointer; }
      .slider-value { font-weight: bold; margin-left: 0.5rem; }
      button { background: #1f3c88; color: white; padding: 0.8rem 1.4rem; border: none; border-radius: 8px; cursor: pointer; font-size: 1rem; }
      .summary { margin-top: 2rem; }
      .summary pre { background: #0b1b36; color: #e3f6f5; padding: 1rem; border-radius: 8px; }
      .notice { margin-bottom: 1rem; color: #205072; }
    </style>
    <script>
      function updateSliderValue(id, value) {
        document.getElementById(id).innerText = value;
      }
    </script>
  </head>
  <body>
    <h1>Project NEO Agent Intake</h1>
    $notice
    <form method="post" action="/">
      <fieldset>
        <legend>Agent Profile</legend>
        <label>Agent Name
          <input type="text" name="agent_name" placeholder="e.g., Atlas Analyst" required>
        </label>
        <label>Version
          <input type="text" name="agent_version" value="1.0.0">
        </label>
        <label>Persona Tagline
          <input type="text" name="agent_persona" placeholder="Adaptive enterprise analyst">
        </label>
        <label>Primary Domain
          <select name="domain" required>
            $domain_options
          </select>
        </label>
        <label>Primary Role
          <select name="role" required>
            $role_options
          </select>
        </label>
      </fieldset>

      <fieldset>
        <legend>Toolsets</legend>
        <div class="options">
          $toolset_checkboxes
        </div>
        <label>Custom Toolsets (comma separated)
          <input type="text" name="custom_toolsets" placeholder="e.g., Knowledge Graphing, Scenario Planning">
        </label>
        <label>Toolsets Payload (JSON)
          <textarea name="toolsets_payload" rows="4" placeholder='{"capabilities":["reasoning_planning"],"connectors":[],"governance":{"storage":"kv","redaction":["mask_pii","never_store_secrets"],"retention":"default_365","data_residency":"auto"},"ops":{"env":"staging","dry_run":true,"latency_slo_ms":1200,"cost_budget_usd":5.0}}'></textarea>
        </label>
      </fieldset>

      <fieldset>
        <legend>Preferences</legend>
        <label>Autonomy Level <span class="slider-value" id="autonomy_value">50</span>
          <input type="range" min="0" max="100" value="50" name="autonomy" oninput="updateSliderValue('autonomy_value', this.value)">
        </label>
        <label>Confidence Level <span class="slider-value" id="confidence_value">50</span>
          <input type="range" min="0" max="100" value="50" name="confidence" oninput="updateSliderValue('confidence_value', this.value)">
        </label>
        <label>Collaboration Level <span class="slider-value" id="collaboration_value">50</span>
          <input type="range" min="0" max="100" value="50" name="collaboration" oninput="updateSliderValue('collaboration_value', this.value)">
        </label>
        <label>Communication Style
          <select name="communication_style">
            $communication_options
          </select>
        </label>
        <label>Collaboration Mode
          <select name="collaboration_mode">
            $collaboration_options
          </select>
        </label>
        <label>Traits Payload (JSON)
          <textarea name="traits_payload" rows="4" placeholder='{"traits": {"strategic": 70, ...}, "provenance": "manual", "version": "1.0"}'></textarea>
        </label>
      </fieldset>

      <fieldset>
        <legend>LinkedIn</legend>
        <label>Profile URL
          <input type="url" name="linkedin_url" placeholder="https://www.linkedin.com/in/example">
        </label>
      </fieldset>

      <fieldset>
        <legend>Custom Notes</legend>
        <label>Engagement Notes
          <textarea name="notes" rows="4" placeholder="Outline constraints, knowledge packs, or workflow context."></textarea>
        </label>
      </fieldset>

      <button type="submit">Generate Agent Profile</button>
    </form>
    $summary
  </body>
</html>
"""
)


class IntakeApplication:
    """Minimal WSGI application serving the intake workflow."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or Path(__file__).resolve().parents[1]
        self.profile_path = self.base_dir / "agent_profile.json"
        self.spec_dir = self.base_dir / "generated_specs"
        self.traits_schema_path = TRAITS_SCHEMA_PATH
        self._traits_schema = self._load_traits_schema()
        self.repo_output = self.base_dir / "generated_repo"
        self.api_router = ApiRouter(output_root=self.repo_output)

    def _load_traits_schema(self) -> Mapping[str, Any]:
        try:
            with self.traits_schema_path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except FileNotFoundError:
            LOGGER.warning("Traits schema not found at %s", self.traits_schema_path)
            return {}

    # Rendering helpers -------------------------------------------------
    def render_form(
        self,
        *,
        message: str | None = None,
        profile: Mapping[str, Any] | None = None,
    ) -> str:
        return FORM_TEMPLATE.substitute(
            notice=_notice(message),
            summary=_summary_block(profile, str(self.profile_path), str(self.spec_dir)),
            domain_options=_option_list(DOMAINS),
            role_options=_option_list(ROLES),
            toolset_checkboxes=_checkboxes("toolsets", TOOLSETS),
            communication_options=_option_list(COMMUNICATION_STYLES),
            collaboration_options=_option_list(COLLABORATION_MODES),
        )

    def _extract_traits(self, data: Mapping[str, List[str]]) -> Dict[str, Any]:
        payload = data.get("traits_payload", [])
        raw = payload[0].strip() if payload else ""
        if not raw:
            return _default_traits()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive branch
            raise ValueError("Traits payload must be valid JSON.") from exc
        return _validate_traits_payload(parsed)

    def _extract_preferences(self, data: Mapping[str, List[str]]) -> Dict[str, Any]:
        payload = data.get("preferences_payload", [])
        raw = payload[0].strip() if payload else ""
        if not raw:
            return _default_preferences()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive branch
            raise ValueError("Preferences payload must be valid JSON.") from exc
        return _validate_preferences_payload(parsed)

    def _extract_toolsets(self, data: Mapping[str, List[str]]) -> tuple[Dict[str, Any], list[str]]:
        payload = data.get("toolsets_payload", [])
        raw = payload[0].strip() if payload else ""
        if raw:
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as exc:  # pragma: no cover - defensive branch
                raise ValueError("Toolsets payload must be valid JSON.") from exc
            normalized = _validate_toolsets_payload(parsed)
            return normalized, []

        selected = list(data.get("toolsets", []))
        custom = data.get("custom_toolsets", [])
        custom_text = custom[0] if custom else ""
        migrated, legacy_tags = _migrate_legacy_toolsets(selected, _split_csv(custom_text))
        return migrated, legacy_tags

    def _build_profile(
        self,
        data: Mapping[str, List[str]],
        linkedin: Mapping[str, Any],
        traits_envelope: Mapping[str, Any],
        preferences_envelope: Mapping[str, Any],
        toolsets_envelope: Mapping[str, Any],
        legacy_toolset_tags: list[str],
    ) -> Dict[str, Any]:
        def _get(name: str, default: str = "") -> str:
            values = data.get(name, [])
            return values[0] if values else default

        def _getlist(name: str) -> List[str]:
            return list(data.get(name, []))

        preferences_payload = dict(preferences_envelope)
        conflict_blocked = bool(preferences_payload.pop("_conflict_blocked", False))

        toolsets_payload = json.loads(json.dumps(toolsets_envelope))

        profile: Dict[str, Any] = {
            "agent": {
                "name": _get("agent_name", "Custom Project NEO Agent"),
                "version": _get("agent_version", "1.0.0"),
                "persona": _get("agent_persona", ""),
                "domain": _get("domain", ""),
                "role": _get("role", ""),
            },
            "toolsets": toolsets_payload,
            "preferences": preferences_payload,
            "traits": traits_envelope,
            "notes": _get("notes", ""),
            "linkedin": linkedin,
            "persona": {},
            "request_envelope": {
                "persona": {},
                "traits": traits_envelope,
                "preferences": preferences_payload,
                "toolsets": toolsets_payload,
            },
        }

        profile["toolsets_meta"] = {
            "legacy_selected": _getlist("toolsets"),
            "legacy_tags": legacy_toolset_tags,
        }

        if (
            "orchestration" in toolsets_payload.get("capabilities", [])
            and not toolsets_payload.get("connectors")
        ):
            profile.setdefault("warnings", [])
            profile["warnings"].append("Orchestration enabled without connector scopes.")

        if conflict_blocked:
            profile.setdefault("audit", {})["preferences_conflict_blocked"] = True

        mbti = traits_envelope.get("mbti")
        if mbti:
            profile["persona"]["mbti"] = mbti
            profile["request_envelope"]["persona"]["mbti"] = mbti

        if linkedin:
            derived_tools = linkedin.get("skills", [])
            if derived_tools:
                tags = profile.setdefault("toolsets_meta", {}).setdefault("legacy_tags", [])
                for tag in derived_tools:
                    normalized = tag.strip()
                    if normalized and normalized not in tags:
                        tags.append(normalized)

            derived_roles = linkedin.get("roles", [])
            if derived_roles and not profile["agent"].get("role"):
                profile["agent"]["role"] = derived_roles[0].title()

        return profile

    # WSGI interface ----------------------------------------------------
    def wsgi_app(self, environ: Mapping[str, Any], start_response):
        method = environ.get("REQUEST_METHOD", "GET").upper()
        path = environ.get("PATH_INFO", "/")

        if path.startswith("/api/"):
            try:
                length = int(environ.get("CONTENT_LENGTH", "0"))
            except ValueError:
                length = 0
            body = environ.get("wsgi.input").read(length) if length > 0 else b""
            status, headers, payload = self.api_router.dispatch(path, method, body)
            start_response(status, headers)
            return [payload]

        if method == "POST":
            try:
                length = int(environ.get("CONTENT_LENGTH", "0"))
            except ValueError:
                length = 0
            body = environ.get("wsgi.input").read(length) if length > 0 else b""
            data = parse_qs(body.decode("utf-8"))
            try:
                traits_envelope = self._extract_traits(data)
                preferences_envelope = self._extract_preferences(data)
                toolsets_envelope, legacy_toolset_tags = self._extract_toolsets(data)
            except ValueError as exc:
                response_body = self.render_form(message=str(exc)).encode("utf-8")
                status = "400 Bad Request"
                headers = [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(response_body)))]
                start_response(status, headers)
                return [response_body]

            linkedin_url = data.get("linkedin_url", [""])[0].strip()
            linkedin_data = scrape_linkedin_profile(linkedin_url)
            profile = self._build_profile(
                data,
                linkedin_data,
                traits_envelope,
                preferences_envelope,
                toolsets_envelope,
                legacy_toolset_tags,
            )

            with self.profile_path.open("w", encoding="utf-8") as handle:
                json.dump(profile, handle, indent=2)

            generate_agent_specs(profile, self.spec_dir)
            LOGGER.info("Generated profile at %s", self.profile_path)

            response_body = self.render_form(
                message="Agent profile generated successfully.",
                profile=profile,
            ).encode("utf-8")
            status = "200 OK"
        else:
            response_body = self.render_form().encode("utf-8")
            status = "200 OK"

        headers = [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(response_body)))]
        start_response(status, headers)
        return [response_body]

    # Convenience launcher ----------------------------------------------
    def serve(self, host: str = "127.0.0.1", port: int = 5000) -> None:
        server = make_server(host, port, self.wsgi_app)
        LOGGER.info("Serving intake app on http://%s:%s", host, port)
        server.serve_forever()


def create_app(base_dir: Path | None = None) -> IntakeApplication:
    """Factory used by tests and CLI tooling."""

    return IntakeApplication(base_dir=base_dir)


if __name__ == "__main__":  # pragma: no cover - manual execution helper
    create_app().serve()
