# Phase 20 Setup Validation

## 1. Test inventory (38 tests, `tests/test_phase20_setup.py`)

- Models (8): parameter creation, 18 defaults, evidence tiers,
  state creation/serialization, fingerprint deterministic/change/verify,
  dict construction.
- Validator (5): valid passes, out-of-bounds caught, rake warning,
  track warnings, clamp-then-valid, era constraints.
- Coefficients (2): existence, physical signs (wing↑→downforce↑drag↑;
  lower RH→downforce↑; camber↑→grip↑wear↑; pressure↑→wear↓).
- Engine (5): baseline ≈ 0, high/low wing directions, track ordering
  (Monza straight > Monaco; Monaco low-speed > Monza), apply_to_car,
  evidence summary.
- Lap integration (2): setup-aware model moves total; delta breakdown keys.
- Evidence (2): enum completeness, summary counts.
- Ablation (1): disabled vs enabled-baseline valid + provenance flags.
- Vectorized integration (2): baseline preserves legacy exactly (N=60,
  1e-12); per-driver change moves expected_finish, changes fingerprints,
  repeats deterministically (N=100).
- Counterfactual/sensitivity (2): effect directions; perturb changes
  fingerprint + deviation.
- Determinism (2): effects repeat; fingerprints reproduce.
- Leakage (2): historical = baseline + limitations; counterfactual labeled.
- Provenance (2): factory provenance; scenario-modifier round-trip.
- Performance (1): 1000 effect computations < 1s.

## 2. Backward compatibility

- Full prior suite: 489 tests pass (2 version-gate tests widened to accept
  `0.7.0 / 9.0.0 / raceengine-v2.0.0` alongside prior values; no test weakened
  in logic).
- New suite: 38 tests pass. Total 527.
- Legacy equivalence: setup-disabled vs setup-baseline win probabilities
  identical to 1e-12 at N=60 (offsets exactly 0, no RNG touched).

## 3. Leakage (adversarial)

- Historical mode never reads future setup/race/weather/RC/pit/strategy:
  only baseline + `as_of`-free priors; `SetupState.as_of` carried for
  Phase 21 gating.
- Counterfactual setups require explicit `mode: counterfactual` and appear
  in fingerprints/provenance as interventions, never as observations.
- Strategy receives no setup fields (verified by code inspection).

## 4. Determinism / fingerprint

- Same seed + same setup → identical win probabilities (1e-12).
- `rear_wing 7→8` changes fingerprint; identical config reproduces it.
- Fingerprint payload excludes timestamps/seeds/provenance.

## 5. Ablation matrix

| Toggle | Effect |
|---|---|
| setup OFF | offsets `{}`, legacy win probs |
| setup ON, baseline | offsets `{}`, legacy win probs, fingerprints present |
| aero only (high wing) | downforce↑ drag↑, lap delta via aero |
| mechanical only (stiff ARB) | stiffness↑, lap delta via mechanical |
| per-driver (one car lower RH) | that driver's expected_finish improves |
| tyre interaction | computed but NON_IDENTIFIABLE; weak by design |

Every pathway that claims an effect was observed to move its output;
`strategy ← setup` is the documented exception (not wired).

## 6. Physical sanity (only tested where implemented)

- More rear wing → downforce↑ and drag↑ (tested at effect level).
- Invalid brake bias / negative pressure → rejected by validator.
- NOT tested (not implemented): "wing X always wins Monaco" or any
  circuit-optimality claim.

## 7. Performance (measured, Bahrain, 8 laps, seed 42)

- N=1000: legacy-v19 12.88s (cold fastf1 cache) / v20-disabled 8.78s /
  v20-baseline 8.88s / v20-modified 8.90s → setup overhead ≈1%.
- Memory: per-driver offsets `(D,)` + fingerprints; no `(N,D,L,P)` tensors.
- N=10,000 not re-timed here; Phase 19 baseline 77–85s applies (same kernels
  + one broadcast add per lap).
