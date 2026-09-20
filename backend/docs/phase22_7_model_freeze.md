# Phase 22.7 Model Freeze Verification

Generated: 2026-09-20T11:54:22.499280+00:00

## Frozen models (must remain unchanged)

- calibration-v1.0.0
- tyre-v1.0.0 (tyre-calibration-v1.0.0)
- weather-v1.0.0
- racecontrol-v1.0.0
- strategy-v1.1.0
- setup-v1.0.0
- replay-v1.0.0
- counterfactual-v1.0.0
- raceengine-v1.2.0

Verification: dataset-manifest-v1.3 calibration_changed = false, simulation_behavior_changed = false
Races hash: 2cce529c (expected 2cce529c)
Results hash: 112c8475 (expected 112c8475)
Backbone unchanged from v1.1

## Evidence

- Registry calibration entries still present: ['calibration-v1.0.0', 'tyre-calibration-v1.0.0']
- No tyre/weather/strategy coefficients modified (checked via file mtime)
