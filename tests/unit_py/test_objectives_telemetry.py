from __future__ import annotations

import json
from pathlib import Path

import pytest


pytestmark = pytest.mark.unit


def test_build_events_include_objectives_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Import inside test to allow monkeypatching emit_event before use
    import neo_agent.intake_app as appmod
    from neo_agent.intake_app import IntakeApplication

    emitted: list[tuple[str, dict]] = []

    def _emit(name: str, payload: dict | None = None) -> None:  # type: ignore[override]
        emitted.append((name, payload or {}))

    monkeypatch.setattr(appmod, "emit_event", _emit, raising=False)

    fixture_path = Path.cwd() / "fixtures" / "sample_profile.json"
    profile = json.loads(fixture_path.read_text(encoding="utf-8"))
    role_profile = profile.get("role_profile")
    if not isinstance(role_profile, dict):
        role_profile = {}
        profile["role_profile"] = role_profile
    role_profile["objectives"] = ["Ship reliably"]
    role_profile["objectives_status"] = "explicit"

    app = IntakeApplication(base_dir=tmp_path)
    status, resp = app._transactional_build(profile, {"neo.req_id": "req-telemetry"})
    assert status == 200
    assert resp.get("objectives_status") == "explicit"
    assert resp.get("objectives_count") == 1

    def _payload(event_name: str) -> dict:
        for name, payload in emitted:
            if name == event_name:
                return payload
        raise AssertionError(f"event {event_name} not emitted")

    for event_name in ("build:start", "build:success", "build.success.time_ms"):
        payload = _payload(event_name)
        assert payload.get("objectives_status") == "explicit"
        assert payload.get("objectives_count") == 1
        assert "Ship reliably" not in json.dumps(payload)
