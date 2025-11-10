import json
from pathlib import Path

from neo_build.ssot import assemble_ssot
from neo_build.writers import write_sme_overlay


def _ssot_fixture():
    return {
        "naics": {
            "code": "237130",
            "title": "Power and Communication Line and Related Structures Construction",
            "lineage": [
                {"level": 2, "code": "23", "title": "Construction"},
                {
                    "level": 5,
                    "code": "23713",
                    "title": "Power and Communication Line and Related Structures Construction",
                },
            ],
        },
        "industry": "",
    }


def test_ssot_sets_canonical_from_two_digit():
    payload = _ssot_fixture()
    out = assemble_ssot(payload)
    assert out["canonical_industry"] == "Construction"
    assert out["industry"] == "Construction"
    assert out["industry_source"] == "naics_lineage"


def test_manual_override_preserved():
    payload = _ssot_fixture()
    payload["industry"] = "Utility Interconnections"
    out = assemble_ssot(payload)
    assert out["canonical_industry"] == "Construction"
    assert out["industry"] == "Utility Interconnections"
    assert out["industry_source"] == "manual"


def test_overlay_writer_emits_triplet(tmp_path: Path):
    ssot = assemble_ssot(_ssot_fixture())
    out_path = tmp_path / "overlay.json"
    written = write_sme_overlay(ssot, out_path)
    data = json.loads(out_path.read_text(encoding="utf-8"))
    for payload in (written, data):
        assert payload["canonical_industry"] == "Construction"
        assert payload["industry"] == "Construction"
        assert payload["industry_source"] == "naics_lineage"
