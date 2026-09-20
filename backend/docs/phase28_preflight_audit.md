# Phase 28 Preflight Audit

Generated: 2026-09-20
Dataset: f1-dataset-v1.3  ~552,656 laps / 1,172 races / 12,747 pit stops

## 1. Existing Service Abstractions
- `app/services/` empty (0 bytes), `app/schemas/` empty, `app/domain/` empty, `app/repositories/` empty
- Business logic lives in `app/simulation/` and `app/data/` — no duplicate abstraction needed
- No existing API schemas beyond `app/api/v1/endpoints/health.py:HealthResponse`

## 2. Existing Pydantic Schemas
- `app/simulation/core/state.py:SimulationConfig` — full race config (seed, track_id, total_laps, weather, pit, fuel, tyre, safety_car, vsc, incident, Phase7 env, Phase8 procedure, Phase18 race_control, Phase19 strategy)
- `app/simulation/core/state.py:RaceResult, DriverResult, DriverState, RaceState`
- `app/simulation/models/driver.py:Driver`, `car.py:Car/Engine`, `track.py:Track`, `tyre.py:TyreSpec`, `weather.py:WeatherState`
- `app/simulation/scenario/models.py:Intervention, ScenarioSpec, ScenarioResult`
- `app/simulation/replay/models.py:HistoricalRace, ReplayResult, CounterfactualExperiment`
- `app/simulation/strategy/state.py:StrategyState`, `strategy/decision_engine.py:DecisionOutput`

Reuse these types directly — do not duplicate.

## 3. Engine Constructors
- `RaceEngine` (`app/simulation/core/race_engine.py:103`): no args, lazy-init in `simulate_race(config, drivers, cars, track, rng, engines=None) -> RaceResult`
- `RandomProvider(seed)` (`core/random.py:14`) with `get_stream(name)` isolated via `hash((seed,name)) & 0xFFFFFFFF`
- `VectorizedMonteCarlo(calibration_state, scenario, seed)` (`performance/vectorized_montecarlo.py:24`) -> `run(simulations) -> dict`
- `ScenarioEngine(seed, simulations)` (`scenario/engine.py`) -> `run_baseline / run_counterfactual / run_spec`
- `ReplayEngine(seed, simulations)` (`replay/replay_engine.py:37`) -> `replay(race_id, seed, simulations, laps)`, `counterfactual(race_id, interventions...)`, `checkpoint(race_id, lap, ...)`
- `DecisionEngine(as_of, seed, max_candidates)` (`strategy/decision_engine.py:102`) -> `decide(state, track_pit_loss, seed, sim_idx) -> DecisionOutput`
- `SetupEngine`, `WeatherEngine`, `RaceControlEngine` — lazy inside RaceEngine / Vectorized
- `Scenario` built via `app/simulation/replay/state_builder.py:build_scenario_for_race(hrace, laps)`
- `HistoricalRace` loaded via `load_historical_race(race_id)` from `data/canonical/races.json`

## 4. Monte Carlo Interfaces
- Vectorized path is production. Do NOT create (N,D,L) tensors. Uses `BatchState(N,D)` with `(N,D)` arrays + `(N,L)` weather/RC trajectories shared across drivers.
- RNG contracts: Level A `seed+sim_idx*1000` for base_pace/qualifying/reliability; Level B `seed+100+lap` for AR1; offset 700 for strategy; isolated streams for weather/RC.

## 5. Scenario Interfaces
- Allowlist in `scenario/registry.py`: families setup/strategy/tyre/race_control/weather/driver/car, ops per family, bounds, `LEAKAGE_SUBSTRINGS`, `STRUCTURAL_FIELDS`
- Validation in `scenario/validation.py:validate_spec / validate_intervention` — raises `ScenarioValidationError`
- Compilation deterministic via `scenario/compiler.py:compile_spec`
- Resolver helpers: `scenario/resolvers.py:resolve_pace_deltas, resolve_pit_schedule, resolve_pit_loss`

## 6. Replay Interfaces
- Checkpoints: `replay/checkpoints.py:valid_checkpoints(total_laps)` -> `pre_race, lap_1/5/10/.../finish` via `checkpoint_lap`
- Replay returns `ReplayResult.checkpoint_results` (truncated horizon legs) + `deviation_metrics` + provenance
- Counterfactual via `ReplayEngine.counterfactual` with `CRNManifest` (same seed both legs)

## 7. Provenance / Version Structures
- `app/simulation/version.py`: SIMULATION_VERSION 9.2.0, RACEENGINE v2.2.0, MODEL 0.9.0, SCENARIO v1.0.0, REPLAY v1.0.0, WEATHER v1.0.0, RACE_CONTROL v1.0.0, STRATEGY v1.1.0, SETUP v1.0.0, CONFIG 1.0.0
- `replay/provenance.py:build_experiment_provenance, experiment_fingerprint, model_versions()`
- `RaceResult.reproducibility` dict, `simulation_version`, `config_version`

## 8. Error Handling Conventions
- No structured API errors exist. Scenarios raise `ScenarioValidationError(ValueError)`. Replay raises `ValueError` for unknown race.
- No global exception handlers, no error codes. Must create structured error model for Phase 28.

## 9. Track / Race Discovery
- `app/simulation/models/track.py:get_2024_calendar()` returns 6 hard-coded tracks (bahrain, saudi_arabia, australia, monaco, spain, monza)
- `app/data/catalog.py:SourceCatalog` + `default_catalog()` for field priorities, not for race listing
- Canonical `data/canonical/races.json` + `results.json` + `state_builder.load_historical_race` is source of truth for discovery (do not load fully per-request; cache metadata)
- `data/canonical/races.json` contains ~1,172 races with race_id, season_id, round, circuit_id, date

## 10. Calibration / Evidence Tiers
- Production: calibration-v1.0.0, tyre-v1.0.0, weather-v1.0.0, racecontrol-v1.0.0, strategy-v1.1.0, setup-v1.0.0, raceengine-v2.2.0, dataset f1-dataset-v1.3
- Tiers: CALIBRATED/LIMITED/PRIOR_ONLY/NON_IDENTIFIABLE — Phase 27 retained production, candidates not promoted
- Fuel NON_IDENTIFIABLE, tyre historical NON_IDENTIFIABLE, setup PRIOR_ONLY, strategy PRIOR_ONLY, weather/RC PRIOR_ONLY, driver/circuit LIMITED

## 11. Existing Tests
- `tests/test_race_engine.py` deterministic race, `test_random_provider.py` seed isolation
- Phase tests: `test_phase16_tyre`, `test_phase17_weather`, `test_phase18_race_control`, `test_phase19_strategy`, `test_phase20_setup`, `test_phase21_scenario`, `test_phase22_replay|leakage|provenance|sanity|sensitivity|...`
- `test_phase22_leakage` expects zero leakage via blocklist. Must preserve.

## 12. Gaps / Risks for Phase 28
- Only `GET /api/v1/health` exists; all other endpoints missing
- No request validation beyond Pydantic on SimulationConfig
- No limits on N (DoS via Monte Carlo), no request size limits
- No simulation store for `GET /simulation/{id}`
- Frontend placeholders — not blocking API but must remain functional
- Need thin service layer delegating to existing engines, not duplicating logic

## 13. Decision
- Create `app/api/v1/schemas.py` for API schemas, `app/services/` thin wrappers, `app/core/errors.py` for structured errors
- Endpoints: metadata, races, simulate/race, simulate/monte-carlo, strategy/evaluate, scenario/compare, replay, simulation
- Reuse `RandomProvider`, `RaceEngine`, `VectorizedMonteCarlo`, `DecisionEngine`, `ReplayEngine`, `ScenarioEngine`, registry/validation directly
- In-memory store for simulation results (no Redis)
- Hard limits: Monte Carlo max 5000 (configurable), race laps 1-100, seed int32 range
- Security: no filesystem paths from client, no eval/exec, Pydantic validation, CORS retained from settings
