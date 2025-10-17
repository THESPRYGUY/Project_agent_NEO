from __future__ import annotations

from pathlib import Path


def test_generate_gating_contract_tokens_present() -> None:
    js_path = Path("src/ui/generate_agent.js")
    assert js_path.exists(), "generate_agent.js should exist"
    text = js_path.read_text(encoding="utf-8")
    # Minimal browserless contract: gating must reference these fields
    assert "agent_name" in text, "Gating should require agent_name"
    assert "naics_code" in text, "Gating should require naics_code"
    assert "business_function" in text, "Gating should require business_function"
    # Role can be satisfied by code or title
    assert ("role_code" in text or "role_title" in text), "Gating should require role"

