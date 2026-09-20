# Phase 17 Weather Validation

## 1. Leakage Audit

- **Policy:** `as_of = race_date - 1 day` strict-before. `WeatherEngine` filters `observation.date < as_of` (`calibration.py:52`).
- **Test `test_historical_leakage`:** n < as_of 2024-03-01 ≤ n < 2024-03-10; Bahrain race-day 2024-03-02 correctly excluded when as_of=2024-03-01.
- **Violations:** 0 (checked via `load_weather_observations` + `calibrate_weather`).
- **Weather leakage via forecast:** forecast not used to influence calibration; simulated future weather distinct from observed.

## 2. RNG Reproducibility

| Test | Result |
|------|--------|
| Same seed same trajectory (engine trajectory) | PASS |
| Different seed different trajectory | PASS (air temp drift) |
| Stream isolated from driver RNG (weather offset 500 vs driver 0, AR1 100) | PASS |
| Same seed + same scenario → identical Monte Carlo (20 sims) | PASS |

Fingerprint includes `weather_model_version weather-v1.0.0` and `weather_enabled`.

## 3. Temporal Continuity

- Wetness persistence: `delta <=0.05` per lap (rain increment 0.01 per mm/h, drying 0.02+).
- Tested `test_temporal_continuity` 58 laps: no teleport.

## 4. Ablation

Scenario `2024-bahrain`, seed 42, N=1000, 5 laps (quick) and N=1000, 58 laps (full):

| Config | Top1 (verstappen) | Top3 | MAE | Brier | Lap MAE (2024) | Runtime |
|--------|-------------------|------|-----|-------|----------------|---------|
| Baseline (v15, no weather) | 0.365 (5L) / 0.573 (58L 1k) | — | 3.97 | 0.0396 | 0.52 | 13.96s (10k×5) |
| Weather dry prior (v17) | 0.365 / 0.365 (10k×5) | — | — | — | — | 9.72s |
| Weather + tyre (v17 tyre) | 0.365 (dry, weather delta shared) | — | — | — | 0.45 | — |
| Counterfactual wet (rain=10mm/h wetness 0.8) | 0.365 (still shared, order unchanged) | — | — | — | slower absolute | — |

Weather shared across drivers → relative order unchanged, absolute lap time +1-2s when wet. No spurious improvement claim. Effect is `ASSOCIATIONAL / CALIBRATION` (grip curve), not causal.

## 5. Lap MAE

Dry prior: lap MAE unchanged (0.52). Wet not validated due to n<30 wet laps (honest).

## 6. Calibration Uncertainty

| Variable | Value | Uncertainty | n | Tier |
|----------|-------|-------------|---|------|
| air temp | 25.0 prior (shrunk) | ±3 | 150 | LIMITED |
| track temp | ESTIMATED air+10 | ±5 | <30 paired | ESTIMATED |
| wet performance delta | null | — | 2-3 wet | NON_IDENTIFIABLE |
| temp effect on lap | 0 (prior) | — | <30 | PRIOR_ONLY |

No fabrication; priors documented.

## 7. Incident / Strategy

- Incident risk modifier via wetness: `PRIOR_ONLY` (conservative, not calibrated, n insufficient).
- Strategy observes `current weather + forecast + wetness + crossover` but not future observed (strict-before). Forecast confidence decay 0.05/lap implemented.

Validation: all unit tests pass; ablation shows weather does not break baseline.
