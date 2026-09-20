# Phase 16.6 RNG Audit — Stochastic Call Graph

**Date:** 2026-09-10  
**Engines:** `race_engine_v14.py` (reference), `race_engine_v15.py`/`performance/vectorized_montecarlo.py` (optimized)  
**Seed:** `42`, `seed + sim_idx*1000` per simulation

## 1. Reference Engine (race_engine_v14.py + core)

| Component | File | RNG Call | Seed / Stream | Consumption | Determinism |
|---|---|---|---|---|---|
| **Master** | `core/random.py:RandomProvider` | `np.random.default_rng(seed)` | `seed=42` | 1 per RaceEngine | Yes |
| **Driver pace** | `race_engine_v14.py:RaceModel.sample_driver_performance` | `rng.normal(pace_val, pace_std)` | `seed+sim_idx*1000` per sim | `D` per sim (20) | Per-sim independent |
| **Constructor** | `RaceModel` | `rng.normal(val, 1.5)` per constructor | `seed+sim_idx*1000` | `C` per sim (10) | Correlated (shared) |
| **Qualifying** | `QualifyingModel` | `rng.normal(0,0.3)` | `seed+sim_idx*1000+2` | `D` per sim | Per-sim |
| **AR1 lap noise** | `LapSimulator` | `rng.normal(0,0.4)` per lap per driver + `0.7*prev` | `seed+sim_idx*1000+100+lap` | `D` per lap (20*58=1160) | Per-sim per-lap |
| **Reliability/DNF** | `RaceModel.sample_reliability` | `rng.random() < dnf_rate` | `seed+sim_idx*1000+3` | `D` per sim | Per-sim |
| **Incidents** | `LapSimulator` | `rng.random() < per_sector_p` | `get_stream("sector")` | Variable | Per-sim |
| **Safety car** | `RaceEngine._check_safety_car` | `rng.random() <0.02`, `rng.integers(3,6)` | `seed+sim_idx*1000` | Per lap | Per-sim |
| **Pit** | `LapSimulator` | `rng.normal(0,0.5)` for pit loss | `seed+sim_idx*1000` | Per pit | Per-sim |
| **Grid** | `RaceEngine._determine_grid_order` | `rng.normal(0,2)` | `seed+sim_idx*1000` | `D` | Per-sim |

**Total per simulation (20 drivers, 58 laps):** ~20 (driver) +10 (constr) +20 (qual) +1160 (AR1) +20 (DNF) + variable incidents = ~1230 draws, all via `seed+sim_idx*1000` hierarchy, **not shared**.

## 2. Optimized Engine (vectorized)

| Component | File | RNG Call | Seed | Level | Issue |
|---|---|---|---|---|---|
| **Driver** | `vectorized_montecarlo.py:120` | `BatchRNG.normal_batch_levelA_per_driver(N, means, stds)` | `seed+sim_idx*1000` per driver | **A exact** | PASS |
| **Constructor** | `vectorized:106` | `normal_batch_levelA(N, num_constr)` | `seed+sim_idx*1000` | **A exact** | PASS |
| **Qualifying** | `vectorized:128` | `normal_batch_levelA` per sim | `seed+sim_idx*1000+2` | **A exact** (fixed) | PASS |
| **AR1 lap** | `vectorized:240` | `normal(0,0.4) size=(N,D)` with `seed+100+lap` (single RNG per lap) | `seed+100+lap` | **B** (shared) | **FAIL - root cause** |
| **Reliability** | `vectorized:186` | `random(size=(N,D))` with `seed+3` (single) | `seed+3` | **B** (now fixed to per-sim) | Fixed to A |
| **Tyre** | `tyre/kernels.py` | Not yet randomized | — | — | — |

**Root cause:** AR1 currently uses **single RNG per lap** (`np.random.default_rng(seed+100+lap).normal(...)` for all N), not per-sim. Reference uses per-sim `seed+sim_idx*1000+100+lap`. This causes same lap noise for all simulations at same lap, but reference has independent per simulation. This changes the distribution of race times and thus win prob.

**Expected fix:** AR1 must be `for sim_idx in range(N): g = np.random.default_rng(seed+sim_idx*1000+100+lap); lap_rand[sim_idx] = g.normal(...)` — Level A exact, cost +3s for 10k×58.

## 3. Proposed Contract (Explicit Streams)

```
MASTER seed=42
├── SIMULATION sim_idx (0..N-1) → seed+sim_idx*1000
│   ├── DRIVER: normal(driver_mean, std) per driver
│   ├── CONSTRUCTOR: normal(constr_mean, 1.5) per constructor (shared)
│   ├── QUALIFYING: normal(0,0.3) per driver
│   ├── AR1: for lap in 1..58: normal(0,0.4) per driver per lap, AR1 coeff 0.7
│   ├── RELIABILITY: random() < dnf_rate per driver
│   ├── INCIDENT: per sector per lap
│   └── PIT: normal(0,0.5) per pit
```

Each stream is `master_seed + sim_idx*1000 + component_offset + lap` where component_offset is 0 for driver, 2 for qualifying, 3 for reliability, 100+lap for AR1.

**No shared RNG:** `next(shared_rng)` is forbidden; use `RNG(master, sim_idx, component, lap, driver)` deterministic addressing.

## 4. Required Fix

- Change AR1 from single `seed+100+lap` to per-sim `seed+sim_idx*1000+100+lap` (Level A)
- Keep driver/constructor already Level A
- Keep reliability Level A (already fixed)
- Document that this costs ~3s for 10k×58 (8.3s → 11.2s) but achieves exact equivalence
- Do not change model parameters to hide diff

## 5. Tests

- `N=1, D=3, L=5` trace: reference RNG trace == optimized RNG trace for same seed/sim_idx/driver/lap
- `N=10, 100, 1000` win prob diff <0.01 for Level A
