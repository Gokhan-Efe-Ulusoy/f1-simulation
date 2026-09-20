# Phase 20 Setup Integration — Call Paths

All paths verified against code; only paths that exist are listed.

## 1. Setup → vehicle effects → lap time (sequential / analytical)

```
SetupState
  → SetupEngine.compute_effects(setup, car, track) → SetupEffects
  → SetupEngine.compute_lap_time_delta(effects, base, track)
      {aero, mechanical, tyre, total} seconds
  → SetupEngine.apply_to_car(car, effects) → adjusted Car
  → SetupAwareLapTimeModel.calculate_lap_time_with_setup(inputs, setup)
      = parent lap time, total × (1 + setup_delta)
      (setup_delta folded into car_delta; schema unchanged)
```

Used by: unit/physics tests, `compute_setup_lap_time_delta` analysis,
`create_setup_aware_inputs` (adjusted-Car + attached effects).
`core/lap_simulator.py` is NOT modified (lineage preserved); the
setup-aware model is available for Phase 21+ sequential rollouts.

## 2. Setup → vectorized Monte Carlo (production path, N≥50)

```
Scenario.hypothetical_modifiers["setup"]
  {enabled, mode, parameters (global), drivers.{id} (per-driver override)}
  → setup/offsets.py: setup_offsets_for_scenario(scenario)
      per-driver seconds-per-lap (deterministic, validated + clamped)
  → VectorizedMonteCarlo.run: lap_times += setup_vec  (broadcast (N,D)+(D,))
  → drivers win/podorium/expected_finish move when offsets ≠ 0
```

Shapes: static `(D,)` broadcast — never `(N,D,L,P)`. Per-lap cost is one
broadcast add. No RNG consumed.

## 3. Setup → race engine → provenance/fingerprint

```
SetupAwareRaceEngine.simulate(scenario, simulations, seed)
  → resolve setup_enabled (engine flag + scenario override)
  → super().simulate (strategy → race control → weather → tyre → vectorized)
  → attach: provenance.setup_model_version / setup_enabled /
      setup_evidence_tier / setup_fingerprints (per-driver)
  → setup_model {version, enabled, evidence_tier,
      offsets_sec_per_lap, fingerprints, vectorized}
```

Changing any parameter changes `setup_fingerprint` (16-hex) and hence
`provenance.setup_fingerprints`; changing offsets changes win probabilities.

## 4. Setup → strategy (Phase 19 interface)

Strategy (`DecisionEngine`) does NOT consume setup state in Phase 20.
`setup_model.offsets` and tyre-degradation tendencies are exposed in the
result for future use. No hidden future setup is passed to strategy;
historical mode uses baseline only. Claiming strategy integration would be
fake — it is documented as NOT_AVAILABLE (see limitations).

## 5. Setup → race control / weather / tyre models

No direct edges. Setup affects lap pace; race control, weather, and tyre
trajectories evolve independently (isolated RNG streams). Interaction is
emergent through race dynamics only, per spec §18/§17/§16.

## 6. Scenario modifiers contract

```python
hypothetical_modifiers["setup"] = {
    "enabled": True,                 # False → legacy path, offsets {}
    "mode": "counterfactual",        # historical|counterfactual|hypothetical|future
    "parameters": {"rear_wing": 3},  # global to all drivers
    "drivers": {"VER": {"ride_height_front": 15.0}},  # per-driver override
}
```

Baseline (no `parameters`, no `drivers`) → offsets `{}` → legacy bit-identical.
Small-N fallback (`MonteCarloRunner`, N<50, `race_engine_v14.LapSimulator`)
does NOT apply offsets — documented limitation; setup tests use N≥50.
