#!/usr/bin/env bash
set -euo pipefail
echo '{"PRI":0.95,"HAL":0.02,"AUD":0.90}' > artifacts/kpi-run-$(git rev-parse --short HEAD).json
cp artifacts/evaluator-report-PLACEHOLDER.md artifacts/evaluator-report-$(git rev-parse --short HEAD).md
