"""Knowledge base interfaces used by skills and planners."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Sequence


@dataclass(slots=True)
class KnowledgeDocument:
    """A piece of knowledge stored in the knowledge base."""

    identifier: str
    text: str
    tags: Sequence[str] = field(default_factory=tuple)


class KnowledgeBase:
    """In-memory knowledge base supporting naive keyword search."""

    def __init__(self) -> None:
        self._documents: Dict[str, KnowledgeDocument] = {}

    def add(self, document: KnowledgeDocument) -> None:
        self._documents[document.identifier] = document

    def bulk_add(self, documents: Iterable[KnowledgeDocument]) -> None:
        for document in documents:
            self.add(document)

    def search(self, keyword: str, limit: int = 3) -> List[KnowledgeDocument]:
        results: List[KnowledgeDocument] = []
        for document in self._documents.values():
            if keyword.lower() in document.text.lower():
                results.append(document)
            if len(results) >= limit:
                break
        return results

    def clear(self) -> None:
        self._documents.clear()
