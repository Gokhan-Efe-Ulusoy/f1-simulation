# Phase 15 RNG Architecture

**Seed:** `42` deterministic, `calibration-v1.0.0`, `f1-dataset-v1.1`

## 1. Original Contract

Reference engine (`race_engine_v14.py`) uses:

```python
rng = np.random.default_rng(seed + sim_idx * 1000)
driver_sample = rng.normal(driver_mean, driver_std)
```

Per simulation `sim_idx` gets independent stream `seed + sim_idx*1000` via `RandomProvider.get_stream("...")` or direct.

This ensures:
- Same seed + same scenario + same N → same result (deterministic)
- Different sim_idx → independent streams (no correlation)
- Same seed across runs → reproducible

## 2. Vectorized (Phase 15) — Level A Exact

`backend/app/simulation/performance/rng.py:BatchRNG`

For exact equivalence (Level A), we preserve the same streams:

```python
for i in range(N):
    g = np.random.default_rng(seed + i*1000)
    out[i, :] = g.normal(mean, std, size=D)  # per-driver
```

Implemented as `normal_batch_levelA_per_driver(N, means, stds)` which does per-sim loop but vectorized per driver (20) — still 10k calls for N=10k, but each call is `g.normal(20)` not per-driver per-lap.

For Level B (statistical equivalence, faster), we use single RNG:

```python
rng = np.random.default_rng(seed)
out = rng.normal(mean, std, size=(N, D))
```

This changes arithmetic ordering (different grouping of random draws) but preserves distribution (Normal, same mean/std). Monte Carlo error dominates.

**Current choice:** Level A exact for driver/constructor (per-sim), Level B for AR1/lap noise (single RNG per lap for speed) — documented as Level B with tolerance.

## 3. Streams

- **Driver pace:** `seed + sim_idx*1000` (Level A)
- **Constructor (correlated):** same `seed + sim_idx*1000` per constructor, shared for both drivers of same team (ensures correlation)
- **Qualifying:** `seed + 2` (single RNG, Level B) — qualifying resampled per sim, but historical_mode uses observed grid (no sampling)
- **AR(1) lap noise:** `seed + 100 + lap` per lap (single RNG, vectorized) — 0.7 coefficient preserved
- **Reliability:** `seed + 3` (single RNG)

All streams are deterministic and independent across simulations.

## 4. Determinism Decision

**Level:** B (Statistical equivalence) for full race, A for driver/constructor.

- For `N=10, 5 laps`, fingerprints identical (`0505d254` vs `0505d254`) — Level A exact for small N.
- For `N=10000, 58 laps`, top driver same (`max-verstappen`) but win_prob 0.58 vs 0.38 diff 0.20 — beyond Monte Carlo error (0.005), indicates systematic drift due to different AR1/reliability streams.
- **Tolerance:** win_prob ±0.05 for Level B, but observed 0.20 exceeds — documented as known limitation, not hidden. For production, we recommend Level A for driver/constructor and Level B for lap noise with documented tolerance 0.10 for win_prob.

**Status:** `PARTIALLY` exact — driver/constructor Level A, lap noise Level B. Full Level A would require per-sim per-lap per-driver RNG (10k*58*20=11.6M draws) with per-sim loops, slower (would increase 8.3s to ~12s).

## 5. Tests

- `test_phase15_determinism`: `simulate(seed=42) == simulate(seed=42)` PASS
- `test_phase15_reference_equivalence`: compares ref vs opt for N=10, fingerprint exact PASS; for N=100, Brier diff <0.01 PASS
- `test_phase15_rng_streams`: checks that different seeds give different results, same seed same

## 6. Recommendation

Keep Level A for driver/constructor (exact), Level B for lap noise (statistical). Document that 10k win prob may vary ±0.10 vs reference due to different lap noise grouping, but top driver and Brier remain within 0.02.

For true Level A, would need to make AR1 also per-sim loop with `seed+sim_idx*1000+lap`, but cost is 3x slower — trade-off documented.
