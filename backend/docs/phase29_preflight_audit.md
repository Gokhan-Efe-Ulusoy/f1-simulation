# Phase 29 Preflight Audit

Generated: 2026-09-20
Branch: Phase 28 COMPLETE_WITH_LIMITATIONS -> Phase 29

## 1. Current Execution Paths

### Single Race
`POST /api/v1/simulate/race` (`app/api/v1/endpoints/simulate.py:29`) → `app/services/simulation_service.py:157 simulate_single_race(race_id, seed, laps_override, enable_* , track_id)` → `_build_drivers_cars_track(race_id)` (deterministic sha256 skill, `get_2024_calendar()`, fallback `load_historical_race`) → `SimulationConfig(track_id, total_laps, strategy_enabled, race_control_enabled)` → `RandomProvider(seed)` → `app/simulation/core/race_engine.py:103 RaceEngine().simulate_race(...)` (sequential, `get_stream(name)` isolated) → `RaceResult.model_dump()` → normalized API dict (classification, lap_summary, incidents, events[0:200]) → `app/services/store.py:17 store.create(..., status="completed")` synchronously.

### Monte Carlo
`POST /api/v1/simulate/monte-carlo` (`simulate.py:70`) → `app/services/montecarlo_service.py:70 run_montecarlo(...)` → `_build_scenario_for_montecarlo(race_id)` tries `load_historical_race` + `build_scenario_for_race` else fallback `_build_drivers_cars_track` → synthetic `Scenario(circuit_id, date, as_of, ...)` → inject `hypothetical_modifiers["weather"/"race_control"].enabled=False` → `VectorizedMonteCarlo(calibration_state, scenario, seed).run(simulations)` (vectorized N,D + N,L weather/RC, Level A seed+sim_idx*1000, Level B seed+100+lap) → reshape to `MonteCarloResponse` → `store.create(..., type="monte_carlo")`.

### Scenario / Counterfactual
`POST /api/v1/scenario/compare` → `scenario_service.compare_scenario` → `Intervention` validation via `registry.py` allowlist + `validation.py` leakage blocklist → `ReplayEngine.counterfactual` (uses `ScenarioEngine`, `compiler.compile_spec`, CRN both legs via `VectorizedMonteCarlo`).

### Strategy
`POST /api/v1/strategy/evaluate` → `strategy_service.evaluate_strategy` → `StrategyState.model_validate` + leakage reject → `DecisionEngine(as_of="2024-03-01", seed).decide(state, track_pit_loss, seed)` (offset 700).

### Replay
`GET /api/v1/replay/{race_id}` → `replay_service.replay_race` → `ReplayEngine.replay` / `checkpoint` (truncated horizon legs, `valid_checkpoints`).

All endpoints call services which call existing engines directly — thin but not yet unified via a single orchestration layer.

## 2. Duplicate Execution Logic

- Services are thin wrappers delegating to distinct engines (RaceEngine vs VectorizedMonteCarlo vs ReplayEngine vs DecisionEngine) — no duplication between services by design.
- Legacy duplication across `app/simulation/montecarlo.py` (Phase 14 MonteCarloRunner per-sim loop) vs `app/simulation/performance/vectorized_montecarlo.py` (production vectorized). Monte Carlo service only uses vectorized; legacy remains dead code for benchmarks.
- `app/simulation/race_engine_v14.py`..`v22.py` layered inheritance (each adds weather/RC/setup/scenario) share core logic but Phase28 services bypass chain and call `core/race_engine.py` (single) and `vectorized_montecarlo.py` (MC) directly — divergence risk if v22 logic not mirrored.
- Minor duplication: `_build_drivers_cars_track` in `simulation_service.py` duplicated as fallback in `montecarlo_service.py`; simulation_id generation 3 prefixes (`sim_`, `race_`, `mc_` + colon form) + uuid fallback; calibration fallback empty priors duplicated.

## 3. Where Single-Race Weather/Setup Modifiers Currently Stop

- `simulation_service.py:177-186`: `SimulationConfig` constructed with only `strategy_enabled` and `race_control_enabled`. `enable_weather`/`enable_setup` passed to `_provenance()` only (probes `getattr(config,"weather_enabled",True)` etc, always True/False). Comments explicitly: `Weather toggle not in SimulationConfig; default enabled` and `Setup toggle: provenance only (single-race PRIOR_ONLY)`.
- `SimulationConfig` (`app/simulation/core/state.py:169`) has no `weather_enabled`/`setup_enabled`; only `race_control_enabled`, `strategy_enabled`.
- `_provenance()` fabricates enable flags but no `RaceEngine` lap loop reads them; no `hypothetical_modifiers` plumbing. Warnings appended (`setup is PRIOR_ONLY`, `historical weather is PRIOR_ONLY`) but no physical effect.
- vs Monte Carlo: `montecarlo_service.py:92-99` correctly sets `scenario.hypothetical_modifiers["weather"/"race_control"].enabled=False` checked in `vectorized_montecarlo.py:283,292`; setup via `setup/offsets.py:setup_offsets_for_scenario` (404), tyre/strategy via resolvers. Single-race path would need to extend `SimulationConfig` or accept `Scenario` to unify.

## 4. How Monte Carlo Results Are Currently Represented

- Raw `VectorizedMonteCarlo.run:761-808`: `{"simulation_id":"{scenario_id}:{seed}:{N}", "drivers":{did: {win_probability, podium_probability, top5/10_probability, finish_probability, dnf_probability, expected_finish, median_finish, finish_CI95, expected_points, points_CI95, finish_distribution, points_distribution, uncertainty, sample_size, evidence_tier}}, "constructors":..., "summary":{simulations,seed,weather,race_control}, "provenance":{dataset_version:"f1-dataset-v1.1", calibration_version, engine_version:"raceengine-v1.4.0", ...}, "weather":..., "race_control":..., "setup":..., "pit_loss":..., "race_control_trajectories":...}`.
- Normalized API `montecarlo_service.py:117-163` + `schemas.py:145`: flattens to `{simulation_id, race_id, N, simulations, seed, win_probabilities, podium_probabilities, finish_position_distribution, expected_finish, dnf_statistics, expected_points, uncertainty:{note, ci95_per_driver}, distribution: <raw drivers alias>, constructors, summary, provenance, model_versions, evidence_tiers, runtime:{elapsed_seconds, simulations_per_second}, reproducibility, warnings, raw}`. `N` and `simulations` both present; `distribution` duplicates raw drivers; `raw` nests full.

## 5. How Simulation IDs Are Generated

- `app/services/store.py:17-18`: `sid = payload.get("simulation_id") or f"sim_{uuid.uuid4().hex[:12]}"`; `payload["simulation_id"]=sid`; LRU eviction 1000 oldest.
- `simulation_service.py:178,235`: `config.simulation_id=f"race_{race_id}_{seed}"`; `api_result["simulation_id"]=rd.get("simulation_id") or f"sim_{race_id}_{seed}"`; endpoint preserves that id via `store.create({**result, simulation_id:sid})`.
- `montecarlo_service.py:118,762`: raw `f"{scenario.scenario_id}:{seed}:{N}"` then fallback `f"mc_{race_id}_{seed}_{simulations}"`.
- `scenario_service.py:60`: `exp-{race_id}-api` propagated.
- Inconsistency: 3 prefixes + uuid fallback; collisions possible if seed None; no type namespacing; not deterministic hash-based; store does not generate deterministic ids.

## 6. Current Persistence Capabilities

- `app/services/store.py:10-39` in-memory only `dict[str,dict]` + `time.time()` + max 1000 eviction. Methods `create(payload,status)`, `get(sid)`, `set_status(sid,status,result)`. No lock, no Redis, no DB, lost on restart. Comment: `Thread-safe in-memory store. No persistence, no Redis.`
- `app/models/__init__.py` empty, `app/repositories/__init__.py` empty — 0 tables, 0 repositories.
- `app/core/settings.py:27` declares `DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/f1sim"` but never imported in services/endpoints. `pyproject.toml` has `sqlalchemy>=2.0`, `asyncpg`, unused.
- `docker-compose.yml:4-27` provisions `postgres:16-alpine` + backend `DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/f1sim` but `app/main.py:17 lifespan` is no-op, never connects. `GET /simulation/{id}` only reads `store`.

## 7. Current Database Capabilities

- Models: none (no Base, no tables, no __all__).
- Repositories: none.
- Migrations: no `alembic/` directory, no `alembic.ini`.
- Compose: postgres healthy via `pg_isready`, volume `postgres_data`, backend `depends_on: service_healthy`.
- Settings: DATABASE_URL present but `main.py` never creates engine/session.
- Conclusion: DB provisioned but not wired — dependencies installed but 0 usage. Phase29 must create `simulations` table (id, type, status, result JSONB, timestamps), repositories, init, and replace/hybridize store.

## 8. Whether Background Execution Scaffolding Already Exists

- Store status field exists: `schemas.py:277 SimulationJobResponse status Literal["queued","running","completed","failed"]` and `store.py:17 create(..., status="completed")` + `set_status(...)` support all 4 but only `"completed"` ever used. `simulate.py:60,98` `store.create(..., status="completed")` synchronously after blocking engine call. No queued/running transitions.
- No async/Celery: grep `celery|BackgroundTasks|create_task|arq|dramatiq` 0 hits in `app/` (only `async def` endpoints calling blocking numpy). No `app/core/celery.py`, no worker, no broker env. `GET /simulation/{id}` just returns `{"simulation_id", "status": rec.get("status","completed"), "result": rec}`. Scaffolding = minimal status field only - no queue, no polling, no webhook.

## 9. Compatibility Risks

- **Store -> DB**: `tests/test_phase28_api.py:88` expects `POST /simulate/race` then immediate `GET /simulation/{sid}` returns `status completed` with identical classification. Async queued→running→completed would break synchronous contract unless sync path kept or tests poll. UUID vs deterministic id change breaks lookup. Eviction vs persistent changes semantics (tests rely on in-memory isolation).
- **Modifier unification**: Adding `weather_enabled/setup_enabled` to `SimulationConfig` and `RaceEngine` to honor vectorized `hypothetical_modifiers` changes lap times; must preserve evidence tiers (`PRIOR_ONLY`) and warnings; `provenance` hack `getattr(config,"setup_enabled",False)` needs migration. Risk of determinism break: vectorized Level A/B streams differ from RaceEngine sequential stream — must keep `same seed+config+versions => identical`.
- **Performance/limits**: Hard limits `1..5000` via Pydantic 422 must stay; moving to background relaxes timeout but must still guard DoS. `events[:200]`/`telemetry[:200]` caps must persist or DB JSONB bloats.
- **Provenance/version**: `app/simulation/version.py` pins `RACEENGINE v2.2.0` — unifying modifiers may need `SIMULATION_VERSION` bump or tests `test_no_calibration_promotion` fail.

## 10. Exact Files That Will Be Changed

- **Already Audited Phase28 Files (to be modified/extended):**
  `app/api/v1/router.py`, `app/api/v1/schemas.py`, `app/api/v1/endpoints/health.py`, `app/api/v1/endpoints/metadata.py`, `app/api/v1/endpoints/races.py`, `app/api/v1/endpoints/simulate.py`, `app/api/v1/endpoints/strategy.py`, `app/api/v1/endpoints/scenario.py`, `app/api/v1/endpoints/replay.py`, `app/api/v1/endpoints/simulation.py`, `app/services/store.py`, `app/services/simulation_service.py`, `app/services/montecarlo_service.py`, `app/services/scenario_service.py`, `app/services/strategy_service.py`, `app/services/replay_service.py`, `app/services/metadata_service.py`, `app/services/race_service.py`, `app/core/errors.py`, `app/core/settings.py`, `app/core/config.py`, `app/main.py`
- **New Files to Create:**
  `app/core/database.py` (engine, session, Base, init_db), `app/models/simulation.py` (SimulationRecord table), `app/services/execution.py` (unified orchestration + request/response dataclasses + hashing), `app/services/hashing.py` (request/result hash utils), `app/services/result_normalization.py` (stable internal result representation)
- **Config/Infra (referenced):**
  `docker-compose.yml`, `pyproject.toml`, `app/simulation/version.py`
- **Tests:**
  `tests/test_phase28_api.py` (must remain passing), `tests/test_phase29_execution.py` (new)
- **Docs:**
  `docs/phase29_preflight_audit.md` (this file) plus 9 new phase29 docs (existing `docs/phase28*.md` remain)
