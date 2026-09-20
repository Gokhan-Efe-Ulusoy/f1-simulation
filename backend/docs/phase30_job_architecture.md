# Phase 30 — Job Architecture

## Overview

Phase 30 adds a durable job abstraction without rewriting the simulation engine.

```
Client
  ↓ HTTP
FastAPI (/api/v1/simulate/*)
  ↓ Pydantic validation
Execution Service (app/services/execution.py) — one execution path
  ↓ request_hash (deterministic)
Job Store (app/jobs/queue.py InProcessJobQueue) — persistent via DB
  ↓ enqueue / claim
Worker (app/jobs/worker.py) — calls execution service
  ↓ RandomProvider isolated
Simulation Engine (RaceEngine / VectorizedMonteCarlo / Replay / Decision)
  ↓ result normalization
Persistent Store (app/services/store.py + SimulationRecord)
  ↓
Client polling GET /simulation/{id}
```

## Components

- `app/jobs/models.py:JobRecord` — durable job with `job_id` PK, `simulation_id`, `request_hash`, `status`, `simulation_type`, `priority`, `created_at/started_at/completed_at/failed_at/cancelled_at`, `progress 0-1`, `current_stage`, `attempt/max_attempts`, `worker_id`, `error`, `result_hash`, `race_id/seed/sample_count`, `heartbeat_at`, indexes.

- `app/jobs/queue.py:JobQueue` abstract + `InProcessJobQueue` (DB-backed, no Redis). Methods `enqueue`, `claim`, `complete`, `fail`, `cancel`, `get_status`, `get_by_request_hash`, `update_progress`, `detect_stale`. Backpressure via `MAX_QUEUE_DEPTH` and `MAX_CONCURRENT_JOBS`.

- `app/jobs/worker.py:Worker` — `process_one()` claims oldest QUEUED, marks RUNNING, executes via `app.services.execution`, updates progress (`PREPARING 0.05 → SIMULATING 0.05-0.95 → NORMALIZING 0.95 → STORING 0.98 → COMPLETED 1.0`), persists to `SimulationRecord`, handles retry/cancellation, logs structured events.

- `app/jobs/cancellation.py` — cooperative tokens `request_cancellation(job_id)`, `is_cancelled(job_id)` checked at batch/lap boundaries.

- `app/jobs/policies.py` — `MAX_SYNC=1000`, `MAX_ASYNC=5000`, `MAX_CONCURRENT_JOBS=4`, `MAX_RETRIES=2`, `VALID_TRANSITIONS`, `is_retryable_error`.

- `app/core/database.py` — sync engine, sqlite fallback `data/simulations.db`, `init_db()` creates both `simulations` and `jobs` tables.

- `app/services/store.py` — DB primary + in-memory fallback, lifecycle `create`, `complete`, `fail`, `get`.

## Design Choices

- No mandatory Redis/Celery: `InProcessJobQueue` allows future `RedisJobQueue` without API change.
- Job IDs `job_<uuid12>` collision-safe, `simulation_id` same uuid for simplicity; `request_hash` deterministic for idempotency, not same DB ID.
- Worker does not implement simulation logic; calls `app.services.execution`.
