# Phase 22.6 — Lap Quality Report (`laps_jolpica/`, 98,950 rows, 99 races)

No outliers were removed. Classification first, always.

| check | result |
|---|---|
| rows / races / drivers | 98,950 / 99 (1996–2001) / 49 |
| duplicate `lap_id` PKs | **0** |
| null lap_time / lap_number / driver_id | **0 / 0 / 0** |
| impossible lap < 50 s | **0** (min 70.843 s) |
| extreme laps > 600 s | **6** (max 1169.7 s) — red-flag/suspended-race laps, kept + flagged by duration |
| lap_number range | 1–78, per-race maxima consistent with era race distances |
| driver completeness vs results | 151 missing driver-slots / 99 races — retirement truncation (DNF before laps recorded) + DNQ, expected, not backfilled by invention |
| temporal precision | race date as `observed_at`; lap-level wall-clock absent in source → precision marked `race-day` |
| leakage | all `observed_at` = race date; usable only with `as_of` = race_date − 1 day; violations = 0 |

## Pit duration quality (companion, `pitstops_jolpica/`, n = 12,733 observed)

mean 86.96 s (red-flag waits inflate) · median **23.580** · std 316.7 ·
min 12.092 · p05 18.774 · p25 21.893 · p75 26.554 · p95 46.722 · max 3069.0.
14 nulls (source gaps, time_of_day kept). By era: 2011–2017 median 23.34
(n 6244); 2018–2021 median 23.96 (n 2573); 2022–2026 median 23.70 (n 3916).
By circuit (top-n): 2023-zandvoort median 21.30 (n 101); 2017-singapore 29.68;
2025-australia 16.22 (wet); 2025-canada 18.30 (wet chaos).

**State: PIT_DURATION_OBSERVED. PIT_LOSS_NOT_IDENTIFIABLE** — no source splits
stationary vs lane loss. The 24.4 s prior is untouched.
