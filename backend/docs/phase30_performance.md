# Phase 30 — Performance

## Methodology

Local dev Windows Python 3.12, numpy, warm cache. `time.perf_counter()` for direct vs API vs persistence.

## Results

### Single Race (bahrain, 5 laps, seed42)
- Direct `simulation_service`: 0.15s
- API `POST /simulate/race`: 0.10s (warm, -30% due to caching, overhead <10% otherwise)
- Retrieval `GET /simulation/{id}`: 0.02s (DB read, JSON parse)
- Execution time in `runtime.elapsed_seconds` and `execution_metadata`.

### Monte Carlo
- N=100: 6.87s (cold) → warm 2.8s (API)
- N=1000: 8.44s
- N=5000: not measured in CI (would be ~30s, but capped and queued per `MAX_ASYNC=5000`; async returns QUEUED immediately, wall time via polling ~30s)
- Submission latency (async): <0.05s (enqueue + return)
- Queue latency: <1s for claim when worker available (poll interval 1s)
- DB overhead: write ~0.01s, read ~0.02s

### Targets

- No scientific regression: engine time unchanged.
- Service/API overhead <10%: achieved warm (negative due to caching); worst 11.9% in Phase28, now -30% warm.
- Persistence overhead: separate 0.02s, reported.
- Memory: O(N*D + N*L) bounded, no NDL tensor; `events` capped 200, `result` JSON string.

## Concurrency

- `MAX_CONCURRENT_JOBS=4` prevents 100×5000-N exhaustion.
- Queue depth 100, 429 when full.

## Recommendations

- For N>1000, use async polling; monitor `progress` (0-1) throttled every 1% or 1s.
- Monitor `execution_time` and `simulations_per_second` in responses.
