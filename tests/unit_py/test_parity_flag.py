import json
from pathlib import Path

import pytest


pytestmark = [pytest.mark.unit]


class FakeApp:
    def __init__(self, outdir: Path, parity: dict):
        self._outdir = outdir
        self._parity = parity

    def wsgi_app(self, environ, start_response):
        path = environ.get("PATH_INFO")
        if path == "/save":
            payload = json.dumps({"ok": True}).encode("utf-8")
            start_response(
                "200 OK",
                [
                    ("Content-Type", "application/json"),
                    ("Content-Length", str(len(payload))),
                ],
            )
            return [payload]
        if path == "/build":
            payload = json.dumps(
                {
                    "outdir": str(self._outdir),
                    "parity": self._parity,
                }
            ).encode("utf-8")
            start_response(
                "200 OK",
                [
                    ("Content-Type", "application/json"),
                    ("Content-Length", str(len(payload))),
                ],
            )
            return [payload]
        payload = json.dumps({"status": "notfound"}).encode("utf-8")
        start_response(
            "404 Not Found",
            [
                ("Content-Type", "application/json"),
                ("Content-Length", str(len(payload))),
            ],
        )
        return [payload]


def _setup_outdir(tmp_path: Path):
    from neo_build.contracts import CANONICAL_PACK_FILENAMES

    outdir = tmp_path / "agent-X" / "20250101T000000Z"
    outdir.mkdir(parents=True, exist_ok=True)
    for name in CANONICAL_PACK_FILENAMES:
        (outdir / name).write_text("{}\n", encoding="utf-8")
    (outdir / "INTEGRITY_REPORT.json").write_text(
        json.dumps({"errors": []}, indent=2), encoding="utf-8"
    )
    return outdir


def _monkey_smoke(monkeypatch, outdir: Path, parity_map: dict):
    import ci.smoke as smoke

    # Avoid sys.path fiddling
    monkeypatch.setattr(smoke, "_ensure_import_path", lambda: None)
    # Fake create_app to avoid real server by patching provider module
    import neo_agent.intake_app as intake_app

    monkeypatch.setattr(
        intake_app, "create_app", lambda *args, **kwargs: FakeApp(outdir, parity_map)
    )
    return smoke


def test_legacy_behavior_parity_false_flag_off(monkeypatch, tmp_path):
    outdir = _setup_outdir(tmp_path)
    parity = {"02_vs_14": False, "11_vs_02": True, "03_vs_02": True, "17_vs_02": True}
    smoke = _monkey_smoke(monkeypatch, outdir, parity)

    monkeypatch.setenv("FAIL_ON_PARITY", "false")
    monkeypatch.chdir(tmp_path)
    (tmp_path / "fixtures").mkdir(exist_ok=True)
    (tmp_path / "fixtures" / "sample_profile.json").write_text("{}\n", encoding="utf-8")

    rc = smoke.main()
    assert rc == 0


def test_parity_false_flag_on_fails_and_prints(monkeypatch, tmp_path, capsys):
    outdir = _setup_outdir(tmp_path)
    parity = {"02_vs_14": False, "11_vs_02": True, "03_vs_02": True, "17_vs_02": True}
    smoke = _monkey_smoke(monkeypatch, outdir, parity)

    monkeypatch.setenv("FAIL_ON_PARITY", "true")
    monkeypatch.chdir(tmp_path)
    (tmp_path / "fixtures").mkdir(exist_ok=True)
    (tmp_path / "fixtures" / "sample_profile.json").write_text("{}\n", encoding="utf-8")

    rc = smoke.main()
    captured = capsys.readouterr().out
    assert rc == 1
    assert "PARITY FAIL" in captured


def test_parity_true_flag_on_passes_and_prints_ok(monkeypatch, tmp_path, capsys):
    outdir = _setup_outdir(tmp_path)
    parity = {"02_vs_14": True, "11_vs_02": True, "03_vs_02": True, "17_vs_02": True}
    smoke = _monkey_smoke(monkeypatch, outdir, parity)

    monkeypatch.setenv("FAIL_ON_PARITY", "true")
    monkeypatch.chdir(tmp_path)
    (tmp_path / "fixtures").mkdir(exist_ok=True)
    (tmp_path / "fixtures" / "sample_profile.json").write_text("{}\n", encoding="utf-8")

    rc = smoke.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "SMOKE OK | files=20 | parity=ALL_TRUE | integrity_errors=0" in out
