# Phase 22 — Physical Sanity Checks

`app/simulation/replay/sanity.py` and `tests/test_phase22_sanity.py`. All checks perturb **one** mechanism in a fixed direction, compare two legs under CRN, and pass only if the simulated finish distribution moves **and** moves in the physically expected direction (within a Monte Carlo tolerance `tol=0.75` on expected finish, which accommodates N=60 noise at ~1.5 std on this circuit/prior). Where the model has no mechanism, the check returns `NOT_TESTABLE` or `NON_IDENTIFIABLE` instead of fabricating a pass.

## 1. Results (2024-bahrain, 6 laps, N=60, seed 42, same seed across the pair)

| Check | Status | Detail |
|---|---|---|
| `pit_loss_monotonic` | PASS | `E[finish]` at `loss=5s: 5.083` vs `loss=30s: 9.317`, delta `+4.233` (higher loss must not systematically improve; `delta >= -0.75`). Legs moved: true. |
| `extra_stop_cost` | PASS | Extra stop free `E=3.933` vs costly `24.4s: 8.667`, delta `+4.733`. |
| `pace_monotonic` | PASS | Pace `-1 (fast) 3.633` vs `+1 (slow) 4.700`, delta `-1.067` (faster must not be worse). |
| `aero_grip_monotonic` | PASS | Ride height `15mm 3.883` vs `25mm 4.250`, delta `-0.367` (lower = more downforce/less drag must not be slower). PRIOR_ONLY coefficients. |
| `wet_weather_effect` | PASS | `delta mean_wetness +0.1832` (> 0) and at least one finish distribution moved. |
| `tyre_compound_effect` | PASS | `SOFT->MEDIUM` moved finish distributions. |

All 6/6 PASS. At `N=60` the tolerance `0.75` is needed: smaller N introduces Monte Carlo scatter in expected finishes of order `~0.3-0.5`; the sanity assertion is monotonicity in expectation, not per-sample ordering.

## 2. Pit-stop time loss investigation (Phase 21 blocker)

Phase 21: "pit-stop time loss not fully modeled" — extra stops showed tyre-freshness benefit only.

Phase 22 resolution: added `strategy.pit_loss_seconds` channel (see `scenario/registry.PIT_LOSS_*`, `scenario/validation`, `scenario/compiler._apply_strategy`, `scenario/resolvers.resolve_pit_loss`, `performance/vectorized_montecarlo._pit_loss_vec/_pit_loss_active`). Mechanics:

- Modifier form: `hypothetical_modifiers.strategy.pit_loss_seconds` scalar or `{"all": x, driver_id: y}`. Default `0.0` -> vectorized path **unchanged** (legacy exact); explicitly set to e.g. `24.4` -> a deterministic per-stop cost `+24.4s` on each scheduled pit lap to that driver's cumulative time (DNF drivers excluded). No new RNG: cost is a fixed additive offset; exogenous streams are untouched (CRN intact).
- Reference value `PIT_LOSS_PRIOR_REFERENCE_SECONDS = 24.4 = 22.0 (pit_lane_drive_through_time) + 2.4 (stationary_base_time)` is the mean of the repository's own `PitStopModel` prior (`simulation/models/strategy.PitStopModel`). Tier is `PRIOR_ONLY` (no calibrated timing exists at per-race resolution in the canonical dataset), recorded in `VectorizedMonteCarlo` result blocks as `pit_loss.evidence_tier = PRIOR_ONLY`.
- Baseline equivalence: with `pit_loss_seconds` absent/zero the new engine is numerically identical to `v2.1.0` on all tested short legs (`1e-12`).
- Propagation: `sanity.check_pit_loss_monotonic` and `check_extra_stop_cost` demonstrate the costly leg is now slower and moves the finish distribution; `comparison.py` surfaces `race_effects.pit_loss` and `ExtendedComparison.pit_counts.delta` for drift accounting.

## 3. What is NOT_TESTABLE here

- Detailed pit-lane time loss variance / slow-stop issues / wheel-nut delays: the deterministic channel adds the mean only; per-stop noise is not modelled (would require a new stochastic stream and calibration).
- Sector-resolved aero vs mechanical decomposition beyond lap-time total: only the `total` offset is consumed by the lap loop; component contributions are prior-only diagnostics.

## 4. Implementation notes

- Pit-loss addition is after `batch.times += lap_times` and before `gaps_compression_kernel`, so field-compression still correctly applies on safety-car laps to pit loss as well.
- Per-driver tailoring is orthogonal to the schedule (`pit_laps`): `resolve_pit_schedule` and `resolve_pit_loss` are independent and compose.
