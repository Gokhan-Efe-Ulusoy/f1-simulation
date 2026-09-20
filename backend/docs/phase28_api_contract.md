# Phase 28 — API Contract

Base: `/api/v1`

## Error Model
All errors return:
```json
{"error": {"code": "RACE_NOT_FOUND", "message": "...", "details": {}}}
```
Codes: `INVALID_CONFIGURATION`, `RACE_NOT_FOUND`, `DATA_NOT_AVAILABLE`, `DATA_PARTIAL`, `UNSUPPORTED_INTERVENTION`, `SCIENTIFIC_NON_IDENTIFIABLE`, `SIMULATION_LIMIT_EXCEEDED`, `INVALID_SEED`, `INVALID_LAP_RANGE`, `INTERNAL_SIMULATION_ERROR`, `VALIDATION_ERROR` (422 for Pydantic).

## Endpoints

### GET /health
Response `HealthResponse { status, version, simulation_model_version }`

### GET /metadata
Returns dataset/model versions + evidence tiers. See `metadata_service.get_metadata()`.
```
dataset_version: f1-dataset-v1.3
calibration_version: calibration-v1.0.0
tyre_version: tyre-v1.0.0
weather_version: weather-v1.0.0
race_control_version: racecontrol-v1.0.0
strategy_version: strategy-v1.1.0
setup_version: setup-v1.0.0
race_engine_version: raceengine-v2.2.0
model_version: 0.9.0
simulation_version: 9.2.0
evidence_tiers: {fuel:NON_IDENTIFIABLE, tyre_historical:NON_IDENTIFIABLE, strategy:PRIOR_ONLY, ...}
```

### GET /races
Query: `season, circuit, driver, constructor, limit(1-200, default 50), offset`
Response: `{ races: [{race_id, season_id, round, circuit_id, race_date, total_laps, availability, unavailable}], total, limit, offset }`
Uses cached `data/canonical/races.json` metadata, not full dataset per request.

### GET /races/{race_id}
Response: `{race_id, season_id, round, circuit_id, race_date, total_laps, availability, unavailable, driver_count}`
404 `RACE_NOT_FOUND` if missing; 422 if path traversal.

### POST /simulate/race
Request `RaceSimulationRequest`:
```
race_id: str 1-100 (no path traversal)
seed: int32 nullable default 42
laps_override: 1-200 nullable
track_id: nullable (overrides inferred track)
enable_strategy, enable_setup, enable_weather, enable_race_control: bool (defaults: false,false,true,false)
save_replay: bool default true
```
Response `RaceSimulationResponse`:
```
simulation_id, race_id, seed, track_id, total_laps,
classification: [{position, driver_id, total_time, status, laps_completed, best_lap_time, points}],
lap_summary, incidents, strategy_summary, provenance, model_versions, evidence_tiers, warnings, reproducibility, events[0:200], runtime
```
Provenance includes dataset/model versions + evidence_tiers. Warnings for PRIOR_ONLY toggles. Reproducibility: same seed+race+config+versions = identical.

### POST /simulate/monte-carlo
Request `MonteCarloRequest` (same fields, simulations 1-5000 default 1000)
Response `MonteCarloResponse`:
```
simulation_id, race_id, N, simulations, seed,
win_probabilities: {driver_id: float},
podium_probabilities,
finish_position_distribution: {driver_id: {position: prob}},
dnf_statistics, expected_points, uncertainty, provenance, model_versions, evidence_tiers, runtime, reproducibility
```
Hard limits enforced via Pydantic (422 if out of range). Uses VectorizedMonteCarlo, no NDL tensors, CRN isolated streams.

### POST /strategy/evaluate
Request `StrategyEvaluateRequest { state: StrategyState dict (no future_*), track_pit_loss 0-60, seed }`
Response:
```
driver_id, lap, recommended_action, decision, target_compound, pit_window, candidate_actions, evaluations, uncertainty, confidence, evidence_tier, explanation, provenance
```
Leakage fields (`future*`, `observed_result`, `actual_*`) rejected 422/400.

### POST /scenario/compare
Request `ScenarioCompareRequest`:
```
race_id, interventions: [{family, op, target, parameter, value}] 1-20, seed, simulations 1-5000, laps, experiment_id, question
```
Validation via `scenario/registry.py` allowlist + `scenario/validation.py` + `registry.LEAKAGE_SUBSTRINGS`. Rejects `future_*`, `winner`, `final_position`, etc with 400 `UNSUPPORTED_INTERVENTION`.
Response:
```
experiment_id, race_id, seed, simulations, trace, comparison, attribution, crn_manifest, provenance, evidence, limitations, fingerprint, warnings
```
Comparison deltas = counterfactual - baseline. All tiers PRIOR_ONLY.

### GET /replay/{race_id}
Query: `seed, simulations 1-5000, laps, checkpoint (pre_race|lap_1|lap_5|...|finish or int)`
Response:
```
race_id, seed, simulations, laps, checkpoint, checkpoints, checkpoint_results, deviation_metrics, provenance, evidence_summary
```
If data missing, evidence_tiers show NON_IDENTIFIABLE; never fabricates. 404 if race not found.

### GET /simulation/{simulation_id}
Response:
```
simulation_id, status: queued|running|completed|failed, result: <stored payload>, created_at
```
In-memory only; 404 if not found.

## Reproducibility
Every simulation/monte-carlo/scenario response includes `reproducibility {seed, race_id, simulations, dataset_version, note}` and `provenance` with model versions. Same inputs → identical output within engine tolerance.

## OpenAPI
`/openapi.json` generated; each endpoint has summary, description, request/response schemas, error responses. See `/docs`.
