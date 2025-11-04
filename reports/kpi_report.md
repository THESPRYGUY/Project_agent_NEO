# KPI Report

Timestamp: 2025-11-04T23:43:54Z
Commit: 7f9ceb6b1c2a098d7b7aa5075d3ef391fe867b85
Version: 1.0.0

## KPI Snapshot
- PRI: value 0.95, target >=0.95, target-only
- HAL: value 0.02, target <=0.02, target-only
- AUD: value 0.9, target >=0.90, target-only

## Gates Overview
- activation: AUD_min=0.9, HAL_max=0.02, PRI_min=0.95
- change: allow_latency_increase_pct=10, no_severity_downgrade=true, require_regression=true
- workflow_targets: AUD_min=0.9, HAL_max=0.02, PRI_min=0.95
- global_go_live: AUD>=0.9, HAL<=0.02, PRI>=0.95

## Recent CI Runs (0)
none
