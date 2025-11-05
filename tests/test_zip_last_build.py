import io
import json
import os
import re
import sys
import zipfile
from pathlib import Path


def _wsgi_call(app, method: str, path: str, body: dict | None = None):
    raw = json.dumps(body or {}).encode("utf-8")
    env = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "SERVER_NAME": "test",
        "SERVER_PORT": "80",
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": "http",
        "wsgi.input": io.BytesIO(raw),
        "CONTENT_LENGTH": str(len(raw)),
    }
    status_headers = []

    def start_response(status, headers):
        status_headers.append((status, headers))

    resp_iter = app.wsgi_app(env, start_response)
    data = b"".join(resp_iter)
    status, headers = status_headers[0]
    return status, dict(headers), data


def test_last_build_and_zip_endpoints(tmp_path: Path):
    # Arrange isolated out root
    work_root = tmp_path / "sprint7"
    work_root.mkdir(parents=True, exist_ok=True)
    os.environ["NEO_REPO_OUTDIR"] = str(work_root.resolve())

    # Ensure import path includes project root and src/
    root = Path.cwd()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    srcp = root / "src"
    if str(srcp) not in sys.path:
        sys.path.insert(0, str(srcp))
    from neo_agent.intake_app import create_app

    app = create_app(base_dir=work_root)
    # Save profile
    fixture = json.loads(
        (Path.cwd() / "fixtures" / "sample_profile.json").read_text(encoding="utf-8")
    )
    st, _, _ = _wsgi_call(app, "POST", "/save", fixture)
    assert st == "200 OK"
    # Build
    st, headers, body = _wsgi_call(app, "POST", "/build", {})
    assert st == "200 OK"
    headers = {k.lower(): v for k, v in headers.items()}
    assert headers.get("cache-control", "").startswith("no-store")
    assert headers.get("x-neo-intake-version") == "v3.0"
    res = json.loads(body.decode("utf-8"))
    outdir = Path(res["outdir"]) if isinstance(res, dict) else None
    assert outdir and outdir.exists()

    # GET /last-build should return JSON
    st, headers, body = _wsgi_call(app, "GET", "/last-build", None)
    assert st == "200 OK"
    headers = {k.lower(): v for k, v in headers.items()}
    assert headers.get("cache-control", "").startswith("no-store")
    assert headers.get("x-neo-intake-version") == "v3.0"
    last = json.loads(body.decode("utf-8"))
    assert last["outdir"] == str(outdir)

    # GET /build/zip valid
    # Build query-string env
    q = f"outdir={str(outdir)}"
    raw = b""
    env = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": "/build/zip",
        "QUERY_STRING": q,
        "SERVER_NAME": "test",
        "SERVER_PORT": "80",
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": "http",
        "wsgi.input": io.BytesIO(raw),
        "CONTENT_LENGTH": "0",
    }
    st_headers = []

    def start_response(status, headers):
        st_headers.append((status, headers))

    data = b"".join(app.wsgi_app(env, start_response))
    st, hdrs = st_headers[0]
    hdrs = {k.lower(): v for k, v in dict(hdrs).items()}
    assert st == "200 OK"
    assert hdrs.get("content-type") == "application/zip"
    assert hdrs.get("cache-control", "").startswith("no-store")
    # Content-Disposition filename contract
    cd = hdrs.get("content-disposition", "")
    assert re.match(r'^attachment; filename="[A-Za-z0-9._-]+\.zip"$', cd) is not None
    # Ensure excluded files are not present
    # create some excluded files then download again
    (outdir / "_last_build.json").write_text("{}", encoding="utf-8")
    (outdir / ".DS_Store").write_text("x", encoding="utf-8")
    (outdir / ".hidden").write_text("x", encoding="utf-8")
    (outdir / "__pycache__").mkdir(exist_ok=True)
    (outdir / "__pycache__" / "a.pyc").write_bytes(b"\x00")
    (outdir / ".pytest_cache").mkdir(exist_ok=True)
    (outdir / ".pytest_cache" / "b").write_bytes(b"\x00")
    # re-request
    st_headers.clear()
    data = b"".join(app.wsgi_app(env, start_response))
    st, hdrs = st_headers[0]
    assert st == "200 OK"
    with zipfile.ZipFile(io.BytesIO(data), "r") as zf:
        names = set(zf.namelist())
    assert "_last_build.json" not in names
    assert ".DS_Store" not in names
    assert ".hidden" not in names
    assert not any(n.startswith("__pycache__/") for n in names)
    assert not any(n.startswith(".pytest_cache/") for n in names)
    assert len(data) > 0

    # Invalid: outside root
    env_bad = dict(env)
    env_bad["QUERY_STRING"] = f"outdir={Path.cwd()}"
    st_headers.clear()
    data = b"".join(app.wsgi_app(env_bad, start_response))
    st, _ = st_headers[0]
    assert st == "400 Bad Request"

    # Missing: 404
    env_missing = dict(env)
    env_missing["QUERY_STRING"] = f"outdir={work_root / 'nope' / 'missing'}"
    st_headers.clear()
    data = b"".join(app.wsgi_app(env_missing, start_response))
    st, _ = st_headers[0]
    assert st == "404 Not Found"


def test_last_build_204_when_missing(tmp_path: Path):
    os.environ["NEO_REPO_OUTDIR"] = str((tmp_path / "root").resolve())
    root = Path.cwd()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    srcp = root / "src"
    if str(srcp) not in sys.path:
        sys.path.insert(0, str(srcp))
    from neo_agent.intake_app import create_app

    app = create_app(base_dir=tmp_path)
    st, headers, body = _wsgi_call(app, "GET", "/last-build", None)
    assert st == "204 No Content"
    headers = {k.lower(): v for k, v in headers.items()}
    assert headers.get("cache-control", "").startswith("no-store")
    assert headers.get("x-neo-intake-version") == "v3.0"


def test_zip_streams_large_tree(tmp_path: Path):
    # Arrange
    work_root = tmp_path / "stream"
    work_root.mkdir(parents=True, exist_ok=True)
    os.environ["NEO_REPO_OUTDIR"] = str(work_root.resolve())
    root = Path.cwd()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    srcp = root / "src"
    if str(srcp) not in sys.path:
        sys.path.insert(0, str(srcp))
    from neo_agent.intake_app import create_app

    app = create_app(base_dir=work_root)
    # prepare an outdir with > 10MB dummy file
    outdir = work_root / "AGT-xx" / "20250101T000000Z"
    outdir.mkdir(parents=True, exist_ok=True)
    big = outdir / "big.bin"
    big.write_bytes(b"0" * (11 * 1024 * 1024))
    # request zip
    q = f"outdir={str(outdir)}"
    env = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": "/build/zip",
        "QUERY_STRING": q,
        "SERVER_NAME": "test",
        "SERVER_PORT": "80",
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": "http",
        "wsgi.input": io.BytesIO(b""),
        "CONTENT_LENGTH": "0",
    }
    st_headers = []

    def start_response(status, headers):
        st_headers.append((status, headers))

    it = app.wsgi_app(env, start_response)
    st, hdrs = st_headers[0]
    assert st == "200 OK"
    # iterate in chunks to ensure streaming returns > 1 chunk
    chunk_count = 0
    total = 0
    for chunk in it:
        total += len(chunk)
        chunk_count += 1
    assert chunk_count > 1
    assert total > 0
