import io
import json
import os
from pathlib import Path
import pytest


pytestmark = pytest.mark.unit


def _wsgi_call(app, method: str, path: str, headers: dict[str, str] | None = None):
    body = b""
    env = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "SERVER_NAME": "unit",
        "SERVER_PORT": "80",
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": "http",
        "wsgi.input": io.BytesIO(body),
        "CONTENT_LENGTH": "0",
    }
    headers = headers or {}
    for k, v in headers.items():
        env[k] = v
    status_headers: list[tuple[str, list[tuple[str, str]]]] = []

    def start_response(status, hdrs):
        status_headers.append((status, hdrs))

    # Use the WSGI callable so middleware is applied
    data = b"".join(app(env, start_response))
    status, hdrs = status_headers[0]
    return status, dict(hdrs), data


def _ensure_import():
    root = Path.cwd()
    src = root / "src"
    for p in (str(root), str(src)):
        if p not in os.sys.path:
            os.sys.path.insert(0, p)


def test_auth_stub_off_by_default_all_routes_ok(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _ensure_import()
    # Ensure AUTH_REQUIRED is not set
    monkeypatch.delenv("AUTH_REQUIRED", raising=False)
    monkeypatch.delenv("AUTH_TOKENS", raising=False)
    from neo_agent.intake_app import create_app
    app = create_app(base_dir=tmp_path)
    st, _, _ = _wsgi_call(app, "GET", "/last-build")
    # Default behavior (no auth) must not be 401
    assert not st.startswith("401")


def test_auth_stub_health_exempt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _ensure_import()
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setenv("AUTH_TOKENS", "tokenA, tokenB")
    from neo_agent.intake_app import create_app
    app = create_app(base_dir=tmp_path)
    st, hdrs, raw = _wsgi_call(app, "GET", "/health")
    assert st == "200 OK"
    payload = json.loads(raw.decode("utf-8"))
    assert payload.get("status") == "ok"


def test_auth_stub_unauthorized_without_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _ensure_import()
    monkeypatch.setenv("AUTH_REQUIRED", "1")
    monkeypatch.setenv("AUTH_TOKENS", "tokenA,tokenB")
    from neo_agent.intake_app import create_app
    app = create_app(base_dir=tmp_path)
    st, hdrs, raw = _wsgi_call(app, "GET", "/last-build")
    assert st.startswith("401")
    body = json.loads(raw.decode("utf-8"))
    assert body.get("status") == "error"
    assert body.get("code") == "UNAUTHORIZED"
    # WWW-Authenticate present
    assert any(k.lower() == "www-authenticate" for k in hdrs.keys())


def test_auth_stub_unauthorized_with_invalid_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _ensure_import()
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setenv("AUTH_TOKENS", "tokenA, tokenB")
    from neo_agent.intake_app import create_app
    app = create_app(base_dir=tmp_path)
    st, hdrs, raw = _wsgi_call(
        app,
        "GET",
        "/last-build",
        headers={"HTTP_AUTHORIZATION": "Bearer wrong"},
    )
    assert st.startswith("401")
    body = json.loads(raw.decode("utf-8"))
    assert body.get("code") == "UNAUTHORIZED"
