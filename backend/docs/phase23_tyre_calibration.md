# Tyre Degradation Calibration

## SOFT: coeff 0.08 se 0.02 n_stints 913 n_races 74 n_circuits 34 seasons [2023, 2024, 2025, 2026] tier LIMITED
## MEDIUM: coeff 0.04 se 0.02 n_stints 1823 n_races 82 n_circuits 36 seasons [2023, 2024, 2025, 2026] tier LIMITED
## HARD: coeff 0.02 se 0.02 n_stints 1743 n_races 82 n_circuits 36 seasons [2023, 2024, 2025, 2026] tier LIMITED
Controls: circuit, driver, constructor, progression, weather where observable, neutralisation where observable; fuel major confounder -> raw not causal; compared raw vs progression-adjusted vs circuit-adjusted vs hierarchical; per-compound only SOFT/MEDIUM/HARD when gates satisfied else PRIOR_ONLY/LIMITED; historical without compound PRIOR_ONLY/NON_IDENTIFIABLE, no backward extrapolation
