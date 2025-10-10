from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from neo_agent.intake_app import create_app


def _base_payload() -> dict[str, list[str]]:
    return {
        "agent_name": ["Neg Test"],
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
        "notes": ["Negative tests"],
    }


def _encode_selector(obj: Any) -> str:
    return json.dumps(obj)


def test_malformed_json_rejected(tmp_path: Path) -> None:
    app = create_app(base_dir=tmp_path)
    payload = _base_payload()
    # Intentionally not valid JSON (missing closing brace)
    payload["domain_selector"] = ["{\"topLevel\": \"Strategic Functions\", \"subdomain\": \"Workflow Orchestration\""]
    profile = app._build_profile(payload, {})
    # Should ignore malformed selector entirely
    assert "domain_selector" not in profile["agent"]
    errs = profile.get("_validation", {}).get("domain_selector_errors", [])
    assert any("Failed to parse" in e or "malformed" in e.lower() for e in errs)


def test_oversized_tag_array_truncated_or_rejected(tmp_path: Path) -> None:
    app = create_app(base_dir=tmp_path)
    huge_tags = [f"tag{i}" for i in range(600)]  # exceed any reasonable soft cap
    selector = {"topLevel": "Strategic Functions", "subdomain": "Workflow Orchestration", "tags": huge_tags}
    payload = _base_payload()
    payload["domain_selector"] = [_encode_selector(selector)]
    profile = app._build_profile(payload, {})
    # Implementation currently normalizes tags but may cap length (if added later). For now assert presence and size <= input
    ds = profile["agent"].get("domain_selector")
    assert ds is not None
    tags = ds.get("tags", [])
    assert len(tags) <= len(huge_tags)
    # All tags normalized lower-case
    assert all(t == t.lower() for t in tags)


def test_non_string_tags_ignored(tmp_path: Path) -> None:
    app = create_app(base_dir=tmp_path)
    mixed_tags = ["Alpha", 123, None, {"x": 1}, "Beta"]
    selector = {"topLevel": "Strategic Functions", "subdomain": "Workflow Orchestration", "tags": mixed_tags}
    payload = _base_payload()
    payload["domain_selector"] = [_encode_selector(selector)]
    profile = app._build_profile(payload, {})
    ds = profile["agent"].get("domain_selector")
    assert ds is not None
    tags = ds.get("tags", [])
    assert "alpha" in tags and "beta" in tags
    assert all(isinstance(t, str) for t in tags)


def test_extreme_tag_values_trimmed(tmp_path: Path) -> None:
    app = create_app(base_dir=tmp_path)
    raw_tags = ["   MIXED   Case   Tag   ", "Symbols*&^%$#@!", "----multi----hyphen----", "   ", "OK"]
    selector = {"topLevel": "Strategic Functions", "subdomain": "Workflow Orchestration", "tags": raw_tags}
    payload = _base_payload()
    payload["domain_selector"] = [_encode_selector(selector)]
    profile = app._build_profile(payload, {})
    ds = profile["agent"].get("domain_selector")
    assert ds is not None
    tags = ds.get("tags", [])
    # Expect cleaned forms
    assert "mixed-case-tag" in tags
    assert "symbols" in tags  # trimmed symbols removed
    assert "multi-hyphen" in tags
    assert "ok" in tags
    # Blank tag removed
    assert all(t.strip() for t in tags)
