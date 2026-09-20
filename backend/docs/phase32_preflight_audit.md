# Phase 32 Preflight Audit (actual code, not reports)

Date: 2026-09-20. `fatal: not a git repository` still true (checked frontend + backend). Documented as infra limitation; no git init.

## Backend (verified live)

- Router `backend/app/api/v1/router.py`: 9 routers → 12 OpenAPI paths: health, metadata, metrics, races, races/{id}, simulate/race, simulate/monte-carlo, strategy/evaluate, scenario/compare, replay/{id}, simulation/{id}, simulation/{id}/cancel. Matches expected list + metrics/cancel additions.
- Schemas `backend/app/api/v1/schemas.py`: RaceSimulationRequest (race_id, seed int32, laps 1..200, track_id, enable_strategy/setup/weather/race_control, save_replay, priority 0..100), MonteCarloRequest (+simulations 1..5000, chunk_size 1..5000), ScenarioCompareRequest (interventions 1..20, leakage blocklist), StrategyEvaluateRequest (state dict, leakage guard), SimulationJobResponse (QUEUED/RUNNING/COMPLETED/FAILED/CANCELLED/TIMEOUT). Field names are source of truth for frontend.
- Execution: `app/services/execution.py` → simulation_service (RaceEngine), montecarlo_service (VectorizedMonteCarlo + chunked), scenario/strategy/replay services. No duplicate physics in endpoints (thin orchestration). Store: SQLAlchemy SimulationRecord + JobRecord, postgres→sqlite fallback. Queue: InProcessJobQueue + RedisJobQueue interface, max_concurrent 4, max_depth 100.
- Versions `app/simulation/version.py`: SIMULATION 9.2.0, RACEENGINE v2.2.0, MODEL 0.9.0, calibration-v1.0.0, tyre-v1.0.0, weather-v1.0.0, racecontrol-v1.0.0, strategy-v1.1.0, setup-v1.0.0. Live `/metadata` returns dataset f1-dataset-v1.3 + evidence_tiers. No discrepancy with reports.
- Error handling: structured `{error:{code,message}}`, no stack traces. Provenance: request_hash/result_hash, seed, versions in every result.

## Frontend (verified files)

- `frontend/app/page.tsx`: real home nav (4 cards) — works.
- `frontend/app/simulator/page.tsx`: placeholder — only health-check button + static config boxes ("will be implemented in Phase 1+"), hardcoded VER/+2.341s. NOT functional.
- `frontend/app/monte-carlo/page.tsx`: placeholder — hardcoded VER 65%/15% bars, "will be implemented in Phase 10+". Fake probabilities — must be replaced.
- `frontend/app/strategy/page.tsx`: placeholder — hardcoded Optimal 1:23:45.6 table, "will be implemented in Phase 6+". Fake.
- `frontend/app/championship/page.tsx`: placeholder — hardcoded VER 437pts, "will be implemented in Phase 9+". Fake.
- `frontend/app/components|features|hooks|lib|types`: all empty. No API client, no types, no state management, no polling, no loading/error states beyond local useState in simulator.
- `frontend/__tests__/HomePage.test.tsx`: only home title/nav — passes.
- Config: `package.json` (next 14.2, react 18, axios present but unused, recharts unused), `next.config.js` rewrite `/api/backend/:path*` → localhost:8000 (hard-coded localhost, should use env), `.env.example` has `NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1` (correct env name to use), `tsconfig` strict + `@/*` → `./app/*`, jest jsdom + `__tests__/**/*.test`.
- Server/client: pages needing interactivity must be `'use client'` (simulator already is).

## Architecture decision (smallest fitting)

- No Redux/Zustand/React Query. Use native `useState/useEffect/useCallback`, `fetch` (axios already dep but fetch suffices; keep axios unused to avoid churn — actually use fetch for zero new deps).
- Structure: `frontend/app/lib/api/{client.ts,races.ts,simulations.ts,scenarios.ts,types.ts}` (fits `@/*` mapping). Types mirror backend field names, `unknown` isolated at boundary.
- Base URL: `process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1'` with rewrite fallback. No hard-coded localhost in components.
- Polling: `setInterval` 2000ms in simulator, stop on COMPLETED/FAILED/CANCELLED/TIMEOUT.
- Shell: update `app/layout.tsx` with nav (/, /simulator, /monte-carlo, /strategy, /championship). Primary functional page `/simulator`; others become honest entry points linking to simulator + disabled future modes.
