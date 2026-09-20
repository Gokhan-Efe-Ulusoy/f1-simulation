# Phase 29 — Validation

## Determinism

- Same request+seed → identical content (see `phase29_determinism.md`). Verified via API/service/direct engine equivalence.

## Leakage

- `tests/test_phase29_execution.py::test_leakage_future_result_rejected` etc. — 0 violations.
- API-level adversarial: `future_weather`, `future_result`, `observed_result`, `actual_*`, `realized`, `final_position`, `championship`, `standing` rejected via `ScenarioCompareRequest` validator + `scenario/validation.py` `LEAKAGE_SUBSTRINGS` + `STRUCTURAL_FIELDS`. Tested with aliases, nested objects, extra fields, alternate capitalization (lowercase check `param.lower()`).
- Strategy leakage: `future_pit`, `future_*` in `StrategyState` rejected 422.

## Regression

- Direct engine behavior unchanged (thin orchestration only). `test_backward_compat_default_path_reproduces_legacy` passes (default modifiers path identical to legacy).
- Existing tests: `tests/test_phase28_api.py` 26/26, `tests/test_phase29_execution.py` 36/36, `tests/test_race_engine.py` 13/13, `tests/test_random_provider.py` 7/7 pass.

## Error Model

- `RACE_NOT_FOUND` (404), `SIMULATION_LIMIT_EXCEEDED` (400/422), `UNSUPPORTED_INTERVENTION` (400), `INVALID_SEED` (400), `INVALID_LAP_RANGE` (400), `DATA_NOT_AVAILABLE` (404 for unknown simulation), `VALIDATION_ERROR` (422) — all verified via `test_malformed_*`, `test_unknown_simulation_id`.

## Persistence

- `test_persistent_storage`: POST race → GET `/simulation/{id}` retrieves same classification via DB (or memory fallback).
- `test_serialization_round_trip`: serialize→persist→retrieve preserves result.
- DB round-trip verified via `SimulationRecord` JSON string storage; `result_hash` stable.

## Modifier Handling

- `test_modifier_weather_provenance_only`, `test_modifier_setup_provenance_only` — warnings contain PRIOR_ONLY, not silently upgraded.
- `test_modifier_montecarlo_weather_disable` — evidence_tiers weather DISABLED when requested.

## OpenAPI

- `GET /openapi.json` 10 paths (health, metadata, races, race detail, simulate race, monte-carlo, strategy, scenario, replay, simulation) each with summary/description/schemas.
