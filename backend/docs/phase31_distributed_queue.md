# Phase 31 — Distributed Queue

- `JobQueue` protocol preserved (enqueue/claim/complete/fail/cancel/get_status).
- `InProcessJobQueue` (DB, default safe) + `RedisJobQueue` (same semantics, atomic claim via SETNX lock, DB remains durable).
- API does not know backend; `get_queue()` factory via `JOB_QUEUE_BACKEND=inprocess|redis`, `REDIS_URL`, explicit fallback (`JOB_QUEUE_FALLBACK_INPROCESS`).
- Lifecycle QUEUED→RUNNING→COMPLETED/FAILED/CANCELLED/TIMEOUT, existing Phase30 rules authoritative.
- No mandatory Redis for local dev; unavailable → explicit error, optional fallback logged.
