# Phase 26 Validation

## Chronological Validation
- splits as in walk_forward.md: train <=2023->2024, <=2024->2025, <=2025->2026, all with as_of race_date -1 day
- Metrics measured: lap MAE (primary), finish MAE LIMITED, winner match/top3/Brier NOT_TESTABLE for lap-only model
- Baseline (circuit mean): 6.26, 8.42, 5.96 MAE
- Candidate (circuit mean + tyre_age*beta): 6.99, 8.66, 7.85 MAE
- Improvement: -0.72, -0.23, -1.88 (all negative, candidate worse)
- Conclusion: no chronological improvement, worsens validation

## Compared
- production tyre-v1.0.0 (prior beta GLOBAL -0.207 from 1127 FastF1 laps, but not used in validation baseline which is circuit mean)
- vs Phase-26 candidate decomposition (beta -0.309 etc)
- Candidate must NOT be promoted merely because training fit improves (training r2 small but validation worsens indicates overfit to confounded progression)

## Sensitivity
- Tested linear, quadratic, piecewise, with/without circuit/driver/phase: range [-0.332,-0.060] still negative
- Circuit hierarchical, driver shrinkage, constructor sparse all tested

## Leakage
- 0 violations, strict_before, future injection tests passed

## Reproducibility
- seed 42, deterministic, second run identical manifest fingerprint 8-char sha256 via proxy definition

## Promotion
- NOT promoted due to counterfactual inverted, confounding, walk-forward inconsistent

