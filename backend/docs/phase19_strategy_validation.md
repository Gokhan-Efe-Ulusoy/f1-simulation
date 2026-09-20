# Phase 19 Validation

## 1. Structural (rules obeyed)

| Check | Result |
|-------|--------|
| State serialization round-trip | `test_state_serialization` pass |
| Action serialization (PitAction) | pass |
| Deterministic representation same laps | pass |
| Candidate valid pit_laps within race & sum==L_rem | pass |
| Invalid `two_stop` with 1 lap remaining rejected | pass |
| Constraints: available_compounds subset, min 3 laps per stint | pass |
| Race length respected (8 laps → stops capped) | pass |
| Pit window feasible `earliest <= preferred <= latest` and >lap | pass |
| Pit window impossible L=1 clamped to race end ≤58 | pass |
| Tyre-driven window older tyre earlier | pass (age 28 vs 2) |
| Weather-driven window rain→crossover | pass |
| SC/VSC cheap pit loss 0.35/0.55 | pass |

## 2. Tyre / Weather / RC Integration

* Tyre beta loading not stale +0.07: `beta_for("soft")` <0 when CALIBRATED → `test_tyre_compound_selection` pass.
* Degradation via current age influences decision: `test_tyre_degradation_integration` pass.
* Age effect: old 22 vs new 2 → window earlier.
* Dry vs damp vs wet crossover → candidates include intermediate when wet 0.35 + rain_prob 0.7 → `test_weather_wet_crossover` pass.
* Forecast uncertainty 0.15 propagated → `test_weather_forecast_uncertainty` pure logic.
* RC GREEN/YELLOW/VSC/SC/RED/RESTART eachproduce decision with reasoning list → all 6 tests pass.

## 3. Opponent & Undercut

* Observable gap 1.2 → undercut analysis viable; SC increases p_pit from 0.09 to 0.27 → `test_opponent_uncertainty` pass.
* Opponent model only uses gap+age, so future pit at lap 30 doesn't change current `p_pit` → `test_opponent_no_future_access` pass.
* Undercut/overcut via `PitStopStrategyEngine` reused, prior-only but distribution not fake exact.

## 4. Leakage (adversarial future)

| Adversarial | Kept same through t | Changed future | Decision at t should be |
|-------------|--------------------|----------------|-------------------------|
| Future weather 0.9 wet vs dry | forecast 0.05 same | realized wet 0.9 vs 0.0 | identical → **pass** `test_leakage_future_weather` |
| Future SC lap 27 | RC GREEN at 15 | future SC vs none | identical → **pass** |
| Future incident lap 25 | tyre_age 5 | incident vs none | identical → **pass** |
| Future opponent pit 30 | gap 1.2 same | future pit vs stay | identical → **pass** |
| Future result | same state | winner A vs B | identical → **pass** |

If any decision had changed, we would have isolated leakage via state containing future array — fixed by building state only from `current` fields + isolated RNG.

## 5. RNG

* Same seed+sim_idx+lap identical → `test_rng_same_seed_identical` pass.
* Different seed stream random differs → `test_rng_different_seed_different` pass.
* Offset 700 distinct from 500 weather, 600 RC → `test_rng_isolated_stream` pass (3 distinct).
* Fingerprint: strategy version changes hash → `test_provenance_fingerprint` pass.

## 6. Monte Carlo

* Deterministic 50 sims same seed identical (max diff <1e-12) → `test_monte_carlo_deterministic` pass.
* Vectorized distribution sanity: evaluations have `0≤uncertainty≤1`, risk≥0, race_time>0 → pass.
* Historical/counterfactual/hypothetical/future scenario modes supported via `ScenarioResolver` — strategy engine reads only `as_of` and `hypothetical_modifiers.strategy.enabled`.

## 7. Explanation

* Old tyre + VSC → reasons include `tyre degradation` + `RACE_CONTROL` → `test_explanation_corresponds_to_inputs` pass.
* Components are subset of allowed 10 labels → `test_no_unsupported_claims` pass (no hallucinated `ENGINE_MODE` etc.).

## 8. Counterfactual API

* `evaluate_strategy` returns `expected_race_time>0` → `test_counterfactual_evaluate` pass.
* `compare_strategies` returns `deltas[0].delta_expected_race_time` → `test_counterfactual_compare` pass.

## 9. Sensitivity

* Exposes `risk`, `uncertainty` per evaluation for Phase 24 → `test_sensitivity_exposure` pass.

## 10. Ablation (structural validation)

* Strategy disabled vs enabled still produces win probs 0-1 → `test_ablation_strategy_disabled` pass.
* Tyre-disabled still generates candidates → pass.
* No ablation claims realism; only checks behavior changes as expected.

## 11. Regression

* All 440 prior tests remain passing; `test_regression_vec_still_works` trivial import pass.

## 12. In Invariants

* Pit loss SC 0.35 < VSC 0.55 < GREEN 1.0
* Gap compression rate SC 0.55 > VSC 0.25
* No duplicate positions, gap ≥0 (inherited)

## 13. Known Limitations in Validation

* Backtesting `pit-lap error` etc. cannot be reported because `strategy_history` dataset missing → metrics documented as NON_IDENTIFIABLE, not fabricated.
* Historical walk-forward for tyre uses `as_of` split but n small → sample sizes noted.
