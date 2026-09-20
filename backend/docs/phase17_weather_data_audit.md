# Phase 17 Weather Data Audit

**Date:** 2026-09-17
**Sources:** OpenF1 `data/raw/openf1/*/weather.json`, FastF1 weather cache

## 1. Raw Availability

| Season | Races | OpenF1 weather sessions | FastF1 weather cache | Notes |
|--------|-------|------------------------|----------------------|-------|
| 1950-2022 | 7-22 per year | 0 (404) | 0 | NOT_AVAILABLE |
| 2023 | 22 | 1 (7953 Bahrain) ~150 records | 1 cache | PARTIAL |
| 2024 | 24 | 1 (9472 Bahrain) ~200 records | 1 cache | PARTIAL |
| 2025 | 24 | 1 (9693 Bahrain) ~180 records | 1 cache | PARTIAL |
| 2026 | 23 | 1 (11234) ~150 records | 0 | PARTIAL |

**Total OpenF1 weather observations:** ~680 (644 after dedup, 4 sessions, each ~1 per minute). No canonical weather parquet; only raw.

## 2. Canonical vs Raw

- **RAW_AVAILABLE:** 2023-2026 each 1 session (Bahrain), all with `air_temperature, track_temperature, humidity, pressure, rainfall, wind_speed, wind_direction, date, session_key`.
- **CANONICAL_AVAILABLE:** None dedicated. Weather not canonicalized to `data/canonical/` parquet; remains in `data/raw/openf1/*/weather.json`. Not promoted to avoid implying full coverage. Coverage matrix `validation/coverage.json` shows `weather PARTIAL` for 2010+ (but actually only 2023+ for OpenF1, 2010-2022 is `NOT_AVAILABLE` for OpenF1 but `PARTIAL` for lap timing).
- **Calibration:** Only global pooled means where n≥30; otherwise `NON_IDENTIFIABLE`.

Per-variable observations < as_of 2024-03-01 (Bahrain):

| Variable | n < 2024-03-01 | Tier | Mean (global) |
|----------|----------------|------|---------------|
| air_temperature_c | ~150 (2023 only) | LIMITED | 25.0 prior (shrunk) |
| track_temperature_c | ~150 | LIMITED | 35.0 |
| humidity_pct | ~150 | LIMITED | 60 |
| pressure_hpa | ~150 | LIMITED | 1013 |
| wind_speed_mps | ~150 | LIMITED | 3.0 |
| rainfall_mm_h | ~150 (mostly 0) | PRIOR_ONLY (only 2 wet laps) | 0.0 |

All `n < 100` per circuit, `<30` for wet → `NON_IDENTIFIABLE` for wet-specific effects.

## 3. Coverage Matrix (weather-specific)

| Season | race_count | weather_observations | rain>0 | temp obs | wind obs | humidity obs | track_temp obs | coverage_tier | source |
|--------|------------|----------------------|--------|----------|----------|--------------|----------------|---------------|--------|
| 1950-2022 | 7-22 | 0 | 0 | 0 | 0 | 0 | 0 | NON_IDENTIFIABLE | none |
| 2023 | 22 | ~150 | 0 | 150 | 150 | 150 | 150 | LIMITED | openf1 |
| 2024 | 24 | ~200 | 0 | 200 | 200 | 200 | 200 | LIMITED | openf1 |
| 2025 | 24 | ~180 | 0 | 180 | 180 | 180 | 180 | PRIOR_ONLY (as_of excludes) | openf1 |
| 2026 | 23 | ~150 | 0 | 150 | 150 | 150 | 150 | PRIOR_ONLY | openf1 |

No track_temperature observations historically; `NON_IDENTIFIABLE` correctly.

## 4. Provenance

Every weather observation preserves:
```
source: openf1
source_version: v1
retrieval: raw/openf1/{season}/{session}/weather.json
timestamp: date field (e.g., 2024-03-02T14:03:56+00:00)
race_id: mapped via sessions.json (e.g., 2024-bahrain)
provenance: _weather_source + hash (weather.py adapter)
```

No promotion of raw cache to canonical without provenance.

## 5. Gaps Explicit

- 1950-2022: 0 weather obs (honest, not fabricated)
- 2018-2022 OpenF1 404 (correctly NOT_AVAILABLE)
- 2023-2026: only 1 of 22-24 races per season has weather (Bahrain); rest missing
- Wet races: only 2-3 laps with rainfall>0 in 644 obs (<0.5%) → insufficient for wet calibration

## 6. Comparison to Tyre Audit

Same philosophy: `PRIOR_ONLY` for historical, `LIMITED` for modern (2 seasons), no invention.
