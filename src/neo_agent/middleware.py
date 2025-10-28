"""WSGI middleware for request observability, lightweight resilience, and optional auth.

Features:
- X-Request-ID propagation and response header
- Response timing header (X-Response-Time-ms)
- Uniform JSON error envelope for common HTTP errors
- Payload size guard via MAX_BODY_BYTES
- Simple per-IP token-bucket rate limit with RATE_LIMIT_RPS/RATE_LIMIT_BURST
- Telemetry sampling for non-critical events; errors always emit
 - Optional bearer-token auth stub behind ``AUTH_REQUIRED`` (default off)

Environment variables:
- MAX_BODY_BYTES (default 1048576)
- RATE_LIMIT_RPS (default 5)
- RATE_LIMIT_BURST (default 10)
- TELEMETRY_SAMPLE_RATE (default 0.1)
 - AUTH_REQUIRED (default false)
 - AUTH_TOKENS (comma-separated list of allowed tokens)
"""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Callable, Iterable, Mapping, MutableMapping, Optional
from uuid import uuid4

from .logging import get_logger

LOGGER = get_logger("middleware")


WSGIApp = Callable[[Mapping[str, object], Callable], Iterable[bytes]]


class _TokenBucket:
    def __init__(self, rps: float, burst: int) -> None:
        self.rps = float(max(0.0, rps))
        self.burst = int(max(0, burst))
        self.tokens = float(self.burst)
        self.t_last = time.perf_counter()

    def allow(self) -> bool:
        now = time.perf_counter()
        dt = max(0.0, now - self.t_last)
        self.t_last = now
        if self.rps > 0:
            self.tokens = min(self.burst, self.tokens + self.rps * dt)
        # If rps is 0, tokens never refill; burst 0 blocks immediately
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False


class ObservabilityMiddleware:
    def __init__(self, app: WSGIApp) -> None:
        self.app = app
        # Config
        self.max_body_bytes = _get_int_env("MAX_BODY_BYTES", 1_048_576)
        self.rps = _get_float_env("RATE_LIMIT_RPS", 5.0)
        self.burst = _get_int_env("RATE_LIMIT_BURST", 10)
        self.sample_rate = _get_float_env("TELEMETRY_SAMPLE_RATE", 0.1)
        self.auth_required = _get_bool_env("AUTH_REQUIRED", False)
        self.auth_tokens = _parse_tokens(os.environ.get("AUTH_TOKENS", ""))
        # State
        self._buckets: dict[str, _TokenBucket] = {}
        self._lock = threading.Lock()

    # ---- Public WSGI entry ----
    def __call__(self, environ: MutableMapping[str, object], start_response: Callable) -> Iterable[bytes]:
        t0 = time.perf_counter()
        req_id = _req_id_from_env(environ)
        environ["neo.req_id"] = req_id
        method = str(environ.get("REQUEST_METHOD", "GET"))
        path = str(environ.get("PATH_INFO", "/")) or "/"

        # Optional bearer auth (exempt only /health)
        if self.auth_required and path != "/health":
            authz = environ.get("HTTP_AUTHORIZATION")
            if isinstance(authz, (bytes, bytearray)):
                authz = authz.decode("utf-8", errors="ignore")
            token = None
            if isinstance(authz, str) and authz.startswith("Bearer "):
                token = authz[7:].strip()
            if not token or token not in self.auth_tokens:
                duration_ms = int((time.perf_counter() - t0) * 1000)
                body = _error_envelope(req_id, "UNAUTHORIZED", "missing or invalid bearer token", details={"path": path})
                headers = _base_headers(environ, req_id, duration_ms)
                headers += [("WWW-Authenticate", "Bearer realm=\"neo-intake\", charset=\"UTF-8\""), ("Content-Type", "application/json; charset=utf-8"), ("Content-Length", str(len(body)))]
                start_response("401 Unauthorized", headers)
                _log_http(method, path, 401, duration_ms, req_id)
                return [body]

        # Payload size guard for methods that typically carry a body
        if method in {"POST", "PUT", "PATCH"}:
            try:
                clen = int(str(environ.get("CONTENT_LENGTH") or "0"))
            except Exception:
                clen = 0
            if clen > self.max_body_bytes:
                duration_ms = int((time.perf_counter() - t0) * 1000)
                body = _error_envelope(req_id, "PAYLOAD_TOO_LARGE", "payload exceeds MAX_BODY_BYTES", details={"content_length": clen})
                headers = _base_headers(environ, req_id, duration_ms)
                start_response("413 Payload Too Large", headers + [("Content-Type", "application/json; charset=utf-8"), ("Content-Length", str(len(body)))])
                self._emit_error({"status": 413, "method": method, "path": path, "req_id": req_id, "reason": "size_limit"})
                _log_http(method, path, 413, duration_ms, req_id)
                return [body]

        # Rate limiting (exempt health/last-build)
        if path not in {"/health", "/last-build"}:
            ip = _client_ip(environ)
            if not self._allow(ip):
                duration_ms = int((time.perf_counter() - t0) * 1000)
                body = _error_envelope(req_id, "TOO_MANY_REQUESTS", "rate limit exceeded", details={"ip": ip})
                headers = _base_headers(environ, req_id, duration_ms)
                start_response("429 Too Many Requests", headers + [("Content-Type", "application/json; charset=utf-8"), ("Content-Length", str(len(body)))])
                self._emit_error({"status": 429, "method": method, "path": path, "req_id": req_id, "ip": ip})
                _log_http(method, path, 429, duration_ms, req_id)
                return [body]

        # Call downstream app and capture status/headers
        captured: dict[str, object] = {}

        def _sr(status: str, headers: list[tuple[str, str]], exc_info=None):  # noqa: ANN001
            captured["status"] = status
            captured["headers"] = headers
            captured["exc_info"] = exc_info
            # Defer actual start_response until we decide on final body/headers

        try:
            chunks = list(self.app(environ, _sr))
            body_bytes = b"".join(chunks)
            status_text = str(captured.get("status", "200 OK"))
            status_code = int(status_text.split(" ")[0])
            duration_ms = int((time.perf_counter() - t0) * 1000)

            final_headers = _merge_headers(list(captured.get("headers", [])), _base_headers(environ, req_id, duration_ms))

            if status_code in {400, 404, 405, 413, 429, 500}:
                # Build uniform error envelope; try to extract message/details from original body
                msg, details = _extract_message_details(body_bytes)
                code = _status_code_name(status_code)
                body_bytes = _error_envelope(req_id, code, msg, details=details)
                final_headers = _replace_header(final_headers, "Content-Type", "application/json; charset=utf-8")
                final_headers = _replace_header(final_headers, "Content-Length", str(len(body_bytes)))
                self._emit_error({"status": status_code, "method": method, "path": path, "req_id": req_id})
            else:
                # Non-error: optionally sample a telemetry event
                self._emit_sampled("http:request", {"status": status_code, "method": method, "path": path, "req_id": req_id, "duration_ms": duration_ms})

            _log_http(method, path, status_code, duration_ms, req_id)
            exc_info = captured.get("exc_info")
            if exc_info is None:
                start_response(status_text, final_headers)
            else:
                start_response(status_text, final_headers, exc_info)
            return [body_bytes]
        except Exception as exc:  # noqa: BLE001
            duration_ms = int((time.perf_counter() - t0) * 1000)
            body = _error_envelope(req_id, "INTERNAL_ERROR", str(exc), details={})
            headers = _base_headers(environ, req_id, duration_ms)
            start_response("500 Internal Server Error", headers + [("Content-Type", "application/json; charset=utf-8"), ("Content-Length", str(len(body)))])
            self._emit_error({"status": 500, "method": method, "path": path, "req_id": req_id, "exc": type(exc).__name__})
            _log_http(method, path, 500, duration_ms, req_id)
            return [body]

    # ---- internals ----
    def _allow(self, ip: str) -> bool:
        key = ip or "unknown"
        with self._lock:
            bucket = self._buckets.get(key)
            if not bucket:
                bucket = _TokenBucket(self.rps, self.burst)
                self._buckets[key] = bucket
        return bucket.allow()

    def _emit_sampled(self, name: str, payload: Mapping[str, object]) -> None:
        # Dynamic import to play well with monkeypatching in tests
        try:
            from . import telemetry  # type: ignore
            emitter = getattr(telemetry, "emit_event", None)
        except Exception:  # pragma: no cover
            emitter = None
        try:
            rate = float(self.sample_rate)
        except Exception:
            rate = 0.0
        if emitter and rate > 0:
            # Simple time-based sampler with per-process determinism (no RNG)
            t = int(time.time() * 1_000_000)
            if (t % 1000) < int(rate * 1000):  # approx
                try:
                    emitter(name, dict(payload))
                except Exception:  # pragma: no cover
                    pass

    def _emit_error(self, payload: Mapping[str, object]) -> None:
        try:
            from . import telemetry  # type: ignore
            emitter = getattr(telemetry, "emit_event", None)
            if emitter:
                emitter("http:error", dict(payload))
        except Exception:  # pragma: no cover
            pass


def _get_int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except Exception:
        return int(default)


def _get_float_env(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except Exception:
        return float(default)


def _req_id_from_env(environ: Mapping[str, object]) -> str:
    rid = environ.get("HTTP_X_REQUEST_ID")
    if isinstance(rid, (bytes, bytearray)):
        rid = rid.decode("utf-8", errors="ignore")
    if isinstance(rid, str) and rid.strip():
        return rid.strip()
    return str(uuid4())


def _client_ip(environ: Mapping[str, object]) -> str:
    # Prefer first forwarded for entry if present
    fwd = environ.get("HTTP_X_FORWARDED_FOR")
    if isinstance(fwd, (bytes, bytearray)):
        fwd = fwd.decode("utf-8", errors="ignore")
    if isinstance(fwd, str) and fwd:
        return fwd.split(",")[0].strip()
    ra = environ.get("REMOTE_ADDR")
    if isinstance(ra, (bytes, bytearray)):
        ra = ra.decode("utf-8", errors="ignore")
    return str(ra or "")


def _status_code_name(status: int) -> str:
    mapping = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        413: "PAYLOAD_TOO_LARGE",
        429: "TOO_MANY_REQUESTS",
        500: "INTERNAL_ERROR",
    }
    return mapping.get(int(status), f"HTTP_{int(status)}")


def _error_envelope(req_id: str, code: str, message: str, *, details: Optional[Mapping[str, object]] = None) -> bytes:
    payload = {
        "status": "error",
        "code": code,
        "message": message or "",
        "details": dict(details or {}),
        "req_id": req_id,
    }
    return json.dumps(payload).encode("utf-8")


def _extract_message_details(body: bytes) -> tuple[str, dict[str, object]]:
    if not body:
        return "", {}
    try:
        obj = json.loads(body.decode("utf-8"))
        if isinstance(obj, dict):
            msg = (
                str(obj.get("message"))
                or str(obj.get("error"))
                or str(obj.get("status"))
            )
            return msg, obj if isinstance(obj, dict) else {}
    except Exception:
        try:
            txt = body.decode("utf-8", errors="ignore")
            return txt[:200], {}
        except Exception:
            return "", {}
    return "", {}


def _replace_header(headers: list[tuple[str, str]], name: str, value: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    seen = False
    for k, v in headers:
        if k.lower() == name.lower():
            out.append((k, value))
            seen = True
        else:
            out.append((k, v))
    if not seen:
        out.append((name, value))
    return out


def _merge_headers(existing: list[tuple[str, str]], additions: list[tuple[str, str]]) -> list[tuple[str, str]]:
    out = list(existing)
    for name, value in additions:
        # replace if exists
        replaced = False
        for i, (k, _v) in enumerate(out):
            if k.lower() == name.lower():
                out[i] = (k, value)
                replaced = True
                break
        if not replaced:
            out.append((name, value))
    return out


def _base_headers(environ: Mapping[str, object], req_id: str, duration_ms: int) -> list[tuple[str, str]]:
    return [
        ("X-Request-ID", req_id),
        ("X-Response-Time-ms", str(int(duration_ms))),
        ("Cache-Control", "no-store, must-revalidate"),
    ]


def _log_http(method: str, path: str, status: int, duration_ms: int, req_id: str) -> None:
    try:
        # Attach fields for our JSON formatter when available
        LOGGER.info(
            "http_request",
            extra={
                "req_id": req_id,
                "method": method,
                "path": path,
                "status": status,
                "duration_ms": duration_ms,
            },
        )
    except Exception:
        pass


def _parse_tokens(csv: str) -> set[str]:
    try:
        parts = [p.strip() for p in str(csv or "").split(",")]
        return {p for p in parts if p}
    except Exception:
        return set()


def _get_bool_env(name: str, default: bool) -> bool:
    raw = str(os.environ.get(name, "")).strip().lower()
    if not raw:
        return bool(default)
    return raw in {"1", "true", "yes", "y", "on"}
