# Phase 20 Setup Model — Car Setup & Vehicle Configuration Engine

**Version:** `setup-v1.0.0`, `MODEL_VERSION 0.7.0`, `SIMULATION_VERSION 9.0.0`, `raceengine-v2.0.0`
**Status:** Modular, deterministic, PRIOR_ONLY unless stated, integrated into vectorized + lap-time paths.

## 1. Architecture

```
simulation/setup/
  __init__.py      # re-exports + SETUP_MODEL_VERSION
  models.py        # EvidenceTier, ConstraintType, SetupMode, SetupParameter,
                   # SetupParameters (18 params), SetupConstraints, SetupEffects,
                   # SetupEvidence, SetupState, create_baseline_setup,
                   # create_setup_from_dict, get_era_constraints
  engine.py        # SetupCoefficients, get_default_coefficients,
                   # get_track_modifiers, SetupEngine
                   # (compute_effects, compute_lap_time_delta, apply_to_car)
  validator.py     # SetupValidator, ValidationResult
  fingerprint.py   # setup_fingerprint, setup_fingerprint_full,
                   # scenario_fingerprint, verify_fingerprint
  integration.py   # SetupAwareLapTimeModel, create_setup_aware_inputs,
                   # compute_setup_lap_time_delta
  offsets.py       # setup_offsets_for_scenario, setup_states_for_scenario,
                   # setup_fingerprints_for_scenario, is_setup_enabled
```

Supporting changes (additive):
- `simulation/race_engine_v20.py` — `SetupAwareRaceEngine` (extends v19).
- `simulation/performance/vectorized_montecarlo.py` — per-driver setup offsets
  added to `lap_times` each lap; `setup` block in result + provenance keys.
- `simulation/version.py` — `SETUP_MODEL_VERSION`, `MODEL_VERSION 0.7.0`,
  `SIMULATION_VERSION 9.0.0`, `RACEENGINE_VERSION raceengine-v2.0.0`.

Smallest fitting architecture: no duplication of car/track/tyre/weather logic;
reuses `Car`, `Track`, `LapTimeModel`, `Scenario.hypothetical_modifiers`.

## 2. Parameters (18)

Aero: `front_wing` (1–10°), `rear_wing` (1–10°).
Ride/platform: `ride_height_front` (10–50mm), `ride_height_rear` (15–60mm).
Suspension: `front_anti_roll`, `rear_anti_roll`, `front_spring`, `rear_spring` (1–10 index).
Braking: `brake_bias` (50–65 %front).
Differential: `diff_entry`, `diff_mid`, `diff_exit` (0–100 %).
Geometry: `front_camber` (−5–−1°), `rear_camber` (−4–−0.5°),
`front_toe` (−0.5–0.5°), `rear_toe` (−0.2–0.5°).
Tyre: `tyre_pressure_front`, `tyre_pressure_rear` (18–28 psi).

Ranges are MODEL_PHYSICAL bounds, not historical regulations (see §5).

## 3. SetupState

```
setup_id, car_id, constructor_id, season, track_id,
parameters: SetupParameters,
constraints: SetupConstraints,
effects: SetupEffects | None,
evidence: SetupEvidence,
model_version (= setup-v1.0.0),
provenance {created_at, source, car_id, track_id, note},
mode: historical | counterfactual | hypothetical | future,
as_of: str | None,
fingerprint: 16-hex (sha256 of stable payload)
```

Serializable via `model_dump`; reproducible via fingerprint.

## 4. Effects (interpretable intermediates)

`SetupEffects`: `downforce_change`, `drag_change`, `aero_balance_change`,
`cornering_stiffness_change`, `traction_change`, `braking_stability_change`,
`ride_compliance_change`, `front/rear_tyre_load_change`,
`front/rear_tyre_deg_change`, `tyre_warmup_change` (all fractions vs baseline),
plus `track_*_factor` (5 track multipliers) and per-category evidence.

`SetupEngine.compute_effects(setup, car, track)`:
`effect = Σ (param − baseline) × coeff` (deterministic, no RNG).

`get_lap_time_contributions(base_lap_time)` (seconds, PRIOR_ONLY scale —
full wing sweep ≈ O(0.5–1.0s); small trims within noise):
- aero: `(-downforce×0.05 + drag×0.06) × base` (negative = faster)
- mechanical: `-(stiffness×0.03 + traction×0.02 + braking×0.015) × base`
- tyre: `(-load×0.01 + deg×0.02) × base` per axle

## 5. Constraints

`SetupConstraints.parameters[name] = {minimum, maximum, type, era?}`.
Types: `MODEL_PHYSICAL | REGULATORY | DATA_SUPPORTED | USER_DEFINED`.
Era preset: 2022–2026 raises ride-height minima (15/25mm); older eras keep
physical bounds. No modern regulations are back-projected as history —
regulatory detail is deferred to Phase 22; unknown status is reported as
warning/`UNKNOWN`, never invented.

## 6. Baseline

`create_baseline_setup()` = mid-range values (wing 5/5, RH 20/30,
ARB/spring 5, bias 55%, diffs 50%, cambers −3/−2, toes 0.1/0.2,
pressures 22/20). All effect deltas are exactly 0 → vectorized offsets are
exactly 0 → legacy behaviour preserved bit-for-bit in win probabilities
(tested at N=60, tolerance 1e-12).

## 7. RNG

No setup RNG stream: all transforms deterministic. Existing streams
(weather 500, race control 600, strategy 700, AR1 100) untouched.
Same seed + same setup → identical; same seed + changed setup → changed
offsets/fingerprints; setup disabled → legacy.
