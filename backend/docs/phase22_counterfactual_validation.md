# Phase 22 — Counterfactual Validation

## 1. Model

One controlled intervention on an otherwise identical simulation, executed under **Common Random Numbers** (same `seed`, same per-simulation streams, same exogenous weather/race-control trajectories, same initial state). The difference is the intervention; all other model components remain identical.

Where scientifically appropriate, unrelated RNG streams remain unchanged (verified).

## 2. Intervention families (all tested to actually propagate at N=60, CRN, 2024-bahrain)

- `setup.*` -> `setup/offsets.py` per-driver seconds-per-lap -> outcome (PRIOR_ONLY)
- `strategy.pit_laps` -> schedule matrices / tyre age resets -> outcome
- `strategy.pit_loss_seconds` -> deterministic per-stop time cost on each scheduled pit lap -> outcome (PRIOR_ONLY prior mean 24.4s = pit_lane 22.0 + stationary 2.4)
- `tyre.*` (starting_compound / pit_compound / stints) -> compound matrices / calibrated betas -> outcome
- `race_control` flags/thresholds -> `RaceControlEngine.generate_batch` -> outcome
- `weather.*` -> `WeatherEngine` initial-state override -> wetness/grip trajectories -> outcome
- `driver/car pace_delta` -> calibration means -> base_pace sampling -> outcome

Rejected by validation (never silently passed): unknown parameters, out-of-range values, `future_*` / `actual_*` / `realized*` / `winner` / structural fields.

## 3. Baseline preservation

With all replay/counterfactual/sensitivity legs disabled and `pit_loss_seconds` at its default `0.0`, `race_engine_v22` reproduces `race_engine_v21` within `1e-12` on all tested short horizons (verified in `test_phase22_counterfactual.py::test_pit_loss_disabled_baseline_equivalence`). Any unexpected outer-provenance difference (e.g. dataset hash drift) is stamped separately and does not affect dynamics.

## 4. What changed scheme

- **Direct**: the model namespace the compiler wrote (e.g. `hypothetical_modifiers.strategy.pit_laps`, `setup.drivers.VER.front_wing`, `strategy.pit_loss_seconds`).
- **Downstream**: declared pathway steps between the direct and final nodes (from `PATHWAYS`, e.g. `pit-lap schedule -> tyre age resets -> degradation profile -> per-lap pace`).
- **Final**: measured distribution contrasts (win/podium/top10/expected finish/DNF) under CRN.

Language is **model-attributed effect**, never a claim about what happened in reality.

## 5. Validation posture

- The objective is NOT to force exact historical reproduction. `DeviationMetrics` reports predicted vs observed winner, top-3 overlap, finish MAE, DNF mismatch, and coverage metadata post-hoc; the model may diverge and does.
- Small-N sequential fallback (`N<50`) skips setup/pit/pace offsets in the vectorized path; all Phase 22 tests and e2e experiments use `N>=60` so offsets apply.
- Determinism: `same seed -> same result`, different seeds diverge, batch partitions are N-invariant, branch runs leave the baseline dump-identical, CRN legs share the baseline leg exactly.
