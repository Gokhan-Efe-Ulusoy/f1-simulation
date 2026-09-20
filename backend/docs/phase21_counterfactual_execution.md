# Phase 21 — Counterfactual Execution

## 1. Pipeline (no fabricated deltas)

```
Baseline Scenario (immutable, caller's object never touched)
  │  deep copy ──► ScenarioAwareRaceEngine (v2.1.0), seed X ──► baseline distribution
  │
  │  ScenarioSpec + interventions ──► validate ──► compile (deep copy + ordered
  │  modifier writes + trace) ──► SAME engine, SAME seed X ──► counterfactual distribution
  │
  └─► compare (common random numbers) ──► effect + uncertainty + explanation
```

BAD (prohibited, not present): `counterfactual = baseline + arbitrary_delta`.
GOOD (implemented): both legs run the real pipeline; differences emerge from
setup offsets, pit schedules, RC trajectories, weather trajectories, or pace
means. Each family has a propagation test asserting distribution movement.

## 2. Common random numbers

Both legs use identical `seed` (and identical `simulations`). All stochastic
streams (driver/qualifying/reliability/AR1-100/weather-500/RC-600/strategy-700)
derive per-sim deterministically from that seed, so sim *i* of baseline and
sim *i* of counterfactual share randomness; the intervention is the principal
difference. Interventions themselves consume no RNG (deterministic transforms).
Verified: baseline legs of two different counterfactual runs are bit-identical.

## 3. Vectorized integration points (all default-identical)

- **Setup**: per-driver sec/lap offsets (Phase 20 `offsets.py`), `(D,)`
  broadcast add per lap; `{}` when disabled/baseline.
- **Pit/compound schedule** (`scenario/resolvers.py`): `(L+1, D)` pit-bool and
  compound-int8 matrices. Default reproduces legacy exactly (pits at
  L%20==0, L≠total; compound SOFT): guarded by Phase 15 reference-equivalence
  + Phase 20 baseline tests, all still passing.
- **Pace deltas**: added to calibration means pre-sampling (driver + correlated
  constructor). Default zero.
- **Weather/RC**: pre-existing modifier paths (`weather` initial-state override;
  `race_control` enable flags + 2 thresholds); untouched by Phase 21.

Memory: matrices are `(L+1, D)` booleans/int8 (≈1–2 KB); no `(N, D, L)` tensors.

## 4. Branching

`run_branch(baseline, {A: [...], B: [...], C: [...]})`: baseline leg runs ONCE;
each branch compiles from the same immutable baseline and runs with the same
seed. Verified: shared baseline fingerprint, distinct counterfactual
fingerprints, no cross-branch state (baseline object dump-identical afterwards).

## 5. Temporal discipline

Compiler verifies `as_of` strictly before race `date` (repo rule) and never
modifies `as_of`/`date`/drivers/grid. Calibration stays `as_of`-gated inside
the engines. Interventions are user-specified assumptions, not observations;
historical mode additionally uses neutral setup baselines (Phase 20 rule).

## 6. Engine & versions

Execution engine: `ScenarioAwareRaceEngine` (`raceengine-v2.1.0`, Model 0.8.0)
— thin provenance layer over v20, zero dynamics change. Provenance of every
run records the full version map including `scenario-v1.0.0`.

## 7. Known execution limits

- Vectorized path (N≥50) applies setup/pit/compound/pace interventions; the
  sequential small-N fallback preserves legacy behavior but not these offsets
  (same limitation class as Phase 20; propagation tests use N≥50).
- Pre-2023 eras: pit/compound interventions are recorded but pace-inert (tyre
  model inactive) — explicit warning, not silent.
- Pit stops cost no time in the vectorized model (freshness benefit only).
