# Phase 32 — API ↔ Frontend Contract

Frontend sends exactly backend-schema fields (verified in `schemas.py`):

- `RaceSimulationRequest`: race_id, seed int32, laps_override 1..200, track_id, enable_strategy/setup/weather/race_control, save_replay, priority 0..100.
- `MonteCarloRequest`: + simulations 1..5000, chunk_size 1..5000.
- Responses consumed: classification, win/podium_probabilities, finish_position_distribution, provenance, evidence_tiers, warnings, reproducibility, request_hash/result_hash, status/progress/current_stage, poll_url.
- Errors: `{error:{code,message}}` mapped to UI states (NETWORK_ERROR, VALIDATION_ERROR 422, 404, 429 QUEUE_FULL, 500, TIMEOUT). No stack traces shown.
- Backend changes in Phase 32: NONE to schemas/services/engine. Only added `tests/test_phase32_contract.py` (12 tests). Frontend config fix: `jest.config.js` ts-jest `jsx: react-jsx` + `setupFilesAfterEnv` (pre-existing breakage, documented below).
