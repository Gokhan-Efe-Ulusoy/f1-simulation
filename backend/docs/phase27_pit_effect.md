# Phase 27 Pit-Lap Effect

## Separation
Pit-lap observations separated from ordinary racing laps via quality filter pit-lap (2950 laps, 3.3%).

## Calibrated Total Pit-Loss
- Mean ≈ 23.2 s (phase27) vs 24.1 s literature Phase24
- Median ≈ 23.1 s vs 23.8 s
- n_pit_laps 2950
- Tier LIMITED (n>100)
- Method: mean(pit lap times) - mean(valid laps), per race not per driver
- Excluding pit laps improves ordinary lap prediction MAE by ~0.1s (baseline 6.23 vs with pit included 6.35) because pit outliers inflate error; do not accidentally teach model that pit laps represent poor driver pace

## Do NOT Claim
- lane_loss
- stationary_loss
Because these remain NON_IDENTIFIABLE (intervals data partial 12/84, pit durations are totals lane+stationary split not observed, stint data no lane time)

## Exclusion
Pit-lap exclusion improves ordinary lap prediction and is deterministic.

