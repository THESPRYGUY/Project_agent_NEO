from __future__ import annotations

import io
import json
from pathlib import Path
import pytest


pytestmark = pytest.mark.unit


def _ensure_import() -> None:
    import sys
    from pathlib import Path
    root = Path.cwd()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


def _call_save(app, payload: dict):
    raw = json.dumps(payload).encode("utf-8")
    env = {
        "REQUEST_METHOD": "POST",
        "PATH_INFO": "/save",
        "QUERY_STRING": "",
        "SERVER_NAME": "unit",
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


def test_migrate_legacy_only_minimal_payload_ok():
    _ensure_import()
    from neo_build.adapters.legacy_to_v3 import transform

    legacy_payload = {
        "identity": {"agent_id": "AG-1", "display_name": "Agent One", "owners": ["CAIO"]},
        "legacy": {
            "sector": "Finance",
            "role": "AIA-P",
            "regulators": ["SEC"],
            "traits": ["Analytical"],
            "voice": ["Crisp"],
            "tools": ["email"],
            "capabilities": ["plan"],
            "human_gate": {"actions": ["external_email_send"]},
            "memory": {"scopes": ["semantic:domain/*"], "packs": ["base"], "sources": ["index:docs_v1"]},
            "kpi": {"PRI_min": 0.95, "HAL_max": 0.02, "AUD_min": 0.9},
        },
    }

    v3, diag = transform(legacy_payload)
    assert v3["intake_version"] == "v3.0"
    assert v3["role"]["role_code"] == "AIA-P"
    assert v3["sector_profile"]["sector"] == "Finance"
    assert v3["sector_profile"]["regulatory"] == ["SEC"]
    assert v3["persona"]["traits"] == ["Analytical"]
    assert v3["brand"]["voice"]["voice_traits"] == ["Crisp"]
    assert set(v3["capabilities_tools"]["tool_suggestions"]) == {"email", "plan"}
    assert v3["capabilities_tools"]["human_gate"]["actions"] == ["external_email_send"]
    assert v3["memory"]["memory_scopes"] == ["semantic:domain/*"]
    assert v3["memory"]["initial_memory_packs"] == ["base"]
    assert v3["memory"]["data_sources"] == ["index:docs_v1"]
    assert v3["governance_eval"]["gates"]["PRI_min"] == 0.95
    assert v3["governance_eval"]["gates"]["hallucination_max"] == 0.02
    assert v3["governance_eval"]["gates"]["audit_min"] == 0.9
    assert diag["dropped"] == []


def test_migrate_drops_unknown_values_but_succeeds():
    _ensure_import()
    from neo_build.adapters.legacy_to_v3 import transform

    legacy_payload = {
        "legacy": {
            "sector": "Tech",
            "unknown_field": "x",
            "kpi": {"PRI_min": 0.9},
        }
    }
    v3, diag = transform(legacy_payload)
    assert v3["sector_profile"]["sector"] == "Tech"
    assert diag["dropped"] == ["legacy.unknown_field"]


def test_conflict_role_legacy_plus_v3_rejected_400(tmp_path: Path):
    _ensure_import()
    from neo_agent.intake_app import create_app
    app = create_app(base_dir=tmp_path)
    payload = {
        "intake_version": "v3.0",
        "identity": {"agent_id": "X", "display_name": "X", "owners": ["CAIO"]},
        "context": {"naics": {"code": "541110"}},
        "role": {"function_code": "fn", "role_code": "rc"},
        "governance_eval": {"gates": {"PRI_min": 0.95, "hallucination_max": 0.02, "audit_min": 0.9}},
        "legacy": {"role": "OLD"},
    }
    st, _, raw = _call_save(app, payload)
    assert st.startswith("400")
    body = json.loads(raw.decode("utf-8"))
    assert body.get("code") == "DUPLICATE_LEGACY_V3_CONFLICT"
    assert any(c.get("legacy_path", "").startswith("legacy.role") for c in body.get("conflicts", []))
    assert any("Legacy field not allowed in v3" in e for e in body.get("errors", []))


def test_conflict_persona_legacy_plus_v3_rejected_400(tmp_path: Path):
    _ensure_import()
    from neo_agent.intake_app import create_app
    app = create_app(base_dir=tmp_path)
    payload = {
        "intake_version": "v3.0",
        "identity": {"agent_id": "X", "display_name": "X", "owners": ["CAIO"]},
        "context": {"naics": {"code": "541110"}},
        "role": {"function_code": "fn", "role_code": "rc"},
        "governance_eval": {"gates": {"PRI_min": 0.95, "hallucination_max": 0.02, "audit_min": 0.9}},
        "persona": {"traits": ["Crisp"]},
        "legacy": {"traits": ["LegacyTrait"]},
    }
    st, _, raw = _call_save(app, payload)
    assert st.startswith("400")
    body = json.loads(raw.decode("utf-8"))
    assert body.get("code") == "DUPLICATE_LEGACY_V3_CONFLICT"


def test_conflict_kpi_legacy_plus_v3_rejected_400(tmp_path: Path):
    _ensure_import()
    from neo_agent.intake_app import create_app
    app = create_app(base_dir=tmp_path)
    payload = {
        "intake_version": "v3.0",
        "identity": {"agent_id": "X", "display_name": "X", "owners": ["CAIO"]},
        "context": {"naics": {"code": "541110"}},
        "role": {"function_code": "fn", "role_code": "rc"},
        "governance_eval": {"gates": {"PRI_min": 0.95, "hallucination_max": 0.02, "audit_min": 0.9}},
        "legacy": {"kpi": {"PRI_min": 0.9}},
    }
    st, _, raw = _call_save(app, payload)
    assert st.startswith("400")
    body = json.loads(raw.decode("utf-8"))
    assert body.get("code") == "DUPLICATE_LEGACY_V3_CONFLICT"


def test_no_conflict_when_only_v3_present(tmp_path: Path):
    _ensure_import()
    from neo_agent.intake_app import create_app
    app = create_app(base_dir=tmp_path)
    payload = {
        "intake_version": "v3.0",
        "identity": {"agent_id": "X", "display_name": "X", "owners": ["CAIO"]},
        "context": {"naics": {"code": "541110"}},
        "role": {"function_code": "fn", "role_code": "rc"},
        "governance_eval": {"gates": {"PRI_min": 0.95, "hallucination_max": 0.02, "audit_min": 0.9}},
    }
    st, _, raw = _call_save(app, payload)
    assert st.startswith("200")


def test_telemetry_emitted_on_legacy_detected(tmp_path: Path, monkeypatch):
    _ensure_import()
    from neo_agent import intake_app as mod
    from neo_agent.intake_app import create_app

    calls = []
    def fake_emit(event, payload):  # type: ignore
        calls.append((event, payload))

    monkeypatch.setattr(mod, "emit_event", fake_emit, raising=False)
    app = create_app(base_dir=tmp_path)

    # Legacy-only (no v3 concepts) triggers migration path and telemetry
    payload = {
        "identity": {"agent_id": "X", "display_name": "X", "owners": ["CAIO"]},
        "legacy": {"memory": {"scopes": ["s1"]}},
    }
    st, _, _ = _call_save(app, payload)
    # May be 400 due to missing v3 required fields after migration; telemetry should still be emitted
    assert any(ev == "intake.legacy" and p.get("legacy_detected") for ev, p in calls)

