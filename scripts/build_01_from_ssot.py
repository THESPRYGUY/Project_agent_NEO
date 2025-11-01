import json, os
SRC_SSOT='ref/intake/agent_profile.json'
TEMPLATE='canon/01_README+Directory-Map_v2.json'
OUT='_generated/01_README+Directory-Map_v2.json'
DIFF='_diffs/01_README+Directory-Map_v2.diff'
FIXED_TS='1970-01-01T00:00:00Z'; STABLE_SEED=1337

def deep_sort(obj):
    if isinstance(obj, dict):
        return {k: deep_sort(obj[k]) for k in sorted(obj)}
    if isinstance(obj, list):
        return [deep_sort(x) for x in obj]
    return obj

def main():
    with open(SRC_SSOT,'r',encoding='utf-8') as f: ssot=json.load(f)
    with open(TEMPLATE,'r',encoding='utf-8') as f: canon=json.load(f)
    canon.setdefault('meta',{})['agent_id']=ssot['agent']['agent_id']
    canon['meta']['timestamp']=FIXED_TS
    canon['meta']['stable_seed']=STABLE_SEED
    out=deep_sort(canon)
    os.makedirs(os.path.dirname(OUT),exist_ok=True)
    cur=json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)
    with open(OUT,'w',encoding='utf-8') as f: f.write(cur)
    os.makedirs(os.path.dirname(DIFF),exist_ok=True)
    with open(DIFF,'w',encoding='utf-8') as f: f.write('')
    print(f'Wrote {OUT} ({len(cur)} bytes)')
if __name__=='__main__':
    main()

