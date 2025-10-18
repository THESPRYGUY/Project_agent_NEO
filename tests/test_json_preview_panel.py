from __future__ import annotations

import io
from urllib.parse import urlencode

from neo_agent.intake_app import create_app


def _invoke(app, method: str, data: dict[str, list[str] | str]) -> tuple[str, bytes]:
    encoded = urlencode(data, doseq=True).encode("utf-8")
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": "/",
        "QUERY_STRING": "",
        "SERVER_NAME": "testserver",
        "SERVER_PORT": "80",
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": "http",
        "wsgi.input": io.BytesIO(encoded if method == "POST" else b""),
        "CONTENT_LENGTH": str(len(encoded) if method == "POST" else 0),
    }
    status_headers: list[tuple[str, list[tuple[str, str]]]] = []

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        status_headers.append((status, headers))

    body = b"".join(app.wsgi_app(environ, start_response))
    return status_headers[0][0], body


def test_preview_panel_shows_after_post(tmp_path) -> None:
    app = create_app(base_dir=tmp_path)

    # Initial GET to render the page
    status, body = _invoke(app, "GET", {})
    assert status == "200 OK"
    html = body.decode("utf-8", "ignore")
    # No preview expected before any POST/profile exists
    assert "Generated Agent Profile" not in html

    # Submit minimal valid form to generate a profile
    post_data = {
        "agent_name": "Preview JSON Agent",
        "agent_version": "1.0.0",
        "agent_persona": "ENTJ",
        "domain": "Finance",
        "role": "Enterprise Analyst",
        "toolsets": ["Data Analysis"],
        "attributes": ["Strategic"],
        "autonomy": "70",
        "confidence": "65",
        "collaboration": "55",
        "communication_style": "Formal",
        "collaboration_mode": "Cross-Functional",
        "notes": "Preview panel smoke",
        "linkedin_url": "",
    }

    status, body = _invoke(app, "POST", post_data)
    assert status == "200 OK"
    html = body.decode("utf-8", "ignore")
    # Preview block present with pretty-printed JSON
    assert "Generated Agent Profile" in html
    assert "\"agent\"" in html
