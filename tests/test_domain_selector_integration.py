"""Domain selector integration smoke tests."""

from __future__ import annotations

import json
from pathlib import Path

from neo_agent.intake_app import create_app
from neo_agent.spec_generator import generate_agent_specs


import pytest

@pytest.mark.skip(reason="Legacy domain selector deprecated; replaced by NAICS/function classification")
def test_domain_selector_basic_persist(tmp_path: Path) -> None:
    app = create_app(base_dir=tmp_path)

    payload = {
        "agent_name": ["Selector Agent"],
        "agent_version": ["1.0.0"],
        "agent_persona": ["ENTJ"],
        "domain": ["Finance"],
        "role": ["Enterprise Analyst"],
        "toolsets": ["Data Analysis"],
        "attributes": ["Strategic"],
        "autonomy": ["60"],
        "confidence": ["55"],
        "collaboration": ["45"],
        "communication_style": ["Formal"],
        "collaboration_mode": ["Solo"],
        "notes": ["Domain selector integration"],
        "domain_selector": [
            json.dumps(
                {
                    "topLevel": "Strategic Functions",
                    "subdomain": "Workflow Orchestration",
                    "tags": ["workflow-orchestration", "ops"],
                }
            )
        ],
    }

    profile = app._build_profile(payload, {})
    selector = profile["agent"].get("domain_selector")
    assert selector is not None
    assert selector["topLevel"] == "Strategic Functions"
    assert selector["subdomain"] == "Workflow Orchestration"
    assert selector["tags"] == ["workflow-orchestration", "ops"]

    outputs = generate_agent_specs(profile, tmp_path / "generated")
    config_path = outputs["agent_config"]
    with config_path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)

    metadata = config.get("metadata", {})
    metadata_selector = metadata.get("domain_selector", {})
    assert metadata_selector.get("topLevel") == "Strategic Functions"

    persona_meta = metadata.get("persona", {})
    assert persona_meta.get("mbti_code") == "ENTJ"
