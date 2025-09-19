"""Pipeline orchestration primitives."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, List, Protocol

from .exceptions import PipelineError


class PipelineStage(Protocol):
    """Signature of a pipeline stage."""

    def __call__(self, payload: dict) -> dict:  # pragma: no cover - interface only
        ...


@dataclass(slots=True)
class Pipeline:
    """A sequence of pipeline stages executed in order."""

    stages: List[PipelineStage]

    def run(self, payload: dict) -> dict:
        current = payload
        for stage in self.stages:
            try:
                current = stage(current)
            except Exception as exc:  # pragma: no cover - defensive
                raise PipelineError(f"Pipeline stage {stage} failed") from exc
        return current

    @classmethod
    def from_callables(cls, callables: Iterable[Callable[[dict], dict]]) -> "Pipeline":
        return cls(list(callables))
