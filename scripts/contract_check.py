#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict


def main(argv: list[str] | None = None) -> int:
    argv = list(argv or sys.argv[1:])
    if not argv:
        print("Usage: python scripts/contract_check.py <pack_dir>", file=sys.stderr)
        return 2
    try:
        # Lazy imports so we can return structured JSON even if project imports fail
        from neo_build.contracts import CANONICAL_PACK_FILENAMES  # type: ignore
        from neo_build.schemas import required_keys_map  # type: ignore
        root = Path(argv[0])
        req = required_keys_map()
        missing: Dict[str, list[str]] = {}
        for fname in CANONICAL_PACK_FILENAMES:
            path = root / fname
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                missing[fname] = list(req.get(fname, []))
                continue
            present = set(data.keys()) if isinstance(data, dict) else set()
            need = [k for k in req.get(fname, []) if k not in present]
            if need:
                missing[fname] = need

        ok = len(missing) == 0
        print(json.dumps({"contract_ok": ok, "missing_keys": missing}, indent=2))
        return 0 if ok else 3
    except Exception as e:  # pragma: no cover - defensive fallback for CI
        print(json.dumps({"contract_ok": False, "missing_keys": {}, "error": str(e)}))
        return 3


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
