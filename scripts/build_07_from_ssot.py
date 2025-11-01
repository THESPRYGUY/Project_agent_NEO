#!/usr/bin/env python3
from __future__ import annotations

import json
import difflib
from pathlib import Path


SSOT = Path('ref/intake/agent_profile.json')
CANON = Path('canon/07_Subagent_Role-Recipes_v2.json')
OUT = Path('_generated/07_Subagent_Role-Recipes_v2.json')
DIFF = Path('_diffs/07_Subagent_Role-Recipes_v2.diff')


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
    slug = (ssot.get('agent', {}).get('slug') or 'turkey-rnd').upper().replace('-', '_')
    primary_code = f'{slug}_LEAD'

    out = json.loads(json.dumps(base))
    out.setdefault('meta', {})
    out['meta']['agent_id'] = agent_id
    out['persona'] = 'ENTJ'
    out['link_to_index'] = {'primary_role_code': primary_code}
    out['references'] = {
        'prompt_pack': '10_Prompt-Pack_v2.json',
        'workflow_pack': '11_Workflow-Pack_v2.json'
    }

    # Ensure Planner, Builder, Evaluator entries with IO summaries and token budgets
    archetypes = out.get('archetypes') or []
    def ensure_archetype(name: str, in_sum: str, out_sum: str):
        for a in archetypes:
            if str(a.get('id')) == name:
                io = a.setdefault('io', {})
                io.setdefault('input_schema', {})['summary'] = in_sum
                io.setdefault('output_contract', {})['summary'] = out_sum
                return
        archetypes.append({
            'id': name,
            'io': {
                'input_schema': {'summary': in_sum},
                'output_contract': {'summary': out_sum}
            }
        })

    ensure_archetype('Planner', 'Goal + constraints + SSOT context', 'Plan with hypotheses, endpoints, sampling, SOP refs')
    ensure_archetype('Builder', 'Approved plan + datasets + SOPs', 'Artifacts (prompts, pipelines, data packs) + checks')
    ensure_archetype('Evaluator', 'Artifacts + acceptance gates (PRI/HAL/AUD)', 'Validation report + pass/fail + rollback advice')
    out['archetypes'] = archetypes

    # Token budgets
    out['token_budgets'] = out.get('token_budgets') or {
        'planner': 4096,
        'builder': 8192,
        'evaluator': 4096,
    }

    # Required top-level 'recipes' (minimal, aligned to IO summaries)
    out['recipes'] = out.get('recipes') or [
        {
            'name': 'Planner',
            'io': {
                'input_schema': {'summary': 'Goal + constraints + SSOT context'},
                'output_contract': {'summary': 'Plan with hypotheses, endpoints, sampling, SOP refs'}
            }
        },
        {
            'name': 'Builder',
            'io': {
                'input_schema': {'summary': 'Approved plan + datasets + SOPs'},
                'output_contract': {'summary': 'Artifacts (prompts, pipelines, data packs) + checks'}
            }
        },
        {
            'name': 'Evaluator',
            'io': {
                'input_schema': {'summary': 'Artifacts + acceptance gates (PRI/HAL/AUD)'},
                'output_contract': {'summary': 'Validation report + pass/fail + rollback advice'}
            }
        }
    ]

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
