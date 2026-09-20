# Phase 19 Limitations — Strategy

## 1. Preserved Historical Limitations

* **Tyre:** Compound coverage limited pre-2011 (no Pirelli labels), modern calibrated only SOFT/HARD via 2024 Bahrain FastF1; MEDIUM remains PRIOR_ONLY; warmup/cliff NON_IDENTIFIABLE; degradation model linear `beta*age` not exponential/cliff.
* **Weather:** Coverage limited pre-2023 (0-2 rows), modern ~644 OpenF1 rows LIMITED, wet races n≈2 PRIOR_ONLY; forecast accuracy not calibrated.
* **Race-control:** Sector flags, VSC/SC laps not historically observed (NON_IDENTIFIABLE); neutralisation coefficients PRIOR_ONLY; SC field dynamics simplified.
* **Fuel:** `fuel_remaining` in DriverState but historical per-lap fuel not observed → fuel strategy uses `base 1.8 kg/lap` prior not fitted; confounding remains.
* **Pit:** Historical pit strategy timeline not in `canonical` → pit-lap error, strategy-class agreement metrics are NON_IDENTIFIABLE until `data/strategy.csv` created.
* **Opponent:** Opponent pit policy not fitted; uses prior `p=0.09*age*RC` not calibrated.
* **Team orders:** No historical team order logs; model prior.
* **Historical decision-making:** Exact team reasoning cannot be reconstructed without telemetry/radio logs.

All limitations labeled, not hidden. No fabricated ground truth.

## 2. Strategy-Specific Limitations

* Candidate generation heuristic (even-split) not optimal search; may miss exotic 4-stop if `max_candidates=8`.
* Pit window `optimal = 2.5/beta` is prior (2.5s cliff), not fitted per compound per circuit.
* Weather crossover thresholds (`wetness 0.30`, `rain_prob 0.3`) prior not calibrated.
* SC/VSC pit cheap factors (0.35/0.55) prior not calibrated against real pit delta under SC.
* Evaluation `expected_race_time` analytic ignores traffic dirty air, battle, slipstream interactions beyond gap.
* Uncertainty `std = 0.8*stints + 0.05*L_rem + risk*0.05 + weather 1.5` prior heuristic not posterior.
* Explanation components limited to 10 labels; more granular `FUEL_MODE` etc. not yet.

## 3. Vectorization Limitations

* Full per-lap per-driver per-sim `DecisionEngine.decide` not vectorized (would be N*D*L python loops); vectorized Monte Carlo currently uses pre-planned candidate schedule, not reactive per-lap SC adaptation mid-race per sim per driver. Reactive adaptation is available in sequential `RaceEngine` path.
* Strategy RNG 700 isolated but per-driver `sim_idx = hash(driver_id)%1000` introduces mild correlation across sims for same driver (acceptable prior).

## 4. Evidence Tier Honesty

| Quantity | Tier | Justification |
|----------|------|---------------|
| `beta soft/hard` | LIMITED (n≈40) | FastF1 2024 Bahrain only |
| `beta medium` | PRIOR_ONLY | n<30 |
| `pit_window` tyre remaining | PRIOR_ONLY or LIMITED | depends on beta |
| `weather crossover` | PRIOR_ONLY | wet n<5 |
| `SC pit cheap` | PRIOR_ONLY | no SC pit dataset |
| `opponent p_pit` | PRIOR_ONLY | no opponent fit |
| `undercut gain` | PRIOR_ONLY | pace delta prior |
| `forecast rain_prob_next_5` | PRIOR_ONLY | forecast not validated |
| `strategy risk` | PRIOR_ONLY | heuristic |

Never upgraded without fit.

## 5. What Would Be Needed to Calibrate

* `data/strategy.csv` per race per driver stint logs for n≥30 per circuit × season.
* `data/pit.csv` with pit entry/exit timestamps correlated with `race_control_phase`.
* Wet races with crossover logs to fit `wetness threshold`.
* Fuel telemetry (FIA) to fit `fuel_per_lap` per track per car.

Until then remain `PRIOR_ONLY`.

## 6. Future Research

* Fit per-circuit `beta` via hierarchical shrinkage (global → circuit) when tyre data grows.
* Learn opponent policy via `P(pit | gap, tyre_age, RC)` logistic regression on 2024 pit data.
* Replace analytic `expected_race_time` with lightweight Monte Carlo rollouts (K=20) per candidate for distribution.
* Add `sensitivity` analytic via autodiff of `total = base + beta*age²/2 + pit_loss*(cheap)` w.r.t `beta`, `pit_loss`.
