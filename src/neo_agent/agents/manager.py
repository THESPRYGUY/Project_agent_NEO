"""Agent manager orchestrating multiple agents."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List

from rich.console import Console

from ..config import AgentSettings
from .base import BaseAgent


@dataclass
class AgentManager:
    """Manage a cohort of collaborating agents."""

    console: Console = field(default_factory=Console)
    agents: Dict[str, BaseAgent] = field(default_factory=dict)

    def create_agent(self, settings: AgentSettings, skill_factory) -> BaseAgent:
        if settings.name in self.agents:
            raise ValueError(f"Agent '{settings.name}' already exists")
        agent = BaseAgent(settings=settings, console=self.console)
        agent.load_skills(skill_factory)
        self.agents[settings.name] = agent
        return agent

    def get_agent(self, name: str) -> BaseAgent:
        try:
            return self.agents[name]
        except KeyError as exc:  # pragma: no cover - defensive
            raise KeyError(f"Unknown agent '{name}'") from exc

    def broadcast(self, speaker: str, message: str) -> None:
        self.console.log(f"[bold blue]Broadcast[/] from {speaker}: {message}")
        for agent in self.agents.values():
            agent.observe(speaker, message)

    def coordinate(self, query: str) -> Dict[str, List[str]]:
        """Ask each agent to propose a plan for the query."""

        plans: Dict[str, List[str]] = {}
        for name, agent in self.agents.items():
            plans[name] = agent.plan(query)
        return plans

    def run_skill(self, agent_name: str, skill_name: str, inputs: Dict[str, str]) -> str:
        agent = self.get_agent(agent_name)
        return agent.act(skill_name, inputs)

    def list_agents(self) -> Iterable[str]:
        return self.agents.keys()


__all__ = ["AgentManager"]
