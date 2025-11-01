#!/usr/bin/env python3
from __future__ import annotations

import json
import difflib
from pathlib import Path


SSOT = Path('ref/intake/agent_profile.json')
CANON = Path('canon/03_Operating-Rules_v2.json')
OUT = Path('_generated/03_Operating-Rules_v2.json')
DIFF = Path('_diffs/03_Operating-Rules_v2.diff')


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


def ensure_role(roles: list[dict], name: str, perms: list[str]) -> None:
    for r in roles:
        if str(r.get('name')) == name:
            # extend perms minimally
            pset = set(r.get('permissions') or [])
            for p in perms:
                if p not in pset:
                    (r.setdefault('permissions', [])).append(p)
            return
    roles.append({'name': name, 'permissions': perms})


def main() -> int:
    ssot = read_json(SSOT)
    base = read_json(CANON)
    agent_id = ssot.get('agent', {}).get('agent_id')
    owners = ssot.get('identity', {}).get('owners') or []
    g = ssot.get('governance_eval') or {}
    channel = (ssot.get('observability', {}).get('channels') or [{}])[0].get('id') or 'agentops://turkey-rnd-001'

    out = json.loads(json.dumps(base))
    out.setdefault('meta', {})
    out['meta']['agent_id'] = agent_id

    # Stage default (non-breaking)
    out.setdefault('stage', {})
    out['stage'].setdefault('default', 'staging')

    # RBAC merge
    rbac = out.get('rbac') or {}
    roles = list(rbac.get('roles') or [])
    for owner in owners:
        perms = ['approve_policy'] if owner == 'CAIO' else ['escalate']
        ensure_role(roles, owner, perms)
    rbac['roles'] = roles
    out['rbac'] = rbac

    # Gates from SSOT
    ssot_gates = g.get('gates') or {}
    out.setdefault('gates', {})
    out['gates']['activation'] = {
        'PRI_min': ssot_gates.get('PRI_min', 0.95),
        'HAL_max': ssot_gates.get('hallucination_max', 0.02),
        'AUD_min': ssot_gates.get('audit_min', 0.9),
    }

    # Logging sink id
    out.setdefault('logging_audit', {})
    out['logging_audit']['sink_id'] = channel

    # Rollback rule
    out['rollback'] = {'on_gate_fail': True}

    # References
    out['references'] = {
        'governance': '04_Governance+Risk-Register_v2.json',
        'safety': '05_Safety+Privacy_Guardrails_v2.json',
        'observability': '15_Observability+Telemetry_Spec_v2.json',
        'kpi': '14_KPI+Evaluation-Framework_v2.json',
        'lifecycle': '17_Lifecycle-Pack_v2.json',
    }

    out = deep_sort(out)
    canon_text = CANON.read_text(encoding='utf-8')
    write_json(OUT, out)
    out_text = OUT.read_text(encoding='utf-8')
    DIFF.parent.mkdir(parents=True, exist_ok=True)
    DIFF.write_text(uni(canon_text, out_text, str(CANON), str(OUT)), encoding='utf-8')
    print(json.dumps({'file': str(OUT), 'agent_id': agent_id, 'sink_id': channel}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

