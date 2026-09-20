# Phase 31 — Timeout

- `MAX_JOB_RUNTIME_SECONDS=300` via settings, configurable.
- `RUNNING` exceeding → `TIMEOUT` (distinct from FAILED/CANCELLED), `timed_out_at` set, idempotent.
- Worker checks elapsed after execution; `queue.check_timeouts()` for sweeper.
- Retry allowed `TIMEOUT→QUEUED` per policy. No duplicate completed records (timeout before persistence, not after).
