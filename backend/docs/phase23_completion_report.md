# Phase 23 Completion Report

Generated: 2026-09-20T13:26:35.158802+00:00

## WHAT WAS CALIBRATED
- Lap-time baseline CALIBRATED, circuit/era CALIBRATED (hierarchical), pit total CALIBRATED (12147 obs)
- Tyre SOFT/MEDIUM/HARD LIMITED (fuel confounded, 2023+ only), driver/constructor/circuit LIMITED (shrinkage)
## WHAT WAS NOT CALIBRATED
- Fuel NON_IDENTIFIABLE, pit split NON_IDENTIFIABLE, setup NON_IDENTIFIABLE, strategy NON_IDENTIFIABLE, weather PRIOR_ONLY, race_control PRIOR_ONLY, historical tyre PRIOR_ONLY/NON_IDENTIFIABLE, sectors LIMITED
## WHY
- Evidence gates: insufficient observations, confounding, leakage risk, walk-forward no improvement, uncertainty high
## WHAT DATA SUPPORTED EACH DECISION
- Tyre: n_stints SOFT 913 MEDIUM 1823 HARD 1743 but lap-tyre join insufficient and fuel confounded -> LIMITED
- Pit: n=12147 total pit-loss -> CALIBRATED; split not separable -> NON_IDENTIFIABLE
- Fuel: exact load unavailable, progression slope -0.25798 not separable -> NON_IDENTIFIABLE
- Walk-forward: MAE 12.96 etc; ablation shows tyre hurts validation -> LIMITED
## WHAT REMAINS NON_IDENTIFIABLE
- fuel exact, pit split, setup, strategy, historical compounds, historical weather pre-2023, sector decomposition
## WHAT FAILED
- No calibration failed catastrophically; some candidates REJECTED/LIMITED due to validation
## WHAT IMPROVED
- Pit total calibrated with robust quantiles; circuit/era hierarchical model improves lap MAE modestly; baseline recalibrated on larger 552k laps
## WHAT DID NOT IMPROVE
- Tyre not promoted to CALIBRATED (needs lap-tyre age join and fuel separation); driver/constructor not promoted over v1.0.0 (shrinkage LIMITED)
## EVIDENCE TIERS SUMMARY
- circuit: LIMITED
- constructor: LIMITED
- driver: LIMITED
- era: CALIBRATED
- fuel: NON_IDENTIFIABLE
- lap_time_baseline: CALIBRATED
- pit_split: NON_IDENTIFIABLE
- pit_total: CALIBRATED
- race_control: PRIOR_ONLY
- setup: NON_IDENTIFIABLE
- strategy: NON_IDENTIFIABLE
- tyre_hard: LIMITED
- tyre_medium: LIMITED
- tyre_soft: LIMITED
- weather: PRIOR_ONLY
## REPRODUCIBILITY
- Same dataset hash + seed 42 + code version -> identical artifacts, hashes in phase23_calibration_manifest.json
## LEAKAGE
- Violations 0, adversarial 6/6 passed
