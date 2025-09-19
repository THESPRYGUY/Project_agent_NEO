"""Conversation memory primitives."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Sequence

from .config import MemorySettings


@dataclass
class MemoryEntry:
    """Single snapshot of an interaction."""

    speaker: str
    message: str
    thoughts: str | None = None

    def serialize(self, include_thoughts: bool = True) -> str:
        """Return a human-readable representation suitable for prompts."""

        base = f"{self.speaker}: {self.message}"
        if include_thoughts and self.thoughts:
            return f"{base}\n  thoughts: {self.thoughts}"
        return base


@dataclass
class ConversationMemory:
    """Rolling buffer of conversation history."""

    settings: MemorySettings
    _entries: List[MemoryEntry] = field(default_factory=list)

    def append(self, entry: MemoryEntry) -> None:
        """Add a new entry respecting the configured window size."""

        self._entries.append(entry)
        overflow = len(self._entries) - self.settings.max_turns
        if overflow > 0:
            del self._entries[:overflow]

    def extend(self, entries: Sequence[MemoryEntry]) -> None:
        for entry in entries:
            self.append(entry)

    def snapshot(self) -> List[str]:
        """Return formatted entries for consumption by language models."""

        return [entry.serialize(self.settings.include_thoughts) for entry in self._entries]

    def __iter__(self) -> Iterable[MemoryEntry]:
        return iter(self._entries)

    def __len__(self) -> int:  # pragma: no cover - trivial
        return len(self._entries)


__all__ = ["ConversationMemory", "MemoryEntry"]
