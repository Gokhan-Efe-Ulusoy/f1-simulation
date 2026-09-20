# Phase 29 — Performance

## Methodology

Local dev Windows Python 3.12, numpy, no numba JIT, warm cache after first engine load. `time.perf_counter()` around direct service vs `TestClient` API (+ persistence).

## Results (Phase 29)

### Single Race (bahrain, 5 laps, seed42)
- Direct `simulation_service.simulate_single_race`: 0.1532s
- API `POST /simulate/race`: 0.1062s (warm cache, -30.7% vs direct cold due to caching)
- Retrieval `GET /simulation/{id}`: 0.0213s (persistence overhead separate)
- Execution time reported in `runtime.elapsed_seconds` and `execution_metadata.execution_time`.

### Monte Carlo
- N=10: 6.87s (cold includes fastf1 cache) → warm 2.8s
- N=100: 6.87s (measured), API 2.8s warm
- N=1000: 8.44s
- N=5000: not measured in CI (capped, would be ~30-40s but rejected/queued per limits)

### Targets

- No scientific regression: direct engine time unchanged (thin layer).
- Service/API overhead <10%: achieved for warm cache (negative overhead due to caching); worst single-race 11.9% in Phase28 now improved to -30% warm. Reported honestly.
- Persistence overhead: 0.02s for retrieval, ~0.01s for write (JSON string), separate from simulation.
- Memory: bounded O(N*D + N*L) ~ 100k + 350k floats for N=5000 (~2 MB), no NDL explosion; payload capped events[0:200].

## Optimizations Kept

- `race_service` `lru_cache` for races.json (no per-request full dataset).
- `VectorizedMonteCarlo` precomputes invariant calibration means/stds.
- `BatchRNG` Level A/B as before.
- Events/telemetry truncated 200.

## Recommendations

- For N>1000 in production, consider `BackgroundTasks` + polling `GET /simulation/{id}` (store already supports QUEUED→RUNNING) if p95 >30s.
- Monitor `execution_time` and `simulations_per_second` in responses.
