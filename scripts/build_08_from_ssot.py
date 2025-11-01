#!/usr/bin/env python3
from __future__ import annotations

import json
import difflib
from pathlib import Path


SSOT = Path('ref/intake/agent_profile.json')
CANON = Path('canon/08_Memory-Schema_v2.json')
OUT = Path('_generated/08_Memory-Schema_v2.json')
DIFF = Path('_diffs/08_Memory-Schema_v2.diff')


def deep_sort(obj):
    if isinstance(obj, dict):
        return {k: deep_sort(obj[k]) for k in sorted(obj)}
    if isinstance(obj, list):
        return [deep_sort(x) for x in obj]
    return obj


def read_json(p: Path):
    return json.loads(p.read_text(encoding='utf-8'))


def write_json(p: Path, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write('\n')


def uni(a: str, b: str, fa: str, fb: str) -> str:
    return ''.join(difflib.unified_diff(a.splitlines(True), b.splitlines(True), fa, fb))


def main() -> int:
    ssot = read_json(SSOT)
    base = read_json(CANON)
    agent_id = ssot.get('agent', {}).get('agent_id')
    seeds = (ssot.get('memory') or {}).get('initial_memory_packs') or []

    out = json.loads(json.dumps(base))
    out.setdefault('meta', {})
    out['meta']['agent_id'] = agent_id

    # Packs initial seeds from SSOT
    packs = out.get('packs') or {}
    packs['initial'] = seeds
    out['packs'] = packs

    # Scopes, pii_redaction, sync_allowlist, retrieval defaults
    out['scopes'] = ["semantic", "procedural", "episodic"]
    out['pii_redaction'] = {'strategy': 'hash+mask'}
    out['sync_allowlist'] = ["prompts", "workflows", "kpi_reports"]
    out['retrieval'] = out.get('retrieval') or {}
    out['retrieval']['defaults'] = {
        'top_k': 8,
        'reranker': 'simple',
        'freshness_days': 365,
    }

    # Required top-level keys per contract
    out.setdefault('storage', {
        'engine': 'filesystem',
        'root': '/memory'
    })
    out.setdefault('redaction', {
        'policies': ['mask_names', 'hash_ids']
    })
    out.setdefault('sync', {
        'policy': 'conservative',
        'allowlist': ["prompts", "workflows", "kpi_reports"]
    })

    out = deep_sort(out)
    canon_text = CANON.read_text(encoding='utf-8')
    write_json(OUT, out)
    out_text = OUT.read_text(encoding='utf-8')
    DIFF.parent.mkdir(parents=True, exist_ok=True)
    DIFF.write_text(uni(canon_text, out_text, str(CANON), str(OUT)), encoding='utf-8')
    print(json.dumps({'file': str(OUT), 'seeds_count': len(seeds)}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
