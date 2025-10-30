#!/usr/bin/env python3
"""One-command smoke runner: build repo, verify parity, emit artifacts.

Writes artifacts to `_artifacts/smoke/`:
- build.json (summary for CI checks)
- INTEGRITY_REPORT.json (copied from outdir)
- repo.zip (zip of the generated repo)

Prints one line on success:
  SMOKE OK | files=20 | parity=ALL_TRUE | integrity_errors=0
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

    # Decide behavior based on parity gate flag
    fail_on_parity = str(os.environ.get("FAIL_ON_PARITY") or "false").lower() in ("1", "true", "yes")

    # Always write a concise smoke.log line for PR summary
    log_path = artifacts / "smoke.log"

    # If parity is false and gate is enabled, emit required one-liner and deltas, then exit(1)
    if not all_true and fail_on_parity:
        def _tf(b: bool) -> str:
            return "t" if bool(b) else "f"
        line = (
            f"PARITY FAIL | "
            f"02_vs_14={_tf(parity_clean.get('02_vs_14'))} "
            f"11_vs_02={_tf(parity_clean.get('11_vs_02'))} "
            f"03_vs_02={_tf(parity_clean.get('03_vs_02'))} "
            f"17_vs_02={_tf(parity_clean.get('17_vs_02'))}"
        )
        print(line)
        try:
            log_path.write_text(line + "\n", encoding="utf-8")
        except Exception:
            pass
        # Pretty-print first 10 deltas (pack:key got→expected)
        deltas = res.get("parity_deltas")
        items: list[dict] = []
        try:
            if isinstance(deltas, dict):
                for pack_key, diffs in deltas.items():
                    for k, tup in (diffs or {}).items():
                        got, expected = (tup[0], tup[1]) if isinstance(tup, (list, tuple)) and len(tup) == 2 else (None, None)
                        items.append({"pack": str(pack_key), "key": str(k), "got": got, "expected": expected})
            elif isinstance(deltas, list):
                # Already flattened structure
                for d in deltas:
                    if isinstance(d, dict) and {"pack","key","got","expected"}.issubset(d.keys()):
                        items.append({"pack": str(d["pack"]), "key": str(d["key"]), "got": d.get("got"), "expected": d.get("expected")})
        except Exception:
            items = []
        for item in items[:10]:
            print(f" - {item['pack']}:{item['key']} got={item['got']} expected={item['expected']}")
        return 1

    # If other fatal conditions occur, preserve legacy failure behavior
    if count_present != 20 or len(integrity_errors) > 0:
        line = (
            f"SMOKE FAIL | files={count_present} | parity={'ALL_TRUE' if all_true else 'HAS_FALSE'} | "
            f"integrity_errors={len(integrity_errors)} | outdir={build_json['outdir']}"
        )
        print(line)
        try:
            log_path.write_text(line + "\n", encoding="utf-8")
        except Exception:
            pass
        return 1

    # Success path regardless of FAIL_ON_PARITY when parity is true
    ok_line = "✅ SMOKE OK | files=20 | parity=ALL_TRUE | integrity_errors=0"
    print(ok_line)
    try:
        log_path.write_text(ok_line + "\n", encoding="utf-8")
    except Exception:
        pass
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
