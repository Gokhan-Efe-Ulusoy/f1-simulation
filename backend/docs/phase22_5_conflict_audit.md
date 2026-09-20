# Phase 22.5 — Conflict Audit

Machine-readable: `backend/data/manifests/external_conflicts.json`.
Code: `backend/app/data/external/conflicts.py`
(`classify_numeric_diff`, `detect_lap_conflicts`, `conflict_pattern`,
`detect_result_conflicts`).

## Result: 20 conflicts over 1129 compared lap pairs (1.77%)

- Tolerance: 2 ms rounding band. All other 1109 pairs agree within rounding.
- Pattern: `systematic_single_lap_offset`, lap `1`, direction `B_slower`
  (OpenF1 slower on all 20).
- Every conflict is lap 1, one per driver (all 20 drivers), OpenF1 slower by
  **0.317–0.510 s** (e.g. VER 97.284 vs 97.759; LEC 98.271 vs 98.679).

## Interpretation (recorded, not resolved away)

All disagreements on one lap with one sign = **timing-definition difference**,
not random measurement error: Jolpica lap-1 times are measured from race start
lights while OpenF1 `lap_duration` is measured from the lap-start line, so the
start-offset (~0.3–0.5 s reaction + positioning) appears on lap 1 only. Laps
2–57 agree within 2 ms across all drivers — strong independent verification of
both sources.

## Disposition

- No canonical data changed (canonical holds no lap-level rows to conflict with).
- Both observations preserved in staging with provenance; neither selected.
- Conflict rate 1.77% < 5% gate ceiling → lap_timing remains a promotion
  candidate (LIMITED, observed era only), with the lap-1 definition caveat
  attached for any future calibration use (exclude or offset-model lap 1).
- `detect_result_conflicts` (canonical vs staging classifications) found no
  staging classification rows to compare — no classification conflicts exist.
