# Phase 26 Tyre Analysis per Compound and Era

## Compound Analysis (independent per SOFT/MEDIUM/HARD)

All use exact join 2023-2026 only, filtered 50<lap_time<400.

### SOFT
- Sample 10998 laps, stints 873, races 74, circuits 34, seasons [2023,2024,2025,2026]
- Coefficients vs specification:
  - A tyre only: -0.681 (phase25) / -0.68 with se 0.02 ci [-0.72,-0.64]
  - B +lap_number: -0.38 (approx via per-compound recompute, 44% change)
  - C +stint_lap: ~-0.12 (high collinearity)
  - D +normalized: -0.58
  - E +circuit: -0.55
  - F +circuit+driver: -0.54
- Range [-0.68, -0.12] width 0.56, sign stable negative, not plausible (soft should degrade fastest positive ~0.08 per Phase23 prior)
- Walk-forward per compound limited: training <=2024 val 2025 MAE baseline 5.3 candidate 5.0 improvement 0.29 in Phase25 but inconsistent across splits (see global walk_forward negative now)
- Between-circuit var 1.13, between-driver var 1.29 large due to sparse soft usage (soft mostly qualifying/short stints)
- Classification: LIMITED but inverted sign => effectively NON_IDENTIFIABLE for causal

### MEDIUM
- Sample 33259, stints 1778, races 82, circuits 36
- A -0.388 se 0.0088 ci [-0.405,-0.370]
- B -0.21, C -0.07, D -0.35, E -0.28, F -0.27
- Range [-0.388,-0.07] width 0.31, sign stable negative, medium expected ~0.04 prior positive
- Between-circuit var 0.355, between-driver var 0.104 moderate

### HARD
- Sample 44147, stints 1721, races 82, circuits 36
- A -0.253 se 0.0059 ci [-0.264,-0.241]
- B -0.14, C -0.04, D -0.23, E -0.19, F -0.19
- Range [-0.253,-0.04] width 0.21, sign stable negative, hard expected ~0.02 prior positive slowest degradation but still positive

Do not pool compounds if pooling masks differences: we did separate, all show same pattern negative with fuel confounding, pooling global -0.309 is more negative than hard but less than soft as expected ordinal but still wrong sign.

## Walk-Forward per Compound

Same splits as global; per-compound walk-forward improvement inconsistent: 2023->2024 -0.08 worse, 2024->2025 +0.29 better in Phase25 but Phase26 full decomposition worsens consistently (-0.72, -0.23, -1.88). Indicates candidate does not generalize chronologically.

## Circuit vs Tyre Interaction

Hierarchical per-compound per-circuit shrunk estimates (tau 30):
- soft global -0.681, per-circuit raw ranges -3.92 to +2.57 but shrunk toward global, e.g., baku +2.57 n10 raw but shrunk 0.94, melbourne -3.92 n84 shrunk -3.53 (sparse)
- medium global -0.388, losail -0.813 n1147 shrunk -0.81, baku -0.388 n763 stable
- hard global -0.253, melbourne -3.92 n84 extreme shrinkage, hungaroring -0.083 n3056 stable -0.083
Sparse circuits (<400) shrinkage_weight <0.9, dense >0.95, respects existing shrinkage rules, not dominate.

Between-circuit variance hard 0.65, medium 0.355, soft 1.13 large due to sparse soft

## Era Analysis

Only eras where tyre observations actually exist:

- 1996-2009: n 0, status NON_IDENTIFIABLE, note no tyre data historical
- 2010-2016: n 0, NON_IDENTIFIABLE
- 2017-2021: n 0, NON_IDENTIFIABLE
- 2022-present: n 88404 beta -0.309 se 0.0048 status LIMITED (but sign inverted so LIMITED not CALIBRATED)

Do NOT manufacture historical tyre age, do NOT apply 2023-2026 tyre behaviour to 1996-2022, historical without compound PRIOR_ONLY/NON_IDENTIFIABLE, no backward extrapolation.

## Summary

Per-compound and per-era analysis confirms identical confounding pattern: negative beta across all specifications, stable sign but wrong sign, fuel proxy does not rescue physical plausibility. Classification for each compound separately still NON_IDENTIFIABLE for causal degradation.
