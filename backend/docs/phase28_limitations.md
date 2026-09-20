# Phase 28 — Limitations

All limitations from Phase 27 persist; Phase 28 adds no new physics and promotes nothing.

## Production Model (unchanged)
- Dataset: f1-dataset-v1.3 (552,656 laps, 1,172 races)
- Versions: calibration-v1.0.0, tyre-v1.0.0, weather-v1.0.0, racecontrol-v1.0.0, strategy-v1.1.0, setup-v1.0.0, raceengine-v2.2.0, model 0.9.0

## Evidence Tiers (exposed via GET /metadata and every simulation response)
- fuel: NON_IDENTIFIABLE (no fuel telemetry, proxy only)
- tyre_historical: NON_IDENTIFIABLE (no per-lap degradation for historical races)
- tyre_modern: LIMITED (only 2023+ Pirelli era with constraints)
- strategy: PRIOR_ONLY (DecisionEngine priors, not calibrated wins)
- setup: PRIOR_ONLY (18 dials, model offsets only)
- weather_historical: PRIOR_ONLY (prior policy, no observed weather injected)
- race_control_historical: PRIOR_ONLY (prior policy, no observed flags injected)
- driver/circuit/constructor: LIMITED (hierarchical shrinkage, confounding)

## What Phase 28 Does NOT Do
- No fuel manufacturing, no historical tyre reconstruction, no weather/strategy history fabrication, no fake telemetry, no arbitrary scenario parameters.
- No promotion of LIMITED/PRIOR_ONLY models.
- No new calibration, no dataset hash change.

## API-Specific Limitations
- Single-race `enable_weather/setup/race_control` are provenance-only toggles: single RaceEngine path currently applies strategy/RC but historical weather/setup remain PRIOR_ONLY (vectorized Monte Carlo path honours hypothetical_modifiers correctly; single-race will be unified in future phase).
- Simulation store is in-memory (1000 entries, not persistent, lost on restart).
- Monte Carlo max 5000 (DoS protection); larger N requires job abstraction (scaffolded but not yet background-executed).
- No per-request telemetry beyond 200 events (payload bound).
- Scenario interventions limited to allowlist (setup/strategy/tyre/race_control/weather/driver/car); `future_*`, `observed_result`, `final_standings` etc rejected.
- Replay requires historical race in `data/canonical/races.json`; synthetic track-only ids (e.g., `bahrain` alone) work for simulate/monte-carlo but not for replay/scenario (returns 404).

## Honest Warnings Returned by API
- `"strategy is PRIOR_ONLY: not calibrated, prior assumptions only"`
- `"setup is PRIOR_ONLY: model dials, not historical data"`
- `"historical weather is PRIOR_ONLY: no per-race observed weather injected"`
- `"historical race control is PRIOR_ONLY: prior policy only"`
- Plus per-intervention `evidence_tier: PRIOR_ONLY` and `limitations` list in scenario/replay.

## Future Work (not in Phase 28)
- Unified single-race + vectorized modifiers for full PRIOR_ONLY honesty
- Persistent job queue (Redis/Celery) if N=5000 p95 >30s in prod
- More granular evidence tiers per field (currently race-level)
