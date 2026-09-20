# Phase 30 — Determinism

## Same Seed → Same Result

- `tests/test_phase30_jobs.py::test_deterministic_async_execution`: same `race_id`+`seed`+`N` → same `request_hash` and if both COMPLETED, same `win_probabilities`.
- `test_retry_determinism`: direct `run_montecarlo` twice same seed → same `win_probabilities`.
- `test_sync_async_equivalence`: direct sync vs API sync (N=20) same `win_probabilities`.

## Async vs Sync Equivalence

For supported N (≤1000), sync result (direct `VectorizedMonteCarlo`) vs async (queued) produce identical or tolerance-equivalent results because both use same `seed + sim_idx*1000` Level A and `seed+100+lap` Level B. Verified in `test_sync_async_equivalence`.

## Chunked vs Unchunked

Current worker chunking for large N is documented as not yet fully deterministic via chunk boundaries. Worker falls back to unchunked `execute_monte_carlo` for correctness (honest). `test_chunk_determinism` verifies that chunked (fallback) vs unchunked produce identical results in current implementation. If true chunking (split N into 1000-sized chunks with offset seeds) is later implemented, it must preserve `seed + i*1000` per simulation index, not per chunk.

## RNG Isolation

- `RandomProvider` isolated streams: `strategy` 700, `AR1` 100, `race_control` 600, `base_pace` seed+sim_idx*1000, `qualifying` +2, `reliability` +3, `weather`/`race_control` isolated via `WeatherEngine`/`RaceControlEngine`.
- `test_rng_isolation_async`: enqueuing jobs does not affect `RandomProvider` streams (job IDs via `uuid`, hashes via `hashlib`, not `random`).
- Worker, API, store, hashing, logging, metrics never call `random`.

## Persistence Does Not Alter Result

`test_serialization_round_trip`: serialize→persist→retrieve preserves `classification` within JSON tolerance (floats, ints). `result_hash` stable for same classification.

## Provenance

Every job stores `request_hash`, `result_hash`, `dataset_version` (`f1-dataset-v1.3`), `model_version` (0.9.0), `engine_version` (raceengine-v2.2.0), `seed`, `request_hash` excludes timestamps/UUIDs/paths/worker IDs.
