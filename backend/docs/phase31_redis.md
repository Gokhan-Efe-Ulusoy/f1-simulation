# Phase 31 — Redis

- Optional `redis` package (not in mandatory deps). `RedisJobQueue(redis_url)` pings on init, raises `Redis backend unavailable` if down.
- Atomic claim via `SET f1:queue:claim_lock NX EX 5`, then DB claim (priority DESC, created_at ASC), then DEL lock.
- Config: `JOB_QUEUE_BACKEND`, `REDIS_URL=redis://localhost:6379/0`, fallback explicit.
- Never silently switches semantics; same RNG/result whether inprocess or redis.
- Tested unavailable path (no silent success).
