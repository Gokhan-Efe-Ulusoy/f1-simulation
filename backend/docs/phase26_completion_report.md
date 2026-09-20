# Phase 26 Completion Report

Generated 2026-09-20T17:45:00+00:00

## Scientific Question
Test whether tyre-age degradation can be separated from fuel/race progression. All three outcomes (identifiable, partially_identifiable, non_identifiable) acceptable. Final result legitimately NON_IDENTIFIABLE is not failure.

## Fuel Data
- ACTUAL_FUEL_DATA = NOT_AVAILABLE (searched 6 fuel fields across 1084830 rows, 84 OpenF1 sessions, 552656 laps, no measurement)
- No synthetic fuel model created

## Fuel Proxy
- FUEL_PROGRESSION_PROXY PROXY_ONLY with variables normalized_lap, lap_number, stint_lap, race_progress, remaining_laps, race_phase
- Evidence tier PROXY_ONLY, not kg, warning not to claim kg values

## Decomposition Models A-H
- A tyre only -0.3090 se0.0048
- B +lap -0.1676 se0.0054 change 45.7% (Phase25 -0.309->-0.126 59%)
- C +stint_lap -0.0596 se0.0264 collinear 0.983
- D +norm_progress -0.2914
- E +lap+circuit -0.2206
- F +lap+circuit+driver -0.2224
- G +lap+circuit+driver+constructor -0.2224
- H +lap+circuit+driver+constructor+race_phase -0.2201
- Within-stint demeaned -0.1742, within-race avg -0.332, range [-0.332,-0.060] never positive

## Identifiability
- Correlations tyre_age vs lap_number 0.497 Pearson 0.503 Spearman globally, vs stint_lap 0.983, vs race_progress 0.495
- By compound soft 0.287 medium 0.485 hard 0.567, by season stable 0.45-0.53, by circuit 0.16-0.60
- Partial identification beta range [-0.332,-0.060], no positive plausible values
- Robustness NON_IDENTIFIABLE max_corr 0.983 beta_change 45.7% range 1.24 vs magnitude
- H1 confounded supported, H2 not supported (still negative), H3 insufficient supported

## Compound / Era / Controls
- per-compound soft -0.681 medium -0.388 hard -0.253 all negative, sign wrong
- era: 1996-2009 0 NON_IDENTIFIABLE, 2010-2016 0, 2017-2021 0, 2022-present 88404 LIMITED but inverted
- circuit hierarchical tau30, driver/constructor hierarchical, pit effect 25.05s for stint_lap1, race_control LIMITED 8875 msgs 222 SC laps, weather LIMITED 84 files

## Walk-Forward
- Train <=2023 val2024 improvement -0.722 (worse), <=2024 val2025 -0.236, <=2025 val2026 -1.889 all negative, candidate worse than baseline
- NOT_TESTABLE for pre-2023 due to no tyre data
- Candidate must NOT be promoted merely training improves

## Counterfactual
- increase tyre age -> predicts faster due to -0.309 FAIL
- increase degradation -> faster FAIL
- reset -> slower FAIL
- physically_correct false, hard gate fails

## Falsification
- randomized tyre_age weakened -0.388->-0.017 pass, shuffled stint/lap/compound/circuit pass, future injection leakage 0 pass, overall true but not causal proof

## Promotion Gate 10 criteria
1 no leakage true
2 reproducibility true
3 physically correct false -> fail
4 stable sign false (negative not plausible) fail
5 robust false (NON_IDENTIFIABLE) fail
6 no severe confounding false (corr 0.497 change 45%) fail
7 chronological improvement false fail
8 uncertainty true
9 no historical overreach true
10 provenance true
Decision KEEP_PRODUCTION_MODEL, candidate NON_IDENTIFIABLE, production tyre-v1.0.0 unchanged

## Classification
- FUEL_TYRE_SEPARATION = NON_IDENTIFIABLE reason tyre_age/progression correlated 0.497+0.983 proxy only inverted sign
- TYRE_DEGRADATION = NON_IDENTIFIABLE (or LIMITED associational but not calibrated, rejected for causal)

## Performance
- calibration offline 30s, production overhead <10% target met 2.4%, no NDL tensors, memory bounded, phase26_enabled=False legacy equivalence reproduced within tolerance

## Provenance
- dataset f1-dataset-v1.3 hashes 2cce529c/ac13fa1f, tyre_join-v1.0.0, calibration phase26-fuel-tyre-decomp-v1.0.0-candidate, circuit circuit-v1.0.0-candidate, fuel proxy PROXY_ONLY, seed 42, fingerprint b22a1491 changes if proxy changes

## Tests
- New 35+ required, added, 0 failures, 0 leakage violations, not weakenig existing

## Legacy Equivalence
- tyre-v1.0.0, weather-v1.0.0, racecontrol-v1.0.0, strategy-v1.1.0, setup-v1.0.0 unchanged unless promotion passed (not passed)

## Final Status
PHASE_26_STATUS = NON_IDENTIFIABLE (scientifically successful, not failure), FUEL_TYRE_SEPARATION = NON_IDENTIFIABLE, PRODUCTION TYRE MODEL = UNCHANGED, next research requires actual fuel measurements

