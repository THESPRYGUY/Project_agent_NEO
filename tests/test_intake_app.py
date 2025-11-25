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


def _base_form_data() -> dict[str, list[str] | str]:
    return {
        "agent_name": "Test Agent",
        "agent_version": "1.0.0",
        "agent_persona": "ENTJ",
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


def test_intake_form_submission(tmp_path: Path) -> None:
    app = create_app(base_dir=tmp_path)

    body = _invoke(app, "GET", {})
    assert b"Project NEO Agent Intake" in body

    post_data = {
        "agent_name": "Test Agent",
        "agent_version": "1.0.0",
        "agent_persona": "ENTJ",
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

    # Trigger a deterministic build then verify last-build pointer
    # (Some form submissions may defer actual build to the explicit /build step)
    def _wsgi_call(method: str, path: str, body: dict | None = None):
        raw = json.dumps(body or {}).encode("utf-8")
        env = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path,
            "QUERY_STRING": "",
            "SERVER_NAME": "test",
            "SERVER_PORT": "80",
            "wsgi.version": (1, 0),
            "wsgi.url_scheme": "http",
            "wsgi.input": io.BytesIO(raw),
            "CONTENT_LENGTH": str(len(raw)),
        }
        status_headers = []

        def start_response(status, headers):
            status_headers.append((status, headers))

        data = b"".join(app.wsgi_app(env, start_response))
        status, headers = status_headers[0]
        return status, dict(headers), data

    st, _, _ = _wsgi_call("POST", "/build", {})
    assert st == "200 OK"
    last_path = tmp_path / "_generated" / "_last_build.json"
    assert last_path.exists()

    profile_path = tmp_path / "agent_profile.json"
    assert profile_path.exists()

    with profile_path.open("r", encoding="utf-8") as handle:
        profile = json.load(handle)

    assert profile["agent"]["name"] == "Test Agent"
    assert "Data Analysis" in profile["toolsets"]["selected"]
    assert profile["agent"]["persona"] == "ENTJ"
    assert profile["agent"]["mbti"]["mbti_code"] == "ENTJ"

    # Specs now live under last build's spec_preview
    last_path = tmp_path / "_generated" / "_last_build.json"
    assert last_path.exists()
    last = json.loads(last_path.read_text(encoding="utf-8"))
    outdir = Path(last["outdir"])
    spec_dir = outdir / "spec_preview"
    assert (spec_dir / "agent_config.json").exists()


def test_mbti_payload_enriched(tmp_path: Path) -> None:
    app = create_app(base_dir=tmp_path)
    saved = app._save_persona_state(
        {
            "operator": {"code": "INFJ"},
            "agent": {"code": "INTJ"},
            "alternates": [{"code": "ENTJ"}],
        }
    )
    agent_block = saved.get("agent", {})
    mbti_block = agent_block.get("mbti", {})
    assert mbti_block.get("mbti_code") == "INTJ"
    axes = mbti_block.get("axes", {})
    assert axes.get("EI") == "I"
    reloaded = app._load_persona_state()
    assert reloaded.get("persona_details", {}).get("mbti_code") == "INTJ"


def test_repo_scaffold_contains_mbti(tmp_path: Path) -> None:
    app = create_app(base_dir=tmp_path)
    app._save_persona_state(
        {
            "operator": {"code": "INFJ"},
            "agent": {"code": "ENTJ"},
            "alternates": [],
        }
    )
    post_data = {
        "agent_name": "MBTI Agent",
        "agent_version": "1.0.0",
        "agent_persona": "ENTJ",
        "domain": "Finance",
        "role": "Enterprise Analyst",
        "toolsets": ["Data Analysis"],
        "attributes": ["Strategic"],
        "autonomy": "70",
        "confidence": "65",
        "collaboration": "55",
        "communication_style": "Formal",
        "collaboration_mode": "Cross-Functional",
        "notes": "Persona persistence smoke",
        "linkedin_url": "",
    }
    _invoke(app, "POST", post_data)

    # Kick off build to populate last-build pointer
    def _wsgi_call(method: str, path: str, body: dict | None = None):
        raw = json.dumps(body or {}).encode("utf-8")
        env = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path,
            "QUERY_STRING": "",
            "SERVER_NAME": "test",
            "SERVER_PORT": "80",
            "wsgi.version": (1, 0),
            "wsgi.url_scheme": "http",
            "wsgi.input": io.BytesIO(raw),
            "CONTENT_LENGTH": str(len(raw)),
        }
        status_headers = []

        def start_response(status, headers):
            status_headers.append((status, headers))

        data = b"".join(app.wsgi_app(env, start_response))
        status, headers = status_headers[0]
        return status, dict(headers), data

    st, _, _ = _wsgi_call("POST", "/build", {})
    assert st == "200 OK"
    # Specs path moved to spec_preview under SoT outdir
    last_path = tmp_path / "_generated" / "_last_build.json"
    assert last_path.exists()
    last = json.loads(last_path.read_text(encoding="utf-8"))
    config_path = Path(last["outdir"]) / "spec_preview" / "agent_config.json"
    with config_path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)
    persona_meta = config.get("metadata", {}).get("persona", {})
    assert persona_meta.get("mbti_code") == "ENTJ"
    assert persona_meta.get("axes", {}).get("EI") == "E"
    assert isinstance(persona_meta.get("suggested_traits", []), list)


def test_api_generate_agent_repo(tmp_path: Path) -> None:
    # Spin app, then call /api/agent/generate with minimal v3-style profile
    app = create_app(base_dir=tmp_path)

    # Build payload
    profile = {
        "agent": {"name": "API Agent", "version": "1.0.0"},
        "classification": {
            "naics": {
                "code": "541110",
                "title": "Offices of Lawyers",
                "level": 6,
                "lineage": [],
            }
        },
        "context": {"region": ["CA"]},
        "business_function": "legal_compliance",
        "role": {"code": "AIA-P", "title": "Legal & Compliance Lead"},
    }

    body = json.dumps({"profile": profile}).encode("utf-8")
    environ = {
        "REQUEST_METHOD": "POST",
        "PATH_INFO": "/api/agent/generate",
        "QUERY_STRING": "",
        "SERVER_NAME": "testserver",
        "SERVER_PORT": "80",
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": "http",
        "wsgi.input": io.BytesIO(body),
        "CONTENT_LENGTH": str(len(body)),
    }

    status_headers: list[tuple[str, list[tuple[str, str]]]] = []

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        status_headers.append((status, headers))

    response_iter = app.wsgi_app(environ, start_response)
    body_bytes = b"".join(response_iter)
    assert status_headers[0][0] == "200 OK"
    payload = json.loads(body_bytes.decode("utf-8"))
    assert payload.get("status") == "ok"
    gen_root = Path(payload.get("out_dir"))
    # Writers place packs directly in the target directory; check canonical file present
    expect = gen_root / "01_README+Directory-Map_v2.json"
    assert expect.exists(), f"missing {expect}"


def test_advanced_overrides_persist_on_form_post(tmp_path: Path) -> None:
    app = create_app(base_dir=tmp_path)
    post_data = _base_form_data()
    post_data["advanced_overrides"] = '{"foo": "bar", "flag": true}'

    body = _invoke(app, "POST", post_data)

    profile_path = tmp_path / "agent_profile.json"
    assert profile_path.exists()
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    assert profile.get("advanced_overrides") == {"foo": "bar", "flag": True}
    assert b"_raw_advanced_overrides" not in body
    assert b"Validation error" not in body.split(b"</h1>", 1)[0]


def test_advanced_overrides_omitted_when_empty(tmp_path: Path) -> None:
    app = create_app(base_dir=tmp_path)
    post_data = _base_form_data()
    post_data["advanced_overrides"] = "   "

    _invoke(app, "POST", post_data)

    profile_path = tmp_path / "agent_profile.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    assert "advanced_overrides" not in profile


def test_advanced_overrides_invalid_json_blocks_save(tmp_path: Path) -> None:
    app = create_app(base_dir=tmp_path)

    # Seed a valid profile to confirm it remains untouched
    _invoke(app, "POST", _base_form_data())
    profile_path = tmp_path / "agent_profile.json"
    baseline = profile_path.read_text(encoding="utf-8")
    baseline_mtime = profile_path.stat().st_mtime_ns

    bad_payload = _base_form_data()
    bad_payload["advanced_overrides"] = '{"foo": "bar",}'

    body = _invoke(app, "POST", bad_payload)
    assert b"Advanced Overrides must be valid JSON" in body
    assert b"{&quot;foo&quot;: &quot;bar&quot;,}" in body
    assert b"_raw_advanced_overrides" not in body
    assert b"Validation error" not in body.split(b"</h1>", 1)[0]  # no header blob
    assert profile_path.read_text(encoding="utf-8") == baseline
    assert profile_path.stat().st_mtime_ns == baseline_mtime


def test_advanced_overrides_non_object_blocks_save(tmp_path: Path) -> None:
    app = create_app(base_dir=tmp_path)

    bad_payload = _base_form_data()
    bad_payload["advanced_overrides"] = '["not", "an", "object"]'

    body = _invoke(app, "POST", bad_payload)
    assert b"Advanced Overrides JSON must be an object" in body
    assert b"[&quot;not&quot;, &quot;an&quot;, &quot;object&quot;]" in body
    assert b"_raw_advanced_overrides" not in body
    assert b"Validation error" not in body.split(b"</h1>", 1)[0]
    profile_path = tmp_path / "agent_profile.json"
    assert not profile_path.exists()
