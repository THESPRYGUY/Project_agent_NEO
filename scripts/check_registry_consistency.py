#!/usr/bin/env python3
"""CI guard to ensure UI payloads stay aligned with pack-12 registry enums."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, Iterable, Set

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from neo_agent.registry_loader import load_tool_registry
from neo_agent.intake_app import IntakeApplication


def _normalise_tokens(values: Iterable[object]) -> Set[str]:
    tokens: Set[str] = set()
    for value in values or []:
        if isinstance(value, str):
            token = value.strip()
        elif isinstance(value, dict):
            ident = value.get("id") or value.get("name")
            token = str(ident or "").strip()
        else:
            token = str(value or "").strip()
        if token:
            tokens.add(token)
    return tokens


def main() -> int:
    registry = load_tool_registry()
    schema = IntakeApplication()._intake_schema_payload()
    defaults = schema.get("defaults") or {}
    sample = schema.get("sample") or {}

    pack_connector_ids = {c.id for c in registry.connectors if c.id}
    pack_data_sources = set(registry.data_sources)
    pack_dataset_ids = {dataset.id for dataset in registry.datasets if dataset.id}

    defaults_connectors = _normalise_tokens(defaults.get("connectors") or [])
    defaults_data_sources = _normalise_tokens(defaults.get("data_sources") or [])
    defaults_dataset_ids = _normalise_tokens(defaults.get("datasets") or [])

    sample_connectors = _normalise_tokens(sample.get("connectors") or [])
    sample_data_sources = _normalise_tokens(sample.get("data_sources") or [])
    sample_dataset_ids = _normalise_tokens(sample.get("datasets") or [])

    issues: list[str] = []

    def _diff(label: str, expected: Set[str], observed: Set[str]) -> None:
        missing = sorted(expected - observed)
        extra = sorted(observed - expected)
        if missing:
            issues.append(f"{label}: missing -> {missing}")
        if extra:
            issues.append(f"{label}: unknown -> {extra}")

    _diff("defaults.connectors", pack_connector_ids, defaults_connectors)
    _diff("defaults.data_sources", pack_data_sources, defaults_data_sources)
    _diff("defaults.datasets", pack_dataset_ids, defaults_dataset_ids)

    if sample_connectors:
        _diff("sample.connectors", pack_connector_ids, sample_connectors)
    if sample_data_sources:
        _diff("sample.data_sources", pack_data_sources, sample_data_sources)
    if sample_dataset_ids:
        _diff("sample.datasets", pack_dataset_ids, sample_dataset_ids)

    if issues:
        for issue in issues:
            print(issue)
        return 1

    print("registry-consistency: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
