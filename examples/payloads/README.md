# Example Payloads

This folder contains example JSON payloads for local testing. These files are not used by tests or the golden snapshot.

## Files
- `v3_intake.json` — a minimal-but-valid v3 intake suitable for `/build`
- `legacy_only.json` — a legacy-only payload that exercises the legacy→v3 adapter (auto-migration)

## Usage

Build with v3 intake:
```bash
curl -sS -X POST -H "Content-Type: application/json" --data @examples/payloads/v3_intake.json http://127.0.0.1:5000/build
```

Build with legacy-only payload (adapter will migrate):
```bash
curl -sS -X POST -H "Content-Type: application/json" --data @examples/payloads/legacy_only.json http://127.0.0.1:5000/build
```

Notes:
- Do not include secrets/PII in payloads.
- To enforce strict parity locally, set `FAIL_ON_PARITY=true`.

