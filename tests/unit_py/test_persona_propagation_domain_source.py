import json
from pathlib import Path


def _load(path: str) -> dict:
    target = Path(path)
    if not target.exists():
        raise AssertionError(f"{path} missing (run build step before CI)")
    return json.loads(target.read_text(encoding="utf-8"))


def test_state_has_domain_source() -> None:
    data = _load("reports/persona_state.json")
    assert data.get("agent", {}).get("domain_source") in {"override", "derived", "none"}


def test_profile_has_domain_source() -> None:
    data = _load("reports/agent_profile.json")
    assert data.get("persona", {}).get("domainSource") in {
        "override",
        "derived",
        "none",
    }
