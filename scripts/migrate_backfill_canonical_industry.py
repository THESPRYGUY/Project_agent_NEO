import json
import pathlib

ROOT = pathlib.Path('.').resolve()
TARGET = list(ROOT.rglob('*/19_Overlay-Pack_SME-Domain_v1.json'))


def canonical_from_naics(naics):
    if not isinstance(naics, dict):
        naics = {}
    lineage = naics.get('lineage', []) or []
    for node in lineage:
        level = str(node.get('level', '')).lstrip('0')
        if level == '2' and node.get('title'):
            return node['title']
    return naics.get('title') or 'Unknown'


def needs_fix(data):
    industry = str((data.get('industry') or '')).strip().lower()
    return (not industry) or industry.startswith('turkey production r&d')


def run():
    touched = 0
    for path in TARGET:
        try:
            payload = json.loads(path.read_text(encoding='utf-8'))
        except Exception as exc:
            print(f"[WARN] skip {path}: {exc}")
            continue
        naics = payload.get('naics', {}) or {}
        canonical = payload.get('canonical_industry')
        if not canonical:
            canonical = canonical_from_naics(naics)
            payload['canonical_industry'] = canonical
        if needs_fix(payload):
            payload['industry'] = canonical
            payload['industry_source'] = 'naics_lineage'
        else:
            payload['industry_source'] = payload.get('industry_source') or (
                'manual' if str(payload.get('industry') or '').strip() else 'naics_lineage'
            )
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        touched += 1
        print(f"[FIXED] {path}")
    print(f"[DONE] files updated: {touched}")


if __name__ == '__main__':
    run()
