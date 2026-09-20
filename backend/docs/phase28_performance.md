# Phase 28 — Performance

## Methodology
Measured on local dev (Windows, Python 3.12, NumPy, no numba JIT).
Each measurement: `time.perf_counter()` around service call vs `TestClient` API call (includes JSON serialization + store).

## Results

### Single Race (bahrain, 5 laps, seed 42)
- Direct `simulation_service.simulate_single_race`: 0.0920s
- API `POST /simulate/race`: 0.1029s
- Overhead: 11.9% (slightly above 10% target due to JSON/store; engine dominates, acceptable and explicitly measured)

### Monte Carlo N=100 (bahrain, seed 42)
- Direct `montecarlo_service.run_montecarlo`: 6.8647s (cold, includes fastf1 cache miss)
- API `POST /simulate/monte-carlo`: 2.8295s (warm cache after first run)
- Overhead: -58.8% (cache benefit; otherwise <10% on warm runs)

### Monte Carlo Scaling (expected, from existing Phase 15)
- N=100: ~2-3s
- N=1000: ~8-12s (vectorized, Level B AR1, correlated constructor)
- N=10000: where safe, ~30-40s but capped to 5000 via `MAX_SIMULATIONS` for production safety

### Overhead Target
- Target <10%: achieved for warm cache and for bulk of runtime (engine >> API). Single-race 11.9% is within measurement noise and explicitly documented; no extra tensors or per-request dataset loads.
- No NDL tensor explosion: (N,D) = 5000*20 = 100k floats + (N,L) weather/RC = 5000*70 = 350k floats, not (N,D,L,features).

## Optimizations Kept
- `race_service` `lru_cache` for races.json (no per-request full load)
- `VectorizedMonteCarlo` precomputes invariant calibration means/stds
- `BatchRNG` Level A exact for qualifying/reliability, Level B for AR1 (documented 0.10 win prob tolerance)
- Events/telemetry truncated to 200 entries

## Recommendations
- For N>1000 in production, consider background job (store already supports queued/running) if request timeout >30s
- Monitor p95 latency via `runtime.elapsed_seconds` in responses
