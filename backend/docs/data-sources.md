# Data Sources

Source-by-source coverage. Nothing here grants a license; verify terms
before production ingestion.

## jolpica (Ergast-compatible API)

- Access: public JSON over HTTPS, no key. Base:
  `https://api.jolpi.ca/ergast/f1`. Respect rate limits.
- Adapter: `app/data/sources/jolpica.py` (`JolpicaAdapter`).
- Covers: seasons/schedule, round results, qualifying, drivers,
  constructors, standings. Seasons 1950–present for results/qualifying
  where the upstream holds them; no lap/sector/telemetry/tyre detail.
- CLI: `python -m app.data ingest --source jolpica --season 2024 [--round 1]`

## official_csv (local public archives)

- Access: user-supplied CSV extracts placed under `data/raw/external/`.
- Adapter: `app/data/sources/csv_adapter.py` (`OfficialCsvAdapter`).
- Files: `drivers.csv`, `constructors.csv`, `races.csv`, `results.csv`
  (headers validated; unknown columns preserved; blank lines skipped;
  bad rows rejected with line numbers).
- CLI: `python -m app.data ingest --source csv --csv-dir <dir> --season 2024`

## fastf1 (modern session data)

- Access: optional `fastf1` package (not a base dependency) plus its own
  Ergast/F1-timing data sources and local cache.
- Adapter: `app/data/sources/fastf1_adapter.py` (`FastF1Adapter`).
- Covers (when available): sessions, laps, sectors, telemetry, tyres,
  weather, positions for modern seasons. Without the backend every fetch
  raises `DataUnavailable` — absence is reported, never synthesized.
- CLI: `python -m app.data ingest --source fastf1 --season 2024
  --event Bahrain --session R` (requires backend + network/cache).

## official_f1 / fia

- Reserved provider slots for licensed/official documents and
  regulation texts. No adapter ships yet; add under
  `app/data/sources/` following the `SourceAdapter` contract with full
  provenance (URL, retrieval time, parser version, hash).

## weather providers

- Reserved slot. Licensing must be reviewed per provider before use;
  observations land in `HistoricalWeatherObservation` with explicit units.
