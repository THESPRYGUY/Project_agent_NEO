# API: Function-Scoped Role Lookup

Endpoint
- `GET /api/function_roles?fn=<function>&q=<query>`

Parameters
- `fn` (required): business function name, case-insensitive (e.g., `Finance`, `Security & Risk`).
- `q` (optional): space-separated tokens to filter by role code, titles, or seniority.

Response (200 OK)
```
{
  "status": "ok",
  "items": [
    { "code": "FIN:VP", "function": "Finance", "seniority": "VP", "titles": ["VP Finance"] }
  ]
}
```

Notes
- Results are de-duplicated by `code` server-side.
- The UI fetches this endpoint on function change and search input; it falls back to local filtering if the request fails.
- Data source: `data/roles/role_catalog.json` (enterprise catalog).

Errors
- Non-200 responses return `{ "status": "not_found" | "invalid" }` where applicable; the UI gracefully falls back.

