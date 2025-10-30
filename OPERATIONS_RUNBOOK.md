# Operations Runbook â€” Project NEO Intake Service

- Environments: local (compose), staging, prod
- Runtime: Python 3.11, gunicorn, WSGI app `wsgi:app`

## Environment Variables
- NEO_REPO_OUTDIR — base path for generated repos (default: <repo>/_generated)
- FAIL_ON_PARITY — hard-fail KPI parity in integrity checks (	rue|false)
- NEO_APPLY_OVERLAYS — apply overlays post build (	rue|false)
- NEO_CONTRACT_MODE — preview|full (CI default: ull)

## Health & Headers
- `GET /health` â†’ 200 JSON: `{status, build_tag, app_version, pid, repo_output_dir, ...}`
- Response headers include:
  - `X-NEO-Intake-Version: v3.0`
  - `X-Commit-SHA: <sha>`
  - `Cache-Control: no-store, must-revalidate`

## Logs
- Structured JSON to stdout: `{ts, level, logger, msg, [event], [payload]}`
- Tune via `LOG_LEVEL`.

## Docker
- Build: `docker build -t neo-intake:local --build-arg GIT_SHA=$(git rev-parse --short HEAD) .`
- Run: `docker run -p 5000:5000 --env-file .env neo-intake:local`
- Health: `curl -i http://localhost:5000/health`

## Compose (dev)
- `docker compose -f docker-compose.dev.yml up --build`
- Mounts repo, exposes `:5000`.

## Release
- Tag * — GH workflow builds image, smoke-tests /health, generates artifacts:
  - epo.zip (source archive)
  - INTEGRITY_REPORT.json (from builder)
  - contract_report.json (from contract validator)
  - uild.json (tag, sha, timestamp)

## Resilience & Limits

Environment variables (override via `.env` or container env):

- `MAX_BODY_BYTES` (default `1048576`) â€“ hard cap on request body size. Exceeding returns `413` with a JSON error envelope. Keep at 1â€“5MB for typical form/JSON posts.
- `RATE_LIMIT_RPS` (default `5`) â€“ perâ€‘IP token refill rate in requests per second.
- `RATE_LIMIT_BURST` (default `10`) â€“ perâ€‘IP burst tokens. Set both to `0` to disable nonâ€‘exempt traffic (useful in maintenance).
- `TELEMETRY_SAMPLE_RATE` (default `0.1`) â€“ sampling rate (0.0â€“1.0) for nonâ€‘critical telemetry. Errors always emit.

Headers emitted on middlewareâ€‘wrapped responses:
- `X-Request-ID` â€“ echoed from client `X-Request-ID` or generated.
- `X-Response-Time-ms` â€“ integer duration from request receive to response.

Error envelope (uniform across 400/404/405/413/429/500):

```json
{"status":"error","code":"<UPPER_SNAKE>","message":"...","details":{},"req_id":"..."}
```

Rateâ€‘limit exemptions: `GET /health`, `GET /last-build`.

## Security

Environment variables (auth stub is optional and OFF by default):

- `AUTH_REQUIRED` (default `false`) â€” when `true`, all non-`/health` routes require a valid Bearer token
- `AUTH_TOKENS` (default empty) â€” commaâ€‘separated list of accepted tokens

Behavior:
- When `AUTH_REQUIRED=true` and the `Authorization: Bearer <token>` header is missing/invalid, responses return `401` with a JSON envelope `{status:"error", code:"UNAUTHORIZED", ...}` and `WWW-Authenticate: Bearer` header
- `/health` is always exempt to support liveness/readiness probes

Headers & Privacy:
- Always emit: `X-Request-ID`, `X-Response-Time-ms`, `Cache-Control: no-store`
- Do not log secrets, tokens, or PII. Ensure any identifiers are hashed or redacted

Dependency Pinning Policy:
- Python: pins live in `constraints/requirements.lock` and `constraints/requirements-dev.lock`; update monthly or on CVE
- Node: `package-lock.json` is authoritative; update monthly or on CVE via `npm audit fix` PRs

SCA Overview (warnâ€‘only):
- CI runs `pip-audit` for Python and `npm audit --production` for Node
- Findings do not fail PRs; reports are uploaded as artifacts for review

## Environment Defaults (Truth Table)

| Name | Default | Effect |
| - | - | - |
| `NEO_REPO_OUTDIR` | `/_data/generated` | Base folder for generated repos |
| `FAIL_ON_PARITY` | `false` | When `true`, fail parity mismatches as errors in integrity checks |
| `NEO_APPLY_OVERLAYS` | `false` | Apply overlays post-build |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `MAX_BODY_BYTES` | `1048576` | Hard cap on request body size; > returns 413 |
| `RATE_LIMIT_RPS` | `5` | Token refill rate per IP |
| `RATE_LIMIT_BURST` | `10` | Max burst tokens per IP |
| `TELEMETRY_SAMPLE_RATE` | `0.1` | Sampling for non-critical telemetry |
| `AUTH_REQUIRED` | `false` | When `true`, non-`/health` routes require Bearer token |
| `AUTH_TOKENS` | `` | CSV list of accepted tokens when auth is enabled |
| `GIT_SHA` | â€” | Injected at build; echoed in headers |

## Headers
- Always: `X-Request-ID`, `X-Response-Time-ms`, `Cache-Control: no-store`
- Health/others: `X-NEO-Intake-Version: v3.0`, `X-Commit-SHA: <sha>` (via app headers)

## Error Envelope Contract
All error responses share the JSON envelope:

```json
{"status":"error","code":"<UPPER_SNAKE>","message":"<string>","details":{},"req_id":"<uuid>"}
```

Examples:
- 400 BAD_REQUEST: invalid payload
- 404 NOT_FOUND: unknown path
- 405 METHOD_NOT_ALLOWED: wrong method
- 413 PAYLOAD_TOO_LARGE: body exceeds `MAX_BODY_BYTES`
- 429 TOO_MANY_REQUESTS: rate limit exceeded
- 500 INTERNAL_ERROR: unhandled exception
- `DUPLICATE_LEGACY_V3_CONFLICT`: legacy+v3 fields for same concept (adapter guard)

Auth 401 (when `AUTH_REQUIRED=true`):
- Envelope: `{ "status":"error", "code":"UNAUTHORIZED", "message":"Missing or invalid bearer token.", "details":{}, "req_id":"..." }`
- Header: `WWW-Authenticate: Bearer realm="neo", error="invalid_token"`

## Release Steps
1) Tag `v*`
2) CI builds image and runs health smoke
3) Generate integrity artifacts (`repo.zip`, `INTEGRITY_REPORT.json`, `build.json`)
4) Attach artifacts to the release


## Determinism Policy
- JSON writes use canonical UTF-8, indent=2, sort_keys=True.
- Deep-sorted lists and dict keys for stable ordering across builds.
- In CI, meta.created_at is fixed to 1970-01-01T00:00:00Z.
- Meta ersion prefers APP_VERSION or GIT_SHA when present.

## Validator Failure Modes & Triage
- contract-validate job runs python scripts/contract_validate.py <pack_dir> and uploads:
  - INTEGRITY_REPORT.json, contract_report.json, epo.zip.
- Fails when any of: contract_ok, crossref_ok, parity_ok, packs_complete is false, or any missing_* entries non-empty.
- Common fixes:
  - Add missing top-level keys per file contract.
  - Align KPI targets across 02/11/14/17.
  - Ensure cross-file refs in 02 point to canonical filenames.

