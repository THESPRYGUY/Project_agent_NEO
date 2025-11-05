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


def test_datastore_put_get_roundtrip():
    _ensure_import()
    from neo_agent.datastores import InMemoryStore, ConversationStore
    from neo_agent.context import Message

    store = InMemoryStore()
    assert store.get("missing") is None
    store.set("a", 1)
    store.set("b", {"x": 2})
    assert store.get("a") == 1
    assert store.get("b", {}).get("x") == 2
    # items snapshot
    items = dict(store.items())
    assert items["a"] == 1
    # conversation
    conv = ConversationStore()
    conv.append(Message(role="user", content="hi"))
    conv.extend([Message(role="assistant", content="hello")])
    exported = conv.export()
    assert exported[0]["role"] == "user"
    assert exported[1]["role"] == "assistant"


def test_datastore_missing_key_raises():
    _ensure_import()
    from neo_agent.datastores import InMemoryStore, BaseStore

    s = InMemoryStore()
    # delete missing is no-op; ensure methods don't throw
    s.delete("nope")
    assert s.get("nope") is None
    # Exercise abstract methods for coverage
    bs = BaseStore()
    with pytest.raises(NotImplementedError):
        bs.get("x")
    with pytest.raises(NotImplementedError):
        bs.set("x", 1)
    with pytest.raises(NotImplementedError):
        bs.delete("x")
    with pytest.raises(NotImplementedError):
        list(bs.items())
