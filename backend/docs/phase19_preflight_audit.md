# Phase 19 Preflight Audit — Advanced Strategy & Decision Engine

**Date:** 2026-09-17
**Model Version (pre):** 0.5.0 / SIM 8.4.0 / raceengine-v1.4.0
**Dataset:** f1-dataset-v1.1 (races 2cce529c, results 112c8475, tyre 503079ee)
**Calibration:** calibration-v1.0.0 driver 3df26222

## 1. Existing Strategy Architecture

| File | Class | Responsibility | Evidence Tier |
|------|-------|----------------|---------------|
| `strategy/engine.py` | `StrategyEngine`, `StrategyContext`, `StintPlan` | Generate `StrategyOption` via brute-force stint combinations, estimate stint lap times via tyre deg + fuel + track evolution, rank by `total_estimated_time + risk*0.1` | PRIOR_ONLY (deg multipliers 1.5x cliff not calibrated) |
| `strategy/evaluator.py` | `StrategyEvaluator`, `StrategyComparison`, `StrategyRecommendation`, `LiveStrategyAdvisor` | Compare options, recommend with reasoning, contingencies, Monte Carlo `simulate_strategy_battle` (adds N(0,0.3) per stint + random SC) | PRIOR_ONLY (SC effect uniform -5..5 not calibrated) |
| `strategy/pitstop.py` | `PitStopStrategyEngine`, `PitStopDecision`, `PitWindow`, `UndercutAnalysis`, `OvercutAnalysis` | Real-time pit decision, undercut/overcut analysis via pace estimates `target_old - attacker_fresh`, pit loss via `estimate_pit_stop_loss` | PRIOR_ONLY (pace estimates use 90s base, not per-track) |
| `strategy/fuel.py` | `FuelStrategyOptimizer`, `AdaptiveFuelManager`, `EngineMode` | Fuel per stint, engine modes rich/standard/lean/overtake/harvest with fuel/pace/deg multipliers | PRIOR_ONLY |
| `strategy/team_orders.py` | `TeamOrderModel` | HOLD_POSITION etc. | PRIOR_ONLY |
| `models/strategy.py` | `RaceStrategy`, `StrategyOption`, `StrategyEvaluation`, `PitStopModel` | DTOs; `PitStopModel.calculate_stop_time` with `base 2.4s +-0.15` and 2% issue | PRIOR_ONLY |
| `core/race_engine.py` | `RaceEngine.simulate_race` | Initializes driver strategies via even-split heuristic for >10 laps, else `generate_strategy_options(max_stops=2)`; calls `PitStopStrategyEngine.make_pit_decision` per lap with `forecast_rain`, `safety_car_active` | PRIOR_ONLY; gap 2.0s candidate scope |
| `performance/vectorized_montecarlo.py` | `VectorizedMonteCarlo.run` | Every 20 laps reset tyre age (pit) — no strategy; pit is fixed schedule not decision-driven | Simplified |

**Total lines:** ~1800 for strategy logic.

## 2. Existing Interfaces

```python
StrategyContext(track, car, engine, driver, race_laps, pit_lane_time_loss, available_compounds, starting_compound, starting_fuel_kg, fuel_tank_capacity, team_pit_skill, weather_forecast, safety_car_probability, track_evolution_rate)
StrategyEngine.generate_strategy_options(context, max_stops, min_stint_laps, max_stint_laps) -> list[StrategyOption]
StrategyEngine.rank_strategies(options, context) -> list[(Option, score)]
StrategyEngine.evaluate_strategy(option, context) -> StrategyEvaluation
PitStopStrategyEngine.make_pit_decision(driver_state dict, strategy RaceStrategy, competitors list, track_pit_lane_loss, laps_remaining, safety_car_active, safety_car_probability, weather_change_imminent) -> PitStopDecision
PitStopStrategyEngine.calculate_pit_window(...) -> PitWindow
PitStopStrategyEngine.analyze_undercut(...) -> UndercutAnalysis
PitStopStrategyEngine.analyze_overcut(...) -> OvercutAnalysis
RaceEngine._initialize_driver_strategies(...), _handle_pit_stops_with_strategy(...), _process_racing_dynamics(...)
BatchState.positions (N,D), times (N,D), tyre_age (N,D), weather_wetness (N,), race_control_phase (N,) / traj (N,L)
```

## 3. Reusable Components (MUST reuse)

* `StrategyEngine._spec_for`, `_optimal_laps`, `_estimate_stint_lap_times`, `_estimate_base_lap_time` — tyre compound logic
* `TyreCompounds` & `TyreSpec` via `get_standard_tyre_specs` + calibrated `beta_soft/medium/hard` via `tyre/calibration.py:calibrate_degradation`
* `WeatherState`, `WeatherTransition`, `ForecastUncertainty` via `weather/*` (already isolated RNG 500)
* `RaceControlEngine`, `RaceControlPolicy`, `NeutralisationFactors` via `race_control/*` (RNG 600, (N,L) phase)
* `TrackOvertakeMap`, `BattleEngine`, `DirtyAirModel` — gap/battle
* `PitStopModel`, `estimate_pit_stop_loss` — physical pit duration
* `RandomProvider.get_stream(name)` — deterministic streams
* `Scenario` + `TemporalContext` strict_before
* `VectorizedMonteCarlo.base_pace + AR1 + tyre+weather+RC` pipeline

## 4. Components that MUST NOT be duplicated

* Tyre degradation `beta` loading — must go through `tyre/calibration` not hard-code SOFT -0.07 stale.
* Weather intensity/regime/transition — must reuse `weather/state+transition` not reimplement.
* Race control state machine / policy — reuse `race_control/state_machine` + `policy` not duplicate thresholds.
* Pit stop physical loss — reuse `models/strategy.PitStopModel` not reimplement.
* RNG streams — reuse `core/random` + `race_control/rng` offset scheme not duplicate global RNG.

## 5. Leakage Risks

| Risk | Location | Mitigation |
|------|----------|------------|
| Future weather `weather_wetness_traj[:, lap+1:]` visible to strategy | `vectorized_montecarlo` has full trajectory available in memory | Strategy DecisionEngine must accept only `wetness_current` not full array; expose forecast via `ForecastUncertainty` with noise |
| Future race control `race_phase_traj[:, lap+1:]` | Same (N,L) array pre-generated | Only pass `phase_current` (N,) per lap; never pass full traj to decision |
| Future tyre `tyre_age` evolution | Could precompute tyre effects | Strategy estimates via `_estimate_stint_lap_times` using current age + prior, not future realized wear |
| Opponent future pit | Competitor list currently gaps only at t | Opponent model must be `P(pit_next)`, not actual future pit lap |
| Global RNG reuse | `StrategyEngine.rng` currently single `default_rng()` not seeded | Replace with isolated `strategy` stream per `seed + sim_idx*1000 + 700` |
| Forecast perfect | `weather_model.generate_forecast` is base forecast + noise (good) | Keep; do not give strategy `traj` |

## 6. Performance Risks

* `StrategyEngine.generate_strategy_options` brute-forces `O(compounds^stints * modes^stints)` exponential in laps — already limited in `RaceEngine` via heuristic for >10 laps (even-split). Candidate generation must remain bounded.
* Evaluating each candidate with `evaluate_strategy` loops over stints; with 20 laps and 3-stop, number of candidates ~200+ per driver → at N=10k D=20 would be 40M evaluations if naïve → must vectorize or pre-prune.
* Monte Carlo undercut Monte Carlo `simulate_strategy_battle` with 100 sims per battle would be heavy; use analytic approximation where possible.
* BatchState (N,D)=200k floats fine; (N,D,L)=11M would be 44MB float32 (tolerable) but (N,candidates,D) blow up. Must keep candidates per-driver not per-sim tensor.

**Mitigation:** Generate candidates per driver once (invariant), evaluate with vectorized tyre/weather/RC factors broadcast per sim, rank with coarse model, deep-evaluate top-K (K=5) only.

## 7. Missing Inputs (must add or mark NON_IDENTIFIABLE)

| Required by spec | Exists? | Action |
|------------------|---------|--------|
| `gap_ahead/behind` per driver per lap | Exists in `DriverState.gap_ahead` and `BatchState` via `times` sort | Reuse |
| `fuel_remaining` per driver | `DriverState.fuel_mass` exists | Reuse |
| `tyre_age` | Exists `DriverState.tyre_age` / `BatchState.tyre_age` | Reuse |
| `current_compound` | Exists | Reuse |
| `race_control_phase` | Exists `RaceState.race_state` + `BatchState.race_control_phase` | Reuse |
| `sector_flags` | Exists `race_control_sector` (N,L,S) | Wire |
| `wetness/rainfall/track_temp` | Exists `WeatherState` / `BatchState.weather_*` | Wire |
| `forecast_summary/uncertainty` | Exists `ForecastUncertainty` but not wired to strategy per lap | Wire via `track_wetness_model` forecast representation |
| `pit_loss_estimate` | Exists `estimate_pit_stop_loss` | Reuse |
| `opponent_states` observable | Exists via gap + competitor dict but not consolidated | Create `OpponentState` view |
| `degradation estimate` | `tyre deg` exists but not exposed as state | Expose via `tyre_effect_kernel` beta |
| `stint_index` | Not explicit | Add |

Mark unavailable as `PRIOR_ONLY` or `NON_IDENTIFIABLE` not fabricated.

## 8. Existing Evidence Tiers

* Driver pace std `1.5` inflated 1.5× if sample<3
* Constructor pace std 1.5
* Tyre degradation beta: modern 2023-2024 SOFT -0.2229 ±0.038, HARD -0.20185 ±0.024 CALIBRATED (>=30 obs), MEDIUM PRIOR_ONLY
* Weather: many vars NON_IDENTIFIABLE pre-2023, LIMITED modern, wet PRIOR_ONLY
* Race control: all PRIOR_ONLY
* Strategy risk/sensitivity: PRIOR_ONLY

Must preserve.

## 9. Recommended Integration Points

1. **Sequential path (`RaceEngine.simulate_race`):** Replace even-split heuristic + `PitStopStrategyEngine.make_pit_decision` with new `DecisionEngine.decide(StrategyState at lap t)` that returns `action ∈ {CONTINUE, PIT_TO_X}` with explanation. Keep legacy `make_pit_decision` as fallback when `strategy_enabled=False`.
2. **Vectorized path (`VectorizedMonteCarlo.run`):** Pre-generate `StrategyState` per driver per lap? But vectorized currently has fixed every-20-laps pit. Instead inject strategy-evaluated pit schedule per driver per sim: generate candidate set per driver once, evaluate expected `total_estimated_time + race_control_pit_factors`, pick per-sim via sampled noise (strategy RNG 700) → yields `pit_laps` array (N,D) variable not fixed 20. Requires `pit_window` per sim.
3. **Calibration loading:** `StrategyState.estimated_degradation` must call `load_tyre_observations` via `as_of` not hard-code SOFT +0.07 stale (removed in Phase 16).
4. **Versioning:** Add `STRATEGY_MODEL_VERSION = "strategy-v1.0.0"` to `version.py`, include in `provenance`.
5. **Provenance:** `RaceEngine` reproducibility should list `strategy_model_version`, `strategy_enabled`, `strategy_seed`.

## 10. Exact Implementation Plan

**Module layout (smallest fitting existing repo):**

```
strategy/
  __init__.py          # re-export + version
  state.py             # StrategyState immutable dataclass (leakage-safe view)
  actions.py           # StrategyAction Enum + PitAction, ContinueAction etc. serializable
  candidates.py        # CandidateGenerator (pruned, respects race length, compounds, SC/VSC, tyre age)
  pit_window.py        # PitWindowEngine (earliest/preferred/latest, SC/VSC aware)
  tyre_strategy.py     # TyreStrategyEngine (uses calibrated beta, uncertainty)
  weather_strategy.py  # WeatherStrategy (forecast-aware, crossover, PRIOR_ONLY)
  race_control_strategy.py # RaceControlStrategy (VSC/SC/RED/RESTART logic)
  opponent_model.py    # OpponentModel lightweight P(pit_next)
  evaluator.py         # (extend existing) add distributions via Monte Carlo of tyre/weather/RC
  decision_engine.py   # DecisionEngine.decide(state) + compare_strategies API + RNG isolation 700
  explanation.py       # ExplanationEngine (derive reasons from evaluator inputs)
  rng.py               # STRATEGY_RNG_OFFSET = 700
```

**Steps:**

 1. Create `strategy/rng.py` offset 700, `strategy/state.py` with `Known/Estimated tiers`, `strategy/actions.py`.
 2. Create `candidates.py` reusing `StrategyEngine._generate_stint_combinations` but capped and leaking-safe.
 3. Create `pit_window.py` reusing `PitStopStrategyEngine.calculate_pit_window` but extending with degradation + RC + weather.
 4. Create `tyre_strategy.py`, `weather_strategy.py`, `race_control_strategy.py` thin wrappers around existing models, exposing `evidence_tier`.
 5. Create `opponent_model.py` prior-only `Beta(2,20)` ~10% pit next lap.
 6. Extend `evaluator.py` to return `StrategyEvaluation` with distributions `finish_position_distribution`, `race_time_distribution` via vectorized tyre/weather/RC factors + `opponent_model`.
 7. Create `decision_engine.py` with `decide(state)` returning `Decision` dataclass with `chosen_action`, `candidates`, `uncertainty`, `reasoning`, `evidence_tier`, deterministic under isolated RNG, and `compare_strategies`/`evaluate_strategy` APIs for Phase 21.
 8. Wire into `RaceEngine`: add `strategy_enabled` flag to `SimulationConfig`, initialize `DecisionEngine` lazily, call per lap per driver (sequential) and per batch (vectorized via `pit_laps` array).
 9. Vectorized: generate per-driver candidate best per scenario via `CandidateGenerator` + `Evaluator` (once), then per-sim sample pit loss via strategy RNG to choose variation; handle SC opportunity via `race_phase_traj`.
10. Add provenance, bump `MODEL_VERSION 0.6.0`, `SIMULATION_VERSION 8.5.0`, `strategy-v1.0.0`.
11. Tests: models, candidates, pit windows, tyre, weather, RC, opponent, leakage (adversarial future weather/RC), RNG isolation, Monte Carlo, explanation, regression + backtesting via `as_of` walk-forward.
12. Docs + benchmarks (`N=100/1k/10k`) and ablation (strategy disabled vs tyre-only etc.).

**Verification:** `pytest -q` 440 must stay passing (baseline tolerance), new ~50 tests added.
