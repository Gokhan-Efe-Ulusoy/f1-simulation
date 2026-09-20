# Phase 22 — Leakage

Strict contract: `training_observation_date < target_race_date` / `as_of = race_date - 1 day`. The following must never reach the decision layer: final result, final standings, future race-control events, realized future weather, future pits, future tyre state, future positions, future telemetry, future incidents. Future realized events may be used only as post-hoc validation targets.

## 1. Enforcement points

- `state_builder.as_of_for_race_date()`: always `race_date - 1 day`.
- `calibration_state.build_calibration_state()` -> `calibration_api*(as_of)` with `strict_before`.
- `scenario/registry.LEAKAGE_SUBSTRINGS` + `is_leakage_param()` block `future_*`, `actual_*`, `realized*`, `winner`, `podium_result`, `finishing_position`, etc. `validation.validate_intervention` rejects on match.
- `historical_observer.build_observation(lap)` explicitly documents each in-race history as `NON_IDENTIFIABLE` rather than fabricating it; `assert_no_future_fields()` audits the serialized observation for any forbidden token.
- `build_scenario_for_race()` never copies `observed_result` (monitored by the anti-double-count test `final_position not in blob`).

## 2. Adversarial probes (all pass)

- Validation rejects `future_result` / `actual_winner` / `finishing_position` / `observed_weather` at `validate_intervention` (tested: `test_phase21_scenario` + `test_phase22_leakage`).
- Hand-injected realized blocks (`future_result`, `realized_weather`, `realized_rain_lap10`, `observed_pit`, `final_standings`) into `hypothetical_modifiers` are inert: `leakage_probe()` runs a baseline vs dirty leg (same seed/N) and requires `max_abs_win_delta == 0.0` (1e-12) and `violations == []`. Verified at `N=60, seed 42`.
- Unknown `realized_*` weather keys are inert (weather engine only reads allowlisted initial-state fields).

## 3. Walk-forward validation

`validation.walk_forward(race_ids, seed, N, laps)` replays each race through the `as_of`-gated calibration API and records `training_end`, `target_date`, `observations_used`, `observations_excluded`, fingerprints. Sample (2024 `albert-park` through `monaco`, `N=60`, `laps=8`, seed 42) uses only the reproducible fixed set - not cherry-picked.

## 4. Historical replay validation sample

`scripts/phase22_walkforward.py` (`N=60`, shortened 8-lap horizon) on 2024 rounds 1-8 shows finite per-race `finish_mae` and stable `top3_overlap`; the model diverges from reality (reporting honest MAE) rather than being tuned to single races. Full 1950-present sweep would be multi-hour and is deferred to nightly ( tyres are inert pre-2023 anyway).

## 5. Coverage reporting

`DeviationMetrics.coverage` distinguishes `fully_observable` (grid, final positions, statuses), `partially_observable` (pit stops where canonical exists, qualifying), and `non_identifiable` (weather, setup, fuel, strategy, tyre, lap times). No aggregate is reported without coverage metadata.

## 6. Failures ("no leakage" is not an approximation)

`validation.check_spec()` raises `ScenarioValidationError` on any detected future token; `leakage_probe()` returns non-empty `violations` on any positive delta. Both are tested (see `test_phase22_leakage.py`).
