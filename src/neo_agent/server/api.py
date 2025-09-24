"""JSON API surface for intake-powered repository generation."""

from __future__ import annotations

import json
from http import HTTPStatus
from pathlib import Path
from typing import Any, Dict, Tuple

from .build_repo import build_repository, plan_repository
from .errors import ServerError, enrich_error
from .validators import validate_build_options, validate_profile


class ApiRouter:
    """Minimal router for the intake WSGI entrypoint."""

    def __init__(self, output_root: Path | None = None) -> None:
        self.output_root = output_root

    def _json(self, status: HTTPStatus, payload: Dict[str, Any]) -> Tuple[str, list[tuple[str, str]], bytes]:
        body = json.dumps(payload).encode("utf-8")
        headers = [("Content-Type", "application/json"), ("Content-Length", str(len(body)))]
        return f"{status.value} {status.phrase}", headers, body

    def dispatch(self, path: str, method: str, body: bytes) -> Tuple[str, list[tuple[str, str]], bytes]:
        try:
            data = json.loads(body.decode("utf-8") or "{}") if body else {}
        except json.JSONDecodeError as exc:
            return self._json(HTTPStatus.BAD_REQUEST, {"status": "error", "message": f"Invalid JSON: {exc}"})

        if path == "/api/profile/validate" and method == "POST":
            return self._validate_profile(data)
        if path == "/api/repo/dry_run" and method == "POST":
            return self._dry_run(data)
        if path == "/api/repo/build" and method == "POST":
            return self._build(data)
        return self._json(HTTPStatus.NOT_FOUND, {"status": "error", "message": "Unknown endpoint"})

    def _validate_profile(self, data: Dict[str, Any]):
        profile = data.get("profile")
        issues = validate_profile(profile)
        if issues:
            return self._json(HTTPStatus.OK, {"status": "error", "issues": [issue.to_dict() for issue in issues]})
        return self._json(HTTPStatus.OK, {"status": "ok", "issues": []})

    def _dry_run(self, data: Dict[str, Any]):
        profile = data.get("profile")
        options = data.get("options", {})
        issues = validate_profile(profile)
        option_issues = validate_build_options(options)
        if issues or option_issues:
            payload = {
                "status": "error",
                "issues": [issue.to_dict() for issue in issues + option_issues],
            }
            return self._json(HTTPStatus.OK, payload)
        try:
            plan = plan_repository(profile, options, output_root=self.output_root)
        except ServerError as exc:
            return self._json(HTTPStatus.BAD_REQUEST, {"status": "error", "issues": [exc.to_dict()]})
        plan_payload = {
            "status": "ok",
            "plan": plan["plan"],
            "inputs_sha256": plan["context"]["inputs_sha256"],
        }
        return self._json(HTTPStatus.OK, plan_payload)

    def _build(self, data: Dict[str, Any]):
        profile = data.get("profile")
        options = data.get("options", {})
        try:
            result = build_repository(profile, options, output_root=self.output_root)
        except ServerError as exc:
            return self._json(HTTPStatus.BAD_REQUEST, {"status": "error", "issues": [exc.to_dict()]})
        except Exception as exc:  # pragma: no cover - unexpected failure
            server_exc = enrich_error("E_IO_WRITE", str(exc))
            return self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"status": "error", "issues": [server_exc.to_dict()]})
        return self._json(HTTPStatus.OK, result)
