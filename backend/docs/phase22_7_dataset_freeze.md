# Phase 22.7 Dataset Freeze

Generated: 2026-09-20T11:54:22.499280+00:00

## Dataset version

- version: f1-dataset-v1.3
- parent: f1-dataset-v1.2
- frozen: true
- creation_timestamp: 2026-09-20T11:54:22.499280+00:00

## Hashes

- races: 2cce529c
- results: 112c8475
- backbone: UNCHANGED_FROM_V1.1
- laps_jolpica: ac13fa1f

## Coverage

- laps_jolpica races: 582 (1996-2026, 483 for 2002+ plus 99 pre-2002)
- laps_jolpica rows: 552656
- laps_jolpica partitions: 582
- pitstops, sectors, stints, weather, race_control: see registry

## Provenance

- acquisition manifest: phase22_7_laps_acquisition_manifest.json
- canonical manifest: phase22_7_canonical_manifest.json (version 22.7.0)
- conflicts: 0 material, 0 duplicate identical
- quality metrics: duplicate_pks=0, orphan_races=0, orphan_drivers=0, leakage=0
- quarantine: 0 (future 2026)

## Limitations

- 2026 season future races 15-23 NOT_AVAILABLE (season in progress)
- intervals_openf1 parquet partial (12/84); raw complete
- pit durations are totals; lane/stationary split NON_IDENTIFIABLE
- ERA5 rows are REANALYSIS, not sensors
- telemetry bulk not acquired
- setup/strategy/fuel NON_IDENTIFIABLE
- OpenF1 overlap classified, not blindly merged; future calibration will select strongest evidence
- lap-1 systematic offset documented between Jolpica and OpenF1 lap numbering
