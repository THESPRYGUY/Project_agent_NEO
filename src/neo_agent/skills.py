"""Skill primitives for Project NEO."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Protocol

from .config import SkillSettings, ToolConfig


class SkillContext(Protocol):
    """Minimal interface agents provide to skills."""

    def log(self, message: str) -> None:
        ...


@dataclass
class Skill:
    """Concrete capability that can be executed by an agent."""

    name: str
    description: str
    handler: Callable[[SkillContext, Dict[str, str]], str]
    settings: SkillSettings | None = None

    def __call__(self, context: SkillContext, inputs: Dict[str, str]) -> str:
        return self.handler(context, inputs)

    @property
    def tools(self) -> List[ToolConfig]:
        return list(self.settings.tools) if self.settings else []


@dataclass
class SkillRegistry:
    """Registry mapping skill names to implementations."""

    skills: Dict[str, Skill] = field(default_factory=dict)

    def register(self, skill: Skill) -> None:
        if skill.name in self.skills:
            raise ValueError(f"Skill '{skill.name}' already registered")
        self.skills[skill.name] = skill

    def get(self, name: str) -> Skill:
        try:
            return self.skills[name]
        except KeyError as exc:  # pragma: no cover - defensive
            raise KeyError(f"Unknown skill '{name}'") from exc

    def list(self) -> Iterable[Skill]:
        return self.skills.values()

    def from_settings(self, settings: Iterable[SkillSettings], factory: Callable[[SkillSettings], Skill]) -> None:
        for skill_setting in settings:
            self.register(factory(skill_setting))


__all__ = ["Skill", "SkillRegistry", "SkillContext"]
