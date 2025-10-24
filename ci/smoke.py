#!/usr/bin/env python3
"""One-command smoke runner: build repo, verify parity, emit artifacts.

Writes artifacts to `_artifacts/smoke/`:
- build.json (summary for CI checks)
- INTEGRITY_REPORT.json (copied from outdir)
- repo.zip (zip of the generated repo)

Prints one line on success:
  SMOKE OK | files=20 | parity=ALL_TRUE | integrity_errors=0 | outdir=<path>
"""

from __future__ import annotations

import io
import json
import os
import sys
import zipfile
from pathlib import Path
import shutil


def _ensure_import_path() -> None:
    # Ensure `src/` is importable when running `python ci/smoke.py` directly
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


def _wsgi_call(app, method: str, path: str, body: dict | None = None):
    raw = json.dumps(body or {}).encode("utf-8")
    env = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "SERVER_NAME": "smoketest",
        "SERVER_PORT": "80",
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": "http",
        "wsgi.input": io.BytesIO(raw),
        "CONTENT_LENGTH": str(len(raw)),
    }
    status_headers: list[tuple[str, list[tuple[str, str]]]] = []

    def start_response(status, headers):
        status_headers.append((status, headers))

    resp = b"".join(app.wsgi_app(env, start_response))
    status = status_headers[0][0]
    headers = dict(status_headers[0][1])
    return status, headers, resp


def main() -> int:
    _ensure_import_path()
    from neo_agent.intake_app import create_app
    from neo_build.contracts import CANONICAL_PACK_FILENAMES

    root = Path.cwd()
    artifacts = root / "_artifacts" / "smoke"
    artifacts.mkdir(parents=True, exist_ok=True)

    fixture_path = root / "fixtures" / "sample_profile.json"
    if not fixture_path.exists():
        print(f"Missing fixture: {fixture_path}", file=sys.stderr)
        return 2
    try:
        profile = json.loads(fixture_path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover
        print(f"Failed to read fixture: {exc}", file=sys.stderr)
        return 2

    # Work root for generated repos. Respect env if provided.
    env_out = os.environ.get("NEO_REPO_OUTDIR")
    if env_out:
        work_root = Path(env_out)
    else:
        work_root = root / ".pytest-tmp" / "smoke"
        os.environ["NEO_REPO_OUTDIR"] = str(work_root.resolve())
    work_root.mkdir(parents=True, exist_ok=True)

    app = create_app(base_dir=work_root)

    # Save v3 profile
    status, _, body = _wsgi_call(app, "POST", "/save", profile)
    if status != "200 OK":
        print(f"/save failed: {body.decode('utf-8', 'ignore')}", file=sys.stderr)
        return 2

    # Build repo
    status, _, body = _wsgi_call(app, "POST", "/build", {})
    if status != "200 OK":
        print(f"/build failed: {body.decode('utf-8', 'ignore')}", file=sys.stderr)
        return 2

    res = json.loads(body.decode("utf-8"))
    outdir = Path(res["outdir"]) if isinstance(res, dict) and "outdir" in res else None
    if not outdir or not outdir.exists():
        print("build returned missing/invalid outdir", file=sys.stderr)
        return 2

    # Compute canonical file count (20)
    canonical = list(CANONICAL_PACK_FILENAMES)
    count_present = sum(1 for name in canonical if (outdir / name).exists())

    # Copy integrity report
    integrity_path = outdir / "INTEGRITY_REPORT.json"
    integrity_errors: list[str] = []
    if integrity_path.exists():
        shutil.copy2(integrity_path, artifacts / "INTEGRITY_REPORT.json")
        try:
            integrity_obj = json.loads(integrity_path.read_text(encoding="utf-8"))
            integrity_errors = list(integrity_obj.get("errors", []) or [])
        except Exception:
            integrity_errors = ["integrity_read_failed"]
    else:
        integrity_errors = ["integrity_missing"]

    # Parity flags
    parity = dict(res.get("parity") or {})
    wanted_keys = ("02_vs_14", "11_vs_02", "03_vs_02", "17_vs_02")
    parity_clean = {k: bool(parity.get(k)) for k in wanted_keys}
    all_true = all(parity_clean.values())

    # Zip the repo
    zip_path = artifacts / "repo.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Deterministic ordering
        rels = sorted((p.relative_to(outdir) for p in outdir.rglob("*")), key=lambda r: str(r))
        for rel in rels:
            zf.write(outdir / rel, arcname=str(rel))

    # Emit build summary JSON for CI
    build_json = {
        "outdir": str(outdir),
        "file_count": int(count_present),
        "parity": parity_clean,
        "integrity_errors": integrity_errors,
    }
    (artifacts / "build.json").write_text(json.dumps(build_json, indent=2), encoding="utf-8")

    # Assertions and single-line status
    if count_present != 20 or not all_true or len(integrity_errors) > 0:
        print(
            f"SMOKE FAIL | files={count_present} | parity={'ALL_TRUE' if all_true else 'HAS_FALSE'} | "
            f"integrity_errors={len(integrity_errors)} | outdir={build_json['outdir']}"
        )
        return 1

    # Print single-line status for CI logs
    print("SMOKE OK | files=20 | parity=ALL_TRUE | integrity_errors=0")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
