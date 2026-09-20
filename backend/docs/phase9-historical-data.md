# Phase 9 — Historical Data & Calibration Foundation

## Architecture

```
RAW SOURCES (official F1 / FIA / Jolpica / FastF1 / weather / external)
        │
SOURCE ADAPTERS (app/data/sources/*, per-provider raw records)
        │  data/raw/<source>/ + data/manifests/<run>.json
NORMALIZATION (app/data/normalization.py: dates, durations, compounds…)
        │
ENTITY RESOLUTION (app/data/resolution.py: AliasRegistry)
        │
CANONICAL STORE (app/data/models/canonical.py, data/canonical/)
        │
VALIDATION (app/data/validation.py → DataQualityReport, data/validation/)
CONFLICTS (app/data/conflicts.py, priority-resolved, recorded)
        │
FEATURE ENGINE (app/data/features.py → data/derived/*)
        │
CALIBRATION SETS (app/data/calibration_bridge.py → data/calibration/)
        │
HISTORICAL SCENARIO BUILDER (app/data/scenario.py)
        │
RACE ENGINE (unchanged API)
        │
HISTORICAL BENCHMARK (app/data/benchmark.py + app/data/metrics.py)
```

Layers (see `data/README.md`): raw → normalized → canonical → derived
→ calibration. Never collapsed, never fabricated.

## Source strategy

Adapters emit source-specific raw records; each declares provider,
endpoint/URL, coverage, license notes and parser version. Jolpica
(Ergast-compatible, keyless JSON) covers seasons/schedule/results/
qualifying/drivers/constructors/standings. Local CSV covers offline
public archives with validated headers. FastF1 is architecture-only:
`FastF1Adapter.is_available()` reports backend presence and every fetch
raises `DataUnavailable` without it — no telemetry is ever invented.
Transports are injectable so tests never touch the network.

## Schema

Canonical models (`app/data/models/canonical.py`): seasons, races
(events, never venues), sessions, drivers, constructors, engines, cars,
circuits, results, qualifying results, laps, sectors, pit stops, tyre
stints, weather observations, championship standings, regulations —
plus `DataSource`, `DataProvenance`, `DataAvailability`,
`DataQualityReport`. Stable `{type}:{slug}` IDs; aliases for historical
names; `None` means unavailable; units in field names
(`lap_time_seconds`, `distance_km`, `speed_kph`, `temperature_c`).

## Provenance

Every imported record carries `DataProvenance`: provider, record id,
URL, retrieval timestamp, parser version, raw sha256, confidence and an
append-only `transformation_chain` (`extended()` clones). Manifests
(`app/data/manifests.py`) record run id, coverage, fetched/accepted/
rejected counts, warnings, versions and payload hash; raw bundles persist
under `data/raw/<source>/`.

## Resolution tiers

`COVERAGE_TIERS` states plausible per-field coverage by era
(1950s: results/qualifying/championship; 1980s: +pit stops; 2000s:
+lap/tyre detail; 2010s: +sectors/weather; 2020s: +telemetry/positions).
`availability_for()` answers coverage questions with confidence 1.0 for
impossible and 0.7 for possible-but-unverified — never a guarantee.

## Era model

Overlapping `Era` intervals by kind (technical/sporting/tyre/
power-unit/regulation); `season_eras()` / `eras_by_kind()` are sorted and
deterministic. Built-ins are major documented changes only, each with
confidence (e.g. V6 turbo-hybrid 2014+, DRS 2011+, refuelling ban 2010+,
sprint weekends 2021+).

## Ingestion / normalization / validation

`python -m app.data ingest --source {jolpica,csv,fastf1} ...` fetches and
manifests. Normalization parses dates/durations/compounds/sessions/units;
ambiguous values become `None` + warnings. `AliasRegistry` resolves
entities (accents/case/sponsor-suffix insensitive, conflicts rejected);
race events keep event slugs (San Marino ≠ Emilia-Romagna).
`validate_bundle()` checks duplicates, impossible dates/lap counts,
position ranges, negative times, orphans and points consistency.
`detect_conflicts()` records disagreements with priority-based resolution
and reason (default: official_f1 > fia > jolpica > fastf1 > weather >
external).

## Dataset versioning

Frozen `DatasetVersion` records (`f1-dataset-vX.Y.Z`) with schema/source
versions, coverage, counts, quality score and limitations; registry
(`data/manifests/registry.json`) is append-only — duplicates rejected,
history never mutated.

## Calibration bridge

`FittedCalibrationSet` (tracks/drivers/cars/constructors/era) holds
`CalibratedParameter`s (value, uncertainty, source dataset, fitting
method, dates, model/dataset versions, confidence) and projects onto the
Phase 8 engine-native `CalibrationProfile` (identity when unfitted).
`build-calibration` scaffolds an explicitly-labelled identity baseline.

## Benchmarking & metrics

`run_benchmark()` compares one observed classification against N
simulated distributions from an injected simulator (deterministic stubs
in tests; `HistoricalScenarioBuilder` output wires the real engine).
Metrics: MAE, RMSE, Spearman rank correlation, position/lap-time/DNF/
pit-stop/tyre-degradation errors, Brier score, calibration curves.
`TemporalSplit` assigns seasons to train/validation/test/out-of-sample
by year (default 1950–2000 / 2001–2010 / 2011–2020 / 2021–2026).

## Testing strategy

`tests/test_phase9*.py`: schemas, parsers (fixture payloads, malformed
shapes rejected), normalization ambiguity, resolution (incl. conflicts
and event/circuit separation), provenance hashing/chaining,
availability, version immutability/registry, validation findings,
conflict priority, era overlap, curated regulations, feature
observed/derived/unavailable semantics, determinism, scenario gaps,
calibration projection, metric identities, split assignment, benchmark
distributions, CLI end-to-end in tmp dirs.

## Known limitations

- No bulk historical import has been executed; `data/canonical/` ships
  empty pending licensed sourcing decisions.
- No season-level championship-points cross-check against official
  totals yet (row-level consistency only).
- FastF1 payload materialization is stubbed behind availability.
- No database backend wired (file stores + repository-shaped modules;
  Postgres/Parquet guidance in §Storage below).
- Feature set covers classification-derived signals; lap/sector-level
  features activate once modern-resolution imports land.

## Storage

PostgreSQL for canonical relational entities, Parquet (pandas
available) for lap/telemetry frames, JSON for configs/manifests/small
sets. Batch-oriented ingestion (manifest counts, bulk file writes);
telemetry frames stay out of JSON stores.

## Licensing / data usage

No source data is bundled. Jolpica is a free public API (respect rate
limits / terms); FastF1 requires its own install and downloads cache
under the user's responsibility; weather providers need licensing review
before production use. Curated regulation facts are marked
`provider="curated"` and must not be presented as observed records.
