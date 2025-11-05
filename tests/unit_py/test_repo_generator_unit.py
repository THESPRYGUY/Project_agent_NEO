import json
from pathlib import Path
import sys
import pytest


pytestmark = pytest.mark.unit


def _ensure_import():
    root = Path.cwd()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


def test_repo_generate_minimal_ok(tmp_path: Path, monkeypatch):
    _ensure_import()
    from neo_agent import repo_generator as rg

    profile = {
        "agent": {"name": "Test Agent", "version": "1.0.0"},
        "business_function": "governance",
        "role": {"code": "AIA-P", "title": "Planner", "seniority": "senior"},
        "classification": {
            "naics": {
                "code": "541110",
                "title": "Offices of Lawyers",
                "level": 5,
                "lineage": ["54", "541", "5411", "54111"],
            }
        },
        "routing_hints": {"language": "en"},
    }
    out = rg.generate_agent_repo(profile, tmp_path)
    assert out["slug"]
    p = Path(out["path"]) if isinstance(out["path"], (str, Path)) else None
    assert p and p.exists()
    # files present
    assert (p / "README.md").exists()
    assert (p / "neo_agent_config.json").exists()
    cfg = json.loads((p / "neo_agent_config.json").read_text(encoding="utf-8"))
    assert cfg.get("agent", {}).get("name") == "Test Agent"


def test_repo_generate_invalid_outdir_resolution(tmp_path: Path, monkeypatch):
    _ensure_import()
    from neo_agent import repo_generator as rg

    profile = {"agent": {"name": "X", "version": "1.0.0"}}

    # Force _next_available_dir to return a path outside base to trigger guard
    def _fake_next(base: Path, slug: str) -> Path:  # type: ignore
        return Path.cwd() / "outside"

    monkeypatch.setattr(rg, "_next_available_dir", _fake_next)
    with pytest.raises(rg.AgentRepoGenerationError):
        rg.generate_agent_repo(profile, tmp_path)
