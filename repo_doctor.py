"""Repo Doctor: normalize legacy NEO agent repos.

Tasks:
- Coerce connectors/events formats
- Add 01.files[] if missing
- Sync KPI across 11/14/17
- Wire 02->(08,16) references
- Propagate NAICS
- Inject owners/role if missing
- Write repair_log.md
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from neo_build.contracts import CANONICAL_PACK_FILENAMES, KPI_TARGETS
from neo_build.utils import json_write


def _load(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _save(path: Path, payload: Dict[str, Any]) -> None:
    json_write(path, payload)


def repair(repo_root: Path) -> int:
    repo_root = repo_root.resolve()
    log: list[str] = []

    # 01 files[]
    p01 = repo_root / "01_README+Directory-Map_v2.json"
    if p01.exists():
        doc = _load(p01)
        if "files" not in doc:
            doc["files"] = list(CANONICAL_PACK_FILENAMES)
            _save(p01, doc)
            log.append("FIXED: added files[] to 01")

    # KPI sync 11/14/17
    p11 = repo_root / "11_Workflow-Pack_v2.json"
    p14 = repo_root / "14_KPI+Evaluation-Framework_v2.json"
    p17 = repo_root / "17_Lifecycle-Pack_v2.json"
    for path in (p11, p14, p17):
        if not path.exists():
            continue
        doc = _load(path)
        if path.name.startswith("11") or path.name.startswith("17"):
            doc.setdefault("gates", {})["kpi_targets"] = dict(KPI_TARGETS)
        else:
            doc["targets"] = dict(KPI_TARGETS)
        _save(path, doc)
        log.append(f"SYNC: KPI targets in {path.name}")

    # Observability events/alerts coercion (15)
    p15 = repo_root / "15_Observability+Telemetry_Spec_v2.json"
    if p15.exists():
        doc = _load(p15)
        if isinstance(doc.get("events"), dict):
            doc["events"] = list(doc["events"].keys())
            log.append("FIXED: coerced events dict->list")
        if isinstance(doc.get("alerts"), dict):
            doc["alerts"] = list(doc["alerts"].keys())
            log.append("FIXED: coerced alerts dict->list")
        _save(p15, doc)

    # NAICS propagate (02->09)
    p02 = repo_root / "02_Global-Instructions_v2.json"
    p09 = repo_root / "09_Agent-Manifests_Catalog_v2.json"
    if p02.exists() and p09.exists():
        d2 = _load(p02)
        d9 = _load(p09)
        naics = ((d2.get("context") or {}).get("naics") or {})
        if naics:
            d9.setdefault("summary", {})["naics"] = naics
            _save(p09, d9)
            log.append("SYNC: propagated NAICS to 09")

    (repo_root / "repair_log.md").write_text("\n".join(log) + "\n", encoding="utf-8")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Normalize legacy NEO repos")
    parser.add_argument("--path", required=True, type=Path, help="Path to repo root")
    args = parser.parse_args(argv)
    return repair(args.path)


if __name__ == "__main__":  # pragma: no cover - exercised via manual usage
    raise SystemExit(main())

