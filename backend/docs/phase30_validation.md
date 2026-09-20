# Phase 30 — Validation

## Determinism

Same request+seed → same `request_hash` → same classification/result (tested `test_deterministic_async_execution`, `test_retry_determinism`, `test_sync_async_equivalence`). Different seed → different result.

## Async vs Sync Equivalence

N=20 sync direct vs API sync identical `win_probabilities` (tested). For async large N, chunked fallback to unchunked ensures identical (documented tolerance, not claimed exact if chunking changes).

## Lifecycle

Valid transitions tested `test_invalid_transitions`, `test_lifecycle_transitions`; invalid rejected. Race conditions tested: cancel while queued/running, duplicate claim, retry after completion, duplicate submission (idempotency).

## Persistence

`test_persistent_storage`: POST → GET via DB returns same `classification`; `test_serialization_round_trip`: serialize→persist→retrieve preserves result within JSON tolerance; `result_hash` stable for same classification.

## Progress

`test_progress_monotonicity`: 0.1 → 0.05 not regress, `test_progress_bounds`: clamp 0-1 (1.5→1.0, -0.5→1.0 due to monotonicity).

## Cancellation

`test_cancellation_queued` (async N=2000, QUEUED → cancel), `test_cancellation_running` (token), honest if not cancellable.

## Retry

`test_worker_failure` (retryable → QUEUED attempt 2), `test_non_retryable_failure` (validation → FAILED), `test_retry_policy` classification.

## Crash Recovery

`test_stale_job_recovery` and `test_crash_recovery_stale`: heartbeat expired → `detect_stale` → retry/FAILED.

## Security/Leakage

Preserved: `test_leakage_*`, `test_security_limits` (excessive N, path traversal), `tests/test_phase28_api.py` still 26/26.

## Idempotency

`test_idempotent_submission`, `test_no_duplicate_execution_idempotent`: same `request_hash` returns same `simulation_id`/job, no duplicate expensive execution.

## Chunk Determinism

Documented fallback to unchunked for determinism; `test_chunk_determinism` verifies identical.

## No Promotion

`test_versioning_unchanged` (calibration-v1.0.0 etc), `test_provenance_preservation` (dataset_v1.3, model 0.9.0).
