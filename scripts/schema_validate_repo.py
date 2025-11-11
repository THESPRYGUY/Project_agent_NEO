import json
import pathlib
import sys
from jsonschema import Draft202012Validator

repo = pathlib.Path('.')
errors = 0

def validate(schema_path: pathlib.Path, targets: list[str]) -> None:
    global errors
    if not schema_path.exists():
        print(f'SCHEMA MISSING: {schema_path}', file=sys.stderr)
        errors += 1
        return
    schema = json.loads(schema_path.read_text(encoding='utf-8'))
    validator = Draft202012Validator(schema)
    for target in targets:
        tp = repo / target
        if not tp.exists():
            continue
        try:
            data = json.loads(tp.read_text(encoding='utf-8'))
        except Exception as exc:
            print(f'JSON ERROR: {target}: {exc}', file=sys.stderr)
            errors += 1
            continue
        issues = list(validator.iter_errors(data))
        if issues:
            print(f'SCHEMA FAIL: {target}')
            for issue in issues[:5]:
                print(' -', issue.message)
            errors += 1

schemas = {
    repo / 'packs' / '19_Overlay-Pack_SME-Domain_v1.schema.json': [
        'fixtures/expected_pack_golden/19_Overlay-Pack_SME-Domain_v1.json',
        *[str(p.relative_to(repo)) for p in repo.glob('generated_repos/**/19_Overlay-Pack_SME-Domain_v1.json')]
    ]
}

for schema_path, targets in schemas.items():
    validate(schema_path, targets)

if errors:
    print(f'Schema validation found {errors} issue(s).', file=sys.stderr)
    sys.exit(1)
print('Schema validation passed.')
