#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
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

    print(json.dumps(out, indent=2))
    return 0 if not fail else 3


if __name__ == "__main__":
    raise SystemExit(main())
