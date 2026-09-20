# Phase 16 Performance

**Engine:** `raceengine-v1.2.0` (tyre-aware, vectorized)  
**Baseline:** `raceengine-v1.1.0` (vectorized, no tyre) — both <30s, tyre adds small overhead

## Benchmarks (2024-bahrain, 20 drivers)

| Simulations | Laps | Baseline (s) | Tyre (s) | Speedup | Sim/s (tyre) |
|---|---|---|---|---|---|
| 1,000 | 5 | 2.07 | 0.18 | 11.05x | 5335 |
| 10,000 | 5 | 1.70 | 1.69 | 1.00x | 5888 |
| 1,000 | 58 | 0.30 | 0.28 | 1.09x | 3527 |
| 10,000 | 58 | 2.70 | 2.73 | 0.99x | 3659 |

**Note:** 5 laps 1k baseline 2.07s vs tyre 0.18s is 11x due to caching (first run includes calibration load). For 10k, both ~1.7s, tyre overhead negligible.

**Target:** `10k × 58 <30s` — **PASS** (2.73s). Stretch `<10s` — **PASS**. `<5s` — **PASS** (2.73s).

**Memory:** Same as Phase 15 (<200 MB, no N×D×L).

**Vectorized tyre:** `(N,D)` arrays for `compound, age, grip`, kernels `update_tyre_age`, `tyre_effect` via Numba, no Python loops.

**Conclusion:** Tyre integration adds <5% overhead, preserves Phase 15 performance.
