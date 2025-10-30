#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
import hashlib
import io
import zipfile
import hashlib
import io
import zipfile
from typing import Any, Dict


def _load_pack_dir(path: Path) -> Dict[str, Any]:
    packs: Dict[str, Any] = {}
    for p in path.iterdir():
        if p.suffix == ".json" and p.name != "contract_report.json":
            try:
                packs[p.name] = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                # treat unreadable files as missing content; validator will mark keys missing
                packs.setdefault(p.name, {})
    return packs


def main(argv: list[str] | None = None) -> int:
    argv = list(argv or sys.argv[1:])
    if not argv:
        print("Usage: python scripts/contract_validate.py <pack_dir>", file=sys.stderr)
        return 2

    pack_dir = Path(argv[0])
    if not pack_dir.exists() or not pack_dir.is_dir():
        print(json.dumps({"error": f"pack_dir not found: {pack_dir}"}))
        return 2

    # Ensure `src/` is importable similar to other CLI helpers
    root = Path(__file__).resolve().parents[1]
    src = root / "src"
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))

    # Lazy imports to avoid import errors masking JSON output
    from neo_build.validators import integrity_report  # type: ignore
    from neo_build.contracts import CANONICAL_PACK_FILENAMES  # type: ignore

    # Load only canonical 20 files for report
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
    try:
        # pack_dir expected as .../_generated/<AGENT_ID>/<TS>
        outdir = pack_dir
        out_root = outdir.parents[1]
        last_path = out_root / "_last_build.json"
        if last_path.exists():
            last = json.loads(last_path.read_text(encoding="utf-8"))
            stored_hash = str(last.get("zip_hash") or "")
            # Build canonical zip bytes (fixed date_time)
            excluded_names = {"_last_build.json", ".DS_Store"}
            excluded_dirs = {"__pycache__", ".pytest_cache", ".git"}
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
            # tmp residue check under _generated/<AGENT_ID>/.tmp
            tmp_dir = out_root / outdir.parent.name / ".tmp"
            tmp_residue = [p for p in tmp_dir.glob("*") if p.exists()] if tmp_dir.exists() else []
            out["zip_hash_match"] = (stored_hash and stored_hash == calc_hash)
            out["no_tmp_residue"] = (len(tmp_residue) == 0)
        else:
            out["zip_hash_match"] = False
            out["no_tmp_residue"] = True
    except Exception:
        # Ignore SoT extras if unavailable
        pass

    print(json.dumps(out, indent=2))
    if not fail and out.get("zip_hash_match") and out.get("no_tmp_residue"):
        # Emit a concise success line for CI summaries
        try:
            print(f"✅ contract-validate: OK (hash={calc_hash})", file=sys.stderr)
        except Exception:
            pass
    # Ensure single-line success marker for CI
    if not fail and out.get("zip_hash_match") and out.get("no_tmp_residue"):
        try:
            print(f"✅ contract-validate: OK (hash={calc_hash})", file=sys.stderr)
        except Exception:
            pass
    return 0 if not fail else 3


if __name__ == "__main__":
    raise SystemExit(main())
