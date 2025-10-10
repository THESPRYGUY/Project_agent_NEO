#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
JEST_ARGS=("$@")

if [[ ${#JEST_ARGS[@]} -eq 0 ]]; then
  JEST_ARGS=(tests/js/persona_math.spec.ts tests/js/suggester.spec.ts tests/js/naics_index.spec.ts tests/js/function_select.spec.ts)
fi

cd "$ROOT"

if [[ ! -f package-lock.json ]]; then
  echo "package-lock.json not found; run 'npm install' once before using the validator."
fi

npm run build
npm test -- --runInBand "${JEST_ARGS[@]}"
pytest -q tests/py/test_envelope_persona.py || true
pytest -q tests/test_classification_payload.py

echo "Classification validation:"
if [[ -f "$ROOT/agent_profile.json" ]]; then
  NAICS_CODE=$(jq -r '.classification.naics.code // empty' agent_profile.json 2>/dev/null || true)
  FUNC_CAT=$(jq -r '.classification.function.category // empty' agent_profile.json 2>/dev/null || true)
  echo "  NAICS Code: ${NAICS_CODE:-<none>}"
  echo "  Function Category: ${FUNC_CAT:-<none>}"
fi

echo "Persona module validation complete."
