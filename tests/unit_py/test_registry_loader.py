from __future__ import annotations

import json
from pathlib import Path

import pytest

from neo_agent.registry_loader import load_tool_registry


pytestmark = pytest.mark.unit


def test_load_tool_registry_baseline_returns_connectors() -> None:
    snapshot = load_tool_registry()
    assert snapshot.connectors, "expected baseline registry to expose connectors"
    assert snapshot.data_sources, "expected baseline registry to expose data sources"


def test_load_tool_registry_prefers_last_build(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out_root = tmp_path / "_generated"
    build_dir = out_root / "AGENT-XYZ" / "20250101T000000Z"
    build_dir.mkdir(parents=True)

    pack_payload = {
        "connectors": [
            {"id": "alpha", "name": "alpha", "scopes": ["read"], "secret_ref": "vault://alpha"}
        ],
        "data_sources": ["SRC-ALPHA-01"],
        "datasets": [
            {"id": "DS-001", "name": "Dataset One", "description": "Synthetic", "classification": "internal"}
        ],
    }
    (build_dir / "12_Tool+Data-Registry_v2.json").write_text(json.dumps(pack_payload), encoding="utf-8")
    (out_root / "_last_build.json").write_text(json.dumps({"outdir": str(build_dir)}), encoding="utf-8")

    monkeypatch.setenv("NEO_REPO_OUTDIR", str(out_root))

    snapshot = load_tool_registry()

    assert [connector.id for connector in snapshot.connectors] == ["alpha"]
    assert snapshot.data_sources == ["SRC-ALPHA-01"]
    assert [dataset.id for dataset in snapshot.datasets] == ["DS-001"]

    monkeypatch.delenv("NEO_REPO_OUTDIR")
