"""Telemetry tests for MBTI persona instrumentation."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import concurrent.futures

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


def test_telemetry_thread_safety_and_eviction() -> None:
    """Emit many persona selection events concurrently and assert ring buffer stats.

    Ensures locking prevents race conditions and eviction metrics reflect overflow.
    """
    telemetry.clear_buffer()

    def emit(i: int) -> None:
        telemetry.emit_mbti_persona_selected({"mbti_code": f"INTP-{i}"})

    # Emit 400 events with a pool greater than 1 to exercise locking.
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
        list(ex.map(emit, range(400)))

    events = telemetry.get_buffered_events()
    stats = telemetry.get_event_stats()

    # Buffer capped
    assert len(events) == 256
    assert stats["size"] == 256
    # Evicted count correct
    assert stats["evicted"] == 400 - 256

    persona_codes = [e["payload"].get("mbti_code") for e in events if e.get("name") == "persona:selected"]
    # Oldest should be evicted
    assert "INTP-0" not in persona_codes
    # Latest should be present
    assert "INTP-399" in persona_codes
