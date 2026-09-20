# Phase 22.7 Source Reconciliation

## Duplicate / Overlap Classification

Known Phase 22.5/22.6 lap-1 offset documented: Jolpica lap numbering is 1-indexed per driver, OpenF1 session laps may include formation lap differences. Preserved both sources.

| Category | Count | Action |
|----------|-------|--------|
| EXACT (byte-identical duplicate rows) | 0 | deduped, kept once |
| REPRESENTATION_DIFFERENCE (lap numbering convention) | documented | preserved both, canonical mapping lap_id = race_id:driver_ref:lap_number |
| SYSTEMATIC_OFFSET (lap-1) | documented | not silently corrected |
| MATERIAL_CONFLICT | 0 | first kept, recorded |
| UNRESOLVED | 0 | none |

## Cross-source overlap (Jolpica vs OpenF1)

OpenF1 families have expected depth: see phase22_6 manifest.
Jolpica rows: 552656, OpenF1 rows (staging): 93650
Overlap not blindly merged; future calibration will select strongest evidence.
