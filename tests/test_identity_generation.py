from __future__ import annotations

from neo_agent.services.identity_utils import generate_agent_id


def test_agent_id_stability() -> None:
    id1 = generate_agent_id("541512", "it_ops", "AIA-P", "Neo Test Agent")
    id2 = generate_agent_id("541512", "it_ops", "AIA-P", "Neo Test Agent")
    assert id1 == id2


def test_agent_id_variation() -> None:
    id1 = generate_agent_id("541512", "finance", "AIA-P", "Neo Agent")
    id2 = generate_agent_id("541512", "legal", "AIA-P", "Neo Agent")
    assert id1 != id2
