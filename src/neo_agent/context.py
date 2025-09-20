"""Conversation context and message primitives."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable, List, Sequence


@dataclass(slots=True)
class Message:
    """Represents an utterance exchanged between the agent and an external actor."""

    role: str
    content: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, str]:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass(slots=True)
class ConversationContext:
    """Container for messages that make up the conversation history."""

    messages: List[Message] = field(default_factory=list)

    def add(self, message: Message) -> None:
        self.messages.append(message)

    def extend(self, new_messages: Iterable[Message]) -> None:
        self.messages.extend(new_messages)

    def history(self, limit: int | None = None) -> Sequence[Message]:
        if limit is None:
            return tuple(self.messages)
        if limit <= 0:
            return tuple()
        return tuple(self.messages[-limit:])
