# Phase 8 — Race Resolution, Per-Sector Dynamics & Performance Engineering

> This remains a reduced-order statistical simulation and is not a full
> CFD, multibody vehicle dynamics, or professional race-engineering
> simulator.

## 1. Sector simulation

- New `app/simulation/racing/sectors.py`: `SectorState` (index, type,
  distance, wetness, following distance, dirty-air loss, fuel/ERS use,
  tyre-wear delta, DRS, battle state, sector/cumulative time),
  `compute_sector_weights(track, car, driver)` (length-based weights
  tilted ±20% by aero/power/traction/braking match, normalized to sum
  exactly 1.0; cached per `(track, car, driver)` on the engine),
  `split_lap_into_sectors` (last sector = remainder, so
  S1+S2+S3 == lap time exactly), `sector_gap_trace` (cumulative
  per-sector gaps).
- `LapSimulator` still owns the authoritative lap total; sector times are
  an exact partition stored on `DriverState.sector_times`. Sector effects
  are redistributive/diagnostic — never double-applied to the lap total.

## 2. Performance architecture

- Profiling (cProfile, 20×20): racing dynamics ~46%, lap sim ~34%
  (of which tyre-physics pydantic copies dominate), strategy/pits ~5%.
- Optimizations: adjacent-pair battle scan kept O(N·L) (no full N²);
  `battle_candidate_gap` skips distant pairs; single timestamp and single
  tyre-spec lookup per lap; `driver_map` instead of linear scans;
  `lru_cache` on the pure `get_standard_tyre_specs()` (verified read-only
  callers); sector model evaluations gated to battles in active states
  (ATTACKING/SIDE_BY_SIDE/WITHIN_DRS/DEFENDING); sector probabilities via
  arithmetic scaling of the lap-level decision (no extra engine calls or
  RNG draws); event gating by verbosity; telemetry off by default.
- Determinism preserved: new features draw only on new named streams
  (`formation`, `start`, `sector`, `red_flag`, `sprint`, `planner`);
  existing streams keep exact draw order. Caches are keyed pure functions.

## 3. Standing start

- `StandingStartModel` (+`StartConfig`): reaction time (skill-adjusted +
  Gaussian via `start` stream), launch quality (traction/power/aggression/
  start skill/tyre temp/grip), bounded position delta (±3).
- Applied as small total-time deltas (skill-ordered, so established pace
  hierarchies survive); explicit grid reorder deferred to keep lap-1
  resolution in the lap simulator.

## 4. First corner

- `FirstCornerModel` (+`FirstCornerConfig`, conservative defaults):
  contact probability from aggression, grid density, braking difficulty,
  awareness, weather. Outcomes: clean / lockup / spin / contact / damage /
  DNF with bounded time loss. Incident paths are gated by
  `incident_probability > 0` so deterministic test baselines are untouched;
  battle contact logic still delegates to `IncidentModel` (no duplication).

## 5. Red flag

- `RedFlagModel` (+`RedFlagConfig`, `RedFlagState`): per-lap trigger from
  base probability + terminal-incident/extreme-weather boosts
  (`red_flag` stream). Suspension freezes lap sim, pits, dynamics and
  weather for `red_flag_laps`; fuel/tyre/positions preserved by construction
  (no state evolution while suspended). Default probability 0.0.

## 6. Restart

- `StandingRestartModel` reuses `SafetyCarRestartModel` (composition, not
  forced inheritance): reaction + most-likely bounded position delta.
  GREEN→SC→RESTART→GREEN and GREEN→RED→STANDING_RESTART→GREEN are separate
  code paths sharing only the restart physics.

## 7. Sprint weekend

- `app/simulation/weekend.py`: `WeekendFormat` (STANDARD/SPRINT),
  `RaceWeekend` (shared teams/drivers/cars/track, per-session results),
  pace-model qualifying stub with Q1/Q2/Q3-shaped output, sprint as a
  shortened `simulate_race`, full `run_weekend` orchestration. Session
  seeds derive deterministically from the weekend seed.

## 8. Battle resource planning

- `BattlePlanner` (+config, horizon 2–5): compares ATTACK_NOW /
  ATTACK_NEXT / SAVE / HARVEST on expected gain vs fuel/ERS cost and
  feasibility; harvest mode is applied to ERS state with events.
- ERS/fuel state machines: energy/fuel clamped ≥ 0, harvest regen,
  attack/defense costs, conservation flags gate attack probability and
  defense aggressiveness (Phase 7 states, planner adds the horizon).

## 9. Telemetry architecture

- `app/simulation/telemetry.py`: `TelemetryRecord` (lap, sector, driver,
  position, gap, times, speed proxy = sector_distance/sector_time, fuel,
  ERS, tyre, wetness, DRS, battle state; `to_dict()` serializable) and
  `TelemetrySampler` (OFF/SECTOR/LAP/FULL). Attached as
  `RaceResult.telemetry`.
- Events: `SECTOR_COMPLETED`, `SECTOR_OVERTAKE_OPPORTUNITY/ATTEMPT`,
  `SECTOR_INCIDENT` emitted only at FULL_TELEMETRY. Verbosity levels:
  MINIMAL (lifecycle + safety/red-flag/restarts/procedures),
  STANDARD (Phase 1–7 default set, unchanged default), FULL_TELEMETRY.

## 10. Model versioning

- `app/simulation/version.py`: `SIMULATION_VERSION="8.0.0"`,
  `MODEL_VERSION="0.2.0"`, `CONFIG_VERSION="1.0.0"`, recorded on every
  `RaceResult` plus a `reproducibility` dict (seed, versions, track,
  drivers, teams, stream names).

## 11. Determinism

- Same seed + config + versions + initial state ⇒ identical results
  (tested for formation, start, sectors, red flag, restart, weekend,
  planner, telemetry, full races).

## 12. Performance benchmarks

Measured with tracemalloc, fresh `RaceEngine` per sim (Windows, Py3.12):

| case | before (Ph7) | after (Ph8) | events/race |
|---|---|---|---|
| 2×5 | 0.022 s (44.6/s) | 0.029–0.035 s (~30/s) | 12 → 16 |
| 20×20 | 0.84 s (1.19/s) | 1.2–1.8 s (~0.7/s) | 1216 → ~1300 |
| 20×50 | 2.22 s (0.45/s) | 2.5–4.3 s (~0.3/s) | 2668 → ~3000 |
| 20×70 | 2.92 s (0.34/s) | 3.2–4.1 s (~0.3/s) | 3571 → ~4000 |
| 20×70×100 | ~309 s | 341 s (0.29/s) | ~3738 |
| 20×70 MINIMAL | — | ~3.2 s, −30% events, −35% mem | 2690–2963 |
| 20×70 FULL | — | ~3.8–6.3 s, +55–75% events | 5770–7324 |

Before/after deltas include machine noise (±30% run-to-run observed) and
tracemalloc amplification. First-cut Phase 8 code measured ~2× baseline;
profiling-driven optimization (gating, caching, arithmetic sector scaling)
brought it to ~10–30%. Remaining cost is feature payload (procedures,
sectors, planner) plus irreducible lap-simulator physics (~35%).

## 13. Known limitations

- Sector effects shape distribution/opportunities, not the lap total
  (full sector-accumulated timing deferred to avoid double-counting).
- Representative-sector evaluation per pair per lap; full per-sector
  model calls reserved for FULL_TELEMETRY-scale analysis in future work.
- Formation/start effects are small by design to preserve established
  hierarchies; full grid-reorder starts deferred.
- Red-flag weather is frozen (documented rule choice).
- Strategy long-race heuristic (>10 laps) retained from Phase 7.
- Ruff: remaining E501/UP042 are project-wide pre-existing style;
  C408 `dict()` test helpers are intentional override patterns. MyPy:
  extensive pre-existing errors; no new Phase 8 errors.
