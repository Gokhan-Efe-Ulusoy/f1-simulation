# Phase 28 — Security Audit

## CORS
- `app/main.py` uses `CORSMiddleware` with `allow_origins=settings.CORS_ORIGINS` (default localhost:3000,8000), `allow_credentials=True`, `allow_methods=["*"]`, `allow_headers=["*"]`. No wildcard origin in production config; restricted via env `CORS_ORIGINS`.

## Request Size / Limits
- `RaceSimulationRequest.race_id` max 100, `MonteCarloRequest.race_id` max 100, `ScenarioCompareRequest` interventions max 20, simulations 1-5000, laps 1-200, seed int32, track_pit_loss 0-60. Pydantic `ge/le/max_length` enforced → 422 before handler.
- `GET /races` limit 1-200, offset >=0; `GET /simulation/{id}` id max 200.
- Events/telemetry capped to 200 entries per response to bound payload.

## Parameter Validation
- All inputs validated via Pydantic v2. No `eval`/`exec`, no `shell`, no `pickle`.
- Path traversal blocked: `..`, `/`, `\` rejected in every `race_id`, `simulation_id`, `checkpoint` (see `schemas.py` validators + endpoint guards).
- No filesystem paths from client: server resolves canonical data root internally (`app/services/race_service.py:_canonical_root()`), never trusts client path.
- No unsafe deserialization: JSON only, via Pydantic.

## Simulation Limits (DoS)
- Monte Carlo max 5000 (configurable `MAX_SIMULATIONS` in `montecarlo_service.py`), min 1. Requesting 6000 → 422 `SIMULATION_LIMIT_EXCEEDED` / `VALIDATION_ERROR`.
- Laps 1-200 prevents degenerate long races; interventions 20 prevents combinatorial explosion.
- No (N,D,L) tensors: VectorizedMonteCarlo uses (N,D) + (N,L) shared trajectories, not (N,D,L,features). Memory O(N*D + N*L) ~ 5000*20 + 5000*70 = 450k floats ~ 2 MB.
- No per-request full dataset load: `race_service` caches races.json/results.json via `lru_cache`.

## Code Execution
- No user input reaches `eval`, `exec`, `subprocess`, `open` with user path, `import` with user string.
- Scenario compilation is deterministic allowlist-driven (`registry.FAMILY_OPS/PARAMS`, `validation.validate_spec`), not code generation.

## Denial-of-Service via N/laps
- Covered by hard limits above + synchronous path is bounded (< ~10s for N=5000). Future async job abstraction via `store` with status queued/running/completed/failed is scaffolded (in-memory) if background execution becomes needed; no Redis/Celery introduced per spec (smallest architecture that works).

## Error Handling
- Structured errors via `app/core/errors.py:ErrorCode`; `RequestValidationError` and `StarletteHTTPException` handlers return JSON with code/message, never stack traces in production (DEBUG flag controls FastAPI debug, but handlers always sanitize).

## Verification
- `tests/test_phase28_api.py::test_path_traversal_rejected`, `test_monte_carlo_limits`, `test_strategy_leakage_rejected`, `test_scenario_leakage_rejected` all pass.
- Manual check: `curl -X POST ... race_id="../etc/passwd"` → 422.

## Residual Risks
- In-memory store not persistent; restart loses jobs (acceptable for current deployment).
- CORS allow_methods "*" is permissive; consider restricting to GET/POST in production.
