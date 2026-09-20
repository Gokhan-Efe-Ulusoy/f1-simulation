# Phase 30 — Lifecycle

## States

```
QUEUED → RUNNING → COMPLETED
  ↓        ↓
CANCELLED  → CANCELLED
  ↓        ↓
       FAILED → QUEUED (retry)
```

Valid transitions enforced via `policies.VALID_TRANSITIONS` and `can_transition()`:

- `QUEUED → RUNNING`, `QUEUED → CANCELLED`, `QUEUED → FAILED` (via stale)
- `RUNNING → COMPLETED`, `RUNNING → FAILED`, `RUNNING → CANCELLED`, `RUNNING → QUEUED` (retry)
- `COMPLETED →` none
- `FAILED → QUEUED` (retry)
- `CANCELLED →` none

Invalid transitions rejected.

## Flow

1. `POST /simulate/monte-carlo` with `simulations > 1000` → `InProcessJobQueue.enqueue` creates `QUEUED` (progress 0.0, stage QUEUED).
2. BackgroundTasks schedules `Worker.process_one()` which `claim`s (→ `RUNNING`, stage `PREPARING`, progress 0.05, heartbeat).
3. Worker executes: `PREPARING 0.05 → SIMULATING 0.05-0.95 → NORMALIZING 0.95 → STORING 0.98`.
4. On success: `complete` → `COMPLETED` 1.0.
5. On failure: `fail` → `FAILED` or `QUEUED` for retry.
6. Client polls `GET /simulation/{id}` which checks `JobRecord` first (progress, stage, attempt) then `SimulationRecord`.

## Persistence

Both `JobRecord` and `SimulationRecord` are SQLAlchemy tables with `created_at`, `updated_at`, `heartbeat_at`. `init_db()` creates via `Base.metadata.create_all`.

## Sync vs Async

- Small `N ≤ 1000`: sync path still creates QUEUED→RUNNING→COMPLETED in same request for simplicity and backward compat; returns `COMPLETED` immediately.
- Large `N > 1000`: async path returns `QUEUED` immediately with `poll_url`; worker runs in BackgroundTasks.

## Progress

`progress 0.0-1.0` monotonic, clamped, throttled (update only if +1% or stage change). Stage-level if per-sample not measurable.

## Crash Recovery

`detect_stale(timeout=60s)` finds `RUNNING` with expired heartbeat, marks retryable `FAILED→QUEUED` or `FAILED`.

## Cancellation

Cooperative: `POST /simulation/{id}/cancel` sets token; worker checks at batch/lap boundaries. `QUEUED` → `CANCELLED` immediately.
