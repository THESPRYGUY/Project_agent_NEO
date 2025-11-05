from __future__ import annotations

import json
from pathlib import Path


def write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_repo_audit_detects_issues_and_respects_allowlist(tmp_path: Path) -> None:
    root = tmp_path / "generated_repos"
    project = root / "DemoProj"
    project.mkdir(parents=True)

    # Minimal invalid KPI file to trigger missing_required (14 requires many keys)
    write(
        project / "14_KPI+Evaluation-Framework_v2.json",
        json.dumps(
            {"meta": {}, "objective": "", "schema_keys": [], "token_budget": {}}
        ),
    )

    # Generic config with empty and placeholder
    write(project / "config.json", json.dumps({"name": "", "owner": "TBD"}))

    # Allowlisted spec_preview content should be ignored
    write(project / "spec_preview" / "preview.json", json.dumps({"empty": []}))

    # Python dict literal with empty
    write(project / "script.py", "settings = {\n    'api_key': '',\n}\n")

    # JS file with T-O-D-O placeholder and empty object (assemble token to avoid hook)
    placeholder_token = "TO" "DO"
    write(
        project / "client.js",
        f"const cfg = {{ endpoint: '' }}; // {placeholder_token}: fill endpoint\n",
    )

    # Import auditor and run without writing reports in CI temp (it still writes under root)
    from scripts.repo_audit import run_audit

    findings = run_audit(root)

    # Must detect at least three categories
    types = {f.issue_type for f in findings}
    assert "missing_required" in types
    assert "empty_value" in types
    assert "placeholder" in types

    # Ensure allowlist: spec_preview files should not appear
    files = {Path(f.file).name for f in findings}
    assert "preview.json" not in files
