"""Skill abstractions and builtin implementations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Iterable, Mapping

from .exceptions import SkillExecutionError
from .logging import get_logger

LOGGER = get_logger("skills")


@dataclass(slots=True)
class Skill:
    """Callable unit of work executed by the runtime."""

    name: str
    description: str
    function: Callable[[dict], dict]

    def execute(self, payload: dict) -> dict:
        try:
            LOGGER.debug("Executing skill %s with payload %s", self.name, payload)
            return self.function(payload)
        except Exception as exc:  # pragma: no cover - safety
            raise SkillExecutionError(f"Skill {self.name} failed") from exc


class SkillRegistry:
    """Registry that exposes skills by name."""

    def __init__(self) -> None:
        self._skills: Dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        self._skills[skill.name] = skill

    def get(self, name: str) -> Skill:
        try:
            return self._skills[name]
        except KeyError as exc:  # pragma: no cover - defensive
            raise SkillExecutionError(f"Unknown skill: {name}") from exc

    def configure(self, mappings: Mapping[str, Callable[[dict], dict]]) -> None:
        for name, function in mappings.items():
            skill = Skill(name=name, description=function.__doc__ or name, function=function)
            self.register(skill)

    def all(self) -> Iterable[Skill]:
        return tuple(self._skills.values())


def echo(payload: dict) -> dict:
    """Return the payload unchanged."""

    return {**payload, "echo": payload.get("input")}


def greet(payload: dict) -> dict:
    """Return a friendly greeting for the provided input."""

    message = str(payload.get("input", ""))
    return {**payload, "greeting": f"Hello {message}"}
