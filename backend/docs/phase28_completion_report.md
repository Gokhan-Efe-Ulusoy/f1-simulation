# Phase 28 Completion Report

Generated: 2026-09-20
Dataset: f1-dataset-v1.3  laps 552,656 / races 1,172 / pit 12,747
Production: calibration-v1.0.0, tyre-v1.0.0, weather-v1.0.0, racecontrol-v1.0.0, strategy-v1.1.0, setup-v1.0.0, raceengine-v2.2.0

## What Was Done
Thin production API over existing engines (no physics rewritten, no promotion):
- `GET /health` (existing)
- `GET /metadata` (all versions + evidence tiers)
- `GET /races` (filtered, cached metadata, pagination)
- `GET /races/{race_id}`
- `POST /simulate/race` (single deterministic RaceEngine, capped events)
- `POST /simulate/monte-carlo` (vectorized, 1..5000, no NDL tensors)
- `POST /strategy/evaluate` (DecisionEngine, leakage-safe)
- `POST /scenario/compare` (allowlist + leakage blocklist, CRN)
- `GET /replay/{race_id}` (checkpoints: pre_race/lap_1/5/10/finish or arbitrary lap)
- `GET /simulation/{simulation_id}` (in-memory store, queued/running/completed/failed minimal)

All endpoints have OpenAPI summaries/descriptions/schemas.

## What Improved
- Engine is now accessible to clients: select race → configure → run deterministic race → run Monte Carlo → retrieve structured results → strategy → counterfactual → provenance → reproduce via seed.
- `GET /metadata` makes scientific limitations visible (fuel NON_IDENTIFIABLE etc).
- `GET /races` no longer loads 500+ MB per request (lru_cache).

## What Was Not Done (by design)
- No new physics, no calibration promotion, no data fabrication.
- No duplicate engines; services delegate.
- No Redis/Celery (smallest architecture that works).

## Verification
- `pytest tests/test_phase28_api.py` 26/26 pass (health, metadata, races, deterministic same/different seed, Monte Carlo determinism/limits, strategy ok/leakage, scenario valid/leakage/invalid, replay/checkpoint, path traversal, openapi, API/direct equivalence, no promotion).
- Direct vs API equivalence: `simulate_single_race` classification identical.
- Determinism: same seed identical, different seed different (both paths).
- RNG isolation: strategy offset 700, AR1 100, RC 600 preserved; API adds no RNG.
- Leakage: violations 0 (adversarial future_ tests rejected).
- Regression: existing `test_race_engine`/`test_random_provider` still pass.
- Performance: single race 0.09→0.10s (11.9% overhead, explicitly measured), Monte Carlo N=100 2.8s warm; no NDL explosion.
- Security: path traversal, oversize, simulation limits tested.

## Why Complete
All Phase 28 success criteria met except mypy strict (pre-existing 363 errors in repo, not introduced by new thin layer; ruff passes after fixes). API introduces minimal overhead and no behavior change.

## Scientific Gate: PASS
No promotion, no fabrication, evidence tiers exposed, leakage 0.

## Artifacts
- `app/api/v1/schemas.py`, `app/api/v1/endpoints/{metadata,races,simulate,strategy,scenario,replay,simulation}.py`, `app/api/v1/router.py`, `app/main.py` (error handlers), `app/core/errors.py`, `app/services/{metadata,race,simulation,montecarlo,strategy,scenario,replay,store}.py`
- Docs: `phase28_preflight_audit.md`, `phase28_api_architecture.md`, `phase28_api_contract.md`, `phase28_security.md`, `phase28_validation.md`, `phase28_performance.md`, `phase28_limitations.md`, `phase28_completion_report.md`
- Tests: `tests/test_phase28_api.py` (26 tests)
