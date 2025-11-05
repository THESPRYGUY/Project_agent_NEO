"""Persona traits composition helpers."""

from __future__ import annotations

import hashlib
import random
from typing import Any, Iterable, List, Mapping, Optional, Sequence

AXIS_TRAIT_POOL: Mapping[str, Mapping[str, Sequence[str]]] = {
    "EI": {
        "E": ("energy_connector", "engagement_host"),
        "I": ("analytical_anchor", "calm_mediator"),
    },
    "SN": {
        "S": ("process_anchor", "precision_advocate"),
        "N": ("innovation_scout", "foresight_planner"),
    },
    "TF": {
        "T": ("strategic_executor", "diagnostic_solver"),
        "F": ("values_champion", "people_steward"),
    },
    "JP": {
        "J": ("decisive_orchestrator", "quality_guardian"),
        "P": ("experience_crafter", "curiosity_researcher"),
    },
}

FALLBACK_TRAITS: Sequence[str] = (
    "strategic_executor",
    "values_champion",
    "innovation_scout",
    "process_anchor",
    "team_mobilizer",
)


def _normalise_trait(trait: Any, lexicon: Mapping[str, Any]) -> Optional[str]:
    if not isinstance(lexicon, Mapping):
        return None
    key = str(trait).strip()
    if not key:
        return None
    return key if key in lexicon else None


def _deterministic_shuffle(items: Sequence[str], seed: str) -> List[str]:
    if not items:
        return []
    seed_int = int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16], 16)
    rng = random.Random(seed_int)
    shuffled = list(items)
    rng.shuffle(shuffled)
    return shuffled


def compose_traits(
    *,
    lexicon: Mapping[str, Any],
    overlays: Optional[Mapping[str, Sequence[str]]] = None,
    mbti_traits: Optional[Iterable[Any]] = None,
    role_key: Optional[str] = None,
    axes: Optional[Mapping[str, Any]] = None,
    agent_id: Optional[str] = None,
    max_traits: int = 5,
) -> List[str]:
    """Merge overlay + MBTI traits; fallback deterministically when empty."""

    overlays = overlays or {}
    collected: List[str] = []
    seen: set[str] = set()

    def _append(trait: Any) -> None:
        trait_key = _normalise_trait(trait, lexicon)
        if trait_key and trait_key not in seen:
            collected.append(trait_key)
            seen.add(trait_key)

    if role_key:
        overlay_traits = overlays.get(str(role_key).upper())
        if isinstance(overlay_traits, Iterable) and not isinstance(
            overlay_traits, (str, bytes)
        ):
            for trait in overlay_traits:
                _append(trait)

    if isinstance(mbti_traits, Iterable) and not isinstance(mbti_traits, (str, bytes)):
        for trait in mbti_traits:
            _append(trait)

    limit = max_traits if isinstance(max_traits, int) else 5
    if limit <= 0:
        return []

    min_required = min(3, limit)

    if len(collected) < min_required:
        axis_candidates: List[str] = []
        if isinstance(axes, Mapping):
            for axis_name in ("EI", "SN", "TF", "JP"):
                axis_map = AXIS_TRAIT_POOL.get(str(axis_name).upper())
                if not isinstance(axis_map, Mapping):
                    continue
                letter = axes.get(axis_name, "")
                trait_pool = axis_map.get(str(letter).upper())
                if isinstance(trait_pool, Iterable) and not isinstance(
                    trait_pool, (str, bytes)
                ):
                    for trait in trait_pool:
                        trait_key = _normalise_trait(trait, lexicon)
                        if trait_key and trait_key not in axis_candidates:
                            axis_candidates.append(trait_key)

        for trait in axis_candidates:
            _append(trait)
            if len(collected) >= limit or len(collected) >= min_required:
                break

        if len(collected) < min_required:
            general_candidates: List[str] = []
            for base in FALLBACK_TRAITS:
                trait_key = _normalise_trait(base, lexicon)
                if trait_key and trait_key not in axis_candidates:
                    general_candidates.append(trait_key)

            if isinstance(lexicon, Mapping):
                lexicon_keys = [
                    key
                    for key in lexicon.keys()
                    if isinstance(key, str) and key.strip()
                ]
                for key in lexicon_keys:
                    if key not in axis_candidates and key not in general_candidates:
                        general_candidates.append(key)

            remaining = _deterministic_shuffle(
                general_candidates, agent_id or "persona-traits"
            )

            for trait in remaining:
                _append(trait)
                if len(collected) >= limit or len(collected) >= min_required:
                    break

    if len(collected) < min_required:
        base = list(collected)
        if not base:
            return []
        idx = 0
        while len(collected) < min_required and len(collected) < limit:
            trait = base[idx % len(base)]
            collected.append(trait)
            idx += 1

    return collected[:limit]
