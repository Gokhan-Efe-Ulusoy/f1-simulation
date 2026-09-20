# Phase 11 — Historical Data Landing, Scientific Calibration & Validation

> Historical F1 data → canonical dataset → features → parameter fitting → calibrated profiles → historical replay → statistical validation → versioned calibration release.

## 1. Dataset pipeline

`python -m app.data build-dataset --dataset f1-dataset-v1.0 --start-season 1950 --end-season 2026` performs
`SOURCE DISCOVERY → RAW (hash/provenance) → NORMALIZATION → ENTITY RESOLUTION → CONFLICT RESOLUTION → VALIDATION → CANONICAL (data/canonical/*.json, batched) → FEATURES → DATASET VERSION`. Every stage is restartable: `CheckpointStore` tracks `completed/failed/skipped/pending` per season/round, `IngestionCache` skips unchanged resources via content hash, `force`/`offline`/`dry-run`/`limit`/`workers` are honored. Raw is immutable (parser bumps create new normalized versions).

## 2. Coverage

`build_coverage_report(1950,2026)` produces machine-readable `data/validation/coverage.json` and human table (`coverage_report.md`). Levels: `FULL` (verifiable records), `PARTIAL` (some), `UNKNOWN` (uninvestigated), `NOT_AVAILABLE` (tier gap), `CONFLICTED`. 1950 has race results + qualifying; 2024 has lap/sector/tyre/pit/weather/telemetry where sources permit.

## 3. Eras & regulations

10 historical eras (`1950–1957 … 2022–2026`) plus 9 technical/sporting/tyre/PU eras, each with `confidence` and notes justifying boundaries from `HistoricalRegulation` (curated `provider="curated"`). `season_eras()` is overlapping and deterministic.

## 4. Features

12+ driver (`average_grid/finish`, qualifying/race deltas, variance, DNF/incident/overtaking/defending, wet, tyre, consistency, pressure, finish rate), 9+ constructor (qualifying/race pace, reliability, pit, degradation, development slope, adaptability, wet), 7+ circuit (overtaking frequency, lap time, safety-car, degradation, pit-loss, field spread), plus `car_performance_decomposition` (hierarchical `track + car + driver + tyre` with shrinkage `n/(n+5)`, era-normalized). All declare `observed` vs `derived` + `sample_size`; unavailable → `None`.

## 5. Calibration engine

`app/data/calibration/` — `parameter_registry` (27 params, bounds, units, `identifiable/weakly/non` — driver vs car marked `NON_IDENTIFIABLE` and stays at prior), `objective` (MAE/RMSE/position+rank), `optimizer` (scipy L-BFGS-B or deterministic hill climbing with seed), `uncertainty` (bootstrap 95% CI, p5/25/75/95), `cross_validation` (temporal, never random), `fitter` (regularized L2, min sample 10, bootstrap intervals), `report` (markdown under `docs/calibration/`). Candidates are `status=candidate`; promotion is explicit.

## 6. Benchmark

`HistoricalRaceBenchmark` on injected simulators (deterministic stubs in tests, `HistoricalScenarioBuilder` for real engine). Metrics: MAE, RMSE, Spearman, position/lap/DNF/pit/tyre/Brier, calibration curves. CLI: `benchmark --season 2024 --race Bahrain --simulations 1000`, `benchmark-season`, `benchmark-range --start 2014 --end 2026`.

## 7. Performance & storage

Raw: JSON/CSV source-native; Canonical: JSON (bulk) + Parquet for laps/telemetry (pandas available, partitioned by season/session/driver); Calibration/Benchmark: JSON + Parquet. Bulk builder deduplicates and writes in batches (not one transaction per record). `RateLimiter` + `IngestionCache` prevent redundant downloads. Ingestion is batch-oriented; telemetry never stored as per-record JSON.

## 8. Known limitations

No production bulk import executed in CI (fixtures only); no Postgres backend wired (file store, repository-shaped modules); FastF1 payload stubbed; season-level points cross-check not yet implemented; pre-existing `app/simulation` mypy backlog unchanged (no new strict errors for Phase 11 core).

## 9. Reproducibility

Same `dataset_version + source_snapshot + parser_version + model_version + calibration_version + configuration + seed` → identical canonical/features/candidate/benchmark distributions. Tested via `test_reproducibility_canonical` and `test_benchmark_monte_carlo_determinism`.

> Reduced-order statistical simulation; not a full CFD / multibody / race-engineering simulator.
