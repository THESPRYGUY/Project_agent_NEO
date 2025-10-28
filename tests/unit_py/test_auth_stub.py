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
    assert body == {
        "status": "error",
        "code": "UNAUTHORIZED",
        "message": "Missing or invalid bearer token.",
        "details": {},
        "req_id": hdrs.get("X-Request-ID") or hdrs.get("x-request-id"),
    }
    # WWW-Authenticate header exact value
    wa = next((v for k, v in hdrs.items() if k.lower() == "www-authenticate"), "")
    assert wa == 'Bearer realm="neo", error="invalid_token"'


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
    assert body == {
        "status": "error",
        "code": "UNAUTHORIZED",
        "message": "Missing or invalid bearer token.",
        "details": {},
        "req_id": hdrs.get("X-Request-ID") or hdrs.get("x-request-id"),
    }
    wa = next((v for k, v in hdrs.items() if k.lower() == "www-authenticate"), "")
    assert wa == 'Bearer realm="neo", error="invalid_token"'


def test_auth_stub_happy_path_valid_token_returns_200(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _ensure_import()
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setenv("AUTH_TOKENS", "tok1,tok2")
    from neo_agent.intake_app import create_app
    app = create_app(base_dir=tmp_path)
    st, hdrs, raw = _wsgi_call(
        app,
        "GET",
        "/api/naics/roots",
        headers={"HTTP_AUTHORIZATION": "Bearer tok2"},
    )
    assert st.startswith("200")
    payload = json.loads(raw.decode("utf-8"))
    assert (isinstance(payload, list)) or (
        isinstance(payload, dict) and ("items" in payload or payload.get("status") == "ok")
    )


def test_auth_stub_csv_whitespace_and_case_insensitive_scheme(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _ensure_import()
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setenv("AUTH_TOKENS", "tok1, tok2 ")
    from neo_agent.intake_app import create_app
    app = create_app(base_dir=tmp_path)
    st, hdrs, raw = _wsgi_call(
        app,
        "GET",
        "/api/naics/roots",
        headers={"HTTP_AUTHORIZATION": "bearer   tok2  "},
    )
    assert st.startswith("200")


def test_auth_ordering_precedes_rate_limit_and_body_size(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _ensure_import()
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setenv("AUTH_TOKENS", "tok1")
    from neo_agent.intake_app import create_app
    app = create_app(base_dir=tmp_path)

    # Even with rate-limit 0/0, missing Authorization should return 401 (not 429)
    monkeypatch.setenv("RATE_LIMIT_RPS", "0")
    monkeypatch.setenv("RATE_LIMIT_BURST", "0")
    st, hdrs, raw = _wsgi_call(app, "GET", "/api/naics/roots")
    assert st.startswith("401")

    # Even with MAX_BODY_BYTES=1 and a large payload, missing Authorization should return 401 (not 413)
    monkeypatch.setenv("MAX_BODY_BYTES", "1")
    big = b"x" * 100
    body = io.BytesIO(big)
    env_hdrs = {
        "wsgi.input": body,  # override helper default
        "CONTENT_LENGTH": str(len(big)),
    }
    st2, hdrs2, raw2 = _wsgi_call(app, "POST", "/api/agent/generate", headers=env_hdrs)
    assert st2.startswith("401")
