"""Integration style tests for the custom intake WSGI application."""

from __future__ import annotations

import io
import json
from pathlib import Path
from urllib.parse import urlencode

from neo_agent.intake_app import create_app


def _invoke(app, method: str, data: dict[str, list[str] | str]) -> bytes:
    encoded = urlencode(data, doseq=True).encode("utf-8")
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": "/",
        "QUERY_STRING": "",
        "SERVER_NAME": "testserver",
        "SERVER_PORT": "80",
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": "http",
        "wsgi.input": io.BytesIO(encoded),
        "CONTENT_LENGTH": str(len(encoded)),
    }

    status_headers: list[tuple[str, list[tuple[str, str]]]] = []

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        status_headers.append((status, headers))

    response_iter = app.wsgi_app(environ, start_response)
    body = b"".join(response_iter)
    assert status_headers[0][0] == "200 OK"
    return body


def test_intake_form_submission(tmp_path: Path) -> None:
    app = create_app(base_dir=tmp_path)

    body = _invoke(app, "GET", {})
    assert b"Project NEO Agent Intake" in body

    post_data = {
        "agent_name": "Test Agent",
        "agent_version": "1.0.0",
        "agent_persona": "Insight navigator",
        "domain": "Finance",
        "role": "Enterprise Analyst",
        "toolsets": ["Data Analysis", "Reporting"],
        "attributes": ["Strategic"],
        "autonomy": "75",
        "confidence": "60",
        "collaboration": "80",
        "communication_style": "Conversational",
        "collaboration_mode": "Cross-Functional",
        "notes": "Test submission",
        "linkedin_url": "",
    }

    response = _invoke(app, "POST", post_data)
    assert b"Agent profile generated successfully" in response

    profile_path = tmp_path / "agent_profile.json"
    assert profile_path.exists()

    with profile_path.open("r", encoding="utf-8") as handle:
        profile = json.load(handle)

    assert profile["agent"]["name"] == "Test Agent"
    assert "Data Analysis" in profile["toolsets"]["selected"]

    spec_dir = tmp_path / "generated_specs"
    assert (spec_dir / "agent_config.json").exists()

