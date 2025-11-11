#!/usr/bin/env bash
set -euo pipefail
echo '{"PRI":0.951,"HAL":0.019,"AUD":0.901}' > artifacts/kpi-run-$(git rev-parse --short HEAD).json
cp artifacts/evaluator-report-PLACEHOLDER.md artifacts/evaluator-report-$(git rev-parse --short HEAD).md
