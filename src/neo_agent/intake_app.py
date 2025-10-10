"""HTTP server for the Project NEO agent intake experience."""

from __future__ import annotations

import html
import json
import os
import time
import threading
from pathlib import Path
from string import Template
from typing import Any, Dict, Iterable, List, Mapping
from urllib.parse import parse_qs

from wsgiref.simple_server import make_server

from .linkedin import scrape_linkedin_profile
from .logging import get_logger
from .spec_generator import generate_agent_specs

try:
    from .telemetry import (
        emit_mbti_persona_selected,
        emit_domain_selector_changed,
        emit_domain_selector_error,
        emit_domain_selector_validated,
        emit_event,
    )
except Exception:  # pragma: no cover - defensive import fallback
    emit_mbti_persona_selected = None
    emit_domain_selector_changed = None
    emit_domain_selector_error = None
    emit_domain_selector_validated = None
    emit_event = None

LOGGER = get_logger("intake")

WSGIResponse = tuple[str, list[tuple[str, str]], bytes]


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

ATTRIBUTES = [
    "Detail Oriented",
    "Collaborative",
    "Proactive",
    "Strategic",
    "Empathetic",
    "Experimental",
    "Efficient",
]

COMMUNICATION_STYLES = ["Formal", "Conversational", "Concise", "Storytelling"]
COLLABORATION_MODES = ["Solo", "Pair", "Cross-Functional", "Advisory"]



def _mbti_axes(code: str) -> Dict[str, str]:
    code = (code or "").upper()
    labels = ("EI", "SN", "TF", "JP")
    axes: Dict[str, str] = {}
    for idx, label in enumerate(labels):
        axes[label] = code[idx] if len(code) > idx else ""
    return axes

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
$persona_styles
$domain_selector_styles
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
                <!-- NAICS + Function Selection -->
                <div id="domain-bundle" data-domain-bundle>
                    $naics_selector_html
                    $function_select_html
                    <input type="hidden" name="naics_code">
                    <input type="hidden" name="naics_title">
                    <input type="hidden" name="naics_level">
                        <input type="hidden" name="naics_lineage_json">
                    <input type="hidden" name="function_category">
                    <input type="hidden" name="function_specialties_json">
                </div>
        <label>Agent Name
          <input type="text" name="agent_name" placeholder="e.g., Atlas Analyst" required>
        </label>
        <label>Version
          <input type="text" name="agent_version" value="1.0.0">
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
        <!-- MBTI SECTION (moved below domain/role) -->
        <section id="mbti-section" data-testid="mbti-section" data-mbti-tooltips="enabled" class="persona-inline">
          <input type="hidden" name="agent_persona" value="$persona_hidden_value" data-persona-input>
          $persona_tabs
        </section>
      </fieldset>

      <fieldset>
        <legend>Toolsets</legend>
        <div class="options">
          $toolset_checkboxes
        </div>
        <label>Custom Toolsets (comma separated)
          <input type="text" name="custom_toolsets" placeholder="e.g., Knowledge Graphing, Scenario Planning">
        </label>
      </fieldset>

      <fieldset>
        <legend>Attributes & Traits</legend>
        <div class="options">
          $attribute_checkboxes
        </div>
        <label>Custom Attributes (comma separated)
          <input type="text" name="custom_attributes" placeholder="e.g., Customer obsessed, Pattern matcher">
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
    <script type="module">
$persona_script
$domain_selector_script
$domain_selector_init
    </script>
  </body>
</html>
"""
)


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



class IntakeApplication:
    """Minimal WSGI application serving the intake workflow."""
    # Step 4 Non-goals (documented):
    # - No advanced NAICS fuzzy search beyond simple prefix/substring match.
    # - No pagination or caching layer for NAICS API (reference small & cached in-process).
    # - No schema version updates yet; domain_selector shape unchanged.
    # - No analytics batching/export; telemetry buffered only in-memory.

    MAX_BODY_BYTES = 1_048_576

    def __init__(self, base_dir: Path | None = None) -> None:
        self.project_root = Path(__file__).resolve().parents[2]
        self.assets_root = self.project_root / "src"
        self.ui_dir = self.assets_root / "ui"
        self.persona_dir = self.assets_root / "persona"
        self.static_dir = self.assets_root / "neo_agent" / "static"
        self.base_dir = self._resolve_base_dir(base_dir)
        self.profile_path = self.base_dir / "agent_profile.json"
        self.spec_dir = self.base_dir / "generated_specs"
        self.spec_dir.mkdir(parents=True, exist_ok=True)
        self.persona_state_path = self.base_dir / "persona_state.json"
        self.persona_assets = self._load_persona_assets()
        self.persona_config = self._load_persona_config()
        self.mbti_lookup = self._index_mbti_types(self.persona_config.get("mbti_types", []))
        self.domain_selector_assets = self._load_domain_selector_assets()
        # Step 3 / 4: Domain selector validation / NAICS
        self._naics_cache: dict[str, dict] | None = None  # lazy load on first lookup
        self._naics_prefix_index: dict[str, list[str]] | None = None
        # Lock protects atomic swap of NAICS caches during reloads
        self._naics_lock = threading.RLock()
        # Fuzzy search small LRU cache: key=query -> list[entries]
        self._naics_search_cache: list[tuple[str, list[dict]]] = []  # simple FIFO/LRU list
        self._naics_search_cache_capacity = 64
        LOGGER.debug(
            "Initialised intake application with base_dir=%s persona_state=%s",
            self.base_dir,
            self.persona_state_path,
        )

    @staticmethod
    def _resolve_base_dir(base_dir: Path | None) -> Path:
        if base_dir is not None:
            return base_dir
        current = Path(__file__).resolve()
        parents = list(current.parents)
        for candidate in parents:
            if (candidate / "pyproject.toml").exists():
                return candidate
        fallback = parents[2] if len(parents) > 2 else parents[-1]
        LOGGER.warning(
            "Unable to locate project root via pyproject.toml; defaulting to %s",
            fallback,
        )
        return fallback

    @staticmethod
    def _ensure_content_length(
        headers: Iterable[tuple[str, str]], size: int
    ) -> list[tuple[str, str]]:
        updated: list[tuple[str, str]] = []
        has_length = False
        for name, value in headers:
            if name.lower() == "content-length":
                updated.append((name, str(size)))
                has_length = True
            else:
                updated.append((name, value))
        if not has_length:
            updated.append(("Content-Length", str(size)))
        return updated

    def _indent_block(self, content: str, spaces: int = 6) -> str:
        if not content:
            return ""
        prefix = " " * spaces
        return "\n".join(
            f"{prefix}{line}" if line else "" for line in content.splitlines()
        )



    def _safe_read_text(self, path: Path) -> str:
        if not path.exists():
            LOGGER.warning("Persona asset missing: %s", path)
            return ""
        return path.read_text(encoding="utf-8")

    def _safe_read_json(self, path: Path, default: Any) -> Any:
        if not path.exists():
            LOGGER.warning("Persona config missing: %s", path)
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            LOGGER.exception("Failed to parse JSON at %s", path)
            return default

    def _load_persona_assets(self) -> dict[str, str]:
        html = self._safe_read_text(self.ui_dir / "persona_tabs.html")
        base_css = self._safe_read_text(self.ui_dir / "persona.css")
        tooltip_css = self._safe_read_text(self.static_dir / "mbti_tooltip.css")
        combined_css = base_css
        if tooltip_css:
            combined_css = (combined_css + "\n" + tooltip_css) if combined_css else tooltip_css
        css = self._indent_block(combined_css)
        script = self._indent_block(self._safe_read_text(self.ui_dir / "persona.js"), spaces=4)
        return {"html": html, "css": css, "js": script}
    def _load_domain_selector_assets(self) -> dict[str, str]:
        html_block = self._safe_read_text(self.ui_dir / "domain_selector.html")
        css_block = self._safe_read_text(self.ui_dir / "domain_selector.css")
        script_block = self._safe_read_text(self.ui_dir / "domain_selector.js")
        return {
            "html": self._indent_block(html_block, spaces=8),
            "css": self._indent_block(css_block),
            "js": self._indent_block(script_block, spaces=4),
        }

    def _index_mbti_types(self, entries: Iterable[Mapping[str, Any]]) -> Dict[str, Mapping[str, Any]]:
        lookup: Dict[str, Mapping[str, Any]] = {}
        for entry in entries or []:
            if not isinstance(entry, Mapping):
                continue
            code = str(entry.get("code", "")).upper()
            if code:
                lookup[code] = entry
        return lookup

    def _enrich_persona_metadata(self, code: str | None) -> Dict[str, Any] | None:
        if not code:
            return None
        entry = self.mbti_lookup.get(str(code).upper()) if hasattr(self, "mbti_lookup") else None
        if not entry:
            return None
        axes = _mbti_axes(entry.get("code", code))
        description = entry.get("summary") or entry.get("description") or ""
        return {
            "mbti_code": str(entry.get("code", code)).upper(),
            "name": entry.get("nickname") or entry.get("name") or "",
            "description": description,
            "axes": axes,
            "suggested_traits": [],
        }

    def _load_persona_config(self) -> dict[str, Any]:
        mbti = self._safe_read_json(self.persona_dir / "mbti_types.json", [])
        priors = self._safe_read_json(
            self.persona_dir / "priors_by_domain_role.json", {}
        )
        return {
            "mbti_types": mbti,
            "priors_by_domain_role": priors,
        }

    # Rendering helpers -------------------------------------------------
    def render_form(
        self,
        *,
        message: str | None = None,
        profile: Mapping[str, Any] | None = None,
        domain_selector_errors: list[str] | None = None,
    ) -> str:
        persona_style_block = self.persona_assets.get("css", "")
        persona_html = self.persona_assets.get("html", "")
        persona_script = self.persona_assets.get("js", "")
        persona_script += """
window.addEventListener('DOMContentLoaded', function () {
  var grid = document.querySelector('[data-operator-grid]');
  if (!grid) { return; }
  grid.querySelectorAll('button').forEach(function (button) {
    var code = button.getAttribute('data-code') || (button.dataset ? button.dataset.code : null);
    if (code && !button.hasAttribute('data-mbti-code')) {
      button.setAttribute('data-mbti-code', code);
    }
  });
});
"""
        persona_hidden = ""
        # MBTI SECTION (moved below domain/role)

        if profile:
            persona_section = profile.get("persona") if isinstance(profile, Mapping) else {}
            if isinstance(persona_section, Mapping):
                agent_section = persona_section.get("agent", {})
                if isinstance(agent_section, Mapping):
                    persona_hidden = str(agent_section.get("code", ""))
            agent_persona = profile.get("agent", {}).get("persona") if isinstance(profile, Mapping) else ""
            if not persona_hidden and agent_persona:
                persona_hidden = str(agent_persona)

        # Load NAICS & function selection partials
        naics_selector_html = self._safe_read_text(self.ui_dir / "naics_selector.html")
        function_select_html = self._safe_read_text(self.ui_dir / "function_select.html")

        domain_selector_styles = ""
        domain_selector_script = ""
        domain_selector_init = ""
        domain_selector_value = ""
        try:
            domain_selector_styles = self._indent_block(
                self._safe_read_text(self.ui_dir / "domain_bundle.css")
            )
        except FileNotFoundError:
            LOGGER.debug("domain_bundle.css not found", exc_info=True)
        except Exception:  # pragma: no cover - defensive read
            LOGGER.debug("Failed to load domain_bundle.css", exc_info=True)

        try:
            domain_selector_script = self._indent_block(
                self._safe_read_text(self.ui_dir / "domain_bundle.js"), spaces=4
            )
        except FileNotFoundError:
            LOGGER.debug("domain_bundle.js not found", exc_info=True)
        except Exception:  # pragma: no cover - defensive read
            LOGGER.debug("Failed to load domain_bundle.js", exc_info=True)
        # Render domain selector / persona form. Surface domain selector errors if present.
        error_block = ""
        if domain_selector_errors:
            items = "".join(f"<li>{html.escape(err)}</li>" for err in domain_selector_errors)
            error_block = f'<div class="notice error" id="domain-selector-errors" tabindex="-1"><ul>{items}</ul></div>'

        return FORM_TEMPLATE.substitute(
            notice=_notice(message) + error_block,
            summary=_summary_block(profile, str(self.profile_path), str(self.spec_dir)),
            persona_tabs=persona_html,
            persona_styles=persona_style_block,
            persona_script=persona_script,
            persona_hidden_value=persona_hidden,
            domain_selector_styles=domain_selector_styles,
            domain_selector_html="",
            domain_selector_script=domain_selector_script,
            domain_selector_init=domain_selector_init,
            domain_selector_value=domain_selector_value,
            naics_selector_html=naics_selector_html,
            function_select_html=function_select_html,
            domain_options=_option_list(DOMAINS),
            role_options=_option_list(ROLES),
            toolset_checkboxes=_checkboxes("toolsets", TOOLSETS),
            attribute_checkboxes=_checkboxes("attributes", ATTRIBUTES),
            communication_options=_option_list(COMMUNICATION_STYLES),
            collaboration_options=_option_list(COLLABORATION_MODES),
        )

    def _build_profile(self, data: Mapping[str, List[str]], linkedin: Mapping[str, Any]) -> Dict[str, Any]:
        def _get(name: str, default: str = "") -> str:
            values = data.get(name, [])
            return values[0] if values else default

        def _getlist(name: str) -> List[str]:
            return list(data.get(name, []))

        profile: Dict[str, Any] = {
            "agent": {
                "name": _get("agent_name", "Custom Project NEO Agent"),
                "version": _get("agent_version", "1.0.0"),
                "persona": _get("agent_persona", ""),
                "domain": _get("domain", ""),
                "role": _get("role", ""),
            },
            "toolsets": {
                "selected": _getlist("toolsets"),
                "custom": _split_csv(_get("custom_toolsets")),
            },
            "attributes": {
                "selected": _getlist("attributes"),
                "custom": _split_csv(_get("custom_attributes")),
            },
            "preferences": {
                "sliders": {
                    "autonomy": int(_get("autonomy", "50") or 50),
                    "confidence": int(_get("confidence", "50") or 50),
                    "collaboration": int(_get("collaboration", "50") or 50),
                },
                "communication_style": _get("communication_style"),
                "collaboration_mode": _get("collaboration_mode"),
            },
            "notes": _get("notes", ""),
            "linkedin": linkedin,
            "persona": self._load_persona_state(),
        }

        # NAICS + Function hidden fields (new classification system)
        naics_code = _get("naics_code")
        if naics_code:
            try:
                naics_level = int(_get("naics_level") or 0)
            except ValueError:
                naics_level = 0
            naics_title = _get("naics_title")
            lineage_raw = _get("naics_lineage_json")
            lineage: list[dict[str, Any]] = []
            if lineage_raw:
                try:
                    parsed = json.loads(lineage_raw)
                    if isinstance(parsed, list):
                        for item in parsed:
                            if isinstance(item, Mapping) and item.get("code"):
                                lineage.append({
                                    "code": str(item.get("code")),
                                    "title": str(item.get("title", "")),
                                    "level": item.get("level")
                                })
                except Exception:
                    LOGGER.debug("Failed to parse naics_lineage_json", exc_info=True)
            profile.setdefault("classification", {})["naics"] = {
                "code": naics_code,
                "title": naics_title,
                "level": naics_level,
                "lineage": lineage,
            }
            if emit_event:
                try:
                    emit_event("naics:selected", {"code": naics_code, "level": naics_level})
                except Exception:  # pragma: no cover
                    LOGGER.debug("Failed to emit naics:selected event", exc_info=True)

        function_category = _get("function_category")
        specialties_json = _get("function_specialties_json")
        specialties: list[str] = []
        if specialties_json:
            try:
                loaded = json.loads(specialties_json)
                if isinstance(loaded, list):
                    for s in loaded:
                        if isinstance(s, str) and s.strip():
                            if s.strip() not in specialties:
                                specialties.append(s.strip())
            except Exception:
                LOGGER.debug("Failed to parse function_specialties_json", exc_info=True)
        if function_category:
            profile.setdefault("classification", {})["function"] = {
                "category": function_category,
                "specialties": specialties,
            }
            if emit_event:
                try:
                    emit_event("function:selected", {"category": function_category, "specialties": len(specialties)})
                except Exception:  # pragma: no cover
                    LOGGER.debug("Failed to emit function:selected event", exc_info=True)

        domain_selector_raw = _get("domain_selector", "")
        # local error collection to avoid cross-request leakage
        ds_errors: list[str] = []
        domain_selector = self._parse_domain_selector(domain_selector_raw, ds_errors)
        if domain_selector and not ds_errors:
            profile["agent"]["domain_selector"] = domain_selector
        # attach collected errors so caller (POST handler) can render them
        profile.setdefault("_validation", {})["domain_selector_errors"] = ds_errors

        persona_state = profile.get("persona")
        enriched_persona = None
        if isinstance(persona_state, Mapping):
            agent_state = persona_state.get("agent")
            if isinstance(agent_state, Mapping):
                mbti_block = agent_state.get("mbti")
                if isinstance(mbti_block, Mapping):
                    enriched_persona = mbti_block
            if not enriched_persona:
                details_block = persona_state.get("persona_details")
                if isinstance(details_block, Mapping):
                    enriched_persona = details_block
        fallback_persona = profile["agent"].get("persona")
        if not enriched_persona and fallback_persona:
            enriched_persona = self._enrich_persona_metadata(fallback_persona)
        if isinstance(enriched_persona, Mapping):
            profile["agent"]["mbti"] = dict(enriched_persona)
            code_value = enriched_persona.get("mbti_code")
            if code_value:
                profile["agent"]["persona"] = str(code_value)
            if emit_mbti_persona_selected and not profile["agent"].get("_mbti_telemetry_emitted"):
                try:
                    emit_mbti_persona_selected(enriched_persona)
                    profile["agent"]["_mbti_telemetry_emitted"] = True
                except Exception:
                    LOGGER.debug("Failed to emit MBTI telemetry event", exc_info=True)

        if linkedin:
            derived_tools = linkedin.get("skills", [])
            for tool in derived_tools:
                candidate = tool.title()
                if candidate not in profile["toolsets"]["selected"]:
                    profile["toolsets"]["selected"].append(candidate)

            derived_roles = linkedin.get("roles", [])
            if derived_roles and not profile["agent"].get("role"):
                profile["agent"]["role"] = derived_roles[0].title()

        # Optional schema validation (Step 5) - does not block profile generation
        try:
            self._maybe_validate_schema(profile)
        except Exception:
            LOGGER.debug("Schema validation failed (non-blocking)", exc_info=True)
        return profile

    def _maybe_validate_schema(self, profile: Mapping[str, Any]) -> None:
        """Validate profile against JSON schema if jsonschema is installed.

        Non-blocking: logs debug on failure. Intended for development feedback.
        """
        schema_path = self.project_root / "schemas" / "agent_profile.schema.json"
        if not schema_path.exists():  # nothing to do
            return
        try:  # dynamic import to keep dependency optional
            import jsonschema  # type: ignore
        except Exception:
            return
        try:
            schema_obj = json.loads(schema_path.read_text(encoding="utf-8"))
        except Exception:
            LOGGER.debug("Failed to load schema file %s", schema_path, exc_info=True)
            return
        validator = jsonschema.Draft202012Validator(schema_obj) if hasattr(jsonschema, 'Draft202012Validator') else jsonschema.Draft7Validator(schema_obj)  # type: ignore
        errors = sorted(validator.iter_errors(profile), key=lambda e: e.path)  # type: ignore
        if errors:
            msgs = [f"{'/'.join(str(p) for p in err.path)}: {err.message}" for err in errors]
            LOGGER.debug("Profile schema validation issues: %s", msgs)

    def _build_naics_structures(self) -> tuple[dict[str, dict], dict[str, list[str]]]:
        """Load NAICS JSON and build cache + prefix index (without mutating state).

        Returns a tuple of (cache, prefix_index). Any exception bubbles to caller for
        rollback logic handled by reload invoker.
        """
        sources = self._naics_reference_sources()
        cache: dict[str, dict] = {}
        raw_parents: dict[str, Any] = {}
        raw_paths: dict[str, Any] = {}
        for ref_path in sources:
            try:
                entries = json.loads(ref_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:  # pragma: no cover - parse error path
                LOGGER.debug("Failed to parse NAICS reference %s: %s", ref_path, exc)
                continue
            for entry in entries or []:
                if not isinstance(entry, Mapping):
                    continue
                code = str(entry.get("code", "")).strip()
                if not code or code in cache:
                    continue
                cache[code] = dict(entry)
                raw_parents[code] = entry.get("parents")
                raw_paths[code] = entry.get("path")

        def _normalise_parents(code: str) -> list[dict]:
            parents_raw = raw_parents.get(code)
            parents: list[dict] = []
            if isinstance(parents_raw, list):
                for parent in parents_raw:
                    if isinstance(parent, Mapping):
                        p_code = str(parent.get("code", "")).strip()
                        if not p_code:
                            continue
                        parents.append(
                            {
                                "code": p_code,
                                "title": str(parent.get("title", "")),
                                "level": int(parent.get("level", 0) or 0),
                            }
                        )
            elif parents_raw:
                LOGGER.debug("Unexpected parents payload for NAICS code %s: %r", code, parents_raw)
            if parents:
                return parents
            # Fallback: infer parents from path if available
            path_raw = raw_paths.get(code)
            if isinstance(path_raw, list) and len(path_raw) >= 2:
                inferred: list[dict] = []
                for ancestor_code in path_raw[:-1]:
                    ancestor_code = str(ancestor_code).strip()
                    if not ancestor_code:
                        continue
                    ancestor = cache.get(ancestor_code)
                    if ancestor:
                        inferred.append(
                            {
                                "code": ancestor.get("code"),
                                "title": ancestor.get("title"),
                                "level": int(ancestor.get("level", 0) or 0),
                            }
                        )
                return inferred
            return []

        def _normalise_path(code: str, parents: list[dict]) -> list[str]:
            path_raw = raw_paths.get(code)
            if isinstance(path_raw, list) and path_raw:
                return [str(item).strip() for item in path_raw if str(item).strip()]
            lineage = [p.get("code") for p in parents if p.get("code")]
            lineage.append(code)
            return lineage

        for code, entry in cache.items():
            parents = _normalise_parents(code)
            entry["parents"] = parents
            entry["path"] = _normalise_path(code, parents)
            # Ensure level normalised/integer
            try:
                entry["level"] = int(entry.get("level") or len(entry["path"]))
            except Exception:
                entry["level"] = len(entry["path"])
            version = entry.get("version")
            entry["version"] = str(version) if version else "2022"

        # Pass 2: Ensure parent chains exist for deeper levels (e.g., 4- and 6-digit)
        # by synthesising missing intermediate parents from code prefixes if needed.
        for code, entry in cache.items():
            code_str = str(entry.get("code") or code)
            try:
                lvl = int(entry.get("level") or 0)
            except Exception:
                lvl = 0
            if lvl <= 2:
                continue
            desired_levels = [L for L in (2, 3, 4, 5) if L < lvl]
            existing_list = entry.get("parents") or []
            existing_codes = [p.get("code") for p in existing_list if isinstance(p, Mapping)]
            chain: list[dict] = []
            for L in desired_levels:
                pref = code_str[:L]
                if pref in existing_codes:
                    # reuse existing parent payload
                    for p in existing_list:
                        if isinstance(p, Mapping) and p.get("code") == pref:
                            chain.append({
                                "code": p.get("code"),
                                "title": str(p.get("title", "")),
                                "level": int(p.get("level", L) or L),
                            })
                            break
                else:
                    ref_parent = cache.get(pref)
                    chain.append({
                        "code": pref,
                        "title": str(ref_parent.get("title")) if ref_parent else "",
                        "level": L,
                    })
            # de-dup ordered
            seen: set[str] = set()
            deduped: list[dict] = []
            for p in chain:
                c = str(p.get("code") or "")
                if c and c not in seen:
                    seen.add(c)
                    deduped.append(p)
            entry["parents"] = deduped
            entry["path"] = [p["code"] for p in deduped] + [code_str]
        prefix_index: dict[str, list[str]] = {}
        for code in cache.keys():
            for i in range(2, min(len(code), 6) + 1):
                prefix = code[:i]
                bucket = prefix_index.setdefault(prefix, [])
                if code not in bucket:
                    bucket.append(code)
        for bucket in prefix_index.values():
            bucket.sort()
        return cache, prefix_index

    def _naics_children_at_level(self, parent_code: str, target_level: int) -> list[dict]:
        """Return descendants of parent_code exactly at target_level using path membership."""
        ref = self._load_naics_reference()
        parent_code = str(parent_code or "").strip()
        try:
            target_level = int(target_level)
        except Exception:
            return []
        if target_level < 2 or target_level > 6:
            return []
        items: list[dict] = []
        for entry in ref.values():
            try:
                lvl = int(entry.get("level") or 0)
            except Exception:
                continue
            if lvl != target_level:
                continue
            if str(entry.get("code") or "") == parent_code:
                continue
            path_list = entry.get("path") or []
            if isinstance(path_list, list) and parent_code in path_list:
                items.append({
                    "code": entry.get("code"),
                    "title": entry.get("title"),
                    "level": lvl,
                })
        items.sort(key=lambda e: e["code"])  # deterministic ordering
        return items

    def _load_naics_reference(self) -> dict[str, dict]:
        # Fast path: already loaded
        if self._naics_cache is not None:
            return self._naics_cache
        # Acquire lock for initial build to avoid duplicate work under concurrency
        with self._naics_lock:
            if self._naics_cache is not None:  # double-checked
                return self._naics_cache
            cache, prefix_index = self._build_naics_structures()
            self._naics_cache = cache
            self._naics_prefix_index = prefix_index
            LOGGER.debug("Loaded %d NAICS reference entries (initial build)", len(cache))
            if emit_event:
                try:
                    emit_event(
                        "naics:loaded",
                        {"entries": len(cache), "prefix_keys": len(prefix_index)},
                    )
                except Exception:  # pragma: no cover
                    LOGGER.debug("Failed to emit naics:loaded event", exc_info=True)
            return cache

    def reload_naics(self) -> int:
        """Atomically rebuild NAICS cache + prefix index.

        Builds new structures off-lock and swaps them in under lock ensuring readers never
        observe a partially-built index. Returns number of entries on success (0 on failure).
        Emits telemetry events if available.
        """
        start = time.perf_counter()
        if emit_event:
            try:
                emit_event("naics_reload:start", {})
            except Exception:  # pragma: no cover
                LOGGER.debug("Failed to emit naics_reload:start", exc_info=True)
        try:
            new_cache, new_index = self._build_naics_structures()
        except Exception as exc:  # build failure, do not swap
            LOGGER.exception("NAICS reload build failed")
            if emit_event:
                try:
                    emit_event(
                        "naics_reload:failure",
                        {"error": str(exc)},
                    )
                except Exception:  # pragma: no cover
                    LOGGER.debug("Failed to emit naics_reload:failure", exc_info=True)
            return 0
        # Successful build; swap under lock
        with self._naics_lock:
            self._naics_cache = new_cache
            self._naics_prefix_index = new_index
        duration = (time.perf_counter() - start) * 1000.0
        LOGGER.info(
            "NAICS reload successful entries=%d prefix_keys=%d duration=%.1fms",
            len(new_cache),
            len(new_index),
            duration,
        )
        if emit_event:
            try:
                emit_event(
                    "naics_reload:success",
                    {
                        "entries": len(new_cache),
                        "prefix_keys": len(new_index),
                        "duration_ms": round(duration, 2),
                    },
                )
            except Exception:  # pragma: no cover
                LOGGER.debug("Failed to emit naics_reload:success", exc_info=True)
        return len(new_cache)

    def _naics_lookup(self, code: str) -> dict | None:
        if not code:
            return None
        ref = self._load_naics_reference()
        return ref.get(str(code).strip())

    def _naics_prefix_search(self, prefix: str, limit: int = 25) -> list[dict]:  # pragma: no cover - will be covered via API test
        """Return entries whose code starts with the prefix using the prefix index if available.

        Falls back to linear scan if index missing (e.g., build failure). Limit enforced to avoid huge payloads.
        """
        prefix = (prefix or "").strip()
        if not prefix:
            return []
        self._load_naics_reference()  # ensure cache & index built
        results: list[dict] = []
        try:
            index = getattr(self, "_naics_prefix_index", None)
            if isinstance(index, dict) and prefix in index:
                codes = index[prefix][:limit]
                ref = self._naics_cache or {}
                for c in codes:
                    entry = ref.get(c)
                    if entry:
                        results.append(entry)
                return results
        except Exception:  # pragma: no cover
            LOGGER.debug("Prefix index lookup failed, falling back", exc_info=True)
        # Fallback linear scan
        ref = self._naics_cache or {}
        for c, entry in ref.items():
            if c.startswith(prefix):
                results.append(entry)
                if len(results) >= limit:
                    break
        return results

    _CURATED_TOP_LEVELS: Dict[str, List[str]] | None = None

    def _load_curated_domains(self) -> Dict[str, List[str]]:
        if self._CURATED_TOP_LEVELS is not None:
            return self._CURATED_TOP_LEVELS
        # Look in data/catalog/domain_curated.json relative to base_dir
        catalog_path = self.base_dir / "data" / "catalog" / "domain_curated.json"
        if not catalog_path.exists():
            LOGGER.warning("Curated domain catalog missing at %s; using embedded defaults", catalog_path)
            # Embedded fallback mirrors previous hard-coded list to keep behaviour stable in tests
            self._CURATED_TOP_LEVELS = {
                "Strategic Functions": [
                    "AI Strategy & Governance",
                    "Prompt Architecture & Evaluation",
                    "Workflow Orchestration",
                    "Observability & Telemetry",
                ],
                "Sector Domains": [
                    "Energy & Infrastructure",
                    "Economic Intelligence",
                    "Environmental Intelligence",
                    "Multi-Sector SME Overlay",
                ],
                "Technical Domains": [
                    "Agentic RAG & Knowledge Graphs",
                    "Tool & Connector Integrations",
                    "Memory & Data Governance",
                    "Safety & Privacy Compliance",
                ],
                "Support Domains": [
                    "Onboarding & Training",
                    "Reporting & Publishing",
                    "Lifecycle & Change Mgmt",
                ],
            }
            return self._CURATED_TOP_LEVELS
        try:
            data = json.loads(catalog_path.read_text(encoding="utf-8"))
        except Exception:
            LOGGER.exception("Failed to parse curated domain catalog %s", catalog_path)
            data = {}
        curated: Dict[str, List[str]] = {}
        if isinstance(data, Mapping):
            for k, v in data.items():
                if isinstance(k, str) and isinstance(v, list):
                    curated[k] = [str(item) for item in v if isinstance(item, (str, bytes))]
        self._CURATED_TOP_LEVELS = curated
        return curated

    def _validate_domain_selector(self, payload: Mapping[str, Any], errors: list[str]) -> dict | None:
        """Validate and enrich domain selector; append errors to self._domain_selector_errors.

        Responsibilities per Step 3 specification.
        """
        if not isinstance(payload, Mapping):  # defensive
            return None
        top_level = str(payload.get("topLevel") or "").strip()
        subdomain = str(payload.get("subdomain") or "").strip()
        if not top_level or not subdomain:
            return None
        curated = self._load_curated_domains().get(top_level)
        if curated is None:
            errors.append(f"Invalid topLevel {top_level}")
            if emit_domain_selector_error:
                try:
                    emit_domain_selector_error(
                        f"Invalid topLevel {top_level}",
                        {"topLevel": top_level, "subdomain": subdomain},
                    )
                except Exception:
                    LOGGER.debug("Failed to emit domain selector error event", exc_info=True)
        if curated is not None and subdomain not in curated:
            errors.append(f"Invalid subdomain {subdomain} for topLevel {top_level}")
            if emit_domain_selector_error:
                try:
                    emit_domain_selector_error(
                        f"Invalid subdomain {subdomain} for topLevel {top_level}",
                        {"topLevel": top_level, "subdomain": subdomain},
                    )
                except Exception:
                    LOGGER.debug("Failed to emit domain selector error event", exc_info=True)
        # Normalise tags (stringify, unique order-preserving)
        unique_tags: list[str] = []
        seen: set[str] = set()
        raw_tags = payload.get("tags", [])
        if isinstance(raw_tags, Iterable) and not isinstance(raw_tags, (str, bytes)):
            for tag in raw_tags:
                if tag is None:
                    continue
                if isinstance(tag, (dict, list, set)):  # ignore complex structures
                    continue
                tag_str = str(tag).strip().lower()
                if not tag_str:
                    continue
                # Normalize: remove disallowed chars, collapse whitespace/hyphens
                import re
                cleaned = re.sub(r"[^a-z0-9\s-]", "", tag_str)
                cleaned = re.sub(r"\s+", "-", cleaned)
                cleaned = re.sub(r"-+", "-", cleaned).strip("-")
                if not cleaned:
                    continue
                if cleaned not in seen:
                    seen.add(cleaned)
                    unique_tags.append(cleaned)
                # Enforce cap to mitigate abuse / excessive CPU
                if len(unique_tags) >= 50:
                    if emit_event:
                        try:
                            emit_event(
                                "domain_selector:tags_capped",
                                {"limit": 50, "topLevel": top_level, "subdomain": subdomain},
                            )
                        except Exception:  # pragma: no cover
                            LOGGER.debug("Failed to emit tags_capped event", exc_info=True)
                    break
        result: dict[str, Any] = {
            "topLevel": top_level,
            "subdomain": subdomain,
            "tags": unique_tags,
        }
        # NAICS handling
        naics_value = payload.get("naics")
        if top_level == "Sector Domains" and not errors:
            naics_code = None
            if isinstance(naics_value, Mapping):
                naics_code = str(naics_value.get("code") or "").strip()
            if not naics_code:
                errors.append("NAICS required for Sector Domains")
                if emit_domain_selector_error:
                    try:
                        emit_domain_selector_error(
                            "NAICS required for Sector Domains",
                            {"topLevel": top_level, "subdomain": subdomain},
                        )
                    except Exception:
                        LOGGER.debug("Failed to emit domain selector error event", exc_info=True)
                return None
            entry = self._naics_lookup(naics_code)
            if not entry:
                errors.append(f"Invalid NAICS code {naics_code}")
                if emit_domain_selector_error:
                    try:
                        emit_domain_selector_error(
                            f"Invalid NAICS code {naics_code}",
                            {"topLevel": top_level, "subdomain": subdomain},
                        )
                    except Exception:
                        LOGGER.debug("Failed to emit domain selector error event", exc_info=True)
                return None
            # If the client attempted to send additional NAICS fields (title/level/path/version)
            # we enforce integrity: any mismatch with reference causes rejection of the selector.
            if isinstance(naics_value, Mapping):
                mismatch = False
                # Compare selected fields when provided by client
                for field in ("title", "level", "version", "path"):
                    if field in naics_value:
                        ref_val = entry.get(field)
                        provided = naics_value.get(field)
                        # Normalize path lists for comparison
                        if field == "path" and isinstance(provided, list) and isinstance(ref_val, list):
                            if provided != ref_val:
                                mismatch = True
                                break
                        elif provided != ref_val:
                            mismatch = True
                            break
                if mismatch:
                    errors.append("NAICS fields mismatch reference; rejecting selector")
                    if emit_domain_selector_error:
                        try:
                            emit_domain_selector_error(
                                "NAICS fields mismatch reference",
                                {"topLevel": top_level, "subdomain": subdomain, "code": naics_code},
                            )
                        except Exception:
                            LOGGER.debug("Failed to emit domain selector error event", exc_info=True)
                    return None
            # Enrich: strictly overwrite fields
            result["naics"] = {
                "code": entry.get("code"),
                "title": entry.get("title"),
                "level": entry.get("level"),
                "version": entry.get("version"),
                "path": entry.get("path"),
            }
        else:
            # strip any provided NAICS
            pass
        if not errors and emit_domain_selector_validated:
            try:
                emit_domain_selector_validated(result)
            except Exception:
                LOGGER.debug("Failed to emit domain selector validated event", exc_info=True)
        return result

    def _parse_domain_selector(self, raw: str | None, errors: list[str]) -> Dict[str, Any] | None:
        if not raw:
            return None
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            LOGGER.debug("Unable to decode domain selector payload", exc_info=True)
            errors.append("Malformed domain_selector JSON; ignored")
            return None
        # Guard: if essential fields missing, treat as stale and ignore to prevent
        # previously valid JSON from being resubmitted after client cleared UI.
        if isinstance(payload, Mapping):
            top_level = str(payload.get("topLevel") or "").strip()
            subdomain = str(payload.get("subdomain") or "").strip()
            if not top_level or not subdomain:
                # Explicitly ignore and do not emit change telemetry to avoid noise.
                return None
        if isinstance(payload, Mapping) and emit_domain_selector_changed:
            try:
                emit_domain_selector_changed(payload)
            except Exception:
                LOGGER.debug("Failed to emit domain selector changed event", exc_info=True)
        return self._validate_domain_selector(payload, errors) if isinstance(payload, Mapping) else None


    def _read_body(self, environ: Mapping[str, Any]) -> bytes:
        stream = environ.get("wsgi.input")
        if stream is None:
            return b""
        reader = getattr(stream, "read", None)
        if reader is None:
            return b""
        try:
            length = int(environ.get("CONTENT_LENGTH") or 0)
        except (TypeError, ValueError):
            length = 0
        limit = self.MAX_BODY_BYTES
        chunk = reader(min(length, limit) if length > 0 else limit)
        if not isinstance(chunk, (bytes, bytearray)):
            return b""
        return bytes(chunk)

    def _json_response(
        self, payload: Mapping[str, Any], *, status: str = "200 OK"
    ) -> WSGIResponse:
        body = json.dumps(payload).encode("utf-8")
        headers = [("Content-Type", "application/json; charset=utf-8")]
        headers = self._ensure_content_length(headers, len(body))
        return status, headers, body

    def _method_not_allowed(self, allowed: Iterable[str]) -> WSGIResponse:
        allowed_methods = sorted({method.upper() for method in allowed})
        body = json.dumps(
            {"status": "method_not_allowed", "allowed": allowed_methods}
        ).encode("utf-8")
        headers = [
            ("Content-Type", "application/json; charset=utf-8"),
            ("Allow", ", ".join(allowed_methods)),
        ]
        headers = self._ensure_content_length(headers, len(body))
        return "405 Method Not Allowed", headers, body

    def _dispatch_api(
        self, path: str, method: str, environ: Mapping[str, Any]
    ) -> WSGIResponse:
        if path.startswith("/api/persona/"):
            return self._handle_persona_api(path, method, environ)
        if path.startswith("/api/naics/"):
            return self._handle_naics_api(path, method, environ)
        if path == "/api/domains/curated":
            if method != "GET":
                return self._method_not_allowed(["GET"])
            curated = self._load_curated_domains()
            # lightweight hash for cache-busting
            try:
                import hashlib
                digest = hashlib.sha1(json.dumps(curated, sort_keys=True).encode("utf-8")).hexdigest()[:12]
            except Exception:
                digest = "unknown"
            return self._json_response({"status": "ok", "curated": curated, "etag": digest})
        if path in ("/api/health", "/api/healthz"):
            return self._json_response({"status": "ok"})
        if path == "/api/profile/validate":
            if method != "POST":
                return self._method_not_allowed(["POST"])
            raw = self._read_body(environ)
            if not raw:
                payload: Any = {}
            else:
                try:
                    payload = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    return self._json_response(
                        {
                            "status": "invalid",
                            "issues": [f"Invalid JSON payload: {exc}"],
                        },
                        status="400 Bad Request",
                    )
            issues = self._validate_profile_payload(payload)
            status_value = "ok" if not issues else "invalid"
            return self._json_response({"status": status_value, "issues": issues})
        return self._json_response(
            {"status": "not_found", "message": f"Unknown API path: {path}"},
            status="404 Not Found",
        )
    def wsgi_app(self, environ: Mapping[str, Any], start_response):
        start = time.perf_counter()
        method = str(environ.get("REQUEST_METHOD", "GET")).upper()
        path_info = environ.get("PATH_INFO")
        path = path_info if isinstance(path_info, str) and path_info else "/"
        response_status = "200 OK"
        response_headers: list[tuple[str, str]] = []
        response_body = b""
        try:
            if path.startswith("/api/"):
                response_status, response_headers, response_body = self._dispatch_api(
                    path, method, environ
                )
            elif path in ("/health", "/healthz"):
                response_body = b"OK"
                response_headers = [("Content-Type", "text/plain; charset=utf-8")]
            elif path == "/" and method == "POST":
                # Clear previous request errors
                if hasattr(self, "_domain_selector_errors"):
                    self._domain_selector_errors.clear()
                form_bytes = self._read_body(environ)
                data = parse_qs(form_bytes.decode("utf-8"))
                linkedin_url = data.get("linkedin_url", [""])[0].strip()
                linkedin_data: Mapping[str, Any] = {}
                if linkedin_url:
                    try:
                        linkedin_data = scrape_linkedin_profile(linkedin_url)
                    except Exception:
                        LOGGER.exception(
                            "Failed to enrich profile from LinkedIn URL %s",
                            linkedin_url,
                        )
                        linkedin_data = {}
                profile = self._build_profile(data, linkedin_data)
                if not self.profile_path.parent.exists():
                    self.profile_path.parent.mkdir(parents=True, exist_ok=True)
                with self.profile_path.open("w", encoding="utf-8") as handle:
                    json.dump(profile, handle, indent=2)
                generate_agent_specs(profile, self.spec_dir)
                LOGGER.info("Generated profile at %s", self.profile_path)
                response_body = self.render_form(
                    message="Agent profile generated successfully.",
                    profile=profile,
                ).encode("utf-8")
                response_headers = [("Content-Type", "text/html; charset=utf-8")]
            elif path == "/" and method in {"GET", "HEAD"}:
                response_body = self.render_form().encode("utf-8")
                response_headers = [("Content-Type", "text/html; charset=utf-8")]
            elif path == "/":
                response_status, response_headers, response_body = self._method_not_allowed(
                    ["GET", "HEAD", "POST"]
                )
            else:
                response_status = "404 Not Found"
                response_body = self.render_form(
                    message="The requested path was not found."
                ).encode("utf-8")
                response_headers = [("Content-Type", "text/html; charset=utf-8")]
        except Exception:
            LOGGER.exception("Unhandled error while processing %s %s", method, path)
            response_status = "500 Internal Server Error"
            response_body = self.render_form(
                message="We encountered a problem processing your request. Please retry."
            ).encode("utf-8")
            response_headers = [("Content-Type", "text/html; charset=utf-8")]
        response_headers = self._ensure_content_length(response_headers, len(response_body))
        start_response(response_status, response_headers)
        duration_ms = (time.perf_counter() - start) * 1000
        LOGGER.info(
            "Handled %s %s -> %s in %.1fms",
            method,
            path,
            response_status.split(" ")[0],
            duration_ms,
        )
        return [response_body]


    def _handle_persona_api(
        self, path: str, method: str, environ: Mapping[str, Any]
    ) -> WSGIResponse:
        if path == "/api/persona/config" and method == "GET":
            return self._json_response(self.persona_config)
        if path == "/api/persona/state":
            if method == "GET":
                return self._json_response(self._load_persona_state())
            if method == "POST":
                raw = self._read_body(environ)
                if not raw:
                    return self._json_response(
                        {"status": "invalid", "issues": ["Missing request body"]},
                        status="400 Bad Request",
                    )
                try:
                    payload = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    return self._json_response(
                        {"status": "invalid", "issues": [f"Invalid JSON payload: {exc}"]},
                        status="400 Bad Request",
                    )
                state = self._save_persona_state(payload)
                return self._json_response(state)
            return self._method_not_allowed(["GET", "POST"])
        return self._json_response(
            {"status": "not_found", "message": f"Unknown persona path: {path}"},
            status="404 Not Found",
        )

    def _save_persona_state(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        if not isinstance(payload, Mapping):
            raise ValueError("Persona payload must be a mapping")
        operator_payload = payload.get("operator")
        operator = dict(operator_payload) if isinstance(operator_payload, Mapping) else None
        agent_payload = payload.get("agent")
        agent = dict(agent_payload) if isinstance(agent_payload, Mapping) else None
        alternates = payload.get("alternates")
        history_limit = 5

        persona_details = None
        if isinstance(agent, Mapping):
            persona_details = self._enrich_persona_metadata(agent.get("code"))
            if persona_details:
                agent = dict(agent)
                agent["mbti"] = persona_details

        state = self._load_persona_state()
        history = state.get("history", [])
        if state.get("operator") and state.get("agent"):
            history.insert(
                0,
                {
                    "operator": state.get("operator"),
                    "agent": state.get("agent"),
                    "stored_at": state.get("updated_at"),
                },
            )
            history = history[:history_limit]

        new_state: Dict[str, Any] = {
            "operator": operator,
            "agent": agent,
            "alternates": alternates if isinstance(alternates, list) else [],
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "history": history,
        }
        if persona_details:
            new_state["persona_details"] = persona_details
        with self.persona_state_path.open("w", encoding="utf-8") as handle:
            json.dump(new_state, handle, indent=2)
        return new_state

    def _load_persona_state(self) -> Dict[str, Any]:
        if not self.persona_state_path.exists():
            return {"operator": None, "agent": None, "alternates": [], "history": []}
        with self.persona_state_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        data.setdefault("history", [])
        data.setdefault("alternates", [])
        agent_section = data.get("agent")
        persona_details = data.get("persona_details") if isinstance(data.get("persona_details"), Mapping) else None
        enriched = None
        if isinstance(agent_section, Mapping):
            mbti_block = agent_section.get("mbti")
            if isinstance(mbti_block, Mapping):
                enriched = mbti_block
            else:
                enriched = self._enrich_persona_metadata(agent_section.get("code"))
                if enriched:
                    agent_section = dict(agent_section)
                    agent_section["mbti"] = enriched
                    data["agent"] = agent_section
        if enriched and not isinstance(persona_details, Mapping):
            data["persona_details"] = enriched
        return data

    def _naics_reference_sources(self) -> list[Path]:
        """Return existing NAICS dataset paths ordered by preference."""
        candidates = [
            self.project_root / "data" / "naics" / "naics_2022.json",
            self.project_root / "data" / "naics" / "naics_2022.sample.json",
            self.static_dir / "naics_reference.json",
        ]
        sources = [candidate for candidate in candidates if candidate.exists()]
        if not sources:
            raise FileNotFoundError(
                "NAICS reference data not found. Checked: {}".format(
                    ", ".join(str(path) for path in candidates)
                )
            )
        return sources
    def _validate_profile_payload(self, payload: Any) -> List[str]:
        if not isinstance(payload, Mapping):
            return ["Payload must be a JSON object."]
        issues: List[str] = []
        agent = payload.get("agent")
        if not isinstance(agent, Mapping):
            issues.append('"agent" must be an object containing intake attributes.')
        else:
            if not str(agent.get("name", "")).strip():
                issues.append('"agent.name" is required.')
            if "version" in agent and not str(agent.get("version", "")).strip():
                issues.append('"agent.version" cannot be blank when provided.')
        toolsets = payload.get("toolsets")
        if toolsets is not None:
            if not isinstance(toolsets, Mapping):
                issues.append('"toolsets" must be an object when provided.')
            else:
                selected = toolsets.get("selected")
                if selected is not None and not isinstance(selected, list):
                    issues.append('"toolsets.selected" must be a list when provided.')
        preferences = payload.get("preferences")
        if preferences is not None:
            if not isinstance(preferences, Mapping):
                issues.append('"preferences" must be an object when provided.')
            else:
                sliders = preferences.get("sliders")
                if sliders is not None and not isinstance(sliders, Mapping):
                    issues.append('"preferences.sliders" must be an object when provided.')
        return issues

    # --- NAICS API (Step 4) -------------------------------------------------
    def _handle_naics_api(self, path: str, method: str, environ: Mapping[str, Any]) -> WSGIResponse:
        if method != "GET":
            return self._method_not_allowed(["GET"])
        prefix = "/api/naics/code/"
        roots_path = "/api/naics/roots"
        children_prefix = "/api/naics/children/"
        search_prefix = "/api/naics/search"
        # Roots (level-2 entries)
        if path == roots_path:
            ref = self._load_naics_reference()
            roots: list[dict] = []
            for entry in ref.values():
                try:
                    level = int(entry.get("level") or 0)
                except Exception:
                    continue
                parents = entry.get("parents") or []
                if level == 2 and not parents:
                    roots.append({"code": entry.get("code"), "title": entry.get("title"), "level": level})
            roots.sort(key=lambda e: e["code"])  # deterministic ordering
            return self._json_response({"status": "ok", "items": roots, "count": len(roots)})
        # Children for given parent code
        if path.startswith(children_prefix):
            parent_code = path[len(children_prefix):]
            # Optional level targeting (e.g., 4 or 6)
            qs = environ.get("QUERY_STRING") or ""
            try:
                params = parse_qs(qs, keep_blank_values=False)
            except Exception:
                params = {}
            target_level = None
            if isinstance(params, dict):
                vals = params.get("level") or []
                if vals:
                    try:
                        lv = int(vals[0])
                        if lv in (4, 6):
                            target_level = lv
                    except Exception:
                        target_level = None
            if target_level is not None:
                items = self._naics_children_at_level(parent_code, target_level)
                return self._json_response({"status": "ok", "items": items, "parent": parent_code, "count": len(items)})
            ref = self._load_naics_reference()
            children_items: list[dict] = []
            for entry in ref.values():
                code_value = str(entry.get("code") or "")
                try:
                    level = int(entry.get("level") or 0)
                except Exception:
                    level = 0
                if level <= 2:
                    continue
                parents_list = entry.get("parents") or []
                if not isinstance(parents_list, list) or not parents_list:
                    continue
                immediate_parent = parents_list[-1] if parents_list else None
                if immediate_parent and immediate_parent.get("code") == parent_code:
                    children_items.append({"code": code_value, "title": entry.get("title"), "level": level})
            children_items.sort(key=lambda e: e["code"])  # deterministic ordering
            return self._json_response({"status": "ok", "items": children_items, "parent": parent_code, "count": len(children_items)})
        if path.startswith(prefix):
            code = path[len(prefix):]
            start_lookup = time.perf_counter()
            entry = self._naics_lookup(code)
            duration_ms = (time.perf_counter() - start_lookup) * 1000.0
            if not entry:
                if emit_event:
                    try:
                        emit_event("naics:code_miss", {"code": code, "duration_ms": round(duration_ms, 2)})
                    except Exception:  # pragma: no cover
                        LOGGER.debug("Failed to emit naics:code_miss", exc_info=True)
                return self._json_response({"status": "not_found", "code": code}, status="404 Not Found")
            if emit_event:
                try:
                    emit_event(
                        "naics:code_hit",
                        {"code": entry.get("code"), "level": entry.get("level"), "duration_ms": round(duration_ms, 2)},
                    )
                except Exception:  # pragma: no cover
                    LOGGER.debug("Failed to emit naics:code_hit", exc_info=True)
            return self._json_response({"status": "ok", "entry": entry})
        if path.startswith(search_prefix):
            from urllib.parse import parse_qs
            qs = environ.get("QUERY_STRING") or ""
            parsed = parse_qs(qs, keep_blank_values=False)
            query_list = parsed.get("q", [])
            query = query_list[0] if query_list else ""
            ref = self._load_naics_reference()
            items: list[dict] = []
            q_norm = query.strip().lower()
            start_search = time.perf_counter()
            if q_norm:
                # Fast path: purely digit prefix queries leverage prefix index
                if q_norm.isdigit() and 2 <= len(q_norm) <= 6:
                    try:
                        pref_results = self._naics_prefix_search(q_norm, limit=50)
                        for e in pref_results:
                            items.append({
                                "code": e.get("code"),
                                "title": e.get("title"),
                                "level": e.get("level"),
                            })
                    except Exception:  # pragma: no cover
                        LOGGER.debug("Prefix search failure", exc_info=True)
                # Fallback / title substring if no prefix hits or non-digit query
                if not items:
                    # Attempt cache lookup first (non-numeric queries)
                    cached = None
                    for k, v in self._naics_search_cache:
                        if k == q_norm:
                            cached = v
                            break
                    if cached is not None:
                        items.extend(cached)
                    else:
                        scored: list[tuple[float, dict]] = []
                        tokens = [t for t in q_norm.split() if t]

                        def _lev(a: str, b: str) -> int:
                            if a == b:
                                return 0
                            if not a:
                                return len(b)
                            if not b:
                                return len(a)
                            # simple DP; strings short (titles tokens) so fine
                            dp = list(range(len(b) + 1))
                            for i, ca in enumerate(a, 1):
                                prev = dp[0]
                                dp[0] = i
                                for j, cb in enumerate(b, 1):
                                    cur = dp[j]
                                    if ca == cb:
                                        dp[j] = prev
                                    else:
                                        dp[j] = 1 + min(prev, dp[j], dp[j - 1])
                                    prev = cur
                            return dp[-1]

                        for entry in ref.values():
                            title = str(entry.get("title") or "").lower()
                            code_value = str(entry.get("code") or "")
                            if code_value.startswith(q_norm) or q_norm in title:
                                score = 0.0  # best direct match
                            else:
                                # token-based fuzzy: compute min lev distance among tokens
                                title_tokens = [t for t in title.replace('/', ' ').split() if t]
                                if not tokens:
                                    continue
                                # aggregated distance normalized by token lengths
                                dist = 0.0
                                for qt in tokens:
                                    best = min((_lev(qt, tt) for tt in title_tokens), default=len(qt))
                                    dist += best / max(len(qt), 1)
                                score = dist / len(tokens)
                                if score > 0.75:  # prune weak fuzzy matches
                                    continue
                            scored.append((score, {
                                "code": entry.get("code"),
                                "title": entry.get("title"),
                                "level": entry.get("level"),
                            }))
                        scored.sort(key=lambda x: (x[0], x[1]["code"]))
                        for s, rec in scored[:50]:
                            items.append(rec)
                        # update cache (simple LRU by append & trim)
                        self._naics_search_cache.append((q_norm, items.copy()))
                        if len(self._naics_search_cache) > self._naics_search_cache_capacity:
                            self._naics_search_cache = self._naics_search_cache[-self._naics_search_cache_capacity:]
            duration_ms = (time.perf_counter() - start_search) * 1000.0
            if emit_event:
                try:
                    emit_event(
                        "naics:search",
                        {
                            "query": query,
                            "count": len(items),
                            "duration_ms": round(duration_ms, 2),
                            "digit_prefix": bool(q_norm.isdigit()),
                            "cache_hit": any(k == q_norm for k,_ in self._naics_search_cache[-1:]) if q_norm else False,
                        },
                    )
                except Exception:  # pragma: no cover
                    LOGGER.debug("Failed to emit naics:search event", exc_info=True)
            return self._json_response({"status": "ok", "items": items, "query": query, "count": len(items)})
        return self._json_response(
            {"status": "not_found", "message": f"Unknown NAICS path: {path}"},
            status="404 Not Found",
        )


    def serve(self, host: str | None = None, port: int | None = None) -> None:
        host_value = (host or os.getenv("HOST") or "127.0.0.1").strip() or "127.0.0.1"
        port_value = port if port is not None else os.getenv("PORT", "5000")
        try:
            port_number = int(port_value)
        except (TypeError, ValueError):
            LOGGER.warning("Invalid port value %s; defaulting to 5000", port_value)
            port_number = 5000
        server = make_server(host_value, port_number, self.wsgi_app)
        LOGGER.info("Serving intake app on http://%s:%s", host_value, port_number)
        LOGGER.info("Health check available at http://%s:%s/healthz", host_value, port_number)
        LOGGER.info("Press CTRL+C to stop the server. Profiles saved to %s", self.profile_path)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            LOGGER.info("Shutting down intake server.")
        finally:
            server.server_close()


def create_app(base_dir: Path | None = None) -> IntakeApplication:
    """Factory used by tests and CLI tooling."""

    return IntakeApplication(base_dir=base_dir)


if __name__ == "__main__":  # pragma: no cover - manual execution helper
    create_app().serve()
