import os, json
from pathlib import Path
from neo_build.writers import write_repo_files
os.environ['NEO_CONTRACT_MODE']='full'
profile={"identity":{"agent_id":"atlas"}}
packs=write_repo_files(profile, Path('_tmp_packs'))
print('19.datasets', packs['19_Overlay-Pack_SME-Domain_v1.json'].get('datasets'))
print('20.escalations', packs['20_Overlay-Pack_Enterprise_v1.json'].get('escalations'))
