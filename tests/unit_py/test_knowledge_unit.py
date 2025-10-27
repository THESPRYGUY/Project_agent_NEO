from pathlib import Path
import sys
import pytest


pytestmark = pytest.mark.unit


def _ensure_import():
    root = Path.cwd()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


def test_knowledge_add_search_clear():
    _ensure_import()
    from neo_agent.knowledge import KnowledgeBase, KnowledgeDocument
    kb = KnowledgeBase()
    kb.add(KnowledgeDocument(identifier="a", text="Alpha beta gamma"))
    kb.bulk_add([
        KnowledgeDocument(identifier="b", text="Beta rules"),
        KnowledgeDocument(identifier="c", text="Gamma world"),
    ])
    res = kb.search("beta", limit=2)
    assert len(res) >= 1
    kb.clear()
    assert kb.search("beta") == []

