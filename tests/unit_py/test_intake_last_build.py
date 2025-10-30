import io
import json
import os
import sys
from pathlib import Path


def _wsgi_call(app, method: str, path: str, body: dict | None = None):
    raw = json.dumps(body or {}).encode("utf-8")
    env = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "SERVER_NAME": "unit",
        "SERVER_PORT": "80",
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": "http",
        "wsgi.input": io.BytesIO(raw),
        "CONTENT_LENGTH": str(len(raw)),
    }
    status_headers: list[tuple[str, list[tuple[str, str]]]] = []
    def start_response(status, headers):
        status_headers.append((status, headers))
    resp_iter = app.wsgi_app(env, start_response)
    data = b"".join(resp_iter)
    status, headers = status_headers[0]
    return status, dict(headers), data


def _ensure_import_path():
    root = Path.cwd()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    srcp = root / "src"
    if str(srcp) not in sys.path:
        sys.path.insert(0, str(srcp))


def test_last_build_204_when_missing(tmp_path: Path):
    _ensure_import_path()
    os.environ["NEO_REPO_OUTDIR"] = str((tmp_path / "root").resolve())
    from neo_agent.intake_app import create_app
    app = create_app(base_dir=tmp_path)
    st, headers, body = _wsgi_call(app, "GET", "/last-build", None)
    assert st == "204 No Content"
    hdr = {k.lower(): v for k, v in headers.items()}
    assert hdr.get("cache-control", "").startswith("no-store")
    assert hdr.get("x-neo-intake-version") == "v3.0"
    assert body == b""


def test_last_build_headers_no_store_and_version(tmp_path: Path):
    _ensure_import_path()
    # Seed a minimal last-build file
    out_root = tmp_path / "out"
    out_root.mkdir(parents=True, exist_ok=True)
    last_path = out_root / "_last_build.json"
    last_path.write_text(json.dumps({"outdir": str(out_root / "AGT"), "parity": {}, "integrity_errors": []}), encoding="utf-8")
    os.environ["NEO_REPO_OUTDIR"] = str(out_root)
    from neo_agent.intake_app import create_app
    app = create_app(base_dir=tmp_path)
    st, headers, body = _wsgi_call(app, "GET", "/last-build", None)
    assert st == "200 OK"
    hdr = {k.lower(): v for k, v in headers.items()}
    assert hdr.get("cache-control", "").startswith("no-store")
    assert hdr.get("x-neo-intake-version") == "v3.0"
    data = json.loads(body.decode("utf-8"))
    assert data["outdir"].endswith("AGT")


def test_last_build_with_minimal_pointer_schema(tmp_path: Path):
    _ensure_import_path()
    os.environ["NEO_REPO_OUTDIR"] = str((tmp_path / "root").resolve())
    os.environ["NEO_APPLY_OVERLAYS"] = "true"
    from neo_agent.intake_app import create_app
    app = create_app(base_dir=tmp_path)
    # Save + build to generate last-build pointer
    fixture = json.loads((Path.cwd() / "fixtures" / "sample_profile.json").read_text(encoding="utf-8"))
    st, _, _ = _wsgi_call(app, "POST", "/save", fixture)
    assert st == "200 OK"
    st, _, _ = _wsgi_call(app, "POST", "/build", {})
    assert st == "200 OK"
    st, headers, body = _wsgi_call(app, "GET", "/last-build", None)
    assert st == "200 OK"
    hdr = {k.lower(): v for k, v in headers.items()}
    assert hdr.get("cache-control", "").startswith("no-store")
    assert hdr.get("x-neo-intake-version") == "v3.0"
    payload = json.loads(body.decode("utf-8"))
    assert set(["agent_id", "outdir", "files", "ts"]).issubset(payload.keys())
    assert (Path(payload["outdir"]).exists())
