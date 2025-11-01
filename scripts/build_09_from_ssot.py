#!/usr/bin/env python3
from __future__ import annotations

import json
import difflib
from pathlib import Path


SSOT_PATH = Path('ref/intake/agent_profile.json')
CANON_09 = Path('canon/09_Agent-Manifests_Catalog_v2.json')
OUT_09 = Path('_generated/09_Agent-Manifests_Catalog_v2.json')
DIFF_09 = Path('_diffs/09_Agent-Manifests_Catalog_v2.diff')


def deep_sort(obj):
    if isinstance(obj, dict):
        return {k: deep_sort(obj[k]) for k in sorted(obj)}
    if isinstance(obj, list):
        return [deep_sort(x) for x in obj]
    return obj


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write('\n')


def read_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def unified(a: str, b: str, fa: str, fb: str) -> str:
    return ''.join(difflib.unified_diff(a.splitlines(True), b.splitlines(True), fa, fb))


def main() -> int:
    ssot = read_json(SSOT_PATH)
    owners = ssot.get('identity', {}).get('owners') or []
    agent = ssot.get('agent', {})
    agent_id = agent.get('agent_id')
    display = agent.get('display_name') or 'Turkey R&D Agent'
    obs_id = (ssot.get('observability', {}).get('channels') or [{}])[0].get('id') or 'agentops://turkey-rnd-001'
    out_paths = (ssot.get('packaging', {}) or {}).get('output_paths') or {}
    governance = ssot.get('governance_eval', {})
    provenance = ssot.get('provenance', {})

    payload = {
        'meta': {
            'name': '09_Agent-Manifests_Catalog',
            'version': 'v2.0.1',
            'owner': 'CAIO+CPA',
            'created_at': '1970-01-01T00:00:00Z',
        },
        'objective': 'Catalog of agent manifests (GEN2.1) for Turkey R&D.',
        'policy': {
            'governance_file': out_paths.get('governance', '04_Governance+Risk-Register_v2.json'),
            'global_instructions': '02_Global-Instructions_v2.json',
            'operating_rules': '03_Operating-Rules_v2.json',
            'memory_schema': '08_Memory-Schema_v2.json',
            'prompt_pack': out_paths.get('prompts', '10_Prompt-Pack_v2.json'),
            'workflow_pack': out_paths.get('workflows', '11_Workflow-Pack_v2.json'),
        },
        'agents': [
            {
                'agent_id': agent_id,
                'display_name': display,
                'status': 'staged',
                'owners': owners or ['CAIO', 'CPA', 'TeamLead'],
                'region': ['TR'],
                'languages': ['en'],
                'classification_default': governance.get('classification_default', 'confidential'),
                'telemetry_channel': obs_id,
                'paths': {
                    'prompt_pack': out_paths.get('prompts', '10_Prompt-Pack_v2.json'),
                    'workflow_pack': out_paths.get('workflows', '11_Workflow-Pack_v2.json'),
                    'tool_data_registry': '12_Tool+Data-Registry_v2.json',
                    'governance': out_paths.get('governance', '04_Governance+Risk-Register_v2.json'),
                    'kpi_eval': out_paths.get('kpi', '14_KPI+Evaluation-Framework_v2.json'),
                    'observability': out_paths.get('observability', '15_Observability+Telemetry_Spec_v2.json'),
                },
                'capabilities': [
                    'research', 'experiment_design', 'data_analysis', 'reporting'
                ],
                'routing': {
                    'default_onboard': 'WF_Onboarding_TurkeyRnD_v1'
                },
                'provenance': {
                    'attribution_policy': provenance.get('attribution_policy', 'inspired-by'),
                    'no_impersonation': bool(provenance.get('no_impersonation', True)),
                }
            }
        ]
    }

    payload = deep_sort(payload)
    # Write file and diff against canon
    OUT_09.parent.mkdir(parents=True, exist_ok=True)
    canon_text = CANON_09.read_text(encoding='utf-8')
    write_json(OUT_09, payload)
    out_text = OUT_09.read_text(encoding='utf-8')
    DIFF_09.parent.mkdir(parents=True, exist_ok=True)
    DIFF_09.write_text(unified(canon_text, out_text, str(CANON_09), str(OUT_09)), encoding='utf-8')

    print(json.dumps({'file': str(OUT_09), 'agent_id': agent_id, 'owners': owners, 'telemetry_channel': obs_id}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

