#!/usr/bin/env python3
"""
Build NAICS 2022 JSON from a 2–6 digit CSV.

Input CSV: data/naics/2-6 digit_2022_Codes.csv
- Expected columns (case-insensitive): Code, Title
- Ignores non-data rows or extra columns.

Output JSON: data/naics/naics_2022.json
- Array of objects: {
    "code": "541611",
    "title": "Administrative Management and General Management Consulting Services",
    "level": 6,
    "parents": [ { code, title, level }, ... ]
  }
- Parents include existing shorter prefixes (2-, 3-, 4-, 5-digit) where present in CSV.
- Sorted by code, pretty-printed (indent=2), UTF-8.

Run: python scripts/build_naics_json.py
"""
from __future__ import annotations
import csv
import json
import os
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "naics" / "2-6 digit_2022_Codes.csv"
OUT_PATH = ROOT / "data" / "naics" / "naics_2022.json"


def _normalize_header(h: str) -> str:
    return (h or "").strip().lower().replace("  ", " ").replace(" ", "_")


def load_naics_rows(csv_path: Path) -> Dict[str, Dict[str, str]]:
    """Load rows into a code->row map. Row contains 'code', 'title'.
    Skips blank/malformed codes.
    """
    code_map: Dict[str, Dict[str, str]] = {}
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        rows = list(reader)

    # Heuristically find columns: look for headers containing 'code' and 'title'.
    # Some files may have extra columns or empty rows at top.
    header_idx = None
    for i, row in enumerate(rows[:10]):
        joined = ",".join(row).strip().lower()
        if "code" in joined and "title" in joined:
            header_idx = i
            break
    # If not found, assume first non-empty row is header
    if header_idx is None:
        for i, row in enumerate(rows):
            if any(cell.strip() for cell in row):
                header_idx = i
                break

    if header_idx is None:
        raise RuntimeError("Could not locate header row in CSV")

    headers = [_normalize_header(h) for h in rows[header_idx]]
    # Identify column indices (fallbacks if not found)
    try:
        code_col = headers.index("2022_naics_us_code") if "2022_naics_us_code" in headers else headers.index("code")
    except ValueError:
        # Try to guess: pick first header containing 'code'
        code_col = next((i for i, h in enumerate(headers) if "code" in h), -1)
    try:
        title_col = headers.index("2022_naics_us_title") if "2022_naics_us_title" in headers else headers.index("title")
    except ValueError:
        title_col = next((i for i, h in enumerate(headers) if "title" in h), -1)

    if code_col < 0 or title_col < 0:
        raise RuntimeError(f"Could not detect Code/Title columns in headers: {headers}")

    for row in rows[header_idx + 1 :]:
        if not row or all((c or "").strip() == "" for c in row):
            continue
        # Guard against short rows
        if code_col >= len(row) or title_col >= len(row):
            continue
        raw_code = (row[code_col] or "").strip()
        raw_title = (row[title_col] or "").strip()
        # Filter to 2-6 digit numeric codes
        code = "".join(ch for ch in raw_code if ch.isdigit())
        if not (2 <= len(code) <= 6) or not code.isdigit():
            continue
        if not raw_title:
            continue
        title = raw_title
        # Deduplicate: last occurrence wins (but typically they’re identical)
        code_map[code] = {"code": code, "title": title}

    return code_map


essential_prefix_lengths = (2, 3, 4, 5)


def build_parents(code: str, code_map: Dict[str, Dict[str, str]]) -> List[Dict[str, str]]:
    parents: List[Dict[str, str]] = []
    for L in essential_prefix_lengths:
        if len(code) > L:
            p = code[:L]
            info = code_map.get(p)
            if info:
                parents.append({
                    "code": info["code"],
                    "title": info["title"],
                    "level": len(info["code"]),
                })
    # Ensure ascending by level
    parents.sort(key=lambda x: x["level"])  # 2 -> 5
    return parents


def build_output(code_map: Dict[str, Dict[str, str]]) -> List[Dict[str, object]]:
    out: List[Dict[str, object]] = []
    for code, info in code_map.items():
        level = len(code)
        item = {
            "code": code,
            "title": info["title"],
            "level": level,
            "parents": build_parents(code, code_map),
        }
        out.append(item)
    # Sort by code
    out.sort(key=lambda x: (len(x["code"]), x["code"]))
    return out


def main() -> int:
    if not CSV_PATH.exists():
        print(f"Input CSV not found: {CSV_PATH}")
        return 1
    code_map = load_naics_rows(CSV_PATH)
    if not code_map:
        print("No rows parsed from CSV; aborting.")
        return 1
    out = build_output(code_map)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"Wrote {len(out)} NAICS entries -> {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
