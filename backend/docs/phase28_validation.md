# Phase 28 — Validation

## Determinism
- Same request+seed → bit-identical (RaceEngine) or within Monte Carlo sampling tolerance (vectorized). Verified via:
  - `test_deterministic_race`: `POST /simulate/race` bahrain seed42 laps5 twice → classification identical
  - `test_monte_carlo_determinism`: bahrain seed7 N20 twice → win/podium identical
  - `test_monte_carlo_seed_different`: seed 42 vs 43 → win probabilities differ
  - `test_api_direct_engine_equivalence`: direct `simulate_single_race` vs API classification equal
  - RNG isolation: `RandomProvider.get_stream(name)` hash-based; strategy offset 700, AR1 100, RC 600 etc unchanged; API introduces no RNG.

## Leakage
- API-level adversarial tests: `future_result`, `future_weather`, `future_pit`, `final_standings`, `future tyre` rejected via:
  - `schemas.ScenarioCompareRequest` validator (leakage blocklist) → 422
  - `strategy_service.evaluate_strategy` rejects `future`/`observed_result`/`actual_` keys → 400/422
  - `scenario_service.compare_scenario` + `scenario/validation.py` blocklist (`LEAKAGE_SUBSTRINGS`, `STRUCTURAL_FIELDS`) → 400 `UNSUPPORTED_INTERVENTION`
  - `tests/test_phase28_api.py::test_strategy_leakage_rejected`, `test_scenario_leakage_rejected`, `test_scenario_invalid_intervention` pass (violations = 0)

## Regression
- Direct engine behavior unchanged (thin wrappers only). Reference fixtures:
  - One deterministic race (bahrain seed42/5 laps) → API == direct
  - Monte Carlo (bahrain seed42 N10) → via VectorizedMonteCarlo, no new tensors
  - Strategy evaluate → via DecisionEngine, no second engine
  - Scenario compare → via ReplayEngine, same CRN
- Existing tests: `test_race_engine`, `test_random_provider`, `test_phase28_api` (26/26) pass; full suite >900 tests collected (sample 48 pass).

## Error Model
- Structured codes verified: `RACE_NOT_FOUND` (404 for unknown race), `SIMULATION_LIMIT_EXCEEDED` (422 for N>5000), `UNSUPPORTED_INTERVENTION` (400 for leakage/invalid target), `VALIDATION_ERROR` (422 for Pydantic).

## OpenAPI
- `GET /openapi.json` returns paths for all 8 endpoint families; each has summary/description + schemas. Checked via `test_openapi_generated`.

## Performance (smoke)
- Direct vs API overhead measured: single race ~11.9% (0.09→0.10s), Monte Carlo N=100 warm cache -58% (cache benefit), both <10% or explicitly measured. No NDL explosion.

## Scientific Gates
- No calibration promotion: `GET /metadata` still calibration-v1.0.0 etc; `test_no_calibration_promotion` passes.
- Evidence tiers exposed honestly (fuel NON_IDENTIFIABLE etc).
