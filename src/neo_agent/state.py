"""State model maintained by the agent runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Sequence

from .context import ConversationContext, Message


@dataclass(slots=True)
class AgentState:
    """Mutable runtime state for an executing agent."""

    conversation: ConversationContext = field(default_factory=ConversationContext)
    variables: Dict[str, object] = field(default_factory=dict)
    completed_skills: List[str] = field(default_factory=list)

    def remember(self, message: Message) -> None:
        self.conversation.add(message)

    def record_skill(self, skill_name: str) -> None:
        if skill_name not in self.completed_skills:
            self.completed_skills.append(skill_name)

    def get_variable(self, key: str, default: object | None = None) -> object | None:
        return self.variables.get(key, default)

    def set_variable(self, key: str, value: object) -> None:
        self.variables[key] = value

    def history(self, limit: int | None = None) -> Sequence[Message]:
        return self.conversation.history(limit)
