"""Edge case tests for tag normalization in domain selector validation."""
from __future__ import annotations

import json
from pathlib import Path

from neo_agent.intake_app import create_app


def make_payload(tags):
    return {
        "agent_name": ["Tag Agent"],
        "agent_version": ["1.0.0"],
        "agent_persona": ["ENTJ"],
        "domain": ["Finance"],
        "role": ["Enterprise Analyst"],
        "toolsets": ["Data Analysis"],
        "attributes": ["Strategic"],
        "autonomy": ["50"],
        "confidence": ["50"],
        "collaboration": ["50"],
        "communication_style": ["Formal"],
        "collaboration_mode": ["Solo"],
        "notes": ["Tag test"],
        "domain_selector": [json.dumps({
            "topLevel": "Strategic Functions",
            "subdomain": "Workflow Orchestration",
            "tags": tags,
        })],
    }


def extract_tags(profile):
    return profile["agent"].get("domain_selector", {}).get("tags")


def test_duplicates_preserve_first_order(tmp_path: Path):
    app = create_app(base_dir=tmp_path)
    payload = make_payload(["ops", "ops", "workflow", "ops", "workflow"])
    profile = app._build_profile(payload, {})
    assert extract_tags(profile) == ["ops", "workflow"]


def test_whitespace_and_empty_filtered(tmp_path: Path):
    app = create_app(base_dir=tmp_path)
    payload = make_payload(["  alpha  ", " ", "", None, "beta"])
    profile = app._build_profile(payload, {})
    assert extract_tags(profile) == ["alpha", "beta"]


def test_non_string_values_coerced(tmp_path: Path):
    app = create_app(base_dir=tmp_path)
    payload = make_payload([123, True, False, {"a":1}, ["x"], "plain"])  # type: ignore
    profile = app._build_profile(payload, {})
    # All converted to str and stripped; dict/list become their str repr
    tags = extract_tags(profile)
    # After normalization booleans lowercased
    assert "123" in tags
    assert "true" in tags
    assert "false" in tags
    assert "plain" in tags


def test_large_tag_list_performance(tmp_path: Path):
    app = create_app(base_dir=tmp_path)
    big = [f"tag{i}" for i in range(500)] + ["tag10", "tag20"]
    payload = make_payload(big)
    profile = app._build_profile(payload, {})
    tags = extract_tags(profile)
    # Capped at 50 by server-side safeguard
    assert len(tags) == 50
    assert tags[0] == "tag0"
    assert tags[-1] == "tag49"

