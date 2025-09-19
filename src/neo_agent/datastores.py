"""Simple data stores for agent state and memory."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, MutableMapping, Tuple

from .context import Message


class BaseStore:
    """Abstract mapping like interface used by the runtime."""

    def get(self, key: str, default: object | None = None) -> object | None:
        raise NotImplementedError

    def set(self, key: str, value: object) -> None:
        raise NotImplementedError

    def delete(self, key: str) -> None:
        raise NotImplementedError

    def items(self) -> Iterable[Tuple[str, object]]:
        raise NotImplementedError


class InMemoryStore(BaseStore):
    """A thread-unsafe in-memory key value store."""

    def __init__(self) -> None:
        self._data: Dict[str, object] = {}

    def get(self, key: str, default: object | None = None) -> object | None:
        return self._data.get(key, default)

    def set(self, key: str, value: object) -> None:
        self._data[key] = value

    def delete(self, key: str) -> None:
        self._data.pop(key, None)

    def items(self) -> Iterable[Tuple[str, object]]:
        return tuple(self._data.items())


@dataclass(slots=True)
class ConversationStore:
    """A specialized store for maintaining ordered conversation messages."""

    messages: List[Message] = field(default_factory=list)

    def append(self, message: Message) -> None:
        self.messages.append(message)

    def extend(self, messages: Iterable[Message]) -> None:
        self.messages.extend(messages)

    def export(self) -> List[MutableMapping[str, str]]:
        return [message.to_dict() for message in self.messages]
