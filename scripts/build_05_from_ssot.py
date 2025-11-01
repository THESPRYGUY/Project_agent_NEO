#!/usr/bin/env python3
from __future__ import annotations

import json
import difflib
from pathlib import Path


SSOT = Path('ref/intake/agent_profile.json')
CANON = Path('canon/05_Safety+Privacy_Guardrails_v2.json')
OUT = Path('_generated/05_Safety+Privacy_Guardrails_v2.json')
DIFF = Path('_diffs/05_Safety+Privacy_Guardrails_v2.diff')
FIXED_TS = '1970-01-01T00:00:00Z'


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
    obs = ssot.get('observability', {})
    channel_id = (obs.get('channels') or [{}])[0].get('id') or 'agentops://turkey-rnd-001'

    out = json.loads(json.dumps(base))
    out.setdefault('meta', {})
    out['meta']['agent_id'] = agent_id
    out['meta']['updated_at'] = '1970-01-01T00:00:00Z'

    # Refusal style
    out.setdefault('refusal_style', {})
    out['refusal_style']['default'] = 'brief, neutral, policy-backed; safer alternative'

    # Privacy / PII scrub alignment
    out.setdefault('privacy', {})
    out['privacy']['pii_scrub'] = True

    # Classification default
    out['classification_default'] = 'confidential'

    # Content filters: ensure critical toggles
    cf = out.get('content_filters') or {}
    actions = cf.get('actions') or {}
    actions['no_impersonation'] = True
    actions['sensitive_data_block'] = True
    cf['actions'] = actions
    out['content_filters'] = cf

    # References
    refs = out.get('references') or {}
    refs['governance'] = '04_Governance+Risk-Register_v2.json'
    out['references'] = refs

    # Required top-level keys per contract that may be absent; add minimal non-empty entries
    out.setdefault('operational_hooks', {
        'pre_task': ['apply_guardrails', 'set_observability_keys'],
        'post_task': ['redact_pii', 'store_footprints_summary']
    })
    out.setdefault('audit_checklist', [
        'No PII in logs', 'No raw chain-of-thought exposed', 'Gates enforced'
    ])

    out = deep_sort(out)

    canon_text = CANON.read_text(encoding='utf-8')
    write_json(OUT, out)
    out_text = OUT.read_text(encoding='utf-8')
    DIFF.parent.mkdir(parents=True, exist_ok=True)
    DIFF.write_text(uni(canon_text, out_text, str(CANON), str(OUT)), encoding='utf-8')
    print(json.dumps({'file': str(OUT), 'agent_id': agent_id, 'telemetry_channel': channel_id}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

