import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


def _build_full(repo_root: Path, tmp: Path) -> Path:
    intake = tmp / "intake.json"
    outdir = tmp / "out"
    profile = {
        "agent": {"name": "Atlas Analyst", "version": "1.0.0"},
        "identity": {"agent_id": "atlas"},
        "capabilities_tools": {
            "tool_suggestions": ["email", "calendar"],
            "tool_connectors": [
                {
                    "name": "email",
                    "enabled": True,
                    "scopes": ["send:internal"],
                    "secret_ref": "vault://email/agent",
                }
            ],
            "human_gate": {"actions": ["legal_advice"]},
        },
        "memory": {"data_sources": ["default_index"]},
    }
    intake.write_text(json.dumps(profile, indent=2), encoding="utf-8")
    env = dict(os.environ)
    env["NEO_CONTRACT_MODE"] = "full"
    cp = subprocess.run(
        [
            sys.executable,
            str(repo_root / "build_repo.py"),
            "--intake",
            str(intake),
            "--out",
            str(outdir),
            "--extend",
            "--force-utf8",
            "--emit-parity",
        ],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        env=env,
    )
    assert cp.returncode == 0, cp.stderr + cp.stdout
    return outdir / "atlas-1-0-0"


def test_tools_secrets_and_rag_names_resolve(tmp_path: Path) -> None:
    repo_root = Path.cwd()
    repo_path = _build_full(repo_root, tmp_path)
    p10 = json.loads((repo_path / "10_Prompt-Pack_v2.json").read_text(encoding="utf-8"))
    p11 = json.loads(
        (repo_path / "11_Workflow-Pack_v2.json").read_text(encoding="utf-8")
    )
    p12 = json.loads(
        (repo_path / "12_Tool+Data-Registry_v2.json").read_text(encoding="utf-8")
    )
    p13 = json.loads(
        (repo_path / "13_Knowledge-Graph+RAG_Config_v2.json").read_text(
            encoding="utf-8"
        )
    )

    # 12 secrets contain names only (no values)
    for s in p12.get("secrets", []):
        assert "value" not in s and "token" not in s and "password" not in s

    # policies asserted
    assert (
        isinstance(p12.get("policies"), dict)
        and p12["policies"].get("least_privilege") is True
    )

    # 13 has retriever and embedding
    assert any(r.get("name") for r in p13.get("retrievers", []))
    assert p13.get("embeddings", {}).get("model")

    # Names resolve: modules reference retriever present in 13, and indices exist
    retrievers = {r.get("name"): r.get("index") for r in p13.get("retrievers", [])}
    indices = {i.get("name") for i in p13.get("indices", [])}
    for m in p10.get("modules", []):
        rv = m.get("retriever")
        if rv:
            assert rv in retrievers
            idx = retrievers[rv]
            assert idx in indices

    # 11 node tool names exist in 12 tools
    tool_names = {t.get("name") for t in p12.get("tools", [])}
    for g in p11.get("graphs", []):
        for n in g.get("nodes", []):
            t = n.get("tool")
            if t:
                assert t in tool_names
