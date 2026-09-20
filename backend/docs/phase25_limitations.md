# Limitations

- Exact join only 2023-2026 99.4% (93096), historical 1996-2022 0% NON_IDENTIFIABLE
- Tyre coefficients negative implausible -> fuel confounding not resolved, 59% change when controlling lap_number, corr 0.497
- Walk-forward only 2 testable splits due to limited tyre seasons, improvement -0.08 then +0.29 inconsistent
- No historical modern tyre backfill, no interpolation of missing laps, no fabricated fuel/temperature
- Driver interaction limited due to sparse per-driver n, circuit interaction limited, era 1996-2009 NON_IDENTIFIABLE
- Candidate improves validation inconsistently, sign not plausible -> NOT_PROMOTED
