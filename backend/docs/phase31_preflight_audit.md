# Phase 31 Preflight Audit

## Baseline (Phase 30 COMPLETE)

- Dataset f1-dataset-v1.3 (552656 laps / 1172 races / 12747 pitstops), calibration-v1.0.0, tyre-v1.0.0, weather-v1.0.0, racecontrol-v1.0.0, strategy-v1.1.0, setup-v1.0.0, raceengine-v2.2.0, model 0.9.0, simulation 9.2.0.
- API 10 endpoints (health, metadata, races, races/{id}, simulate/race, simulate/monte-carlo, strategy/evaluate, scenario/compare, replay/{id}, simulation/{id}).
- Unified service layer `app/services/execution.py` (execute_single_race, execute_monte_carlo), request_hash deterministic, result normalization, SQLAlchemy persistence (SimulationRecord + JobRecord, postgres→sqlite fallback).
- Queue `app/jobs/queue.py:InProcessJobQueue` (enqueue/claim/complete/fail/cancel/get_status, max_concurrent=4, max_depth=100), worker `app/jobs/worker.py` (calls execution service, progress PREPARING→SIMULATING→NORMALIZING→STORING→COMPLETED), cancellation tokens, policies (MAX_SYNC=1000, MAX_ASYNC=5000, MAX_RETRIES=2).
- Tests 985 total, 0 failures, 1 skip. Scientific gate PASS.

## Phase 30 Limitations (to address)

1. True deterministic chunking NOT IMPLEMENTED — `worker.py:_execute` falls back to unchunked for N>1000 with comment.
2. Distributed queue NOT IMPLEMENTED — only InProcessJobQueue, no Redis.
3. Priority scheduling NOT IMPLEMENTED — `priority` column exists but `claim()` orders by `created_at` only.
4. Per-job timeout NOT IMPLEMENTED — `MAX_JOB_RUNTIME_SECONDS=300` defined but never enforced; no TIMEOUT status.
5. Observability NOT IMPLEMENTED — no `/metrics` endpoint.

## Current Execution Paths

- `POST /simulate/monte-carlo` → `simulate.py:monte_carlo_endpoint` → idempotency via `queue.get_by_request_hash` → sync if N≤1000 else async enqueue + BackgroundTasks `_bg_task` → `Worker` → `execute_monte_carlo` → `montecarlo_service.run_montecarlo` → `VectorizedMonteCarlo.run(N)` → reshape → store + `queue.complete`.
- `VectorizedMonteCarlo.run(N)`: Level A per-sim (pace seed+i*1000, qual +2, rel +3, weather +500, RC +600+lap*7919) + Level B AR1 shared per-lap (`seed+100+lap`, size (N,D)) + vectorized lap loop + integer-count aggregation.

## RNG Streams (must preserve)

- pace: `seed + i*1000`, qual: `+2`, rel: `+3`, weather: `+500`, RC: `+600 + lap*7919`, AR1: `seed+100+lap` shared. No worker_id/process/timestamp/UUID in derivation.

## Files to Change

- `app/simulation/performance/rng.py` (add offset-aware Level A)
- `app/simulation/performance/vectorized_montecarlo.py` (add start_index support, chunk manifest helpers)
- NEW `app/simulation/performance/chunked_montecarlo.py` (deterministic chunked runner, manifest, aggregation)
- `app/jobs/models.py` (add TIMEOUT, chunk fields, priority docs)
- `app/jobs/policies.py` (priority levels, timeout/heartbeat config)
- `app/jobs/queue.py` (priority ordering, timeout, Redis abstraction)
- NEW `app/jobs/redis_queue.py` (RedisJobQueue, lazy import)
- `app/jobs/worker.py` (chunked execution, progress per chunk, timeout/heartbeat, cancellation at chunk boundaries)
- `app/core/settings.py` (JOB_QUEUE_BACKEND, REDIS_URL, timeouts, chunk_size)
- `app/api/v1/endpoints/simulate.py` (priority param, chunk_size param, async chunked)
- `app/api/v1/endpoints/simulation.py` (enrichment: chunk counts, heartbeat, priority, timeout)
- NEW `app/api/v1/endpoints/metrics.py` + router
- `app/services/montecarlo_service.py` (chunked entrypoint)
- `app/services/execution.py` (chunked passthrough)
- Tests `tests/test_phase31_chunking.py`, `tests/test_phase31_jobs.py` (or test_phase31_distributed.py)
- Docs 16 files.

## Risks

- Changing AR1 to per-sim would break backward compat; instead preserve Level B shared semantics via discard-slice for chunk equivalence.
- Adding TIMEOUT status must not break Phase 30 clients expecting only 5 statuses; keep backward compat (old statuses still valid).
- Redis optional: default inprocess, explicit fallback, never silently switch semantics.
- Priority must not affect RNG/result (request_hash excludes priority).
