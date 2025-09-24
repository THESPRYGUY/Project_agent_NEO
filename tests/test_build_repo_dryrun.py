from __future__ import annotations

import json

from neo_agent.server.api import ApiRouter

from tests._profile_factory import DEFAULT_OPTIONS, make_profile


def test_dry_run_plan(tmp_path):
    router = ApiRouter(output_root=tmp_path)
    profile = make_profile()
    payload = {
        "profile": profile,
        "options": dict(DEFAULT_OPTIONS),
    }
    status, headers, body = router.dispatch("/api/repo/dry_run", "POST", json.dumps(payload).encode("utf-8"))
    assert status.startswith("200")
    response = json.loads(body)
    assert response["status"] == "ok"
    assert response["plan"]["inputs_sha256"]
    assert response["plan"]["files"][0]["action"] == "create"


def test_build_flow(tmp_path):
    router = ApiRouter(output_root=tmp_path)
    profile = make_profile()
    payload = {
        "profile": profile,
        "options": dict(DEFAULT_OPTIONS),
    }
    build_status, _, build_body = router.dispatch("/api/repo/build", "POST", json.dumps(payload).encode("utf-8"))
    assert build_status.startswith("200")
    response = json.loads(build_body)
    assert response["status"] == "ok"
    assert response["manifest"]["files"]
    assert response["zip_path"]
