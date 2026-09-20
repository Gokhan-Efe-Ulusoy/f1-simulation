# Phase 29 — API Contract (Refined)

Base: `/api/v1` — all Phase 28 endpoints remain, now via unified service layer + persistent store.

## Endpoints (all use service layer)

- `GET /health` → `HealthResponse`
- `GET /metadata` → `MetadataResponse` (versions + evidence_tiers)
- `GET /races?season&circuit&driver&constructor&limit&offset` → cached `races.json` metadata, pagination
- `GET /races/{race_id}` → single race metadata, 404 if missing
- `POST /simulate/race` → `RaceSimulationRequest` → `RaceSimulationResponse` + persisted
- `POST /simulate/monte-carlo` → `MonteCarloRequest` → `MonteCarloResponse` + persisted
- `POST /strategy/evaluate` → `StrategyEvaluateRequest` → `StrategyEvaluateResponse`
- `POST /scenario/compare` → `ScenarioCompareRequest` → `ScenarioCompareResponse` + persisted as scenario
- `GET /replay/{race_id}?seed&simulations&laps&checkpoint` → `ReplayCheckpointResponse`
- `GET /simulation/{simulation_id}` → `SimulationJobResponse` (persisted, not in-memory only)

## POST /simulate/race (refined)

Request `RaceSimulationRequest` (unchanged schema Phase28, plus internal modifiers mapping):
```
race_id, seed int32, laps_override 1-200, track_id, enable_strategy/setup/weather/race_control, save_replay
```
Response `RaceSimulationResponse` now includes Phase29 fields:
```
simulation_id, status: "COMPLETED" (sync) | QUEUED/RUNNING/FAILED, simulation_type: "race",
request_hash, result_hash, execution_time, execution_metadata:{request_hash, execution_time, modifiers_support},
+ legacy: race_id, seed, track_id, total_laps, classification, lap_summary, incidents, strategy_summary, provenance, model_versions, evidence_tiers, warnings, reproducibility, events[0:200], runtime
```
Lifecycle: POST creates QUEUED→RUNNING→COMPLETED in store; returns COMPLETED for small jobs. Large jobs remain sync in Phase29 (no Celery) but scaffolded for queued.

## POST /simulate/monte-carlo (refined)

Request `MonteCarloRequest` (simulations 1-5000):
```
race_id, simulations, seed, laps_override, enable_strategy/setup/weather/race_control, save_replay
```
Response `MonteCarloResponse` now includes `status`, `simulation_type: "monte_carlo"`, `request_hash`, `result_hash`, `execution_time`, `execution_metadata`.
Hard limits preserved: 1..5000 → 422 `SIMULATION_LIMIT_EXCEEDED` if exceeded. Never allows N×D×L×features.

## GET /simulation/{simulation_id}

Returns persisted `SimulationRecord`:
```
simulation_id, status: QUEUED|RUNNING|COMPLETED|FAILED, result: <full payload or null>, created_at, updated_at, error
```
404 `DATA_NOT_AVAILABLE` if unknown. Path traversal rejected (422). Retrieval is via DB (SQLAlchemy) with in-memory fallback; serialize→persist→retrieve preserves result within JSON tolerance.

## Request Hash (Idempotency)

Canonical request fingerprint via `hashing.request_hash`:
```
race_id, simulation_type, seed, sample_count, laps, modifiers, interventions, engine_version, model_version, dataset_version
```
Excludes timestamps, random IDs, paths. Same logical request → same hash. No automatic reuse unless explicitly allowed; hash stored as `request_hash` for provenance/caching.

## Result Normalization

Internal result distinguishes:
- execution_metadata: simulation_id, status, seed, sample_count, execution_time, engine_version, model_version, dataset_version, dataset_hash, request_hash, result_hash
- race_output / monte_carlo_output: finishing order, positions, DNF, win/probabilities, finish_distribution, DNF probability, quantiles, uncertainty
- provenance: evidence_tier, applied modifiers, unsupported modifiers, fingerprint, reproducibility

Unavailable metrics → `null` + explicit availability field (e.g., `pit: null` for single race).

## Errors (unchanged)

Structured `{"error": {"code": "...", "message": "...", "details": {}}}` with codes `RACE_NOT_FOUND`, `SIMULATION_LIMIT_EXCEEDED`, `UNSUPPORTED_INTERVENTION`, `INVALID_SEED`, `INVALID_LAP_RANGE`, etc. No stack traces.

## Backward Compatibility

Default path with no modifiers reproduces legacy result (verified `test_backward_compat_default_path_reproduces_legacy`). Calibration versions unchanged.
