"""Optimizer: bounded least-squares / regularized regression (Phase 11).

Uses scipy if available, otherwise falls back to simple hill climbing.
Deterministic given seed via RandomProvider.
"""
from __future__ import annotations

from collections.abc import Callable

import numpy as np

try:
    from scipy.optimize import minimize  # type: ignore[import-not-found]

    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


def bounded_optimize(
    objective: Callable[[list[float]], float],
    initial: list[float],
    bounds: list[tuple[float, float]],
    seed: int | None = 0,
    max_iter: int = 50,
) -> tuple[list[float], float]:
    """Bounded optimization (deterministic). Returns (best_params, best_value)."""
    rng = np.random.default_rng(seed)
    best = list(initial)
    best_val = objective(best)

    if HAS_SCIPY:
        try:
            res = minimize(
                objective,
                np.array(initial, dtype=float),
                bounds=bounds,
                method="L-BFGS-B",
                options={"maxiter": max_iter},
            )
            if res.fun < best_val:
                return res.x.tolist(), float(res.fun)
        except Exception:
            pass

    # Fallback: simple random hill climbing (deterministic)
    for _ in range(max_iter * 2):
        candidate = [
            float(np.clip(v + rng.normal(0, (hi - lo) * 0.1), lo, hi))
            for v, (lo, hi) in zip(best, bounds)
        ]
        val = objective(candidate)
        if val < best_val:
            best, best_val = candidate, val
    return best, best_val
