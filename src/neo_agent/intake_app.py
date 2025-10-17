"""HTTP server for the Project NEO agent intake experience."""

from __future__ import annotations

import html
import json
import os
import time
from pathlib import Path
import csv
from string import Template
from typing import Any, Dict, Iterable, List, Mapping, Optional
from urllib.parse import parse_qs

from wsgiref.simple_server import make_server

from .linkedin import scrape_linkedin_profile
from .logging import get_logger
from .repo_generator import AgentRepoGenerationError, generate_agent_repo
from .spec_generator import generate_agent_specs

try:  # pragma: no cover - telemetry is optional in some environments
    from .telemetry import (
        emit_event,
        emit_mbti_persona_selected,
        emit_repo_generated_event,
    )
except Exception:  # pragma: no cover - fall back gracefully when telemetry unavailable
    emit_event = None
    emit_mbti_persona_selected = None
    emit_repo_generated_event = None

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

CURATED_DOMAIN_FALLBACK: Dict[str, List[str]] = {
    "Sector Domains": [
        "Advanced Manufacturing",
        "Financial Services & Fintech",
        "Healthcare Providers",
        "Technology & SaaS Platforms",
        "Public Sector & Education",
    ],
    "Strategic Functions": [
        "AI Strategy & Governance",
        "Workflow Orchestration",
        "Observability & Telemetry",
    ],
    "Operational Functions": [
        "Revenue Operations",
        "Supply Chain Optimization",
        "Customer Experience",
        "Field Operations",
    ],
    "Innovation Tracks": [
        "R&D / Product Innovation",
        "Agent Safety & Compliance",
        "Knowledge Automation",
    ],
}



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


def _option_list(
    options: Iterable[str], *, selected: Optional[str] = None
) -> str:
    selected_value = str(selected) if selected is not None else None
    rendered: list[str] = []
    for option in options:
        value = str(option)
        attrs = " selected" if selected_value is not None and value == selected_value else ""
        rendered.append(
            f'<option value="{html.escape(value, quote=True)}"{attrs}>'
            f"{html.escape(value)}"
            "</option>"
        )
    return "\n".join(rendered)


def _checkboxes(
    name: str,
    options: Iterable[str],
    *,
    selected: Optional[Iterable[str] | str] = None,
) -> str:
    if selected is None:
        selected_set: set[str] = set()
    elif isinstance(selected, str):
        selected_set = {selected}
    else:
        selected_set = {str(item) for item in selected}
    chunks: list[str] = []
    for option in options:
        value = str(option)
        checked = " checked" if value in selected_set else ""
        chunks.append(
            f'<label><input type="checkbox" name="{html.escape(name, quote=True)}" '
            f'value="{html.escape(value, quote=True)}"{checked}> '
            f"{html.escape(value)}</label>"
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
            .generate-agent { display: flex; justify-content: flex-end; margin-top: 1rem; }
$persona_styles
$extra_styles
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
                    <input type="text" name="agent_name" placeholder="e.g., Atlas Analyst" value="$agent_name" required>
                </label>
                <label>Version
                    <input type="text" name="agent_version" value="$agent_version">
                </label>
            </fieldset>

            <fieldset>
                <legend>Business Context</legend>
                <input type="hidden" name="naics_code" value="$naics_code">
                <input type="hidden" name="naics_title" value="$naics_title">
                <input type="hidden" name="naics_level" value="$naics_level">
                <input type="hidden" name="naics_lineage_json" value="$naics_lineage">
                $naics_selector_html
                <input type="hidden" name="domain_selector" value="$domain_selector_state" data-hidden-domain-selector>
                $domain_selector_html
            </fieldset>

            <fieldset>
                <legend>Business Function & Role</legend>
                <input type="hidden" name="function_category" value="$function_category">
                <input type="hidden" name="function_specialties_json" value="$function_specialties">
                $function_select_html
                $function_role_html
                <div class="generate-agent">
                    <button type="button" data-generate-agent disabled>Generate Agent Repo</button>
                </div>
            </fieldset>

            <fieldset>
                <legend>Persona Alignment</legend>
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
                    <input type="text" name="custom_toolsets" placeholder="e.g., Knowledge Graphing, Scenario Planning" value="$custom_toolsets">
                </label>
            </fieldset>

            <fieldset>
                <legend>Attributes & Traits</legend>
                <div class="options">
                    $attribute_checkboxes
                </div>
                <label>Custom Attributes (comma separated)
                    <input type="text" name="custom_attributes" placeholder="e.g., Customer obsessed, Pattern matcher" value="$custom_attributes">
                </label>
            </fieldset>

            <fieldset>
                <legend>Preferences</legend>
                <label>Autonomy Level <span class="slider-value" id="autonomy_value">$autonomy_value</span>
                    <input type="range" min="0" max="100" value="$autonomy_value" name="autonomy" oninput="updateSliderValue('autonomy_value', this.value)">
                </label>
                <label>Confidence Level <span class="slider-value" id="confidence_value">$confidence_value</span>
                    <input type="range" min="0" max="100" value="$confidence_value" name="confidence" oninput="updateSliderValue('confidence_value', this.value)">
                </label>
                <label>Collaboration Level <span class="slider-value" id="collaboration_value">$collaboration_value</span>
                    <input type="range" min="0" max="100" value="$collaboration_value" name="collaboration" oninput="updateSliderValue('collaboration_value', this.value)">
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
                    <input type="url" name="linkedin_url" placeholder="https://www.linkedin.com/in/example" value="$linkedin_url">
                </label>
            </fieldset>

            <fieldset>
                <legend>Custom Notes</legend>
                <label>Engagement Notes
                    <textarea name="notes" rows="4" placeholder="Outline constraints, knowledge packs, or workflow context.">$notes</textarea>
                </label>
            </fieldset>

            <button type="submit">Generate Agent Profile</button>
        </form>

        $summary
        <script type="module">
$persona_script
        </script>
        <script>
$function_role_bootstrap
        </script>
        <script>
$domain_bundle_script
        </script>
        <script>
$function_role_script
        </script>
        <script>
$generate_agent_script
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

    MAX_BODY_BYTES = 1_048_576

    def __init__(self, base_dir: Path | None = None) -> None:
        self.project_root = Path(__file__).resolve().parents[2]
        self.assets_root = self.project_root / "src"
        self.ui_dir = self.assets_root / "ui"
        self.persona_dir = self.assets_root / "persona"
        self.static_dir = self.assets_root / "neo_agent" / "static"
        self.data_root = self.project_root / "data"
        self.naics_path = self.data_root / "naics" / "naics_2022.json"
        self.naics_sample_path = self.data_root / "naics" / "naics_2022.sample.json"
        self.functions_catalog_path = self.data_root / "functions" / "functions_catalog.json"
        self.business_functions_path = self.data_root / "functions" / "business_functions.json"
        self.role_catalog_path = self.data_root / "roles" / "role_catalog.json"
        self.routing_defaults_path = self.data_root / "routing" / "function_role_map.json"
        self.base_dir = self._resolve_base_dir(base_dir)
        self.profile_path = self.base_dir / "agent_profile.json"
        self.spec_dir = self.base_dir / "generated_specs"
        self.spec_dir.mkdir(parents=True, exist_ok=True)
        self.repo_output_dir = self.base_dir / "generated_repos"
        self.repo_output_dir.mkdir(parents=True, exist_ok=True)
        self.persona_state_path = self.base_dir / "persona_state.json"
        self.persona_assets = self._load_persona_assets()
        self.persona_config = self._load_persona_config()
        self.mbti_lookup = self._index_mbti_types(self.persona_config.get("mbti_types", []))
        # NAICS caches (filled on-demand)
        self._naics_cache = None
        self._naics_by_code = None
        self._function_role_data = self._load_function_role_data()
        self._domain_selector_html = self._safe_read_text(self.ui_dir / "domain_selector.html")
        self._domain_selector_css = self._safe_read_text(self.ui_dir / "domain_selector.css")
        self._domain_selector_js = self._safe_read_text(self.ui_dir / "domain_selector.js")
        self._domain_bundle_css = self._safe_read_text(self.ui_dir / "domain_bundle.css")
        self._domain_bundle_js = self._safe_read_text(self.ui_dir / "domain_bundle.js")
        self._domain_selector_assets = self._load_domain_selector_assets()
        self._function_select_html = self._safe_read_text(self.ui_dir / "function_select.html")
        self._function_role_html = self._safe_read_text(self.ui_dir / "function_role_picker.html")
        self._function_role_css = self._safe_read_text(self.ui_dir / "function_role.css")
        self._function_role_js = self._safe_read_text(self.ui_dir / "function_role.js")
        self._generate_agent_js = self._safe_read_text(self.ui_dir / "generate_agent.js")
        self._naics_selector_html = self._safe_read_text(self.ui_dir / "naics_selector.html")
        LOGGER.debug("Loaded function/role assets: functions=%d roles=%d",
                     len(self._function_role_data.get("functions", [])),
                     len(self._function_role_data.get("roles", [])))
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
        """Read a text asset safely, tolerating mixed encodings.

        Prefer UTFÃƒÆ’Ã…Â½ÃƒÂ¢Ã¢â€šÂ¬Ã…â€œÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¦8. If the file contains stray bytes (e.g., smart quotes
        pasted from Word), fall back to decoding with replacement so the app
        does not crash during initialisation.
        """
        if not path.exists():
            if not hasattr(self, "_warned_once"):
                self._warned_once = set()
            key = f"missing_text:{path}"
            if key not in self._warned_once:
                LOGGER.warning("Asset missing: %s", path)
                self._warned_once.add(key)
            return ""
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                raw = path.read_bytes()
                text = raw.decode("utf-8", errors="replace")
                if not hasattr(self, "_warned_once"):
                    self._warned_once = set()
                key = f"non_utf8:{path}"
                if key not in self._warned_once:
                    LOGGER.warning("Non-UTF-8 characters in %s; replaced invalid bytes", path)
                    self._warned_once.add(key)
                return text
            except Exception:
                LOGGER.exception("Failed to read text at %s", path)
                return ""

    def _safe_read_json(self, path: Path, default: Any) -> Any:
        if not path.exists():
            if not hasattr(self, "_warned_once"):
                self._warned_once = set()
            key = f"missing_json:{path}"
            if key not in self._warned_once:
                LOGGER.warning("Config missing: %s", path)
                self._warned_once.add(key)
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            # Retry with UTF-8 BOM tolerant decoding, then fall back to default
            try:
                raw = path.read_bytes()
                text = raw.decode("utf-8-sig")  # strips BOM if present
                return json.loads(text)
            except Exception:
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

    def _load_function_role_data(self) -> dict[str, Any]:
        """Load function/role data with resilient fallbacks.

        Builds a unified set of business functions from multiple sources:
        - data/functions/business_functions.json (preferred explicit list)
        - keys from data/functions/functions_catalog.json values (flattened)
        - distinct values of the "function" field in data/roles/role_catalog.json

        Any missing files are tolerated; the union is de-duplicated and
        sorted for stable UI rendering.
        """
        # Load raw sources (tolerate missing files)
        functions_raw = self._safe_read_json(self.business_functions_path, [])
        if not isinstance(functions_raw, list):
            functions_raw = []

        roles_raw = self._safe_read_json(self.role_catalog_path, [])
        if not isinstance(roles_raw, list):
            roles_raw = []

        routing_defaults = self._safe_read_json(self.routing_defaults_path, {})
        if not isinstance(routing_defaults, Mapping):
            routing_defaults = {}

        function_catalog = self._safe_read_json(self.functions_catalog_path, {})
        if not isinstance(function_catalog, Mapping):
            function_catalog = {}

        # Build allowed set from role catalog and routing default keys
        role_functions: set[str] = set()
        try:
            for role in roles_raw:
                if isinstance(role, Mapping):
                    fn = role.get("function")
                    if fn:
                        role_functions.add(str(fn))
        except Exception:
            pass

        default_functions: set[str] = set()
        try:
            for key in routing_defaults.keys():
                default_functions.add(str(key))
        except Exception:
            pass

        allowed: set[str] = role_functions.union(default_functions)

        # Aggregate candidate names
        candidates: set[str] = set()
        for item in functions_raw:
            try:
                if item:
                    candidates.add(str(item))
            except Exception:
                continue
        try:
            for value in function_catalog.values():
                if isinstance(value, list):
                    for entry in value:
                        if entry:
                            candidates.add(str(entry))
        except Exception:
            pass
        # Always include the allowed functions from roles/defaults
        candidates |= allowed

        # If we have an allow-list (from roles/defaults), filter candidates to it; otherwise keep candidates
        if allowed:
            final_functions = sorted({name for name in candidates if name in allowed}, key=lambda s: s.lower())
        else:
            final_functions = sorted(candidates, key=lambda s: s.lower())

        # Log a brief summary for diagnostics
        try:
            LOGGER.debug(
                "Function/role data loaded: functions_raw=%d, catalog_groups=%d, roles=%d, union=%d",
                len(functions_raw),
                len(function_catalog) if isinstance(function_catalog, Mapping) else 0,
                len(roles_raw),
                len(final_functions),
            )
        except Exception:
            pass

        return {
            "functions": final_functions,
            "roles": roles_raw,
            "functionDefaults": routing_defaults,
            "catalog": function_catalog,
        }

    def _load_domain_selector_assets(self) -> dict[str, Any]:
        curated_path = self.data_root / "catalog" / "domains_curated.json"
        curated_raw = self._safe_read_json(curated_path, CURATED_DOMAIN_FALLBACK)
        curated: dict[str, list[str]] = {}
        if isinstance(curated_raw, Mapping):
            for key, value in curated_raw.items():
                if isinstance(value, list):
                    curated[str(key)] = [str(item) for item in value]
        if not curated:
            curated = {key: list(values) for key, values in CURATED_DOMAIN_FALLBACK.items()}
        if "Sector Domains" not in curated:
            curated["Sector Domains"] = list(CURATED_DOMAIN_FALLBACK.get("Sector Domains", []))
        return {
            "html": self._domain_selector_html,
            "css": self._domain_selector_css,
            "bundle_css": self._domain_bundle_css,
            "js": self._domain_selector_js,
            "bundle_js": self._domain_bundle_js,
            "curated": curated,
        }

    # Rendering helpers -------------------------------------------------
    def render_form(
        self,
        *,
        message: str | None = None,
        profile: Mapping[str, Any] | None = None,
    ) -> str:
        if not isinstance(profile, Mapping):
            profile = {}
        agent_section_candidate = profile.get("agent") if isinstance(profile, Mapping) else None
        agent_section = agent_section_candidate if isinstance(agent_section_candidate, Mapping) else {}
        toolset_section_candidate = profile.get("toolsets") if isinstance(profile, Mapping) else None
        toolset_section = (
            toolset_section_candidate if isinstance(toolset_section_candidate, Mapping) else {}
        )
        attribute_section_candidate = profile.get("attributes") if isinstance(profile, Mapping) else None
        attribute_section = (
            attribute_section_candidate if isinstance(attribute_section_candidate, Mapping) else {}
        )
        preferences_section_candidate = profile.get("preferences") if isinstance(profile, Mapping) else None
        preferences_section = (
            preferences_section_candidate if isinstance(preferences_section_candidate, Mapping) else {}
        )

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
        sliders_candidate = preferences_section.get("sliders") if isinstance(preferences_section, Mapping) else None
        if not isinstance(profile, Mapping):
            profile = {}

        slider_section = sliders_candidate if isinstance(sliders_candidate, Mapping) else {}

        def _str(value: Any, default: str = "") -> str:
            return str(value) if value is not None else default

        persona_hidden = ""
        if isinstance(profile, Mapping):
            persona_block = profile.get("persona")
            if isinstance(persona_block, Mapping):
                agent_persona_block = persona_block.get("agent")
                if isinstance(agent_persona_block, Mapping):
                    persona_hidden = _str(agent_persona_block.get("code", ""))
            if not persona_hidden:
                persona_hidden = _str(agent_section.get("persona", ""))

        selected_toolsets = toolset_section.get("selected", []) if isinstance(toolset_section, Mapping) else []
        selected_attributes = attribute_section.get("selected", []) if isinstance(attribute_section, Mapping) else []
        custom_toolsets_value = ", ".join(toolset_section.get("custom", [])) if isinstance(toolset_section, Mapping) else ""
        custom_attributes_value = ", ".join(attribute_section.get("custom", [])) if isinstance(attribute_section, Mapping) else ""

        autonomy_value = int(slider_section.get("autonomy", 50) or 50)
        confidence_value = int(slider_section.get("confidence", 50) or 50)
        collaboration_value = int(slider_section.get("collaboration", 50) or 50)

        communication_style = preferences_section.get("communication_style") if isinstance(preferences_section, Mapping) else None
        collaboration_mode = preferences_section.get("collaboration_mode") if isinstance(preferences_section, Mapping) else None

        linkedin_section = profile.get("linkedin", {}) if isinstance(profile, Mapping) else {}
        linkedin_url = ""
        if isinstance(linkedin_section, Mapping):
            linkedin_url = _str(linkedin_section.get("url") or linkedin_section.get("profile") or "")

        domain_selector_state = ""
        if isinstance(agent_section, Mapping) and isinstance(agent_section.get("domain_selector"), Mapping):
            domain_selector_state = json.dumps(agent_section["domain_selector"], ensure_ascii=False)
        elif isinstance(profile, Mapping) and isinstance(profile.get("domain_selector"), Mapping):
            domain_selector_state = json.dumps(profile["domain_selector"], ensure_ascii=False)

        naics_section: Mapping[str, Any] | None = None
        if isinstance(profile, Mapping):
            candidate = profile.get("naics")
            if isinstance(candidate, Mapping):
                naics_section = candidate
            else:
                classification = profile.get("classification")
                if isinstance(classification, Mapping):
                    nested = classification.get("naics")
                    if isinstance(nested, Mapping):
                        naics_section = nested

        naics_code = naics_section.get("code", "") if naics_section else ""
        naics_title = naics_section.get("title", "") if naics_section else ""
        naics_level = naics_section.get("level", "") if naics_section else ""
        naics_lineage = ""
        if naics_section and isinstance(naics_section.get("lineage"), list):
            naics_lineage = json.dumps(naics_section["lineage"], ensure_ascii=False)

        business_function = _str(profile.get("business_function") or agent_section.get("business_function") or "")
        role_payload = profile.get("role") if isinstance(profile, Mapping) else None
        if not isinstance(role_payload, Mapping):
            role_payload = agent_section.get("role") if isinstance(agent_section, Mapping) else {}
        if isinstance(role_payload, str):
            role_payload = {"title": role_payload, "code": role_payload}
        role_payload = role_payload if isinstance(role_payload, Mapping) else {}

        routing_defaults = profile.get("routing_defaults") if isinstance(profile, Mapping) else None
        if not isinstance(routing_defaults, Mapping):
            routing_defaults = profile.get("routing_hints") if isinstance(profile, Mapping) else None
        routing_defaults = routing_defaults if isinstance(routing_defaults, Mapping) else {}

        # Merge routing defaults with precedence: baseline < function < role
        try:
            fr_data = self._function_role_data if isinstance(self._function_role_data, Mapping) else {}
            fr_map = fr_data.get("functionDefaults") if isinstance(fr_data.get("functionDefaults"), Mapping) else {}
            baseline_defaults = fr_map.get("baseline") or fr_map.get("_baseline") or {}
            baseline_defaults = baseline_defaults if isinstance(baseline_defaults, Mapping) else {}
            func_defaults = fr_map.get(business_function) if business_function else None
            func_defaults = func_defaults if isinstance(func_defaults, Mapping) else {}
            roles_catalog = fr_data.get("roles") if isinstance(fr_data.get("roles"), list) else []
            role_code_value = _str(role_payload.get("code", ""))
            role_defaults = {}
            if role_code_value:
                for r in roles_catalog:
                    if isinstance(r, Mapping) and _str(r.get("code", "")) == role_code_value:
                        cand = r.get("defaults")
                        if isinstance(cand, Mapping):
                            role_defaults = cand
                        break
            effective_defaults: dict[str, Any] = {}
            for source in (baseline_defaults, func_defaults, role_defaults):
                if isinstance(source, Mapping):
                    effective_defaults.update(source)
        except Exception:
            effective_defaults = {}

        function_category = _str(profile.get("function_category") or agent_section.get("function_category") or "")
        function_specialties = profile.get("function_specialties")
        if not isinstance(function_specialties, list):
            function_specialties = []
        function_specialties_json = json.dumps(function_specialties, ensure_ascii=False) if function_specialties else ""

        function_role_state = {
            "business_function": business_function,
            "role_code": _str(role_payload.get("code", "")),
            "role_title": _str(role_payload.get("title", "")),
            "role_seniority": _str(role_payload.get("seniority", "")),
            "routing_defaults_json": (
                json.dumps(routing_defaults, ensure_ascii=False)
                if routing_defaults
                else (json.dumps(effective_defaults, ensure_ascii=False) if effective_defaults else "")
            ),
        }

        function_role_bootstrap = self._indent_block(
            "\n".join(
                [
                    "window.__FUNCTION_ROLE_DATA__ = " + json.dumps(self._function_role_data, ensure_ascii=False) + ";",
                    "window.__FUNCTION_ROLE_STATE__ = " + json.dumps(function_role_state, ensure_ascii=False) + ";",
                ]
            ),
            spaces=4,
        )

        extra_styles = self._indent_block(
            "\n".join(
                part
                for part in (
                    self._domain_selector_assets.get("css"),
                    self._domain_selector_assets.get("bundle_css"),
                    self._function_role_css,
                )
                if part
            ),
        )

        domain_selector_html = self._indent_block(self._domain_selector_assets.get("html", ""), spaces=8)
        naics_selector_html = self._indent_block(self._naics_selector_html, spaces=8)
        function_select_html = self._indent_block(self._function_select_html, spaces=8)
        # Pre-populate business function options server-side as a resilient fallback
        # so the picker is usable even if client JS fails to execute.
        fr_html_raw = self._function_role_html
        try:
            marker = '<option value="">Select a business function</option>'
            if marker in fr_html_raw:
                fn_list = self._function_role_data.get("functions", [])
                if isinstance(fn_list, list) and fn_list:
                    selected_fn = business_function
                    def _opt(label: str) -> str:
                        sel = ' selected' if selected_fn and str(selected_fn) == str(label) else ''
                        return f'<option value="{html.escape(str(label), quote=True)}"{sel}>{html.escape(str(label))}</option>'
                    extra_opts = "\n".join(_opt(fn) for fn in fn_list)
                    fr_html_raw = fr_html_raw.replace(marker, marker + "\n" + extra_opts, 1)
            # Also pre-populate role options for the currently selected function (if any).
            # Do NOT prepopulate with all roles by default; we prefer a disabled select
            # until the user chooses a business function so the list stays scoped.
            selected_fn_norm = (business_function or "").strip().lower().replace("&", "&")
            role_default_marker = '<option value="">Select a role</option>'
            roles_src = self._function_role_data.get("roles", [])
            roles_for_select: list[dict[str, Any]] = []
            if isinstance(roles_src, list) and selected_fn_norm:
                for r in roles_src:
                    if not isinstance(r, Mapping):
                        continue
                    rf = str(r.get("function", "")).strip().lower().replace("&", "&")
                    if rf == selected_fn_norm:
                        roles_for_select.append(r)
            if selected_fn_norm and roles_for_select:
                # Enable the select (remove disabled) and inject options
                fr_html_raw = fr_html_raw.replace('data-role-select disabled', 'data-role-select')
                def _role_label(role: Mapping[str, Any]) -> str:
                    titles = role.get("titles") if isinstance(role.get("titles"), list) else []
                    primary = titles[0] if titles else ""
                    code = role.get("code") or ""
                    label = (str(primary) + (f" ({code})" if code else "")).strip() or str(code)
                    return label
                # Sort by label for stable UI
                roles_for_select.sort(key=lambda r: _role_label(r).lower())
                role_opts = []
                current_code = _str(role_payload.get("code", "")) if isinstance(role_payload, Mapping) else ""
                for r in roles_for_select:
                    code = html.escape(str(r.get("code", "")), quote=True)
                    label = html.escape(_role_label(r))
                    sel = ' selected' if current_code and str(r.get("code", "")) == current_code else ''
                    role_opts.append(f'<option value="{code}"{sel}>{label}</option>')
                if role_default_marker in fr_html_raw:
                    fr_html_raw = fr_html_raw.replace(role_default_marker, role_default_marker + "\n" + "\n".join(role_opts), 1)
        except Exception:
            # If anything goes wrong, keep the original template and rely on JS init.
            pass

        function_role_html = self._indent_block(fr_html_raw, spaces=8)

        domain_bundle_script = self._indent_block(
            "\n".join(
                part
                for part in (
                    self._domain_selector_assets.get("js"),
                    self._domain_selector_assets.get("bundle_js"),
                )
                if part
            ),
            spaces=4,
        )
        # Finalise options and HTML substitution for the intake form
        agent_name = _str(agent_section.get("name", ""))
        agent_version = _str(agent_section.get("version", "1.0.0")) or "1.0.0"
        notes_value = _str(profile.get("notes") if isinstance(profile, Mapping) else "")

        communication_options = _option_list(COMMUNICATION_STYLES, selected=communication_style)
        collaboration_options = _option_list(COLLABORATION_MODES, selected=collaboration_mode)
        domain_options = _option_list(DOMAINS, selected=agent_section.get("domain"))
        role_options = _option_list(ROLES, selected=agent_section.get("role"))

        toolset_checkboxes = _checkboxes("toolsets", TOOLSETS, selected=selected_toolsets)
        attribute_checkboxes = _checkboxes("attributes", ATTRIBUTES, selected=selected_attributes)

        generate_agent_script = self._indent_block(self._generate_agent_js, spaces=8)
        function_role_script = self._indent_block(self._function_role_js, spaces=8)

        summary_html = _summary_block(profile if isinstance(profile, Mapping) else None, str(self.profile_path), str(self.spec_dir))

        html_out = FORM_TEMPLATE.substitute(
            persona_styles=self._indent_block(persona_style_block),
            extra_styles=extra_styles,
            notice=_notice(message),
            domain_options=domain_options,
            role_options=role_options,
            persona_tabs=persona_html,
            persona_hidden_value=html.escape(persona_hidden, quote=True),
            domain_selector_state=html.escape(domain_selector_state, quote=True),
            naics_code=html.escape(str(naics_code), quote=True),
            naics_title=html.escape(str(naics_title), quote=True),
            naics_level=html.escape(str(naics_level), quote=True),
            naics_lineage=html.escape(str(naics_lineage), quote=True),
            domain_selector_html=domain_selector_html,
            naics_selector_html=naics_selector_html,
            function_category=html.escape(function_category, quote=True),
            function_specialties=function_specialties_json,
            function_select_html=function_select_html,
            function_role_html=function_role_html,
            toolset_checkboxes=toolset_checkboxes,
            attribute_checkboxes=attribute_checkboxes,
            custom_toolsets=html.escape(custom_toolsets_value, quote=True),
            custom_attributes=html.escape(custom_attributes_value, quote=True),
            autonomy_value=autonomy_value,
            confidence_value=confidence_value,
            collaboration_value=collaboration_value,
            communication_options=communication_options,
            collaboration_options=collaboration_options,
            linkedin_url=html.escape(linkedin_url, quote=True),
            notes=html.escape(notes_value),
            summary=summary_html,
            persona_script=self._indent_block(persona_script, spaces=8),
            function_role_bootstrap=function_role_bootstrap,
            domain_bundle_script=domain_bundle_script,
            function_role_script=function_role_script,
            generate_agent_script=generate_agent_script,
            agent_name=html.escape(agent_name, quote=True),
            agent_version=html.escape(agent_version, quote=True),
        )
        return html_out

    def _build_profile(
        self,
        data: Mapping[str, Any],
        linkedin: Mapping[str, Any] | None = None,
    ) -> Dict[str, Any]:
        def _get(name: str, default: str = "") -> str:
            values = data.get(name, []) if isinstance(data, Mapping) else []
            if isinstance(values, list):
                return values[0] if values else default
            try:
                return str(values)
            except Exception:
                return default

        def _getlist(name: str) -> List[str]:
            values = data.get(name, []) if isinstance(data, Mapping) else []
            return [str(v) for v in values] if isinstance(values, list) else []

        def _parse_json(name: str) -> Any:
            raw = _get(name)
            if not raw:
                return None
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                LOGGER.debug("Failed to parse JSON payload for field %s", name, exc_info=True)
                return None

        linkedin = linkedin or {}

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
            derived_tools = linkedin.get("skills", []) if isinstance(linkedin.get("skills"), list) else []
            for tool in derived_tools:
                candidate = str(tool).title()
                if candidate not in profile["toolsets"]["selected"]:
                    profile["toolsets"]["selected"].append(candidate)

            derived_roles = linkedin.get("roles", []) if isinstance(linkedin.get("roles"), list) else []
            if derived_roles and not profile["agent"].get("role"):
                profile["agent"]["role"] = str(derived_roles[0]).title()

        domain_selector_payload = _parse_json("domain_selector")
        if isinstance(domain_selector_payload, Mapping):
            profile["agent"]["domain_selector"] = dict(domain_selector_payload)
            profile["domain_selector"] = dict(domain_selector_payload)

        naics_code = _get("naics_code").strip()
        naics_title = _get("naics_title").strip()
        naics_level_raw = _get("naics_level").strip()
        naics_lineage_payload = _parse_json("naics_lineage_json")
        if naics_code:
            try:
                level_value = int(naics_level_raw) if naics_level_raw else None
            except ValueError:
                level_value = None
            lineage: list[Any] = []
            if isinstance(naics_lineage_payload, list):
                for node in naics_lineage_payload:
                    if isinstance(node, Mapping):
                        lineage.append({
                            "code": str(node.get("code", "")),
                            "title": str(node.get("title", "")),
                            "level": node.get("level"),
                        })
                    elif isinstance(node, str):
                        lineage.append({"code": node})
            naics_payload = {
                "code": naics_code,
                "title": naics_title,
                "level": level_value,
                "lineage": lineage,
            }
            profile["naics"] = naics_payload
            classification = profile.setdefault("classification", {})
            if isinstance(classification, Mapping):
                classification = dict(classification)
            profile["classification"] = classification
            profile["classification"]["naics"] = naics_payload

        business_function = _get("business_function").strip()
        if business_function:
            profile["business_function"] = business_function
            profile["agent"]["business_function"] = business_function

        role_code = _get("role_code").strip()
        role_title = _get("role_title").strip()
        role_seniority = _get("role_seniority").strip()
        if role_code or role_title or role_seniority:
            role_payload = {
                "code": role_code,
                "title": role_title or role_code,
                "seniority": role_seniority,
                "function": business_function or profile["agent"].get("role"),
            }
            profile["role"] = role_payload

        routing_defaults_payload = _parse_json("routing_defaults_json")
        if isinstance(routing_defaults_payload, Mapping):
            profile["routing_defaults"] = dict(routing_defaults_payload)

        function_category = _get("function_category").strip()
        if function_category:
            profile["function_category"] = function_category
            profile["agent"]["function_category"] = function_category
        specialties_payload = _parse_json("function_specialties_json")
        if isinstance(specialties_payload, list):
            parsed_specialties = [str(item) for item in specialties_payload if item]
            profile["function_specialties"] = parsed_specialties

        return profile

    # NAICS helpers ----------------------------------------------------
    def _load_naics_reference(self) -> list[dict[str, Any]]:
        if self._naics_cache is None:
            # Prefer full JSON; fall back to sample JSON; then CSV; finally a tiny built-in payload
            default_payload = [
                {"code": "54", "title": "Professional, Scientific, and Technical Services", "level": 2, "parents": []},
                {"code": "541", "title": "Professional, Scientific, and Technical Services (541)", "level": 3, "parents": [{"code": "54", "title": "Professional, Scientific, and Technical Services", "level": 2}]},
            ]
            data: Any = None
            if self.naics_path.exists():
                data = self._safe_read_json(self.naics_path, default_payload)
            elif self.naics_sample_path.exists():
                if not getattr(self, "_warned_naics_sample", False):
                    try:
                        LOGGER.warning("Using NAICS sample dataset: %s (missing %s)", self.naics_sample_path, self.naics_path)
                    except Exception:
                        pass
                    self._warned_naics_sample = True
                data = self._safe_read_json(self.naics_sample_path, default_payload)
            else:
                # CSV fallback (2-6 digit_2022_Codes.csv)
                csv_path = self.data_root / "naics" / "2-6 digit_2022_Codes.csv"
                if csv_path.exists():
                    try:
                        import csv as _csv
                        rows: list[dict[str, str]] = []
                        with csv_path.open("r", encoding="utf-8", newline="") as handle:
                            reader = _csv.DictReader(handle)
                            headers = [h.lower() for h in (reader.fieldnames or [])]
                            def pick(name_opts: list[str]) -> str | None:
                                for opt in name_opts:
                                    for h in headers:
                                        if opt in h:
                                            return [x for x in (reader.fieldnames or []) if x.lower() == h][0]
                                return None
                            code_col = pick(["code"]) or (reader.fieldnames or [""])[0]
                            title_col = pick(["title"]) or (reader.fieldnames or ["", ""])[1]
                            for r in reader:
                                code = str(r.get(code_col, "")).strip()
                                title = str(r.get(title_col, "")).strip()
                                if code and title:
                                    rows.append({"code": code, "title": title})
                        entries_tmp: list[dict[str, Any]] = []
                        index_tmp: dict[str, dict[str, Any]] = {}
                        for row in rows:
                            code = row["code"]
                            level = len(code)
                            if level < 2 or level > 6 or not code.isdigit():
                                continue
                            entry = {"code": code, "title": row["title"], "level": level, "parents": []}
                            entries_tmp.append(entry)
                            index_tmp[code] = entry
                        for entry in entries_tmp:
                            code = entry["code"]
                            parents: list[dict[str, Any]] = []
                            for lv in (2,3,4,5):
                                if lv < entry["level"]:
                                    parent = index_tmp.get(code[:lv])
                                    if parent:
                                        parents.append({"code": parent["code"], "title": parent["title"], "level": parent["level"]})
                            entry["parents"] = parents
                        data = entries_tmp
                    except Exception:
                        LOGGER.exception("Failed to parse NAICS CSV fallback at %s", csv_path)
                        data = default_payload
                else:
                    data = default_payload
            entries: list[dict[str, Any]] = []
            index: dict[str, dict[str, Any]] = {}
            items: Iterable[Any]
            if isinstance(data, Mapping):
                items = [dict({"code": key, **value}) for key, value in data.items() if isinstance(value, Mapping)]
            elif isinstance(data, list):
                items = data
            else:
                items = default_payload
            for raw in items:
                if not isinstance(raw, Mapping):
                    continue
                code = str(raw.get("code", "")).strip()
                if not code:
                    continue
                entry = dict(raw)
                level_raw = entry.get("level")
                try:
                    level_value = int(level_raw) if level_raw is not None else len(code)
                except (TypeError, ValueError):
                    level_value = len(code)
                entry["level"] = level_value
                parents = entry.get("parents")
                if isinstance(parents, list):
                    entry["parents"] = [dict(parent) for parent in parents if isinstance(parent, Mapping)]
                else:
                    entry["parents"] = []
                entry["title"] = str(entry.get("title", ""))
                entries.append(entry)
                index[code] = entry
            if not entries:
                entries = [dict(item) for item in default_payload]
                for entry in entries:
                    code = entry.get("code")
                    if code:
                        index[str(code)] = entry
            self._naics_cache = entries
            self._naics_by_code = index
        return list(self._naics_cache or [])

    def _naics_entry(self, code: str) -> dict[str, Any] | None:
        self._load_naics_reference()
        if not self._naics_by_code:
            return None
        return self._naics_by_code.get(str(code))

    @staticmethod
    def _naics_summary(entry: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "code": str(entry.get("code", "")),
            "title": str(entry.get("title", "")),
            "level": entry.get("level"),
        }

    def _naics_children(self, code: str, target_level: int | None = None) -> list[dict[str, Any]]:
        children: list[dict[str, Any]] = []
        entries = self._load_naics_reference()
        for entry in entries:
            parents = entry.get("parents")
            if not isinstance(parents, list):
                continue
            matches_parent = any(
                isinstance(parent, Mapping) and str(parent.get("code")) == str(code)
                for parent in parents
            )
            if not matches_parent:
                continue
            if target_level is not None and entry.get("level") != target_level:
                continue
            children.append(self._naics_summary(entry))
        children.sort(key=lambda item: item.get("code", ""))
        return children

    def _naics_search(self, query: str, limit: int = 25) -> list[dict[str, Any]]:
        query = (query or "").strip()
        if not query:
            return []
        entries = self._load_naics_reference()
        q_lower = query.lower()
        numeric = q_lower.isdigit()
        tokens = [token for token in q_lower.split() if token]
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for entry in entries:
            code = str(entry.get("code", ""))
            if not code or code in seen:
                continue
            haystack = f"{code} {entry.get('title', '')}".lower()
            if numeric:
                if not code.startswith(q_lower):
                    continue
            else:
                if not all(token in haystack for token in tokens):
                    continue
            results.append(self._naics_summary(entry))
            seen.add(code)
            if len(results) >= limit:
                break
        return results

    def reload_naics(self) -> int:
        self._naics_cache = None
        self._naics_by_code = None
        return len(self._load_naics_reference())

    def _naics_lineage(self, entry: Mapping[str, Any]) -> list[dict[str, Any]]:
        lineage: list[dict[str, Any]] = []
        parents = entry.get("parents")
        if isinstance(parents, list):
            for parent in parents:
                if isinstance(parent, Mapping):
                    lineage.append(self._naics_summary(parent))
                elif parent:
                    candidate = self._naics_entry(str(parent))
                    if candidate:
                        lineage.append(self._naics_summary(candidate))
        lineage.append(self._naics_summary(entry))
        return lineage

    def _handle_naics_api(self, path: str, method: str, environ: Mapping[str, Any]) -> WSGIResponse:
        if method != "GET":
            return self._method_not_allowed(["GET"])

        # Normalise path (tolerate trailing slash)
        try:
            norm_path = str(path or "").split("?")[0].rstrip("/") or "/"
        except Exception:
            norm_path = path

        if norm_path == "/api/naics/roots":
            items = [
                self._naics_summary(entry)
                for entry in self._load_naics_reference()
                if entry.get("level") == 2 and not entry.get("parents")
            ]
            items.sort(key=lambda item: item.get("code", ""))
            return self._json_response({"status": "ok", "items": items, "count": len(items)})

        if norm_path.startswith("/api/naics/code/"):
            code = norm_path.split("/api/naics/code/")[-1]
            entry = self._naics_entry(code)
            if not entry:
                return self._json_response(
                    {"status": "not_found", "code": code},
                    status="404 Not Found",
                )
            payload = dict(entry)
            payload["lineage"] = self._naics_lineage(entry)
            return self._json_response({"status": "ok", "entry": payload})

        if norm_path.startswith("/api/naics/children/"):
            parent = norm_path.split("/api/naics/children/")[-1]
            query_string = environ.get("QUERY_STRING") or ""
            try:
                params = parse_qs(query_string, keep_blank_values=False)
            except Exception:
                params = {}
            level_param = None
            if isinstance(params, Mapping):
                level_values = params.get("level") or []
                if level_values:
                    try:
                        level_param = int(str(level_values[0]))
                    except (TypeError, ValueError):
                        level_param = None
            if level_param is None and parent and parent.isdigit():
                level_param = min(len(parent) + 1, 6)
            children = self._naics_children(parent, level_param)
            return self._json_response(
                {
                    "status": "ok",
                    "items": children,
                    "parent": parent,
                    "count": len(children),
                    "level": level_param,
                }
            )

        if norm_path == "/api/naics/search":
            query_string = environ.get("QUERY_STRING") or ""
            try:
                params = parse_qs(query_string, keep_blank_values=False)
            except Exception:
                params = {}
            query = ""
            if isinstance(params, Mapping):
                values = params.get("q") or []
                if values:
                    query = str(values[0])
            start = time.perf_counter()
            # Return a generous set so UI search can populate cascades without missing candidates
            items = self._naics_search(query, limit=500)
            duration_ms = (time.perf_counter() - start) * 1000
            return self._json_response(
                {
                    "status": "ok",
                    "items": items,
                    "count": len(items),
                    "query": query,
                    "duration_ms": round(duration_ms, 2),
                }
            )

        return self._json_response(
            {"status": "not_found", "message": f"Unknown NAICS path: {norm_path}"},
            status="404 Not Found",
        )

    def _handle_agent_generate(
        self, method: str, environ: Mapping[str, Any]
    ) -> WSGIResponse:
        if method != "POST":
            return self._method_not_allowed(["POST"])
        raw = self._read_body(environ)
        if not raw:
            return self._json_response(
                {"status": "invalid", "issues": ["Missing request body"]},
                status="400 Bad Request",
            )
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            LOGGER.debug("Invalid JSON payload for agent generate", exc_info=True)
            return self._json_response(
                {"status": "invalid", "issues": [f"Invalid JSON payload: {exc}"]},
                status="400 Bad Request",
            )

        if not isinstance(payload, Mapping):
            return self._json_response(
                {"status": "invalid", "issues": ["Request payload must be a JSON object"]},
                status="400 Bad Request",
            )

        profile = payload.get("profile")
        options = payload.get("options") if isinstance(payload, Mapping) else None
        if not isinstance(profile, Mapping):
            return self._json_response(
                {"status": "invalid", "issues": ["Missing or invalid profile payload"]},
                status="400 Bad Request",
            )

        try:
            result = generate_agent_repo(profile, self.repo_output_dir, options)
        except AgentRepoGenerationError as exc:
            LOGGER.warning("Agent repo generation failed: %s", exc)
            return self._json_response(
                {"status": "invalid", "issues": [str(exc)]},
                status="400 Bad Request",
            )
        except Exception:
            LOGGER.exception("Unhandled error during agent repo generation")
            return self._json_response(
                {"status": "error", "issues": ["Unexpected error generating repo"]},
                status="500 Internal Server Error",
            )

        if emit_repo_generated_event:
            try:
                emit_repo_generated_event(result)
            except Exception:
                LOGGER.debug("Failed to emit repo generated telemetry", exc_info=True)

        return self._json_response({"status": "ok", "result": result})

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
        path = str(path or "").strip()
        norm = path.split("?", 1)[0].rstrip("/")
        # path normalized above; temporary dispatch logging removed
        if norm == "/api/naics/roots" or norm == "/api/naics/search" or norm.startswith("/api/naics/"):
            return self._handle_naics_api(path, method, environ)
        if path == "/api/domains/curated" and method == "GET":
            curated = self._domain_selector_assets.get("curated", {})
            return self._json_response({"status": "ok", "curated": curated})
        if path.startswith("/api/persona/"):
            return self._handle_persona_api(path, method, environ)
        if path == "/api/agent/generate":
            return self._handle_agent_generate(method, environ)
        if norm == "/api/function_roles" and method == "GET":
            # Scoped role lookup by business function + optional search query
            from html import unescape as _html_unescape
            qs = environ.get("QUERY_STRING", "") or ""
            params = parse_qs(qs)
            raw_fn = (params.get("fn") or [""])[0]
            raw_q = (params.get("q") or [""])[0]

            def _norm(text: str) -> str:
                return " ".join((_html_unescape(str(text or "")).strip()).split()).lower()

            target = _norm(raw_fn)
            tokens = [t for t in _norm(raw_q).split(" ") if t]

            roles = self._function_role_data.get("roles", [])
            out: list[dict[str, Any]] = []
            if isinstance(roles, list) and target:
                for r in roles:
                    if not isinstance(r, Mapping):
                        continue
                    rf = _norm(r.get("function", ""))
                    if rf != target:
                        continue
                    titles_list = r.get("titles", []) if isinstance(r.get("titles"), list) else []
                    hay = " ".join([str(r.get("code", "")), str(r.get("seniority", ""))] + [str(t) for t in titles_list]).lower()
                    if tokens and not all(t in hay for t in tokens):
                        continue
                    out.append(
                        {
                            "code": r.get("code", ""),
                            "function": r.get("function", ""),
                            "seniority": r.get("seniority", ""),
                            "titles": r.get("titles", []),
                        }
                    )
            # Deduplicate by role code
            seen: set[str] = set()
            uniq: list[dict[str, Any]] = []
            for r in out:
                code = str(r.get("code", ""))
                if code and code not in seen:
                    seen.add(code)
                    uniq.append(r)
            return self._json_response({"status": "ok", "items": uniq})
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
                # Compile a normalized view for downstream mapping (non-breaking addition)
                try:
                    from .profile_compiler import compile_profile  # lazy import to avoid start-up cost
                    compiled = compile_profile(profile)
                    profile["_compiled"] = compiled
                except Exception:
                    compiled = None
                if not self.profile_path.parent.exists():
                    self.profile_path.parent.mkdir(parents=True, exist_ok=True)
                with self.profile_path.open("w", encoding="utf-8") as handle:
                    to_write = {"version": "1.0.0"}
                    try:
                        if isinstance(profile, dict):
                            to_write.update(profile)
                    except Exception:
                        pass
                    json.dump(to_write, handle, indent=2)
                # Also write a sibling compiled profile for tools that prefer a standalone file
                if compiled is not None:
                    compiled_path = self.profile_path.with_name("agent_profile.compiled.json")
                    with compiled_path.open("w", encoding="utf-8") as handle:
                        # Include a top-level version for pack_loader compatibility
                        payload = {"version": "1.0.0"}
                        try:
                            if isinstance(compiled, dict):
                                payload.update(compiled)
                        except Exception:
                            pass
                        json.dump(payload, handle, indent=2)
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
            "version": "1.0.0",
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




