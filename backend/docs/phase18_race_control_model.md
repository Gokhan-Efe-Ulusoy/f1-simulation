# Phase 18 Race Control & Dynamic Event System — Model

**Version:** `racecontrol-v1.0.0`, `policy racecontrol-policy-v1.0.0`, `MODEL_VERSION 0.5.0`, `SIMULATION_VERSION 8.4.0`, `raceengine-v1.4.0`
**Status:** Production, deterministic, prior-only, vectorized (N,L) shared, leakage-safe, backward compatible.
**Baseline:** Phase 17 `MODEL 0.4.0 / SIM 8.3.0` preserved; `race_control_enabled=False` reproduces Phase-17 path within tolerance.

## 1. Architecture

Dedicated package `app/simulation/race_control/`:

```
race_control/
  __init__.py          # public exports + version
  models.py            # RaceControlState, TrackControlState, SectorControlState, DriverControlState, RaceEvent, enums
  state_machine.py     # explicit VALID_TRANSITIONS + PRIORITY + RaceControlStateMachine
  policy.py            # RaceControlPolicy (thresholds, PRIOR_ONLY)
  neutralisation.py    # NeutralisationFactors table + gaps_compression
  rng.py               # isolated stream offset 600 + deterministic_event_id
  engine.py            # RaceControlEngine (batch (N,L) + sequential next_state)
  kernels.py           # vectorized kernels: gaps_compression, pace_control, overtake/drs masks (Numba + NumPy fallback)
  flags.py             # sector flag helpers (N,L,S)
  propagation.py       # EventQueue deterministic FIFO with parent chain
```

No duplication of existing `core/events.py`, `core/state.py`, `lap_simulator`, `weather`, `tyre`. Integration is additive.

## 2. State Machine (not if-spaghetti)

### 2.1 States

```
GREEN, YELLOW, DOUBLE_YELLOW, VSC, SAFETY_CAR, RED_FLAG,
FORMATION_LAP, START, RESTART, CHEQUERED_FLAG, RACE_SUSPENDED, RACE_RESUMED
```

### 2.2 Valid Transitions (explicit table `state_machine.py:VALID_TRANSITIONS`)

```
GREEN -> YELLOW | DOUBLE_YELLOW | VSC | SAFETY_CAR | RED_FLAG | FORMATION | START | CHEQUERED
YELLOW -> GREEN | DOUBLE_YELLOW | VSC | SAFETY_CAR | RED_FLAG
DOUBLE_YELLOW -> GREEN | VSC | SAFETY_CAR | RED_FLAG
VSC -> GREEN | SAFETY_CAR | RED_FLAG | RESTART
SAFETY_CAR -> RESTART | RED_FLAG | GREEN (tolerant)
RED_FLAG -> RESTART | RACE_SUSPENDED | RACE_RESUMED | CHEQUERED | GREEN
RACE_SUSPENDED -> RACE_RESUMED | RESTART | CHEQUERED
RACE_RESUMED -> RESTART | GREEN
RESTART -> GREEN | YELLOW | SAFETY_CAR | RED_FLAG
FORMATION_LAP -> START | GREEN | RED_FLAG
START -> GREEN | YELLOW | SAFETY_CAR | RED_FLAG
CHEQUERED_FLAG -> (terminal)
```

Staying in same state is allowed. Any other edge raises `ValueError`. Enforced via `assert_valid_transition`.

### 2.3 Priority (deterministic resolution when multiple deploy simultaneously)

```
CHEQUERED (110) > RED_FLAG (100) > RACE_SUSPENDED (95) > RESTART (90) > SAFETY_CAR (80) > VSC (60) > DOUBLE_YELLOW (40) > YELLOW (30) > GREEN (10)
```

`resolve_highest_priority(cands)` sorts by `(-priority, value)` — lexical tie break deterministic.

### 2.4 Granularity (not flattened boolean)

```
race_control_state   : global (N,L) shared across drivers
track_control_state  : derived from race_control_state
sector_control_state : (N,L,S) per-sector GREEN/YELLOW/DOUBLE_YELLOW
driver_control_state : per-driver RACING | YELLOW_AFFECTED | VSC_CONTROLLED | SC_CONTROLLED | SUSPENDED | RETIRED
```

## 3. Event Model

`RaceEvent` (pydantic, enums):

```
id: deterministic RC:race:lap:counter:hash
event_type: 22 enum values (SPIN … CHEQUERED_FLAG, FORMATION_LAP, START etc.)
lap, timestamp, track_position, sector (-1=global), driver_ids, severity, duration, trigger, cause, confidence,
evidence_tier (PRIOR_ONLY unless OBSERVED), resolved, parent_event_id, metadata
```

Severity `MINOR|MODERATE|MAJOR|SEVERE` — configuration-driven, `EvidenceTier PRIOR_ONLY`. IDs are deterministic: `hash(race_id:lap:counter)`.

## 4. Causality (no disconnected random events)

```
rain_intensification -> grip_loss -> lockup/spin -> stopped_car -> yellow_flag -> VSC/SC -> field_compression -> pit_window -> strategy_adaptation
```

Represented via `parent_event_id`, `trigger`, `cause`, `metadata`. Propagation via `EventQueue` which sorts parent before child. No recursive uncontrolled generation; queue caps via `reference_incident_prob` and durations.

## 5. Incident → Race Control (policy-driven)

Incident severity (sampled from prior 0.50/0.30/0.15/0.05) maps via `RaceControlPolicy`:

```
minor      -> NO_ACTION / local yellow
moderate   -> YELLOW (30% double if blockage)
major      -> VSC (35%) or SC (50%) else DOUBLE_YELLOW
severe     -> RED_FLAG (40% if blockage/retirement) else SC
```

All thresholds `Field(..., ge=, le=)` with `evidence_tier PRIOR_ONLY`. No magic numbers without documentation.

## 6. Yellow Flags — Sector-level

```
GREEN, YELLOW, DOUBLE_YELLOW per sector S (default 3)
```

Local incident sets one (or two for double) sector(s) to 1/2 in `sector_flags (N,L,S)`. Drivers in affected sector get `YELLOW_AFFECTED` vs `RACING`. Effects:

* pace floor 1.12x / 1.22x
* overtaking 0.25 / 0.10 (VSC 0.05 SC 0.0)
* DRS disabled
* incident factor reduced 0.85 / 0.75
* pit cost 1.0 / 0.95 (no free pit)

Return to GREEN after `yellow_duration_laps=1` (config) unless escalated (10% to VSC, 5% to SC).

## 7. VSC

Distinct state `VSC`:

* pace floor 1.25x (uniform across drivers)
* gaps compress rate 0.25 toward 0.7s (vs SC 0.55)
* overtaking near zero (0.05)
* battle 0.10, incident 0.65
* pit cost factor 0.55 (cheap, strategy opportunity)
* DRS disabled, fuel saving 0.6x
* Duration sampled 2-4 laps (uniform), PRIOR_ONLY

Not `lap_time += constant` — structured `NeutralisationFactors`.

## 8. Safety Car

* pace floor 1.35x uniform
* gaps compress rate 0.55 toward 0.7s, progressive not teleport (kernel `gaps_compression_kernel`)
* overtaking 0.0 suppressed
* DRS disabled
* pit 0.35 (cheapest)
* tyre age continues, weather continues evolving
* incident probability 0.5x (reduced speed, prior)
* Duration 3-6 laps uniform

Field compression: `new_gap = old*(1-r) + target*r`, leader stays 0, no negative gaps, no order swaps.

## 9. Field Compression (critical)

```
times matrix (N,D) -> gaps_compression_kernel(times, phase, target=0.7, rate_sc=0.55, rate_vsc=0.25)
```

Per sim: `min_t = min(times[n])` leader; for each driver `gap = t - min_t; new = gap*(1-r)+target*r`. Numba njit fast path, NumPy fallback. Preserves invariants: leader gap 0, gaps >=0, no duplicate positions after resort.

Restart creates transient: RESTART lap pace 1.05x, overtaking 1.35x, battle 1.25x, incident 1.15x, then GREEN with DRS locked 2 laps.

## 10. Red Flag

* pace 0, overtaking 0, frozen `lap_times=0` so `times` not advancing (field frozen)
* preserves race order/state (positions, tyre age, gaps, fuel)
* duration 3-6 laps, then `RESTART` (or CHEQUERED if <3 laps remain)
* interaction with weather: Wetness still evolves but race not progressing — frozen
* Abstraction documented: does not model full FIA sporting regs (parc fermé, tyre changes etc.), labelled PRIOR_ONLY

## 11. Formation Lap & Start

Sequential path `RaceEngine._run_formation_and_start` already existed Phase 8. Phase 18 adds `FORMATION_LAP`/`START` phases to state machine and gating:

* formation not counted as race lap, does not accumulate championship times
* start launch: `reaction_time N(0.25,0.08)` + `launch_quality` -> delta `(reaction-0.25)+(0.5-quality)*0.3` added to `total_time` clamped >=0
* first-corner risk seeded via `formation`/`start` isolated streams

Vectorized batch currently keeps laps as configured (formation handled separately), but phase machine includes `FORMATION_LAP`→`START`→`GREEN`.

## 12. First-Lap Incidents

Config `start_incident_multiplier=3.0`, `first_lap_density_multiplier=2.0`, `first_corner_risk=0.02` all `PRIOR_ONLY` (Labelled, not calibrated). Integration: `reference_incident_prob * multiplier` for lap 1, *0.5 for lap2. Gated by `enable_first_lap_incidents`.

## 13. Event Propagation — Deterministic Queue

`EventQueue(race_id)` with `push(event_type, lap, sector, driver_ids, severity, parent_id, cause, evidence_tier)`. IDs deterministic, causal ordering via `sorted_by_causality` (parent before child). Used in sequential path for audit; vectorized path logs counts not full queue for performance but same RNG determinism.

## 14. Strategy Integration (leakage-safe)

Strategy sees only `current race-control state`, `sector flags`, `SC/VSC/RED`, `laps_under_neutralisation`, `restart_pending`, `weather`, `wetness`, `tyre`, `field_gaps`. It does **not** see `future phase[t+1]`. Enforced architecturally: `VectorizedMonteCarlo` generates `phase (N,L)` upfront but per-lap `weather_eff` and `lap_times` only use `phase[:, lap_idx]` for that lap; strategy's pit decision (every 20 laps) uses current `gap_ahead` and `track_pit_loss` only. No foresight of `phase[:, lap+1]`.

Invalid example blocked: `strategy knows SC will deploy lap 27` — impossible.

## 15. Weather → Event System

```
rainfall/wetness (WeatherState) -> visibility/grip -> incident prob * (1+wet*0.6) -> severity sampling -> policy -> race-control -> pace/compression -> strategy -> outcome
```

Probabilistic, not deterministic `rain causes accident`. Coupling enabled via `weather_event_coupling=True` (scenario-level). Thresholds `wetness_red_flag_threshold=0.85`, `rainfall_red_flag=15 mm/h`, `consecutive_wet_laps_for_red=3` all `PRIOR_ONLY`. If `weather_enabled=False` then coupling is no-op (dry prior).

Weather → Red Flag path: `WeatherState -> WeatherSafetyAssessment (via decider) -> RaceControlPolicy.decide_for_weather`.

Only information at current timestamp influences current state; no future leakage (checked via batch trajectory generation sequential per-lap, not looking ahead).

## 16. DRS Gating

```
GREEN: 1.0      (existing model)
YELLOW/DOUBLE: disabled (sector-level also disabled even if one sector yellow globally suppress for simplicity)
VSC/SC/RED/RACE_SUSPENDED: disabled
RESTART: disabled for 2 laps after (FIA-like prior)
```

Implemented via `drs_mask_for_phase(phase (N,L))` and `RaceEngine._check_drs_availability` which checks `race_control_state == PHASE_GREEN`.

## 17. Overtaking / Battle Integration

Modifiers exposed:

```
race_control_overtake_factor, attack_factor, defense_factor, slipstream_factor
GREEN 1.0, YELLOW 0.25/0.10, VSC 0.05, SC 0.0, RESTART 1.35
```

Existing Phase 7 `BattleEngine`/`OvertakeEngine` not replaced; vectorized path applies `overtaking_allowed` mask (suppressed under VSC/SC/RED/YELLOW) and uniform lap times prevent swaps. Sequential path skips `._process_racing_dynamics` under full neutralisation (SC/VSC/RED) and probabilistically reduces under YELLOW.

## 18. Pit Integration

```
GREEN pit cost 1.0
VSC pit 0.55
SC pit 0.35
RED 0.0 (suspended)
```

Vectors: pit every 20 laps is simplified but cheaper during SC/VSC is documented as PRIOR_ONLY opportunity cost. Separation of `physical pit duration (track.pit_stop_time_loss)` vs `strategic opportunity (pit_cost_factor)` vs `field-gap consequence` retained.

## 19. Race Order Invariants (checked per lap)

```
position in [1,D], no duplicate, no missing, gap >=0, leader gap=0, times monotonic,
no teleport (max wetness delta 0.05, gap r=0.55 progressive), deterministic IDs
```

Enforced via kernels and tests `test_race_order_invariants`, `test_no_duplicate_positions`.

## 20. RNG Isolation

`RACE_CONTROL_RNG_OFFSET=600` (weather 500, AR1 100, driver 0, qual 2, reliability 3). Per-sim per-lap `seed+sim_idx*1000 + 600 + lap*7919`. No reuse of weather/driver streams. Consuming numbers only when branch is taken still deterministically offsets via `race_control_rng(base, sim, lap)` fresh each lap regardless of earlier decisions (so unrelated streams not shifted).

Verified `test_weather_rng_isolated_from_race_control`, `test_same_seed_identical`, `test_different_seed_different`.

## 21. Monte Carlo Architecture (vectorized, shared)

`(N,L)` for race-level control, `(N,L,S)` for sectors (3 → 58*3*10000 ≈ 1.7M ints ~1.7 MB). No `(N,D,L)` duplicated (would be 20× larger). `BatchState` extended with `race_control_phase_traj`, `race_control_sector`, `race_control_drs_mask`. Lap loop cost O(N*L*D) but race-control trajectory generation O(N*L) cheap pre-loop. Masks are `int8`.

## 22. Versioning & Fingerprint

```
SIMULATION_VERSION 8.4.0 (was 8.3.0)
RACEENGINE_VERSION raceengine-v1.4.0 (was v1.3.0)
MODEL_VERSION 0.5.0 (was 0.4.0)
WEATHER still 1.0.0, TYRE 1.0.0
RACE_CONTROL_MODEL racecontrol-v1.0.0
RACE_CONTROL_POLICY racecontrol-policy-v1.0.0
```

Provenance includes `race_control_model_version`, `race_control_policy_version`, `race_control_enabled`, `weather_model_version`, `tyre_model_version`, `dataset`, `calibration`, `seed`, `as_of`. Changing any behaviour changes hash.

## 23. Scenario Modes & Counterfactuals

Supports `historical | counterfactual | hypothetical | future`:

* `hypothetical_modifiers.race_control.enabled`
* `enable_vsc` `enable_safety_car` `enable_red_flag` `enable_yellow_flags` `enable_first_lap_incidents` `weather_event_coupling`

Tested via `test_counterfactual_controls`, `test_ablation_*`.

## 24. Evidence Tiers

Every new coefficient `PRIOR_ONLY` (or `NON_IDENTIFIABLE` for missing historical observations). No upgrade to `CALIBRATED` without fit. `DEFAULT_RACE_CONTROL_POLICY.evidence_tier` and `NEUTRALISATION_TABLE` entries all `PRIOR_ONLY`.

## 25. Limitations (honest)

* Incomplete historical SC/VSC/flag observations (<30 modern races with OpenF1 flag data vs 1950-2022 NON_IDENTIFIABLE)
* Sector flags derived not observed
* Incident causality prior not fitted
* Neutralisation coefficients prior-only (0.35 pit under SC)
* Simplified SC field dynamics (not following distance physics)
* Restart DRS 2-lap lock is FIA-prior approximation
* Red-flag not modelling parc fermé regulations
* Formation lap not vectorized

See `phase18_race_control_data_audit.md` for coverage counts.
