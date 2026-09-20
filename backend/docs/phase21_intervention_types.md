# Phase 21 — Intervention Types

Each row is implemented, validated, and propagation-tested. Anything else is
rejected (`ScenarioValidationError`) — never silently accepted.

## 1. Setup (reuses Phase 20, no logic duplicated)

| Op | Parameter | Target | Bounds source |
|---|---|---|---|
| SET_VALUE | 18 setup params | driver / constructor (→members) / all | Phase 20 era constraints |
| ADD_DELTA | 18 setup params | same | resolved value ± delta must stay in bounds |

Effect: per-driver sec/lap offsets via `setup/offsets.py` → vectorized lap loop.
Tier: `PRIOR_ONLY`. Pre-2022 eras: `UNKNOWN` applicability (allowed + flagged).

## 2. Strategy — pit-lap level only

| Op | Parameter | Target | Rule |
|---|---|---|---|
| SET_VALUE | `pit_laps` | driver / constructor / all | non-empty int list, strictly increasing, each in [2, L−1] |

Effect: per-driver pit schedule → tyre-age resets → degradation profile → pace.
**No pit-loss channel exists in the vectorized model**: added stops show
tyre-freshness benefit only (surfaced in every explanation). Tier: `PRIOR_ONLY`.
Strategy *policies* (DecisionEngine candidates, aggressiveness, `policy`, …)
are UNSUPPORTED: the vectorized path does not consult the decision engine
(diagnostics only) — wiring it would change legacy dynamics.

## 3. Tyre — compound level only

| Op | Parameter | Target | Rule |
|---|---|---|---|
| SET_VALUE | `starting_compound`, `pit_compound` | driver / constructor / all | one of SOFT/MEDIUM/HARD/INTERMEDIATE/WET |
| SET_VALUE | `stints` | driver / constructor / all | `[{compound, laps}]`, laps ≥ 1, Σ laps == race laps |

Effect: stint compound sequence → calibrated betas where available → pace.
Calibrated tyre coefficients themselves are never modified. Tier: `PRIOR_ONLY`
(effect-level; never upgraded by Monte Carlo output). Pre-2023 eras: tyre model
inactive → allowed with explicit no-effect warning.

## 4. Race control

| Op | Parameter | Target | Notes |
|---|---|---|---|
| ENABLE/DISABLE | `enabled`, `enable_yellow`, `enable_vsc`, `enable_safety_car`, `enable_red_flag`, `enable_first_lap_incidents`, `weather_coupling` | race/all | value must be null |
| SET_VALUE | `wetness_red_flag_threshold` [0,1], `rainfall_red_flag_threshold_mm_h` [0,100] | race/all | only thresholds the vectorized path honours |

Effect: neutralization trajectories (shared across drivers) → pace control /
compression / overtake suppression → dynamics → outcome. Forced events
(`force_safety_car_lap`, red-flag timing, restart scripting) are UNSUPPORTED:
no such mechanism exists; claiming it would be fake. Tier: `PRIOR_ONLY`.

## 5. Weather

| Op | Parameter | Target | Range source |
|---|---|---|---|
| SET_VALUE/ADD_DELTA/MULTIPLY | `rainfall_mm_h`, `track_wetness`, `air_temperature_c`, `track_temperature_c`, `humidity_pct`, `pressure_hpa`, `wind_speed_mps`, `wind_direction_deg`, `visibility_km`, `cloud_cover_pct` | race/all | `WeatherState` ranges, re-validated after delta/multiply |
| ENABLE/DISABLE | `enabled` | race/all | must stand alone (no field overrides in the same spec) |

Effect: initial-state override → trajectories → grip/pace (+ tyre environment,
+ race-control coupling). Override states are marked `ESTIMATED` by the weather
engine; the counterfactual *effect* stays `PRIOR_ONLY`. Historical weather is
never fabricated: without override, `as_of`-gated observations or prior apply.

## 6. Driver / car pace (explicit model interventions)

| Op | Parameter | Target | Bounds |
|---|---|---|---|
| ADD_DELTA | `pace_delta` | driver → driver_id / car → constructor_id | [−3.0, +3.0] pace units |

Effect: additive shift of calibrated pace means before sampling (CRN streams
untouched) → base pace → quali + race. These are labelled model assumptions,
never historical performance claims. Tier: `PRIOR_ONLY`.

## 7. Deliberately unsupported (rejected, documented)

Strategy policies · forced/scripted RC events · championship/result/standings
fields · structural scenario fields (`as_of`, `date`, `drivers`, `grid_order`,
…) · unknown families/parameters · `MULTIPLY` outside weather · `SET_VALUE`
on pace · out-of-range values · duplicate (family, target, parameter) ·
`pit_laps` + `stints` for the same target · weather flag mixed with fields.
