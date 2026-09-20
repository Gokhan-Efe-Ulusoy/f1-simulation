# Phase 22.5 — Data Audit

Source: `backend/data/manifests/external_acquisition_manifest.json`.
Staging: `backend/data/external_staging/`. Raw: `backend/data/raw/external/`.

## Acquired totals (all staged, none canonical)

| table | rows | new | dup | invalid | content |
|-------|------|-----|-----|---------|---------|
| `laps_jolpica` | 1129 | 1129 | 0 | 0 | 2024 Bahrain, all drivers+laps, Jolpica timing |
| `laps_openf1` | 1129 | 1129 | 0 | 0 | same race, OpenF1 durations + sectors (1127 with S1) + speed traps + pit flags |
| `pit_stops_jolpica` | 192 | 192 | 0 | 0 | 2024 R1–R5 stop durations (incl. M:SS.mmm + red-flag waits, parsed, not dropped) |
| `pit_openf1` | 43 | 43 | 0 | 0 | 2024 Bahrain observed pit durations |
| `stints_openf1` | 63 | 63 | 0 | 0 | observed compound + tyre_age_at_start (20 drivers × ~3 stints) |
| `weather_openf1` | 157 | 157 | 0 | 0 | 1-min track sensors, session-aligned |
| `race_control_openf1` | 71 | 71 | 0 | 0 | flags/incidents: BLUE×26, CLEAR×4, GREEN×2, DOUBLE YELLOW×2, YELLOW×1, CHEQUERED×1, BLACK AND WHITE×1, Drs×2, SessionStatus×2, CarEvent×2, Other×28 |
| `reanalysis_openmeteo` | 144 | 144 | 0 | 0 | 6 races × 24 hourly ERA5 rows, kind=REANALYSIS |

Total: **2928 staged rows, 32 raw files, 0 warnings, 0 invalid.**

## Parsing notes (no fabrication)

- Jolpica stop durations arrive as seconds (`24.418`) but also `M:SS.mmm`
  (`1:14.773`) and red-flag waits (`26:15.603`, Suzuka 2024 R4). All parse via
  `normalize_duration_seconds` and are kept as observed totals.
- Jolpica durations are totals: `stationary_time_seconds` and
  `pit_lane_time_seconds` are `null` in staging (source does not split them).
- OpenF1 lap 1 differs systematically from Jolpica lap 1 (see conflict audit).
- Reanalysis rows record requested vs grid coordinates + elevation and are
  labeled `REANALYSIS` so they can never be mistaken for track sensors.
- Entity resolution over 1129 Jolpica lap rows: 1129 MATCHED, 0 AMBIGUOUS,
  0 UNMATCHED against canonical driver aliases.

## Cross-validation inputs (not staged as observations)

- f1db pinned release (v2026.13.0): 12 local CSVs counted; independent lineage
  vs Jolpica for future classification cross-checks.
- FastF1: library AVAILABLE, local cache present (2023–2025 Bahrain); no bulk
  pull this phase.

## Leakage

Every staged row preserves `observed_at` (race/session date) + `ingested_at`.
Staging is not calibration input; any future calibration use must obey
`observation_date < as_of` (race_date − 1 day). Reanalysis timestamps are
race-day hourly — usable only for post-hoc analysis, never pre-race features,
unless the timestamp precedes `as_of`.
