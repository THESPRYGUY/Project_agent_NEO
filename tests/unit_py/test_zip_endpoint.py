import io
import json
import os
import sys
import zipfile
from pathlib import Path


def _wsgi_call(
    app, method: str, path: str, *, query: str = "", body: dict | None = None
):
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
    }
    status_headers: list[tuple[str, list[tuple[str, str]]]] = []

    def start_response(status, headers):
        status_headers.append((status, headers))

    it = app.wsgi_app(env, start_response)
    data = b"".join(it)
    status, headers = status_headers[0]
    return status, dict(headers), data


def _ensure_import_path():
    root = Path.cwd()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    srcp = root / "src"
    if str(srcp) not in sys.path:
        sys.path.insert(0, str(srcp))


def _app(tmp_path: Path):
    _ensure_import_path()
    from neo_agent.intake_app import create_app

    return create_app(base_dir=tmp_path)


def _build_small_repo(app, out_root: Path) -> Path:
    # Use /save + /build pipeline to produce a small repo
    fixture = json.loads(
        (Path.cwd() / "fixtures" / "sample_profile.json").read_text(encoding="utf-8")
    )
    st, _, _ = _wsgi_call(app, "POST", "/save", body=fixture)
    assert st == "200 OK"
    st, _, body = _wsgi_call(app, "POST", "/build", body={})
    assert st == "200 OK"
    outdir = Path(json.loads(body.decode("utf-8"))["outdir"])
    assert outdir.exists()
    return outdir


def test_zip_ok_small_repo_streamed(tmp_path: Path):
    os.environ["NEO_REPO_OUTDIR"] = str(tmp_path / "root")
    app = _app(tmp_path)
    outdir = _build_small_repo(app, Path(os.environ["NEO_REPO_OUTDIR"]))
    st, headers, data = _wsgi_call(app, "GET", "/build/zip", query=f"outdir={outdir}")
    assert st == "200 OK"
    hdr = {k.lower(): v for k, v in headers.items()}
    assert hdr.get("content-type") == "application/zip"
    assert hdr.get("content-disposition", "").startswith("attachment;")
    with zipfile.ZipFile(io.BytesIO(data), "r") as zf:
        names = set(zf.namelist())
    assert len(names) >= 1


def test_zip_400_missing_or_invalid_param(tmp_path: Path):
    os.environ["NEO_REPO_OUTDIR"] = str(tmp_path / "root")
    app = _app(tmp_path)
    st, headers, body = _wsgi_call(app, "GET", "/build/zip", query="")
    assert st == "400 Bad Request"
    payload = json.loads(body.decode("utf-8"))
    assert payload.get("status") == "invalid"


def test_zip_400_outside_root(tmp_path: Path):
    os.environ["NEO_REPO_OUTDIR"] = str(tmp_path / "root")
    app = _app(tmp_path)
    outside = Path.cwd()  # outside tmp root
    st, headers, body = _wsgi_call(app, "GET", "/build/zip", query=f"outdir={outside}")
    assert st == "400 Bad Request"
    payload = json.loads(body.decode("utf-8"))
    assert payload.get("status") == "invalid"


def test_zip_404_folder_not_found(tmp_path: Path):
    os.environ["NEO_REPO_OUTDIR"] = str(tmp_path / "root")
    app = _app(tmp_path)
    missing = Path(os.environ["NEO_REPO_OUTDIR"]) / "x" / "missing"
    st, headers, body = _wsgi_call(app, "GET", "/build/zip", query=f"outdir={missing}")
    assert st == "404 Not Found"
    payload = json.loads(body.decode("utf-8"))
    assert payload.get("status") == "not_found"
