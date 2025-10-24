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
import io
import zipfile

from wsgiref.simple_server import make_server

from .linkedin import scrape_linkedin_profile
from .logging import get_logger
from .repo_generator import AgentRepoGenerationError, generate_agent_repo
from neo_build.writers import write_repo_files
from neo_build.validators import integrity_report
from neo_build.contracts import CANONICAL_PACK_FILENAMES
from .adapters.normalize_v3 import normalize_context_role
from .spec_generator import generate_agent_specs
from .services.identity_utils import generate_agent_id

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
# Build tag to help operators confirm the running code version via headers and /health
# For Intake v3 stabilization phase, expose the intake version constant in headers
INTAKE_BUILD_TAG = "v3.0"

def _read_app_version(project_root: Path) -> str:
    try:
        pyproj = project_root / "pyproject.toml"
        if pyproj.exists():
            txt = pyproj.read_text(encoding="utf-8")
            for line in txt.splitlines():
                if line.strip().startswith("version"):
                    parts = line.split("=")
                    if len(parts) >= 2:
                        return parts[1].strip().strip('"')
    except Exception:
        pass
    return "0.0.0"

def _std_headers(content_type: str, size: int, *, extra: Optional[list[tuple[str,str]]] = None) -> list[tuple[str,str]]:
    base = [
        ("Content-Type", content_type),
        ("Cache-Control", "no-store, must-revalidate"),
        ("X-NEO-Intake-Version", INTAKE_BUILD_TAG),
        ("Content-Length", str(size)),
    ]
    if extra:
        base.extend(extra)
    return base

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
            /* Build Panel styles */
            .build-panel { position: relative; margin-top: 1.5rem; padding: 1rem; background: #ffffff; border: 1px solid #dbe2ef; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.05); }
            .build-panel__header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.75rem; }
            .build-panel__title { font-size: 1.1rem; font-weight: 600; color: #112d4e; }
            .build-panel__actions { display: flex; gap: 0.5rem; }
            .build-panel__btn { background: #1f3c88; color: #fff; padding: 0.5rem 0.9rem; border: none; border-radius: 6px; cursor: pointer; font-size: 0.95rem; }
            .build-panel__btn[disabled] { opacity: 0.6; cursor: not-allowed; }
            .build-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 0.75rem; }
            .card { background: #f7f9fc; border: 1px solid #e6edf6; border-radius: 8px; padding: 0.75rem; }
            .card h3 { margin: 0 0 0.5rem 0; font-size: 0.95rem; color: #0b2545; }
            .health-chip { display: inline-flex; align-items: center; gap: 0.5rem; background: #eef2fb; border: 1px solid #dbe2ef; border-radius: 999px; padding: 0.25rem 0.6rem; font-size: 0.85rem; color: #0b2545; }
            .status-ok { color: #1b5e20; }
            .status-bad { color: #b71c1c; }
            .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace; }
            details.build-errors { max-height: 200px; overflow: auto; }
$persona_styles
$extra_styles
$build_panel_styles
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
                <label>Version
                    <input type="text" name="agent_version" value="$agent_version">
                </label>
            </fieldset>

            <fieldset>
                <legend>Identity</legend>
                <input type="hidden" name="agent_name" value="$agent_name">
                <label>Agent Name
                    <input type="text" name="identity.agent_name" placeholder="e.g., Atlas Analyst" value="$agent_name" required data-identity-agent-name>
                </label>
                <label>Display Name
                    <input type="text" name="identity.display_name" placeholder="Display name" value="$agent_name" readonly data-identity-display-name>
                </label>
                <label>Agent ID
                    <input type="text" name="identity.agent_id" placeholder="auto-generated" value="$agent_id" readonly data-identity-agent-id>
                </label>
                <input type="hidden" name="identity.agent_version" value="$agent_version">
                <label>Owners (comma separated)
                    <input type="text" name="identity.owners" placeholder="CAIO, CPA, TeamLead" value="">
                </label>
                <label><input type="checkbox" name="identity.no_impersonation" value="true" checked> No impersonation</label>
                <label>Attribution Policy
                    <select name="identity.attribution_policy">
                        <option value="original" selected>original</option>
                        <option value="derived">derived</option>
                    </select>
                </label>
                <p class="notice">ID regenerates when NAICS, Function, Role or Name changes.</p>
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
                <legend>Capabilities & Tools</legend>
                <label>Tool Connectors (JSON array)
                    <textarea name="capabilities_tools.tool_connectors_json" rows="4" placeholder='[{"name":"sharepoint","enabled":true,"scopes":["read"],"secret_ref":"SET_ME"}]'></textarea>
                </label>
                <label>Human-Gate Actions (comma separated)
                    <input type="text" name="capabilities_tools.human_gate.actions" value="">
                </label>
            </fieldset>

            <fieldset>
                <legend>Memory</legend>
                <label>Memory Scopes (comma separated)
                    <input type="text" name="memory.memory_scopes" value="">
                </label>
                <label>Initial Memory Packs (comma separated)
                    <input type="text" name="memory.initial_memory_packs" value="">
                </label>
                <label>Optional Packs (comma separated)
                    <input type="text" name="memory.optional_packs" value="">
                </label>
                <label>Data Sources (comma separated)
                    <input type="text" name="memory.data_sources" value="">
                </label>
            </fieldset>

            <fieldset>
                <legend>Governance & Evaluation</legend>
                <label>Risk Register Tags (comma separated)
                    <input type="text" name="governance_eval.risk_register_tags" value="">
                </label>
                <label>PII Flags (comma separated)
                    <input type="text" name="governance_eval.pii_flags" value="">
                </label>
                <label>Classification Default
                    <select name="governance_eval.classification_default">
                        <option value="confidential" selected>confidential</option>
                        <option value="restricted">restricted</option>
                        <option value="public">public</option>
                    </select>
                </label>
                <label>RBAC Roles (comma separated)
                    <input type="text" name="governance.rbac.roles" value="">
                </label>
            </fieldset>

            <fieldset>
                <legend>Lifecycle & KPI</legend>
                <label>Lifecycle Stage
                    <select name="lifecycle.stage">
                        <option value="dev" selected>dev</option>
                        <option value="staging">staging</option>
                        <option value="prod">prod</option>
                    </select>
                </label>
            </fieldset>

            <fieldset>
                <legend>Observability & Telemetry</legend>
                <label>Sampling Rate (0-1)
                    <input type="text" name="telemetry.sampling.rate" value="1.0">
                </label>
                <label>Sinks (comma separated)
                    <input type="text" name="telemetry.sinks" value="">
                </label>
                <label>PII Redaction Strategy
                    <select name="telemetry.pii_redaction.strategy">
                        <option value="mask" selected>mask</option>
                        <option value="hash+mask">hash+mask</option>
                    </select>
                </label>
            </fieldset>

            <fieldset>
                <legend>Custom Notes</legend>
                <label>Engagement Notes
                    <textarea name="notes" rows="4" placeholder="Outline constraints, knowledge packs, or workflow context.">$notes</textarea>
                </label>
            </fieldset>

            <fieldset>
                <legend>Advanced Overrides (JSON)</legend>
                <label>Overrides
                    <textarea name="advanced_overrides" rows="6" placeholder='{ }'></textarea>
                </label>
            </fieldset>

            <button type="submit">Generate Agent Profile</button>
        </form>

        $summary
        <section class="build-panel" id="build-panel" aria-labelledby="build-panel-title">
          <div class="build-panel__header">
            <div class="build-panel__title" id="build-panel-title">Build & Verify</div>
            <div class="build-panel__actions">
              <button type="button" class="build-panel__btn" data-build-repo>Build Repo</button>
            </div>
          </div>
          <div class="build-grid">
            <div class="card" id="health-card">
              <h3>Health</h3>
              <div class="health-chip" data-health-chip>
                <span>Schema</span>
                <strong class="mono" data-intake-schema>v3.0</strong>
                <span>• App</span>
                <strong class="mono" data-app-version>0.0.0</strong>
              </div>
              <div style="margin-top: 0.5rem; font-size: 0.85rem;">
                <div>pid: <span class="mono" data-pid>?</span></div>
                <div>output: <span class="mono" data-repo-output-dir>…</span></div>
              </div>
            </div>
            <div class="card" id="parity-card">
              <h3>Parity</h3>
              <div>02 ↔ 14: <strong data-parity-02-14 title="02_Global-Instructions vs 14_KPI targets parity">–</strong></div>
              <div>11 ↔ 02: <strong data-parity-11-02 title="11_Workflow gates vs 02 targets parity">–</strong></div>
            </div>
            <div class="card" id="integrity-card">
              <h3>Integrity</h3>
              <div>Files: <strong data-file-count>0</strong></div>
              <details class="build-errors" data-errors-details>
                <summary>Errors <span data-errors-count>(0)</span></summary>
                <ul data-errors-list></ul>
              </details>
              <details class="build-errors" data-warnings-details>
                <summary>Warnings <span data-warnings-count>(0)</span></summary>
                <ul data-warnings-list></ul>
              </details>
            </div>
            <div class="card" id="output-card">
              <h3>Output</h3>
              <div style="display:flex; align-items:center; gap:0.5rem; flex-wrap: wrap;">
                <input type="text" readonly class="mono" style="flex:1; min-width:260px; padding:0.35rem;" data-outdir value="" placeholder="Run Build to populate path">
                <a href="#" data-open-outdir style="text-decoration: underline; font-size: 0.9rem;">Open</a>
                <button type="button" class="build-panel__btn" data-copy-outdir>Copy Path</button>
              </div>
            </div>
          </div>
        </section>
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
$identity_script
        </script>
        <script>
$generate_agent_script
        </script>
        <script type="module">
$build_panel_script
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
        # New: dedicated location to store versioned agent profiles
        self.profile_output_dir = self.base_dir / "generated_profiles"
        self.profile_output_dir.mkdir(parents=True, exist_ok=True)
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
        # Build panel assets
        self._build_panel_js = self._safe_read_text(self.ui_dir / "build_panel.js")
        self._build_panel_css = self._safe_read_text(self.ui_dir / "build_panel.css")
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

    # --------------------------- Security helpers ----------------------------
    @staticmethod
    def _is_safe_subpath(root: Path, candidate: Path) -> bool:
        """Return True if candidate is the same as root or a descendant of root.

        Uses resolve() to avoid traversal via symlinks/../ components.
        """
        try:
            root_r = root.resolve()
            cand_r = candidate.resolve()
        except Exception:
            return False
        if root_r == cand_r:
            return True
        try:
            return root_r in cand_r.parents
        except Exception:
            return str(cand_r).startswith(str(root_r))

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
        submitted_profile_arg = profile if isinstance(profile, Mapping) and profile else None
        if not isinstance(profile, Mapping):
            # Prefill from the last saved profile if present; otherwise provide a light demo profile
            try:
                if self.profile_path.exists():
                    saved = self._safe_read_json(self.profile_path, None)
                else:
                    saved = None
            except Exception:
                saved = None
            if isinstance(saved, Mapping):
                profile = saved
            else:
                profile = {
                    "agent": {"name": "Sample Agent", "version": "1.0.0", "persona": "ENTJ"},
                    "toolsets": {"selected": ["Data Analysis", "Reporting"], "custom": []},
                    "attributes": {"selected": ["Strategic"], "custom": []},
                    "preferences": {
                        "sliders": {"autonomy": 70, "confidence": 65, "collaboration": 60},
                        "communication_style": "Formal",
                        "collaboration_mode": "Cross-Functional",
                    },
                    "identity": {
                        "agent_name": "Sample Agent",
                        "display_name": "Sample Agent",
                        "owners": ["CAIO", "CPA", "TeamLead"],
                        "no_impersonation": True,
                        "attribution_policy": "original",
                    },
                }
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

        naics_code = str(naics_section.get("code", "")) if naics_section else ""
        naics_title = str(naics_section.get("title", "")) if naics_section else ""
        naics_level = str(naics_section.get("level", "")) if naics_section else ""
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
        identity_script = self._indent_block(
            """
(function(){
  const form = document.querySelector('form');
  if (!form) return;
  function get(name){ return form.querySelector('[name="'+name+'"]'); }
  function set(name,val){ const el=get(name); if(el){ el.value = val||''; } }
  function mirror(){ const n = (get('identity.agent_name')||{}).value || ''; set('identity.display_name', n); set('agent_name', n); }
  // Keep identity.agent_version in sync with agent_version input
  function syncAgentVersion(){ const v = (get('agent_version')||{}).value || '1.0.0'; set('identity.agent_version', v); }
  async function regen(){
    mirror();
    syncAgentVersion();
    const na = (get('naics_code')||{}).value || '';
    const fn = (get('business_function')||{}).value || '';
    const rc = (get('role_code')||{}).value || '';
    const nm = (get('identity.agent_name')||{}).value || '';
    if (!na || !fn || !rc || !nm) return;
    try {
      const res = await fetch('/api/identity/generate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ naics_code: na, business_function: fn, role_code: rc, agent_name: nm }) });
      const data = await res.json();
      if (data && data.agent_id) { set('identity.agent_id', data.agent_id); }
    } catch (e) { /* ignore */ }
  }
  const schedule=(()=>{ let t; return ()=>{ clearTimeout(t); t=setTimeout(regen,200); };})();
  form.addEventListener('input', function(e){ if (!e || !e.target) return; if (e.target.name === 'identity.agent_name') schedule(); if (e.target.name === 'agent_version') syncAgentVersion(); }, true);
  document.addEventListener('business:functionChanged', schedule, true);
  document.addEventListener('role:changed', schedule, true);
  document.addEventListener('change', function(e){ if (e && e.target && e.target.name === 'naics_code') schedule(); }, true);
  mirror(); syncAgentVersion();
})();
""",
            spaces=8,
        )

        # JSON viewer: prefer submitted profile, else last-saved on disk
        submitted_profile = submitted_profile_arg
        summary_source = submitted_profile
        if summary_source is None:
            summary_source = self._safe_read_json(self.profile_path, None)
            if not isinstance(summary_source, Mapping):
                summary_source = None
        summary_html = _summary_block(summary_source, str(self.profile_path), str(self.spec_dir))

        # NAICS coercion to strings before escaping/injecting
        naics_code     = str(naics_code)
        naics_title    = str(naics_title)
        naics_level    = str(naics_level)
        naics_lineage  = str(naics_lineage)
        safe_code      = html.escape(naics_code)
        safe_title     = html.escape(naics_title)
        safe_level     = html.escape(naics_level)
        safe_lineage   = html.escape(naics_lineage)

        # Identity persistence (agent_id)
        agent_id_value = ""
        try:
            if isinstance(profile, Mapping):
                ident = profile.get("identity")
                if isinstance(ident, Mapping):
                    agent_id_value = _str(ident.get("agent_id") or "")
        except Exception:
            agent_id_value = ""

        # Final page assembly
        page = FORM_TEMPLATE.substitute(
            persona_styles=persona_style_block or "",
            extra_styles=extra_styles or "",
            notice=_notice(message),
            persona_tabs=persona_html or "",
            persona_script=persona_script or "",
            persona_hidden_value=persona_hidden or "",
            summary=summary_html or "",
            agent_name=html.escape(agent_name, quote=True),
            agent_version=html.escape(agent_version, quote=True),
            agent_id=html.escape(agent_id_value or "", quote=True),
            notes=html.escape(notes_value or "", quote=True),
            communication_options=communication_options,
            collaboration_options=collaboration_options,
            autonomy_value=str(autonomy_value),
            confidence_value=str(confidence_value),
            collaboration_value=str(collaboration_value),
            toolset_checkboxes=toolset_checkboxes,
            attribute_checkboxes=attribute_checkboxes,
            custom_toolsets=html.escape(custom_toolsets_value, quote=True),
            custom_attributes=html.escape(custom_attributes_value, quote=True),
            linkedin_url=html.escape(linkedin_url, quote=True),
            naics_selector_html=naics_selector_html,
            naics_code=safe_code,
            naics_title=safe_title,
            naics_level=safe_level,
            naics_lineage=safe_lineage,
            domain_selector_state=html.escape(domain_selector_state or "", quote=True),
            domain_selector_html=domain_selector_html,
            function_select_html=function_select_html,
            function_role_html=function_role_html,
            function_category=html.escape(function_category or "", quote=True),
            function_specialties=function_specialties_json or "",
            function_role_bootstrap=function_role_bootstrap or "",
            domain_bundle_script=domain_bundle_script or "",
            function_role_script=function_role_script or "",
            identity_script=identity_script or "",
            generate_agent_script=generate_agent_script or "",
            build_panel_script=self._indent_block(self._build_panel_js or "", spaces=8),
            build_panel_styles=self._indent_block(self._build_panel_css or "", spaces=12),
        )
        return page

    # ------------------------------- NAICS data -------------------------------
    def _ensure_naics_loaded(self) -> list[dict]:
        """Load NAICS reference data if not already cached.

        Preferred source: JSON at data/naics/naics_2022.json (array of
        {code,title}). Fallback: CSV built from the official workbook at
        data/naics/2-6 digit_2022_Codes.csv.
        """
        if isinstance(self._naics_cache, list) and self._naics_cache:
            return self._naics_cache  # type: ignore[return-value]

        entries: list[dict] = []

        # Try JSON first
        try:
            if self.naics_path.exists():
                raw = self.naics_path.read_text(encoding="utf-8")
                data = json.loads(raw)
                if isinstance(data, list):
                    for item in data:
                        if not isinstance(item, Mapping):
                            continue
                        code = str(item.get("code", "")).strip()
                        title = str(item.get("title", "")).strip()
                        if not code or not title:
                            continue
                        level = len("".join(ch for ch in code if ch.isdigit()))
                        if level < 2 or level > 6:
                            continue
                        entries.append({"code": code, "title": title, "level": level})
        except Exception:
            # fall through to CSV
            pass

        # Fallback to CSV (present in repo by default)
        if not entries:
            csv_path = self.data_root / "naics" / "2-6 digit_2022_Codes.csv"
            try:
                if csv_path.exists():
                    with csv_path.open("r", encoding="utf-8", newline="") as fh:
                        reader = csv.DictReader(fh)
                        for row in reader:
                            code = str((row or {}).get("code") or "").strip()
                            title = str((row or {}).get("title") or "").strip()
                            if not code or not title:
                                continue
                            # Codes may include ranges already expanded by builder script.
                            code_digits = "".join(ch for ch in code if ch.isdigit())
                            level = len(code_digits)
                            if level < 2 or level > 6:
                                continue
                            entries.append({"code": code_digits, "title": title, "level": level})
            except Exception:
                LOGGER.exception("Failed to load NAICS CSV")

        # Deduplicate and sort for stable responses
        seen: set[str] = set()
        dedup: list[dict] = []
        for e in entries:
            c = str(e.get("code") or "")
            if not c or c in seen:
                continue
            seen.add(c)
            dedup.append({"code": c, "title": str(e.get("title") or ""), "level": int(e.get("level") or len(c))})
        dedup.sort(key=lambda d: (int(d.get("level", 0)), str(d.get("code", ""))))

        # Build index by code for fast lookup
        by_code: dict[str, dict] = {}
        for e in dedup:
            by_code[str(e["code"])]=e

        self._naics_cache = dedup
        self._naics_by_code = by_code
        LOGGER.info("NAICS loaded: %d entries", len(dedup))
        return dedup

    def reload_naics(self) -> int:
        """Force reload of NAICS reference data. Returns number of entries."""
        self._naics_cache = None
        self._naics_by_code = None
        return len(self._ensure_naics_loaded())

    # Compatibility for scripts/tests that looked for the old helper name
    def _load_naics_reference(self) -> list[dict]:
        return self._ensure_naics_loaded()

    def _naics_children(self, parent: str, level: Optional[int]) -> list[dict]:
        entries = self._ensure_naics_loaded()
        parent = str(parent or "").strip()
        lvl = int(level) if level else 0
        out: list[dict] = []
        for e in entries:
            code = str(e.get("code") or "")
            if lvl and int(e.get("level", 0)) != lvl:
                continue
            if parent and not code.startswith(parent):
                continue
            if lvl and len(code) != lvl:
                continue
            out.append({"code": code, "title": e.get("title")})
        out.sort(key=lambda d: d["code"])  # stable order
        return out

    def _naics_search(self, q: str) -> list[dict]:
        q = str(q or "").strip().lower()
        if not q:
            return []
        entries = self._ensure_naics_loaded()
        results: list[dict] = []
        for e in entries:
            code = str(e.get("code") or "")
            title = str(e.get("title") or "")
            if code.startswith(q) or q in title.lower():
                results.append({"code": code, "title": title})
        results.sort(key=lambda d: (len(d["code"]), d["code"]))
        return results[:100]

    def _naics_detail(self, code: str) -> dict | None:
        by_code = self._naics_by_code or {}
        if not by_code:
            self._ensure_naics_loaded()
            by_code = self._naics_by_code or {}
        c = str(code or "").strip()
        e = by_code.get(c)
        if not e:
            return None
        lineage: list[dict] = []
        try:
            for i in range(2, min(6, len(c)) + 1):
                prefix = c[:i]
                pe = by_code.get(prefix)
                if pe:
                    lineage.append({"code": pe["code"], "title": pe["title"], "level": pe.get("level", i)})
        except Exception:
            pass
        return {"code": e.get("code"), "title": e.get("title"), "level": e.get("level", len(c)), "lineage": lineage}

    # ------------------------------ Persistence ------------------------------
    def _save_persona_state(self, state: Mapping[str, Any]) -> Mapping[str, Any]:
        """Persist persona selection state enriched with MBTI details.

        Returns the enriched state mapping that was saved.
        """
        agent = dict(state.get("agent") or {})
        code = agent.get("code")
        enriched = self._enrich_persona_metadata(code)
        if enriched:
            agent.setdefault("mbti", enriched)
        payload = {
            **dict(state),
            "agent": agent,
            "persona_details": enriched or {},
            "updated_at": int(time.time()),
        }
        try:
            with self.persona_state_path.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
        except Exception:
            pass
        return payload

    def _load_persona_state(self) -> Mapping[str, Any]:
        def _default() -> Mapping[str, Any]:
            return {"operator": None, "agent": None, "alternates": [], "persona_details": {}}
        try:
            with self.persona_state_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            if not isinstance(data, Mapping):
                return _default()
            out = dict(_default())
            out.update({k: data.get(k) for k in ("operator", "agent", "alternates", "persona_details")})
            return out
        except Exception:
            return _default()

    def _build_profile(self, params: Mapping[str, list[str] | str], persona_state: Mapping[str, Any] | None) -> Mapping[str, Any]:
        def _get(name: str, default: str = "") -> str:
            v = params.get(name)
            if isinstance(v, list):
                return str(v[0]) if v else default
            return str(v) if isinstance(v, str) else default
        def _get_list(name: str) -> list[str]:
            v = params.get(name)
            if isinstance(v, list):
                return [str(x) for x in v if x]
            return [str(v)] if isinstance(v, str) and v else []

        persona_state = persona_state or self._load_persona_state()
        persona_block = {
            "operator": persona_state.get("operator"),
            "agent": persona_state.get("agent"),
            "alternates": persona_state.get("alternates") or [],
        }

        persona_code = _get("agent_persona")
        # Business function & role (persist to keep selections on re-render)
        business_function_value = _get("business_function")
        role_code_value = _get("role_code")
        role_title_value = _get("role_title")
        role_seniority_value = _get("role_seniority")

        # NAICS payload from hidden inputs
        naics_code = _get("naics_code")
        naics_title = _get("naics_title")
        naics_level_raw = _get("naics_level")
        try:
            naics_level = int(naics_level_raw) if naics_level_raw else None
        except Exception:
            naics_level = None
        try:
            lineage_text = _get("naics_lineage_json")
            naics_lineage = json.loads(lineage_text) if lineage_text else []
            if not isinstance(naics_lineage, list):
                naics_lineage = []
        except Exception:
            naics_lineage = []

        profile: Dict[str, Any] = {
            "agent": {
                "name": _get("agent_name"),
                "version": _get("agent_version", "1.0.0"),
                "persona": persona_code,
                "mbti": self._enrich_persona_metadata(persona_code),
                "domain": _get("domain"),
                "role": _get("role"),
                "business_function": business_function_value,
            },
            # Persist identity so Agent ID survives form re-render
            "identity": {
                "agent_id": _get("identity.agent_id"),
                "display_name": _get("identity.display_name"),
                "owners": [s for s in _get("identity.owners").split(",") if s.strip()],
                "no_impersonation": bool(_get("identity.no_impersonation") or "true"),
            },
            # Function/role selections
            "business_function": business_function_value,
            "role": {
                "code": role_code_value,
                "title": role_title_value or role_code_value,
                "seniority": role_seniority_value,
                "function": business_function_value,
            },
            # Persist NAICS
            "naics": {"code": naics_code, "title": naics_title, "level": naics_level, "lineage": naics_lineage},
            "classification": {"naics": {"code": naics_code, "title": naics_title, "level": naics_level, "lineage": naics_lineage}},
            "toolsets": {"selected": _get_list("toolsets"), "custom": _get("toolsets_custom")},
            "attributes": {"selected": _get_list("attributes"), "custom": _get("attributes_custom")},
            "preferences": {
                "sliders": {
                    "autonomy": int(_get("autonomy", "50") or 50),
                    "confidence": int(_get("confidence", "50") or 50),
                    "collaboration": int(_get("collaboration", "50") or 50),
                },
                "communication_style": _get("communication_style"),
                "collaboration_mode": _get("collaboration_mode"),
            },
            "notes": _get("notes"),
            "linkedin": {"url": _get("linkedin_url")},
            "persona": persona_block,
        }
        # Emit telemetry event when persona present (for unit tests)
        try:
            from . import telemetry as _telemetry  # type: ignore
            meta = profile["agent"].get("mbti") or self._enrich_persona_metadata(persona_code)
            if persona_code and hasattr(_telemetry, "emit_event"):
                _telemetry.emit_event("persona:selected", meta)
        except Exception:
            pass
        return profile

    # ------------------------------- WSGI layer -------------------------------
    def wsgi_app(self, environ: Mapping[str, Any], start_response) -> Iterable[bytes]:
        method = str(environ.get("REQUEST_METHOD", "GET")).upper()
        path = str(environ.get("PATH_INFO", "/")) or "/"
        try:
            LOGGER.info("req %s %s", method, path)
        except Exception:
            pass

        # Routing: JSON APIs first
        if path == "/health" and method == "GET":
            payload = {
                "status": "ok",
                "build_tag": INTAKE_BUILD_TAG,
                "app_version": _read_app_version(self.project_root),
                "pid": os.getpid(),
                "repo_output_dir": str(self.repo_output_dir),
                "profile_output_dir": str(self.profile_output_dir),
                "has_api_generate": True,
                "build_on_post": True,
            }
            raw = json.dumps(payload).encode("utf-8")
            start_response("200 OK", _std_headers("application/json", len(raw)))
            return [raw]
        # Last build: compact JSON summary saved by /build
        if path == "/last-build" and method == "GET":
            out_root_env = os.environ.get("NEO_REPO_OUTDIR") or str((self.base_dir / "_generated").resolve())
            out_root = Path(out_root_env)
            last_path = out_root / "_last_build.json"
            if not last_path.exists():
                start_response("204 No Content", _std_headers("application/json", 0))
                return [b""]
            try:
                raw = last_path.read_bytes()
                if emit_event:
                    try:
                        emit_event("last_build_read", {"path": str(last_path)})
                    except Exception:
                        pass
                start_response("200 OK", _std_headers("application/json", len(raw)))
                return [raw]
            except Exception as exc:
                payload = json.dumps({"status": "error", "issues": [str(exc)]}).encode("utf-8")
                start_response("500 Internal Server Error", _std_headers("application/json", len(payload)))
                return [payload]
        # Build ZIP download (validated subpath under out root)
        if path == "/build/zip" and method == "GET":
            qs = parse_qs(str(environ.get("QUERY_STRING") or ""))
            outdir_q = (qs.get("outdir") or [""])[0]
            if not outdir_q:
                payload = json.dumps({"status": "invalid", "errors": ["missing outdir"]}).encode("utf-8")
                start_response("400 Bad Request", _std_headers("application/json", len(payload)))
                return [payload]
            out_root_env = os.environ.get("NEO_REPO_OUTDIR") or str((self.base_dir / "_generated").resolve())
            out_root = Path(out_root_env)
            candidate = Path(outdir_q)
            if not self._is_safe_subpath(out_root, candidate):
                payload = json.dumps({"status": "invalid", "errors": ["outdir outside allowed root"]}).encode("utf-8")
                start_response("400 Bad Request", _std_headers("application/json", len(payload)))
                return [payload]
            if not candidate.exists() or not candidate.is_dir():
                payload = json.dumps({"status": "not_found"}).encode("utf-8")
                start_response("404 Not Found", _std_headers("application/json", len(payload)))
                return [payload]

            # Prepare archive name
            try:
                from neo_build.utils import slugify
            except Exception:
                def slugify(s: str) -> str:  # type: ignore[no-redef]
                    return (s or "").strip().replace(" ", "-")
            parent = candidate.parent.name or "repo"
            name = candidate.name or "repo"
            arch = f"{slugify(parent)}_{slugify(name)}.zip"

            # Collect files; estimate size and count
            from neo_build.contracts import CANONICAL_PACK_FILENAMES as _NAMES
            files = [p for p in candidate.rglob("*") if p.is_file()]
            try:
                size_est = sum(int(p.stat().st_size) for p in files)
            except Exception:
                size_est = 0
            file_count = sum(1 for n in _NAMES if (candidate / n).exists())

            # Try recover agent_id for telemetry
            agent_id = None
            try:
                p06 = candidate / "06_Role-Recipes_Index_v2.json"
                if p06.exists():
                    o6 = json.loads(p06.read_text(encoding="utf-8"))
                    agent_id = (o6.get("mapping") or {}).get("agent_id")
            except Exception:
                pass
            if not agent_id:
                try:
                    p09 = candidate / "09_Agent-Manifests_Catalog_v2.json"
                    if p09.exists():
                        o9 = json.loads(p09.read_text(encoding="utf-8"))
                        ags = o9.get("agents") or []
                        if isinstance(ags, list) and ags:
                            agent_id = (ags[0] or {}).get("agent_id")
                except Exception:
                    pass

            # Build zip in-memory (repo is small) and stream as one chunk
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for p in files:
                    try:
                        zf.write(p, arcname=str(p.relative_to(candidate)))
                    except Exception:
                        continue
            data = buf.getvalue()
            headers = _std_headers("application/zip", len(data), extra=[
                ("Content-Disposition", f"attachment; filename=\"{arch}\""),
            ])
            try:
                if emit_event:
                    emit_event("zip_download", {
                        "agent_id": agent_id or "",
                        "outdir": str(candidate),
                        "file_count": int(file_count),
                        "size_bytes_est": int(size_est),
                        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    })
            except Exception:
                pass
            start_response("200 OK", headers)
            return [data]
        # Save v3 intake profile (JSON) with schema validation and normalization
        if path == "/save" and method == "POST":
            try:
                length = int(environ.get("CONTENT_LENGTH") or 0)
            except Exception:
                length = 0
            body = (environ.get("wsgi.input").read(length) if length else b"") or b"{}"
            errors: list[str] = []
            try:
                data = json.loads(body.decode("utf-8"))
            except Exception as exc:
                data = None
                errors.append(f"Invalid JSON: {exc}")

            # Minimal validation against intake_v3 schema (selected required fields and legacy guards)
            def _require(path: list[str], obj: Any) -> None:
                cur = obj
                for p in path:
                    if not isinstance(cur, Mapping) or p not in cur:
                        errors.append(f"Missing field: {'.'.join(path)}")
                        return
                    cur = cur[p]
                if isinstance(cur, str) and not cur.strip():
                    errors.append(f"Empty field: {'.'.join(path)}")
                if isinstance(cur, list) and len(cur) == 0:
                    errors.append(f"Empty list: {'.'.join(path)}")

            legacy_keys = ("legacy", "legacy_industry", "legacy_tool_toggles", "manual_log_level", "meta", "agent_profile", "governance", "privacy")
            if isinstance(data, Mapping):
                if str(data.get("intake_version")) != "v3.0":
                    errors.append("intake_version must equal 'v3.0'")
                _require(["identity", "agent_id"], data)
                _require(["identity", "display_name"], data)
                _require(["identity", "owners"], data)
                _require(["context", "naics", "code"], data)
                _require(["role", "function_code"], data)
                _require(["role", "role_code"], data)
                _require(["governance_eval", "gates", "PRI_min"], data)
                _require(["governance_eval", "gates", "hallucination_max"], data)
                _require(["governance_eval", "gates", "audit_min"], data)
                for k in legacy_keys:
                    if k in data:
                        errors.append(f"Legacy field not allowed in v3: {k}")
            else:
                if not errors:
                    errors.append("Payload must be a JSON object")

            if errors:
                payload = json.dumps({"status": "invalid", "errors": errors}).encode("utf-8")
                start_response("400 Bad Request", _std_headers("application/json", len(payload)))
                return [payload]

            # Normalize to builder-compatible keys
            try:
                normalized = normalize_context_role(data)
                profile = dict(data)
                profile.update(normalized)
                ge = dict(profile.get("governance_eval") or {})
                gates = dict(ge.get("gates") or {})
                gates.setdefault("PRI_min", 0.95)
                gates.setdefault("hallucination_max", 0.02)
                gates.setdefault("audit_min", 0.90)
                ge["gates"] = gates
                profile["governance_eval"] = ge
            except Exception as exc:
                LOGGER.warning("Normalization failed on /save: %s", exc)
                profile = data if isinstance(data, Mapping) else {}

            # Persist and respond
            try:
                self.profile_path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
                # Also write a versioned copy under generated_profiles/<slug>/agent_profile.json
                try:
                    import re
                    agent_section = profile.get("agent") if isinstance(profile, Mapping) else {}
                    if not isinstance(agent_section, Mapping):
                        agent_section = {}
                    identity_section = profile.get("identity") if isinstance(profile, Mapping) else {}
                    if not isinstance(identity_section, Mapping):
                        identity_section = {}
                    agent_name = str((identity_section.get("display_name") or agent_section.get("name") or "agent"))
                    agent_version = str(agent_section.get("version", "1.0.0")).replace(".", "-")
                    slug_base = re.sub(r"[^a-z0-9\-]+", "-", agent_name.lower().strip()).strip("-") or "agent"
                    slug = f"{slug_base}-{agent_version}"
                    prof_dir = self.profile_output_dir / slug
                    prof_dir.mkdir(parents=True, exist_ok=True)
                    (prof_dir / "agent_profile.json").write_text(json.dumps(profile, indent=2), encoding="utf-8")
                except Exception:
                    # Non-fatal; legacy path still saved
                    pass
                agent_id = str(((profile.get("identity") or {}).get("agent_id") or "")).strip()
                naics_code = str((((profile.get("context") or {}).get("naics") or {}).get("code") or "")).strip()
                role_code = str(((profile.get("role") or {}).get("role_code") or "")).strip()
                LOGGER.info("/save agent_id=%s naics=%s role=%s", agent_id, naics_code, role_code)
                payload = json.dumps({"status": "ok", "path": str(self.profile_path), "agent_id": agent_id}).encode("utf-8")
                start_response("200 OK", _std_headers("application/json", len(payload)))
                return [payload]
            except Exception as exc:
                payload = json.dumps({"status": "error", "errors": [str(exc)]}).encode("utf-8")
                start_response("500 Internal Server Error", _std_headers("application/json", len(payload)))
                return [payload]

        # --- NAICS endpoints ---
        if path == "/api/naics/roots" and method == "GET":
            items = [e for e in self._naics_children("", 2)]
            payload = json.dumps({"status": "ok", "items": items}).encode("utf-8")
            headers = [("Content-Type", "application/json"),
                       ("X-NEO-Intake-Version", INTAKE_BUILD_TAG),
                       ("Cache-Control", "no-store, must-revalidate"),
                       ("Content-Length", str(len(payload)))]
            start_response("200 OK", headers)
            return [payload]

        if path.startswith("/api/naics/children/") and method == "GET":
            parent = path.split("/api/naics/children/")[-1]
            try:
                qs = parse_qs(str(environ.get("QUERY_STRING") or ""))
                level = int((qs.get("level") or [0])[0] or 0)
            except Exception:
                level = 0
            items = self._naics_children(parent, level if level else None)
            payload = json.dumps({"status": "ok", "items": items}).encode("utf-8")
            headers = [("Content-Type", "application/json"),
                       ("X-NEO-Intake-Version", INTAKE_BUILD_TAG),
                       ("Cache-Control", "no-store, must-revalidate"),
                       ("Content-Length", str(len(payload)))]
            start_response("200 OK", headers)
            return [payload]

        if path == "/api/naics/search" and method == "GET":
            try:
                qs = parse_qs(str(environ.get("QUERY_STRING") or ""))
                q = (qs.get("q") or [""])[0]
            except Exception:
                q = ""
            items = self._naics_search(q)
            payload = json.dumps({"status": "ok", "items": items}).encode("utf-8")
            headers = [("Content-Type", "application/json"), ("Content-Length", str(len(payload)))]
            start_response("200 OK", headers)
            return [payload]

        if path.startswith("/api/naics/code/") and method == "GET":
            code = path.split("/api/naics/code/")[-1]
            entry = self._naics_detail(code)
            payload = json.dumps({"status": "ok", "entry": entry}).encode("utf-8")
            headers = [("Content-Type", "application/json"), ("Content-Length", str(len(payload)))]
            start_response("200 OK", headers)
            return [payload]
        if path == "/api/identity/generate" and method == "POST":
            try:
                length = int(environ.get("CONTENT_LENGTH") or 0)
            except Exception:
                length = 0
            body = (environ.get("wsgi.input").read(length) if length else b"") or b"{}"
            try:
                data = json.loads(body.decode("utf-8"))
            except Exception:
                data = {}
            agent_id = generate_agent_id(
                str(data.get("naics_code", "NAICS000000")),
                str(data.get("business_func", data.get("business_function", "func-na"))),
                str(data.get("role_code", "role-na")),
                str(data.get("agent_name", "agent-na")),
            )
            payload = json.dumps({"agent_id": agent_id}).encode("utf-8")
            headers = [("Content-Type", "application/json"), ("Content-Length", str(len(payload)))]
            start_response("200 OK", headers)
            return [payload]

        if path == "/api/persona/config" and method == "GET":
            payload = json.dumps(self.persona_config).encode("utf-8")
            headers = [("Content-Type", "application/json"), ("Content-Length", str(len(payload)))]
            start_response("200 OK", headers)
            return [payload]

        if path == "/api/persona/state":
            if method == "POST":
                try:
                    length = int(environ.get("CONTENT_LENGTH") or 0)
                except Exception:
                    length = 0
                body = (environ.get("wsgi.input").read(length) if length else b"") or b"{}"
                try:
                    data = json.loads(body.decode("utf-8"))
                except Exception:
                    data = {}
                saved = self._save_persona_state(data if isinstance(data, Mapping) else {})
                payload = json.dumps(saved).encode("utf-8")
            else:  # GET
                payload = json.dumps(self._load_persona_state()).encode("utf-8")
            headers = [("Content-Type", "application/json"), ("Content-Length", str(len(payload)))]
            start_response("200 OK", headers)
            return [payload]

        # Generate deterministic 20-pack repo from submitted profile (v3-aware)
        if path == "/api/agent/generate" and method == "POST":
            try:
                length = int(environ.get("CONTENT_LENGTH") or 0)
            except Exception:
                length = 0
            body = (environ.get("wsgi.input").read(length) if length else b"") or b"{}"
            try:
                data = json.loads(body.decode("utf-8"))
            except Exception:
                data = {}
            profile = data.get("profile") if isinstance(data, dict) else None
            if not isinstance(profile, dict):
                payload = json.dumps({"status": "error", "issues": ["Missing profile in payload."]}).encode("utf-8")
                headers = [("Content-Type", "application/json"), ("Content-Length", str(len(payload)))]
                start_response("400 Bad Request", headers)
                return [payload]

            # Normalize NAICS + Function/Role → role_profile/sector_profile
            try:
                # Extract region from multiple possible sources
                region_vals = []
                if isinstance(profile.get("context"), dict):
                    region_vals = profile["context"].get("region", [])
                if not region_vals and isinstance(profile.get("sector_profile"), dict):
                    region_vals = profile["sector_profile"].get("region", [])
                if not isinstance(region_vals, list):
                    region_vals = []
                
                naics_data = (profile.get("classification") or {}).get("naics") or profile.get("naics") or {}
                
                v3 = {
                    "context": {
                        "naics": naics_data,
                        "region": region_vals if region_vals else ["CA"],  # Default to CA if empty
                    },
                    "role": {
                        "function_code": str(profile.get("business_function", "")),
                        "role_code": str(((profile.get("role") or {}).get("code") or "")),
                        "role_title": str(((profile.get("role") or {}).get("title") or "")),
                        "objectives": list(((profile.get("role") or {}).get("objectives") or [])),
                    },
                }
                normalized = normalize_context_role(v3)
                merged = dict(profile)
                merged.update(normalized)
                # Ensure classification.naics present for writers
                classification = dict(merged.get("classification") or {})
                classification["naics"] = naics_data
                merged["classification"] = classification
            except Exception as norm_exc:
                LOGGER.warning("Normalization failed in API: %s", norm_exc)
                merged = profile

            # Write repo to generated_repos/{slug}
            try:
                # Create unique repo subdirectory based on agent identity
                agent_section = merged.get("agent") if isinstance(merged, Mapping) else {}
                if not isinstance(agent_section, Mapping):
                    agent_section = {}
                identity_section = merged.get("identity") if isinstance(merged, Mapping) else {}
                if not isinstance(identity_section, Mapping):
                    identity_section = {}
                agent_name = str((identity_section.get("display_name") or agent_section.get("name") or "agent"))
                agent_version = str(agent_section.get("version", "1-0-0")).replace(".", "-")
                
                # Slugify agent name
                import re
                slug_base = re.sub(r"[^a-z0-9\-]+", "-", agent_name.lower().strip()).strip("-") or "agent"
                slug = f"{slug_base}-{agent_version}"
                
                # Find next available directory
                repo_dir = self.repo_output_dir / slug
                counter = 2
                while repo_dir.exists():
                    repo_dir = self.repo_output_dir / f"{slug}-{counter}"
                    counter += 1
                
                # Write repo files to the unique subdirectory
                packs = write_repo_files(merged, repo_dir)
                # Generate and write integrity report
                report = integrity_report(merged, packs)
                integrity_path = repo_dir / "INTEGRITY_REPORT.json"
                with integrity_path.open("w", encoding="utf-8") as handle:
                    json.dump(report, handle, indent=2, ensure_ascii=False)
                    handle.write("\n")
                
                out = {
                    "status": "ok",
                    "out_dir": str(repo_dir),
                    "checks": report.get("checks", {}),
                }
                payload = json.dumps(out).encode("utf-8")
                headers = _std_headers("application/json", len(payload))
                start_response("200 OK", headers)
                return [payload]
            except Exception as exc:
                LOGGER.exception("Failed to generate repo")
                payload = json.dumps({"status": "error", "issues": [str(exc)]}).encode("utf-8")
                headers = _std_headers("application/json", len(payload))
                start_response("500 Internal Server Error", headers)
                return [payload]

        # Deterministic build route for PR-B
        if path == "/build" and method == "POST":
            warnings: list[str] = []
            # Load only the validated agent_profile.json from disk
            if not self.profile_path.exists():
                payload = json.dumps({"status": "error", "issues": ["agent_profile.json not found. Save a v3 profile first via /save."]}).encode("utf-8")
                start_response("400 Bad Request", _std_headers("application/json", len(payload)))
                return [payload]
            try:
                profile = json.loads(self.profile_path.read_text(encoding="utf-8"))
            except Exception as exc:
                payload = json.dumps({"status": "error", "issues": [f"Failed to read agent_profile.json: {exc}"]}).encode("utf-8")
                start_response("500 Internal Server Error", _std_headers("application/json", len(payload)))
                return [payload]

            # Normalize v3 payload for builder compatibility (role_profile/sector_profile)
            try:
                normalized = normalize_context_role(profile)
                profile.update(normalized)
            except Exception as exc:
                warnings.append(f"normalize_failed: {exc}")

            # Choose outdir: respect NEO_REPO_OUTDIR, ensure not OneDrive
            out_root_env = os.environ.get("NEO_REPO_OUTDIR") or str((self.base_dir / "_generated").resolve())
            out_root = Path(out_root_env)
            if "onedrive" in str(out_root).lower():
                warnings.append("selected_outdir_is_onedrive; using local _generated instead")
                out_root = (self.base_dir / "_generated").resolve()
            out_root.mkdir(parents=True, exist_ok=True)

            # Compute agent_id and timestamped path
            ident = profile.get("identity") if isinstance(profile, Mapping) else {}
            if not isinstance(ident, Mapping):
                ident = {}
            agent_id = str(ident.get("agent_id") or generate_agent_id()).strip()
            ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
            out_dir = out_root / agent_id / ts

            # Build files
            try:
                if emit_event:
                    emit_event("build:requested", {"agent_id": agent_id, "out_root": str(out_root)})
                packs = write_repo_files(profile, out_dir)
                # integrity report
                report = integrity_report(profile, packs)
                (out_dir / "INTEGRITY_REPORT.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

                # Gate parity summary
                kpi_02 = ((packs.get("02_Global-Instructions_v2.json") or {}).get("observability") or {}).get("kpi_targets", {})
                kpi_14 = (packs.get("14_KPI+Evaluation-Framework_v2.json") or {}).get("targets", {})
                gates_11_all = (packs.get("11_Workflow-Pack_v2.json") or {}).get("gates", {})
                kpi_11 = gates_11_all.get("kpi_targets", {}) if isinstance(gates_11_all, Mapping) else {}
                parity_02_14 = bool(kpi_02 == kpi_14)
                parity_11_02 = bool(kpi_11 == kpi_02)

                # Optional copy to OneDrive
                try:
                    copy_flag = str(os.environ.get("NEO_COPY_TO_ONEDRIVE") or "false").lower() in ("1", "true", "yes")
                    if copy_flag:
                        import shutil
                        dest = self.repo_output_dir / agent_id / ts
                        shutil.copytree(out_dir, dest, dirs_exist_ok=True)
                except Exception as exc:
                    warnings.append(f"copy_to_onedrive_failed: {exc}")

                # Include sprint-4 parity map and deltas from integrity report
                parity_map = (report or {}).get("parity", {}) if isinstance(report, Mapping) else {}
                parity_deltas = (report or {}).get("parity_deltas", {}) if isinstance(report, Mapping) else {}
                resp = {
                    "outdir": str(out_dir),
                    "file_count": len(list(out_dir.glob("*.json"))) + len(list(out_dir.glob("*.md"))),
                    "parity": {
                        "02_vs_14": bool(parity_map.get("02_vs_14", parity_02_14)),
                        "11_vs_02": bool(parity_map.get("11_vs_02", parity_11_02)),
                        "03_vs_02": bool(parity_map.get("03_vs_02", True)),
                        "17_vs_02": bool(parity_map.get("17_vs_02", True)),
                    },
                    "parity_deltas": parity_deltas,
                    "integrity_errors": report.get("errors", []) if isinstance(report, Mapping) else [],
                    "warnings": warnings,
                }
                # Optional overlay auto-apply (Sprint-6)
                try:
                    apply_flag = str(os.environ.get("NEO_APPLY_OVERLAYS", "false")).lower() in ("1", "true", "yes")
                    if apply_flag:
                        from neo_build.overlays import load_overlay_config, apply_overlays
                        overlay_cfg = load_overlay_config()
                        summary = apply_overlays(out_dir, overlay_cfg)
                        # Reload packs from disk and recompute integrity/parity
                        updated: dict[str, Any] = {}
                        for name in CANONICAL_PACK_FILENAMES:
                            pth = out_dir / name
                            if pth.exists():
                                updated[name] = json.loads(pth.read_text(encoding="utf-8"))
                        report2 = integrity_report(profile, updated)
                        (out_dir / "INTEGRITY_REPORT.json").write_text(json.dumps(report2, indent=2), encoding="utf-8")
                        # Overwrite parity and integrity in response with post-overlay values
                        p2 = (report2 or {}).get("parity", {}) if isinstance(report2, Mapping) else {}
                        resp["parity"] = {
                            "02_vs_14": bool(p2.get("02_vs_14", True)),
                            "11_vs_02": bool(p2.get("11_vs_02", True)),
                            "03_vs_02": bool(p2.get("03_vs_02", True)),
                            "17_vs_02": bool(p2.get("17_vs_02", True)),
                        }
                        resp["parity_deltas"] = (report2 or {}).get("parity_deltas", {}) if isinstance(report2, Mapping) else {}
                        resp["integrity_errors"] = (report2 or {}).get("errors", []) if isinstance(report2, Mapping) else []
<<<<<<< HEAD
                        resp["overlays_applied"] = not bool(summary.get("rolled_back"))
                        if summary.get("rolled_back"):
                            resp["rolled_back"] = True
                            if summary.get("reason"):
                                resp["overlay_failure_reason"] = summary.get("reason")
=======
                        resp["overlays_applied"] = True
>>>>>>> fb9cd1e (feat(overlays): optional auto-apply 19/20 + persistence/adaptiveness with integrity/parity re-check)
                        resp["overlay_summary"] = summary
                    else:
                        resp["overlays_applied"] = False
                except Exception as overlay_exc:
                    warnings.append(f"overlays_apply_failed: {overlay_exc}")
                # Persist last-build summary at out_root for quick UI retrieval
                try:
                    out_root_last = out_root / "_last_build.json"
                    def _deltas_list(d: Mapping[str, Any] | None) -> list[dict]:
                        items: list[dict] = []
                        if not isinstance(d, Mapping):
                            return items
                        for pack_key, diffs in d.items():
                            try:
                                for k, tup in (diffs or {}).items():
                                    got, expected = (tup[0], tup[1]) if isinstance(tup, (list, tuple)) and len(tup) == 2 else (None, None)
                                    items.append({
                                        "pack": str(pack_key),
                                        "key": str(k),
                                        "got": got,
                                        "expected": expected,
                                    })
                            except Exception:
                                continue
                        return items
                    last_payload = {
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "outdir": resp.get("outdir"),
                        "file_count": int(resp.get("file_count") or 0),
                        "parity": dict(resp.get("parity") or {}),
                        "integrity_errors": list(resp.get("integrity_errors") or []),
                        "overlays_applied": bool(resp.get("overlays_applied")),
                        "parity_deltas": _deltas_list(resp.get("parity_deltas") if isinstance(resp, Mapping) else {}),
                    }
                    out_root_last.write_text(json.dumps(last_payload, indent=2), encoding="utf-8")
                except Exception:
                    pass
                # Telemetry: parity checked summary
                if emit_event:
                    try:
                        vals = list(resp["parity"].values())
                        emit_event("gate_parity_checked", {
                            "true_count": int(sum(1 for v in vals if v)),
                            "false_count": int(sum(1 for v in vals if not v)),
                            "deviated": [k for k, ok in resp["parity"].items() if not ok],
                        })
                    except Exception:
                        pass
                if emit_event:
                    emit_event("build:completed", {"agent_id": agent_id, "outdir": resp["outdir"], "parity": resp["parity"]})
                    emit_repo_generated_event({"outdir": resp["outdir"]})
                payload = json.dumps(resp).encode("utf-8")
                start_response("200 OK", _std_headers("application/json", len(payload)))
                return [payload]
            except Exception as exc:
                payload = json.dumps({"status": "error", "issues": [str(exc)]}).encode("utf-8")
                start_response("500 Internal Server Error", _std_headers("application/json", len(payload)))
                return [payload]

        if path == "/api/function_roles" and method == "GET":
            qs = parse_qs(str(environ.get("QUERY_STRING") or ""))
            fn = (qs.get("fn") or [""])[0]
            items: list[dict[str, Any]] = []
            try:
                roles = self._function_role_data.get("roles", [])
                for r in roles or []:
                    if isinstance(r, Mapping):
                        if not fn or str(r.get("function", "")).strip() == str(fn).strip():
                            items.append({
                                "code": r.get("code"),
                                "title": (r.get("titles") or [None])[0],
                                "function": r.get("function"),
                            })
            except Exception:
                items = []
            payload = json.dumps({"status": "ok", "items": items}).encode("utf-8")
            headers = _std_headers("application/json", len(payload))
            start_response("200 OK", headers)
            return [payload]

        if path == "/api/profile/validate" and method == "POST":
            try:
                length = int(environ.get("CONTENT_LENGTH") or 0)
            except Exception:
                length = 0
            body = (environ.get("wsgi.input").read(length) if length else b"") or b"{}"
            issues: list[str] = []
            try:
                data = json.loads(body.decode("utf-8"))
                if not isinstance(data, Mapping) or "agent" not in data:
                    issues.append("Missing 'agent' section")
            except Exception as exc:
                issues.append(f"Invalid JSON: {exc}")
            status = "ok" if not issues else "invalid"
            payload = json.dumps({"status": status, "issues": issues}).encode("utf-8")
            headers = _std_headers("application/json", len(payload))
            start_response("200 OK", headers)
            return [payload]

        # Form rendering and submission
        if path == "/" and method in {"GET", "POST"}:
            notice = None
            form_profile: Mapping[str, Any] | None = None
            if method == "POST":
                try:
                    length = int(environ.get("CONTENT_LENGTH") or 0)
                except Exception:
                    length = 0
                raw = (environ.get("wsgi.input").read(length) if length else b"") or b""
                params = parse_qs(raw.decode("utf-8"), keep_blank_values=True)
                form_profile = self._build_profile(params, self._load_persona_state())

                # Sprint-1: Normalize v3 context/role into builder keys and build repo immediately
                try:
                    def _p(key: str) -> str:
                        v = params.get(key)
                        if isinstance(v, list):
                            return str(v[0]) if v else ""
                        return str(v) if isinstance(v, str) else ""

                    naics_code = _p("naics_code")
                    naics_title = _p("naics_title")
                    naics_level = _p("naics_level")
                    naics_lineage_json = _p("naics_lineage_json")
                    naics_lineage = []
                    if naics_lineage_json:
                        try:
                            naics_lineage = json.loads(naics_lineage_json)
                            if not isinstance(naics_lineage, list):
                                naics_lineage = []
                        except Exception:
                            naics_lineage = []

                    # Region: prefer explicit; else default inside normalizer
                    region_vals = params.get("context.region") or params.get("sector_profile.region") or []
                    region = [str(x) for x in region_vals if x]

                    v3_payload = {
                        "context": {
                            "naics": {
                                "code": naics_code,
                                "title": naics_title,
                                "level": int(naics_level) if str(naics_level).isdigit() else naics_level,
                                "lineage": naics_lineage,
                            },
                            "region": region,
                        },
                        "role": {
                            "function_code": _p("business_function"),
                            "role_code": _p("role_code") or _p("role_profile.archetype"),
                            "role_title": _p("role_title") or _p("role_profile.role_title"),
                            "objectives": [],
                        },
                    }

                    normalized = normalize_context_role(v3_payload)
                    # Merge normalized keys into the form profile
                    fp = dict(form_profile)
                    fp.update(normalized)
                    # Ensure NAICS is present under classification for the builder
                    classification = dict(fp.get("classification") or {})
                    classification["naics"] = v3_payload["context"]["naics"]
                    fp["classification"] = classification
                    form_profile = fp
                except Exception:
                    # Non-fatal: if normalization fails, continue with raw profile
                    pass
                # Merge with last-saved profile to preserve missing agent_id/NAICS/function/role
                try:
                    last_saved = self._safe_read_json(self.profile_path, {})
                    if isinstance(last_saved, Mapping):
                        fp = dict(form_profile)
                        ident = dict(fp.get("identity") or {})
                        if not str(ident.get("agent_id") or "").strip():
                            ls_id = (last_saved.get("identity") or {}).get("agent_id")
                            if ls_id:
                                ident["agent_id"] = ls_id
                        fp["identity"] = ident
                        # classification.naics + top-level naics
                        cls = dict(fp.get("classification") or {})
                        if not isinstance(cls.get("naics"), Mapping) or not cls.get("naics"):
                            ls_na = ((last_saved.get("classification") or {}).get("naics")
                                     or last_saved.get("naics") or {})
                            if isinstance(ls_na, Mapping) and ls_na:
                                cls["naics"] = ls_na
                        fp["classification"] = cls
                        if not isinstance(fp.get("naics"), Mapping) or not fp.get("naics"):
                            if isinstance(cls.get("naics"), Mapping) and cls.get("naics"):
                                fp["naics"] = cls["naics"]
                        # business function / role
                        if not str(fp.get("business_function") or "").strip():
                            bf = last_saved.get("business_function")
                            if bf:
                                fp["business_function"] = bf
                        role_cur = fp.get("role") if isinstance(fp.get("role"), Mapping) else {}
                        if not role_cur:
                            ls_role = last_saved.get("role") if isinstance(last_saved.get("role"), Mapping) else {}
                            if ls_role:
                                fp["role"] = ls_role
                        else:
                            ls_role = last_saved.get("role") if isinstance(last_saved.get("role"), Mapping) else {}
                            for k in ("code", "title", "seniority", "function"):
                                if not str(role_cur.get(k) or "").strip() and str((ls_role or {}).get(k) or "").strip():
                                    role_cur[k] = ls_role[k]
                            fp["role"] = role_cur
                        form_profile = fp
                except Exception:
                    pass
                try:
                    with self.profile_path.open("w", encoding="utf-8") as handle:
                        json.dump(form_profile, handle, indent=2)
                    from .profile_compiler import compile_profile
                    compiled = compile_profile(form_profile)
                    form_profile["_compiled"] = compiled
                    with self.profile_path.open("w", encoding="utf-8") as handle:
                        json.dump(form_profile, handle, indent=2)
                    with (self.profile_path.parent / "agent_profile.compiled.json").open("w", encoding="utf-8") as handle:
                        json.dump(compiled, handle, indent=2)
                    generate_agent_specs(form_profile, self.spec_dir)
                    # Also build and write the 20-pack repo deterministically
                    repo_built = False
                    try:
                        # Create unique repo subdirectory based on agent identity
                        agent_section = form_profile.get("agent") if isinstance(form_profile, Mapping) else {}
                        if not isinstance(agent_section, Mapping):
                            agent_section = {}
                        identity_section = form_profile.get("identity") if isinstance(form_profile, Mapping) else {}
                        if not isinstance(identity_section, Mapping):
                            identity_section = {}
                        agent_name = str((identity_section.get("display_name") or agent_section.get("name") or "agent"))
                        agent_version = str(agent_section.get("version", "1-0-0")).replace(".", "-")
                        
                        # Slugify agent name
                        import re
                        slug_base = re.sub(r"[^a-z0-9\-]+", "-", agent_name.lower().strip()).strip("-") or "agent"
                        slug = f"{slug_base}-{agent_version}"
                        
                        # Find next available directory
                        repo_dir = self.repo_output_dir / slug
                        counter = 2
                        while repo_dir.exists():
                            repo_dir = self.repo_output_dir / f"{slug}-{counter}"
                            counter += 1
                        
                        # Write repo files to the unique subdirectory
                        packs = write_repo_files(form_profile, repo_dir)
                        # Generate and write integrity report
                        report = integrity_report(form_profile, packs)
                        integrity_path = repo_dir / "INTEGRITY_REPORT.json"
                        with integrity_path.open("w", encoding="utf-8") as handle:
                            json.dump(report, handle, indent=2, ensure_ascii=False)
                            handle.write("\n")
                        
                        checks = report.get("checks", {})
                        repo_built = True
                        notice = f"Agent profile generated successfully (repo generated at {repo_dir.name})"
                        # Optionally append quick parity status to the notice
                        if checks:
                            notice += f" (kpi_sync={checks.get('kpi_sync', False)})"
                    except Exception as repo_exc:
                        # If repo build fails, keep profile generation success message
                        LOGGER.warning("Repo build failed: %s", repo_exc)
                        notice = "Agent profile generated successfully"
                except Exception as exc:
                    notice = f"Failed to generate specs: {exc}"

            body_html = self.render_form(message=notice, profile=form_profile)
            body_bytes = body_html.encode("utf-8")
            headers = self._ensure_content_length(
                [("Content-Type", "text/html; charset=utf-8"),
                 ("Cache-Control", "no-store, must-revalidate"),
                 ("Pragma", "no-cache"),
                 ("Expires", "0"),
                 ("X-NEO-Intake-Version", INTAKE_BUILD_TAG)],
                len(body_bytes)
            )
            start_response("200 OK", headers)
            return [body_bytes]

        # Fallback 404
        payload = b"Not Found"
        start_response("404 Not Found", [("Content-Type", "text/plain"), ("X-NEO-Intake-Version", INTAKE_BUILD_TAG), ("Cache-Control", "no-store, must-revalidate"), ("Content-Length", str(len(payload)))])
        return [payload]

    def serve(self, *, host: Optional[str] = None, port: Optional[int] = None) -> None:
        """Run a simple HTTP server for manual testing."""
        host = host or os.environ.get("HOST") or "127.0.0.1"
        try:
            port = int(port or os.environ.get("PORT") or 5000)
        except Exception:
            port = 5000
        httpd = make_server(host, port, self.wsgi_app)
        LOGGER.info("Serving intake app on http://%s:%s", host, port)
        try:
            httpd.serve_forever()
        finally:
            httpd.server_close()


def create_app(*, base_dir: Optional[Path] = None) -> IntakeApplication:
    """Factory for tests and CLI to create the intake application."""
    return IntakeApplication(base_dir=base_dir)

if __name__ == "__main__":  # pragma: no cover - manual run helper
    create_app().serve()
