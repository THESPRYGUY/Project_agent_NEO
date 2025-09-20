"""Event system for the Project NEO runtime."""

from __future__ import annotations

from collections import defaultdict
from typing import Callable, DefaultDict, Dict, Iterable, List, Protocol


class EventListener(Protocol):
    """Callable signature for event listeners."""

    def __call__(self, event: str, payload: Dict[str, object]) -> None:  # pragma: no cover - Protocol
        ...


class EventBus:
    """A lightweight in-process event dispatcher."""

    def __init__(self) -> None:
        self._listeners: DefaultDict[str, List[EventListener]] = defaultdict(list)

    def subscribe(self, event: str, listener: EventListener) -> None:
        self._listeners[event].append(listener)

    def unsubscribe(self, event: str, listener: EventListener) -> None:
        if listener in self._listeners[event]:
            self._listeners[event].remove(listener)

    def emit(self, event: str, payload: Dict[str, object] | None = None) -> None:
        payload = payload or {}
        for listener in tuple(self._listeners[event]):
            listener(event, payload)

    def listeners(self, event: str) -> Iterable[EventListener]:
        return tuple(self._listeners[event])
