# Phase 31 — Failure Injection

- Chunk retry: re-run same global start → identical positions (tested).
- Stale heartbeat → retry/FAILED, no duplicate COMPLETED.
- Duplicate claim: priority ordering + atomic lock prevents double RUNNING.
- Cancel during chunk: token checked at chunk boundaries, never COMPLETED without valid result.
- Timeout: RUNNING exceeding 300s → TIMEOUT, retryable, idempotent.
- Redis disconnect: explicit unavailable error, optional fallback logged, no silent success.
