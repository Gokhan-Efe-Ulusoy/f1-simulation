"""Calibration objectives (Phase 11)."""
from __future__ import annotations

from typing import Any

from app.data.metrics import mae, rank_correlation


def lap_time_objective(actual: list[float], predicted: list[float]) -> float:
    """MAE for lap times (primary)."""
    val = mae(actual, predicted)
    return val if val is not None else float("inf")


def position_objective(actual_order: list[str], predicted_order: list[str]) -> float:
    """Position error + (1 - rank correlation) combined."""
    from app.data.metrics import position_error

    pos_err = position_error(actual_order, predicted_order)
    corr = rank_correlation(
        [float(actual_order.index(d)) if d in actual_order else 0 for d in predicted_order],
        [float(i) for i in range(len(predicted_order))],
    )
    base = pos_err if pos_err is not None else 10.0
    corr_penalty = (1.0 - corr) if corr is not None else 1.0
    return base + corr_penalty * 2.0


def composite_objective(metrics: dict[str, Any], weights: dict[str, float] | None = None) -> float:
    """Weighted sum of available metrics."""
    weights = weights or {"position_error": 1.0, "lap_time_mae": 0.5, "dnf_error": 2.0}
    total = 0.0
    for key, weight in weights.items():
        val = metrics.get(key)
        if val is not None:
            total += float(val) * weight
    return total
