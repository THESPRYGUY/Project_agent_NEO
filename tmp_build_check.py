import json, os
from pathlib import Path
from build_repo import build_repo

tmp = Path('_tmp_build').resolve()
tmp.mkdir(parents=True, exist_ok=True)
intake = tmp / 'intake.json'
profile = {"identity":{"agent_id":"atlas"},"agent":{"name":"Atlas","version":"1.0.0"}}
intake.write_text(json.dumps(profile), encoding='utf-8')
out = tmp / 'out'
os.environ['NEO_CONTRACT_MODE'] = 'full'
rc = build_repo(intake, out, extend=True, strict=False, verbose=False, force_utf8=True, emit_parity=True)
print('RC', rc)
slug = 'atlas-1-0-0'
report_path = out / slug / 'INTEGRITY_REPORT.json'
print('REPORT_PATH', report_path.exists(), report_path)
print(report_path.read_text(encoding='utf-8'))
