# Phase 15 Performance Audit — Baseline Architecture

**Date:** 2026-09-10  
**Engine:** `raceengine-v1.0.0` (`backend/app/simulation/race_engine_v14.py:1`)  
**Dataset:** `f1-dataset-v1.1` (1172 races, 26228 results)  
**Calibration:** `calibration-v1.0.0` (PARTIALLY_PROMOTED)  
**Seed:** `42`

## 1. Execution Path (Actual Implementation)

```
Scenario (HistoricalScenario → ScenarioResolver.from_historical)
  ↓ TemporalContext (as_of = race_date -1 day, strict_before)
HistoricalStateBuilder.build() → {drivers, grid_order, circuit_id, era}
  ↓ CalibrationState (per-driver get_driver_performance, get_circuit_effect, etc.)
  → drivers: {pace, qualifying, reliability Beta, overtaking, uncertainty std, sample_size}
  → constructors: {pace, reliability} (correlated per constructor)
  → circuit: {baseline, overtaking_environment}
  → era: {field_spread}
  ↓ RaceModel (per simulation, seed + sim_idx*1000)
  → constructor_samples: Normal(constructor.pace, 1.5) once per simulation (correlated)
  → sample_driver_performance: Normal(driver.pace, posterior_std) + constructor_sample + circuit*0.1 + N(0,0.5)
  ↓ QualifyingModel.simulate()
  → if historical_mode and grid_order: use observed grid (pre-race, allowed)
  → else: sort by sampled qualifying scores (driver+constructor)
  ↓ LapSimulator.simulate_race(grid_order, total_laps=58 or 5 in tests)
  → for each lap:
      for each driver:
        AR(1) noise: new = 0.7*prev + N(0,0.4)  (preserved)
        lap_time = 90 + base*0.5 + noise  (clipped 70)
        driver_times[driver] += lap_time
      sort by total_time → positions
      reliability: Bernoulli per driver via Beta DNF rate (driver DNF / total)
  ↓ PositionModel (implicit via sorting)
  ↓ MonteCarloRunner.run(simulations=N)
  → for sim_idx in 0..N-1: RaceModel(seed+sim_idx*1000) → Qualifying → LapSimulator → aggregation
  → finish_counts, win_counts, podium, points, position_samples, dnf_counts
  → probabilities: win/total, expected_finish, CI95, finish_distribution
  ↓ SimulationResult (drivers, constructors, summary, provenance)
```

**Files:**

- `backend/app/simulation/scenario_v14.py:1` — TemporalContext, Scenario, Resolver, StateBuilder
- `backend/app/simulation/calibration_state.py:1` — CalibrationState
- `backend/app/simulation/race_engine_v14.py:1` — RaceModel, QualifyingModel, LapSimulator, RaceEngine
- `backend/app/simulation/montecarlo.py:1` — MonteCarloRunner
- `backend/app/data/calibration_api.py:1` — 8 getters, strictly temporal

## 2. Invariant vs Dynamic State

**Static / invariant (precomputable per race):**
- driver IDs, constructor IDs, circuit properties, race distance (58), grid order (if historical),
- calibration means (driver pace, constructor pace, circuit baseline), uncertainties, sample sizes,
- era field_spread, reliability Beta priors, overtaking proxy.

**Dynamic (per simulation / per lap):**
- constructor_samples (N, constructors) — correlated, sampled once per simulation
- driver_samples (N, drivers)
- AR(1) noise_state (N, drivers) per lap
- driver_times (N, drivers)
- positions (N, drivers) per lap
- DNF state (N, drivers)
- lap_times (N, drivers) per lap

**Current flaw:** Static calibration values are re-fetched per simulation via `get_driver_performance` (JSON load) inside RaceModel loop — unnecessary overhead. Also `RaceModel` re-creates `np.random.default_rng` per simulation (cost).

## 3. Known Bottlenecks (Pre-Profile Hypothesis)

- **Python loops:** `for sim in simulations: for lap in laps: for driver in drivers` → `N * laps * drivers` Python iterations (e.g., 10k * 58 * 20 = 11.6M driver-lap iterations, each with attribute access, dict lookups).
- **RNG:** `np.random.default_rng(seed)` per simulation + `rng.normal` per driver per lap.
- **Sorting:** `sorted(grid_order, key=driver_times)` per lap (58 * 10k = 580k sorts of 20 elements).
- **Aggregation:** Python `Counter`, `defaultdict`, per-driver dict construction per simulation.
- **Object overhead:** `Driver`, `Car` objects not used in v14 path but still in `core/race_engine.py` (not in v14, but v14 still does dict lookups).

Profiling required to confirm.

## 4. Scientific Invariants to Preserve

- **Temporal:** `as_of < race_date`, strict_before, no future.
- **Constructor correlation:** both drivers of same team share same `constructor_samples[cid]` per simulation.
- **AR(1):** 0.7 coefficient, not independent.
- **Reliability:** Beta DNF, per-driver per-sim Bernoulli.
- **Determinism:** `seed + sim_idx*1000` streams, sorted outputs.

## 5. Next Steps

- Establish reproducible baseline (same scenario 2024-bahrain, 20 drivers, 5/58 laps).
- Profile with `cProfile`, `perf_counter`.
- Optimize: cache invariant, batch state arrays (N, drivers), vectorize lap loop, batch RNG, Numba kernels, aggregation via arrays.
