from neo_build.scaffolder import enrich_single
profile = {"identity":{"agent_id":"atlas"}}
out = enrich_single(profile, '20_Overlay-Pack_Enterprise_v1.json', {})
print(type(out.get('escalations')).__name__, out.get('escalations'))
