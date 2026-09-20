# Phase 22 — Replay Model

*Factual. Scientific integrity over presentation. Every claim is grounded in the current codebase.*

## 1. Purpose

Turn the Phase 21 scenario system into a trustworthy **Historical Replay + Counterfactual Experiment Engine** that answers:

> "Under the model assumptions and available evidence, the simulated distribution changes by X"

never:

> "this definitely would have happened".

## 2. Architecture (new package `app/simulation/replay/`)

```
replay/
  __init__.py          — REPLAY/COUNTERFACTUAL/SENSITIVITY versions (replay-v1.0.0)
  models.py            — Pydantic contracts: HistoricalRace, HistoricalObservationState,
                         ReplayResult, CounterfactualExperiment, CRNManifest,
                         InterventionAttribution, ExtendedComparison, SensitivityResult,
                         SanityCheck, CounterfactualExperiment
  state_builder.py     — canonical races/results -> HistoricalRace with strict as_of
  historical_observer.py — HistoricalObservationState at lap t (lap 0 = pre-race)
  checkpoints.py       — valid_checkpoints() + checkpoint_lap() mapping
  replay_engine.py     — ReplayEngine: baseline replay + counterfactual replay (CRN)
  comparison.py        — extended_compare() (Phase 21 + top10/P10/P90/relative + pit-counts)
  attribution.py       — model-attributed InterventionAttribution (never real-world causal)
  sensitivity.py       — SensitivityEngine (OFAT + bounded 2-axis grids, capped at 25 cells)
  sanity.py            — 6 monotonicity / physical sanity checks
  validation.py        — deviation_metrics(), walk_forward(), leakage_probe()
  provenance.py        — model_versions(), dataset_hash(), experiment_fingerprint()
  artifacts.py         — machine artifact + markdown report writers
```

Reuses without duplication:

- `ScenarioEngine`, `ScenarioSpec`, `Intervention`, `InterventionTrace`, `ScenarioComparison`, `ScenarioExplanation`
- `SetupEngine`, `StrategyEngine`, `WeatherEngine`, `RaceControlEngine`, `TyreEngine`
- `BatchRNG`, `VectorizedMonteCarlo`, `is_setup_enabled`, `setup_offsets_for_scenario`
- `race_engine_v21.py` -> `race_engine_v22.py` is a thin provenance layer (no dynamics change except the explicitly versioned `strategy.pit_loss_seconds` channel, default 0 = legacy exact)
- `scenario_v14.TemporalContext`, `calibration_state.build_calibration_state`

Version lineage (new in Phase 22):

```
SIMULATION_VERSION  9.1.0 -> 9.2.0
RACEENGINE_VERSION  raceengine-v2.1.0 -> raceengine-v2.2.0
MODEL_VERSION       0.8.0 -> 0.9.0
STRATEGY_MODEL_VERSION strategy-v1.0.0 -> strategy-v1.1.0 (pit_loss_seconds, default 0)
REPLAY_MODEL_VERSION       replay-v1.0.0 (new)
COUNTERFACTUAL_MODEL_VERSION counterfactual-v1.0.0 (new)
SENSITIVITY_MODEL_VERSION  sensitivity-v1.0.0 (new)
```

## 3. Historical observation contract

`HistoricalObservationState` contains **only** information available at time `t`:

```
race_id, season, round, lap, position, gap, tyre_state/age,
weather_current, weather_forecast_summary, race_control_phase,
sector_flags, fuel_state if identifiable, driver/constructor pace estimates,
pit_history_observed_until_t, incident_history_observed_until_t,
strategy_state, setup_state if actually available
```

Each field: `ObservedValue { value, source, evidence_tier, observation_timestamp, as_of }`.

- No historical weather, setup, fuel, strategy, tyre compounds, lap-by-lap pits/incidents exist at the required granularity in the canonical dataset -> `None + NON_IDENTIFIABLE` under `historical_observer.build_observation(lap>0)` rather than fabricated reconstruction.
- Pre-race pace estimates where available are `calibration_api(as_of)` with `LIMITED` tier; unavailable drivers stay `NON_IDENTIFIABLE`.
- The realized result is **never** copied into the scenario: `HistoricalRace.observed_result` is a post-hoc validation target (`observed_result_validation_only=True`), and `build_scenario_for_race()` asserts `final_position` never appears in the scenario JSON.

`as_of` is always `race_date - 1 day` (strict_before), derived in `state_builder.as_of_for_race_date()` and threaded through `Scenario.temporal_context` -> `CalibrationState`.

## 4. Replay checkpoints

Defined names: `pre_race, formation, lap_1, lap_5, lap_10, lap_20, lap_30, lap_40, lap_50, finish` plus arbitrary `checkpoint(lap=N)`. `valid_checkpoints(total_laps)` filters to laps actually valid for the race length (e.g. 6-lap shortened legs produce `[pre_race, lap_1, lap_5, finish]`). Each checkpoint is an independent truncated-horizon simulation from the pre-race information (no state carried); determinism is inherited from the underlying engine.

## 5. Baseline replay

`ReplayEngine.replay(race_id, seed, simulations, laps, with_checkpoints)`:

- loads `HistoricalRace` (canonical, no invention),
- builds a pre-race `Scenario` (observed result excluded),
- runs one vectorized leg at `seed` (or sequential fallback at `N<50`),
- optionally runs truncated legs for each valid checkpoint,
- returns `ReplayResult { race_id, seed, simulations, laps, baseline_fingerprint, checkpoint_results, deviation_metrics, observed_result, provenance, evidence_summary }`.

The objective is **not** exact historical reproduction: the model may diverge. Divergence is reported honestly in `DeviationMetrics` (post-hoc, never an input).

## 6. Counterfactual replay

`ReplayEngine.counterfactual(race_id, interventions, ...)` =

```
HistoricalRace -> baseline Scenario -> compile_spec -> CRN legs (same seed) ->
ExtendedComparison + InterventionAttribution + CRNManifest + fingerprint
```

Only the requested intervention differs; all other components share the same seed / sim index / isolated exogenous streams (see CRN section). `intervention_hash` and `spec` order-sensitivity are covered by the fingerprint.

## 7. Evidence tiers

Every field carries one of: `CALIBRATED` (actual leakage-safe calibration dataset) | `LIMITED` (partial observations) | `PRIOR_ONLY` (model prior, no direct calibration) | `NON_IDENTIFIABLE` (cannot be identified) | `NOT_TESTABLE` (no mechanism). Phase 22 never invents `CALIBRATED`; all setup/strategy/tyre/weather/race-control magnitudes remain `PRIOR_ONLY` unless stated.

## 8. Known gaps vs the written specification

- No live telemetry `position/gap` field in `HistoricalObservationState` is populated from data (no such source at per-lap granularity) -> reported as `NON_IDENTIFIABLE`.
- Walk-forward sample is small (6 x 2024 races + 12 x 2024 at shortened horizons) rather than 1950-present: earlier eras lack the tyre-model support for strategy interventions to propagate and would be horizon-inert; sweeping all eras at `N=1000/10000` x 58 laps would cost hours and was deferred to a nightly job.
- Pre-race total_laps is `NON_IDENTIFIABLE` for at least `2024-bahrain` (`scheduled_laps=null`); legs fall back to the engine default `58` with the tier recorded.

## 9. Files

- `backend/app/simulation/replay/` (13 modules, ~1.6k lines)
- `backend/app/simulation/scenario/registry.py` (+ pit-loss channel)
- `backend/app/simulation/scenario/validation.py` (+ pit_loss_seconds bounds)
- `backend/app/simulation/scenario/compiler.py` (+ _apply pit_loss_seconds)
- `backend/app/simulation/scenario/resolvers.py` (+ resolve_pit_loss)
- `backend/app/simulation/performance/vectorized_montecarlo.py` (+ deterministic per-stop pit loss)
- `backend/app/simulation/race_engine_v22.py` (new thin layer)
- `backend/app/simulation/version.py` (bumped per section 2)
