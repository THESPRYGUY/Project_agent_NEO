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
        "notes": "Test submission",
        "linkedin_url": "",
        "traits_payload": json.dumps(
            {
                "traits": {
                    "detail_oriented": 60,
                    "collaborative": 70,
                    "proactive": 75,
                    "strategic": 80,
                    "empathetic": 55,
                    "experimental": 65,
                    "efficient": 68,
                },
                "provenance": "manual",
                "version": "1.0",
            }
        ),
        "preferences_payload": json.dumps(
            {
                "autonomy": 80,
                "confidence": 65,
                "collaboration": 90,
                "comm_style": "executive_brief",
                "collab_mode": "pair_build",
                "provenance": "manual",
                "version": "1.0",
            }
        ),
        "toolsets_payload": json.dumps(
            {
                "capabilities": ["reasoning_planning", "analysis_modeling"],
                "connectors": [
                    {
                        "name": "email",
                        "scopes": ["read/*", "send:internal"],
                        "instances": [{"label": "work", "secret_ref": "vault://email/work"}],
                    }
                ],
                "governance": {
                    "storage": "kv",
                    "redaction": ["mask_pii", "never_store_secrets"],
                    "retention": "default_365",
                    "data_residency": "auto",
                },
                "ops": {
                    "env": "staging",
                    "dry_run": True,
                    "latency_slo_ms": 900,
                    "cost_budget_usd": 7.5,
                },
            }
        ),
    }

    response = _invoke(app, "POST", post_data)
    assert b"Agent profile generated successfully" in response

    profile_path = tmp_path / "agent_profile.json"
    assert profile_path.exists()

    with profile_path.open("r", encoding="utf-8") as handle:
        profile = json.load(handle)

    assert profile["agent"]["name"] == "Test Agent"
    assert "analysis_modeling" in profile["toolsets"]["capabilities"]
    assert profile["toolsets"]["connectors"][0]["name"] == "email"
    assert profile["traits"]["traits"]["strategic"] == 80
    assert profile["preferences"]["autonomy"] == 80
    assert profile["preferences"]["prefs_knobs"]["confirmation_gate"] == "none"
    assert profile["request_envelope"]["preferences"]["prefs_knobs"]["handoff_freq"] == "high"
    assert profile["request_envelope"]["toolsets"]["ops"]["latency_slo_ms"] == 900
    assert "persona" in profile

    spec_dir = tmp_path / "generated_specs"
    assert (spec_dir / "agent_config.json").exists()

