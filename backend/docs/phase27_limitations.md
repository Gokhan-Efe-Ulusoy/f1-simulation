# Phase 27 Limitations

## What Was Identifiable (LIMITED)
- circuit: hierarchical LIMITED, improves 0.05-0.36 but last split worsens, not stable
- driver: hierarchical LIMITED, driver pace not pure skill, tyre preservation not separated
- progression: RACE_PROGRESSION_ASSOCIATIONAL not fuel, stable beta -6.5 but confounding remains
- pit: LIMITED mean total 23.2, lane/stationary NON_IDENTIFIABLE

## What Was Not Identifiable
- tyre degradation: NON_IDENTIFIABLE unconstrained -0.309 violates monotonic, constrained 0, no causal curve
- fuel: NON_IDENTIFIABLE actual fuel not available, progression proxy only
- constructor: LIMITED but confounded with driver, where n<30 NON_IDENTIFIABLE
- weather: PRIOR_ONLY wet insufficient, ERA5 reanalysis not sensor
- race_control: PRIOR_ONLY SC/VSC sparse, YELLOW/RED limited but historical not calibrated
- fuel remains NON_IDENTIFIABLE per Phase26 finding Pearson 0.497 etc

## What Improved
- Circuit baseline vs global improves 0.3-0.5 MAE in training, walk-forward 0.04-0.36 first two splits

## What Worsened
- Full model with tyre worsens -1.25 for 2026 validation, not stable
- Constructor adds little +0.05 worsen

## What Was Rejected
- Unconstrained tyre degradation (negative beta)
- Fuel effect as independent feature
- Lane/stationary split
- Historical weather/RC inferred from modern

## What Was Promoted
- Nothing promoted to production; all remain CANDIDATE due to gates failing (physical sanity, walk-forward, confounding)
- Production tyre-v1.0.0, weather-v1.0.0, racecontrol-v1.0.0, strategy-v1.1.0, setup-v1.0.0, raceengine-v2.2.0 unchanged

## Why Candidates Remain
Promotion requires all 10 gates: physical sanity FAIL (tyre inverted), walk_forward FAIL (not stable), no_major_confounding FAIL (fuel/tyre r 0.497 + 0.983), so KEEP_PRODUCTION_MODEL.

## Scientific Honesty
More data does NOT automatically mean better causal identification; fuel remains NON_IDENTIFIABLE unless actual measurements obtained; race progression is NOT fuel; negative tyre coefficients rejected; no fabricated variables; failed hypothesis valid; provenance complete.

