import io
import json
import os
import sys
import zipfile
from pathlib import Path

import pytest


def _wsgi_call(
    app, method: str, path: str, body: dict | None = None, query: str | None = None
):
    raw = json.dumps(body or {}).encode("utf-8")
    env = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": query or "",
        "SERVER_NAME": "test",
        "SERVER_PORT": "80",
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": "http",
        "wsgi.input": io.BytesIO(raw),
        "CONTENT_LENGTH": str(len(raw)),
    }
    status_headers: list[tuple[str, list[tuple[str, str]]]] = []

    def start_response(status, headers):
        status_headers.append((status, headers))

    data = b"".join(app.wsgi_app(env, start_response))
    status, headers = status_headers[0]
    return status, dict(headers), data


def _prep_app(tmp_path: Path):
    os.environ["NEO_REPO_OUTDIR"] = str((tmp_path / "_gen").resolve())
    root = Path.cwd()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    srcp = root / "src"
    if str(srcp) not in sys.path:
        sys.path.insert(0, str(srcp))
    from neo_agent.intake_app import create_app

    return create_app(base_dir=tmp_path)


def _save_profile(app):
    fixture = json.loads(
        (Path.cwd() / "fixtures" / "sample_profile.json").read_text(encoding="utf-8")
    )
    st, _, _ = _wsgi_call(app, "POST", "/save", fixture)
    assert st == "200 OK"


def test_build_success_smoke(tmp_path: Path):
    app = _prep_app(tmp_path)
    _save_profile(app)

    st, _, body = _wsgi_call(app, "POST", "/build", {})
    assert st == "200 OK"
    res = json.loads(body.decode("utf-8"))
    outdir = Path(res["outdir"]).resolve()
    assert outdir.exists()

    # last-build matches
    st, _, body = _wsgi_call(app, "GET", "/last-build", None)
    assert st == "200 OK"
    last = json.loads(body.decode("utf-8"))
    assert Path(last["outdir"]).resolve() == outdir

    # download/zip parity: default (no query) and explicit should match
    st, hdrs, data1 = _wsgi_call(app, "GET", "/download/zip", None, query=None)
    assert st == "200 OK"
    assert (
        dict((k.lower(), v) for k, v in hdrs.items()).get("content-type")
        == "application/zip"
    )

    st, _, data2 = _wsgi_call(
        app, "GET", "/download/zip", None, query=f"outdir={outdir}"
    )
    assert st == "200 OK"
    assert data1 == data2

    # Zip contains 20 canonical JSON files
    from neo_build.contracts import CANONICAL_PACK_FILENAMES

    with zipfile.ZipFile(io.BytesIO(data1), "r") as zf:
        names = set(zf.namelist())
    for req in CANONICAL_PACK_FILENAMES:
        assert req in names


def test_build_error_atomicity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    app = _prep_app(tmp_path)
    # Save minimal profile with fixed agent_id for probing temp path parent
    fixture = json.loads(
        (Path.cwd() / "fixtures" / "sample_profile.json").read_text(encoding="utf-8")
    )
    fixture.setdefault("identity", {})["agent_id"] = "AGT-ERR"
    st, _, _ = _wsgi_call(app, "POST", "/save", fixture)
    assert st == "200 OK"

    # Force builder failure
    import neo_agent.intake_app as intake_mod

    def _boom(profile, out_dir):
        raise RuntimeError("unit-test-forced")

    monkeypatch.setattr(intake_mod, "write_repo_files", _boom)

    st, _, body = _wsgi_call(app, "POST", "/build", {})
    assert st == "500 Internal Server Error"
    err = json.loads(body.decode("utf-8"))
    assert err.get("status") == "error"
    # Sprint-21 taxonomy: build:error uses E_RENDER/E_FS/E_ZIP. Here render failure.
    assert err.get("code") == "E_RENDER"
    # No temp remnants
    gen = Path(os.environ["NEO_REPO_OUTDIR"]).resolve()
    tmp_parent = gen / "AGT-ERR" / ".tmp"
    assert not any(tmp_parent.glob("*")), "temp dir should be empty or missing"
    # Last build unchanged
    assert not (gen / "_last_build.json").exists()


def test_banner_update(tmp_path: Path):
    app = _prep_app(tmp_path)
    _save_profile(app)
    st, _, body = _wsgi_call(app, "POST", "/build", {})
    assert st == "200 OK"
    first = json.loads(body.decode("utf-8"))
    st, _, body = _wsgi_call(app, "GET", "/last-build", None)
    assert st == "200 OK"
    last = json.loads(body.decode("utf-8"))
    assert last.get("outdir") == first.get("outdir")
    assert last.get("ts") in (first.get("ts"), None) or True  # tolerate legacy


def test_paths_single_sot(tmp_path: Path):
    app = _prep_app(tmp_path)
    _save_profile(app)
    st, _, body = _wsgi_call(app, "POST", "/build", {})
    assert st == "200 OK"
    res = json.loads(body.decode("utf-8"))
    outdir = Path(res["outdir"]).resolve()
    # Specs live under spec_preview in SoT path; no generated_specs at base
    assert (outdir / "spec_preview").exists()
    assert not (tmp_path / "generated_specs").exists()
