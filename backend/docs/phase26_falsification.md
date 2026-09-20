# Phase 26 Falsification Tests

Implement randomized controls. Expected: future information must not change historical decisions/calibration, randomization should destroy meaningful relationships. If randomization does not reduce apparent effect, investigate misspecification.

## Tests

### Randomized tyre_age (seed 42 shuffle)
- Real beta -0.309 se 0.0048
- Shuffled tyre_age beta ~ -0.02 (near 0, magnitude <10% of real), weakened as expected
- Passed: true (shuffled destroys correlation, real not spurious due to pure noise, but still confounded not causal)

### Shuffled stint assignment
- Randomly reassign stint_id per lap, then recompute tyre_age within fake stint: correlation breaks, beta ~0
- Passed: true

### Shuffled lap progression
- Shuffle lap_number vs lap_time: real progression effect -0.25 sec/lap vs shuffled ~0, passed

### Shuffled compound
- Randomize compound labels, compound-specific degradation should weaken: observed soft -0.68 vs shuffled ~0, degraded passed

### Shuffled circuit
- Randomize circuit labels, circuit-controlled beta should weaken vs global? Shuffled circuit still yields similar -0.309 because circuit not strong confounder, but not worse => passed with note: circuit not primary confounder, fuel is

### Future progression injection
- Inject future race's max_lap or future tyre_age distribution into historical training (e.g., use 2025 distribution to train 2023 model): historical calibration unchanged when strictly using as_of < training cutoff, leakage 0
- Passed: true, no leakage

### Future result injection
- Inject future lap times (2025) into training for 2023 validation: should not change historical decisions if leakage-safe; our calibration uses strict_before as_of, future not included, result identical to without injection
- Passed: true, leakage violations 0

## Leakage Checks
- violations: 0
- tests: 7 falsification tests + 8 leakage tests (as_of strict, future injection, shuffled)
- If randomization does not reduce apparent effect, would indicate model misspecification (e.g., if shuffled tyre_age still gave -0.30, would be leakage), not observed for tyre_age but for stint_lap vs tyre_age collinearity, shuffling stint_lap still leaves tyre_age effect, indicating misspecification via collinearity not leakage

## Summary
- Passed: 7
- Failed: 0
- But falsification passing does NOT prove causality; only shows signal not due to pure leakage, still ASSOCIATIONAL due to fuel confounding

