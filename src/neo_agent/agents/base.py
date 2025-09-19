"""Base agent implementation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List

from rich.console import Console

from ..config import AgentSettings, SkillSettings
from ..memory import ConversationMemory, MemoryEntry
from ..skills import Skill, SkillRegistry


@dataclass
class BaseAgent:
    """Modular agent with pluggable skills and memory."""

    settings: AgentSettings
    console: Console = field(default_factory=Console)
    skill_registry: SkillRegistry = field(default_factory=SkillRegistry)
    memory: ConversationMemory | None = None

    def __post_init__(self) -> None:
        if self.memory is None:
            self.memory = ConversationMemory(self.settings.memory)
        self.console.log(f"[green]Booting agent {self.settings.name} as {self.settings.role}")

    # ----- Agent lifecycle -------------------------------------------------
    def load_skills(self, factory: callable[[SkillSettings], Skill]) -> None:
        """Load skills described by the configuration."""

        self.skill_registry.from_settings(self.settings.skills, factory)

    def available_skills(self) -> Iterable[str]:
        return [skill.name for skill in self.skill_registry.list()]

    def observe(self, speaker: str, message: str, thoughts: str | None = None) -> None:
        """Persist an interaction turn."""

        assert self.memory is not None  # pragma: no cover - defensive
        self.memory.append(MemoryEntry(speaker=speaker, message=message, thoughts=thoughts))

    def plan(self, query: str) -> List[str]:
        """Simple planning: map goals to skill suggestions."""

        self.console.log(f"[bold yellow]Planning for query:[/] {query}")
        plan: List[str] = []
        for skill in self.skill_registry.list():
            if any(keyword.lower() in query.lower() for keyword in skill.description.split()):
                plan.append(skill.name)
        if not plan:
            plan = [skill.name for skill in self.skill_registry.list()]
        self.console.log(f"[cyan]Plan:[/] {', '.join(plan)}")
        return plan

    def act(self, skill_name: str, inputs: Dict[str, str]) -> str:
        """Execute a skill and store the result in memory."""

        self.console.log(f"[bold magenta]Executing skill[/]: {skill_name}")
        skill = self.skill_registry.get(skill_name)
        result = skill(self, inputs)
        self.observe(self.settings.name, result, thoughts=f"Executed {skill_name}")
        return result

    def reflect(self) -> str:
        """Summarize recent interactions for self-reflection."""

        assert self.memory is not None  # pragma: no cover
        snapshot = "\n".join(self.memory.snapshot())
        reflection = f"Reflection for {self.settings.name}:\n{snapshot}"
        self.console.log(reflection)
        return reflection

    # ----- Skill context hooks --------------------------------------------
    def log(self, message: str) -> None:
        self.console.log(message)

    def memory_context(self) -> List[str]:
        assert self.memory is not None  # pragma: no cover
        return self.memory.snapshot()


__all__ = ["BaseAgent"]
