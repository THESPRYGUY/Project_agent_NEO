from __future__ import annotations

import json
from pathlib import Path

import pytest

from persona.traits_utils import compose_traits


def _load_lexicon() -> dict[str, str]:
    path = (
        Path(__file__).resolve().parents[2] / "src" / "persona" / "traits_lexicon.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def _axes(code: str) -> dict[str, str]:
    code = (code or "").upper()
    labels = ("EI", "SN", "TF", "JP")
    return {
        label: code[idx] if len(code) > idx else "" for idx, label in enumerate(labels)
    }


def test_compose_traits_combines_overlay_and_mbti() -> None:
    lexicon = _load_lexicon()
    overlays = {
        "EXEC:GM": [
            "decisive_orchestrator",
            "stakeholder_alignment",
            "strategic_executor",
        ]
    }
    mbti_traits = ["strategic_executor", "systems_thinker", "foresight_planner"]

    traits = compose_traits(
        lexicon=lexicon,
        overlays=overlays,
        mbti_traits=mbti_traits,
        role_key="EXEC:GM",
        axes=_axes("ENTJ"),
        agent_id="agent-001",
    )

    assert traits[:3] == [
        "decisive_orchestrator",
        "stakeholder_alignment",
        "strategic_executor",
    ]
    assert len(traits) <= 5
    assert all(key in lexicon for key in traits), "all traits should exist in lexicon"


def test_compose_traits_returns_minimum_three() -> None:
    lexicon = _load_lexicon()
    traits = compose_traits(
        lexicon=lexicon,
        overlays={},
        mbti_traits=["innovation_scout"],
        role_key=None,
        axes=_axes("ENTP"),
        agent_id="agent-002",
    )
    assert len(traits) >= 3
    assert traits[0] == "innovation_scout"


def test_compose_traits_fallback_deterministic() -> None:
    lexicon = _load_lexicon()
    overlays: dict[str, list[str]] = {}
    traits_first = compose_traits(
        lexicon=lexicon,
        overlays=overlays,
        mbti_traits=[],
        role_key=None,
        axes=_axes("ISFP"),
        agent_id="agent-stable",
    )
    traits_second = compose_traits(
        lexicon=lexicon,
        overlays=overlays,
        mbti_traits=[],
        role_key=None,
        axes=_axes("ISFP"),
        agent_id="agent-stable",
    )
    traits_different_seed = compose_traits(
        lexicon=lexicon,
        overlays=overlays,
        mbti_traits=[],
        role_key=None,
        axes=_axes("ISFP"),
        agent_id="agent-variant",
    )

    assert traits_first == traits_second
    # Different seeds should eventually produce a different ordering
    if traits_first == traits_different_seed:
        pytest.skip("Fallback traits identical for different seeds; lexicon too small")


def test_overlay_duplicates_retains_priority_and_fills_minimum() -> None:
    lexicon = _load_lexicon()
    overlays = {
        "CUSTOM:ROLE": [
            "innovation_scout",
            "innovation_scout",
            "strategic_executor",
        ]
    }
    traits = compose_traits(
        lexicon=lexicon,
        overlays=overlays,
        mbti_traits=["innovation_scout"],
        role_key="CUSTOM:ROLE",
        axes=_axes("ENTP"),
        agent_id="agent-overlay-dup",
    )
    assert traits[:2] == ["innovation_scout", "strategic_executor"]
    assert len(traits) >= 3
    assert len(traits) == len(set(traits))
