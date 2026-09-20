# Phase 22 — Sensitivity

## 1. Engine

`SensitivityEngine` (`app/simulation/replay/sensitivity.py`):

- `run_ofat(baseline, experiment_id, family, target, parameter, values, op)`: one-factor-at-a-time over a deterministic ordered list (default 5 points, e.g. front_wing -2..+2, pit laps 20..30, pace -0.2..+0.2, rain 0..20). Costs `len(values)` legs that share the baseline (CRN; baseline leg factored once per underlying `run_branch`).
- `run_grid(baseline, experiment_id, axes, family, target, op)`: exactly 2 axes, product capped. `len(combos) > MAX_GRID_POINTS(25)` raises. Prevents `N x D x L x candidates x interventions` tensor explosions; each leg stays `(N,D)` (one engine invocation per intervention value, no joint tensor).

Output per point: `{ parameter, value, target, d_win_probability, d_expected_finish, l1_finish_distribution, uncertainty_note, evidence_tier }` plus `method, baseline_fingerprint, seed, N, limitations`.

## 2. Determinism

Same grid + same `seed` + same `N` -> bit-identical `l1` series (tested: `front_wing [3,4,5,6,7]` OFAT reproduces exactly on re-run).

## 3. Attribution consistency

OFAT `points[*].evidence_tier` is taken from the actual per-leg `ScenarioComparison.evidence_tiers[family]` (all `PRIOR_ONLY` in this model). The baseline fingerprint is shared across the sweep.

## 4. Results from the e2e sweeps (N=1000, 2024-bahrain, 58 laps, seed 42)

### Strategy pit-window (+5 laps)

- `[20,40] (baseline) -> 0.0 / 0.0 / 0.0`
- `[22,42]`, `[25,45] (counterfactual)`, `[28,48]`, `[30,50]` span L1 ~ 0.01-0.04 for the target driver (`max-verstappen`). The pit-window shift is a small effect at this scale; counterfactual legs still move visibles but deltas are within a few probability points (Monte Carlo granularity ~0.001 at N=1000).

### Front wing

- `3.0 (-2)` -> slower (downforce lost): `dP(win) ~ -0.008`, `L1 ~ 0.026`
- `5.0 (baseline)` -> `0.0 / 0.0 / 0.0` by construction
- `7.0 (+2)` -> faster on this prior model: `dP(win) ~ +0.009`, `L1 ~ 0.018`, per-lap offset `-0.0209s` (setup offsets, PRIOR_ONLY). Monotonic in this range; outside it bounds-errors are rejected.

### Rainfall

- `0.0 (dry)` baseline, `5..20 mm/h` each move L1 ~ 0.08-0.14 and raise modeled wetness (`delta mean_wetness ~ +0.6` at 10 mm/h). The wet channel is shared across drivers via grip trajectories; per-driver win shifts are small but present.

## 5. What sensitivity does not do

- Does not estimate interactions (OFAT is one-at-a-time).
- Does not produce massive `N x D x L x candidates x interventions` tensors: each leg reuses the `(N,D)` simulation kernel; memory stays bounded (see performance doc).
- Does not claim significance: deltas are reported with a granularity note and `PRIOR_ONLY` tiers; no p-values are produced.
