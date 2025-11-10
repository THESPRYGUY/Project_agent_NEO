#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
import io
import hashlib
import zipfile
from typing import Any, Dict


def main(argv: list[str] | None = None) -> int:
    argv = list(argv or sys.argv[1:])
    if not argv:
        print("Usage: python scripts/contract_validate.py <pack_dir>", file=sys.stderr)
        return 2

    pack_dir = Path(argv[0])
    if not pack_dir.exists() or not pack_dir.is_dir():
        print(json.dumps({"error": f"pack_dir not found: {pack_dir}"}))
        return 2

    # Ensure repository sources are importable
    root = Path(__file__).resolve().parents[1]
    src = root / "src"
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))

    # Lazy import to avoid masking JSON output on import errors
    from neo_build.validators import integrity_report  # type: ignore
    from neo_build.contracts import CANONICAL_PACK_FILENAMES  # type: ignore

    # Load only canonical files for report
    built: Dict[str, Any] = {}
    for name in CANONICAL_PACK_FILENAMES:
        p = pack_dir / name
        try:
            built[name] = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            built[name] = {}

    report = integrity_report({}, built)

    contract_ok = bool(report.get("contract_ok"))
    crossref_ok = bool(report.get("crossref_ok"))
    parity_ok = bool(report.get("parity_ok"))
    packs_complete = bool(report.get("packs_complete"))
    missing_keys = dict(report.get("missing_keys") or {})
    missing_sections = dict(report.get("missing_sections") or {})
    crossref_errors = list(report.get("crossref_errors") or [])
    parity_deltas = report.get("parity_deltas") or []

    out = {
        "contract_ok": contract_ok,
        "crossref_ok": crossref_ok,
        "parity_ok": parity_ok,
        "packs_complete": packs_complete,
        "missing_keys": missing_keys,
        "missing_sections": missing_sections,
        "crossref_errors": crossref_errors,
        "parity_deltas": parity_deltas,
    }

    # Write alongside packs for CI artifact pickup
    (pack_dir / "contract_report.json").write_text(json.dumps(out, indent=2), encoding="utf-8")

    fail = (not contract_ok) or (not crossref_ok) or (not parity_ok) or (not packs_complete)
    if not fail:
        # Also fail if any missing maps are non-empty
        if any(missing_keys.values()) or any(missing_sections.values()):
            fail = True

    # Optional SoT checks (best-effort): last-build presence and zip hash parity
    calc_hash = ""
    try:
        # pack_dir expected as .../_generated/<AGENT_ID>/<TS>
        outdir = pack_dir
        out_root = outdir.parents[1]
        last_path = out_root / "_last_build.json"
        required_keys = {"schema_version", "agent_id", "outdir", "files", "ts", "zip_hash"}
        if last_path.exists():
            last = json.loads(last_path.read_text(encoding="utf-8"))
            # Validate minimal schema and version >= 2.1.1
            try:
                parts = str((last or {}).get("schema_version") or "0.0.0").split(".")
                ver_tuple = (int(parts[0]), int(parts[1]), int(parts[2]))
            except Exception:
                ver_tuple = (0, 0, 0)
            has_keys = required_keys.issubset(set(last.keys()) if isinstance(last, dict) else set())
            out["last_build_schema_ok"] = bool(has_keys and (ver_tuple >= (2, 1, 1)))
            stored_hash = str(last.get("zip_hash") or "")
            recorded_outdir = str(last.get("outdir") or "").replace("\\", "/")
            current_outdir = str(outdir.resolve()).replace("\\", "/")
            same_outdir = False
            if recorded_outdir and current_outdir:
                same_outdir = recorded_outdir.endswith(current_outdir) or current_outdir.endswith(recorded_outdir)
            if same_outdir:
                # Build canonical zip bytes (fixed date_time)
                excluded_names = {"_last_build.json", ".DS_Store", "contract_report.json"}
                excluded_dirs = {"__pycache__", ".pytest_cache", ".git", "spec_preview"}
                rels = []
                for p in outdir.rglob("*"):
                    if not p.is_file():
                        continue
                    rel = p.relative_to(outdir)
                    parts = rel.parts
                    if any(part.startswith(".") for part in parts):
                        continue
                    if any(part in excluded_dirs for part in parts):
                        continue
                    if rel.name in excluded_names:
                        continue
                    rels.append(rel)
                rels = sorted(rels, key=lambda r: str(r))
                buf = io.BytesIO()
                with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                    for rel in rels:
                        data = (outdir / rel).read_bytes()
                        info = zipfile.ZipInfo(str(rel).replace("\\", "/"))
                        info.date_time = (1980, 1, 1, 0, 0, 0)
                        info.compress_type = zipfile.ZIP_DEFLATED
                        zf.writestr(info, data)
                calc_hash = hashlib.sha256(buf.getvalue()).hexdigest()
                tmp_dir = out_root / outdir.parent.name / ".tmp"
                tmp_residue = [p for p in tmp_dir.glob("*") if p.exists()] if tmp_dir.exists() else []
                out["zip_hash_match"] = (stored_hash and stored_hash == calc_hash)
                out["no_tmp_residue"] = (len(tmp_residue) == 0)
            else:
                out["zip_hash_match"] = True
                out["no_tmp_residue"] = True
        else:
            out["zip_hash_match"] = False
            out["no_tmp_residue"] = True
            out["last_build_schema_ok"] = False
    except Exception:
        # Ignore SoT extras if unavailable
        pass

    # Hardened gates: require last-build minimal schema and zip parity
    try:
        if not out.get("last_build_schema_ok", True):
            fail = True
        if not out.get("zip_hash_match", True):
            fail = True
    except Exception:
        pass

    print(json.dumps(out, indent=2))
    # Ensure single-line success marker for CI (stderr) when gates pass
    if not fail:
        try:
            h = calc_hash or "n/a"
            print(f"✅ contract-validate: OK (hash={h})", file=sys.stderr)
        except Exception:
            try:
                print("contract-validate: OK", file=sys.stderr)
            except Exception:
                pass
    return 0 if not fail else 3


if __name__ == "__main__":
    raise SystemExit(main())
