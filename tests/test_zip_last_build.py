import io
import json
import os
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

    from src.neo_agent.intake_app import create_app
    app = create_app(base_dir=work_root)
    # Save profile
    fixture = json.loads((Path.cwd() / "fixtures" / "sample_profile.json").read_text(encoding="utf-8"))
    st, _, _ = _wsgi_call(app, "POST", "/save", fixture)
    assert st == "200 OK"
    # Build
    st, headers, body = _wsgi_call(app, "POST", "/build", {})
    assert st == "200 OK"
    assert headers.get("cache-control", "").startswith("no-store")
    assert headers.get("x-neo-intake-version") == "v3.0"
    res = json.loads(body.decode("utf-8"))
    outdir = Path(res["outdir"]) if isinstance(res, dict) else None
    assert outdir and outdir.exists()

    # GET /last-build should return JSON
    st, headers, body = _wsgi_call(app, "GET", "/last-build", None)
    assert st == "200 OK"
    assert headers.get("cache-control", "").startswith("no-store")
    assert headers.get("x-neo-intake-version") == "v3.0"
    last = json.loads(body.decode("utf-8"))
    assert last["outdir"] == str(outdir)
    assert isinstance(last.get("parity"), dict)
    assert isinstance(last.get("integrity_errors"), list)

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
    hdrs = dict(hdrs)
    assert st == "200 OK"
    assert hdrs.get("content-type") == "application/zip"
    assert hdrs.get("cache-control", "").startswith("no-store")
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
    from src.neo_agent.intake_app import create_app
    app = create_app(base_dir=tmp_path)
    st, headers, body = _wsgi_call(app, "GET", "/last-build", None)
    assert st == "204 No Content"
    assert headers.get("cache-control", "").startswith("no-store")
    assert headers.get("x-neo-intake-version") == "v3.0"

