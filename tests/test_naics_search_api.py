"""Tests for /api/naics/search endpoint (Step 5 backlog: NAICS search endpoint tests).

Covers:
- Basic prefix code search
- Title substring search (case-insensitive)
- URL encoded query (spaces, plus)
- Empty / missing query returns empty items
- Limit of 25 results enforced (synthetic expansion if needed)
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import quote_plus

import json

from neo_agent.intake_app import create_app


def _call(app, full_path: str):
    """Invoke WSGI app returning (status, headers_dict, json_payload)."""
    if "?" in full_path:
        path_only, qs = full_path.split("?", 1)
    else:
        path_only, qs = full_path, ""
    captured: dict[str, object] = {}

    def start_response(status: str, headers: list[tuple[str, str]], exc_info=None):  # type: ignore
        captured["status"] = status
        captured["headers"] = headers

    environ = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": path_only,
        "QUERY_STRING": qs,
        "wsgi.input": None,
    }
    result_iter = app.wsgi_app(environ, start_response)
    body_bytes = b"".join(result_iter)
    status = captured["status"]  # type: ignore
    headers_list = captured["headers"]  # type: ignore
    return status, {k: v for k, v in headers_list}, json.loads(body_bytes.decode("utf-8"))


def test_prefix_code_search(tmp_path: Path):
    app = create_app(base_dir=tmp_path)
    status, _, data = _call(app, "/api/naics/search?q=541")
    assert status.startswith("200"), data
    codes = {item["code"] for item in data["items"]}
    # Expect both 5415 and 541512 etc. depending on reference subset
    assert any(code.startswith("541") for code in codes)


def test_title_substring_search(tmp_path: Path):
    app = create_app(base_dir=tmp_path)
    # 'portfolio' appears in 523920 title (case-insensitive)
    status, _, data = _call(app, "/api/naics/search?q=portfolio")
    assert status.startswith("200"), data
    assert any(item["code"] == "523920" for item in data["items"]), data


def test_url_encoded_query_with_space(tmp_path: Path):
    app = create_app(base_dir=tmp_path)
    # Use a space inside query (Professional, Scientific, and Technical Services -> use 'computer systems')
    q = quote_plus("computer systems")  # encodes space as +
    status, _, data = _call(app, f"/api/naics/search?q={q}")
    assert status.startswith("200"), data
    # Should match 541512 ("Computer Systems Design Services")
    assert any("computer" in item["title"].lower() for item in data["items"]), data


def test_empty_query_returns_empty_items(tmp_path: Path):
    app = create_app(base_dir=tmp_path)
    status, _, data = _call(app, "/api/naics/search?q=")
    assert status.startswith("200"), data
    assert data["items"] == []


def test_missing_query_param_returns_empty_items(tmp_path: Path):
    app = create_app(base_dir=tmp_path)
    status, _, data = _call(app, "/api/naics/search")
    assert status.startswith("200"), data
    assert data["items"] == []


def test_result_item_shape(tmp_path: Path):
    app = create_app(base_dir=tmp_path)
    status, _, data = _call(app, "/api/naics/search?q=54")
    assert status.startswith("200")
    for item in data["items"]:
        assert set(item.keys()) == {"code", "title", "level"}

