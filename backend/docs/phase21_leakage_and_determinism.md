# Phase 21 — Leakage & Determinism

## 1. Leakage model

Counterfactuals are user-specified assumptions by design; leakage means
*realized future information entering through any other door*. Defenses:

1. **Strict allowlists** (`registry.py`): only 7 families / enumerated
   parameters compile. Result/standings/championship fields, `future_*`,
   `realized_*`, `observed_*`, and structural fields (`as_of`, `date`,
   `drivers`, `grid_order`, …) are rejected at validation with exact messages.
2. **Temporal gate**: spec rejected unless baseline `as_of` is strictly before
   race `date` (repo rule, `TemporalContext` policy).
3. **Unknown modifier keys are inert**: engines only read known namespaces.
   Adversarial tests hand-inject `future_result` / `realized_weather` blocks
   into compiled scenarios and assert bit-identical outputs (1e-12).
4. **No historical reconstruction**: baselines use neutral setup priors;
   nothing is inferred from finishing positions. `as_of` is never rewritten.
5. **Strategy sees no future**: pit/compound interventions are fixed schedules
   written before the run, not reactions to simulated events.

## 2. Determinism results (measured)

- Same spec + seed + versions → identical fingerprints and identical
  per-driver deltas (re-run equality, N=60).
- Same seed, N=10 (sequential) → identical win probabilities.
- Empty spec → all deltas exactly 0 (1e-12).
- Baseline object dump-identical before/after branch runs; post-branch
  baseline re-run reproduces cached baseline (1e-12).
- Different seed (42→43) → stochastic output differs (sanity: RNG alive).

## 3. RNG isolation (verified streams)

weather-500 · race_control-600 · strategy-700 · AR1-100 · driver/qualifying/
reliability base offsets. Scenario layer consumes **no RNG**: offsets,
schedules, pace shifts, fingerprints are deterministic transforms. Verified:
baseline legs of two different counterfactuals (same seed) are identical, so
an intervention perturbs no unrelated stream. Test: `test_rng_isolation_baseline_leg_stable`.

## 4. Fingerprint verification

- Different values (`rear_wing` 4.0 vs 5.0) → different fingerprints.
- Identical specs → identical fingerprints (16-hex canonical sha256).
- Baseline vs counterfactual fingerprints differ whenever interventions exist.
- Payload covers ordered interventions + versions + seed + simulations; no
  timestamps, no transient objects, no cycles.

## 5. Ablation

- Empty intervention list ≡ legacy behavior (deltas 0, provenance differs only
  by scenario block).
- Each family toggled independently moves its target distribution when the
  effect is non-zero; tyre-family on pre-2023 seasons is the documented
  no-effect case (warning emitted).
- Unsupported families (strategy policy, forced RC) are rejected, not
  zero-effect impostors.
