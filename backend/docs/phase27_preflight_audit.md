# Phase 27 Preflight Audit

Generated 2026-09-20T18:00:00+00:00
Dataset: f1-dataset-v1.3 (races 1172, laps 552656, valid 402199 after filters, pitstops 12747, stints 4840, seasons 1950-2026)

## Variable Availability — Actual Parquet/JSON Inspection

### lap_time
- Availability: true
- Seasons: 1996-2026 for laps_jolpica, 2023-2026 for laps_openf1
- Races: 582 Jolpica partitions, 84 OpenF1 sessions
- Sample size: 552656 total, 402199 valid 50-400s, 88404 with exact tyre join 2023-2026, 81696 after lap-quality filter (valid)
- Missingness: ~1% null lap_time, 0.3% outliers >400s, formation/pit/SC excluded via quality layer not silently deleted
- Evidence tier: CALIBRATED for modern, LIMITED for historical
- Temporal availability: race_date as observation_date, as_of race_date -1 day strict_before, no leakage
- Leakage risk: low if as_of enforced
- Confounding risk: high with progression/fuel/tyre/traffic

### driver
- Availability: true via drivers.json 1457, drivers_openf1 92 session files, alias deterministic mapping driver_number -> driver_id
- Seasons: all, races: 1172
- Sample size: per driver 50-4500 laps, 40 active 2023-2026 with >1000 laps, 909 in driver_model
- Missingness: 0 driver_unmatched per dataset manifest
- Evidence tier: LIMITED/CALIBRATED hierarchical per driver (n>=500 CALIBRATED, 100-500 LIMITED, <100 PRIOR_ONLY)
- Temporal availability: driver career spans, shrinkage toward era global
- Leakage risk: low
- Confounding: driver vs constructor vs circuit confounding high, must control

### constructor
- Availability: true via constructors.json 236, but per-lap constructor mapping sparse via team_name proxy driver_number fallback
- Seasons: all, races: 1172
- Sample size: per constructor 30-4000 laps, many sparse <30
- Missingness: high for historical per-lap constructor not directly in lap parquet, requires join via results
- Evidence tier: LIMITED where n>=300, NON_IDENTIFIABLE where n<30 or driver-constructor perfect collinearity
- Temporal availability: as_of enforced
- Leakage risk: low
- Confounding: very high with driver (same driver same constructor for season), double-count risk, investigate identifiability

### circuit
- Availability: true via circuits.json 99, races.json circuit_id, laps per circuit 59-5058
- Seasons: all, races: 1172
- Sample size: per circuit n_laps 50-5058, n_races up to 30, sparse losail 369
- Missingness: unknown circuit 938 laps
- Evidence tier: CALIBRATED n>=400, LIMITED small n, PRIOR_ONLY <50
- Temporal availability: era shrinkage global->era->circuit  tau30 tau50
- Leakage risk: low with strict_before
- Confounding: circuit vs era vs car development, but identifiable with shrinkage

### season/race/lap_number/stint_lap
- Availability: true for 2023-2026 detailed, 1996-2022 lap_number via Jolpica but stint_lap/tyre_age only 2023-2026
- Seasons: lap_number all, stint_lap only 2023-2026
- Sample size: stint_lap 1-60, lap_number 1-78
- Missingness: stint_lap missing pre-2023 -> NON_IDENTIFIABLE
- Evidence tier: stint_lap PROXY_ONLY, lap_number PROXY_ONLY when used as fuel proxy
- Temporal availability: observable at lap time, no future
- Leakage risk: low
- Confounding: tyre_age vs stint_lap r 0.983 extreme, vs lap_number r 0.497 moderate, progression collinear

### compound/tyre_age
- Availability: compound true 2023-2026 via stints_openf1, 0 pre-2023; tyre_age derived 0-60 monotonic per stint
- Seasons: 2023-2026 only 93096 exact (99.4%), ambiguous 305, unjoined 249, historical 0
- Sample size: soft 10998 medium 33376 hard 44365 intermediate 4111 wet 81
- Missingness: 100% pre-2023, 0% modern after join
- Evidence tier: LIMITED associational only, NON_IDENTIFIABLE causal due to fuel confounding and inverted beta
- Temporal availability: at stint start observable, no future
- Leakage risk: low if join deterministic
- Confounding: extreme with progression, tyre_age vs lap_number 0.497, vs stint_lap 0.983

### pit events
- Availability: true via pitstops_jolpica 12747 + pitstops_openf1 + laps_openf1 is_pit_in/out flags
- Seasons: 1996-2026 but intervals OpenF1 partial 12/84
- Sample size: pit laps 2950 filtered, mean total loss 23.2s median 23.1s
- Missingness: lane/stationary split not in data -> NON_IDENTIFIABLE
- Evidence tier: LIMITED for total loss, NON_IDENTIFIABLE for split
- Temporal availability: pit lap known at lap time
- Leakage risk: low
- Confounding: pit laps slower not due to driver pace, must exclude from ordinary lap model

### race-control state
- Availability: true for 2023-2026 via race_control_openf1 84 files, historical 0
- Seasons: 2023-2026
- Sample size: 8875 messages, 222 SC laps, YELLOW 3263, RED 66, GREEN 85288
- Missingness: 100% pre-2023, SC/VSC historical PRIOR_ONLY
- Evidence tier: PRIOR_ONLY unless n>100 for SC gate
- Temporal availability: as_of strict, no future flag
- Leakage risk: medium if future flag leaks
- Confounding: SC laps correlate with race phase and pit

### weather
- Availability: partial true via weather_openf1 84 files + ERA5 reanalysis 558 races
- Seasons: sensor 2023-2026, ERA5 1950-2026 reanalysis not sensor
- Sample size: observed wet laps 0 in filtered set (but 4192 intermediate/wet unfiltered), dry 88616, ERA5 558 races *24 rows
- Missingness: historical sensor 0, reanalysis not sensor
- Evidence tier: PRIOR_ONLY for wet (insufficient n<50 in filtered), LIMITED if n>300, sensor vs ERA5 not mixed
- Temporal availability: as_of race_date -1 day, do NOT use realized future weather
- Leakage risk: high if future weather injected
- Confounding: weather vs circuit vs season

### qualifying position / grid position
- Availability: true via qualifying.json 26998 and results.json grid_position, but not per lap
- Seasons: all
- Sample size: 26998 qualifying rows, 26228 results
- Missingness: grid not per lap, cannot directly join to lap_time without race simulation
- Evidence tier: LIMITED for qualifying effect, not per-lap feature
- Temporal availability: qualifying before race, as_of respects
- Leakage risk: low if as_of before race
- Confounding: grid vs driver/constructor vs circuit

### finishing position / DNF/status
- Availability: true via results.json final_position, status, time_gap
- Seasons: all
- Sample size: 26228 results, DNF rate ~15%
- Missingness: laps_completed null for early seasons
- Evidence tier: LIMITED for reliability, not per lap
- Temporal: after race, must not leak into lap model
- Leakage risk: high if final result used as lap feature
- Confounding: driver vs constructor vs reliability

### session metadata
- Availability: true via races.json date, round, official_name, scheduled_laps null for early
- Seasons: all
- Sample size: 1172 races
- Missingness: scheduled_laps null early
- Evidence tier: CALIBRATED
- Temporal: known pre-race
- Leakage risk: low
- Confounding: season length changes

## Old Module References vs Actual Data
- Old modules referencing fuel, tyre temperature, pressure, setup telemetry — do NOT assume exist because app/simulation/models references them. Actual parquet has no fuel, no tyre temp/pressure, no setup telemetry. Verified via schema search for fuel_load etc -> not found.
- Weather sensor vs ERA5 distinction verified, not assumed.
- Historical strategy hidden team data not in dataset -> NON_IDENTIFIABLE.

## Leakage & Provenance
- as_of = race_date - 1 day strict_before, leakage violations target 0
- Fingerprint via sha256 of dataset hash 2cce529c/laps ac13fa1f + calibration version + features + seed 42

