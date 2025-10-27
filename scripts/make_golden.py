#!/usr/bin/env python3
"""
Rebuild the v3 golden snapshot from fixtures/intake_v3_golden.json and
overwrite fixtures/expected_pack_golden/* with the current deterministic output.

Usage:
  python scripts/make_golden.py

Not used in CI. Intended for intentional re-baselines only.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path


def _ensure_import_path() -> None:
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


def _norm(s: str) -> str:
    return s.replace("\r\n", "\n")


def main() -> int:
    _ensure_import_path()
    from neo_build.contracts import CANONICAL_PACK_FILENAMES
    from neo_build.writers import write_repo_files

    root = Path.cwd()
    fixture = root / "fixtures" / "intake_v3_golden.json"
    outdir = root / ".pytest-tmp" / "golden_update"
    repo_dir = outdir / "golden-agent-3-0-0"
    dest = root / "fixtures" / "expected_pack_golden"

    outdir.mkdir(parents=True, exist_ok=True)
    repo_dir.mkdir(parents=True, exist_ok=True)
    dest.mkdir(parents=True, exist_ok=True)

    profile = json.loads(fixture.read_text(encoding="utf-8"))
    write_repo_files(profile, repo_dir)

    changed: list[str] = []
    for name in CANONICAL_PACK_FILENAMES:
        src_path = repo_dir / name
        dst_path = dest / name
        src_text = _norm(src_path.read_text(encoding="utf-8"))
        existing = _norm(dst_path.read_text(encoding="utf-8")) if dst_path.exists() else None
        if existing != src_text:
            changed.append(name)
        # Always overwrite
        dst_path.write_text(src_text, encoding="utf-8", newline="\n")

    print("GOLDEN UPDATED")
    if changed:
        for n in changed:
            print(f" - {n}")
    else:
        print("(no changes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

