# Phase 31 — Security

- Preserved: CORS, Pydantic limits (N 1..5000, laps 1..200, interventions 20, chunk_size 1..5000, priority 0..100, events 200), path traversal rejected, no filesystem/shell/eval/exec, allowlists.
- New: queue flooding (QUEUE_FULL 429), priority abuse (bounded 0..100, no RNG effect), Redis unavailable explicit, duplicate submission safe, invalid IDs 404 sanitized, oversized payloads 422.
- Leakage: future_result/weather/pit/tyre/final_standings/observed_result/future_progression + aliases/nested still 422; workers validate via schemas.
