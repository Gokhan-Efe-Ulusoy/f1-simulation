"""Numerical kernels for Phase 15 — Numba JIT where beneficial."""
from __future__ import annotations

import numpy as np

try:
    import numba

    HAS_NUMBA = True
except ImportError:
    HAS_NUMBA = False

# AR(1) kernel: noise[t+1] = 0.7*noise[t] + N(0,0.4)
if HAS_NUMBA:
    @numba.njit
    def ar1_step(noise: np.ndarray, rand: np.ndarray, coeff: float = 0.7) -> np.ndarray:
        # noise: (N, D), rand: (N, D) ~ N(0,0.4)
        # Using numba, we can loop
        N, D = noise.shape
        out = np.empty_like(noise)
        for i in range(N):
            for j in range(D):
                out[i, j] = coeff * noise[i, j] + rand[i, j]
        return out

    @numba.njit
    def lap_times_kernel(base_pace: np.ndarray, noise: np.ndarray, dnf: np.ndarray) -> np.ndarray:
        # base_pace: (N, D), noise: (N, D), dnf: (N, D) bool
        # lap_time = 90 + base*0.5 + noise, clipped 70, dnf => 0 (will be ignored)
        N, D = base_pace.shape
        out = np.empty((N, D), dtype=np.float32)
        for i in range(N):
            for j in range(D):
                if dnf[i, j]:
                    out[i, j] = 0.0
                else:
                    lt = 90.0 + base_pace[i, j] * 0.5 + noise[i, j]
                    if lt < 70.0:
                        lt = 70.0
                    out[i, j] = lt
        return out

    @numba.njit
    def update_positions_kernel(times: np.ndarray, dnf: np.ndarray, positions: np.ndarray):
        # For each simulation N, sort drivers by times (dnf at end)
        # times: (N, D), dnf: (N, D), positions: (N, D) output
        N, D = times.shape
        for n in range(N):
            # Create index array and sort by time, dnf last
            # Simple insertion sort for D=20 is fine
            # We'll create list of (time, idx) and sort
            # For numba, we need to implement sort manually
            # Use bubble sort for small D=20
            idx = np.empty(D, dtype=np.int64)
            for j in range(D):
                idx[j] = j
            # Bubble sort by time, dnf drivers have large time
            for j in range(D):
                for k in range(j+1, D):
                    # Compare times, dnf drivers have inf
                    t_j = np.inf if dnf[n, idx[j]] else times[n, idx[j]]
                    t_k = np.inf if dnf[n, idx[k]] else times[n, idx[k]]
                    if t_k < t_j:
                        tmp = idx[j]
                        idx[j] = idx[k]
                        idx[k] = tmp
            # Assign positions
            for rank, driver_idx in enumerate(idx):
                positions[n, driver_idx] = rank + 1

    @numba.njit
    def reliability_kernel(rand: np.ndarray, dnf_rates: np.ndarray, dnf: np.ndarray) -> np.ndarray:
        # rand: (N, D) uniform 0-1, dnf_rates: (D,) per driver, dnf: (N, D) bool (current)
        # For each driver, if not already dnf and rand < dnf_rate/total_laps (approx per race)
        # For simplicity, per-race DNF check (not per lap)
        N, D = rand.shape
        out = np.empty((N, D), dtype=np.bool_)
        for i in range(N):
            for j in range(D):
                if dnf[i, j]:
                    out[i, j] = True
                else:
                    out[i, j] = rand[i, j] < dnf_rates[j]
        return out

else:
    # Fallback without numba: use numpy
    def ar1_step(noise, rand, coeff=0.7):
        return coeff * noise + rand

    def lap_times_kernel(base_pace, noise, dnf):
        lt = 90.0 + base_pace * 0.5 + noise
        lt = np.maximum(lt, 70.0)
        lt[dnf] = 0.0
        return lt.astype(np.float32)

    def update_positions_kernel(times, dnf, positions):
        N, D = times.shape
        for n in range(N):
            # Set dnf times to inf for sorting
            t = times[n].copy()
            t[dnf[n]] = np.inf
            order = np.argsort(t)
            for rank, idx in enumerate(order):
                positions[n, idx] = rank + 1

    def reliability_kernel(rand, dnf_rates, dnf):
        # Broadcast dnf_rates (D,) to (N, D)
        prob = dnf_rates[None, :]  # shape (1, D) -> broadcast
        new_dnf = (rand < prob) & (~dnf)
        return dnf | new_dnf
