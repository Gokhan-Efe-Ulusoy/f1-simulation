"""Historical race reconstruction benchmark framework (Phase 9E).

Compares one observed classification against a simulated distribution.
The simulator is injected, so the framework never depends on RaceEngine
directly and tests run with deterministic stubs.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from pydantic import BaseModel, Field

from app.data import metrics

SimulateFn = Callable[[int], dict[str, Any]]
# Per-simulation output: {"order": [driver_ids...], "lap_times": {id: [s...]},
# "dnf_rate": float, "pit_stops": {id: int}, "win_probabilities": {id: float}}


class HistoricalRaceBenchmark(BaseModel):
    """One benchmark run: observed vs simulated distributions."""

    race_id: str
    simulation_count: int = 0
    observed_result: dict[str, Any] = Field(default_factory=dict)
    simulated_position_distribution: dict[str, list[int]] = Field(default_factory=dict)
    simulated_lap_time_distribution: dict[str, list[float]] = Field(default_factory=dict)
    calibration_metrics: dict[str, float | None] = Field(default_factory=dict)
    uncertainty: dict[str, float] = Field(default_factory=dict)
    model_version: str = ""
    dataset_version: str = ""

    model_config = {"use_enum_values": True}


def run_benchmark(
    race_id: str,
    observed_order: Sequence[str],
    observed_lap_times: dict[str, list[float]] | None = None,
    observed_dnf_rate: float | None = None,
    simulate: SimulateFn | None = None,
    simulation_count: int = 20,
    model_version: str = "",
    dataset_version: str = "",
) -> HistoricalRaceBenchmark:
    """Run reconstructions and score them (deterministic per simulate fn)."""
    if simulate is None:
        raise ValueError("a simulate callable is required (no implicit simulator)")
    position_samples: dict[str, list[int]] = {d: [] for d in observed_order}
    lap_samples: dict[str, list[float]] = {d: [] for d in observed_order}
    win_counts: dict[str, int] = dict.fromkeys(observed_order, 0)
    dnf_rates: list[float] = []
    pit_errors: list[int] = []
    for index in range(simulation_count):
        output = simulate(index)
        order = list(output.get("order", []))
        for position, driver in enumerate(order):
            if driver in position_samples:
                position_samples[driver].append(position + 1)
        if order and order[0] in win_counts:
            win_counts[order[0]] += 1
        for driver, times in (output.get("lap_times") or {}).items():
            if driver in lap_samples:
                lap_samples[driver].extend(float(t) for t in times)
        if output.get("dnf_rate") is not None:
            dnf_rates.append(float(output["dnf_rate"]))
        if output.get("pit_stops") is not None:
            pit_errors.append(sum(abs(int(v)) for v in output["pit_stops"].values()))

    mean_positions = {
        driver: (sum(samples) / len(samples) if samples else None)
        for driver, samples in position_samples.items()
    }
    def _sort_key(driver: str) -> tuple[bool, float]:
        mean = mean_positions[driver]
        return (mean is None, mean if mean is not None else 0.0)

    predicted_order = sorted(observed_order, key=_sort_key)
    calibration_metrics: dict[str, float | None] = {
        "position_error": metrics.position_error(list(observed_order), predicted_order),
        "brier_win": metrics.brier_score(
            [win_counts[d] / simulation_count for d in observed_order],
            [1 if d == observed_order[0] else 0 for d in observed_order],
        ) if simulation_count else None,
    }
    if observed_lap_times:
        actual = [t for d in observed_order for t in observed_lap_times.get(d, [])]
        predicted = [t for d in observed_order for t in lap_samples.get(d, [])]
        length = min(len(actual), len(predicted))
        calibration_metrics["lap_time_mae"] = metrics.mae(actual[:length], predicted[:length])
        calibration_metrics["lap_time_rmse"] = metrics.rmse(actual[:length], predicted[:length])
    if observed_dnf_rate is not None and dnf_rates:
        calibration_metrics["dnf_rate_error"] = metrics.dnf_rate_error(
            observed_dnf_rate, sum(dnf_rates) / len(dnf_rates))
    if pit_errors:
        calibration_metrics["pit_stop_error_mean"] = sum(pit_errors) / len(pit_errors)
    uncertainty = {
        driver: (max(samples) - min(samples)) if len(samples) > 1 else 0.0
        for driver, samples in position_samples.items()
    }
    return HistoricalRaceBenchmark(
        race_id=race_id,
        simulation_count=simulation_count,
        observed_result={"order": list(observed_order)},
        simulated_position_distribution=position_samples,
        simulated_lap_time_distribution=lap_samples,
        calibration_metrics=calibration_metrics,
        uncertainty={k: float(v) for k, v in uncertainty.items()},
        model_version=model_version,
        dataset_version=dataset_version,
    )
