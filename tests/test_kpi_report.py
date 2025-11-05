import json
import subprocess
import sys
from pathlib import Path


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_gen_kpi_report_creates_outputs(tmp_path, monkeypatch):
    build_root = tmp_path / "build"
    build_root.mkdir()

    write_json(
        build_root / "02_Global-Instructions_v2.json",
        {
            "go_live": {
                "gates": ["PRI>=0.95", "HAL<=0.02", "AUD>=0.90"],
            }
        },
    )

    write_json(
        build_root / "11_Workflow-Pack_v2.json",
        {
            "gates": {
                "kpi_targets": {
                    "AUD_min": 0.9,
                    "HAL_max": 0.02,
                    "PRI_min": 0.95,
                }
            }
        },
    )

    write_json(
        build_root / "14_KPI+Evaluation-Framework_v2.json",
        {
            "targets": {
                "AUD_min": 0.9,
                "HAL_max": 0.02,
                "PRI_min": 0.95,
            },
            "kpis": [
                {"id": "PRI", "target": ">=0.95"},
                {"id": "HAL", "target": "<=0.02"},
                {"id": "AUD", "target": ">=0.90"},
            ],
            "gates": {
                "activation": {
                    "PRI_min": 0.95,
                    "HAL_max": 0.02,
                    "AUD_min": 0.9,
                },
                "change": {
                    "allow_latency_increase_pct": 10,
                    "require_regression": True,
                },
            },
        },
    )

    write_json(
        build_root / "15_Observability+Telemetry_Spec_v2.json",
        {
            "events": ["kpi_report_generated"],
        },
    )

    out_dir = tmp_path / "reports_out"

    monkeypatch.setenv("GITHUB_SHA", "deadbeef123")
    monkeypatch.setenv("GITHUB_RUN_ID", "987654")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")
    monkeypatch.setenv("GITHUB_WORKFLOW", "kpi-report-smoke")
    monkeypatch.setenv("GITHUB_RUN_NUMBER", "42")
    monkeypatch.setenv("GITHUB_RUN_STARTED_AT", "2025-11-05T00:00:00Z")
    monkeypatch.setenv("CI_JOB_STATUS", "success")

    repo_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            "scripts/gen_kpi_report.py",
            "--root",
            str(build_root),
            "--out",
            str(out_dir),
            "--ci",
        ],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )

    assert result.returncode == 0, result.stderr

    json_path = out_dir / "kpi_report.json"
    md_path = out_dir / "kpi_report.md"
    assert json_path.is_file()
    assert md_path.is_file()

    report = json.loads(json_path.read_text(encoding="utf-8"))
    assert report["version"] == "1.0.0"
    assert report["pri"]["value"] == 0.95
    assert report["hal"]["value"] == 0.02
    assert report["aud"]["value"] == 0.9
    assert report["gates"]["activation"]["PRI_min"] == 0.95
    assert report["gates"]["workflow_targets"]["AUD_min"] == 0.9
    assert report["commit"] == "deadbeef123"
    assert report["ci_runs"], "expected at least one CI run entry"
    assert report["ci_runs"][0]["id"] == "987654"

    md_text = md_path.read_text(encoding="utf-8")
    assert "PRI:" in md_text
    assert "CI Runs" in md_text

    log_lines = [
        line
        for stream in (result.stdout.splitlines(), result.stderr.splitlines())
        for line in stream
        if line.strip()
    ]
    assert any("kpi_report_generated" in line for line in log_lines)
    assert any("kpi-report" in line for line in log_lines)
