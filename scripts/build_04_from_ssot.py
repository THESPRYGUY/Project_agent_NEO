#!/usr/bin/env python3
from __future__ import annotations

import json
import difflib
from pathlib import Path


SSOT = Path('ref/intake/agent_profile.json')
CANON = Path('canon/04_Governance+Risk-Register_v2.json')
OUT = Path('_generated/04_Governance+Risk-Register_v2.json')
DIFF = Path('_diffs/04_Governance+Risk-Register_v2.diff')
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

    owners = ssot.get('identity', {}).get('owners') or []
    g = ssot.get('governance_eval') or {}
    tags = g.get('risk_register_tags') or [
        'prompt-injection', 'data-leakage', 'PII-exposure', 'model-drift'
    ]
    agent_id = ssot.get('agent', {}).get('agent_id')

    out = json.loads(json.dumps(base))
    out.setdefault('meta', {})
    out['meta']['agent_id'] = agent_id
    out['meta']['updated_at'] = FIXED_TS

    # Classification + impersonation
    # Keep canon structure: set under policy or top-level if present
    out.setdefault('policy', {})
    out['policy']['classification_default'] = g.get('classification_default', 'confidential')
    out['policy']['no_impersonation'] = True
    # Map gates
    gates = g.get('gates') or {}
    out['policy']['activation_gates'] = {
        'PRI_min': gates.get('PRI_min', 0.95),
        'hallucination_max': gates.get('hallucination_max', 0.02),
        'audit_min': gates.get('audit_min', 0.9),
    }

    # Risk register tags
    out['risk_register'] = {
        'tags': tags
    }

    # Approvals / change control / escalation
    out.setdefault('approvals', {})
    out['approvals']['approver_roles'] = owners
    # Change control approver
    approver = 'CAIO' if 'CAIO' in owners else (owners[0] if owners else 'Owner')
    out['change_control'] = {'approver': approver}
    # Escalation primary
    primary = 'TeamLead' if 'TeamLead' in owners else (owners[0] if owners else 'Owner')
    out['escalation'] = {'primary': primary}

    # References: ensure pointers exist and match expected pack names
    refs = out.get('references') or {}
    refs.update({
        'global_instructions': '02_Global-Instructions_v2.json',
        'safety_privacy': '05_Safety+Privacy_Guardrails_v2.json',
        'prompt_pack': '10_Prompt-Pack_v2.json',
        'workflow_pack': '11_Workflow-Pack_v2.json',
        'kpi_framework': '14_KPI+Evaluation-Framework_v2.json',
        'observability': '15_Observability+Telemetry_Spec_v2.json',
        'lifecycle_pack': '17_Lifecycle-Pack_v2.json',
    })
    out['references'] = refs

    # Required top-level keys per contract that may be absent in canon
    if not out.get('compliance_mapping'):
        out['compliance_mapping'] = {
            'policy_to_controls': [
                {'policy': 'privacy_by_design', 'controls': ['C-001', 'C-002']},
                {'policy': 'governance_by_design', 'controls': ['C-002']},
            ]
        }
    if not out.get('definition_of_done'):
        out['definition_of_done'] = [
            'Approvals configured (owners present)',
            'Activation gates set (PRI/HAL/AUD)',
            'Escalation primary assigned',
            'References to 02/05/10/11/14/15/17 valid'
        ]

    out = deep_sort(out)
    canon_text = CANON.read_text(encoding='utf-8')
    write_json(OUT, out)
    out_text = OUT.read_text(encoding='utf-8')
    DIFF.parent.mkdir(parents=True, exist_ok=True)
    DIFF.write_text(uni(canon_text, out_text, str(CANON), str(OUT)), encoding='utf-8')
    print(json.dumps({'file': str(OUT), 'agent_id': agent_id, 'owners': owners}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
