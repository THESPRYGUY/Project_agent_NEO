#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import difflib
from pathlib import Path


SSOT = Path('ref/intake/agent_profile.json')
CANON_02 = Path('canon/02_Global-Instructions_v2.json')
OUT_02 = Path('_generated/02_Global-Instructions_v2.json')
DIFF_02 = Path('_diffs/02_Global-Instructions_v2.diff')
TMP_DIR = Path('_tmp_validate_02')


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


def overlay_from_ssot(canon: dict, ssot: dict) -> dict:
    out = json.loads(json.dumps(canon))  # deep copy
    agent_id = ssot.get('agent', {}).get('agent_id')
    gates = (ssot.get('governance_eval') or {}).get('gates') or {}
    classification_default = (ssot.get('governance_eval') or {}).get('classification_default') or 'confidential'
    no_imp = bool((ssot.get('governance_eval') or {}).get('no_impersonation', True))
    channel = (ssot.get('observability', {}).get('channels') or [{}])[0].get('id') or 'agentops://turkey-rnd-001'
    mem_packs = (ssot.get('memory') or {}).get('initial_memory_packs') or []
    out_paths = (ssot.get('packaging') or {}).get('output_paths') or {}

    out.setdefault('meta', {})
    out['meta']['agent_id'] = agent_id
    out['meta']['naics_code'] = '112330'
    out['meta'].setdefault('locale', 'en-CA')

    # Persona + tone
    out['persona'] = {
        'profile': {'code': (ssot.get('persona') or {}).get('agent', {}).get('code', 'ENTJ')},
        'locked': True,
    }
    out.setdefault('tone', {})
    out['tone']['default'] = 'crisp, analytical, executive'

    # Governance/Evaluation
    out.setdefault('governance', {})
    out['governance']['classification_default'] = classification_default
    out['governance']['no_impersonation'] = no_imp
    out['evaluation'] = {'gates': gates}

    # Cross-pack references
    out['references'] = {
        'governance_pack': out_paths.get('governance', '04_Governance+Risk-Register_v2.json'),
        'safety_pack': '05_Safety+Privacy_Guardrails_v2.json',
        'memory_schema': '08_Memory-Schema_v2.json',
        'prompt_pack': out_paths.get('prompts', '10_Prompt-Pack_v2.json'),
        'workflow_pack': out_paths.get('workflows', '11_Workflow-Pack_v2.json'),
        'kpi_pack': out_paths.get('kpi', '14_KPI+Evaluation-Framework_v2.json'),
        'observability': out_paths.get('observability', '15_Observability+Telemetry_Spec_v2.json'),
        'lifecycle_pack': '17_Lifecycle-Pack_v2.json',
        'overlays': {
            'sme': '19_Overlay-Pack_SME-Domain_v1.json',
            'enterprise': '20_Overlay-Pack_Enterprise_v1.json',
        },
    }

    # Observability/default channel
    out.setdefault('observability', {})
    out['observability']['default_channel_id'] = channel

    # Memory defaults
    out.setdefault('memory', {})
    out['memory'].setdefault('defaults', {})
    out['memory']['defaults']['initial_packs'] = mem_packs

    return deep_sort(out)


def validate_with_canon_overlay(tmp_dir: Path) -> int:
    # Prepare temp dir with 20 files: 19 from canon + our 02
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    for p in Path('canon').glob('*.json'):
        shutil.copy2(p, tmp_dir / p.name)
    shutil.copy2(OUT_02, tmp_dir / '02_Global-Instructions_v2.json')
    import subprocess
    r = subprocess.run(['python', 'scripts/contract_validate.py', str(tmp_dir)], capture_output=True, text=True)
    print(r.stdout)
    if r.returncode == 0:
        print(r.stderr.strip())
    return r.returncode


def main() -> int:
    canon = read_json(CANON_02)
    ssot = read_json(SSOT)
    out = overlay_from_ssot(canon, ssot)
    # Write + diff
    canon_text = CANON_02.read_text(encoding='utf-8')
    write_json(OUT_02, out)
    out_text = OUT_02.read_text(encoding='utf-8')
    DIFF_02.parent.mkdir(parents=True, exist_ok=True)
    DIFF_02.write_text(uni(canon_text, out_text, str(CANON_02), str(OUT_02)), encoding='utf-8')

    # Validate
    rc = validate_with_canon_overlay(TMP_DIR)
    print(json.dumps({'validate_rc': rc}, indent=2))
    return rc


if __name__ == '__main__':
    raise SystemExit(main())

