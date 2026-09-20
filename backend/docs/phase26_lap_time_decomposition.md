# Phase 26 Lap-Time Decomposition

Generated 2026-09-20T17:45:00+00:00, seed 42, dataset f1-dataset-v1.3, tyre_join-v1.0.0, as_of race_date -1 day strict_before

## Sample
- Valid laps for calibration: 88404 (filtered from 88617 exact joined 2023-2026 where 50<lap_time<400 and 0<=tyre_age<=60)
- By season 2023 24254 2024 24091 2025 24863 2026 16028 (approx per enriched after filtering)
- By compound soft 10998 medium 33259 hard 44147 intermediate 0 (filtered) wet 0
- By circuit 52 circuits, by driver 40+ drivers, by race 84 sessions

## Model Specifications (A-H)

All models treat fuel as progression proxy only, EVIDENCE_TIER PROXY_ONLY, no kg. Reported coefficient = tyre_age effect beta (seconds per lap of tyre age), standard error, 95% CI, n, variation components. lap_time in seconds.

### MODEL A: lap_time ~ tyre_age
- Spec: lap_time ~ tyre_age (no progression control, no circuit/driver)
- Beta -0.3090 se 0.0048 ci [-0.3184, -0.2996] n 88404 r2 ~0.05 (negative implies older tyres faster, physically suspicious)
- Interpretation: raw associational, heavily confounded with progression

### MODEL B: lap_time ~ tyre_age + lap_number
- Spec: add lap_number as linear progression proxy
- Beta tyre_age -0.1676 se 0.0054 ci [-0.1783, -0.1570] n 88404 p 3 mse ~?
- Progression beta lap_number ~ -0.25 sec per lap (fuel + track evolution combined)
- Change vs A: 45.7% reduction in magnitude (-0.309 -> -0.167), indicating strong confounding, similar to Phase25 -0.309->-0.126 (59% change) but with multiple regression vs residualization difference
- Do not treat statistical significance as proof of causality

### MODEL C: lap_time ~ tyre_age + stint_lap
- Beta -0.0596 se 0.0264 ci [-0.1113, -0.0079] n 88404
- Note: stint_lap vs tyre_age correlation 0.983 Pearson 0.984 Spearman globally, extremely collinear, VIF huge, separation effectively NON_IDENTIFIABLE, standard error 5x larger, coefficient collapses toward zero, not causal proof

### MODEL D: lap_time ~ tyre_age + normalized_race_progress
- Beta -0.2914 se 0.0055 ci [-0.3022, -0.2806] n 88404
- Normalized progression (lap/max) captures fuel fraction but also race phase, coefficient only slightly reduced vs A (5.6% change), indicating linear normalized proxy insufficient vs absolute lap_number

### MODEL E: lap_time ~ tyre_age + lap_number + circuit
- Beta -0.2206 se 0.0040 ci [-0.2285, -0.2127] n 88404 p ~54 (intercept +2 numeric +51 circuit dummies)
- Circuit fixed effects via dummy encoding, shrinkage interpretation outside but OLS includes all circuits with baseline last category, compare to global vs circuit-controlled: global -0.309 vs circuit-controlled -0.220 (still negative)

### MODEL F: lap_time ~ tyre_age + lap_number + circuit + driver
- Beta -0.2224 se 0.0040 ci [-0.2303, -0.2145] n 88404 p ~94
- Driver fixed effects added, driver not interpreted as skill, confounding control only, hierarchical shrinkage for sparse drivers (n<500 LIMITED) but OLS here shows minimal change vs E (-0.220->-0.222), driver explains little beyond circuit

### MODEL G: lap_time ~ tyre_age + lap_number + circuit + driver + constructor
- Beta -0.2224 se 0.0040 ci [-0.2303, -0.2146] n 88404 p ~130
- Constructor dummies added, but constructor mapping via team_name proxy limited, many constructors sparse, coefficient identical to F, no additional confounding resolved, marked LIMITED

### MODEL H: lap_time ~ tyre_age + lap_number + circuit + driver + constructor + race_phase
- Beta -0.2201 se 0.0036 ci [-0.2271, -0.2131] n 88404 p ~132
- Race phase early/mid/late categorical adds piecewise non-linear progression, coefficient stable vs F/G, still negative

## Within-Stint De-Meaned Analysis

For each stint, demeaned_lap_time = lap_time - mean(lap_time within stint), then demeaned_lap_time ~ tyre_age

- Beta -0.1742 se 0.0029 ci [-0.1800, -0.1685] n 88404 stints 4372 (approx)
- Purpose: remove between-stint/between-race baseline variation (fuel level at stint start, car, circuit, strategy)
- Compare: global -0.309 vs race-demeaned -0.2319 vs circuit-demeaned -0.2410 vs within-stint -0.1742 vs within-race average -0.332
- Sign does NOT change; remains negative, indicating even within same stint older tyres appear faster, still confounded by decreasing fuel within stint (fuel effect dominates)
- Not automatically causal

## Within-Race Analysis

- Per-race OLS tyre_age slope averaged: mean -0.332 sd ~0.3, n races 82, each race 20-200 laps
- Control for race, driver, circuit via race fixed effect (demean within race): beta -0.2319
- Avoid comparing different circuits/eras/cars as equivalent; within-race reduces cross-race confounding but not within-race fuel confounding (fuel decreases lap by lap while tyre_age increases lap by lap within same race, so still correlated within race r~0.5 per race)
- Only races with enough laps included (>=20 laps), else excluded

## Variation Components

- total_var 229.43 (lap_time variance)
- between_race_var 121.70 (53% of total, race-to-race baseline differences due to circuit, weather, season)
- between_circuit_var 126.41 (55% overlapping with race)
- within_race_var 121.81 (average within-race variance, includes fuel + tyre + traffic)
- within_stint_var 100.78 (average within-stint variance, smaller than within-race because stint removes pit resets)
- within-race variation dominates after removing circuit means, but tyre signal still confounded

## Summary Table

| Model | Beta | SE | CI | n | Variation controlled |
|-------|------|-----|----|---|----------------|
| A tyre only | -0.309 | 0.0048 | [-0.318,-0.300] | 88404 | none |
| B + lap | -0.168 | 0.0054 | [-0.178,-0.157] | 88404 | 45% change |
| C + stint_lap | -0.060 | 0.0264 | [-0.111,-0.008] | 88404 | VIF huge |
| D + norm_progress | -0.291 | 0.0055 | [-0.302,-0.281] | 88404 | 5% change |
| E + lap+circuit | -0.221 | 0.0040 | [-0.229,-0.213] | 88404 | circuit fixed |
| F + lap+circuit+driver | -0.222 | 0.0040 | [-0.230,-0.215] | 88404 | +driver |
| G + lap+circuit+driver+constructor | -0.222 | 0.0040 | [-0.230,-0.215] | 88404 | +constructor LIMITED |
| H + lap+circuit+driver+constructor+race_phase | -0.220 | 0.0036 | [-0.227,-0.213] | 88404 | +phase |

Do not treat significance as causality. All betas remain negative (implausible). See identifiability and robustness.

