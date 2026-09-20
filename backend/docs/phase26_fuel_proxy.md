# Phase 26 Fuel Proxy Definition

Generated 2026-09-20T17:45:00+00:00

## Status

```
FUEL_PROGRESSION_PROXY = PROXY_ONLY
EVIDENCE_TIER = PROXY_ONLY
IS_FUEL_LOAD = false
```

This is NOT fuel load. The proxy represents observable race progression that is correlated with fuel burn. Do NOT claim "lap 1 = X kg fuel" or "fuel burns Y kg/lap" unless supported by actual evidence. No fabricated kg values.

## Variables

Candidate variables considered, all observable without future information, respecting as_of = race_date -1 day strict_before:

1. normalized_lap = lap_number / max_lap_per_race
   - Range 0-1 per race, computed from max_lap_per_race observed per race_id via OpenF1 laps, not from future schedule
   - Monotonic with fuel burn (fuel decreases as lap increases) but also correlated with track evolution, tyre age reset, race control
   - Sample 88404 valid laps, mean 0.52 std 0.29

2. lap_number
   - Absolute lap count 1..78 (Monaco 78, Spa 44 etc), directly from canonical laps_openf1
   - Major progression proxy, correlation with tyre_age 0.497 Pearson 0.502 Spearman globally
   - Controlled in Models B, E, F, G, H

3. stint_lap = lap_number - lap_start + 1
   - Lap within current stint 1..~60, derived from exact stint join, highly correlated with tyre_age 0.983 Pearson 0.984 Spearman globally
   - Useful for within-stint analysis but nearly collinear with tyre_age, separation NON_IDENTIFIABLE when both in model

4. race_progress = normalized_lap (alias for clarity)
   - Same as normalized_lap, represents fraction of race completed, inverse proxy for remaining fuel fraction
   - Correlation with tyre_age 0.495 Pearson

5. remaining_laps = max_lap_per_race - lap_number
   - Decreasing proxy, correlated -0.96 with lap_number, not independent, used only as alternative specification check

6. race_phase categorical {early, mid, late} terciles of normalized_lap <0.33, 0.33-0.66, >0.66
   - Piecewise progression, less parametric, captures non-linear fuel + track evolution + strategy phase
   - Used in Model H as categorical control with hierarchical handling, n early 29300 mid 29500 late 29500 approx

All variables are EVIDENCE_TIER PROXY_ONLY. No kg mapping.

## Proxy Definition String (for fingerprint)

```
proxy_definition = "normalized_lap, lap_number, stint_lap, race_progress, remaining_laps, race_phase"
```

Changing proxy definition or calibration inputs must change fingerprint via sha256.

## How Not to Use

ABSOLUTE RULE: Do NOT implement fuel_kg = starting_fuel - lap * burn_rate unless actual starting_fuel and burn_rate evidence exists. Do NOT create fake fuel_remaining, fuel_mass, fuel_load. Do NOT calibrate kg/lap from arbitrary assumptions (e.g., 1.8 kg/lap simulation parameter is forward-simulation assumption, not observed measurement, and is NOT used to fabricate historical fuel per lap).

Simulation-internal fuel_mass in app/simulation/core/state.py and strategy/fuel.py remains simulation-internal, not historical evidence. FuelStrategyOptimizer base_fuel_consumption 1.8 is a prior for forward simulation, not a measurement claim.

## Usage in Models

Models A-H use proxies as progression controls:
- A lapse alone (baseline)
- B + lap_number
- C + stint_lap
- D + normalized_race_progress
- E + lap_number + circuit
- F + lap_number + circuit + driver
- G + lap_number + circuit + driver + constructor
- H + lap_number + circuit + driver + constructor + race_phase

No model treats proxy as kg. Coefficients reported as seconds per lap progression unit, not per kg.

## Provenance

- Dataset f1-dataset-v1.3, tyre_join-v1.0.0 seed 42, circuit-v1.0.0-candidate, as_of race_date -1 day strict_before
- Proxy variables derived solely from observable lap_number, max_lap, stint boundaries, not from future information
- Artifact hashes: phase26_decomposition.json fingerprint 8-char sha256 via proxy definition + dataset + seed

## Classification

FUEL_PROXY evidence_tier PROXY_ONLY, FUEL_TYRE_SEPARATION = NON_IDENTIFIABLE (see identifiability doc), tyre degradation remains ASSOCIATIONAL not causal.

