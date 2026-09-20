# Phase 21 Completion Report — Counterfactual & Scenario Engine

*Generated 2026-09-18. Factual; every claim verified by code/tests/measured runs.*

## Architecture

New package `backend/app/simulation/scenario/` (8 modules, ~1.6k lines):
`models` (Intervention/Spec/Trace/Comparison/Explanation/Result),
`registry` (allowlists, tiers, pathways, era/leakage rules),
`validation` (bounds/targets/era/leakage/conflicts),
`compiler` (immutable apply, traces, fingerprints, branching),
`resolvers` (pit/compound matrices, pace deltas for vectorized use),
`comparison` (deltas + L1/quantile distances), `engine` (ScenarioEngine, CRN
execution, grounded explanation), `__init__` (`scenario-v1.0.0`).

Additive engine changes: `performance/vectorized_montecarlo.py` (schedule
matrices + pace deltas; defaults reproduce legacy exactly),
`race_engine_v21.py` (thin provenance layer, no dynamics change),
`version.py` (0.8.0 / 9.1.0 / v2.1.0 / scenario-v1.0.0). No physics duplicated;
no domain logic forked.

## Scenario types / intervention types

Types: historical/counterfactual/hypothetical/future (Phase 14 vocabulary).
Implemented families → call paths:
- setup → `setup/offsets.py` → lap offsets → outcome ✓ tested
- strategy.pit_laps → schedule matrices → tyre-age resets → outcome ✓ tested
- tyre compounds/stints → compound matrices → calibrated betas → outcome ✓ tested
- race_control flags/thresholds → `RaceControlEngine.generate_batch` → outcome ✓ tested
- weather fields → `WeatherEngine` initial state → trajectories → outcome ✓ tested
- driver/car pace_delta → calibration means → base pace → outcome ✓ tested
Rejected: strategy policies, forced RC events, result/standings fields,
structural fields, out-of-range/unknown/conflicting inputs.

## Evidence

Effect tier PRIOR_ONLY for all 7 families (weather override *states*
ESTIMATED, surfaced separately). Monte Carlo never upgrades tiers. Historical
setups remain unknown/neutral (Phase 20 rule preserved).

## Leakage (adversarial, all pass)

- `future_result`/`actual_winner`/positions/structural params → validation rejects.
- Hand-injected `future_result` + `realized_weather` blocks → outputs
  bit-identical (1e-12).
- Unknown `realized_*` weather keys → inert (identical outputs).
- `as_of` < race date enforced; never rewritten.

## Determinism / RNG / fingerprint / provenance

- Same spec+seed → identical fingerprints and deltas (re-run equality).
- N=10 and N=60 determinism; seed 42→43 changes output (RNG alive).
- Baseline legs of different counterfactuals identical → no stream cross-talk
  (streams 500/600/700/100 untouched; scenario layer uses no RNG).
- Fingerprint changes on any value change; reproduces on identical input.
- Provenance carries both fingerprints, ordered trace, versions, warnings.
- Baseline object dump-identical after branch runs; post-branch re-run matches.

## Baseline preservation / propagation / ablation

- Empty spec ≡ legacy (all deltas 0 at 1e-12, N=60).
- All 7 families move finish distributions (L1 > 0, N=60, 2024-bahrain):
  setup .10, RC-disable .03 (+Δwin), wet .13, MEDIUM start .20, extra pit .23,
  driver pace .67, constructor pace .57.
- Multi-intervention (setup+pit+wet) composes; pathways restricted to present
  families. Extreme boundary inputs stay finite (no NaN/Inf/crash).

## Performance (measured, 2024-bahrain, 8 laps, seed 42)

- N=1000: baseline leg 97.5s (cold incl. data load) / full run_spec
  (both legs + compare) 68.5s warm; N=10000: 111.8s / 236.9s.
- Steady-state ≈ 89 sims/s; comparison+explanation sub-second (dict
  arithmetic over 20 drivers). Peak Python mem 86.7 MB (N=1000) / 29.1 MB
  (N=10000 — post-warmup). Schedule/pace overhead negligible (KB matrices,
  one broadcast add per lap). Script: `scripts/phase21_benchmark.py`.

## Tests

Previous 527 · new 51 (`tests/test_phase21_scenario.py`: models 4, registry 2,
validation 13, compiler 6, preservation/ablation 2, propagation 9,
leakage 3, determinism/RNG/branching/corruption 6, extremes/invalid 3,
comparison/explanation/provenance/version 4) · total 578 · passed 578 ·
failed 0 · skipped 0. Existing tests untouched in logic (2 version tuples
extended for the deliberate bump, same pattern as Phase 20).

## Limitations / future work

See `phase21_limitations.md`. Headlines: no pit-loss channel; small-N
fallback skips setup/pit/pace offsets; strategy policies and forced RC events
unsupported; pre-2023 tyre inert; magnitudes prior-only.

## Self-audit (§49, 13 points)

1. Architecture inspected before change ✓ 2. Call graph: every family traced
   to kernel/engine lines, tested ✓ 3. Baseline preservation 1e-12 ✓
4. Propagation per family measured ✓ 5. Leakage adversarial ✓ 6. Determinism
   multi-N ✓ 7. RNG isolation (no scenario RNG; CRN) ✓ 8. Fingerprint ✓
9. Provenance ✓ 10. Multi-intervention isolation (conflicts rejected;
   A→B clean) ✓ 11. Monte Carlo behavior (CRN, granularity noted) ✓
12. Performance measured ✓ 13. Docs match code (paths/keys/tiers verified) ✓.
One-parameter change → rerun → observed distribution change: YES (7/7 families).

```
PHASE_21_STATUS = COMPLETE_WITH_LIMITATIONS
```
