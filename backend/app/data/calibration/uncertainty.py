"""Uncertainty quantification: bootstrap + intervals (Phase 11)."""
from __future__ import annotations

import numpy as np


def bootstrap_intervals(
    values: list[float],
    n_bootstrap: int = 500,
    ci: float = 0.95,
    seed: int | None = 0,
) -> dict[str, float]:
    """Bootstrap confidence interval for mean (deterministic)."""
    if not values:
        return {"mean": 0.0, "lower": 0.0, "upper": 0.0, "std": 0.0}
    rng = np.random.default_rng(seed)
    means = []
    for _ in range(n_bootstrap):
        sample = rng.choice(values, size=len(values), replace=True)
        means.append(float(np.mean(sample)))
    alpha = (1.0 - ci) / 2.0
    return {
        "mean": float(np.mean(values)),
        "median": float(np.median(means)),
        "std": float(np.std(means)),
        "lower": float(np.percentile(means, alpha * 100)),
        "upper": float(np.percentile(means, (1 - alpha) * 100)),
        "p5": float(np.percentile(means, 5)),
        "p25": float(np.percentile(means, 25)),
        "p75": float(np.percentile(means, 75)),
        "p95": float(np.percentile(means, 95)),
    }


def parameter_uncertainty(
    samples: list[list[float]],
    param_names: list[str],
) -> dict[str, dict[str, float]]:
    """Per-parameter uncertainty from posterior/bootstrap samples."""
    result: dict[str, dict[str, float]] = {}
    for idx, name in enumerate(param_names):
        vals = [s[idx] for s in samples if idx < len(s)]
        if vals:
            result[name] = bootstrap_intervals(vals)
        else:
            result[name] = {"mean": 0.0, "lower": 0.0, "upper": 0.0, "std": 0.0}
    return result
