"""Telemetry helpers used for collecting runtime metrics."""

from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
from time import perf_counter
from typing import Any, Dict, Generator, Mapping

from .logging import get_logger

LOGGER = get_logger("telemetry")


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
    """Emit a telemetry event with a structured payload."""

    if not name:
        return
    data: Dict[str, Any] = {}
    if isinstance(payload, Mapping):
        data = dict(payload)
    LOGGER.info("event=%s payload=%s", name, data)


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


def emit_repo_generated_event(result: Mapping[str, Any] | None = None) -> None:
    """Emit a repo:generated event with minimal context.

    Accepts an optional mapping from the repo generator containing fields like
    path/name. The schema is intentionally loose so this stays non-breaking.
    """

    if not isinstance(result, Mapping):
        emit_event("repo:generated", {})
        return
    payload: Dict[str, Any] = {}
    for k, v in result.items():
        if not isinstance(k, str):
            continue
        if isinstance(v, (str, int, float, bool)):
            payload[k] = v
        else:
            payload[k] = str(v)
    emit_event("repo:generated", payload)
