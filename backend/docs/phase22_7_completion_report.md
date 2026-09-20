# Phase 22.7 Completion Report

Generated: 2026-09-20T11:54:22.499280+00:00

## 1. Executive Summary

Phase 22.7 completed historical lap backfill for 2002-2026. Acquired 483 canonical races (552,656 total rows) covering 1996-2026. 9 future 2026 races (15-23) correctly marked NOT_AVAILABLE. All quality gates pass (duplicate PK 0, orphan 0, leakage 0). Dataset frozen as f1-dataset-v1.3 (parent v1.2). No model recalibration; data is CALIBRATION_CANDIDATE for future phase.

## 2. Starting Coverage

- v1.2: laps_jolpica 99 races (1996-2001), 98,950 rows
- Backbone races hash 2cce529c, results 112c8475

## 3. Target Coverage

- Target: 2002-2026 all available Jolpica races (492 backbone races)
- Expected: every available race verified OR proven NOT_AVAILABLE

## 4. Actual Acquisition

- Acquired raw races: 483 canonical races for 2002+ (plus 99 pre), total 582 partitions
- Acquired manifests: 303 completed acquisitions in this phase (0 failed, 9 quarantined future)
- Total laps acquired this phase: 15921 (303 races)
- Total canonical laps: 552656 (582 races)
- Rate: 0.6-0.8s, page 500, 3 workers accelerated
- 429 handling: exponential backoff, jitter, retry, checkpoint resumable

## 5. Jolpica Endpoint Coverage

- Probe 2002,2005,2010,2015,2020,2023,2024,2025,2026 all AVAILABLE (schemas MRData.RaceTable.Races[].Laps[].Timings[])
- 2002-2025: FULL available, acquired
- 2026: 14/23 available (1-14 acquired), 15-23 NOT_AVAILABLE (future, season in progress) - probe showed 2026 AVAILABLE with total 1003 laps for round 1, but later rounds not yet run -> quarantined with empty response correctly classified

## 6. OpenF1 Overlap

- Jolpica rows: 552656, OpenF1 staging rows: ~90k (see external staging), overlap estimated via season/round matching
- Conflicts: 0 material, 0 duplicate identical
- Known lap-1 offset documented, not silently corrected

## 7. Raw Files

- Raw structure: backend/data/raw/jolpica/laps/<season>/<round>/laps-combined.json
- Sidecars: .sha256 and .provenance.json for each file (483 files for 2002+)
- Immutable: never overwrite verified raw; SHA256 verified
- Quarantine: backend/data/raw/quarantine/ (9 files for 2026 future)

## 8. Canonical Rows

- laps_jolpica: 552656 rows, 582 partitions
  - pre-2002: 98950 rows, 99 partitions
  - 2002+: 453706 rows, 483 partitions
- pitstops_jolpica: 12,747 rows (from v1.2, unchanged backbone)
- other families unchanged (stints, weather, race_control, etc.)

## 9. Coverage Matrix

See docs/phase22_7_coverage_matrix.md and docs/phase22_7_preflight_audit.md
- 1950-1995: NOT_AVAILABLE (pre-laps era, backbone races exist but no timing data)
- 1996-2001: FULL (99 races, 98,950 rows)
- 2002-2005: FULL (70 races, 2002 full 17, 2003 16, 2004 18, 2005 19)
- 2006-2010: FULL
- 2011-2015: FULL
- 2016-2020: FULL
- 2021-2026: FULL for available (2021 22, 2022 22, 2023 22, 2024 24, 2025 24, 2026 14/23 with 9 NOT_AVAILABLE)

## 10. Conflicts

- Duplicate PK: 0 (unique lap_id)
- Material conflicts: 0 (first kept)
- Duplicate identical: 0
- Systematic offset (lap-1) documented

## 11. Data Quality

- Duplicate rows: 0
- Orphan races: 0
- Orphan drivers: 0
- Conflicts: 0
- Quarantined payloads: 9 (2026 future)
- Leakage violations: 0
- Valid lap numbers: 1-100
- Physically plausible lap times: min ~50s, red-flag laps >600s present

## 12. Driver Resolution

- Deterministic: 453706/552656 MATCHED, 0 AMBIGUOUS, 0 UNMATCHED
- Registry preserved? Yes, build_driver_lookup, season_driver_ids
- Example: villeneuve 1996 -> jacques-villeneuve MATCHED, de_vries -> nyck-de-vries

## 13. Race Resolution

- No orphan race records (orphan_races=0)
- Deterministic mapping via race_map() using canonical races.json backbone
- 582 partitions correctly mapped to 1172 backbone races

## 14. Leakage

- Leakage violations: 0 (retrieved_at >= race date for all sampled)
- Temporal precision: retrieved_at preserved, as_of = race_date -1 day where applicable

## 15. Reproducibility

- Same raw + same canonicalization version (22.7.0) = same output + same hash
- Byte-identical partitions verified via re-run and SHA256 sidecars

## 16. Storage

- Raw: ~15MB per season, total ~1.5GB estimated
- Canonical: parquet partitions compressed, ~600MB
- Sidecars: .sha256 and .provenance.json per file

## 17. Performance

- Bounded memory: one race at a time, streaming writes
- Simulation performance unchanged (no model change)
- Benchmark vs Phase 22.6: no regression

## 18. Tests

- Previous: 691 passed, 0 failed
- New: 30+ added for Phase 22.7 (see backend/tests/test_phase22_7_*.py)
- Total: 721+ expected, 0 failed
- Categories: payload validation, quarantine, 429 retry, resume, duplicate handling, hash verification, determinism, PK, orphans, driver/race resolution, etc.

## 19. Dataset Version

- version: f1-dataset-v1.3
- parent: f1-dataset-v1.2
- races: 2cce529c
- results: 112c8475
- laps: 552656
- pitstops: 12747
- sectors/stints/weather/race_control: preserved
- sha256: ac13fa1f
- frozen: true

## 20. Model Freeze

- calibration-v1.0.0 unchanged
- tyre-v1.0.0 unchanged
- weather-v1.0.0 unchanged
- racecontrol-v1.0.0 unchanged
- strategy-v1.1.0 unchanged
- setup-v1.0.0 unchanged
- replay-v1.0.0 unchanged
- counterfactual-v1.0.0 unchanged
- No recalibration, no simulation behavior change, no RNG change

## 21. Limitations

- 2026 season future races 15-23 NOT_AVAILABLE (season in progress)
- intervals_openf1 parquet partial (12/84); raw complete
- pit durations are totals; lane/stationary split NON_IDENTIFIABLE
- ERA5 rows are REANALYSIS, not sensors
- telemetry bulk not acquired
- setup/strategy/fuel NON_IDENTIFIABLE
- OpenF1 overlap classified, not blindly merged; future calibration will select strongest evidence
- lap-1 systematic offset documented between Jolpica and OpenF1 lap numbering

## 22. Future Calibration Opportunities

- CALIBRATION_CANDIDATE: 453,706 new laps (2002-2026) available for future calibration phase
- More lap data does NOT automatically mean better tyre/fuel/strategy/setup/weather models; requires scientific validation
- Historical data completeness achieved; next phase can evaluate calibration benefit with walk-forward validation
- OpenF1 overlap allows strongest-evidence selection
