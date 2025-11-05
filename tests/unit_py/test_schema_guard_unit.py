from __future__ import annotations

import pytest


pytestmark = pytest.mark.unit


def _ensure_import() -> None:
    import sys
    from pathlib import Path

    root = Path.cwd()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


def test_schema_guard_detects_conflicts_per_concept():
    _ensure_import()
    from neo_build.validation.schema_guard import check_mutual_exclusion

    payload = {
        "identity": {"agent_id": "X", "display_name": "X", "owners": ["CAIO"]},
        "context": {"naics": {"code": "541110"}},
        "role": {"function_code": "fn", "role_code": "rc"},
        "governance_eval": {
            "gates": {"PRI_min": 0.95, "hallucination_max": 0.02, "audit_min": 0.9}
        },
        "capabilities_tools": {"tool_suggestions": ["email"]},
        "persona": {"traits": ["Crisp"]},
        "legacy": {
            "role": "OLD",
            "traits": ["LegacyTrait"],
            "tools": ["make"],
            "memory": {"scopes": ["s1"]},
            "kpi": {"PRI_min": 0.9},
        },
    }

    conflicts = check_mutual_exclusion(payload)
    codes = {c.get("code") for c in conflicts}
    assert "DUPLICATE_LEGACY_V3_CONFLICT" in codes
    # Expect multiple conflicts across concepts
    assert len(conflicts) >= 3
