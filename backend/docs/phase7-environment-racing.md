# Phase 7 — Dynamic Environment & Racing Refinement

> The environmental and racing models are reduced-order statistical
> approximations and are NOT CFD or full vehicle-dynamics simulations.

## 1. New models

- `app/simulation/environment/models.py`
  - `TrackWetnessModel` — per-sector racing-line / off-line wetness,
    rain accumulation, wind/temperature/traffic-dependent drying,
    rubber build-up.
  - `TyreCrossoverModel` — slick/intermediate/wet crossover assessment
    with hysteresis (`TyreCrossoverAssessment`: recommended compound,
    confidence, expected delta, reason).
  - `ForecastUncertainty` — team-visible forecast with per-lap confidence
    decay and `forecast_error_sigma` noise (distinct from simulator truth).
  - `OvertakeZone` / `TrackOvertakeMap` — sector-indexed zones with entry
    speed, braking intensity, straight length, DRS availability,
    overtake/defense difficulty and straight/braking/traction importance.
    Maps provided for Bahrain, Monaco, Monza (`get_overtake_map_for_track`).
- `app/simulation/strategy/team_orders.py`
  - `TeamOrderModel` + `TeamOrderConfig` + `TeamOrderContext` /
    `TeamOrderDecision` + minimal `ChampionshipContext`
    (points difference, remaining races, constructor position,
    optional priority driver). Orders: HOLD_POSITION, LET_TEAMMATE_BY,
    NO_ATTACK, ATTACK, PIT_PRIORITY, STRATEGIC_SPLIT (evaluated from gap,
    pace difference, late-race, championship context; probabilistic).
- Extended `Track` (`app/simulation/models/track.py`): per-sector corner
  counts, straight lengths, DRS zones, overtaking difficulty, dirty-air
  sensitivity, braking difficulty, traction demand, aero dependency,
  overtaking opportunity, defense difficulty (+ getters and
  `initialize_sector_characteristics()` backfill). 2024 calendar tracks
  (Bahrain, Jeddah, Australia, Monaco, Spain, Monza) carry explicit
  sector data, e.g. Monaco: 95 difficulty / 5 opportunity all sectors,
  no DRS; Monza: 20–30 difficulty, 70–80 opportunity, 2 DRS zones.
- Extended racing contexts (`BattleResourceState`, sector/zone/forecast/
  racing-line/off-line wetness, ERS energies, teammate + team order).

## 2. Equations / relationships

- Dirty air (sector-aware): `distance_factor = (gap / 1.0) ** -1.5`
  (capped 5x) × aero sensitivity × leader efficiency ×
  `(sector_sensitivity / 50)` × corner modifier × wet reduction (0.6).
  Losses: cornering 0.15s, braking 0.05s (base, at reference).
- Overtake (logit + sigmoid, max 0.85): pace ×1.5, tyre ×2.0,
  straight-line × zone importance, skills, DRS bonus × zone straight
  importance, ERS bonus × ERS energy × zone factor, dirty air ×−1.5,
  wet −0.4 / damp −0.2, damage, traffic, zone opportunity, ERS-energy
  delta, drying-line +0.05.
- Defense: predicts attack probability (pace, tyres, DRS zone, skills,
  gap, weather, resources, track difficulty, late race), then selects
  NORMAL/DEFENSIVE/AGGRESSIVE with fuel/ERS/team-order threshold shifts;
  costs 0.0/0.15/0.35 s/lap; risks 1.0/1.3/2.0×.
- Battles: state machine (CLOSING → WITHIN_DRS → ATTACKING →
  SIDE_BY_SIDE → ENDED), termination at gap > 3.0 s or > 10 laps;
  probability adjusted for side-by-side (+0.3), DRS, battle age, and
  attacker/defender fuel/ERS conservation flags.
- Wetness: `+= precip × accumulation_rate` in rain;
  `-= base × (1 + wind×f) × temp-factor × traffic × line-multiplier`
  when dry (racing line 1.5× faster than off-line).
- Crossover: wetness thresholds (slick→inter 0.25, inter→wet 0.55,
  wet→inter 0.4, inter→slick 0.15) with 0.05 hysteresis.
- Restart: reaction 0.3 s base ± skills/tyres/weather + N(0, 0.15),
  clamped [0.1, 1.0]; position-change distributions per advantage band.
- Resources: attack costs extra fuel/ERS (`fuel_attack_cost`,
  `ers_attack_cost`), defense costs less, idle harvests
  (`ers_harvest_rate`); fuel/ERS never negative (clamped); conservation
  flags gate attack probability and defense aggressiveness.

## 3. Configuration

`SimulationConfig` additions (all named, unit-documented, validated):
`wetness_accumulation_rate`, `drying_rate_base`,
`racing_line_drying_multiplier`, `off_line_wetness_multiplier`,
`rain_transition_threshold`, `intermediate_crossover_threshold`,
`slick_crossover_threshold`, `forecast_error_sigma`,
`sector_dirty_air_base`, `sector_dirty_air_decay`,
`ers_attack_cost`, `ers_harvest_rate`, `fuel_attack_cost`,
`defense_fuel_cost`, `team_order_probability`.
Plus `OvertakeConfig`, `BattleConfig`, `DirtyAirConfig`,
`DRSTrainConfig`, `DefenseConfig`, `SafetyCarRestartConfig`,
`TeamOrderConfig`, `TyreCrossoverModel` fields.

## 4. State changes

- `DriverState`: `current_sector`, `racing_line_position`,
  `fuel_remaining`/`fuel_target`/`fuel_mode`, `ers_energy`/`ers_target`
  (single source of truth preserved; `fuel_remaining` mirrors
  `fuel_mass` for the strategy layer).
- `RaceState`: `racing_line_wetness`, `off_line_wetness`,
  `rain_intensity`, `precipitation_rate`, `forecast_rain_probability`,
  `forecast_confidence`.
- No duplicated state: wetness lives in `TrackWetnessModel.sector_wetness`
  and is mirrored onto `RaceState` summaries each lap.

## 5. Event types

New `EventType`s + classes + factories: `OVERTAKE_OPPORTUNITY`,
`RAIN_INTENSITY_CHANGED`, `TRACK_WETNESS_CHANGED`,
`TYRE_CROSSOVER_DETECTED`, `DRYING_LINE_CHANGED`, `FUEL_MODE_CHANGED`,
`ERS_MODE_CHANGED`, `TEAM_ORDER_ISSUED`, `TEAM_ORDER_EXECUTED`.
All serializable (`model_dump()`), deterministic (simulation lap +
named RNG streams), driver/team-associated where applicable.

## 6. Data flow

`RaceEngine.simulate_race` per lap:
weather step → wetness step (stream `drying_line`, emits rain/wetness/
drying-line events) → lap sim → positions/gaps → `_process_racing_dynamics`
(sector dirty air via `calculate_effect_for_sector`, overtake zones from
`overtake_map`, resource states built per driver, battles, predictive
defense, fuel/ERS costs + mode events, overtake attempts, team orders for
teammates, tyre-crossover assessments) → forecast-based pit strategy
(`forecast_model`, never ground truth) → results (now includes `events`).

## 7. Deterministic random streams

`weather` (pre-existing via WeatherModel), `drying_line`, `forecast`,
`overtaking`, `battle`, `defense`, `restart`, `team_orders`
(all via `RandomProvider.get_stream`). Same config + seed + model version
+ initial state ⇒ identical results (tested).

## 8. Testing strategy

`tests/test_phase7.py` (26 tests): determinism (weather/drying/crossover/
battle/team-order/full-race replay), directional (rain→wetness,
wind→drying, racing-line faster drying, wet→intermediate, ERS→attack,
fuel→pace, skill→probability, dirty-air distance, forecast decay),
invariants (wetness bounds, fuel/ERS bounds, probability bounds),
model-level statistics (1000-trial crossover/ERS, 300-trial tyre delta),
and 8 complete-race integrations (even, fast-vs-slow, DRS track, Monaco,
DRS train, SC restart, wet race, aggressive battle) validating positions,
gaps, events, replay.

## 9. Known limitations

- Sector resolution is coarse (3 sectors; single representative sector
  used per driver-pair per lap for zones/dirty air).
- No CFD/vehicle dynamics; wet-line grip effect is a pace-probability
  adjustment, not a contact model.
- Forecast is Gaussian noise on precipitation only (no temperature/wind
  error model, no false-alarm/miss calibration).
- Team orders ignore pit-wall radio delay and driver compliance variance
  (always complied when issued; probability gates issuance).
- Strategy search uses an even-split heuristic for races > 10 laps
  (full combinatorial search is exponential; heuristic is deterministic
  and documented in `RaceEngine._initialize_driver_strategies`).
- Pre-existing `StrategyEngine`/`PitStopStrategyEngine` field-name bugs
  (`optimal_lap_count` vs `max_life_laps`, string-vs-enum compound keys,
  missing `Track.grip_level`/`Driver.skill`) were fixed minimally with
  backward-compatible helpers; deeper strategy-model cleanup deferred.
- Ruff: remaining E501 (line length, mostly pre-existing calendar data)
  and UP042 (`str, Enum` pattern used project-wide); mypy: extensive
  pre-existing errors in strategy/tyre/lap-simulator enum plumbing —
  no new Phase 7 errors (2 touched-file errors fixed).
