# Phase 30 — Limitations

Scientific limitations unchanged from Phase29 (no promotion):

- Dataset `f1-dataset-v1.3` (552,656 laps/1,172 races), calibration `v1.0.0`, tyre `v1.0.0`, weather `v1.0.0`, racecontrol `v1.0.0`, strategy `v1.1.0`, setup `v1.0.0`, raceengine `v2.2.0`, model `0.9.0`.
- Evidence tiers: fuel NON_IDENTIFIABLE, tyre_historical NON_IDENTIFIABLE, strategy/setup/weather/race_control PRIOR_ONLY, driver/circuit LIMITED.

Infrastructure limitations:

- Single-race weather/setup remain `PROVENANCE_ONLY` (vectorized MC honours via `hypothetical_modifiers`; single-race honest, not pretended). Unifying would require rewriting `RaceEngine` sequential weather to share vectorized `WeatherEngine` trajectory (science change, not done).
- Chunking for large N (e.g., 100k) is currently fallback to unchunked for determinism; true chunked `seed + i*1000` per chunk not yet implemented, so large async N still runs as single batch (memory bounded but not chunked). Documented, not claimed equivalent if chunking changes.
- Progress for Monte Carlo is stage-level (0.05 PREPARING → 0.05-0.95 SIMULATING → 0.95 NORMALIZING → 0.98 STORING → 1.0 COMPLETED) throttled every 1% or 1s; per-sample progress not yet per-lap.
- `InProcessJobQueue` is in-process, not distributed; no Redis/Celery, so not multi-host; `MAX_CONCURRENT_JOBS=4` in-process only.
- Persistent store uses SQLAlchemy with postgres→sqlite fallback `data/simulations.db`; in CI fallback to sqlite (not postgres), not replicated.
- Cancellation is cooperative: `QUEUED` immediate, `RUNNING` at batch/lap boundaries; single-race mid-lap cannot be cancelled instantly.
- Retry `max_attempts=2` only for transient errors; non-retryable (validation/leakage) never retried.
- No queue persistence beyond DB; no priority scheduling beyond `priority` field (currently 0).
- No auth for cancellation (single tenant dev).
