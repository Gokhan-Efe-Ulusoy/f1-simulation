# Phase 22 — Limitations (explicit, binding)

## 1. Not implemented (rejected, not faked)

- Timed weather scripting (rain onset at lap X, storm evolution): the model supports only initial-state overrides (`weather.rainfall_mm_h` etc.). Asking for "rain begins earlier" is honestly answered as "wet initial state only".
- Scripted race-control events (SC on lap X, red-flag timing, multi-restart scripting): only flag/timeout policy thresholds are honoured.
- Championship-level multi-race, regulation, natural-language scenario interface: out of scope (deferred to Phases 22-24 architecture notes; not claimed).
- Detailed pit-lane variance / slow-stop issues / wheel-nut delays: the pit-loss channel is a deterministic mean; stochastic pit-stop failures remain hypothetical.
- Lap-time / degradation-trace aggregates: the engine emits finish distributions, not lap-time series, so mean-lap-time/total-time contrasts are `NOT_TESTABLE` (explicitly reported).

## 2. Model simplifications that shape every result

- Pit stops carry **no time loss by default**; a cost is applied only when `strategy.pit_loss_seconds` is explicitly enabled. Documents state this, and costed vs free legs are measured in sanity checks. The prior mean `24.4s = 22.0 (pit_lane) + 2.4 (stationary)` is `PRIOR_ONLY`, not calibrated on per-race timing data (none exists at this granularity).
- Setup coefficients are `PRIOR_ONLY`; magnitudes are order-of-magnitude (full-wing sweep ~0.02s/lap on a ~90s baseline; `front_wing 5.0->7.0` is `-0.0209s/lap`).
- Tyre betas are calibrated where 2024 FastF1 exists, `PRIOR_ONLY` otherwise; warmup/cliff are `NON_IDENTIFIABLE`.
- Weather/RC mechanisms are `PRIOR_ONLY`; starting states are explicit priors.
- Small-N sequential fallback (`N<50`) does not apply setup/pit/pace interventions; all e2e experiments use `N>=60`/`N=1000`/`N=10000` so propagation is real. The walk-forward sample is shortened to 8 laps for cost, not full 58.
- Pre-2023 eras: pit/compound interventions are recorded in provenance but pace-inert.
- Pace deltas are additive mean shifts (cap +-3), not identified driver traits.
- Total_laps is `NON_IDENTIFIABLE` for at least `2024-bahrain` (`scheduled_laps=null`); 58-lap legs document this fallback.

## 3. What must not be claimed

`production-ready`, `scientifically proven`, `fully accurate`, `optimal`, `best`, `validated`, `realistic`, `causal`, `historically accurate` - none apply. Counterfactual deltas are model-implied (`PRIOR_ONLY`) contrasts under CRN.

## 4. Future work (Phases 23-24)

Richer DSL (stint tables with pit-loss + conditional/weather-triggered stops), regulation interventions, championship-level counterfactuals, optimization built on the discrete perturbation surface already present, and a nightly 1950-present walk-forward sweep at `N=60 x 58 laps` (currently deferred due to runtime) with Bayesian aggregation of per-race `finish_mae` into era-conditioned error bars.
