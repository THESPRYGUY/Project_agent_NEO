#!/usr/bin/env python3
from __future__ import annotations

import json
import difflib
from pathlib import Path


SSOT = Path('ref/intake/agent_profile.json')
CANON = Path('canon/06_Role-Recipes_Index_v2.json')
OUT = Path('_generated/06_Role-Recipes_Index_v2.json')
DIFF = Path('_diffs/06_Role-Recipes_Index_v2.diff')


def deep_sort(obj):
    if isinstance(obj, dict):
        return {k: deep_sort(v) for k, v in sorted(obj.items())}
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
    slug = (ssot.get('agent', {}).get('slug') or 'turkey-rnd').upper().replace('-', '_')
    primary_code = f'{slug}_LEAD'

    out = json.loads(json.dumps(base))
    out.setdefault('meta', {})
    out['meta']['agent_id'] = agent_id

    # Inject primary_role block (non-breaking payload add)
    out['primary_role'] = {
        'code': primary_code,
        'title': 'Turkey R&D Lead',
        'persona': (ssot.get('persona') or {}).get('agent', {}).get('code', 'ENTJ'),
        'naics_code': '112330'
    }

    # Ensure objectives contain required entries (without removing canon)
    obj = list(out.get('objectives') or [])
    req = ['Food Safety', 'Process Optimization', 'Welfare/Performance']
    for r in req:
        if r not in obj:
            obj.append(r)
    out['objectives'] = obj

    # pack_links (for 10/11/08)
    out['pack_links'] = {
        'prompt_pack': '10_Prompt-Pack_v2.json',
        'workflow_pack': '11_Workflow-Pack_v2.json',
        'memory_schema': '08_Memory-Schema_v2.json',
    }

    # Required top-level keys per contract
    out.setdefault('roles_index', {
        'primary_role_code': primary_code,
        'roles': [primary_code]
    })
    out.setdefault('mapping', {
        'agent_id': agent_id,
        'primary_role_code': primary_code
    })
    out.setdefault('definition_of_done', [
        'Primary role defined and linked',
        'Pack links to 10/11/08 present',
        'Objectives include food safety/process/welfare'
    ])

    out = deep_sort(out)
    canon_text = CANON.read_text(encoding='utf-8')
    write_json(OUT, out)
    out_text = OUT.read_text(encoding='utf-8')
    DIFF.parent.mkdir(parents=True, exist_ok=True)
    DIFF.write_text(uni(canon_text, out_text, str(CANON), str(OUT)), encoding='utf-8')
    print(json.dumps({'file': str(OUT), 'primary_role_code': primary_code}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
