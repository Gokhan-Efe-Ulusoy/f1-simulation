# Experiment: exp-2024-bahrain-wet-rain10-n1000

## Question

Under the model assumptions and available evidence, how does the simulated finish distribution change when the race starts wet (rainfall 10 mm/h) instead of dry? Historical weather is NON_IDENTIFIABLE; timed rain onset is NOT_TESTABLE in this model.

## Historical context (OBSERVED)

- Race: 2024-bahrain (OBSERVED identity from canonical dataset)
- Race date / as_of: 2024-03-02 / 2024-03-01T00:00:00Z
- Observed result is a post-hoc validation target only (OBSERVED, never a model input).

## Available evidence

- weather: PRIOR_ONLY

## Baseline (SIMULATED from MODEL INPUT)

- Fingerprint: `4e46e11dee7fb4c0`
- N=1000, seed=42, laps=58

## Counterfactual (SIMULATED from MODEL INPUT + INTERVENTION)

- Fingerprint: `e171bc3da33e937c`

## Intervention (MODEL INPUT)

- weather.rainfall_mm_h [race] SET_VALUE: 0.0 -> 10.0 (PRIOR_ONLY)

## Assumptions (MODEL ASSUMPTION)

- Baseline setup is the neutral Phase 20 baseline (historical setups unknown).
- Pit stops carry no time loss unless pit_loss_seconds is explicitly enabled.
- All effect tiers are PRIOR_ONLY unless stated; Monte Carlo never upgrades tiers.
- Model-attributed effects are not real-world causal claims.

## Simulation configuration

- CRN: baseline_seed=42, counterfactual_seed=42, same_seed=True
- Streams: same seed / sim index / isolated exogenous streams (see stream manifest in artifact).

## Results (SIMULATED)

| driver | dP(win) | dP(podium) | dP(top10) | dE[finish] | dP(DNF) | L1 |
|---|---|---|---|---|---|---|
| russell | +0.0230 | +0.0140 | +0.0020 | -0.055 | +0.0000 | 0.1060 |
| max-verstappen | -0.0180 | -0.0020 | +0.0000 | +0.032 | +0.0000 | 0.0780 |
| leclerc | -0.0120 | +0.0050 | +0.0000 | -0.009 | +0.0000 | 0.0720 |
| piastri | +0.0050 | +0.0210 | +0.0050 | -0.049 | +0.0000 | 0.0620 |
| sainz | +0.0020 | +0.0070 | +0.0010 | -0.066 | +0.0000 | 0.0460 |
| gasly | +0.0010 | +0.0030 | -0.0100 | +0.085 | +0.0000 | 0.0580 |
| albon | -0.0010 | -0.0010 | -0.0070 | +0.091 | +0.0000 | 0.0960 |
| alonso | +0.0000 | -0.0030 | -0.0130 | +0.053 | +0.0000 | 0.0900 |

### Distribution comparison notes

- Deltas are counterfactual minus baseline under common random numbers (same seed); residual Monte Carlo noise scales ~1/sqrt(N).
- Relative win deltas are None when the baseline probability is zero (division undefined); absolute deltas always reported.
- No significance testing is performed; no causal identification claimed.
- Mean/total lap-time and degradation-trace contrasts are NOT_TESTABLE: the engine emits finish distributions, not lap-time aggregates.

### Unmeasurable (honestly qualified)

- mean_lap_time: NOT_TESTABLE
- pit_stop_time_loss_observed: NON_IDENTIFIABLE
- position_trajectory: NOT_TESTABLE
- total_race_time: NOT_TESTABLE
- tyre_degradation_trace: NOT_TESTABLE

## Attribution (MODEL-ATTRIBUTED, not causal)

- Intervention: weather.rainfall_mm_h: 0.0 -> 10.0
- Direct: weather: initial weather state override
- Downstream: weather trajectories (shared across drivers); grip / per-lap pace (+ tyre environment, + race-control coupling); race dynamics
- Final: russell: model-attributed dP(win)=+0.0230 (relative +0.397; base 0.0580 -> cf 0.0810), dE[finish]=-0.055, dP(DNF)=+0.0000, dP(top10)=+0.0020; max-verstappen: model-attributed dP(win)=-0.0180 (relative -0.046; base 0.3900 -> cf 0.3720), dE[finish]=+0.032, dP(DNF)=+0.0000, dP(top10)=+0.0000; leclerc: model-attributed dP(win)=-0.0120 (relative -0.112; base 0.1070 -> cf 0.0950), dE[finish]=-0.009, dP(DNF)=+0.0000, dP(top10)=+0.0000
- Model-attributed effect under the stated assumptions and available evidence; not a real-world causal claim.

## Sensitivity

- Method: one_factor_at_a_time over rainfall_mm_h (5 points).
  - rainfall_mm_h=0.0: dP(win)=+0.0000, dE[finish]=+0.000, L1=0.0000
  - rainfall_mm_h=5.0: dP(win)=+0.0070, dE[finish]=+0.015, L1=0.0840
  - rainfall_mm_h=10.0: dP(win)=+0.0230, dE[finish]=-0.055, L1=0.1060
  - rainfall_mm_h=15.0: dP(win)=+0.0150, dE[finish]=-0.074, L1=0.1180
  - rainfall_mm_h=20.0: dP(win)=+0.0170, dE[finish]=-0.073, L1=0.1360

## Uncertainty

- Monte Carlo granularity ~0.0010 per probability point; treat sub-granularity deltas as noise.
- No p-values or significance claims (no justified test implemented).

## Limitations

- Baseline setup is the neutral Phase 20 baseline (historical setups unknown).
- Pit stops carry no time loss unless pit_loss_seconds is explicitly enabled.
- All effect tiers are PRIOR_ONLY unless stated; Monte Carlo never upgrades tiers.
- Model-attributed effects are not real-world causal claims.
- NON_IDENTIFIABLE quantities (historical weather/setup/fuel/strategy/tyre) were never substituted with fabricated values.

## Reproducibility

- Experiment fingerprint: `430f99aeb0db2e85`
- Artifact: `backend/data/simulation/experiments/experiment-2024-bahrain-*-430f99aeb0db2e85.json`
- Re-run from artifact metadata: same race_id + spec + seed + N + versions.

### Versions

- CALIBRATION_VERSION: 
- CONFIG_VERSION: 1.0.0
- COUNTERFACTUAL_MODEL_VERSION: counterfactual-v1.0.0
- DATASET_VERSION: 
- MODEL_VERSION: 0.9.0
- RACEENGINE_VERSION: raceengine-v2.2.0
- RACE_CONTROL_MODEL_VERSION: racecontrol-v1.0.0
- RACE_CONTROL_POLICY_VERSION: racecontrol-policy-v1.0.0
- REPLAY_MODEL_VERSION: replay-v1.0.0
- SCENARIO_MODEL_VERSION: scenario-v1.0.0
- SENSITIVITY_MODEL_VERSION: sensitivity-v1.0.0
- SETUP_MODEL_VERSION: setup-v1.0.0
- SIMULATION_VERSION: 9.2.0
- STRATEGY_MODEL_VERSION: strategy-v1.1.0
- WEATHER_CALIBRATION_VERSION: weather-calibration-v1.0.0
- WEATHER_MODEL_VERSION: weather-v1.0.0
