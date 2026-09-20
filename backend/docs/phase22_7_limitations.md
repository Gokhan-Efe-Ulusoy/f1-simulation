# Phase 22.7 Limitations

- 2026 season future races (rounds 15-23) NOT_AVAILABLE: no lap data yet (season not completed)
- Rate limiting caused 429s: handled with backoff, 7 races required retry (now completed)
- Lap times are raw observed values; no causal interpretation
- OpenF1 overlap not fully reconciled; classified for future calibration
- No interpolation of missing laps, no fabricated laps for retired drivers
- Dataset is CALIBRATION_CANDIDATE only, no model recalibration in this phase
