# Phase 27 Walk-Forward Validation

## Mandatory Gate — Chronological Splits

- train <=2023 -> validate 2024 n_train 23430 n_val 24268 baseline 6.235 candidate 6.188 improvement 0.047
- train <=2024 -> validate 2025 n_train 47698 n_val 24889 baseline 8.410 candidate 8.045 improvement 0.365
- train <=2025 -> validate 2026 n_train 72587 n_val 16030 baseline 5.966 candidate 7.222 improvement -1.255
- Also additional rolling splits where data allows:
  - <=2018 -> 2019,2020 NOT_TESTABLE (no tyre data)
  - <=2020 -> 2021 NOT_TESTABLE
  - <=2021 -> 2022 NOT_TESTABLE
  - <=2022 -> 2023 NOT_TESTABLE (first tyre year need train)
- Each: baseline lap MAE (circuit mean), candidate lap MAE (circuit+driver+progression), improvement, winner/top3 if full simulation permits (not for lap-only model, would need race simulation with pit/SC etc, marked PRIOR_ONLY), uncertainty, sample size
- Do not cherry-pick races, do not average away failures: we report each split individually, note last split fails badly -1.25, so not stable improvement
- Candidate must demonstrate stable improvement across splits: FAIL, improvement not stable (0.047, 0.365, -1.25)

## Interpretation
- Circuit+driver+progression associational improves first two splits slightly but worsens third due to 2026 small sample and progression overfit
- Full identifiable model with tyre would worsen more (phase26 -0.72 etc)
- Therefore walk-forward gate fails for promotion.

