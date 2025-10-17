"""Quick probe for NAICS dataset via IntakeApplication internals.

Run:
  python scripts/probe_naics.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from neo_agent.intake_app import IntakeApplication


def main() -> int:
    app = IntakeApplication(base_dir=Path("."))
    total = app.reload_naics()
    print(f"Loaded entries: {total}")
    # Counts per level
    from collections import Counter
    levels = Counter(int(e.get("level", 0) or 0) for e in app._load_naics_reference())
    print("Per-level counts:", dict(sorted(levels.items())))
    roots = app._naics_children("", None)  # there is no empty parent; find level 2 explicitly
    # more reliable: list level 2 entries directly
    entries = app._load_naics_reference()
    level2 = sorted([e for e in entries if int(e.get("level", 0)) == 2], key=lambda x: x.get("code", ""))
    print(f"Level-2 roots: {len(level2)} (expected > 0)")
    ch_541_lv4 = app._naics_children("541", 4)
    ch_541_lv5 = app._naics_children("541", 5)
    print(f"Children of 541 at level 4: {len(ch_541_lv4)} (expected > 0)")
    print(f"Children of 541 at level 5: {len(ch_541_lv5)} (expected > 0)")
    srch_54 = app._naics_search("54")
    print(f"Search '54' results: {len(srch_54)} (expected > 0)")
    if level2 and ch_541_lv4:
        print("Sample:")
        print("  root:", level2[0])
        print("  541->lv4[0]:", ch_541_lv4[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
