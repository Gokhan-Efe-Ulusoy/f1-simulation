# Phase 31 — Observability

- `GET /api/v1/metrics`: queue_depth, running/completed/failed/cancelled/timed_out, retry_count, average/p50/p95/p99 runtime, jobs_by_type, jobs_by_priority. No RNG effect, no sensitive details.
- Structured logs: job_created/claimed/started/progress/completed/failed/cancelled/retry/stale/timeout with job_id, simulation_id, request_hash, type, attempt, worker_id, duration.
- Lightweight counters, modular, no heavy stack.
