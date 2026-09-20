# Phase 21 — Scenario Model

**Version:** `scenario-v1.0.0`, `MODEL_VERSION 0.8.0`, `SIMULATION_VERSION 9.1.0`, `raceengine-v2.1.0`
**Status:** Implemented in `backend/app/simulation/scenario/` (8 modules). Reuses Phase 14
`Scenario`/`ScenarioType` vocabulary and all domain engines; adds no new physics.

## 1. Architecture

```
simulation/scenario/
  __init__.py      # re-exports + SCENARIO_MODEL_VERSION
  models.py        # InterventionOp, InterventionFamily, Intervention,
                   # ScenarioSpec, InterventionTrace, DriverEffect,
                   # ScenarioComparison, ScenarioExplanation, ScenarioResult
  registry.py      # allowlists, bounds refs, tiers, pathways, era/leakage rules
  validation.py    # validate_intervention / validate_spec / check_spec
  compiler.py      # compile_spec (immutable), fingerprints, build_branch_specs
  resolvers.py     # resolve_pit_schedule, resolve_pace_deltas (vectorized use)
  comparison.py    # compare_results (deltas + L1/quantile distances)
  engine.py        # ScenarioEngine (CRN execution), build_explanation
```

Supporting changes (all additive, default-identical):
- `simulation/performance/vectorized_montecarlo.py` — pit/compound schedule
  matrices + performance pace deltas (zero/absent when unmodified).
- `simulation/race_engine_v21.py` — `ScenarioAwareRaceEngine`, thin provenance
  layer over v20 (no dynamics change).
- `simulation/version.py` — `MODEL_VERSION 0.8.0`, `SIMULATION_VERSION 9.1.0`,
  `RACEENGINE_VERSION raceengine-v2.1.0`, `SCENARIO_MODEL_VERSION scenario-v1.0.0`.

## 2. Core concepts

- **Baseline**: an existing `Scenario` (usually historical, `as_of` = race_date − 1 day).
  Never mutated: the compiler deep-copies; engines receive copies.
- **Intervention**: `{family, op, target, parameter, value}` + reason; validated
  before execution; baseline value resolved at compile time for the trace.
- **Counterfactual**: compiled `Scenario` (type set from the spec) run through the
  SAME engine with the SAME seed (common random numbers).
- **ScenarioSpec**: `{spec_id, baseline_scenario_id, scenario_type, interventions[]
  (ordered), seed, simulations}` — serializable, fingerprinted.
- **ScenarioResult**: `{spec_id, fingerprints, trace, comparison, explanation,
  provenance}` — references engine outputs, duplicates nothing.

Scenario types reuse Phase 14: `historical | counterfactual | hypothetical | future`.

## 3. Intervention vocabulary (only what is implemented)

Ops: `SET_VALUE | ADD_DELTA | MULTIPLY | ENABLE | DISABLE` (per-family subset
enforced; see `phase21_intervention_types.md`).

Families (all with verified propagation paths):
`setup` (18 Phase 20 params) · `strategy` (`pit_laps`) · `tyre`
(`starting_compound`, `pit_compound`, `stints`) · `race_control` (7 flags +
2 thresholds) · `weather` (10 initial-state fields + enable) ·
`driver`/`car` (`pace_delta`, model interventions).

Explicitly NOT families: strategy policies (`policy`, candidate controls),
forced RC events (`force_safety_car_lap`, …), stint tables outside the
`{compound, laps}` form, championship/standings/result fields (leakage
blocklist), structural scenario fields. These are rejected with exact messages.

## 4. Scenario overrides (engine-consumed contract)

```python
hypothetical_modifiers["setup"]   = {"enabled": True, "parameters": {...}, "drivers": {id: {...}}}
hypothetical_modifiers["weather"] = {"rainfall_mm_h": 8.0, ...} | {"enabled": False}
hypothetical_modifiers["race_control"] = {"enabled": False, "enable_vsc": False,
                                          "wetness_red_flag_threshold": 0.9, ...}
hypothetical_modifiers["tyre"]    = {"starting_compound": {"VER": "MEDIUM"},
                                     "stints": {"all": [{compound, laps}, ...]}}
hypothetical_modifiers["strategy"] = {"pit_laps": {"VER": [24]}}
hypothetical_modifiers["performance"] = {"driver_pace_delta": {...},
                                         "constructor_pace_delta": {...}}
```

Unknown top-level modifier keys are inert to every engine (verified by test);
the scenario layer additionally rejects unknown families/parameters at
validation time.

## 5. Serialization & fingerprint

`ScenarioSpec` / `Intervention` / results are pydantic models (`model_dump`
round-trips tested). Fingerprints: canonical JSON → sha256 → 16 hex.
- `baseline_fingerprint` = content hash of baseline scenario + versions.
- `spec/counterfactual fingerprint` = baseline hash + ordered interventions +
  versions + seed + simulations.
Any parameter change alters the fingerprint; identical inputs reproduce it.

## 6. Provenance

Every `ScenarioResult` records: `baseline_scenario_id`, scenario type, both
fingerprints, ordered trace (family/op/target/parameter, baseline →
counterfactual, modifier path, pathways, tier), seed, simulations, warnings,
and full version map. Engine results additionally carry per-family blocks
(`setup_model`, `race_control`, `weather`, `setup`, `scenario_model`).
