from __future__ import annotations

from pathlib import Path

from neo_agent.intake_app import IntakeApplication


def test_save_persona_state_derives_domain(tmp_path: Path) -> None:
    app = IntakeApplication(base_dir=tmp_path)
    state = {
        "operator": {"code": "INTJ"},
        "agent": {
            "code": "INTJ",
            "rationale": ["Domain not provided; using generic persona baseline."],
            "business_function": "Engineering/IT",
        },
    }

    saved = app._save_persona_state(state)
    agent = saved["agent"]

    assert agent["domain"] == "Technology"
    assert agent["domain_source"] == "derived"
    assert "Domain inferred from Business Function: Technology." in agent["rationale"]
    assert all("generic persona baseline" not in line for line in agent["rationale"])


def test_save_persona_state_role_only_fallback(tmp_path: Path) -> None:
    app = IntakeApplication(base_dir=tmp_path)
    state = {
        "operator": {"code": "INTJ"},
        "agent": {
            "code": "INTJ",
            "rationale": ["Domain not provided; using generic persona baseline."],
            "role_code": "ENG:PLATFORM",
        },
    }

    saved = app._save_persona_state(state)
    agent = saved["agent"]

    assert agent.get("domain") in (None, "")
    assert agent["domain_source"] == "none"
    assert "Role prior used (no domain)." in agent["rationale"]
    assert all("generic persona baseline" not in line for line in agent["rationale"])
