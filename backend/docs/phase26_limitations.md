# Phase 26 Limitations

## Fuel
- ACTUAL_FUEL_DATA = NOT_AVAILABLE, searched all families 552656 laps + 4840 stints + 84 OpenF1 sessions, no measurement exists
- FUEL_PROGRESSION_PROXY is PROXY_ONLY, not kg, correlated 0.497 with tyre_age globally and 0.983 within stint, separation NON_IDENTIFIABLE, do not claim physical fuel effect
- No synthetic fuel model created, no starting_fuel or burn_rate kg/lap assumption

## Tyre
- Exact tyre join only 2023-2026 99.4% (93096/93650), historical 1996-2022 0% NON_IDENTIFIABLE, no backward extrapolation, no interpolation of missing laps
- Tyre coefficients negative implausible for all compounds (-0.68 soft, -0.388 medium, -0.253 hard) and all specifications A-H (-0.309 to -0.060), indicates fuel confounding, not causal degradation, classification NON_IDENTIFIABLE / REJECTED for causal, LIMITED only as associational stint-level description
- Within-stint demeaned still negative -0.174, within-race avg -0.332, sign not corrected, range [-0.332,-0.060] never positive
- Between-circuit variance large especially soft 1.13, sparse circuits shrinkage limited, not independent

## Validation
- Walk-forward only 3 testable splits (2023->2024,2024->2025,2025->2026) due to limited tyre seasons, all show worsening -0.72,-0.23,-1.88, inconsistent improvement not found, not sufficient to claim progress
- Finish MAE, winner match, top3, Brier NOT_TESTABLE for lap-only model, requires full race simulation with SC, pit, fuel, not attempted to avoid overclaim
- Error decomposition: tyre does not explain meaningful portion, baseline 6-8s MAE dominated by circuit and progression

## Controls
- Circuit control hierarchical tau 30/50, sparse circuits LIMITED, not dominate but still cannot rescue sign
- Driver/constructor controls via dummy encoding, but constructor mapping via team_name proxy limited, driver coefficient not interpreted as skill, shrinkage for sparse
- Pit/race control LIMITED/PRIOR_ONLY due to sparse SC/VSC data (84 sessions), pit discontinuity via stint_lap==1 proxy not full pit lane model
- Weather control via weather_openf1 84 files, but historical weather pre-2023 unavailable, as_of = race_date -1 day respected, insufficient coverage marked LIMITED/PRIOR_ONLY, not interpolate
- Telemetry bulk not acquired, setup/strategy/ERA5 reanalysis not sensors, all NON_IDENTIFIABLE where not observed

## Provenance
- Provenance complete fingerprint via sha256 of proxy definition + dataset + hashes, changing proxy changes fingerprint
- Deterministic seed 42, reproducible true, but still not causal

## Promotion
- 10 gate criteria all must pass, 5 fail: physically correct counterfactual false, stable sign false, robust false, no severe confounding false, chronological improvement false => KEEP_PRODUCTION_MODEL

## Next Research Requires
- Actual fuel measurements per lap per driver (if ever become available via FIA or team data) to separate fuel/tyre
- Longer modern tyre join period (beyond 2026) to increase walk-forward splits and power
- Better within-stint instruments (e.g., tyre pressure/temperature sensors) not currently in dataset
- Do not attempt to manufacture fuel from progression proxy

