# Phase 22.6 — Preflight Audit (2026-09-19, before any bulk download)

## 1. Current ingestion architecture

- Adapters (`app/data/sources/`): `base` (RawBundle/SourceAdapter contract, injectable
  transport), `jolpica` (results/qualifying/standings only — laps/pitstops NEVER
  ingested), `openf1` (session discovery + `fetch_session`), `f1db_adapter`
  (pinned GitHub ZIP v2026.13.0, sha256), `fastf1_adapter`, `csv_adapter`,
  `fia`, `github`, `kaggle`, `weather` (generic). Phase 22.5 added
  `app/data/external/` (download/checksums/license/normalization/dedup/conflicts/
  resolution/promotion/coverage) + `scripts/phase22_5_acquisition.py`.
- Canonical schemas: `app/data/models/canonical.py` (JSON families) + parquet trees.
- Manifests (`data/manifests/`): `registry.json` (v1.0, v1.1 + model versions),
  `dataset-manifest.json` (v1.1), `external_*.json` (22.5), `checkpoint_jolpica.json`,
  `source_catalog/coverage.json`.
- Provenance/hash infra: `app/data/provenance.py` (`utc_now_iso`, `hash_payload`),
  `app/data/external/checksums.py` (sidecar + `verify_sidecar`), license gates
  (`app/data/external/license.py`).
- Phase 22.5 staging: `data/external_staging/` (8 tables, 2928 rows, 2024 slice).

## 2. Current coverage matrix (canonical v1.1 + trees)

| family | seasons | races/rows | note |
|---|---|---|---|
| results | 1950–2026 | 1172 races / 26228 rows | FULL |
| qualifying | 1950–2026 | 26998 rows | PARTIAL |
| pit_stops.json | 1994–1995 | 1000 rows | sparse legacy |
| pit_stops.parquet | 1994–2026 | **22490 rows** | modern Ergast-sourced; see §5 |
| laps/ (openf1 tree) | 2023–2026 | 4 sessions (~4.6k rows) | 1 Bahrain session/season, NO provenance cols |
| sectors/, telemetry/ | — | empty dirs | NOT_AVAILABLE |
| laps_jolpica | — | 0 | target of this phase |
| stints/weather/race_control | — | 0 canonical (22.5 staged only) | target |

## 3. Source matrix (this phase)

| source | class | range | endpoint status (probed) |
|---|---|---|---|
| Jolpica laps | A | 1996–2026 (1990/94/95 return total=0; 1996 R1 total=812) | paginated ≤100 |
| Jolpica pitstops | A | 2011–2026 (2010 total=0; 2011 R1 total=45) | 1–2 pages/race |
| Jolpica results/quali/standings | A | 1950–2026 | already ingested |
| OpenF1 sessions/laps/stints/weather/pit/race_control/... | B | 2023–2026 (2018–2022 = HTTP 404, never retry) | 23–25 Race sessions/yr |
| Open-Meteo ERA5 archive | B | 1950–2026 | live OK, REANALYSIS label |
| f1db pinned release | B | 1950–2026 | local, CC BY 4.0 |
| FastF1 library | B | 2018–2026 | AVAILABLE, cache present |
| Kaggle mirrors | D | — | REJECTED (license/auth) |
| FIA / F1 official | E | — | reference-only, no scraping |

## 4. Missingness matrix (pre-backfill)

laps: 1996–2022 fully missing (~460 races), 2023–2026 one session each;
pitstops: covered in parquet 1994–2026 (verify vs Jolpica = reconciliation);
sectors/stints/weather/RC: missing except 22.5 single-race staging;
telemetry: missing (sample policy); setup/strategy/fuel: NON_IDENTIFIABLE.

## 5. Duplicate-risk analysis (CRITICAL finding)

`pit_stops.parquet` (22490 rows, 1994–2026) already contains the same stops
Jolpica would return (verified: 2024 Bahrain 43 = 43). Jolpica pit backfill is
therefore **DUPLICATE + enrichment** (adds `duration` semantics check,
`time_of_day`, `stop_number`), NOT new rows. Canonical `pit_stop_id`
(`{race_id}:{driver_id}:{stop}`) vs Jolpica identity
(`season/round/driver_ref/lap/stop`) must be joined via race map + driver
resolution; overlap quantified in reconciliation, never double-counted.
Laps 1996–2022 have NO canonical counterpart → genuinely new. OpenF1 2023–2026
Race sessions beyond the 4 staged ones are new. Canonical `laps/` tree must NOT
be rewritten (downstream readers + missing provenance cols); new families are
created alongside.

## 6. Schema compatibility

New parquet families carry superset provenance columns
(source, source_version, retrieved_at, source_record_id, race_id, season,
round, evidence_tier, raw_sha256, canonicalization_version) + deterministic IDs
(`{race_id}:{driver_ref}:{lap}`). Existing `laps/` tree schema untouched.

## 7. Rate-limit plan

Jolpica/OpenF1/Open-Meteo: 1.2 s spacing (≥1 req/s per spec), ≤100/page,
exponential backoff on 429 (honor Retry-After), checkpoint resume, verified
files never re-downloaded. 2018–2022 OpenF1 never requested (known 404).

## 8. Storage estimate

Jolpica laps ~550 races × ~1100 rows ≈ 600k rows (~75 MB raw JSON, ~15 MB
parquet); pits ~350 races (~20k stops, ~4 MB); OpenF1 96 Race sessions
(~110k laps + stints/weather/RC ≈ 40 MB raw); ERA5 ~30 races (~1 MB).
Total < 150 MB raw, < 60 MB parquet. Disk free: 166 GB. Bounded-memory:
per-round streaming writes, no bulk DataFrames.

## 9. Legal/access classification

All bulk endpoints A/B with free historical access; attribution for f1db/CC-BY
sources; Kaggle D rejected; FIA/F1 E untouched. No ToS violated.

## 10. Expected scientific value

Lap-level evidence 1996–2022 (currently zero) enables degradation/fuel/pilot
studies; pit distributions per circuit/era (from parquet + Jolpica enrichment);
sector/stint/weather/RC 2023–2026 enables modern calibration candidates — all
gated, none auto-promoted.
