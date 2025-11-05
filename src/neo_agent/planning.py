"""Planning utilities for selecting skills."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence

from .configuration import AgentConfiguration, SkillConfiguration
from .knowledge import KnowledgeBase
from .state import AgentState


@dataclass(slots=True)
class PlanStep:
    """Represents an action the agent should perform."""

    skill: SkillConfiguration
    rationale: str


class Planner:
    """Selects skills to execute based on the state and available knowledge."""

    def __init__(
        self, configuration: AgentConfiguration, knowledge: KnowledgeBase
    ) -> None:
        self._configuration = configuration
        self._knowledge = knowledge

    def propose(self, state: AgentState, goal: str) -> List[PlanStep]:
        """Create a naive plan by choosing the first matching skill."""

        steps: List[PlanStep] = []
        for skill in self._configuration.skills:
            if skill.name in state.completed_skills:
                continue
            if goal.lower() in skill.description.lower():
                steps.append(
                    PlanStep(
                        skill=skill,
                        rationale=f"Skill '{skill.name}' matches goal '{goal}'",
                    )
                )
                break
        if not steps and self._configuration.skills:
            fallback = self._configuration.skills[0]
            steps.append(PlanStep(skill=fallback, rationale="Fallback to first skill"))
        return steps
