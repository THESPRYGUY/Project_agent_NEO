#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path


GEN = Path('_generated')
DIFFS = Path('_diffs')
ARCHIVE_ROOT = Path('_archive')
CANONICAL_ID = 'AGT-112330-TURKEY-RND-0001'

ALLOWED = [
    "01_README+Directory-Map_v2.json",
    "02_Global-Instructions_v2.json",
    "03_Operating-Rules_v2.json",
    "04_Governance+Risk-Register_v2.json",
    "05_Safety+Privacy_Guardrails_v2.json",
    "06_Role-Recipes_Index_v2.json",
    "07_Subagent_Role-Recipes_v2.json",
    "08_Memory-Schema_v2.json",
    "09_Agent-Manifests_Catalog_v2.json",
    "10_Prompt-Pack_v2.json",
    "11_Workflow-Pack_v2.json",
    "12_Tool+Data-Registry_v2.json",
    "13_Knowledge-Graph+RAG_Config_v2.json",
    "14_KPI+Evaluation-Framework_v2.json",
    "15_Observability+Telemetry_Spec_v2.json",
    "16_Reasoning-Footprints_Schema_v1.json",
    "17_Lifecycle-Pack_v2.json",
    "18_Reporting-Pack_v2.json",
    "19_Overlay-Pack_SME-Domain_v1.json",
    "20_Overlay-Pack_Enterprise_v1.json",
]


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def move_to_archive(archive: Path, path: Path) -> None:
    dst = archive / path.relative_to(Path('.'))
    ensure_dir(dst.parent)
    shutil.move(str(path), str(dst))


def main() -> int:
    ts = datetime.now().strftime('%Y%m%d_%H%M')
    archive = ARCHIVE_ROOT / f'legacy_{ts}'
    ensure_dir(archive)

    moved = 0
    kept = 0

    # 1) Move all non-allowed files in _generated
    if GEN.exists():
        for p in GEN.rglob('*'):
            if not p.is_file():
                continue
            # Only keep files directly under _generated with allowed names
            if p.parent.resolve() == GEN.resolve() and p.name in ALLOWED:
                # Check meta.agent_id or top-level agent_id if present
                try:
                    data = json.loads(p.read_text(encoding='utf-8'))
                    meta_id = (data.get('meta') or {}).get('agent_id')
                    top_id = data.get('agent_id')
                    check_id = meta_id or top_id
                    if check_id and str(check_id) != CANONICAL_ID:
                        move_to_archive(archive, p)
                        moved += 1
                    else:
                        kept += 1
                except Exception:
                    # If unreadable, quarantine
                    move_to_archive(archive, p)
                    moved += 1
            else:
                move_to_archive(archive, p)
                moved += 1

    # 2) Quarantine non-allowed diffs
    if DIFFS.exists():
        for p in DIFFS.rglob('*'):
            if not p.is_file():
                continue
            base = p.name
            # Accept diffs exactly named like '<allowed>.diff'
            allowed_diffs = {f"{name}.diff" for name in ALLOWED}
            if base not in allowed_diffs:
                move_to_archive(archive, p)
                moved += 1
            else:
                kept += 1

    print(json.dumps({
        'archive_dir': str(archive),
        'moved': moved,
        'kept': kept,
    }, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

