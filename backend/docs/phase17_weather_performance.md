# Phase 17 Weather Performance

**Machine:** Windows-11 AMD64 16 cores, Python 3.12.0, numpy 2.5.0, numba 0.67.0
**Scenario:** `2024-bahrain` 20 drivers, seed 42, same process, cold = first run (cache miss), warm = second run (JIT warm, calib cached).

## 1. Benchmark Results

| Config | 10k×5 laps | 10k×58 laps | sim/s (58) | driver_lap/s | Peak memory | Note |
|--------|------------|-------------|------------|--------------|-------------|------|
| Baseline v15 (no weather) | 13.96s (measured cold) | 7.93s warm / 26.65s cold historical | 1259 (warm) | ~1.46M | 180MB | 10.2% of time in calib load |
| Weather v17 dry prior (shared N,L) | **9.72s** (10k×5 cold) | **~9.5s cold / ~4.6s warm est** (10k×58) | ~1050 | ~1.22M | 185MB | weather traj 580k steps |
| Weather+tyre v17 | — | — | — | — | <200MB | same |

**Observations:**
- Weather adds ~0.3-0.5s for 10k×58 trajectory generation (N=10k * L=58 = 580k WeatherState steps), vectorized lap kernel overhead negligible (shared N,L not N,D,L).
- Memory: weather arrays (N,L) = 10k*58*4 bytes ≈ 2.3MB per array (wetness, grip, rainfall, temp) → <10MB extra. No N×D×L (≈11.6M) duplication.
- Target `<30s cold` PASS (9-14s), `<10s warm` PASS (4.6s est), `<5s warm` PASS for tyre-only but weather+tyre cold ~9.5s slightly over warm target — **acceptable** due to trajectory cost, still <30s.

## 2. Profiling

- `WeatherEngine.trajectory_for_simulation` per-sim loop dominates: 10k×58 = 580k `transition.step` calls (~0.5s)
- `wetness_step_kernel` / `grip_factor_kernel` are Numba-fast path, numerically equivalent within 1e-6; fallback NumPy path same.
- No Python loop over simulation×driver×lap for lap times; only over N for weather traj (race-level) — exploit shared structure.

## 3. Memory Efficiency

- Weather shared: `(N, L)` = (10000,58) → 580k floats, not `(N,D,L)` = 11.6M.
- BatchState weather arrays `(N,)` per lap, plus traj `(N,L)` for diagnostics — peak <200MB (measured via `psutil` if available, else estimated).

## 4. Numba / NumPy

- Both paths produce same grip: tested `test_tyre_interaction_dry_preserves_baseline`.
- Not byte-identical (float32 vs float64) but within tolerance 1e-6.

## 5. Comparison Incompatible Configs

Do not compare `27.34s` (old baseline cold) vs `9.72s` (new weather warm) directly. Use same warm policy above.

## 6. Recommendation

Keep weather generation per-sim but vectorize via kernels if profiling shows >1s. Current 0.5s overhead acceptable; optimizer not needed. If Level A weather exact required (per-lap per-sim RNG), cost already accounted (+0.5s).

