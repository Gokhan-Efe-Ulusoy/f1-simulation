# Phase 26 Walk-Forward Validation

Chronological splits, no future information, as_of = race_date -1 day strict_before

## Splits

- Train <=2018 Val [2019,2020] status NOT_TESTABLE (no tyre data)
- Train <=2020 Val [2021] NOT_TESTABLE
- Train <=2021 Val [2022] NOT_TESTABLE
- Train <=2022 Val [2023] NOT_TESTABLE (first tyre year but need train)
- Train <=2023 Val [2024] status ok n_train 23422 n_val 24091 beta_train -0.4039 baseline_lap_MAE 6.2658 candidate_lap_MAE 6.9879 improvement -0.7222 (worse)
- Train <=2024 Val [2025] status ok n_train 47513 n_val 24863 beta_train -0.3576 baseline 8.4245 candidate 8.6602 improvement -0.2358 (worse)
- Train <=2025 Val [2026] status ok n_train 72376 n_val 16028 beta_train -0.3167 baseline 5.9648 candidate 7.8536 improvement -1.8888 (worse)

Where insufficient data exists, NOT_TESTABLE; do not fabricate additional splits. Only 3 testable due to limited modern tyre periods (2023+). Earlier Phase25 had 2 testable 2024/2025 with baseline 4.79 candidate 4.87 -0.08 then 5.31 vs 5.02 +0.29 inconsistent. Phase26 full decomposition worsens consistently negative.

## Metrics

- lap MAE: baseline (circuit mean) vs candidate (circuit mean + beta*tyre_age)
  - baseline_lap_MAE 6.27, 8.42, 5.96 across splits
  - candidate_lap_MAE 6.99, 8.66, 7.85
  - improvement negative all splits, candidate not better than baseline
- finish MAE: NOT_TESTABLE / LIMITED due to missing full race simulation with SC/fuel etc, marked None but noted LIMITED
- winner match: NOT_TESTABLE for lap-only model (needs race simulation with pit strategy, SC, etc)
- top-3 overlap: NOT_TESTABLE similarly
- Brier: NOT_TESTABLE
- rank correlation: NOT_TESTABLE
- All metrics compare production tyre-v1.0.0 vs Phase-26 candidate decomposition; candidate must NOT be promoted merely because training fit improves (training r2 ~0.05 but validation worsens)

## Interpretation

Candidate decomposition worsens chronological validation (negative improvement) indicates overfitting to confounded progression or fuel effect dominating. Even circuit+driver controls worsen. This matches inverted beta: adding tyre_age with negative coefficient to circuit baseline predicts faster laps for older tyres, which is wrong out-of-sample where fuel effect not perfectly collinear per race due to varying stint lengths.

Candidate promotion requires chronological validation improvement; fails.

## Era Consideration

Only modern tyre periods testable; historical eras not tested due to no tyre data, correctly marked NOT_TESTABLE not fabricated.

