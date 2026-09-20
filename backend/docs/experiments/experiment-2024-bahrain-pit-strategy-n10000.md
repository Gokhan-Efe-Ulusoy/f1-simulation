# Experiment: exp-2024-bahrain-pit-shift5-n10000

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
- N=10000, seed=42, laps=58

## Counterfactual (SIMULATED from MODEL INPUT + INTERVENTION)

- Fingerprint: `62db0228363c18bf`

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
| max-verstappen | -0.0107 | -0.0106 | +0.0000 | +0.040 | +0.0000 | 0.0248 |
| norris | +0.0035 | +0.0021 | +0.0000 | -0.008 | +0.0000 | 0.0082 |
| hamilton | +0.0034 | +0.0023 | +0.0000 | -0.008 | +0.0000 | 0.0076 |
| leclerc | +0.0025 | +0.0022 | +0.0000 | -0.008 | +0.0000 | 0.0068 |
| russell | +0.0011 | +0.0027 | +0.0000 | -0.008 | +0.0000 | 0.0054 |
| piastri | +0.0002 | +0.0011 | +0.0000 | -0.006 | +0.0000 | 0.0040 |
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
- Final: max-verstappen: model-attributed dP(win)=-0.0107 (relative -0.028; base 0.3872 -> cf 0.3765), dE[finish]=+0.040, dP(DNF)=+0.0000, dP(top10)=+0.0000; norris: model-attributed dP(win)=+0.0035 (relative +0.022; base 0.1627 -> cf 0.1662), dE[finish]=-0.008, dP(DNF)=+0.0000, dP(top10)=+0.0000; hamilton: model-attributed dP(win)=+0.0034 (relative +0.014; base 0.2511 -> cf 0.2545), dE[finish]=-0.008, dP(DNF)=+0.0000, dP(top10)=+0.0000
- Model-attributed effect under the stated assumptions and available evidence; not a real-world causal claim.

## Sensitivity

- (no sensitivity sweep attached)

## Uncertainty

- Monte Carlo granularity ~0.0001 per probability point; treat sub-granularity deltas as noise.
- No p-values or significance claims (no justified test implemented).

## Limitations

- Baseline setup is the neutral Phase 20 baseline (historical setups unknown).
- Pit stops carry no time loss unless pit_loss_seconds is explicitly enabled.
- All effect tiers are PRIOR_ONLY unless stated; Monte Carlo never upgrades tiers.
- Model-attributed effects are not real-world causal claims.
- NON_IDENTIFIABLE quantities (historical weather/setup/fuel/strategy/tyre) were never substituted with fabricated values.

## Reproducibility

- Experiment fingerprint: `297d784078085a9b`
- Artifact: `backend/data/simulation/experiments/experiment-2024-bahrain-*-297d784078085a9b.json`
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
