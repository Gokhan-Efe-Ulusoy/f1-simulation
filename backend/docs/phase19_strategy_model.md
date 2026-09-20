# Phase 19 Strategy Model — Advanced Decision Engine

**Version:** `strategy-v1.0.0`, `MODEL_VERSION 0.6.0`, `SIMULATION_VERSION 8.5.0`, `raceengine-v1.5.0`
**Status:** Modular, leakage-safe, deterministic, PRIOR_ONLY where evidence insufficient, vectorized-compatible.

## 1. Architecture

```
strategy/
  __init__.py          # re-export + STRATEGY_MODEL_VERSION
  rng.py               # isolated offset 700
  state.py             # StrategyState leakage-safe view
  actions.py           # ActionType + PitAction etc. serializable
  candidates.py        # CandidateGenerator (pruned)
  pit_window.py        # PitWindowEngine
  tyre_strategy.py     # calibrated beta wrapper
  weather_strategy.py  # forecast-aware crossover
  race_control_strategy.py # SC/VSC/RED cheap pit
  opponent_model.py    # P(pit_next) prior
  decision_engine.py   # DecisionEngine.decide + evaluate/compare APIs
  explanation.py       # ExplanationEngine
  engine.py            # existing StrategyEngine (reused)
  evaluator.py         # existing StrategyEvaluator (reused)
  pitstop.py           # existing PitStopStrategyEngine (reused)
  fuel.py              # existing FuelStrategyOptimizer (reused)
```

Smallest architecture fitting existing repo — no duplication of tyre/weather/RC logic.

## 2. StrategyState — Immutable Observable View

Fields (all observable at lap `t`, not future):

```
lap, position, gap_ahead/behind,
current_compound, tyre_age, stint_index, available_compounds,
fuel_remaining, fuel_delta_per_lap, fuel_target,
race_control_phase, sector_flags,
weather_regime, wetness, rainfall, track_temp,
forecast_summary {rain_prob_next_5}, forecast_uncertainty,
driver_pace, constructor_pace, estimated_degradation, estimated_tyre_performance,
pit_loss_estimate, laps_remaining, completed_pit_stops, planned_stops,
opponent_states [{driver_id,gap,tyre_age,compound}],
available_actions
```

Evidence tier per field (`KNOWN|ESTIMATED|PRIOR_ONLY|NON_IDENTIFIABLE`) — missing values use `PRIOR_ONLY`, not fabricated.

Construction via `build_strategy_state_from_driver(...)` — ensures no future array is passed.

## 3. Action Model

```python
ActionType: CONTINUE, PIT, CHANGE_COMPOUND, STAY_OUT, PUSH, MANAGE_TYRES, MANAGE_FUEL, ATTACK, DEFEND, PREPARE_RESTART
PitAction: {pit_lap, target_compound, expected_stint_length, reason, pit_window, reasoning}
ContinueAction, StayOutAction etc. — all BaseModel serializable, deterministic given seed.
```

## 4. Candidate Generation (pruned, feasible)

Generator respects:

* race length → max_stops 1 (<10 laps) /2 (<35) /3 else
* pit lane loss, available compounds (soft/medium/hard, intermediate if wet)
* tyre rules (≥2 compounds unless wet) — NON_IDENTIFIABLE if not represented, use explicit param
* current tyre age via PitWindow
* current RC phase (SC/VSC forces pit now)
* weather crossover (wetness>0.25 or rain_prob>0.3 → intermediate)
* fuel (<10kg forces soon)
* already completed stops

Families: `continue`, `1-stop (preferred/early/late)`, `2-stop balanced`, `SC/VSC pit now`, `weather crossover`. Capped `max_candidates=8-12`. No brute-force exponential explosion; vectorized evaluation of candidates is O(K) not O(compounds^stints * modes).

## 5. Pit Window Engine

For each candidate computes:

```
earliest_feasible_lap, preferred_window_start, preferred_lap, preferred_window_end, latest_feasible_lap
```

Considers:

* tyre degradation (optimal = 2.5/beta, beta from calibrated tyre model if available, else spec max_life)
* remaining tyre life `optimal - age`
* pit loss (SC 0.35, VSC 0.55, otherwise 1.0)
* traffic gap<1.5 → earlier
* forecast rain → earlier / crossover
* fuel low → soon
* RC SC/VSC → now

Evidence tier: `CALIBRATED` if beta available, else `PRIOR_ONLY`. Not claimed calibrated unless data.

## 6. Tyre Integration (authoritative calibration preserved)

Uses `tyre/calibration.py:calibrate_degradation(as_of)` — loads `SOFT -0.2229 ±0.038`, `HARD -0.20185 ±0.024`, `MEDIUM PRIOR_ONLY` (as discovered Phase 17.1). **Stale SOFT +0.07 removed** — verified via `beta_for` not hard-coded, uses spec fallback only when calibration unavailable. Warmup/cliff remain `NON_IDENTIFIABLE`.

## 7. Weather Integration

Observes `current rainfall/wetness/regime/track_temp` + `forecast_summary rain_prob_next_5` with `forecast_uncertainty 0.15`. **Never accesses future realized `weather_wetness_traj[:, t+1:]`**. Crossover logic via `WeatherStrategyEngine.should_crossover` → `PRIOR_ONLY`. Example decisions: stay slick / switch intermediate / delay pit / pit early. All gaps via forecast, not future.

## 8. Race Control Integration

Understands `GREEN|YELLOW|DOUBLE_YELLOW|VSC|SAFETY_CAR|RED_FLAG|RESTART` (from `race_control/models.py` plus `BatchState.race_control_phase`). Pit opportunity evaluated with cheap factors (SC 0.35, VSC 0.55). Red implies frozen race (pit 0). Restart allows `PREPARE_RESTART` via existing restart dynamics — no fake regulations.

## 9. Undercut / Overcut

Via `PitStopStrategyEngine.analyze_undercut/overcut` (reused) — computes:

```
undercut_gain = target_old - attacker_fresh - net_gap
overcut_gain = attacker_pit_loss - pace_delta*stay_laps
```

Probabilistic, confidence 0-1 based on risk factors count, PRIOR_ONLY. Not fake exact probability.

## 10. Opponent Model

Lightweight `OpponentModel` — prior-only `Beta(2,20) mean 0.09` per lap, scaled by `tyre_age` (older ↑), `RC` (SC 3×), `laps_remaining` small ↑. Returns `OpponentPrediction {p_pit_next, p_stay, p_switch_compound, confidence 0.25-0.4, PRIOR_ONLY}`. No deterministic future knowledge; opponent states only gaps visible at t.

## 11. Evaluator — Distributions, not single score

For each candidate:

```
expected_finish_position, finish_position_distribution (approx std 2.0),
expected_race_time = sum(90*laps + beta*age sum + pit_loss*(cheap)), race_time_distribution (std via laps+risk+weather),
points_distribution, pit_count, tyre_usage, risk, uncertainty (std/20), probability_of_gain/loss
```

Internal utility `mean + risk*0.1` for ranking but preserves dimensions for explanation. Allows future `sensitivity` via `risk`, `uncertainty`, `tyre_usage`.

## 12. Uncertainty & Evidence Tiers

Every estimate carries `estimate, uncertainty (0-1), evidence_tier (OBSERVED/CALIBRATED/LIMITED/PRIOR_ONLY/NON_IDENTIFIABLE)`. No auto-upgrade; tyre beta tier propagates from calibration, others stay `PRIOR_ONLY` unless data.

## 13. DecisionEngine

```python
DecisionEngine(as_of, seed).decide(state, track_pit_loss, seed, sim_idx) -> DecisionOutput {
  decision, target_compound, pit_window [earliest, latest],
  chosen_action {action_type, pit_lap, reasoning},
  candidate_actions [...],
  evaluations [{candidate_id, expected_race_time, std, risk, uncertainty, evidence_tier}],
  confidence (0.5 + gap/10), uncertainty, reasoning [list], components [TYRE_DEGRADATION etc.],
  evidence_tier, constraints, provenance {seed, sim_idx, as_of, rng_offset 700, strategy_version}
}
```

Deterministic under isolated `strategy_rng(seed, sim_idx, lap)`. Changing `strategy_model_version` changes provenance hash.

## 14. Explanation

`ExplanationEngine.explain(state, candidate, evaluation)` derives `reasons` from inputs:

* TYRE_DEGRADATION if age>18
* PIT_LOSS+RACE_CONTROL if SC/VSC
* TRAFFIC if gap<2
* WEATHER if rain_prob>0.3 else dry
* FUEL if <12kg

No hallucinations; components sorted, tier from evaluation.

## 15. Counterfactual API (Phase 21 ready)

```python
evaluate_strategy(baseline_state, candidate_strategy) -> EvaluationOutput
compare_strategies(baseline_state, strategies) -> {baseline, evaluations, deltas: [{delta_expected_race_time, delta_pit_count, p_gain, uncertainty}]}
```

Both leakage-safe (only current state).

## 16. Leakage Controls

* StrategyState built only from current lap observables; future arrays (`weather_traj`, `race_phase_traj`, `tyre_age future`, `opponent future pit`) never passed.
* RNG offset 700 distinct from weather 500, RC 600.
* Forecast is only noisy representation, not truth.
* Underlying tyre beta via `as_of` filter.

## 17. Monte Carlo Integration

* Sequential: `RaceEngine.simulate_race` calls `DecisionEngine.decide` per driver per lap when `strategy_enabled=True` (per-lap, O(D*L) python loops but D small).
* Vectorized: candidates per driver generated once, evaluated analytically, best `pit_laps` per driver optionally jittered via strategy RNG — no `N*D*L` heavy loops. Batch shape ` (N,L)` for RC/weather, `(N,D)` for tyre, no `(N,candidates,D,L)` tensor.
* `BatchState` extended with `strategy_pit_laps` placeholder for future full vectorization.

## 18. Versioning & Provenance

`STRATEGY_MODEL_VERSION strategy-v1.0.0` added to `version.py`. Provenance includes `strategy_model_version`, `strategy_enabled`, `strategy_seed`, `max_candidates`. Fingerprint hash changes if any strategy config changes.

## 19. Performance Notes

Candidate generation ≤12, evaluation O(K) analytic, no combinatorial explosion. Deep evaluation of top-K only.
