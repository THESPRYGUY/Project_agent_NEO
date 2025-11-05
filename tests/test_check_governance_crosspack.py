import json
from pathlib import Path

from scripts.check_governance_crosspack import (
    PACK_FILENAMES,
    check_repo,
    main as run_main,
)


def _write_pack(tmpdir: Path, name: str, payload: dict) -> None:
    with (tmpdir / name).open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def _baseline_payloads() -> tuple[dict, dict, dict]:
    classification = "confidential"
    pii_flags = ["PII"]

    pack02 = {
        "constraints": {
            "governance_file": PACK_FILENAMES["04"],
            "safety_privacy_file": PACK_FILENAMES["05"],
        },
        "refusals": {"playbooks_source": PACK_FILENAMES["05"]},
    }
    pack04 = {
        "meta": {"name": PACK_FILENAMES["04"]},
        "classification_default": classification,
        "pii_flags": pii_flags,
        "policy": {"classification_default": classification, "no_impersonation": True},
        "privacy_alignment": {
            "guardrails_file": PACK_FILENAMES["05"],
            "pii_flags": pii_flags,
        },
    }
    pack05 = {
        "meta": {"name": PACK_FILENAMES["05"]},
        "data_classification": {
            "default": classification,
            "labels": [classification, "internal"],
        },
        "no_impersonation": True,
        "pii_flags": pii_flags,
        "privacy_policies": {"pii_flags": pii_flags},
        "operational_hooks": {"governance_file": PACK_FILENAMES["04"]},
    }
    return pack02, pack04, pack05


def test_crosspack_ok(tmp_path):
    pack02, pack04, pack05 = _baseline_payloads()
    for code, payload in zip(("02", "04", "05"), (pack02, pack04, pack05)):
        _write_pack(tmp_path, PACK_FILENAMES[code], payload)

    issues = check_repo(tmp_path)
    assert issues == []


def test_classification_mismatch_detected(tmp_path):
    pack02, pack04, pack05 = _baseline_payloads()
    pack05["data_classification"]["default"] = "internal"

    for code, payload in zip(("02", "04", "05"), (pack02, pack04, pack05)):
        _write_pack(tmp_path, PACK_FILENAMES[code], payload)

    issues = check_repo(tmp_path)
    assert any(issue.code == "classification_mismatch_05" for issue in issues)


def test_none_flag_combo_flagged(tmp_path):
    pack02, pack04, pack05 = _baseline_payloads()
    pack05["pii_flags"] = ["none", "PII"]

    for code, payload in zip(("02", "04", "05"), (pack02, pack04, pack05)):
        _write_pack(tmp_path, PACK_FILENAMES[code], payload)

    issues = check_repo(tmp_path)
    assert any(issue.code == "pii_flags_none_combo" for issue in issues)


def test_checker_scopes_to_root(tmp_path, monkeypatch):
    build_root = tmp_path / "current_build"
    build_root.mkdir()
    pack02, pack04, pack05 = _baseline_payloads()
    for code, payload in zip(("02", "04", "05"), (pack02, pack04, pack05)):
        _write_pack(build_root, PACK_FILENAMES[code], payload)

    sibling = tmp_path / "ignored_build"
    sibling.mkdir()
    (sibling / PACK_FILENAMES["05"]).write_text("{}", encoding="utf-8")

    monkeypatch.setenv("BUILD_ROOT", str(build_root))
    exit_code = run_main([])
    assert exit_code == 0


def test_checker_utf8_non_ascii(tmp_path, monkeypatch):
    build_root = tmp_path / "utf8_build"
    build_root.mkdir()
    pack02, pack04, pack05 = _baseline_payloads()
    pack02["notes"] = "π, ö, ñ"
    for code, payload in zip(("02", "04", "05"), (pack02, pack04, pack05)):
        _write_pack(build_root, PACK_FILENAMES[code], payload)

    monkeypatch.setenv("BUILD_ROOT", str(build_root))
    exit_code = run_main([])
    assert exit_code == 0
