# Phase 20 Setup Data & Evidence Audit

**Date:** 2026-09-17. **Scope:** what the repository actually contains about
vehicle setup; what is calibrated, derived, prior-only, or non-identifiable.

## 1. Dataset contents (verified)

- `backend/data/canonical/`: races, results, drivers, constructors, circuits —
  NO per-race setup fields (no front/rear wing, ride height, suspension,
  brake bias, differential, camber, toe, tyre pressure).
- `Car` model has `setup_range` (adjustment ranges) and `get_setup_sensitivity`
  (UI sensitivities) — design placeholders, not measurements.
- `Track` model has aero/tyre/braking/energy descriptors used by
  `get_track_modifiers` — statistical characteristics, not setup observations.
- Tyre calibration (`tyre/calibration.py`): SOFT/HARD betas from 2024 Bahrain
  FastF1; MEDIUM prior-only; warmup/cliff NON_IDENTIFIABLE (per Phase 19).

## 2. Statement (mandatory)

> **Historical setup values are not identifiable from the current dataset.**

No values are reconstructed from finishing position, lap time, qualifying,
team reputation, or circuit type. Historical mode uses the neutral baseline
and labels it as such.

## 3. Evidence tiers per parameter

| Parameter | Tier | Basis |
|---|---|---|
| front_wing, rear_wing | PRIOR_ONLY | sign + scale from aero prior; no empirical fit |
| ride_height_front/rear | PRIOR_ONLY | ground-effect direction prior |
| front/rear_anti_roll, front/rear_spring | PRIOR_ONLY | stiffness/response prior |
| brake_bias | PRIOR_ONLY | stability-distribution prior |
| diff_entry/mid/exit | PRIOR_ONLY | traction prior, weak |
| front/rear_camber, front/rear_toe | PRIOR_ONLY | grip-vs-wear tradeoff prior |
| tyre_pressure_front/rear | NON_IDENTIFIABLE | confounded with temperature/compound; no data |

## 4. Evidence tiers per effect

| Effect | Tier | Notes |
|---|---|---|
| downforce / drag / aero balance | PRIOR_ONLY | distinct (not identical); scale O(full sweep ≈ 1s) is a prior |
| cornering / traction / braking / compliance | PRIOR_ONLY | ordering plausible, magnitudes not fitted |
| tyre load / degradation / warmup | NON_IDENTIFIABLE | direction only; excluded from strong claims |
| track interaction | PRIOR_ONLY | derived from existing `Track` descriptors; `get_track_type_category` NOT used (its high/low labels are inverted for Monza/Monaco) |
| lap-time mapping | PRIOR_ONLY | linear prior; no calibration; broad uncertainty |

## 5. What is NOT claimed

No `CALIBRATED` or `LIMITED` setup coefficients exist in Phase 20.
No "optimal setup", "validated", "realistic", or "accurate" claims are made.
No optimal-setup finder is implemented (deferred to Phase 24).

## 6. Calibration path (future)

When per-team setup sheets or controlled test data become available with
`as_of` timestamps: fit per-parameter coefficients hierarchically per
circuit, record source/sample-size/date in `ParameterEvidence`, promote tier
to LIMITED/CALIBRATED per the Phase 11 identifiability rules. API needs no
redesign (`SetupCoefficients` is injectable).
