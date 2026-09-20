# Phase 30 — Retry Policy

## Defaults

- `max_attempts = 2` (initial + 1 retry) via `JobRecord.max_attempts`, `policies.MAX_RETRIES=2`.

## Classification

**Retryable** (via `is_retryable_error`):
- `"transient worker error"`
- `"temporary database connection error"`
- `"temporary queue failure"`
- `"worker crash"`, `"heartbeat expired"`, `"stale job"`, `"transient"`

**Non-retryable** (substrings `NON_RETRYABLE_SUBSTRINGS`):
- `"validation error"`, `"leakage"`, `"invalid"`, `"unsupported"`, `"unknown"`, `"malformed"`, `"deterministic"`, `"scientific"`

If message contains non-retryable substring, never retry even if it also contains retryable phrase.

## Behavior

- `queue.fail(job_id, error, retryable)`: if `retryable and attempt < max_attempts` → transition `RUNNING → QUEUED`, `attempt +=1`, `error` JSON with `retry:true`, `heartbeat` updated; else `RUNNING → FAILED` with `failed_at`.

- `detect_stale` → `fail(..., retryable=True)` → retry or final FAILED.

Logged as `job_failed` with `retryable` flag and `job_retry` if retried.

Tested in `test_worker_failure` (retryable → QUEUED attempt 2), `test_non_retryable_failure` (validation → FAILED), `test_retry_policy`, `test_retry_determinism` (retry produces same deterministic result as clean run).

## Bounds

No blind retries; bounded by `max_attempts`. Invalid transitions rejected via `can_transition`.

## Provenance

Failed jobs store `error` JSON, `attempt`, `max_attempts`; successful retry produces same `result_hash` as clean run (deterministic).
