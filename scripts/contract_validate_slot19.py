import json
import pathlib
import sys

from jsonschema import Draft202012Validator

REPO = pathlib.Path('.')
SCHEMA_PATH = REPO / 'packs' / '19_Overlay-Pack_SME-Domain_v1.schema.json'


def main() -> int:
    if not SCHEMA_PATH.exists():
        print(f"ERROR: slot-19 schema not found at {SCHEMA_PATH}", file=sys.stderr)
        return 2

    schema = json.loads(SCHEMA_PATH.read_text(encoding='utf-8'))
    validator = Draft202012Validator(schema)

    candidates = list(
        REPO.glob('fixtures/expected_pack_golden/19_Overlay-Pack_SME-Domain_v1.json')
    ) + list(REPO.glob('generated_repos/**/19_Overlay-Pack_SME-Domain_v1.json'))

    if not candidates:
        print('WARN: No slot-19 overlays found to validate; passing empty set.')
        return 0

    errors = []
    for file_path in candidates:
        try:
            data = json.loads(file_path.read_text(encoding='utf-8'))
        except Exception as exc:  # pragma: no cover - guardrail only
            errors.append((file_path, f'JSON parse error: {exc}'))
            continue
        for err in validator.iter_errors(data):
            errors.append((file_path, err.message))

    if errors:
        print('Contract validation FAILED:')
        for file_path, message in errors:
            print(f" - {file_path}: {message}")
        return 1

    print(f'Contract validation passed on {len(candidates)} file(s).')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
