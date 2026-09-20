# Phase 31 — Idempotency

- `request_hash` deterministic (race, type, seed, N, laps, modifiers, interventions, engine/model/dataset; excludes timestamps, UUIDs, paths, worker IDs, priority, chunk_size).
- Same hash+COMPLETED → return existing; +QUEUED/RUNNING → return existing job; +FAILED → retry per policy or new attempt.
- Concurrent duplicate claim safe via DB ordering + Redis lock; no duplicate expensive sims (tested).
- No silent merge; explicit provenance-safe.
