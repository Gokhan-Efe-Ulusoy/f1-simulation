# Phase 26 Fuel Data Audit

Generated 2026-09-20T17:45:00+00:00

## Objective
Search complete dataset and acquired sources for actual fuel measurements. Do NOT create synthetic ground-truth fuel data.

## Potential Fields Searched
- fuel_load
- fuel_remaining
- fuel_used
- fuel_mass
- fuel_fraction
- fuel_laps_remaining
- fuel_consumption
- fuel_capacity
- starting_fuel

Search scope:
- data/canonical/* (all parquet families: laps_jolpica, laps_openf1, stints_openf1, pitstops, weather, race_control, intervals, results, qualifying, drivers, constructors, circuits, era5)
- data/raw/* (openf1 raw, fastf1 cache, jolpica raw)
- data/calibration/* (phase23, phase24, phase25)
- data/manifests/*
- app/simulation/* (lap_time, tyre, strategy/fuel, race_engine, core)
- docs/* all prior phase docs
- external_staging /*

Methods: recursive file content search via rg, parquet schema inspection, json field enumeration, manifest coverage analysis.

## Results

### Canonical Data
- laps_jolpica schema 20 cols: lap_id race_id season round driver_ref driver_id lap_number lap_time_seconds position source ... NO fuel field
- laps_openf1 schema 19 cols: session_key meeting_key driver_number lap_number lap_time_seconds sector_1_2_3 speed_trap is_pit_in/out etc: NO fuel field
- stints_openf1 schema 16 cols: session_key driver_number stint_number compound lap_start lap_end tyre_age_at_start etc: NO fuel field
- pitstops_jolpica: pit_stop_id race_id driver_id lap_number stationary_time_seconds: NO fuel
- intervals_openf1: interval times/gaps: NO fuel
- weather_openf1: air/track temp humidity pressure rainfall wind: NO fuel
- race_control_openf1: flag category message: NO fuel
- reanalysis_era5: temperature precipitation: NO fuel
- results/qualifying/races: positions, times, status: NO fuel
- telemetry bulk not acquired (see unavailable_data.json: telemetry only for 2024 probe)

### Acquired Sources
- Jolpica: no fuel endpoint, known limitation in f1-dataset-v1.3 hashes: "setup/strategy/fuel NON_IDENTIFIABLE"
- OpenF1 API: stints, laps, intervals, race_control, weather, team_radio, positions - none expose fuel_load per docs/phase22_7_coverage_matrix.md
- FastF1: telemetry per driver includes FuelLoad? Probe in phase22_7_probe.py checked FastF1 2024 Bahrain laps columns: Driver Number LapNumber Compound TyreLife LapTime Stint etc - NO fuel per lap in available telemetry probe (telemetry not bulk, single session 337 laps)
- F1DB local: no fuel table
- ERA5: weather reanalysis only
- Github/kaggle adapters: not fuel

### Manifests
- f1-dataset-v1.3.json known_limitations: explicitly lists "setup/strategy/fuel NON_IDENTIFIABLE", "telemetry bulk not acquired", "intervals_openf1 parquet partial", "pit durations are totals; lane/stationary split NON_IDENTIFIABLE"
- unavailable_data.json fields: tyre_stints false pre-2011, telemetry false 1950-2017 (only 2024), weather false pre-2023, race_control false pre-2023 - fuel not listed as available
- phase23_fuel_identifiability.md: "Fuel exact load unavailable -> proxy race lap number/stint progression/pit timing/distance/tyre_age/SC... fuel effect NON_IDENTIFIABLE"

### Simulation-Internal Fuel
- app/simulation contains fuel_mass, fuel_remaining, fuel_used ONLY as simulation-internal state variables, NOT as observed historical measurements:
  - lap_time/model.py: fuel_mass input to LapTimeInputs (simulation parameter, not observed)
  - core/state.py: fuel_remaining state variable
  - strategy/fuel.py: FuelStrategyOptimizer base_fuel_consumption 1.8 kg/lap, fuel_tank_capacity 110kg, simulation strategy optimization, NOT evidence from historical data
  - These are theoretical F1 approximations (0.035s per 10kg) used in forward simulation, never claiming to be measured historical fuel per lap

No file contains observed historical fuel_load per lap per driver per race.

## Actual Fuel Data Status

```
ACTUAL_FUEL_DATA = NOT_AVAILABLE
source: none
sample_size: 0
temporal_coverage: none
race_coverage: 0 / 1172
driver_coverage: 0 / 1457
uncertainty: NON_IDENTIFIABLE
provenance: searched all families 1084830 new rows, 84 OpenF1 sessions, 582 Jolpica partitions, no field found
```

If actual measurements exist they would require: source name, sample size, temporal coverage, race coverage, driver coverage, uncertainty, provenance. None exist.

## Evidence Tier

ACTUAL_FUEL_DATA = NOT_AVAILABLE, EVIDENCE_TIER = NOT_IDENTIFIABLE for physical fuel kg.

Do NOT create synthetic ground-truth fuel data. Do NOT calibrate kg/lap from arbitrary assumptions. No fabricated fuel_remaining, fuel_mass, fuel_load.

## Implication

Fuel must be treated via clearly labelled FUEL_PROGRESSION_PROXY only, evidence_tier PROXY_ONLY, not physical measurement. See phase26_fuel_proxy.md

