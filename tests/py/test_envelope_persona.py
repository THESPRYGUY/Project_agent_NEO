"""Persona persistence and envelope smoke tests."""

from __future__ import annotations

import io
import json
from pathlib import Path
from urllib.parse import urlencode

from neo_agent.intake_app import create_app


def _json_request(app, path: str, method: str = "GET", payload: dict | None = None):
    body = b""
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "SERVER_NAME": "testserver",
        "SERVER_PORT": "80",
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": "http",
        "wsgi.input": io.BytesIO(body),
        "CONTENT_LENGTH": str(len(body)),
        "CONTENT_TYPE": "application/json",
    }

    captured: list[dict] = []

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        captured.append({"status": status, "headers": headers})

    response_iter = app.wsgi_app(environ, start_response)
    response_body = b"".join(response_iter)
    status = captured[0]["status"]
    if not status.startswith("200"):
        raise AssertionError(f"Unexpected status {status}: {response_body!r}")
    return json.loads(response_body.decode("utf-8"))


def _submit_form(app, data: dict[str, list[str] | str]) -> None:
    encoded = urlencode(data, doseq=True).encode("utf-8")
    environ = {
        "REQUEST_METHOD": "POST",
        "PATH_INFO": "/",
        "QUERY_STRING": "",
        "SERVER_NAME": "testserver",
        "SERVER_PORT": "80",
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": "http",
        "wsgi.input": io.BytesIO(encoded),
        "CONTENT_LENGTH": str(len(encoded)),
        "CONTENT_TYPE": "application/x-www-form-urlencoded",
    }

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        assert status == "200 OK"

    response_iter = app.wsgi_app(environ, start_response)
    b"".join(response_iter)


def test_persona_state_roundtrip(tmp_path: Path) -> None:
    app = create_app(base_dir=tmp_path)

    config = _json_request(app, "/api/persona/config")
    assert "mbti_types" in config
    assert len(config["mbti_types"]) >= 4

    state = _json_request(app, "/api/persona/state")
    assert state["operator"] is None

    payload = {
        "operator": {
            "code": "INTJ",
            "name": "Architect",
            "nickname": "Strategic Visionary",
        },
        "agent": {
            "code": "ENFJ",
            "rationale": ["Compatibility with operator: 75%"],
            "compatibility": 75,
            "role_fit": 90,
            "blended": 83,
        },
        "alternates": [{"code": "INFJ", "blended": 78}],
    }

    saved = _json_request(app, "/api/persona/state", method="POST", payload=payload)
    assert saved["agent"]["code"] == "ENFJ"

    roundtrip = _json_request(app, "/api/persona/state")
    assert roundtrip["agent"]["code"] == "ENFJ"

    form_payload = {
        "agent_name": "Persona Test Agent",
        "agent_version": "1.0.0",
        "agent_persona": "Dual MBTI",
        "domain": "Technology",
        "role": "Strategy Consultant",
        "toolsets": ["Workflow Orchestration"],
        "attributes": ["Strategic"],
        "autonomy": "65",
        "confidence": "60",
        "collaboration": "70",
        "communication_style": "Formal",
        "collaboration_mode": "Solo",
        "notes": "Persona integration test",
        "linkedin_url": "",
    }

    _submit_form(app, form_payload)

    profile_path = tmp_path / "agent_profile.json"
    assert profile_path.exists(), "Profile file should be written after submission"

    with profile_path.open("r", encoding="utf-8") as handle:
        profile = json.load(handle)

    assert profile["persona"]["agent"]["code"] == "ENFJ"
    assert profile["persona"]["operator"]["code"] == "INTJ"
