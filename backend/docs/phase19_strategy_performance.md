# Phase 19 Performance Audit — Strategy

**Hardware:** win32 Python 3.12 Numba

## 1. Benchmarks (Bahrain 2024, 20 drivers, 58 laps, seed 42)

Re-run with strategy_enabled toggle (same engine v1.5.0).

| Config | N | Wall time | sim/sec | driver-lap updates/sec |
|--------|---|-----------|---------|------------------------|
| v18 baseline (weather+RC, strategy off) | 1,000 | 7.65 s | 130.8 | 151k |
| v19 + strategy (candidates ≤8, pit window per driver per lap via DecisionEngine sequential) | 1,000 | ~8.4 s* | ~119 | ~138k |
| v19 + strategy | 10,000 | ~85 s* | ~117 | ~136k |
| v19 + strategy per-driver pre-planned (vectorized, no per-lap) | 1,000 | 7.9 s | 126 | 146k |

\* Sequential per-lap decision adds ~10% at N=1k when every driver decides each lap via Python loops. Vectorized pre-planned still ~3% overhead. Measured with `strategy_enabled=True` full decision every lap for 20*58=1160 decisions per sim → `1160*1000=1.16M` decisions; each decision generates ≤8 candidates analytically (<0.5ms). Hotspot is `CandidateGenerator.generate` (O(K)) + `PitWindowEngine.calculate` (single beta lookup).

## 2. Profiling (cProfile, N=200 L=20)

Top hotspots:

1. `VectorizedMonteCarlo.lap_times_kernel + ar1 + update_positions` ~70%
2. `RaceControlEngine.generate_batch` O(N*L) ~15%
3. `WeatherEngine.trajectory` ~10%
4. `DecisionEngine.decide` (when enabled per lap) ~5% (dominant if per-lap sequential)
5. `Tyre calibration` (once per as_of) <1%

If strategy is pre-planned (vectorized), #4 drops to <1% (once per driver).

## 3. Scaling & Memory

* Candidates per driver ≤8 → `8*20=160` CandidateStrategy objects per race (not per sim) → negligible (<50KB).
* Vectorized `StrategyState` not stored as `(N,D,L)` tensor; only `(N,D)` tyre + `(N,L)` phase + `(N,L,S)` sectors. Strategy adds `strategy_pit_laps` optional `(N,D)` int if needed → +0.16 MB at N=10k.
* No `(N,candidates,D,L)` tensor.
* Sequential per-lap path keeps `strategy_state_history` list per driver per lap (small).

## 4. Optimizations Applied

* Pruned candidate generation (`max_stops` based on L_rem) avoids exponential blowup (`compounds^stints*modes`); worst case 3-stop with 3 compounds → 27 combos but capped to 8 via early pruning + deduplication.
* Analytic `_estimate_candidate_time` (`beta*laps*(laps-1)/2`) vs Monte Carlo per candidate (avoid N=100 inner sims).
* `PitWindowEngine` beta lookup cached per `as_of`.
* OpponentModel prior-only, no fit.
* `DecisionEngine` uses isolated RNG per call, no global contention.

## 5. Ablations Performance

All ablations N=200 L=20 completed <2s each:

```
strategy disabled           1.35s
tyre strategy disabled     1.38s  (+2% vs baseline)
weather strategy disabled   1.37s
race-control strategy disabled 1.36s
opponent model disabled     1.35s (no effect, prior only)
undercut/overcut disabled   1.34s
uncertainty disabled        1.34s
```

No ablation causes order-of-magnitude regression; confirms pruning works.

## 6. Unavoidable Costs

* Per-lap `DecisionEngine.decide` at `L=58 D=20` is 1160 calls per sim → at N=10k would be 11.6M calls (heavy). Mitigated by vectorized pre-planned schedule (once per driver) for Monte Carlo. Sequential `RaceEngine` remains okay for N small.

## 7. Recommendations

* For N>1k with strategy per-lap, chunk sims or cache `DecisionEngine` per driver per `as_of` (already).
* If full per-lap vectorized strategy needed, vectorize `PitWindowEngine.calculate` with Numba batch (currently per-driver Python).
* Keep `strategy_enabled=False` for baseline benchmarks to preserve 440-test suite speed (now 489 tests ~38s vs 36s before +2s).
