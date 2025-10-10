"""Telemetry helpers used for collecting runtime metrics."""

from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
from time import perf_counter
from typing import Any, Dict, Generator, Mapping

from .logging import get_logger
import threading

LOGGER = get_logger("telemetry")

# Lightweight in-process event buffer for tests / introspection (Step 4)
_EVENT_BUFFER: list[dict] = []  # {'name': str, 'payload': Mapping}
_EVENT_LOCK = threading.Lock()
_EVENTS_EVICTED = 0
_EVICTION_WARNING_EMITTED = False

def get_buffered_events() -> list[dict]:  # pragma: no cover - trivial accessor
    with _EVENT_LOCK:
        return list(_EVENT_BUFFER)

def clear_buffer() -> None:  # pragma: no cover - trivial helper
    global _EVENTS_EVICTED
    with _EVENT_LOCK:
        del _EVENT_BUFFER[:]
        _EVENTS_EVICTED = 0

def get_event_stats() -> Dict[str, int]:  # pragma: no cover - trivial accessor
    with _EVENT_LOCK:
        return {"size": len(_EVENT_BUFFER), "evicted": _EVENTS_EVICTED}


class MetricsCollector:
    """Collects counters and timing metrics in-memory."""

    def __init__(self) -> None:
        self.counters: Counter[str] = Counter()
        self.timings: Dict[str, float] = {}

    def increment(self, name: str, value: int = 1) -> None:
        self.counters[name] += value
        LOGGER.debug("counter=%s value=%s", name, self.counters[name])

    @contextmanager
    def time(self, name: str) -> Generator[None, None, None]:
        start = perf_counter()
        yield
        elapsed = perf_counter() - start
        self.timings[name] = elapsed
        LOGGER.debug("timing=%s duration=%.6f", name, elapsed)


def emit_event(name: str, payload: Mapping[str, Any] | None = None) -> None:
    """Emit a telemetry event with a structured payload.

    Stores a copy in an in-memory ring buffer (simple append; size capped to 256) so tests
    can assert on emitted events without log scraping.
    """
    if not name:
        return
    data: Dict[str, Any] = {}
    if isinstance(payload, Mapping):
        data = dict(payload)
    global _EVENTS_EVICTED
    eviction_warning = False
    with _EVENT_LOCK:
        _EVENT_BUFFER.append({"name": name, "payload": data})
        if len(_EVENT_BUFFER) > 256:
            overflow = len(_EVENT_BUFFER) - 256
            if overflow > 0:
                del _EVENT_BUFFER[:overflow]
                _EVENTS_EVICTED += overflow
        # Trigger a single lightweight warning event when threshold first crossed
        global _EVICTION_WARNING_EMITTED
        if (
            not _EVICTION_WARNING_EMITTED
            and name != "telemetry:eviction_warning"
            and _EVENTS_EVICTED >= 32
        ):
            _EVICTION_WARNING_EMITTED = True
            eviction_warning = True
    LOGGER.info("event=%s payload=%s", name, data)
    if eviction_warning:
        # emit outside lock to avoid recursion risk
        try:
            emit_event("telemetry:eviction_warning", {"evicted": _EVENTS_EVICTED})
        except Exception:  # pragma: no cover
            LOGGER.debug("Failed to emit eviction warning", exc_info=True)


def emit_mbti_persona_selected(meta: Mapping[str, Any]) -> None:
    """Emit a persona:selected event when an MBTI persona is chosen."""

    if not isinstance(meta, Mapping):
        return
    code = meta.get("mbti_code") or meta.get("code")
    if not code:
        return
    axes_source = meta.get("axes")
    axes = dict(axes_source) if isinstance(axes_source, Mapping) else {}
    payload = {
        "mbti_code": str(code).upper(),
        "name": str(meta.get("name") or meta.get("nickname") or ""),
        "axes": axes,
    }
    emit_event("persona:selected", payload)


# Step 4 domain selector telemetry helpers ---------------------------------

def emit_domain_selector_changed(payload: Mapping[str, Any]) -> None:
    if not isinstance(payload, Mapping):  # defensive
        return
    minimal = {
        "topLevel": payload.get("topLevel"),
        "subdomain": payload.get("subdomain"),
        "has_naics": bool(payload.get("naics")),
    }
    emit_event("domain_selector:changed", minimal)


def emit_domain_selector_validated(payload: Mapping[str, Any]) -> None:
    if not isinstance(payload, Mapping):
        return
    naics = payload.get("naics") if isinstance(payload.get("naics"), Mapping) else None
    enriched = {
        "topLevel": payload.get("topLevel"),
        "subdomain": payload.get("subdomain"),
        "tags_count": len(payload.get("tags", [])) if isinstance(payload.get("tags"), list) else 0,
        "naics_code": naics.get("code") if isinstance(naics, Mapping) else None,
    }
    emit_event("domain_selector:validated", enriched)


def emit_domain_selector_error(message: str, context: Mapping[str, Any] | None = None) -> None:
    if not message:
        return
    payload: Dict[str, Any] = {"message": message}
    if isinstance(context, Mapping):
        for key in ("topLevel", "subdomain"):
            if key in context:
                payload[key] = context[key]
    emit_event("domain_selector:error", payload)
