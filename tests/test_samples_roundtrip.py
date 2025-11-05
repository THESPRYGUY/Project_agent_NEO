import json
from pathlib import Path


def test_sample_kpi_report_keys_present():
    root = Path(__file__).resolve().parents[1]
    sample_path = root / "reports" / "kpi_report.sample.json"
    assert sample_path.is_file(), "Sample KPI JSON missing"
    data = json.loads(sample_path.read_text(encoding="utf-8"))
    for key in ("pri", "hal", "aud", "gates"):
        assert key in data, f"Expected key '{key}' in sample KPI report"
    assert "version" in data and data["version"], "Sample should include version"
    assert "timestamp" in data, "Sample should include timestamp metadata"
