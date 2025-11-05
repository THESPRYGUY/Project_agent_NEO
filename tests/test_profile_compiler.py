from __future__ import annotations

import io
import json
from pathlib import Path
from urllib.parse import urlencode

from neo_agent.intake_app import create_app


def _invoke(app, method: str, data: dict[str, list[str] | str]) -> bytes:
    encoded = urlencode(data, doseq=True).encode("utf-8")
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": "/",
        "QUERY_STRING": "",
        "SERVER_NAME": "testserver",
        "SERVER_PORT": "80",
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": "http",
        "wsgi.input": io.BytesIO(encoded),
        "CONTENT_LENGTH": str(len(encoded)),
    }

    status_headers: list[tuple[str, list[tuple[str, str]]]] = []

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        status_headers.append((status, headers))

    response_iter = app.wsgi_app(environ, start_response)
    body = b"".join(response_iter)
    assert status_headers[0][0] == "200 OK"
    return body


def test_compiled_profile_written(tmp_path: Path) -> None:
    app = create_app(base_dir=tmp_path)

    # Minimal post to trigger file creation
    post_data = {
        "agent_name": "Compile Test",
        "agent_version": "1.0.0",
    }
    _invoke(app, "POST", post_data)

    raw_path = tmp_path / "agent_profile.json"
    compiled_path = tmp_path / "agent_profile.compiled.json"
    assert raw_path.exists()
    assert compiled_path.exists()

    with raw_path.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)
    assert isinstance(raw.get("_compiled"), dict)

    with compiled_path.open("r", encoding="utf-8") as fh:
        compiled = json.load(fh)
    # Spot-check keys
    for key in ("meta", "slugs", "agent", "routing", "gating"):
        assert key in compiled
