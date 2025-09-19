"""Workflow orchestration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, List

from rich.console import Console


@dataclass
class WorkflowStep:
    """Single step in a workflow."""

    name: str
    description: str
    run: Callable[[Console], str]


@dataclass
class Workflow:
    """Lightweight linear workflow runner."""

    steps: List[WorkflowStep]
    console: Console | None = None

    def __post_init__(self) -> None:
        if self.console is None:
            self.console = Console()

    def execute(self) -> List[str]:
        """Run the workflow and return collected step outputs."""

        results: List[str] = []
        for step in self.steps:
            self.console.rule(f"[bold cyan]{step.name}")
            result = step.run(self.console)
            self.console.print(result)
            results.append(result)
        return results

    def summary(self) -> str:
        """Return a formatted summary for logging or reporting."""

        outputs = self.execute()
        formatted = "\n".join(f"- {name}: {output}" for name, output in zip((s.name for s in self.steps), outputs))
        return formatted

    def describe(self) -> Iterable[str]:
        for step in self.steps:
            yield f"{step.name}: {step.description}"


__all__ = ["Workflow", "WorkflowStep"]
