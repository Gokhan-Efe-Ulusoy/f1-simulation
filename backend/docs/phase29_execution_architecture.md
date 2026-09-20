# Phase 29 — Execution Architecture

## One Execution Path

All API endpoints delegate to a single orchestration layer, which delegates to existing engines. No second engine.

```
Client
  ↓ HTTP/JSON
API Contract (app/api/v1/schemas.py)
  ↓ Pydantic validation (no leakage, limits)
Service Orchestration (app/services/execution.py)
  ├─ execute_single_race(...) → app/services/simulation_service.py → RaceEngine
  ├─ execute_monte_carlo(...) → app/services/montecarlo_service.py → VectorizedMonteCarlo
  ├─ compare_scenario(...) → app/services/scenario_service.py → ReplayEngine.counterfactual (ScenarioEngine)
  ├─ evaluate_strategy(...) → app/services/strategy_service.py → DecisionEngine
  └─ replay_race(...) → app/services/replay_service.py → ReplayEngine
  ↓
Result Normalization (app/services/result_normalization.py + hashing)
  ↓
Persistent Simulation Store (app/services/store.py + app/core/database.py + app/models/simulation.py)
  ↓
API Response (status, simulation_id, request_hash, result_hash, provenance)
```

## Key Files
- `app/services/execution.py`: SimulationRequest/MonteCarloRequest dataclasses, MODIFIER_SUPPORT map, `execute_single_race`, `execute_monte_carlo`, request hash helpers.
- `app/services/hashing.py`: `canonical_json`, `request_hash`, `result_hash` (sorted keys, excludes timestamps/ids/paths).
- `app/services/result_normalization.py`: separates execution_metadata, race_output/monte_carlo_output, provenance, evidence_tiers.
- `app/services/simulation_service.py`, `montecarlo_service.py`, `scenario_service.py`, `strategy_service.py`, `replay_service.py`: thin wrappers, no duplicated physics.
- `app/services/store.py`: DB primary (SQLAlchemy) + in-memory fallback, lifecycle QUEUED→RUNNING→COMPLETED/FAILED.
- `app/core/database.py`: engine (postgres sync fallback to sqlite file `data/simulations.db`), `Base`, `SessionLocal`, `init_db()`.
- `app/models/simulation.py`: `SimulationRecord` table.

## Service Responsibilities
- `simulation_service`: builds drivers/cars/track deterministically, creates `SimulationConfig`, calls `RaceEngine.simulate_race`, normalizes to API shape.
- `montecarlo_service`: builds `Scenario` (historical or synthetic), injects `hypothetical_modifiers`, calls `VectorizedMonteCarlo.run`.
- `scenario_service`: validates via `registry`/`validation`, calls `ReplayEngine.counterfactual` with CRN.
- `strategy_service`: validates `StrategyState`, calls `DecisionEngine.decide` with isolated RNG 700.
- `replay_service`: calls `ReplayEngine.replay`/`checkpoint`.

## Guarantees
- API never consumes simulation RNG (request IDs via `uuid`, hashes via `hashlib`, no `random`).
- No NDL tensors: VectorizedMonteCarlo remains (N,D)+(N,L) only.
- All modifiers recorded with support status, never silently upgraded.
