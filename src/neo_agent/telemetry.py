"""Telemetry helpers used for collecting runtime metrics."""

from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
from time import perf_counter
from typing import Dict, Generator

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
