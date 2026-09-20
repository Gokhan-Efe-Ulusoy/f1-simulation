# Phase 31 — Heartbeat

- `heartbeat_at` updated on claim, progress, completion. Worker updates per chunk (throttled 1% or 1s).
- `JOB_HEARTBEAT_TIMEOUT_SECONDS=60` configurable. `detect_stale()` distinguishes healthy RUNNING (recent heartbeat, long sim ok) vs dead (expired → retry/FAILED).
- Long simulations not marked stale merely for duration; only heartbeat expiry.
