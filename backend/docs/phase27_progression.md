# Phase 27 Race-Progression Effect

## Family
- lap_number_normalized (lap/max per race)
- race_progress (alias normalized)
- remaining_laps (max - lap)
- stint_lap

Explicitly distinguish observed progression association from physical fuel effect.

## Never call this fuel calibration.

### Specifications Tested
- A: lap progression only (tyre_age + normalized_lap) beta tyre -0.291
- B: circuit + progression (circuit + tyre_age + normalized) tyre -0.211
- C: circuit + driver + progression tyre -0.213
- D: circuit + driver + constructor + progression tyre -0.213
- E: circuit + driver + constructor + tyre + progression (same as D, full) tyre -0.213
- Also progression only (lap_time ~ normalized) beta -6.534 s per normalized progress (i.e., -0.109 per lap for 60 lap race), includes fuel+tyre+traffic

### Coefficient Stability
- Tyre beta changes substantially between specs: -0.291 (A) -> -0.211 (C) change 27%, and vs bare tyre only -0.309 -> -0.167 when controlling lap_number earlier 45% change
- Progression coefficient itself stable -6.5 but its meaning is associational not causal
- If progression coefficient changes substantially between specifications, report confounding: YES, tyre and progression confounding strong, progression absorbs multiple correlated effects

### Tier
- RACE_PROGRESSION_ASSOCIATIONAL, not FUEL_EFFECT
- Associational stable but not causal fuel, do NOT promote as fuel calibration

