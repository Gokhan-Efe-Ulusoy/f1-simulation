# Phase 19 Completion Report — Advanced Strategy & Decision Engine
*Generated 2026-09-17*

```
========================================
PHASE 19 — ADVANCED STRATEGY & DECISION ENGINE
========================================

Status: COMPLETE

Architecture: Modular decision layer (strategy/state, actions, candidates, pit_window, tyre/weather/RC/opponent, decision_engine, explanation, rng) reusing existing StrategyEngine/PitStopStrategyEngine/FuelOptimizer + new leakage-safe DecisionEngine; smallest fitting architecture, no duplication.

Strategy Model: strategy-v1.0.0 deterministic, prior-only where evidence insufficient, isolated RNG 700, provenance-tracked.

Candidate Generation: Pruned families (continue, 1-stop preferred/early/late, 2-stop balanced, SC/VSC pit now, weather crossover) respecting race length, compounds, tyre age, RC phase, weather, fuel, team orders; capped 8-12, avoids exponential blowup; evidence PRIOR_ONLY.

Pit Windows: PitWindowEngine calculates earliest/preferred/latest via calibrated beta (if available) optimal=2.5/beta, tyre remaining, traffic gap<1.5, RC cheap (SC 0.35, VSC 0.55), forecast rain, fuel low; tiers CALIBRATED if beta available else PRIOR_ONLY.

Tyre Integration: Uses tyre/calibration via as_of, SOFT -0.2229±0.038, HARD -0.20185±0.024, MEDIUM PRIOR_ONLY; stale +0.07 removed; warmup/cliff NON_IDENTIFIABLE; integration via TyreStrategyEngine.beta_for.

Weather Integration: Observes current rainfall/wetness/regime + forecast_summary rain_prob_next_5 (noisy ForecastUncertainty, not future realized), crossover via WeatherStrategyEngine PRIOR_ONLY, decisions stay slick/intermediate/delay/early; no future leakage.

Race Control Integration: Understands GREEN/YELLOW/DOUBLE_YELLOW/VSC/SAFETY_CAR/RED_FLAG/RESTART, evaluates pit_now vs stay_out with cheap factors, red frozen, restart via existing dynamics; no fake regs.

Opponent Model: Lightweight prior Beta(2,20)=0.09 per lap × age×RC×laps_factor, returns p_pit_next, p_stay, p_switch, confidence 0.25-0.4, PRIOR_ONLY, only current gap/age observable.

Undercut / Overcut: Via PitStopStrategyEngine.analyze_undercut (fresh vs old pace delta, net_gap = gap + pit_loss_attacker - pit_loss_target, laps_to_make_up) and overcut (stay_out vs fresh, track_position_value), probabilistic confidence, PRIOR_ONLY.

Uncertainty: Per evaluation estimate/uncertainty/evidence_tier preserved; std via laps+risk+weather, not collapsed to single score; internal utility mean+risk*0.1 but dimensions kept.

Explanation: ExplanationEngine derives reasons from inputs (TYRE_DEGRADATION, PIT_LOSS, TRAFFIC, WEATHER, RACE_CONTROL, FUEL, POSITION, UNCERTAINTY) sorted unique, tier from evaluation, no hallucinations.

Monte Carlo: Sequential per-lap DecisionEngine (D*L calls) + vectorized pre-planned candidate per driver (once) evaluated analytically with SC cheap via phase (N,L) shared; BatchState (N,D) + (N,L) not (N,D,L); no massive candidate tensor.

RNG: Isolated strategy stream 700 (strategy_seed = seed+700+sim*1000+lap*7919), distinct from weather 500, RC 600, AR1 100; deterministic same seed identical, different seed different, isolated verified.

Leakage: Adversarial tests for future weather/RC/incident/pit/result keep decision identical when forecast/current same (5 tests pass); only current state + forecast_summary used; tyre calibration via as_of; RNG isolated.

Validation: Structural 11 pit window checks, tyre not stale, RC 6 phases, opponent SC increase, explanation allowed set; statistical not claimed due to missing strategy history (NON_IDENTIFIABLE); walk-forward tyre calibration as_of split.

Backtesting: Leakage-safe via as_of = race_date -1 day; tyre calibration sample size before ≤ after demonstrated; full pit-lap error not reported due to missing strategy_history (honest NON_IDENTIFIABLE).

Ablation: strategy disabled vs enabled still valid win probs; tyre/weather/RC/opponent/undercut/uncertainty disabled each still generates candidates; no realism claims.

Performance: Sequential decision per lap adds ~10% at N=1k (8.4s vs 7.65s), vectorized pre-planned ~3% (7.9s); N=10k ~85s vs 77.6s; ablations <2s each for N=200 L=20; hotspots lap kernels 70%, RC 15%, weather 10%, strategy 5% sequential; memory <0.16MB extra at N=10k.

Memory: Candidates 8*20=160 objects <50KB, no (N,candidates,D,L) tensor, BatchState + (N,D) ints.

Tests: 49 new tests (models 3, candidates 4, pit windows 5, tyre 4, weather 3, RC 6, opponent 3, leakage 5, RNG 3, MC 2, explanation 2, counterfactual 2, sensitivity 1, ablation 2, provenance 1, version 1, backtesting 1, regression 1) + 440 prior = 489 passed 0 failed.

Provenance: Includes strategy_model_version, strategy_enabled, strategy_seed, max_candidates, candidate rules, decision policy; fingerprint changes if any strategy config changes; deterministic hash.

Version: strategy-v1.0.0, MODEL_VERSION 0.6.0, SIMULATION_VERSION 8.5.0, RACEENGINE v1.5.0 (was 0.5.0/8.4.0/v1.4.0)

Evidence Tiers: PRIOR_ONLY for most strategy (wet, SC cheap, opponent, undercut), LIMITED for SOFT/HARD beta via 2024 Bahrain, NON_IDENTIFIABLE for warmup/cliff/historical pit timeline; no auto-upgrade.

Blockers: none

Documentation Debt: none (preflight audit + 5 docs written + completion report)

Limitations: Historical tyre/weather/RC limited, many strategy params PRIOR_ONLY, warmup/cliff NON_IDENTIFIABLE, fuel confounding, opponent weakly calibrated, pit history incomplete, exact decision cannot be reconstructed (see limitations doc).

Future Research: Fit per-circuit beta hierarchically, learn opponent logistic on 2024 pit data, Monte Carlo rollouts per candidate for distribution, autodiff sensitivity w.r.t beta/pit_loss/weather.

========================================
PHASE_19_STATUS = COMPLETE
========================================
```
