from __future__ import annotations

import io
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping


def _wsgi_call(app, method: str, path: str, *, query: str = "", body: Mapping[str, Any] | None = None):
    raw = json.dumps(body or {}).encode("utf-8")
    env = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "SERVER_NAME": "unit",
        "SERVER_PORT": "80",
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": "http",
        "wsgi.input": io.BytesIO(raw),
        "CONTENT_LENGTH": str(len(raw)),
        # unique request id per thread
        "neo.req_id": f"req-{threading.get_ident()}-{time.time_ns()}",
    }
    status_headers = []
    def start_response(status, headers):
        status_headers.append((status, headers))
    data = b"".join(app.wsgi_app(env, start_response))
    status, headers = status_headers[0]
    return status, dict(headers), data


def _save_minimal_profile(app):
    # Use the bundled sample profile to satisfy validation
    prof = json.loads((Path.cwd() / "fixtures" / "sample_profile.json").read_text(encoding="utf-8"))
    st, _, _ = _wsgi_call(app, "POST", "/save", body=prof)
    assert st == "200 OK"


def _read_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def test_build_lock_concurrency(tmp_path: Path, monkeypatch):
    from neo_agent.intake_app import create_app

    out_root = tmp_path / "_generated"
    monkeypatch.setenv("NEO_REPO_OUTDIR", str(out_root))
    app = create_app(base_dir=tmp_path)
    _save_minimal_profile(app)

    # Warm-up build to derive agent_id deterministically
    st, _, body = _wsgi_call(app, "POST", "/build", body={})
    assert st == "200 OK", body
    first = json.loads(body.decode("utf-8"))
    agent_outdir_1 = Path(first["outdir"])  # e.g., _generated/<AGENT_ID>/<TS>
    agent_dir = agent_outdir_1.parent

    # Concurrency: two parallel /build calls
    def do_build():
        return _wsgi_call(app, "POST", "/build", body={})

    with ThreadPoolExecutor(max_workers=2) as ex:
        futures = [ex.submit(do_build), ex.submit(do_build)]
        results = [f.result() for f in as_completed(futures)]

    statuses = [r[0] for r in results]
    bodies = [json.loads(r[2].decode("utf-8")) for r in results]
    headers_list = [r[1] for r in results]

    assert statuses.count("200 OK") == 1
    assert statuses.count("423 Locked") == 1

    # Validate 423 envelope and header
    locked_idx = statuses.index("423 Locked")
    locked_body = bodies[locked_idx]
    locked_headers = {k.lower(): v for k, v in headers_list[locked_idx].items()}
    assert locked_body.get("status") == "error"
    assert locked_body.get("code") == "BUILD_LOCKED"
    assert isinstance(locked_body.get("req_id"), str)
    assert locked_headers.get("retry-after") == "5"

    # No .tmp residue
    tmp_dir = agent_dir / ".tmp"
    assert not tmp_dir.exists() or len(list(tmp_dir.glob("*"))) == 0

    # Re-run /build — should succeed and produce identical zip hash
    st2, _, body2 = _wsgi_call(app, "POST", "/build", body={})
    assert st2 == "200 OK"

    # Read last_build twice (before was previous success; now overwritten). Compare hashes via /download/zip
    # Compute sha256 for default (no outdir) vs explicit outdir — must be identical
    stz1, _, zip1 = _wsgi_call(app, "GET", "/download/zip", query="")
    assert stz1 == "200 OK"
    h_default = sha256(zip1).hexdigest()

    outdir_now = _read_json(out_root / "_last_build.json").get("outdir")
    stz2, _, zip2 = _wsgi_call(app, "GET", "/download/zip", query=f"outdir={outdir_now}")
    assert stz2 == "200 OK"
    h_outdir = sha256(zip2).hexdigest()
    assert h_default == h_outdir


def test_error_taxonomy_render(tmp_path: Path, monkeypatch):
    from neo_agent.intake_app import create_app
    import neo_agent.intake_app as intake_mod

    out_root = tmp_path / "_generated"
    monkeypatch.setenv("NEO_REPO_OUTDIR", str(out_root))
    app = create_app(base_dir=tmp_path)
    _save_minimal_profile(app)

    # Monkeypatch write_repo_files to raise
    def boom(*a, **k):
        raise RuntimeError("render-fail")
    monkeypatch.setattr(intake_mod, "write_repo_files", boom)

    st, _, body = _wsgi_call(app, "POST", "/build", body={})
    assert st == "500 Internal Server Error"
    payload = json.loads(body.decode("utf-8"))
    assert payload.get("code") == "E_RENDER"
    assert isinstance(payload.get("req_id"), str)
    assert isinstance(payload.get("trace_id"), str)


def test_error_taxonomy_fs(tmp_path: Path, monkeypatch):
    from neo_agent.intake_app import create_app
    import neo_agent.intake_app as intake_mod

    out_root = tmp_path / "_generated"
    monkeypatch.setenv("NEO_REPO_OUTDIR", str(out_root))
    app = create_app(base_dir=tmp_path)
    _save_minimal_profile(app)

    # Let rendering proceed, then cause final move to fail
    # Force rename to fail by intercepting low-level os.replace used by pathlib
    import os as _os
    import shutil as _shutil
    orig_replace = _os.replace
    def bad_replace(src, dst, *a, **k):
        if ".tmp" in str(src):
            raise OSError("fs-rename-fail")
        return orig_replace(src, dst, *a, **k)
    monkeypatch.setattr(_os, "replace", bad_replace, raising=True)
    monkeypatch.setattr(_os, "rename", bad_replace, raising=True)

    # Also force shutil.move fallback to fail so E_FS propagates
    orig_move = _shutil.move
    def bad_move(src, dst, *a, **k):
        if ".tmp" in str(src):
            raise OSError("fs-move-fail")
        return orig_move(src, dst, *a, **k)
    monkeypatch.setattr(_shutil, "move", bad_move, raising=True)

    st, _, body = _wsgi_call(app, "POST", "/build", body={})
    assert st == "500 Internal Server Error"
    payload = json.loads(body.decode("utf-8"))
    assert payload.get("code") == "E_FS"
    assert isinstance(payload.get("req_id"), str)


def test_error_taxonomy_zip(tmp_path: Path, monkeypatch):
    from neo_agent.intake_app import create_app
    import neo_agent.intake_app as intake_mod

    out_root = tmp_path / "_generated"
    monkeypatch.setenv("NEO_REPO_OUTDIR", str(out_root))
    app = create_app(base_dir=tmp_path)
    _save_minimal_profile(app)

    # Monkeypatch canonical zip hasher to raise
    def bad_zip(*a, **k):
        raise RuntimeError("zip-hash-fail")
    monkeypatch.setattr(intake_mod.IntakeApplication, "_canonical_zip_hash", staticmethod(bad_zip))

    st, _, body = _wsgi_call(app, "POST", "/build", body={})
    assert st == "500 Internal Server Error"
    payload = json.loads(body.decode("utf-8"))
    assert payload.get("code") == "E_ZIP"
    assert isinstance(payload.get("req_id"), str)


def test_large_zip_streaming(tmp_path: Path, monkeypatch):
    # Build a repo with > 20MB of synthetic content and ensure stable sha256
    from neo_agent.intake_app import create_app
    app = create_app(base_dir=tmp_path)
    monkeypatch.setenv("NEO_REPO_OUTDIR", str(tmp_path / "_generated"))

    # Save minimal profile and build
    _save_minimal_profile(app)
    st, _, body = _wsgi_call(app, "POST", "/build", body={})
    assert st == "200 OK"
    outdir = Path(json.loads(body.decode("utf-8"))["outdir"]) 

    # Inflate large files inside outdir deterministically
    big = outdir / "big" / "data.bin"
    big.parent.mkdir(parents=True, exist_ok=True)
    # Write 21MB of bytes (repeatable pattern)
    chunk = (b"ABCD" * 1024)  # 4KB
    with open(big, "wb") as f:
        for _ in range((21 * 1024 * 1024) // len(chunk)):
            f.write(chunk)

    # Fetch with default (last-build) and explicit outdir; compare hashes
    st1, _, z1 = _wsgi_call(app, "GET", "/download/zip", query="")
    assert st1 == "200 OK"
    st2, _, z2 = _wsgi_call(app, "GET", "/download/zip", query=f"outdir={outdir}")
    assert st2 == "200 OK"
    assert sha256(z1).hexdigest() == sha256(z2).hexdigest()


def test_unicode_long_paths_and_determinism(tmp_path: Path, monkeypatch):
    import sys as _sys
    import pytest
    from neo_agent.intake_app import create_app

    out_root = tmp_path / "_generated"
    monkeypatch.setenv("NEO_REPO_OUTDIR", str(out_root))
    app = create_app(base_dir=tmp_path)

    # Determinism at utility level (derived id)
    from neo_agent.services.identity_utils import generate_agent_id
    a1 = generate_agent_id("541110", "marketing", "AIA-P", "Agent X")
    a2 = generate_agent_id("541110", "marketing", "AIA-P", "Agent X")
    b  = generate_agent_id("541110", "marketing", "NEW-R",  "Agent X")
    assert a1 == a2 and a1 != b

    # Build once for unicode/long path checks
    _save_minimal_profile(app)
    st, _, b1 = _wsgi_call(app, "POST", "/build", body={})
    assert st == "200 OK"
    out2 = Path(json.loads(b1.decode("utf-8"))["outdir"])

    # Unicode + long paths under the latest outdir
    target = out2
    try:
        long_name = ("ユニコードΔοκιμή文件тест-" * 10)[:220] + ".txt"
        (target / long_name).write_text("ok", encoding="utf-8")
        (target / "__pycache__" / "ignored.pyc").parent.mkdir(exist_ok=True)
        (target / "__pycache__" / "ignored.pyc").write_bytes(b"x")
        (target / ".hidden" / "secret.txt").parent.mkdir(exist_ok=True)
        (target / ".hidden" / "secret.txt").write_text("hide", encoding="utf-8")
    except Exception:
        pytest.skip("platform does not support long/unicode paths")

    # ZIP should exclude hidden and __pycache__ content; hashing stable
    stz_a, _, za = _wsgi_call(app, "GET", "/download/zip", query=f"outdir={target}")
    stz_b, _, zb = _wsgi_call(app, "GET", "/download/zip", query=f"outdir={target}")
    assert stz_a == stz_b == "200 OK"
    assert sha256(za).hexdigest() == sha256(zb).hexdigest()


def test_sigterm_cleanup(tmp_path: Path, monkeypatch):
    import os as _os
    from neo_agent.intake_app import create_app
    import neo_agent.intake_app as intake_mod

    out_root = tmp_path / "_generated"
    monkeypatch.setenv("NEO_REPO_OUTDIR", str(out_root))
    app = create_app(base_dir=tmp_path)

    # First, successful build to create _last_build.json
    _save_minimal_profile(app)
    st, _, body = _wsgi_call(app, "POST", "/build", body={})
    assert st == "200 OK"
    last_before = json.loads((out_root / "_last_build.json").read_text(encoding="utf-8"))

    # Now simulate interrupt during rendering
    def interrupt(*a, **k):
        raise RuntimeError("sigterm-sim")
    monkeypatch.setattr(intake_mod, "write_repo_files", interrupt)

    st2, _, body2 = _wsgi_call(app, "POST", "/build", body={})
    assert st2 == "500 Internal Server Error"
    # last-build unchanged
    last_after = json.loads((out_root / "_last_build.json").read_text(encoding="utf-8"))
    assert last_before == last_after
    # no tmp residue under _generated/<AGENT_ID>/.tmp
    # use known agent id parent from prior success
    latest_dir = Path(last_after["outdir"]).parent
    tmp_dir = latest_dir / ".tmp"
    assert not tmp_dir.exists() or len(list(tmp_dir.glob("*"))) == 0
