# Phase 29 — Limitations

All Phase 28 scientific limitations persist; no promotion.

- Production: calibration-v1.0.0, tyre-v1.0.0, weather-v1.0.0, racecontrol-v1.0.0, strategy-v1.1.0, setup-v1.0.0, raceengine-v2.2.0, model 0.9.0, dataset f1-dataset-v1.3 (552,656 laps/1,172 races).
- Evidence tiers: fuel NON_IDENTIFIABLE, tyre_historical NON_IDENTIFIABLE, tyre_modern LIMITED, strategy PRIOR_ONLY, setup PRIOR_ONLY, weather_historical PRIOR_ONLY, race_control_historical PRIOR_ONLY, driver/circuit LIMITED.

## Phase 29 Infrastructure Limitations

- Single-race weather/setup remain `PROVENANCE_ONLY`: `execute_single_race` records `modifiers_support` with `provenance_only_single` but does not apply physical effect in `RaceEngine` lap loop (vectorized Monte Carlo does apply via `hypothetical_modifiers` and `setup_offsets_for_scenario`). Keeping as `PRIOR_ONLY` is honest; unifying would require rewriting RaceEngine sequential weather trajectory to share vectorized `WeatherEngine` logic (science change, not done).
- Other modifiers: `baseline` supported, `tyre` supported_conditional (2023+ PIRELLI only), `race_control` supported (both paths), `scenario` supported (allowlist), `strategy` supported (DecisionEngine), `fuel` unsupported.
- Simulation store: persistent via SQLAlchemy (postgres → sqlite fallback `data/simulations.db`), but sqlite fallback is used in CI where postgres not running; not distributed, no replication; 1000-entry LRU still in memory fallback.
- Lifecycle: synchronous QUEUED→RUNNING→COMPLETED in same request for small jobs; no real background worker (no Celery/Redis). Scaffolded statuses allow future upgrade.
- Monte Carlo max 5000 (DoS guard); larger N rejected 422, not queued (per spec small→sync, large→rejected/queued).
- No per-request telemetry beyond 200 events (payload bound).
- Request hashing excludes timestamps/IDs/paths; same logical request → same hash but not same DB ID (IDs remain uuid collision-safe).

## Honest Warnings

API returns warnings for PRIOR_ONLY toggles:
- "strategy is PRIOR_ONLY: not calibrated, prior assumptions only"
- "setup is PRIOR_ONLY: model dials, not historical data"
- "historical weather is PRIOR_ONLY: no per-race observed weather injected"
- plus per-intervention `evidence_tier: PRIOR_ONLY` and `limitations` list.

## Future Research (not Phase29)

- Unify single-race weather/setup via shared `Scenario` resolvers if validated.
- Async worker queue for N=5000 p95 >30s.
- Per-field evidence tiers and more granular `unsupported_modifiers` reporting.
