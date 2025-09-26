"""Telemetry tests for MBTI persona instrumentation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from neo_agent import intake_app, telemetry


def test_mbti_selection_emits_persona_event(monkeypatch, tmp_path: Path) -> None:
    captured: list[dict[str, Any]] = []

    def fake_emit(name: str, payload: Any | None = None) -> None:
        captured.append({"name": name, "payload": payload})

    monkeypatch.setattr(telemetry, "emit_event", fake_emit)

    app = intake_app.create_app(base_dir=tmp_path)
    form_data = {
        "agent_name": "Test Agent",
        "agent_version": "1.0.0",
        "agent_persona": "ENTJ",
        "domain": "Finance",
        "role": "Enterprise Analyst",
    }
    parsed = {key: [value] for key, value in form_data.items()}

    profile = app._build_profile(parsed, {})

    assert len(captured) == 1
    event = captured[0]
    assert event["name"] == "persona:selected"
    payload = event["payload"] or {}
    assert payload.get("mbti_code") == "ENTJ"
    axes = payload.get("axes", {})
    assert axes.get("EI") == "E"
    assert profile["agent"]["mbti"]["mbti_code"] == "ENTJ"
