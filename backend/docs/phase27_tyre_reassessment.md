# Phase 27 Tyre Reassessment

## Previous Result
Phase25/26: negative beta physically inverted fuel-confounded, MUST NOT be promoted. Do NOT fit production degradation curve just to obtain positive.

## Tests

### 1. compound fixed effects
- soft -0.548 vs hard +0.110 vs medium +0.035 relative to global 91.35 => hard slower than soft by ~0.66s as expected, but this is baseline pace not degradation

### 2. within-stint normalized progression
- lap_time ~ tyre_age + stint_lap extremely collinear r 0.983, beta collapses to -0.06, NON_IDENTIFIABLE

### 3. circuit × compound interaction
- Hierarchical per circuit per compound, still negative for all compounds across circuits (soft -0.68, medium -0.39, hard -0.25 global), sparse circuits shrunk but still negative

### 4. driver × compound interaction where identifiable
- Sparse where n<30 NON_IDENTIFIABLE, not forced

### 5. hierarchical shrinkage
- tau30 per circuit, driver tau10, still negative

### 6. non-linear age splines
- Quadratic tyre_age + tyre_age^2 also negative -0.17, still inverted, not rescue

### 7. monotonic constrained model
- MUST enforce increasing tyre age cannot improve lap time
- Unconstrained beta -0.309 <0 violates monotonic
- Constrained beta = 0.0 (reject degradation)
- If constrained improves walk-forward WITHOUT implausible counterfactuals => CANDIDATE not CALIBRATED automatically
- Test constrained 0.0 vs unconstrained -0.309: walk-forward candidate with constrained 0 is just baseline circuit+driver+progression (no tyre), which improves 0.04-0.36 for first two splits but worsens third, still not stable, but at least not inverted
- However tyre remains NON_IDENTIFIABLE because unconstrained violated monotonic, so we reject unconstrained and keep constrained 0 as prior

### Counterfactual Tests
- +5 tyre laps: delta -1.54 faster (expected slower) FAIL
- +10 tyre laps: delta -3.09 faster FAIL
- reset tyre age (20->0): predicts slower FAIL
- compound switch soft->hard: hard slower than soft by 0.66 plausible PASS but not causal
- Overall tyre direction FAIL

### Conclusion
TYRE_DEGRADATION = NON_IDENTIFIABLE, production tyre-v1.0.0 remains unchanged, tyre candidate not promoted, remains candidate with constrained 0 (prior).

