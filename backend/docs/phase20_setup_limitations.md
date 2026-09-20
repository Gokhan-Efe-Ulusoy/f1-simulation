# Phase 20 Setup Limitations & Non-Claims

## 1. Explicitly NOT implemented

- **No calibrated coefficients.** Every numeric mapping is PRIOR_ONLY or
  NON_IDENTIFIABLE. Nothing was fitted to data in Phase 20.
- **No optimal-setup finder.** Systematic search/sensitivity belongs to
  Phase 24; not built here.
- **No strategy consumption of setup.** `DecisionEngine` ignores setup;
  wiring it without evidence would be fake integration.
- **No sector-level setup effects.** Sector descriptors exist on `Track`
  but no sector-specific setup path was added.
- **No regulation engine.** Bounds are MODEL_PHYSICAL; era minima are coarse.
  Full technical rules are Phase 22.
- **No small-N fallback offsets.** `MonteCarloRunner` (N<50,
  `race_engine_v14.LapSimulator`) ignores setup; vectorized path (N≥50)
  applies it. Setup tests therefore use N≥50.
- **No automatic differentiation.** Perturbation API is discrete
  (`create_setup_from_dict` with ±deltas); Phase 24 can build on it.

## 2. Known weaknesses

- Lap-time scale is a prior: full sweep ≈ O(0.5–1s) chosen for plausibility,
  not measured. Treat magnitudes as order-of-magnitude only.
- Aero/mechanical/tyre contributions are linear and additive; real
  interactions (e.g. wing×ride-height coupling, balance windows, cliffs)
  are absent.
- Track modifiers use straight/sector sums, corner shares, energies —
  reasonable but unvalidated; `Track` defaults (e.g. 2.5km straight) can
  inflate short tracks when sector data is missing (mitigated by preferring
  sector sums).
- Per-driver setups share one global `SetupEngine`/coefficients; no
  team-specific aero maps.
- `apply_to_car` clamps to 0–100; extreme setups saturate silently
  (validator warns first).

## 3. Temporal / leakage boundaries

- Historical setups are UNKNOWN (baseline used, labeled).
- `as_of` is carried but not yet enforced against setup calibration
  (there is no setup calibration to leak from — enforcement comes with
  Phase 21 data).
- Future-mode setups are pure model scenarios (`HYPOTHETICAL`/`FUTURE`).

## 4. What must NOT be claimed

`validated`, `realistic`, `accurate`, `scientifically proven`, `optimal`,
`best setup` — none of these apply to Phase 20 outputs. Reports must say
"model-implied (prior-only)" when describing counterfactual deltas.

## 5. Future research (Phases 21–24)

- Phase 21: counterfactual runner using `offsets.py` + `SetupState` pairs
  (baseline vs intervention) with what/why/how-much/uncertainty reporting.
- Phase 22: regulatory constraints per era replacing coarse minima.
- Phase 23: season-level setup development (upgrade tokens) — needs data.
- Phase 24: discrete sensitivity sweeps → surrogate gradients; needs
  calibrated magnitudes first, else sensitivity of a prior is just
  sensitivity of an assumption (report as such).
