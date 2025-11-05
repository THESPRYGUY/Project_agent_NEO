import json
import subprocess
import sys
from pathlib import Path


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_release_gate_report(tmp_path):
    build_root = tmp_path / "build"
    build_root.mkdir()
    lifecycle_payload = {
        "go_live": {
            "blockers": ["gates_fail"],
            "phases": [
                {
                    "id": "preflight",
                    "name": "Preflight",
                    "owner": "COO/PMO",
                    "checks": ["objective_scope_confirmed"],
                    "evidence": ["01_charter/*"],
                }
            ],
            "checklists": [
                {
                    "id": "prelaunch",
                    "title": "Pre-Launch Gate",
                    "owner": "COO/PMO",
                    "steps": ["Confirm blockers cleared"],
                    "triggers": ["schedule_window"],
                }
            ],
        },
        "rollBack": "ignored casing",
        "rollback": {
            "on_failure": "revert_to:staging",
            "checklists": [
                {
                    "id": "decision",
                    "title": "Decision",
                    "owner": "CAIO",
                    "triggers": ["HAL breach"],
                    "steps": ["Notify stakeholders"],
                }
            ],
        },
        "gates": {
            "activation": ["AUD>=0.9"],
            "kpi_targets": {"AUD_min": 0.9},
            "effective_autonomy": 0.0,
        },
        "approvals": {
            "matrix": [
                {"artifact": "02_Global-Instructions_v2.json", "required": ["CAIO", "CPA"]}
            ]
        },
    }
    write_json(build_root / "17_Lifecycle-Pack_v2.json", lifecycle_payload)

    out_dir = tmp_path / "reports_out"
    repo_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            "scripts/release_gate_report.py",
            "--root",
            str(build_root),
            "--out",
            str(out_dir),
        ],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )

    assert result.returncode == 0, result.stderr
    assert "release_gate.json" in result.stdout or "release_gate.md" in result.stdout

    json_path = out_dir / "release_gate.json"
    md_path = out_dir / "release_gate.md"
    assert json_path.exists()
    assert md_path.exists()

    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["go_live"]["blockers"] == ["gates_fail"]
    assert data["go_live"]["phases"][0]["id"] == "preflight"
    assert data["rollback"]["checklists"][0]["owner"] == "CAIO"
    assert data["approvals"][0]["required"] == ["CAIO", "CPA"]

    md_text = md_path.read_text(encoding="utf-8")
    assert "Release Gate Report" in md_text
    assert "Pre-Launch Gate" in md_text
    assert "Decision" in md_text
