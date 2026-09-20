# Phase 20 Completion Report — Car Setup & Vehicle Configuration Engine

*Generated 2026-09-17. All statements verified against code and test runs.*

## Architecture

Created `backend/app/simulation/setup/`:
- `__init__.py` — re-exports + `SETUP_MODEL_VERSION = setup-v1.0.0`
- `models.py` — `EvidenceTier` (5 levels), `ConstraintType` (4),
  `SetupMode` (4), `ParameterEvidence`, `SetupParameter`, `SetupParameters`
  (18 params), `SetupConstraints`, `SetupEffects` (12 effect channels + 5
  track factors + 3 evidence blocks), `SetupEvidence`, `SetupState`,
  `create_baseline_setup`, `create_setup_from_dict`, `get_era_constraints`
- `engine.py` — `SetupCoefficients`, `get_default_coefficients`,
  `get_track_modifiers` (sector-sum straight share, corner shares, energies;
  does NOT use inverted `get_track_type_category`), `SetupEngine`
  (`compute_effects`, `compute_lap_time_delta`, `apply_to_car`,
  `get_effect_evidence_summary`), `compute_setup_effects`
- `validator.py` — `SetupValidator`, `ValidationResult` (bounds, era
  constraints, step alignment, cross-parameter + track warnings, clamp)
- `fingerprint.py` — `setup_fingerprint` (16-hex sha256), full/scenario
  variants, `verify_fingerprint` (TYPE_CHECKING import, no cycles)
- `integration.py` — `SetupAwareLapTimeModel`
  (`calculate_lap_time_with_setup`, parent-call without recursion),
  `create_setup_aware_inputs`, `compute_setup_lap_time_delta`
- `offsets.py` — `setup_offsets_for_scenario`, `setup_states_for_scenario`,
  `setup_fingerprints_for_scenario`, `is_setup_enabled` (global + per-driver
  modifiers, validate-and-clamp, deterministic)

Modified (additive only):
- `simulation/race_engine_v20.py` (new) — `SetupAwareRaceEngine` extends v19;
  resolves flags, delegates simulation, attaches real per-driver
  fingerprints/offsets/evidence (no placeholders).
- `simulation/performance/vectorized_montecarlo.py` — setup offsets block
  (deterministic `(D,)` broadcast add per lap) + `setup` result block +
  provenance keys (`setup_model_version`, `setup_enabled`,
  `setup_fingerprints`). Zero-offset when disabled/baseline → legacy intact.
- `simulation/version.py` — `SETUP_MODEL_VERSION setup-v1.0.0`,
  `MODEL_VERSION 0.7.0`, `SIMULATION_VERSION 9.0.0`,
  `RACEENGINE_VERSION raceengine-v2.0.0`.
- `tests/test_phase18_race_control.py`, `tests/test_phase19_strategy.py` —
  version gates widened to accept Phase 20 values (logic unchanged).
- `scripts/phase20_benchmark.py` (new), `tests/test_phase20_setup.py` (new).

## Integration (existing paths only)

```
Scenario.hypothetical_modifiers["setup"]
  → offsets.py → per-driver sec/lap
  → VectorizedMonteCarlo lap_times += setup_vec   (production, N≥50)
  → drivers/constructors/provenance/setup blocks
SetupState → SetupEngine → SetupEffects → adjusted Car
  → SetupAwareLapTimeModel (sequential/analytical path)
```
Strategy/race-control/weather/tyre trajectories are NOT directly modified by
setup (emergent interaction only). Small-N fallback (N<50) does not apply
offsets (documented).

## Parameters (18)

front_wing, rear_wing, ride_height_front/rear, front/rear_anti_roll,
front/rear_spring, brake_bias, diff_entry/mid/exit, front/rear_camber,
front/rear_toe, tyre_pressure_front/rear. Ranges in model doc §2.

## Evidence

- CALIBRATED: none (setup).  - LIMITED: none (setup).
- PRIOR_ONLY: all aero/mechanical/track/lap-mapping coefficients and all
  parameters except tyre pressures.
- NON_IDENTIFIABLE: tyre pressures, all tyre-interaction effects, historical
  setup values.
- NOT_AVAILABLE: strategy consumption of setup, sector-level setup, regulation
  engine, small-N offsets, autodiff.
Per-parameter table in `phase20_setup_data_and_evidence.md`.

## Historical data

No setup fields exist in `data/canonical` or sources. Statement:
**Historical setup values are not identifiable from the current dataset.**
Historical mode uses neutral baseline, labeled PRIOR_ONLY with limitations.
Nothing is inferred from results/positions/teams/circuits.

## Counterfactual support

Global `parameters` + per-driver `drivers.{id}` overrides with
`mode: counterfactual`; outputs: per-driver offsets, fingerprints, moved
distributions, evidence tier. Reported as model-implied (prior-only).

## Sensitivity support

Discrete perturbation via `create_setup_from_dict(baseline ± delta)`
+ `get_baseline_deviation` + fingerprint diff + offset/lap-delta compare.
No autodiff (not justified). Ready for Phase 24 sweeps.

## Leakage

Historical uses baseline only; counterfactuals explicitly labeled; strategy
receives no setup fields; `as_of` carried for Phase 21. 2 adversarial tests
pass; full prior leakage suites (Phases 13/14/17/18/19) still pass.

## Determinism

Same seed + same setup → identical win probs (1e-12, N=60/100). Setup
change → different fingerprint + moved expected_finish. Baseline fingerprint
reproduces across runs. RNG streams (500/600/700/100) untouched; setup uses
no RNG.

## Performance (measured, Bahrain 8 laps, N=1000, seed 42)

legacy-v19 12.88s (cold fastf1 cache) / v20-disabled 8.78s /
v20-baseline 8.88s / v20-modified 8.90s → setup overhead ≈1%.
Memory: `(D,)` offsets + fingerprints; no `(N,D,L,P)` tensors.

## Tests

- Prior: 489 passed, 0 failed (87 + 68 + 334 in three runs above).
- New: 38 passed, 0 failed.  - Total: 527 passed, 0 failed, 0 skipped.
- No test logic weakened (2 version gates widened for new versions only).

## Limitations / future research

See `phase20_setup_limitations.md`. Headlines: magnitudes are priors;
linear/additive effects; no couplings/cliffs; track modifiers unvalidated;
no team-specific maps; saturation by clamping; strategy/sector/regulation/
small-N/autodiff deferred to Phases 21–24.

## Verification (§42)

1. Repo inspection — done (§0 items 1–9). 2. Implementation — above.
3. Tests — 527 pass. 4. Call-path — vectorized offsets move
expected_finish; lap-model moves total (both tested). 5. Leakage — §above.
6. Determinism — 1e-12 repeats. 7. Fingerprint — changes/reproduces.
8. Provenance — per-driver fingerprints + offsets + tiers in result.
9. Ablation — OFF/baseline/aero/mech/per-driver matrix moves as claimed
(except strategy←setup, documented unwired). 10. Performance — measured.
11. Doc/code consistency — this report matches code as of this run.

```
PHASE_20_STATUS = COMPLETE_WITH_LIMITATIONS
```
(Limitations are the evidenced prior-only/non-identifiable scope above;
no blockers, no fake integrations, no fabrication.)
