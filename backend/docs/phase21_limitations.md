# Phase 21 — Limitations (explicit, binding)

## 1. Not implemented (rejected, not faked)

- Strategy *policies* (DecisionEngine candidates/aggressiveness): the
  vectorized path ignores the decision engine, so policy interventions cannot
  propagate. Only fixed pit-lap schedules are supported.
- Forced/scripted race-control events (SC at lap X, red-flag timing,
  restarts): no mechanism exists.
- Championship-level, multi-race, regulation (Phase 22), sensitivity sweeps
  and optimization (Phase 24), natural-language scenario interface.

## 2. Model simplifications that shape every result

- Pit stops cost **no time** in the vectorized model; extra stops show only
  tyre-freshness benefit. Every affected explanation states this.
- Setup coefficients are prior-only; magnitudes are order-of-magnitude.
- Tyre compound effects use calibrated betas where available, priors
  otherwise; warmup/cliff dynamics are non-identifiable (Phase 16–20).
- Weather/RC mechanisms are prior-only; override states are ESTIMATED.
- Small-N sequential fallback (N<50) does not apply setup/pit/compound/pace
  interventions (documented Phase 20 limitation class).
- Pre-2023 eras: pit/compound interventions are recorded but pace-inert.
- Pace deltas are additive mean shifts (±3 cap), not identified driver traits.

## 3. What must not be claimed

`production-ready`, `scientifically proven`, `fully accurate`, `optimal`,
`best`, `validated`, `realistic` — none apply. Counterfactual deltas are
model-implied (prior-only) contrasts under common random numbers.

## 4. Future work (Phases 22–24)

Richer scenario DSL (stint tables with pit-loss, conditional/weather-triggered
stops) · regulation interventions via Phase 22 engine · championship-level
counterfactuals · Phase 24 sensitivity/optimization built on the discrete
perturbation surface (`create_setup_from_dict` ± deltas, pit-lap grids).
