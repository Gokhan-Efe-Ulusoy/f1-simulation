# Phase 29 — Determinism

## Guarantee

Same `race_id` + `seed` + `N` + `laps` + `modifiers` + `interventions` + `engine_version` + `model_version` + `dataset_version` → identical simulation content (within defined tolerance).

## Tests

- `test_deterministic_reproducibility_race`: `POST /simulate/race` bahrain laps5 seed42 twice → classification identical, same request_hash.
- `test_deterministic_reproducibility_montecarlo`: `POST /simulate/monte-carlo` bahrain seed42 N20 twice → win/podium identical.
- `test_different_seed_different_result`: seed 42 vs 43 → classification differ.
- `test_api_service_engine_equivalence_race`: API vs direct `simulation_service.simulate_single_race` same classification.
- `test_api_service_engine_equivalence_montecarlo`: API vs direct `montecarlo_service.run_montecarlo` same win probabilities.
- `test_backward_compat_default_path_reproduces_legacy`: default modifiers path reproduces legacy RaceEngine result.

## DB Persistence Does Not Alter Result

`test_serialization_round_trip`: POST race → GET `/simulation/{id}` → `result.classification` equals original; `result_hash` stable; JSON round-trip via `json.dumps(payload, default=str)` preserves.

## RNG Isolation

`test_rng_isolation`: `RandomProvider(seed=42).get_stream("strategy")` independent from `get_stream("weather")`; advancing one does not affect the other (hash-based stream seed `hash((seed,name)) & 0xFFFFFFFF`).

`test_rng_isolation_strategy_ar1`: `strategy_rng(42,0,1)` same seed/sim/lap → same first value; strategy offset 700, AR1 100, race_control 600+ streams unchanged; API/service/persistence never call `random` (IDs via `uuid`, hashes via `hashlib`).

## Coverage

- Race, Monte Carlo, scenario, strategy where applicable.
- All via `tests/test_phase29_execution.py` (36 tests) + `tests/test_phase28_api.py` (26 tests) + `tests/test_random_provider.py`.
