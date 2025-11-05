from __future__ import annotations

import re

from neo_agent.intake_app import create_app


def test_persona_tabs_are_non_submit() -> None:
    app = create_app()

    # Render the form (GET /) and assert persona tab buttons are non-submit
    status_headers: list[tuple[str, list[tuple[str, str]]]] = []

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        status_headers.append((status, headers))

    body = b"".join(
        app.wsgi_app(
            {
                "REQUEST_METHOD": "GET",
                "PATH_INFO": "/",
                "QUERY_STRING": "",
                "SERVER_NAME": "testserver",
                "SERVER_PORT": "80",
                "wsgi.version": (1, 0),
                "wsgi.url_scheme": "http",
                "wsgi.input": None,
                "CONTENT_LENGTH": "0",
            },
            start_response,
        )
    )

    assert status_headers and status_headers[0][0] == "200 OK"
    html = body.decode("utf-8", "ignore")
    assert 'id="persona-tab-operator"' in html
    assert 'id="persona-tab-agent"' in html
    # Ensure explicit type="button" to prevent form submission
    assert re.search(r'id="persona-tab-operator"\s+type="button"', html)
    assert re.search(r'id="persona-tab-agent"\s+type="button"', html)
