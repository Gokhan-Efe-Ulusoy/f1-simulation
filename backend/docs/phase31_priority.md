# Phase 31 — Priority

- Bounded int 0..100 (LOW=10 NORMAL=50 HIGH=90). Validated 0..100, defaults 50.
- Affects queue ordering (`priority DESC, created_at ASC`) only; does NOT affect RNG/result (request_hash excludes priority).
- Same request different priority → same result (tested).
- Starvation mitigation: FIFO within priority; future aging possible.
