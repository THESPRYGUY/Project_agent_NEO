from __future__ import annotations

import io
import json
import os
from typing import List, Tuple

import pytest

from neo_agent.intake_app import create_app


def _invoke(
    app,
    method: str,
    path: str = "/",
    body: bytes = b"",
    headers: dict[str, str] | None = None,
):
    headers = headers or {}
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "SERVER_NAME": "testserver",
        "SERVER_PORT": "80",
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": "http",
        "wsgi.input": io.BytesIO(body),
        "CONTENT_LENGTH": str(len(body)),
    }
    for k, v in headers.items():
        environ[f"HTTP_{k.upper().replace('-', '_')}"] = v

    status_headers: List[Tuple[str, list[tuple[str, str]]]] = []

    def start_response(status: str, hdrs: list[tuple[str, str]]):
        status_headers.append((status, hdrs))

    # Use the WSGI callable (middleware wraps __call__)
    body_iter = app(environ, start_response)
    resp_body = b"".join(body_iter)
    status, hdrs = status_headers[0]
    header_map = {k.lower(): v for k, v in hdrs}
    return status, header_map, resp_body


def test_request_id_generated_and_header_returned(tmp_path):
    app = create_app(base_dir=tmp_path)
    status, headers, _ = _invoke(app, "GET", "/health")
    assert "x-request-id" in headers
    assert headers["x-request-id"]


def test_request_id_passthrough_when_client_sets_header(tmp_path):
    app = create_app(base_dir=tmp_path)
    rid = "test-req-123"
    status, headers, _ = _invoke(app, "GET", "/health", headers={"X-Request-ID": rid})
    assert headers.get("x-request-id") == rid


def test_response_time_header_present_and_integer(tmp_path):
    app = create_app(base_dir=tmp_path)
    status, headers, _ = _invoke(app, "GET", "/health")
    assert "x-response-time-ms" in headers
    assert headers["x-response-time-ms"].isdigit()


def test_payload_too_large_returns_413_envelope(monkeypatch, tmp_path):
    app = create_app(base_dir=tmp_path)
    monkeypatch.setenv("MAX_BODY_BYTES", "10")
    payload = b"x" * 100
    status, headers, body = _invoke(app, "POST", "/api/agent/generate", body=payload)
    assert status.startswith("413")
    assert headers.get("content-type", "").startswith("application/json")
    env = json.loads(body.decode("utf-8"))
    assert env.get("status") == "error"
    assert env.get("code") == "PAYLOAD_TOO_LARGE"
    assert env.get("req_id") == headers.get("x-request-id")


def test_rate_limit_returns_429_envelope(monkeypatch, tmp_path):
    app = create_app(base_dir=tmp_path)
    monkeypatch.setenv("RATE_LIMIT_RPS", "0")
    monkeypatch.setenv("RATE_LIMIT_BURST", "0")
    status, headers, body = _invoke(app, "GET", "/api/rate-test")
    assert status.startswith("429")
    env = json.loads(body.decode("utf-8"))
    assert env.get("status") == "error"
    assert env.get("code") == "TOO_MANY_REQUESTS"


def test_error_envelope_shape_for_404_and_500(monkeypatch, tmp_path):
    app = create_app(base_dir=tmp_path)
    # 404 via unknown path
    status, headers, body = _invoke(app, "GET", "/no-such")
    assert status.startswith("404")
    env = json.loads(body.decode("utf-8"))
    assert env["status"] == "error" and env["code"] == "NOT_FOUND"
    assert env["req_id"] == headers.get("x-request-id")

    # 500 via /last-build with unreadable path (make the file a directory)
    out_root = os.getenv("NEO_REPO_OUTDIR")
    assert out_root
    problem_path = os.path.join(out_root, "_last_build.json")
    # Ensure a directory exists at the expected file path to trigger an error on read
    if os.path.isfile(problem_path):
        os.remove(problem_path)
    os.makedirs(problem_path, exist_ok=True)
    status2, headers2, body2 = _invoke(app, "GET", "/last-build")
    assert status2.startswith("500")
    env2 = json.loads(body2.decode("utf-8"))
    assert env2["status"] == "error" and env2["code"] == "INTERNAL_ERROR"


def test_telemetry_sampling_called_on_error(monkeypatch, tmp_path):
    app = create_app(base_dir=tmp_path)
    calls: list[tuple[str, dict]] = []

    def fake_emit(name: str, payload):  # noqa: ANN001
        calls.append((name, dict(payload)))

    monkeypatch.setenv("RATE_LIMIT_RPS", "0")
    monkeypatch.setenv("RATE_LIMIT_BURST", "0")
    monkeypatch.setenv("TELEMETRY_SAMPLE_RATE", "0.0")  # sampling off for non-errors
    monkeypatch.setenv("LOG_LEVEL", "ERROR")
    # Patch telemetry emitter
    import neo_agent.telemetry as telemetry

    monkeypatch.setattr(telemetry, "emit_event", fake_emit, raising=False)

    status, headers, body = _invoke(app, "GET", "/api/rate-test")
    assert status.startswith("429")
    # Ensure error emitter was called regardless of sampling
    assert any(n == "http:error" for (n, _p) in calls)
