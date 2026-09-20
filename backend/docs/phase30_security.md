# Phase 30 — Security

Preserves Phase 28/29.

- CORS: `settings.CORS_ORIGINS` via `CORSMiddleware`.
- Path traversal: `..`, `/`, `\` rejected in `race_id`, `simulation_id`, `job_id`, `checkpoint` (Pydantic + endpoint guards). `GET /simulation/../../etc/passwd` → 404/422.
- Oversized: `race_id` max 100, `simulation_id` 200, `simulations` 1-5000 (422), `laps` 1-200, `interventions` max 20, `events` capped 200, `track_pit_loss` 0-60.
- Queue flooding: `MAX_QUEUE_DEPTH=100`, `MAX_CONCURRENT_JOBS=4` enforced in `InProcessJobQueue.enqueue` (`QUEUE_FULL` → 429) and `claim`; tested `test_bounded_concurrency`, `test_queue_backpressure`.
- Invalid IDs: malformed UUIDs, unknown simulation/job → 404 `DATA_NOT_AVAILABLE` sanitized, no stack traces.
- Leakage: `future_*`, `observed_result`, `actual_`, `realized`, `final_position`, `championship`, `standing` rejected via `schemas` validators + `registry` allowlist; tested `test_leakage_*`, `test_security_limits`.
- No `eval`, `exec`, `subprocess`, filesystem paths from client, dynamic imports, arbitrary worker config.

New:
- Cancellation authorization: no auth yet (single tenant dev); `POST /simulation/{id}/cancel` checks existence, returns 404 if unknown, 400 if not cancellable, no privilege escalation.
- Job queue: no client-defined worker count; `priority` not client-controlled, `worker_id` server-generated.

Verified via `tests/test_phase30_jobs.py` security cases.
