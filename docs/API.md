# Project Agent NEO — API Mini-Reference

This reference covers essential endpoints for health, building a repo from an intake, fetching the last build summary, and downloading the generated ZIP. All responses include cache and observability headers. Errors return a uniform JSON envelope.

## Conventions
- Base URL: `http://127.0.0.1:5000`
- Headers always include: `Cache-Control: no-store`, `X-Request-ID`, `X-Response-Time-ms`
- Health includes: `X-NEO-Intake-Version`, `X-Commit-SHA`
- Error envelope: `{ "status":"error", "code":"<UPPER_SNAKE>", "message":"...", "details":{}, "req_id":"..." }`
- Optional auth (OFF by default): when `AUTH_REQUIRED=true`, all non-`/health` routes require `Authorization: Bearer <token>`

---

## GET /health
Returns health and build metadata.

Response 200 (application/json):
```json
{
  "status": "ok",
  "build_tag": "v3.0",
  "app_version": "0.1.0",
  "pid": 1234,
  "repo_output_dir": "/_data/generated"
}
```

Example:
```bash
curl -i http://127.0.0.1:5000/health
```

---

## POST /build
Builds the canonical 20-pack repo from an intake JSON and writes artifacts to `NEO_REPO_OUTDIR`.

Request (application/json): minimal v3 intake payload.

Response 200 (application/json): summary with outdir and stats, or uniform error envelope.

Example:
```bash
curl -sS -X POST \
  -H "Content-Type: application/json" \
  --data @examples/payloads/v3_intake.json \
  http://127.0.0.1:5000/build
```

Typical errors:
- 400 BAD_REQUEST: invalid/missing fields
- 401 UNAUTHORIZED: when auth enabled and token missing/invalid
- 413 PAYLOAD_TOO_LARGE: exceeds `MAX_BODY_BYTES`
- 429 TOO_MANY_REQUESTS: rate limit exceeded

---

## GET /last-build
Returns a compact JSON summary of the last successful build, including parity flags and outdir.

Response 200 (application/json) or 204 (no content).

Example:
```bash
curl -i http://127.0.0.1:5000/last-build
```

---

## GET /build/zip?outdir=<path>
Returns a ZIP of the generated 20-pack.

Query: `outdir` is a subdirectory name under `NEO_REPO_OUTDIR` (validated server-side).

Example:
```bash
curl -L -o repo.zip "http://127.0.0.1:5000/build/zip?outdir=agent-1-0-0"
```

---

## Parity & Rate/Size Notes
- Parity must be ALL_TRUE across 02 vs 14; failures appear in integrity artifacts and may block CI.
- 429 (rate limit) when per-IP bucket exhausted; tune via `RATE_LIMIT_RPS/BURST`.
- 413 (size) when payload exceeds `MAX_BODY_BYTES`.

