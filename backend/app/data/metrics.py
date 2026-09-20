"""Reusable calibration metrics (Phase 9E).

All functions are pure and deterministic. Rank correlation uses a
rank-based Spearman implementation without external statistics state.
Brier score and calibration-curve helpers support probabilistic claims.
"""
from __future__ import annotations

import math


def mae(actual: list[float], predicted: list[float]) -> float | None:
    """Mean absolute error, or None on empty/mismatched input."""
    if not actual or len(actual) != len(predicted):
        return None
    return sum(abs(a - p) for a, p in zip(actual, predicted, strict=True)) / len(actual)


def rmse(actual: list[float], predicted: list[float]) -> float | None:
    """Root mean squared error, or None on empty/mismatched input."""
    if not actual or len(actual) != len(predicted):
        return None
    return math.sqrt(sum((a - p) ** 2 for a, p in zip(actual, predicted, strict=True))
                     / len(actual))


def _ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    position = 0
    while position < len(order):
        tie_end = position
        while tie_end + 1 < len(order) and values[order[tie_end + 1]] == values[order[position]]:
            tie_end += 1
        average = (position + tie_end) / 2.0 + 1.0
        for k in range(position, tie_end + 1):
            ranks[order[k]] = average
        position = tie_end + 1
    return ranks


def rank_correlation(actual: list[float], predicted: list[float]) -> float | None:
    """Spearman rank correlation, or None when undefined."""
    if len(actual) != len(predicted) or len(actual) < 2:
        return None
    rank_a, rank_b = _ranks(actual), _ranks(predicted)
    mean_a = sum(rank_a) / len(rank_a)
    mean_b = sum(rank_b) / len(rank_b)
    numerator = sum((a - mean_a) * (b - mean_b) for a, b in zip(rank_a, rank_b, strict=True))
    denom_a = math.sqrt(sum((a - mean_a) ** 2 for a in rank_a))
    denom_b = math.sqrt(sum((b - mean_b) ** 2 for b in rank_b))
    if denom_a == 0 or denom_b == 0:
        return None
    return numerator / (denom_a * denom_b)


def position_error(actual_order: list[str], predicted_order: list[str]) -> float | None:
    """Mean absolute position displacement over shared drivers."""
    shared = [d for d in predicted_order if d in actual_order]
    if not shared:
        return None
    actual_rank = {driver: rank for rank, driver in enumerate(actual_order)}
    predicted_rank = {driver: rank for rank, driver in enumerate(predicted_order)}
    return sum(abs(actual_rank[d] - predicted_rank[d]) for d in shared) / len(shared)


def lap_time_error(actual: list[float], predicted: list[float]) -> float | None:
    """MAE over lap times (alias kept explicit for reports)."""
    return mae(actual, predicted)


def dnf_rate_error(actual_rate: float, predicted_rate: float) -> float:
    """Absolute DNF-rate error."""
    return abs(actual_rate - predicted_rate)


def pit_stop_error(actual: int, predicted: int) -> int:
    """Absolute pit-stop count error."""
    return abs(actual - predicted)


def tyre_degradation_error(actual: list[float], predicted: list[float]) -> float | None:
    """MAE over per-lap degradation deltas."""
    return mae(actual, predicted)


def brier_score(probabilities: list[float], outcomes: list[int]) -> float | None:
    """Mean squared probability error, or None on empty/mismatched input."""
    if not probabilities or len(probabilities) != len(outcomes):
        return None
    return sum((p - o) ** 2 for p, o in zip(probabilities, outcomes, strict=True)) \
        / len(probabilities)


def calibration_curve(probabilities: list[float], outcomes: list[int],
                      bins: int = 5) -> list[dict[str, float]]:
    """Binned mean predicted vs observed rates (deterministic)."""
    if not probabilities or len(probabilities) != len(outcomes) or bins < 1:
        return []
    width = 1.0 / bins
    curve = []
    for index in range(bins):
        low, high = index * width, (index + 1) * width
        bucket = [(p, o) for p, o in zip(probabilities, outcomes, strict=True)
                  if (low <= p < high) or (index == bins - 1 and p == high)]
        if not bucket:
            curve.append({"bin": float(index), "mean_predicted": 0.0,
                          "observed_rate": 0.0, "count": 0.0})
        else:
            curve.append({
                "bin": float(index),
                "mean_predicted": sum(p for p, _ in bucket) / len(bucket),
                "observed_rate": sum(o for _, o in bucket) / len(bucket),
                "count": float(len(bucket)),
            })
    return curve
