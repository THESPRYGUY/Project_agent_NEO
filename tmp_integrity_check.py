import json, os
from pathlib import Path
from neo_build.writers import write_repo_files
from neo_build.validators import integrity_report

os.environ['NEO_CONTRACT_MODE'] = 'full'
profile = {"identity":{"agent_id":"atlas"},"agent":{"name":"Atlas","version":"1.0.0"}}
root = Path('_tmp_build4').resolve()
root.mkdir(parents=True, exist_ok=True)
packs = write_repo_files(profile, root)
rep = integrity_report(profile, packs)
print(json.dumps(rep, indent=2))
