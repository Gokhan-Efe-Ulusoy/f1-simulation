# Phase 26 Preflight Audit

Generated 2026-09-20T17:45:00+00:00

## Dataset
- f1-dataset-v1.3 frozen, 552656 laps_jolpica (1996-2026), valid race laps 402199 after filtering 50-400s, stints_openf1 4840 (2023-2026 only), pit 12747, race 1172, driver 1457, qualifying 26998, circuits 99, constructors 236
- Canonical laps: laps_jolpica 16 cols, laps_openf1 19 cols, stints_openf1 16 cols, drivers_openf1 16 cols, intervals_openf1 partial 12/84, weather_openf1 18 cols, race_control_openf1 16 cols, reanalysis_era5 12 cols
- Hashes: races 2cce529c, laps_jolpica ac13fa1f, results 112c8475, dataset frozen true, leaks 0

## Phase 23 Calibration Mart
- Path backend/data/calibration/phase23/ lap_mart.parquet 552656, stint_mart 4840, pit_mart 12747, race_mart 1172, driver_race 26228
- Provenance regenerable via scripts/phase23_calibration.py seed 42, temporal_policy strict_before_as_of, reproducible true
- Every row preserves race_id season round driver constructor circuit lap source source_timestamp observation_date as_of evidence_tier
- No manual edits, derived artifact only

## Phase 24 Circuit Model
- Version circuit-v1.0.0-candidate status CANDIDATE tier LIMITED, circuits 52, eras 7, hierarchical shrinkage global->era->circuit->circuit_era tau30 tau2_50
- Global baseline 94.0517s, example spielberg -20.17 n12438 se0.07 LIMITED, losail 4.04 n369 shrunk0.86, sparse shrink to era->global not independent constants
- Every circuit estimate se sample_size race_count season_range shrinkage_weight evidence_tier, sparse not dominate

## Phase 25 Exact Tyre Join
- Join key race_id+driver_number+lap_number between lap_start and lap_end deterministic via resolve_lap
- Total OpenF1 laps 93650, exact 93096 (99.4%), deterministic 0, ambiguous 305 (0.33% overlapping stints), unjoined 249, invalid 0, NaN 29 stints -> UNJOINED
- Coverage by season 2023:24254 2024:26475 2025:26141 2026:16226; by circuit 24-52 circuits each 2-4 sessions (jeddah 2739, zandvoort 5495, monaco 5555 etc); by compound hard 44365 medium 33376 soft 11078 intermediate 4111 wet 81 "" 85
- Historical 1996-2022 0% joinable -> NON_IDENTIFIABLE, never silently infer ambiguous tyre ages, only EXACT/DETERMINISTIC may enter causal calibration

## Canonical Laps
- laps_jolpica: lap_id race_id season round driver_ref driver_id lap_number lap_time_seconds position source etc
- laps_openf1: session_key meeting_key driver_number lap_number lap_time_seconds sector_1_2_3 speed_trap is_pit_in/out race_id season evidence PARTIAL
- tyre_age: int 0-60 derived via stint tyre_age_at_start + (lap_number - lap_start), monotonic per stint verified, stint_lap = lap_number - lap_start +1, integer not interpolated fractional

## Stint Lap / Lap Number / Race Progress
- tyre_age available only 2023-2026 exact join, stint_lap 1..max per stint, lap_number 1..max per race ( Jeddah 50, Monaco 78 etc), race_progress normalized_lap = lap_number / max_lap_per_race, remaining_laps = max - lap_number, race_phase terciles early <0.33 mid 0.33-0.66 late >0.66
- Verified actual schema: tyre_join_exact.parquet has race_id season round driver_number driver_ref lap_number lap_time_seconds position stint_id compound tyre_age stint_lap join_confidence evidence_tier source_reference source retrieved_at raw_sha256 circuit race_date observation_date as_of

## Driver / Constructor / Circuit / Race
- Driver: drivers.json 1457, AliasRegistry deterministic mapping name_acronym lower, driver_number per race via drivers_openf1, sample per driver 50-4500 laps, 30 active drivers with >1000 laps, driver_betas via hierarchical shrinkage LIMITED/CALIBRATED
- Constructor: 236 canonical, but OpenF1 team_name per results_openf1 limited; constructor control via driver_number proxy marked LIMITED due to sparse per-constructor tyre samples, not interpreted as car pace
- Circuit: 52 via phase24 model, per-circuit n 59-5058, shrinkage_weight 0.3-0.95, evidence_tier limited for sparse (losail n369, las-vegas n886)
- Race: 1172 race_ids, 2023-2026 84 OpenF1 sessions, race_date as_of strict_before, observation_date = race_date

## Weather
- weather_openf1 84 files, 18 cols air_temperature track_temperature humidity pressure rainfall wind_speed_ms etc, total observations ~84*~60 per race ~5000, reanalysis_era5 558 races ERA5 REANALYSIS not sensor, evidence_tier LIMITED per weather_data_audit, as_of = race_date -1 day, do NOT use realized future weather, do NOT interpolate historical to manufacture observations

## Race Control / Pit Stops / Qualifying/Grid
- race_control_openf1 84 files, flag SC/VSC YELLOW RED etc, total messages ~few thousand, 2023+ only, evidence LIMITED/PRIOR_ONLY, do NOT convert priors into observed historical facts, do NOT introduce future information
- Pit stops: pit_stops.json 1000 canonical pre-1994, pitstops_jolpica 12747 (1996-2026), pitstops_openf1 for 2023+, pit lap discontinuity via stint_lap==1, intervals_openf1 partial 12/84, lane/stationary split NON_IDENTIFIABLE, not fabricate
- Qualifying/grid: qualifying.json 26998, results.json grid_position, but grid not used as fuel proxy

## Existing Lap-Time Models
- app/simulation/lap_time/model.py LapTimeModel fuel_effect_per_10kg 0.035s, tyre_degradation_rate, weather, traffic, track evolution etc, deterministic via RandomProvider
- Tyre calibration production tyre-v1.0.0 (tyre_model.json) with SOFT beta -0.22, HARD -0.20 from 337/790 FastF1 samples, retained as production, candidate tyre-calibration-v2.0.0-candidate negative beta -0.309 rejected

## TemporalContext / as_of
- Strict before as_of: calibration only uses observations where observation_date < as_of, as_of = race_date -1 day, no leakage, verified via leakage.json violations 0, 8+ tests, future injection tests must not change historical calibration

## Provenance / Fingerprint
- Dataset version f1-dataset-v1.3 with hashes 2cce529c/ac13fa1f/112c8475, tyre_join-v1.0.0 seed 42, calibration seed 42, circuit version circuit-v1.0.0-candidate, fingerprint via sha256 of proxy definition + dataset + hashes must change if inputs change

## Counterfactual Engine
- app/simulation/scenario, replay, counterfactual validation modules, scenario_v14, replay_engine, sensitivity, validation with leakage and determinism checks
- Expected physical direction: increase tyre age -> not faster, increase degradation -> not improve lap time, reset tyre age -> not worsen, tested via counterfactual.json

## Verification
- No variable assumed until verified in actual schema via parquet reads and canonical json
- Fuel fields searched exhaustively: NOT_AVAILABLE (see fuel_data_audit)
- Variables available for proxy: normalized_lap, lap_number, stint_lap, race_progress, remaining_laps, race_phase all observable, correlated with fuel burn, remain PROXY_ONLY
- Do not assume constructor directly joinable; documented LIMITED
