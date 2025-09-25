"""HTTP server for the Project NEO agent intake experience."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from string import Template
from typing import Any, Dict, Iterable, List, Mapping
from urllib.parse import parse_qs

from wsgiref.simple_server import make_server

from .linkedin import scrape_linkedin_profile
from .logging import get_logger
from .spec_generator import generate_agent_specs

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
        self.base_dir = self._resolve_base_dir(base_dir)
        self.profile_path = self.base_dir / "agent_profile.json"
        self.spec_dir = self.base_dir / "generated_specs"
        self.spec_dir.mkdir(parents=True, exist_ok=True)
        LOGGER.debug("Initialised intake application with base_dir=%s", self.base_dir)

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
        }

        if linkedin:
            derived_tools = linkedin.get("skills", [])
            for tool in derived_tools:
                candidate = tool.title()
                if candidate not in profile["toolsets"]["selected"]:
                    profile["toolsets"]["selected"].append(candidate)

            derived_roles = linkedin.get("roles", [])
            if derived_roles and not profile["agent"].get("role"):
                profile["agent"]["role"] = derived_roles[0].title()

        return profile

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
