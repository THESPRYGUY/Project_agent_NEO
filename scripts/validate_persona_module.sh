#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
JEST_ARGS=("$@")

if [[ ${#JEST_ARGS[@]} -eq 0 ]]; then
  JEST_ARGS=(tests/js/persona_math.spec.ts tests/js/suggester.spec.ts)
fi

cd "$ROOT"

if [[ ! -f package-lock.json ]]; then
  echo "package-lock.json not found; run 'npm install' once before using the validator."
fi

npm run build
npm test -- --runInBand "${JEST_ARGS[@]}"
pytest -q tests/py/test_envelope_persona.py

echo "Persona module validation complete."
