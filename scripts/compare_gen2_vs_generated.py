#!/usr/bin/env python3
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import zipfile
from typing import Any, Dict, List, Tuple


BLANK_PAT = re.compile(r"\b(TBD|TODO|\?\?\?)\b", re.IGNORECASE)


def read_json_from_zip(zpath: str, filename: str) -> Tuple[Dict[str, Any], str]:
    """Return (obj, member_name) for the first member whose name endswith filename."""
    with zipfile.ZipFile(zpath, "r") as zf:
        # greedy match: prefer exact root match; otherwise search anywhere
        candidates = []
        for n in zf.namelist():
            if n.endswith(filename):
                candidates.append(n)
        if not candidates:
            raise FileNotFoundError(f"{filename!r} not found in {zpath}")
        # Prefer shallowest path
        member = sorted(candidates, key=lambda s: s.count('/'))[0]
        raw = zf.read(member)
    # tolerant UTF-8
    try:
        txt = raw.decode("utf-8")
    except Exception:
        txt = raw.decode("utf-8", errors="replace")
    try:
        obj = json.loads(txt)
    except Exception as exc:
        raise ValueError(f"Invalid JSON in {zpath}:{member}: {exc}")
    if not isinstance(obj, dict):
        raise TypeError(f"Top-level JSON must be an object in {member}")
    return obj, member


def is_blank(value: Any) -> bool:
    if value is None:
        return True
    if value == "":
        return True
    if isinstance(value, (list, dict)) and len(value) == 0:
        return True
    if isinstance(value, str) and BLANK_PAT.search(value or ""):
        return True
    return False


def top_level_report(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    ak, bk = set(a.keys()), set(b.keys())
    shared = sorted(ak & bk)
    only_a = sorted(ak - bk)
    only_b = sorted(bk - ak)
    blanks_a = sorted([k for k in ak if is_blank(a.get(k))])
    blanks_b = sorted([k for k in bk if is_blank(b.get(k))])
    side_by_side: List[Tuple[str, Any, Any]] = []
    for k in shared:
        side_by_side.append((k, a.get(k), b.get(k)))
    return {
        "shared_keys": shared,
        "only_in_gen2": only_a,
        "only_in_agent": only_b,
        "blanks_gen2": blanks_a,
        "blanks_agent": blanks_b,
        "pairs": side_by_side,
    }


def list_pack_names(zpath: str) -> List[str]:
    with zipfile.ZipFile(zpath, "r") as zf:
        names = [n.split('/')[-1] for n in zf.namelist() if n.endswith('.json')]
    # Canonical pack names typically start with two digits and underscore
    names = [n for n in names if re.match(r"^\d{2}_", n)]
    return sorted(list(dict.fromkeys(names)))


def main(argv: List[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Compare a GEN2 archetype ZIP vs a generated agent ZIP for one pack file.")
    p.add_argument("--gen2", required=True, help="Path to GEN2 master scaffold zip")
    p.add_argument("--agent", required=True, help="Path to generated agent repo zip")
    p.add_argument("--file", required=True, help="Filename to compare (e.g., 02_Global-Instructions_v2.json)")
    args = p.parse_args(argv)

    gen2_list = list_pack_names(args.gen2)
    agent_list = list_pack_names(args.agent)
    both = sorted(list(set(gen2_list) & set(agent_list)))

    try:
        a_obj, a_member = read_json_from_zip(args.gen2, args.file)
        b_obj, b_member = read_json_from_zip(args.agent, args.file)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    rep = top_level_report(a_obj, b_obj)

    def _safe(v: Any) -> str:
        try:
            return json.dumps(v, ensure_ascii=False)
        except Exception:
            return str(v)

    out = io.StringIO()
    out.write(f"Files in both zips ({len(both)}):\n")
    out.write("\n".join(both) + "\n\n")
    out.write(f"Comparing: GEN2:{a_member} \n           AGENT:{b_member}\n\n")
    out.write("Top-level keys: shared=\n")
    out.write(", ".join(rep["shared_keys"]) + "\n\n")
    if rep["only_in_gen2"]:
        out.write("Only in GEN2:\n- " + "\n- ".join(rep["only_in_gen2"]) + "\n\n")
    if rep["only_in_agent"]:
        out.write("Only in AGENT:\n- " + "\n- ".join(rep["only_in_agent"]) + "\n\n")
    if rep["blanks_gen2"] or rep["blanks_agent"]:
        out.write("Blanks — GEN2: " + ", ".join(rep["blanks_gen2"]) + "; AGENT: " + ", ".join(rep["blanks_agent"]) + "\n\n")
    out.write("Side-by-side (shared keys):\n")
    for k, av, bv in rep["pairs"]:
        avs = _safe(av)
        bvs = _safe(bv)
        mark_a = " [BLANK]" if is_blank(av) else ""
        mark_b = " [BLANK]" if is_blank(bv) else ""
        out.write(f"- {k}:\n    GEN2 : {avs}{mark_a}\n    AGENT: {bvs}{mark_b}\n")

    print(out.getvalue())
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

