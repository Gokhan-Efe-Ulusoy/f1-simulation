# Experiment: exp-2024-bahrain-pit-shift5-n1000

## Question

Under the model assumptions and available evidence, how does the simulated finish distribution for max-verstappen change when his pit window shifts +5 laps ([20, 40] -> [25, 45])?

## Historical context (OBSERVED)

- Race: 2024-bahrain (OBSERVED identity from canonical dataset)
- Race date / as_of: 2024-03-02 / 2024-03-01T00:00:00Z
- Observed result is a post-hoc validation target only (OBSERVED, never a model input).

## Available evidence

- strategy: PRIOR_ONLY

## Baseline (SIMULATED from MODEL INPUT)

- Fingerprint: `4e46e11dee7fb4c0`
- N=1000, seed=42, laps=58

## Counterfactual (SIMULATED from MODEL INPUT + INTERVENTION)

- Fingerprint: `b6673fefccdbac8b`

## Intervention (MODEL INPUT)

- strategy.pit_laps [max-verstappen] SET_VALUE: model default (pits [20, 40]) -> [25, 45] (PRIOR_ONLY)

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
| max-verstappen | -0.0130 | -0.0070 | +0.0000 | +0.046 | +0.0000 | 0.0360 |
| leclerc | +0.0040 | +0.0010 | +0.0000 | -0.009 | +0.0000 | 0.0100 |
| norris | +0.0040 | +0.0030 | +0.0000 | -0.011 | +0.0000 | 0.0100 |
| hamilton | +0.0020 | +0.0030 | +0.0000 | -0.009 | +0.0000 | 0.0060 |
| russell | +0.0020 | +0.0000 | +0.0000 | -0.011 | +0.0000 | 0.0160 |
| piastri | +0.0010 | +0.0000 | +0.0000 | -0.005 | +0.0000 | 0.0080 |
| albon | +0.0000 | +0.0000 | +0.0000 | +0.000 | +0.0000 | 0.0000 |
| alonso | +0.0000 | +0.0000 | +0.0000 | +0.000 | +0.0000 | 0.0000 |

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

- Intervention: strategy.pit_laps: model default (pits [20, 40]) -> [25, 45]
- Direct: strategy: pit-lap schedule
- Downstream: tyre age resets at pit laps; pit-lane time loss (only when pit_loss_seconds explicitly enabled; 0 by default); degradation profile over the race; per-lap pace; race dynamics
- Final: max-verstappen: model-attributed dP(win)=-0.0130 (relative -0.035; base 0.3700 -> cf 0.3570), dE[finish]=+0.046, dP(DNF)=+0.0000, dP(top10)=+0.0000; leclerc: model-attributed dP(win)=+0.0040 (relative +0.036; base 0.1100 -> cf 0.1140), dE[finish]=-0.009, dP(DNF)=+0.0000, dP(top10)=+0.0000; norris: model-attributed dP(win)=+0.0040 (relative +0.024; base 0.1650 -> cf 0.1690), dE[finish]=-0.011, dP(DNF)=+0.0000, dP(top10)=+0.0000
- Model-attributed effect under the stated assumptions and available evidence; not a real-world causal claim.

## Sensitivity

- Method: one_factor_at_a_time over pit_laps (5 points).
  - pit_laps=[20, 40]: dP(win)=+0.0000, dE[finish]=+0.000, L1=0.0000
  - pit_laps=[22, 42]: dP(win)=+0.0030, dE[finish]=-0.006, L1=0.0100
  - pit_laps=[25, 45]: dP(win)=-0.0130, dE[finish]=+0.046, L1=0.0360
  - pit_laps=[28, 48]: dP(win)=-0.0240, dE[finish]=+0.093, L1=0.0560
  - pit_laps=[30, 50]: dP(win)=-0.0350, dE[finish]=+0.133, L1=0.0840

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

- Experiment fingerprint: `cb2084b52d37c69f`
- Artifact: `backend/data/simulation/experiments/experiment-2024-bahrain-*-cb2084b52d37c69f.json`
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
