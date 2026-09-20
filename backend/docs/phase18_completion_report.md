# Phase 18 Completion Report — Race Control & Dynamic Event System

**Date:** 2026-09-17
**Model:** 0.5.0  **Simulation:** 8.4.0  **Engine:** raceengine-v1.4.0  **RaceControl:** racecontrol-v1.0.0 / policy-v1.0.0

## 1. Status

```
Dataset:             f1-dataset-v1.1 (races 2cce529c, results 112c8475, tyre 503079ee)
Calibration:         calibration-v1.0.0 driver 3df26222
Tyre:                tyre-v1.0.0 calibration-v1.0.0
Weather:             weather-v1.0.0 calibration-v1.0.0
Race Engine:         raceengine-v1.4.0
Race Control Model:  racecontrol-v1.0.0
Model Version:       0.5.0
Simulation Version:  8.4.0
Tests:               440 passed (398 baseline + 42 phase18)
Baseline Tests:      398 unchanged
Phase 18 Tests:      42 new (test_phase18_race_control.py)
Failures:            0
Skipped:             0
Leakage Violations:  0
RNG:                 isolated stream 600, deterministic, different-seed variation proven
Determinism:         N=10/100/1000/5000 same-seed identical True
Event Types Implemented: 22 (SPIN … CHEQUERED_FLAG, FORMATION_LAP, START)
State Machine:       explicit VALID_TRANSITIONS 12 states,  PRIORITY, invalid raises
Yellow:              sector-level (N,L,S) int8, 1.15/1.22, DRS disabled
VSC:                 1.25 uniform, rate 0.25, pit 0.55, duration 2-4
Safety Car:          1.35 uniform, rate 0.55 target 0.7, pit 0.35, duration 3-6
Red Flag:            frozen 0, preserve order/tyre/weather, RESTART or CHEQUERED
Restart:             1.05 pace, overtake 1.35, DRS locked 2 laps
Formation/Start:     phases FORMATION_LAP/START + existing Phase-8 models
Event Causality:     parent_event_id chain via EventQueue deterministic IDs
Weather Integration: wet*0.6 incident multiplier, Wetness->Policy->Phase, isolated
Tyre Integration:    tyre age continues under SC, grip via wetness prior, PRIOR_ONLY
Strategy Integration: sees current phase only, no future, leakage-safe
DRS Integration:     mask (N,L) GREEN only, restart lock 2
Overtaking Integration: factors 1.0/0.25/0.05/0.0/1.35
Monte Carlo:         (N,L) shared, (N,L,S) sectors, no (N,D,L)
Performance:         N=1k 7.65s (+2% vs v17), N=10k 77.6s (+1%), dl/s ~150k
Memory:              <5 MB overhead at N=10k
Ablation:            A disabled, B yellow only, C VSC, D SC, E red, F full, G weather off (see performance doc)
Historical Coverage: SC/VSC/YELLOW sector timeline NON_IDENTIFIABLE (no dataset), incident PIT prior, modern OpenF1 644 weather rows LIMITED
Evidence Tiers:      all new coefficients PRIOR_ONLY, pre-existing observed fields retain tiers
Blockers:            none
Documentation Debt:  none (4 docs written)
Limitations:         see §2 below
Future Research:     see §3 below
```

```
PHASE_18_STATUS = COMPLETE
```

## 2. Limitations (explicit)

* Incomplete historical flag timeline (1950-2024 flags NON_IDENTIFIABLE) — no empirical SC rate.
* Sector-level flag not observed; prior.
* Incident causality (wet multiplier 0.6) prior-only.
* Neutralisation tables prior-only, not calibrated.
* SC dynamics simplified (gap kernel not car-following).
* Restart DRS 2-lap lock prior approximation.
* Red-flag regulations abstraction (no parc fermé tyre change modelling).
* Formation lap not vectorized, per-driver still sequential path only.

## 3. Future Research

* Ingest `OpenF1 trackStatus & raceControl` 2023-2026 to estimate per-circuit `P(SC|incident)`, per-lap wet thresholds.
* Calibrate `pit_cost_factor` under SC via real pit data FastF1.
* Replace uniform SC pace with delta-time model using `reference_lap_time * circuit SC multiplier`.
* Model yellow sectors from telemetry `sector incident` events (Phase-8 `SectorIncidentEvent`).
* Add marshal intervention duration as separate event type with stochastic `duration` fitted.

## 4. Required Outputs Summary

```
Dataset: f1-dataset-v1.1
Calibration: calibration-v1.0.0
Tyre: tyre-v1.0.0
Weather: weather-v1.0.0
Race Engine: raceengine-v1.4.0
Race Control Model: racecontrol-v1.0.0
Model Version: 0.5.0
Simulation Version: 8.4.0
Tests: 440 passed 0 failed
Baseline Tests: 398
Phase 18 Tests: 42
Failures: 0
RNG: isolated 600, deterministic
Event Types: 22
State Machine: explicit 12 states
...
Blockers: none
```

## 5. Artifacts

* `app/simulation/race_control/*` (10 files)
* `app/simulation/performance/batch_state.py` (+ race_control fields)
* `app/simulation/performance/vectorized_montecarlo.py` (+ (N,L) phase generation, gap kernel, DRS mask)
* `app/simulation/core/state.py` (+ race_control_enabled flags default False for seq backward compat)
* `app/simulation/core/race_engine.py` (+ sequential RC handling, DRS gating, compression)
* `app/simulation/race_engine_v18.py`
* `app/simulation/version.py` bumped
* `tests/test_phase18_race_control.py` 42 tests
* `docs/phase18_*.md` ×4
