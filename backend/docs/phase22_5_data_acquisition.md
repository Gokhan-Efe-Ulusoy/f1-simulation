# Phase 22.5 — Data Acquisition

Runner: `backend/scripts/phase22_5_acquisition.py`.
Pipeline: `backend/app/data/external/` (`base, catalog, download, checksums,
license, normalization, deduplication, conflicts, resolution, promotion,
coverage`). Regulation schema: `backend/app/data/regulations/schema.py`.

## Commands (from `backend/`)

```bash
python scripts/phase22_5_acquisition.py            # live run (rate-limited ~1.5 s)
python scripts/phase22_5_acquisition.py --offline  # rebuild staging+manifests from raw only
```

The offline run is bit-reproducible: same staging identities, same 20
conflicts, same pattern (`dup_vs_previous` = full overlap on re-run).

## Acquisition scope (deliberate, not exhaustive)

Bulk-pulling 77 seasons of laps would be ~1300 races × ~11 pages ≈ 14k
requests — abusive to free APIs. This phase acquires a **high-value,
rate-respectful slice** and proves the pipeline end to end:

- Jolpica laps: 2024 R1 full (12 pages, 1129 rows) + availability probes
  1996/2000/2005/2010/2015/2020/2024 R1 (all returned lap rows).
- Jolpica pitstops: 2024 R1–R5 full (43+19+36+54+40 = 192 rows).
- Jolpica results 2024 R1 (driver `{code → driverId}` join map, 20 entries).
- OpenF1 2024 Bahrain Race (session 9472): laps 1129, stints 63, weather 157,
  pit 43, race_control 71, drivers 20/20 mapped.
- Open-Meteo ERA5: 6 anchor races × 24 hourly rows = 144 (Bahrain, Jeddah,
  Melbourne, Suzuka, Monaco, Silverstone 2024).
- f1db: 12 local pinned-release CSVs counted for cross-validation (no re-download).
- FastF1: availability probe (AVAILABLE) + cache evidence; no bulk pull.

## Raw immutability

`backend/data/raw/external/<source_id>/<file>` + `<file>.provenance.json`
(sha256, url, license, timestamp, size). 32 raw files. Re-download is skipped
when the sidecar hash verifies. `verify_sidecar()` is tested.

## Staging (NOT canonical)

`backend/data/external_staging/*.json` — 8 tables, 2928 rows total. Every row
carries `provenance {source_id, source_file, source_record_id, observed_at,
ingested_at}`. Canonical `f1-dataset-v1.1` is untouched (see promotion gate).

## What was NOT pulled (and why)

- OpenF1 telemetry (`/car_data`, `/location`): 3.7 Hz × 20 drivers is
  high-volume; policy is deliberate sampling in a later phase. Endpoint
  documented, gate allows, count = 0 this phase.
- Kaggle mirrors: license unverified per dataset + auth → rejected.
- FIA/F1 official: no bulk endpoint + ToS → reference-only.
- Pre-1996 laps / pre-2011 stops / pre-2023 sectors-weather-stints-RC:
  no legally accessible source found — tiers unchanged (honest gaps).
