# Phase 27 Lap-Time Decomposition

Conceptual equation:
```
observed_lap_time = circuit_baseline + driver_effect + constructor_effect + tyre_effect + race_progression_effect + neutralisation_effect + pit_context + weather_effect + residual_error
```
Only include component if data supports identification. Fuel NOT as independent production feature; progression is RACE_PROGRESSION_ASSOCIATIONAL.

## Decomposition Implementation
`app/simulation/laptime/decomposition.py` class `LapTimeDecomposition` with fit order: circuit -> driver -> constructor -> progression -> tyre (monotonic) -> pit -> weather -> race_control -> residual. Only fitted if identifiable tier not NON_IDENTIFIABLE.

## Fitted Tiers (Phase27)
- circuit: LIMITED (global 91.35s, 36 circuits hierarchical tau30/50)
- driver: LIMITED (hierarchical n>=500 CALIBRATED else LIMITED)
- constructor: LIMITED (but note NON_IDENTIFIABLE for <30 laps driver-constructor confounding, status LIMITED because 3+ calibrated, else would be NON_IDENTIFIABLE)
- progression: RACE_PROGRESSION_ASSOCIATIONAL (NOT fuel, beta -6.53s per normalized race progress)
- tyre: NON_IDENTIFIABLE (unconstrained -0.309 constrained 0.0, monotonic fails)
- pit: LIMITED (mean 23.2s median 23.1s total, lane/stationary NON_IDENTIFIABLE)
- weather: PRIOR_ONLY (wet 0 in filtered set, dry 88616, insufficient n<50)
- race_control: PRIOR_ONLY (GREEN CALIBRATED n85288, YELLOW CALIBRATED 3263, RED LIMITED 66, SC/VSC 0 -> PRIOR_ONLY)
- fuel: NON_IDENTIFIABLE (actual fuel not available)
- Identifiable: circuit, driver, constructor (limited), progression associational, pit
- Non_identifiable: tyre, fuel, weather, race_control where sparse

## Coefficients
- Circuit: global 91.35, era means varying, per-circuit shrunk e.g., monaco ~92.x, spielberg ~88, se 0.05-0.6, evidence LIMITED
- Driver: global 0, per driver shrunk -1.2 to +1.5 sec, e.g., driver 1 -0.307 shrunk, se 0.02-0.15, tier LIMITED
- Constructor: per constructor n 30-4000, raw -0.5 to +0.5, shrunk, LIMITED where n<300 else CALIBRATED, but overall LIMITED
- Progression: progression_specs A-E show tyre beta stability: A -0.291, C -0.211, D -0.213, E -0.213, progression beta itself -6.53 per normalized progress (fuel+tyre+traffic combined)
- Tyre: compound effects hard +0.11 medium +0.03 soft -0.55, unconstrained -0.309 constrained 0.0
- Pit: mean 23.2 median 23.1
- Weather: wet insufficient
- Race control: GREEN mean 90.85, YELLOW 103.2, RED 152.47

## Residual
Total residual var after circuit+driver+progression: still 100+ variance per group, dominant UNEXPLAINED_RESIDUAL where no variable identifiable, do not invent explanations.

## Provenance
Dataset f1-dataset-v1.3 hash 2cce529c, calibration phase27-laptime-decomposition-v1.0.0-candidate, model 0.9.0, features circuit_baseline etc, as_of race_date -1 day, training 2023-2026 valid laps, seed 42, fingerprint 93fc8d68.

