# Phase 28 — API Architecture

## Overview
Thin application layer over existing simulation engines. No physics rewritten.

```
Frontend (Next.js 14)
  ↓ HTTP/JSON
FastAPI /api/v1  (app/main.py + app/api/v1/router.py)
  ↓ Pydantic schemas (app/api/v1/schemas.py)
Application Services (app/services/*)
  ↓
Existing Engines:
  RaceEngine (app/simulation/core/race_engine.py)
  VectorizedMonteCarlo (app/simulation/performance/vectorized_montecarlo.py)
  DecisionEngine (app/simulation/strategy/decision_engine.py)
  ReplayEngine + ScenarioEngine (app/simulation/replay/, scenario/)
  Setup/Weather/RaceControl (lazy inside engines)
  ↓
Data / Calibration (app/data/, app/simulation/version.py)
```

## Key Decisions
- **Reuse, don't duplicate**: All simulation logic delegated. Services are ~50-150 lines wrappers.
- **No new calibration**: Production versions unchanged (calibration-v1.0.0 etc). Candidates remain candidates.
- **In-memory store**: `app/services/store.py:SimulationStore` (dict, max 1000, oldest eviction). No Redis/Celery — synchronous with hard limits is sufficient for current deployment. `POST /simulate/*` with `save_replay=true` stores result for `GET /simulation/{id}` (queued/running/completed/failed minimal shape).
- **Determinism preserved**: Seed is int32, passed through to `RandomProvider(seed)` and `BatchRNG(seed)`. API itself introduces no RNG. Streams isolated: weather, race_control (600+), strategy (700), AR1 (100).
- **Caching**: `app/services/race_service.py` uses `@lru_cache` for canonical races.json/results.json — never loads full dataset per request beyond cached metadata. Races listing uses indexed filtering + pagination (limit 1-200, default 50).
- **Request size guard**: All race_id/simulation_id max 100-200 chars, interventions max 20, simulations max 5000 (see schemas.py).

## Endpoint Map
- `GET /health` (existing, unchanged)
- `GET /metadata` → `metadata_service.get_metadata()` → version.py constants + evidence_tiers
- `GET /races?season&circuit&driver&constructor&limit&offset` → `race_service.list_races()`
- `GET /races/{race_id}` → `race_service.get_race()` → 404 if missing
- `POST /simulate/race` → `simulation_service.simulate_single_race()` → RaceEngine
- `POST /simulate/monte-carlo` → `montecarlo_service.run_montecarlo()` → VectorizedMonteCarlo
- `POST /strategy/evaluate` → `strategy_service.evaluate_strategy()` → DecisionEngine
- `POST /scenario/compare` → `scenario_service.compare_scenario()` → ReplayEngine.counterfactual
- `GET /replay/{race_id}?checkpoint&seed&simulations&laps` → `replay_service.replay_race()` → ReplayEngine
- `GET /simulation/{simulation_id}` → store.get()

## Security
- CORS from `app/core/settings.py:CORS_ORIGINS`
- Path traversal blocked (`..`, `/`, `\` rejected in race_id/simulation_id)
- No filesystem paths from client, no eval/exec, no shell
- Pydantic validation on all inputs (ge/le, max_length)
- Hard limits prevent DoS via N/laps (simulations 1-5000, laps 1-200, interventions 20)
- Error handlers never leak stack traces (see main.py validation/http handlers)

## Performance
- Single race: ~0.09s direct vs ~0.10s API (11.9% overhead, dominated by JSON serialization/store; bulk is engine)
- Monte Carlo N=100: ~2.8s API (warm cache) vs ~6.8s cold direct; overhead <0% when cached, <10% target otherwise
- No (N,D,L) tensors: batch is (N,D) + (N,L) weather/RC shared

## Limitations
- Single-race weather/RC/setup toggles are provenance-only for PRIOR_ONLY honesty (single RaceEngine path not fully vectorized for those; Monte Carlo path honours via hypothetical_modifiers)
- Simulation store is in-memory, not persistent across restarts
- Async jobs not needed yet; synchronous with limits is safe

## OpenAPI
FastAPI auto-generates `/openapi.json`, `/docs`, `/redoc`. Every endpoint has summary/description + request/response schemas + error responses.
