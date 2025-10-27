from pathlib import Path
import sys
import pytest


pytestmark = pytest.mark.unit


def _ensure_import():
    root = Path.cwd()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


def test_event_bus_subscribe_emit_unsubscribe():
    _ensure_import()
    from neo_agent.events import EventBus
    received = {}
    def listener(evt, payload):
        received[evt] = payload
    bus = EventBus()
    bus.subscribe("x", listener)
    assert len(tuple(bus.listeners("x"))) == 1
    bus.emit("x", {"a": 1})
    assert received.get("x", {}).get("a") == 1
    bus.unsubscribe("x", listener)
    assert len(tuple(bus.listeners("x"))) == 0


def test_metrics_and_emitters():
    _ensure_import()
    from neo_agent.telemetry import MetricsCollector, emit_event, emit_mbti_persona_selected, emit_repo_generated_event
    m = MetricsCollector()
    m.increment("a")
    with m.time("t1"):
        pass
    # emit_event guards
    emit_event("")  # no-op
    emit_event("evt", {"x": 1})
    emit_event("evt", None)
    # mbti selected: invalid payloads ignored
    emit_mbti_persona_selected({})
    emit_mbti_persona_selected({"mbti_code": "entj", "name": "Exec", "axes": {"EI": "E"}})
    # repo generated event
    emit_repo_generated_event(None)
    emit_repo_generated_event({"path": "/tmp/x", "name": "repo"})

