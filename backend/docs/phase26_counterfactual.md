# Phase 26 Counterfactual Directionality

Expected physical direction:
- increase tyre age -> should not systematically make tyre faster (should be slower or neutral, +0.02 to +0.08 sec/lap)
- increase degradation -> should not systematically improve lap time
- reset tyre age (pit new tyre) -> should not systematically worsen performance (should be faster)

## Tests

### Increase tyre age by 10 laps
- Production expectation: lap_time +0.2 to +0.8 sec (degradation)
- Candidate model (global beta -0.309): predicts delta = -0.309*10 = -3.09 sec (faster), physically incorrect direction
- Result: FAIL, sign inverted due to fuel confounding (-0.309 captures fuel lightening not tyre slowing)
- Per-compound: soft -0.681*10=-6.81 sec, medium -0.388*10=-3.88, hard -0.253*10=-2.53 all faster, all FAIL

### Increase degradation (wear cliff)
- Expected: slower
- Candidate: with negative wear coefficient similarly predicts faster -> FAIL

### Reset tyre age (new tyre, age 0 vs age 20)
- Expected: new tyre faster by ~0.4-1.6 sec
- Candidate predicts: old tyre 20: -0.309*20=-6.18 vs new 0 => old faster by 6 sec, reset worsens -> FAIL

### Change compound soft->hard
- Expected: hard slower than soft by ~0.5-1 sec per lap baseline
- Candidate compound interaction shows hard less negative than soft (-0.253 vs -0.681) but still both negative, ordering plausible (soft more negative because soft used early in race with heavier fuel, confounded) but not causal => associational only, directionality not clearly fail but not proof

### Move pit earlier/later
- Not tested due to fuel confounding and SC limited, but would be confounded similarly

## Overall
- Passed: 0
- Failed: 3 (increase age, increase degradation, reset)
- Physically correct: false

Because directionality remains inverted, candidate MUST NOT be promoted. Hard scientific gate fails.

This is consistent with Phase25 finding: counterfactual tests also produced physically incorrect directionality.

