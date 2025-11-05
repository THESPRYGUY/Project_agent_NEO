# KPI Report

Timestamp: 2025-11-05T01:38:34Z
Commit: 6c588ee56535ded6a0d6595011965d99c214cb1c
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
