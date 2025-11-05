"""Agent runtime orchestrating planning, execution and telemetry."""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
from typing import Dict, Iterable

from .configuration import AgentConfiguration, SkillConfiguration
from .context import Message
from .events import EventBus
from .exceptions import AgentError
from .knowledge import KnowledgeBase
from .logging import get_logger, log_event
from .planning import Planner, PlanStep
from .pipeline import Pipeline
from .skills import Skill, SkillRegistry
from .state import AgentState
from .telemetry import MetricsCollector

LOGGER = get_logger("runtime")


@dataclass(slots=True)
class AgentRuntime:
    """Coordinates the lifecycle of an agent session."""

    configuration: AgentConfiguration
    state: AgentState = field(default_factory=AgentState)
    skills: SkillRegistry = field(default_factory=SkillRegistry)
    knowledge: KnowledgeBase = field(default_factory=KnowledgeBase)
    events: EventBus = field(default_factory=EventBus)
    telemetry: MetricsCollector = field(default_factory=MetricsCollector)
    planner: Planner | None = None
    pipeline: Pipeline | None = None

    def initialize(self) -> None:
        LOGGER.info("Initializing agent runtime for %s", self.configuration.name)
        self._load_configured_skills(self.configuration.skills)
        self.planner = Planner(self.configuration, self.knowledge)
        self.pipeline = Pipeline.from_callables((self._execute_plan_step,))
        log_event(
            LOGGER,
            "runtime_initialized",
            {"skills": [s.name for s in self.skills.all()]},
        )

    def _load_configured_skills(self, skills: Iterable[SkillConfiguration]) -> None:
        for skill_config in skills:
            try:
                module_name, function_name = skill_config.entrypoint.split(":")
            except ValueError as exc:
                raise AgentError(
                    "Skill entrypoint must be in 'module:function' format"
                ) from exc

            try:
                module = import_module(module_name)
                function = getattr(module, function_name)
            except (ModuleNotFoundError, AttributeError) as exc:
                raise AgentError(
                    f"Unable to resolve skill entrypoint {skill_config.entrypoint}"
                ) from exc

            skill = Skill(
                name=skill_config.name,
                description=skill_config.description,
                function=function,
            )
            self.skills.register(skill)

    def dispatch(self, payload: Dict[str, object]) -> Dict[str, object]:
        if self.planner is None or self.pipeline is None:
            raise AgentError("Runtime must be initialized before dispatch")

        goal = str(payload.get("goal", payload.get("input", "")))
        plan = self.planner.propose(self.state, goal)
        log_event(LOGGER, "plan_created", {"steps": [step.skill.name for step in plan]})

        result = payload
        for step in plan:
            self.telemetry.increment("skills_planned")
            result = self.pipeline.run({**result, "__plan_step__": step})
        return result

    def _execute_plan_step(self, payload: dict) -> dict:
        step: PlanStep = payload.pop("__plan_step__")
        skill = self.skills.get(step.skill.name)

        with self.telemetry.time(f"skill.{skill.name}"):
            result = skill.execute(payload)

        self.state.record_skill(skill.name)
        self._record_message("assistant", f"Executed {skill.name}")
        log_event(LOGGER, "skill_executed", {"skill": skill.name})
        return result

    def _record_message(self, role: str, content: str) -> None:
        message = Message(role=role, content=content)
        self.state.remember(message)
        self.events.emit("message_recorded", message.to_dict())
