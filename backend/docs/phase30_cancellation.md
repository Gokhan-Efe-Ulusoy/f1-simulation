# Phase 30 — Cancellation

## API

`POST /api/v1/simulation/{simulation_id}/cancel`

- `QUEUED` → `CANCELLED` immediately (DB update, `cancelled_at`, `progress 0.0`, `stage CANCELLED`).
- `RUNNING` → cooperative request: sets token via `app/jobs/cancellation.py:request_cancellation(job_id)`, returns 200 but status remains `RUNNING` until worker checks.
- `COMPLETED`/`FAILED`/`CANCELLED` → 400 `cannot cancel job in status X`.

## Cooperative Boundaries

Worker checks `is_cancelled(job_id)` at:

- Before execution (`_execute` entry)
- Monte Carlo chunk boundaries (every 1000 simulations, or per lap if implemented)
- After prepare, before storing

If cancelled, worker calls `_cancel_job` → marks `CANCELLED` in DB, `progress 0.0`, `stage CANCELLED`, clears token.

No unsafe thread/process termination; no `kill`, no `terminate`.

## Honesty

If engine cannot be cancelled mid-lap (single-race lap loop), worker reports cancellation at next safe boundary. For `QUEUED`, immediate. For `RUNNING` single-race, may need to finish current lap.

Tested in `test_cancellation_queued` (async N=2000, QUEUED → cancel → CANCELLED/QUEUED/RUNNING) and `test_cancellation_running` (token set, worker checks).

## Logging

`job_cancelled` event logged with `job_id`, `simulation_id`.
