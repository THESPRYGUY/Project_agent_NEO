from neo_agent.config import MemorySettings
from neo_agent.memory import ConversationMemory, MemoryEntry


def test_memory_window_respected():
    memory = ConversationMemory(MemorySettings(max_turns=2))
    memory.append(MemoryEntry("user", "hello"))
    memory.append(MemoryEntry("agent", "hi"))
    memory.append(MemoryEntry("user", "again"))

    snapshot = memory.snapshot()
    assert len(snapshot) == 2
    assert snapshot[0].startswith("agent")
    assert snapshot[1].startswith("user")


def test_include_thoughts_flag():
    memory = ConversationMemory(MemorySettings(max_turns=2, include_thoughts=False))
    memory.append(MemoryEntry("agent", "result", thoughts="internal"))
    assert "internal" not in memory.snapshot()[0]
