import json, os
from pathlib import Path
from build_repo import build_repo
from neo_build.scaffolder import get_contract_mode

print('MODE at import', get_contract_mode())

tmp = Path('_tmp_build2').resolve()
tmp.mkdir(parents=True, exist_ok=True)
intake = tmp / 'intake.json'
profile = {"identity":{"agent_id":"atlas"},"agent":{"name":"Atlas","version":"1.0.0"}}
intake.write_text(json.dumps(profile), encoding='utf-8')
out = tmp / 'out'
os.environ['NEO_CONTRACT_MODE'] = 'full'
print('MODE before build', get_contract_mode())
rc = build_repo(intake, out, extend=True, strict=False, verbose=False, force_utf8=True, emit_parity=True)
print('MODE after build', get_contract_mode())
slug = 'atlas-1-0-0'
repo = out/slug
print('Exists', repo.exists())
import json as _j
print('Has 18 outputs?', 'outputs' in _j.loads((repo/'18_Reporting-Pack_v2.json').read_text()))
print('Has 13 chunking?', 'chunking' in _j.loads((repo/'13_Knowledge-Graph+RAG_Config_v2.json').read_text()))
print('Has 11 rollback?', 'rollback' in _j.loads((repo/'11_Workflow-Pack_v2.json').read_text()))
