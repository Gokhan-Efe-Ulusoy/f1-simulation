# Phase 18 Validation

## 1. Structural (rules obeyed)

| Check | Result |
|-------|--------|
| Valid transitions only (`state_machine.is_valid_transition`) | 42/42 tests pass including invalid-chequered |
| Precedence `RED>SC>VSC>YELLOW>GREEN` | asserted |
| SC → no normal overtaking (mask 0, uniform pace) | `test_safety_car_no_overtaking` + kernel mask |
| RED → frozen times 0, no position change | `test_red_flag_suspension` |
| VSC pace 1.25 vs SC 1.35 | `test_vsc_pace_control` |
| Restart → GREEN, DRS locked 2 laps | `drs_mask_for_phase` test |
| Yellow sector-local (1-2 sectors) vs whole-track | `test_sector_yellow_local` |
| Yellow returns to GREEN within 1 lap (policy) | `test_yellow_return_to_green` (tolerates consecutive incidents) |
| No negative gaps, leader 0, positions 1..D | `test_race_order_invariants`, `test_no_duplicate_positions` |
| No impossible RED→YELLOW | `test_structural_no_impossible_transitions` |
| Deterministic IDs `RC:race:lap:counter:hash` | `test_event_resolution_deterministic_ids` |

## 2. Statistical (simulated vs available historical where exists)

We **do not** compare simulated SC frequency to historical because historical SC timeline is `NON_IDENTIFIABLE` (no dataset). Any comparison would be fabricated. Instead we validate *sensitivity*:

* Ablation `race_control_disabled` → baseline win prob Δ <0.03 (tolerance) — `test_ablation_race_control_disabled_reproduces_baseline`.
* `weather_coupling=True` extreme wet (0.9, 20 mm/h) produces SC/RED in `>0` sims, while `False` produces ≤ — `test_weather_to_race_control_coupling`.
* SC gap compression rate 0.55 vs VSC 0.25 validated via kernel unit test — progressive not teleport, remains >target after 1 lap.

## 3. Scientific (invariants)

* Determinism same seed identical `N=10,100,1000,5000` — `test_rng_isolation_same_seed_identical` + benchmark determinism block (all True).
* Different seed different (total diff >0.03) — asserts stochastic variation.
* Weather RNG isolated from race control — `test_weather_rng_isolated_from_race_control` (traj identical before/after RC).
* Sector flags bounded `[0,2]`, wetness `[0,1]`, gaps ≥0.
* RNG streams `formation(??)`, `start`, `sector`, `red_flag`, `planner`, `race_control(600)` distinct — listed in `reproducibility.streams`.
* No future leakage: strategy sees only `phase[t]` not `phase[t+1]` — `test_strategy_does_not_see_future` (structural check).
* Evidence tiers all `PRIOR_ONLY` — `test_evidence_tiers`.

## 4. Integration

| Integration | Test |
|-------------|------|
| Incidents → race control (severity mapping) | `test_incident_to_race_control_chain`, `test_event_causality_parent_id` |
| Weather → race control (wet thresholds) | `test_weather_to_race_control_coupling` |
| Race control → DRS | `test_drs_gating` |
| Race control → overtaking (factors table) | `test_overtaking_factor_by_phase` |
| Race control → pit (cost factors) | `test_pit_cost_factors` |
| Race control → gaps (kernel) | `test_safety_car_field_compression_progressive` |
| Race control → strategy (leakage) | `test_strategy_does_not_see_future` |
| Formation/start not breaking lap count | `test_formation_lap_not_counted_as_race_lap` |
| Backward compat `race_control_enabled=False` | `test_backward_compatibility_flag` |
| Mongo: shared (N,L) not (N,D,L) | `test_monte_carlo_race_control_shared_across_drivers` |

## 5. Leakage Checks

* `calibration_state` built via `build_calibration_state(scenario)` with `as_of` filter — same as Phase 14-17.
* `WeatherEngine` filtered `date < as_of` — `test_historical_leakage` still passes.
* `RaceControlEngine.generate_batch` uses per-sim `rng = race_control_rng(seed, sim, lap)` sequential, no peeking beyond lap.
* Timer-based leakage test (no future weather) — implicit via deterministic per-lap generation order.

## 6. Performance Invariants

* `N=1000 L=58 D=20` vectorized adds <3% overhead vs `v17` (7.64s vs 7.81s weather). `N=10000` 77.6s vs 76.7s (+1.1%).
* Batch shapes `(N,L)=58580`, `(N,L,S)=175k` — memory <2 MB overhead.

## 7. Known Limitations in Validation

* No historical flag timeline to calibrate against → statistical validation is sensitivity only.
* `RED_FLAG` model not validated against real red-flag rate (n≈3 in 2023-2024).
* First-lap incident multiplier not fitted.
