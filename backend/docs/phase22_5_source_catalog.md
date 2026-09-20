# Phase 22.5 — Source Catalog (researched 2026-09-19)

Machine-readable: `backend/data/manifests/external_sources.json` (15 entries).
Code: `backend/app/data/external/catalog.py`. License gates: `app/data/external/license.py`.

Every entry below was verified live (HTTP 200 probe or docs inspection) on
2026-09-19. No snippet-only entries. Objective quality flags per source
(`provenance_known, license_known, schema_documented, raw_data_available,
timestamp_available, historical_coverage, granularity_lap_or_better,
independent_verification`) — no subjective scores.

## Priority order (official → open → research → community)

| # | source_id | provider / class | years | granularity | variables | status |
|---|-----------|------------------|-------|-------------|-----------|--------|
| 1 | `official-f1-timing` | Formula 1 / OFFICIAL | 1950–2026 | race | classifications (reference) | BLOCKED (ToS; reference only, never scraped) |
| 2 | `fia-documents` | FIA / OFFICIAL | 1950–2026 | season regulation state | tech/sporting/tyre/quali/DRS/parc fermé/fuel/engine/aero/sprint/points | BLOCKED (no bulk endpoint; curated evidence only) |
| 3 | `jolpica-laps` | Jolpica / PRIMARY_OPEN_DATA | 1996–2026 (verified 2024 R1: 1129 rows) | lap | lap_number, driver, lap_time, position | ACQUIRED |
| 4 | `jolpica-pitstops` | Jolpica / PRIMARY_OPEN_DATA | 2011–2026 (verified 2024 R1: 43 stops) | per stop | lap, stop#, time_of_day, duration (total; split NOT available) | ACQUIRED |
| 5 | `jolpica-results` | Jolpica / PRIMARY_OPEN_DATA | 1950–2026 | race | classification, grid, points, status, standings | ACQUIRED (backbone, pre-existing) |
| 6 | `openf1-timing` | OpenF1 / PRIMARY_OPEN_DATA | 2023–2026 (verified live) | lap + sector | lap_duration, S1/S2/S3, speed trap, pit in/out, position | ACQUIRED (2024 Bahrain, session 9472) |
| 7 | `openf1-stints` | OpenF1 / PRIMARY_OPEN_DATA | 2023–2026 | stint | compound (observed), stint#, lap_start/end, tyre_age_at_start | ACQUIRED (63 rows) |
| 8 | `openf1-weather` | OpenF1 / PRIMARY_OPEN_DATA | 2023–2026 | 1-min, session-aligned | air/track temp, humidity, pressure, rainfall, wind | ACQUIRED (157 rows) |
| 9 | `openf1-racecontrol` | OpenF1 / PRIMARY_OPEN_DATA | 2023–2026 | timestamped event | category, flag, lap, sector, message | ACQUIRED (71 rows) |
| 10 | `openf1-pit` | OpenF1 / PRIMARY_OPEN_DATA | 2023–2026 | per stop | pit_duration (observed), lap, date | ACQUIRED (43 rows) |
| 11 | `openf1-telemetry` | OpenF1 / PRIMARY_OPEN_DATA | 2023–2026 | 3.7 Hz | speed, throttle, brake, rpm, gear, DRS, x/y/z | DOCUMENTED (sample-only policy; not pulled this phase) |
| 12 | `fastf1-timing` | FastF1 MIT / REPUTABLE_SECONDARY | 2018–2026 | sector + telemetry | laps/sectors/car+pos/weather/messages/stints | ACQUIRED (availability probe: AVAILABLE; cache evidence; no bulk pull) |
| 13 | `f1db-database` | F1DB CC BY 4.0 / REPUTABLE_SECONDARY | 1950–2026 | race (+ per-stop rows) | results/quali/sprint/pit/circuits/engines | ACQUIRED (12 local CSVs, pinned v2026.13.0) |
| 14 | `openmeteo-era5` | Open-Meteo ERA5 / VERIFIED_RESEARCH | 1950–2026 (verified live) | hourly reanalysis grid (~11 km) | temp, humidity, precip, pressure, wind | ACQUIRED (144 hourly rows, 6 races; labeled REANALYSIS, never a sensor) |
| 15 | `ergast-mirror-kaggle` | Community mirrors / COMMUNITY_DATA | 1950–2026 claimed (~600k laps, ~22k stops per mirror docs) | lap / per-stop | lap_times.csv, pit_stops.csv (integer-FK relational) | REJECTED (per-dataset license unverified + auth required; documented only) |

## Key research findings

- **Jolpica laps/pitstops endpoints were never ingested by the project pipeline**
  (only results/qualifying/standings). They are the highest-value addition:
  lap-level timing back to ~1996 and stop durations back to ~2011.
  Availability probes (limit=1) returned lap rows for 1996/2000/2005/2010/
  2015/2020/2024 round 1 — full-era pagination is future work, rate-limited.
- **Jolpica `duration` is a total** (stationary + lane loss). The split needed
  for pit-loss calibration is NOT in this source — recorded honestly in staging
  (`stationary_time_seconds: null`, `pit_lane_time_seconds: null`).
- **OpenF1 historical (2023+) is free without auth**; only live data is
  paywalled. Session discovery via `/sessions?year=` → `session_key`.
  Bahrain 2024 Race = session 9472 / meeting 1229 (`location: Sakhir`,
  `country_name: Bahrain` — the discovery filter must match both).
- **Open-Meteo ERA5-Land covers 1950+ hourly** but is a reanalysis grid, not a
  track sensor: no track temperature, ~11 km cells. Staged rows carry
  `kind: REANALYSIS` and grid-vs-requested coordinates.
- **Kaggle/Ergast mirrors are second-hand copies** with per-uploader licenses
  and divergent integer FKs. Ingesting them without per-file verification
  would pollute provenance — rejected this phase, documented for later.
- **Official F1/FIA have no open bulk endpoints.** They stay reference-only
  (manual cross-checks, curated regulation facts). No scraping, per ToS.
