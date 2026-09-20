# Phase 10 — Historical Dataset v1.0 & Data Fusion

## Pipeline

```
RAW (data/raw/<source>/ + .cache)  — immutable, content-hashed
  → NORMALIZED (standardized dates/durations/compounds/sessions/units;
    ambiguous → None + warning)
  → ENTITY RESOLUTION (AliasRegistry, accent/case/sponsor-insensitive)
  → MATCHING (season+round+driver contextual keys, never fuzzy-name-only)
  → FIELD COMPARISON → CONFLICT DETECTION (compare_fact, priority + reason)
  → FIELD-LEVEL PRIORITY (SourceCatalog, configurable per field/dataset)
  → CANONICAL RECORD (provenance chain extended)
  → VALIDATION (DataQualityReport: 13 finding classes)
  → PERSIST (data/canonical/*.json, batched)
  → FEATURES (data/derived/*, observed/derived/inferred/simulated)
  → CALIBRATION DATASET (data/calibration/, no auto-promote)
  → BENCHMARK (HistoricalRaceBenchmark, TemporalSplit)
```

Layers are strictly separated; raw is never overwritten (parser version
bumps create new normalized versions).

## Source catalog

`app/data/catalog.py` — 8 default sources (jolpica, openf1, fastf1,
kaggle_generic, github_generic, official_f1, fia_documents, weather_api)
with tier (1=official, 2=structured API, 3=curated, 4=community), type,
coverage (1950–2026 where applicable), supported entities/resolution,
license/terms, retrieval method, last_verified. `SourceCatalog` tracks
field-level priority (race_winner: official > fia > jolpica …, lap_time:
official > openf1/fastf1 …) — configurable via `set_priority()`.

## Ingestion

- Jolpica: `JolpicaAdapter` (injectable transport), pagination via
  season/round, `RateLimiter` (rps/timeout/retries/backoff), `IngestionCache`
  (content-hashed key = source+endpoint+params+version), manifests + raw
  storage under `data/raw/jolpica/`.
- OpenF1: `OpenF1SourceAdapter.capabilities(season)` → dynamic session
  discovery; fetch only supported endpoints.
- FastF1: optional backend; `is_available()` guard, `DataUnavailable`
  when missing (never fabricated).
- Kaggle: `KaggleSourceAdapter.fetch_dataset(owner/slug, version)` —
  local import, file hashes, sanitized paths, formula-injection guards.
- GitHub: `GitHubSourceAdapter.fetch_file(owner/repo/path@ref)` — pinned
  commit SHA/tag, sanitized paths, raw content hashed.
- FIA / weather: document-oriented importers with document id, date,
  version, hash, extracted fields.
- Bulk & checkpoint: `bulk_ingest_jolpica()` iterates 1950–2026,
  `CheckpointStore` tracks completed/failed/skipped/pending per
  season/round, `cache.has()` enables incremental skip, `force`/`offline`/
  `dry-run`/`limit` all honored, resumable after failure at any round.

## Security

Untrusted input treated as hostile: CSV formula injection (`=+-@`),
path traversal (`..`, absolute paths), oversized payloads (50 MB cap),
excessive record counts (100k cap), and schema expansion are all
validated. `sanitize_filename`/`sanitize_path` are used in cache,
Kaggle, GitHub, and FIA paths.

## Storage

JSON for metadata/configuration/small sets; CSV for small interchange
(Cool); Parquet recommended for large timing/telemetry (pandas
available, `scipy`/`pandas` in dependencies); no telemetry in JSON.
PostgreSQL noted as canonical relational target; current file store is
incremental/batched (not one-transaction-per-record).

## Feature & calibration bridge

`driver_features` / `constructor_features` / `circuit_features` /
`era_features` emit `FeatureRecord`s with observed/derived/unavailable
semantics and sample_size. Era-normalized metrics (field percentile,
gap-to-field) are available as derived features. `FittedCalibrationSet`
carries per-parameter value/uncertainty/dataset/method/date/versions/
confidence and projects via `to_simulation_profile()` onto the untouched
Phase 8 `CalibrationProfile` — identity when unfitted.

## Benchmarking & splits

`run_benchmark()` compares observed vs simulated distributions (MAE,
RMSE, Spearman, position/lap/DNF/pit/deg errors, Brier, calibration
curves) on an injected simulator (deterministic stubs in tests, builder
output for real engines). `TemporalSplit` assigns seasons by year
(default 1950–2000 / 2001–2010 / 2011–2020 / 2021–2026), never random.

## Known limitations

- No production bulk import executed (sourcing decisions pending license
  review).
- No Postgres backend wired (file store + in-repo modules).
- Lap/sector/telemetry features activate only after modern-resolution
  imports land.
- No season-level points cross-check yet beyond row-level consistency.
