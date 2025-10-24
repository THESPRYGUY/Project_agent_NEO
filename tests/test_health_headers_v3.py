from __future__ import annotations

import io
import json

from neo_agent.intake_app import create_app


def test_health_reports_and_headers(tmp_path):
    app = create_app(base_dir=tmp_path)
    environ = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": "/health",
        "QUERY_STRING": "",
        "SERVER_NAME": "testserver",
        "SERVER_PORT": "80",
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": "http",
        "wsgi.input": io.BytesIO(b""),
        "CONTENT_LENGTH": "0",
    }
    status_headers = []
    def start_response(status, headers):
        status_headers.append((status, headers))
    body = b"".join(app.wsgi_app(environ, start_response))
    status, headers = status_headers[0]
    assert status == "200 OK"
    hdrs = {k.lower(): v for k, v in headers}
    assert hdrs.get("cache-control", "").startswith("no-store")
    assert hdrs.get("x-neo-intake-version") == "v3.0"
    payload = json.loads(body.decode("utf-8"))
    assert payload.get("pid")
    assert payload.get("build_tag") == "v3.0"
    assert payload.get("app_version")
    assert payload.get("repo_output_dir")

