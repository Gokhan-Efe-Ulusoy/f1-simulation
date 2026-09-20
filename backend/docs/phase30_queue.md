# Phase 30 — Queue

## Interface

`JobQueue` abstract in `app/jobs/queue.py`:

```python
enqueue(payload) -> job_id
claim(worker_id) -> job_dict | None
complete(job_id, result)
fail(job_id, error, retryable)
cancel(job_id) -> bool
get_status(job_id) -> dict | None
get_by_request_hash(hash) -> dict | None
update_progress(job_id, progress, stage)
detect_stale(timeout) -> list[job_id]
```

## Implementation

`InProcessJobQueue`:

- Backed by `JobRecord` table (Postgres → sqlite fallback).
- `enqueue`: checks `MAX_QUEUE_DEPTH` (100) and `MAX_CONCURRENT_JOBS` (4) via count of QUEUED+RUNNING; raises `QUEUE_FULL` → API 429. Creates `QUEUED` record with `progress 0.0`, `stage QUEUED`, `attempt 1`.

- `claim`: respects `MAX_CONCURRENT_JOBS`; selects oldest `QUEUED` ordered by `created_at`; transitions `QUEUED→RUNNING` transactionally, sets `started_at`, `heartbeat_at`, `worker_id`, `progress 0.05`, `stage PREPARING`.

- `complete`: transitions `RUNNING→COMPLETED`, sets `completed_at`, `progress 1.0`, `stage COMPLETED`, stores `result` JSON + `result_hash`.

- `fail`: if retryable and `attempt < max_attempts`, transitions `RUNNING→QUEUED` with `attempt+1`; else `RUNNING→FAILED` with `failed_at`, `error`.

- `cancel`: `QUEUED→CANCELLED` immediately; `RUNNING` sets cancellation token (cooperative), worker checks.

- `get_by_request_hash`: query by `request_hash` ordered by `created_at` desc, used for idempotency.

- `update_progress`: throttled (only if progress increased or stage changed), clamps 0-1, updates `heartbeat_at`.

- `detect_stale`: finds `RUNNING` with `heartbeat_at < now - timeout`, calls `fail(..., retryable=True)`.

No Redis required; interface allows future `RedisJobQueue` drop-in.

## Limits

- `MAX_SYNC_MONTE_CARLO=1000`, `MAX_ASYNC=5000`, `MAX_CONCURRENT_JOBS=4`, `MAX_QUEUE_DEPTH=100`, enforced at API and queue levels.
- No unbounded queue/worker spawning; 429 `QUEUE_FULL` documented.
