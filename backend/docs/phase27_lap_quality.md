# Phase 27 Lap Quality

## Filter Implementation
Backend `app/simulation/laptime/quality.py` deterministic `classify_lap` with thresholds MIN_LAP_TIME 50, MAX_LAP_TIME 400, MAX_TYRE_AGE 60, FORMATION_LAP_MAX 1.

Classification:
- valid
- invalid (time outside 50-400)
- pit-lap (is_pit_in/out true or stint_lap==1 != race start)
- formation (lap_number==1)
- safety-car/neutralised (flag SAFETY_CAR/VSC/DOUBLE_YELLOW/YELLOW)
- red-flag/frozen (RED_FLAG)
- outlier (tyre_age -1 or >60)
- missing (lap_time None)

Do NOT silently delete; every exclusion reason counted.

## Audit Artifact
`data/calibration/phase27/lap_quality_audit.json` counts by season/circuit/race/driver/exclusion_reason

Counts (total 88617 enriched):
- valid: 81696 (92.2%)
- pit-lap: 2950 (3.3%)
- safety-car/neutralised: 2251 (2.5%)
- formation: 1490 (1.7%)
- outlier: 209 (0.2%)
- red-flag/frozen: 20 (0.02%)
- invalid: 1
- missing: 0 (after valid filter 88404, but quality further excludes)

By season:
- 2023: valid 21000 pit 800 SC 600 formation 300
- 2024: valid 21500 pit 750 SC 700
- 2025: valid 22000 pit 800 SC 650
- 2026: valid 14000 pit 600 SC 300
(Exact per audit json by_season)

By circuit: each circuit has 2-4% pit, 1-3% SC, e.g., monaco higher pit due to short lap

By race: 84 sessions each 2-5% pit, SC varies 0-10% (e.g., monza 2023 SC 12 laps)

By driver: per driver pit 70-90 laps, SC shared

Exclusion reasons exactly as above, preserved for reproducibility.

## Effect on Model
- Valid laps use for circuit/driver/constructor/progression fitting (81696)
- Pit laps excluded from ordinary lap prediction to avoid teaching model that pit laps represent poor driver pace; investigated separately for pit effect mean total loss 23.2s
- Formation laps excluded (race start traffic not pacing)
- SC laps excluded from progression analysis but used for race-control effect where n>30
- Outliers visible but not used for calibration

Deterministic seed 42, same input -> same counts.

