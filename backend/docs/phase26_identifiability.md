# Phase 26 Identifiability Analysis

Generated 2026-09-20T17:45:00+00:00

## Pearson / Spearman Correlations

Variables: tyre_age, stint_lap, lap_number, race_progress (normalized_lap)

### Global (n=88404)
- tyre_age vs stint_lap: Pearson 0.9834 Spearman 0.9844
- tyre_age vs lap_number: Pearson 0.4967 Spearman 0.5025
- tyre_age vs race_progress: Pearson 0.4951 Spearman 0.5030
- stint_lap vs lap_number: Pearson 0.4891 Spearman 0.4908
- lap_number vs race_progress: Pearson 0.9604 Spearman 0.9681
- stint_lap vs race_progress: Pearson 0.4914 Spearman 0.4941

Distribution notes: tyre_age mean ~15 std ~12 min 0 max 60, lap_number mean ~29 std ~16, stint_lap mean ~15 std ~12, highly overlapping.

### By Compound
- soft tyre_age vs lap_number: Pearson ~0.48 Spearman ~0.49 n10998 tyre_age mean ~10
- medium vs lap_number: Pearson ~0.50 n33259 mean ~15
- hard vs lap_number: Pearson ~0.51 n44147 mean ~18
- All show similar 0.49-0.51 correlation, hard slightly higher due to longer stints
- tyre_age vs stint_lap per compound still >0.98 for all compounds

### By Season
- 2023: Pearson tyre_age vs lap_number 0.49 n24254
- 2024: 0.50 n24091
- 2025: 0.50 n24863
- 2026: 0.48 n16028
- Stable across modern era, no temporal change indicating systematic not random

### By Circuit (top 10 by n)
- zandvoort n5495 Pearson 0.51
- monaco n5555 0.48
- hungaroring n5404 0.45
- jeddah n2739 0.52
- suzuka n3950 0.53
- etc all 0.45-0.55, no circuit with low correlation (<0.3), even low-deg circuits still moderate correlation because fuel progression universal

### By Race (sample 5)
- 2023-jeddah: Pearson 0.53 n850
- 2023-bahrain: 0.50 n900
- 2024-monaco: 0.47 n1500
- etc stable 0.45-0.55, within-race collinearity persists

## Collinearity Severity

- Threshold for severe collinearity often VIF>10 or corr>0.8. Here:
  - tyre_age vs stint_lap 0.983 => VIF ~60, severe, separation NON_IDENTIFIABLE if both in same model (Model C)
  - tyre_age vs lap_number 0.497 => VIF ~1.33, moderate, not severe by strict threshold but combined with race fixed effects still confounded because within stint lap_number and tyre_age increase together monotonic (every stint lap_number increases by 1 while tyre_age increases by 1, within stint corr ~1.0)
  - lap_number vs race_progress 0.96 => redundant, not independent

Do not force coefficient when variables too collinear: mark separation as NON_IDENTIFIABLE where appropriate.

## Partial Identification (Bounded Sensitivity)

Instead of asking "What is fuel effect?" ask "What range of tyre-age effects remains compatible under reasonable progression specifications?"

Specifications considered:
- baseline progression control (Model A) -0.309
- linear progression (Model B lap_number) -0.168
- stint_lap (Model C) -0.060
- normalized race_progress (Model D) -0.291
- quadratic progression (lap + lap^2) -0.173
- within-stint demeaned -0.174
- race fixed effect (demeaned) -0.232
- circuit fixed effect -0.221
- driver + circuit -0.222
- hierarchical per-circuit shrunk -0.252 to -0.68 per compound but global still negative

Range:
```
beta_tyre ∈ [-0.332, -0.060]
```
All values negative, none positive. The range does NOT include physically plausible positive degradation (should be +0.02 to +0.08 per prior). Thus even bounded sensitivity shows misspecification, not just uncertainty.

Only if statistically/methodologically justified do we report range; here range is descriptive, not causal confidence interval.

Do not invent confidence ranges beyond OLS CI which are already narrow (se 0.004-0.026) but narrow CI does NOT imply causality when confounding strong.

## Fuel/Tyre Separation Classification

H1: tyre-age coefficient substantially confounded by fuel/race progression -> SUPPORTED: beta changes 45.7% when controlling lap_number (-0.309->-0.167), similar to Phase25 59% (-0.309->-0.126), and within-stint demeaned changes 43% (-0.309->-0.174)

H2: After controlling for progression, tyre degradation becomes more plausible -> NOT SUPPORTED: even after all controls (circuit+driver+constructor+race_phase) beta remains -0.22 negative, not plausible positive, sign not corrected

H3: Data still insufficient to identify fuel and tyre separately -> SUPPORTED: proxy only, correlation 0.5 globally and 0.98 within stint, no actual fuel measurement, walk-forward worsens, counterfactual inverted, robustness NON_IDENTIFIABLE

Final fuel_tyre_separation = NON_IDENTIFIABLE, reason: moderate global correlation 0.497 plus extreme within-stint collinearity 0.983 plus proxy-only status plus inverted sign plus unstable across specifications (range 0.27 width vs magnitude). Mark separation NON_IDENTIFIABLE is scientifically acceptable, not failure.

## Historical Overreach Warning
Do not apply 2023-2026 tyre behaviour to 1996-2022; era analysis shows historical eras n=0 NON_IDENTIFIABLE, no modern tyre join.

