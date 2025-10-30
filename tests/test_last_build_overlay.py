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


def test_last_build_overlay_summary_present_when_applied(tmp_path: Path):
    # Arrange isolated out root and env
    work_root = tmp_path / "overlay"
    work_root.mkdir(parents=True, exist_ok=True)
    os.environ["NEO_REPO_OUTDIR"] = str(work_root.resolve())
    os.environ["NEO_APPLY_OVERLAYS"] = "true"

    # Ensure import path includes project root and src/
    root = Path.cwd()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    srcp = root / "src"
    if str(srcp) not in sys.path:
        sys.path.insert(0, str(srcp))
    from neo_agent.intake_app import create_app
    app = create_app(base_dir=work_root)

    # Save profile and build
    fixture = json.loads((Path.cwd() / "fixtures" / "sample_profile.json").read_text(encoding="utf-8"))
    st, _, _ = _wsgi_call(app, "POST", "/save", fixture)
    assert st == "200 OK"
    st, headers, body = _wsgi_call(app, "POST", "/build", {})
    assert st == "200 OK"
    hdr = {k.lower(): v for k, v in headers.items()}
    assert hdr.get("cache-control", "").startswith("no-store")
    assert hdr.get("x-neo-intake-version") == "v3.0"

    # Read last-build and verify minimal SoT pointer
    st, headers, body = _wsgi_call(app, "GET", "/last-build", None)
    assert st == "200 OK"
    hdr = {k.lower(): v for k, v in headers.items()}
    assert hdr.get("cache-control", "").startswith("no-store")
    assert hdr.get("x-neo-intake-version") == "v3.0"
    last = json.loads(body.decode("utf-8"))
    assert set(["agent_id", "outdir", "files", "ts"]).issubset(last.keys())
    assert Path(last["outdir"]).exists()
