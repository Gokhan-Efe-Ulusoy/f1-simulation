# Phase 21 — Comparison & Explanation

## 1. Compared metrics (only what the engines produce)

Per driver: ΔP(win), ΔP(podium), ΔE[finish], Δmedian, ΔP(DNF), ΔE[points],
L1 distance on finish-position distribution, Δ quantiles (25/50/75 from the
discrete distribution). Per constructor: ΔP(win), ΔP(podium) (sums, as in the
engines). Race level: neutralization cell-count deltas that exist in results
(`vsc/sc/red/yellow/double_yellow/restart_count`), `mean/max_wetness`,
`mean_rainfall`, and applied setup offsets. No invented metrics.

## 2. Distances (deliberately narrow)

Mean/median/quantile differences + L1 on discrete finish distributions.
No KL (zero-probability hazards), no Wasserstein (unjustified machinery), no
significance tests. Notes attached to every comparison state the ~1/√N noise
scale and forbid causal reading.

## 3. Uncertainty reporting

Every explanation lists: N, seed, CRN status, Monte Carlo granularity
(~1/N per probability point — sub-granularity deltas are noise), per-family
evidence tiers, and the standing disclaimer:

> "Model-implied effect under the stated assumptions; not a causally
> identified empirical effect."

Counterfactual output never upgrades evidence tiers (all families PRIOR_ONLY
at effect level; weather override *states* are ESTIMATED, surfaced separately).

## 4. Explanation generation (no hallucination)

`build_explanation` assembles **only** from: the ordered trace (what, with
baseline→counterfactual values), the fixed per-family pathway map restricted
to families present in the trace (why — each pathway mirrors an implemented
code path), the top-3 |ΔP(win)| drivers (how much), compile warnings +
standing model assumptions (uncertainty/assumptions). There is no free-text
model and no mechanism vocabulary beyond `PATHWAYS`.

## 5. Causal language

Outputs say "under the model's assumptions, this intervention changes …".
Never "proves", "optimal", "validated", or "realistic". Phase 24 owns
sensitivity/optimization; Phase 21 is controlled intervention + comparison.
