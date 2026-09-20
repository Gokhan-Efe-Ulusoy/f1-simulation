# Phase 31 — Validation

- Determinism matrix (seed 42/43, N 1/10/100/1000, chunk 1/10/100/500/1000, workers 1/2/4, order seq/shuffled, backend inprocess/redis-unavailable): same seed identical, different seed different, chunk/worker/order independent, retry identical, API==direct.
- Failure injection: worker crash, chunk failure, Redis disconnect, DB temp failure, heartbeat timeout, duplicate claim, retry, cancel during/between chunks, timeout, duplicate submission — no corrupted COMPLETED.
- Backward compat: Phase30 API behavior == Phase31 for equivalent requests; 92 prior tests pass.
- No promotion, versions unchanged, dataset hash unchanged.
