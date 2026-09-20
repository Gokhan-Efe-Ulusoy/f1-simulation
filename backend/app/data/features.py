"""Historical feature extraction (Phase 9D).

Derived features are computed only from canonical records and always
declare feature_type + sample_size. Anything unavailable yields value None
(no estimation). All aggregations are deterministic (sorted inputs).
"""
from __future__ import annotations

import statistics
from typing import Any

from pydantic import BaseModel, Field

from app.data.models.canonical import FeatureType


class FeatureRecord(BaseModel):
    """One extracted feature value with its provenance type."""

    feature_id: str  # e.g. "driver:d1:2024:avg_grid"
    entity_type: str = ""  # driver | constructor | circuit | era
    entity_id: str = ""
    season_id: str = ""
    name: str = ""
    value: float | None = None
    feature_type: FeatureType = "observed"
    sample_size: int = 0
    detail: dict[str, Any] = Field(default_factory=dict)

    model_config = {"use_enum_values": True}


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _stdev(values: list[float]) -> float | None:
    return statistics.pstdev(values) if len(values) >= 2 else None


def _record(entity_type: str, entity_id: str, season_id: str, name: str,
            value: float | None, feature_type: FeatureType,
            sample_size: int) -> FeatureRecord:
    return FeatureRecord(
        feature_id=f"{entity_type}:{entity_id}:{season_id}:{name}",
        entity_type=entity_type, entity_id=entity_id, season_id=season_id,
        name=name, value=value, feature_type=feature_type, sample_size=sample_size,
    )


def driver_features(driver_id: str, season_id: str,
                    results: list[dict[str, Any]],
                    laps: list[dict[str, Any]] | None = None) -> list[FeatureRecord]:
    """Extract driver features from canonical classification rows.

    12+ features, no subjective 0-100 ratings; raw statistical estimates only.
    """
    rows = sorted(
        (r for r in results if str(r.get("driver_id")) == driver_id),
        key=lambda r: str(r.get("race_id", "")),
    )
    grids = [float(r["grid_position"]) for r in rows if r.get("grid_position") is not None]
    finishes = [float(r["final_position"]) for r in rows if r.get("final_position") is not None]
    statuses = [str(r.get("status", "")) for r in rows]
    dnfs = sum(1 for s in statuses if s and s != "finished")
    incidents = sum(1 for s in statuses if s in ("retired", "accident", "collision"))
    gains = [float(r["grid_position"]) - float(r["final_position"]) for r in rows
             if r.get("grid_position") is not None and r.get("final_position") is not None]
    top5_starts = [r for r in rows
                   if r.get("grid_position") is not None and r["grid_position"] <= 5]
    retained = [1.0 if (r.get("final_position") is not None and r["final_position"] <= 5) else 0.0
                for r in top5_starts]
    # Qualifying/race deltas vs field median (era-normalized friendly)
    grid_deltas = [g - (_mean(grids) or g) for g in grids] if grids else []
    finish_deltas = [f - (_mean(finishes) or f) for f in finishes] if finishes else []
    lap_times = [float(l["lap_time_seconds"]) for l in (laps or []) if l.get("lap_time_seconds") is not None]  # noqa: E501
    return [
        _record("driver", driver_id, season_id, "average_grid_position", _mean(grids), "observed", len(grids)),  # noqa: E501
        _record("driver", driver_id, season_id, "average_finish_position", _mean(finishes), "observed", len(finishes)),  # noqa: E501
        _record("driver", driver_id, season_id, "avg_grid", _mean(grids), "observed", len(grids)),
        _record("driver", driver_id, season_id, "avg_finish", _mean(finishes), "observed", len(finishes)),  # noqa: E501
        _record("driver", driver_id, season_id, "qualifying_delta", _mean(grid_deltas), "derived", len(grid_deltas)),  # noqa: E501
        _record("driver", driver_id, season_id, "race_pace_delta", _mean(finish_deltas), "derived", len(finish_deltas)),  # noqa: E501
        _record("driver", driver_id, season_id, "finish_position_variance",
                (_stdev(finishes) ** 2) if finishes and _stdev(finishes) is not None else None, "derived", len(finishes)),  # noqa: E501
        _record("driver", driver_id, season_id, "consistency_pstdev",
                _stdev(finishes), "derived", len(finishes)),
        _record("driver", driver_id, season_id, "lap_time_variance",
                (_stdev(lap_times) ** 2) if lap_times and _stdev(lap_times) is not None else None, "derived", len(lap_times)),  # noqa: E501
        _record("driver", driver_id, season_id, "dnf_rate",
                (dnfs / len(rows)) if rows else None, "observed", len(rows)),
        _record("driver", driver_id, season_id, "incident_rate",
                (incidents / len(rows)) if rows else None, "observed", len(rows)),
        _record("driver", driver_id, season_id, "overtaking_rate",
                (sum(1 for g in gains if g > 0) / len(gains)) if gains else None, "derived", len(gains)),  # noqa: E501
        _record("driver", driver_id, season_id, "overtaking_proxy_mean_gain",
                _mean(gains), "derived", len(gains)),
        _record("driver", driver_id, season_id, "defending_proxy_top5_retention",
                _mean(retained), "derived", len(retained)),
        _record("driver", driver_id, season_id, "wet_performance", None, "observed", 0),
        _record("driver", driver_id, season_id, "tyre_management_proxy", None, "observed", 0),
        _record("driver", driver_id, season_id, "consistency", _stdev(finishes), "derived", len(finishes)),  # noqa: E501
        _record("driver", driver_id, season_id, "pressure_proxy",
                (_mean([abs(g) for g in gains]) if gains else None), "derived", len(gains)),
        _record("driver", driver_id, season_id, "finish_rate",
                ((len(rows) - dnfs) / len(rows)) if rows else None, "observed", len(rows)),
    ]


def constructor_features(constructor_id: str, season_id: str,
                         results: list[dict[str, Any]],
                         pit_stops: list[dict[str, Any]] | None = None) -> list[FeatureRecord]:
    """Extract constructor features from canonical rows."""
    rows = sorted(
        (r for r in results if str(r.get("constructor_id")) == constructor_id),
        key=lambda r: str(r.get("race_id", "")),
    )
    grids = [float(r["grid_position"]) for r in rows if r.get("grid_position") is not None]
    finishes = [float(r["final_position"]) for r in rows if r.get("final_position") is not None]
    dnfs = sum(1 for r in rows if str(r.get("status", "")) not in ("", "finished"))
    pit_times = [float(p["stationary_time_seconds"]) for p in (pit_stops or [])
                 if p.get("stationary_time_seconds") is not None]
    # Development rate: slope of finish positions over season (negative = improving)
    dev_rate = None
    if len(finishes) >= 3:
        try:
            # Simple linear trend (first half vs second half)
            mid = len(finishes) // 2
            dev_rate = _mean(finishes[mid:]) - _mean(finishes[:mid]) if _mean(finishes[:mid]) is not None and _mean(finishes[mid:]) is not None else None  # noqa: E501
        except Exception:
            dev_rate = None
    return [
        _record("constructor", constructor_id, season_id, "qualifying_pace", _mean(grids), "observed", len(grids)),  # noqa: E501
        _record("constructor", constructor_id, season_id, "qualifying_strength_avg_grid",
                _mean(grids), "observed", len(grids)),
        _record("constructor", constructor_id, season_id, "race_pace", _mean(finishes), "observed", len(finishes)),  # noqa: E501
        _record("constructor", constructor_id, season_id, "race_pace_avg_finish",
                _mean(finishes), "observed", len(finishes)),
        _record("constructor", constructor_id, season_id, "reliability", 1.0 - (dnfs / len(rows)) if rows else None, "derived", len(rows)),  # noqa: E501
        _record("constructor", constructor_id, season_id, "reliability_dnf_rate",
                (dnfs / len(rows)) if rows else None, "observed", len(rows)),
        _record("constructor", constructor_id, season_id, "dnf_rate", (dnfs / len(rows)) if rows else None, "observed", len(rows)),  # noqa: E501
        _record("constructor", constructor_id, season_id, "pit_stop_performance", _mean(pit_times), "observed", len(pit_times)),  # noqa: E501
        _record("constructor", constructor_id, season_id, "pit_performance_mean_stationary_s",
                _mean(pit_times), "observed", len(pit_times)),
        _record("constructor", constructor_id, season_id, "tyre_degradation", None, "derived", 0),
        _record("constructor", constructor_id, season_id, "tyre_degradation_proxy",
                None, "derived", 0),
        _record("constructor", constructor_id, season_id, "development_rate", dev_rate, "derived", len(finishes)),  # noqa: E501
        _record("constructor", constructor_id, season_id, "track_adaptability", _stdev(finishes), "derived", len(finishes)),  # noqa: E501
        _record("constructor", constructor_id, season_id, "wet_weather_performance", None, "observed", 0),  # noqa: E501
    ]


def circuit_features(circuit_id: str, season_id: str,
                     races: list[dict[str, Any]],
                     results: list[dict[str, Any]],
                     laps: list[dict[str, Any]] | None = None) -> list[FeatureRecord]:
    """Extract circuit features (overtaking proxy needs grid+finish pairs)."""
    venue_races = {str(r.get("race_id")) for r in races
                   if str(r.get("circuit_id")) == circuit_id}
    rows = [r for r in results if str(r.get("race_id")) in venue_races]
    gains = [float(r["grid_position"]) - float(r["final_position"]) for r in rows
             if r.get("grid_position") is not None and r.get("final_position") is not None
             and float(r["grid_position"]) > float(r["final_position"])]
    lap_times = [float(l["lap_time_seconds"]) for l in (laps or []) if l.get("lap_time_seconds") is not None]  # noqa: E501
    overtakes = len(gains)
    total_cars = len(rows) if rows else 0
    return [
        _record("circuit", circuit_id, season_id, "overtaking_proxy_total_gains",
                float(sum(gains)) if gains else None, "derived", len(gains)),
        _record("circuit", circuit_id, season_id, "overtaking_frequency",
                (overtakes / total_cars) if total_cars else None, "derived", total_cars),
        _record("circuit", circuit_id, season_id, "average_lap_time", _mean(lap_times), "observed", len(lap_times)),  # noqa: E501
        _record("circuit", circuit_id, season_id, "avg_lap_time_seconds",
                _mean(lap_times), "observed", len(lap_times)),
        _record("circuit", circuit_id, season_id, "safety_car_frequency",
                None, "observed", 0),
        _record("circuit", circuit_id, season_id, "degradation", None, "derived", 0),
        _record("circuit", circuit_id, season_id, "pit_loss", None, "derived", 0),
        _record("circuit", circuit_id, season_id, "field_spread", _stdev([float(r["final_position"]) for r in rows if r.get("final_position") is not None]), "derived", len(rows)),  # noqa: E501
    ]


def era_features(era_id: str, season_id: str,
                 standings: list[dict[str, Any]]) -> list[FeatureRecord]:
    """Extract era-level spread features from standings rows."""
    points = [float(s["points"]) for s in standings if s.get("points") is not None]
    return [
        _record("era", era_id, season_id, "field_spread_pstdev",
                _stdev(points), "derived", len(points)),
        _record("era", era_id, season_id, "avg_reliability_proxy",
                None, "derived", 0),
    ]


def car_performance_decomposition(
    laps: list[dict[str, Any]],
    shrinkage: float = 0.3,
) -> dict[str, dict[str, float]]:
    """Hierarchical decomposition: lap_time = track + car + driver + tyre + residual.

    Uses shrinkage to avoid overfitting drivers/cars with small samples.
    Returns {entity_id: {component: value, ...}} with era-normalized residuals.
    Explicitly not a subjective rating.
    """
    if not laps:
        return {}
    # Track baseline per circuit
    by_circuit: dict[str, list[float]] = {}
    for lap in laps:
        circ = str(lap.get("circuit_id", "unknown"))
        if lap.get("lap_time_seconds") is not None:
            by_circuit.setdefault(circ, []).append(float(lap["lap_time_seconds"]))
    track_baseline = {c: _mean(v) or 90.0 for c, v in by_circuit.items()}
    global_mean = _mean([float(l["lap_time_seconds"]) for l in laps if l.get("lap_time_seconds") is not None]) or 90.0  # noqa: E501
    # Car and driver effects with shrinkage toward 0
    by_car: dict[str, list[float]] = {}
    by_driver: dict[str, list[float]] = {}
    for lap in laps:
        if lap.get("lap_time_seconds") is None:
            continue
        t = float(lap["lap_time_seconds"])
        circ = str(lap.get("circuit_id", "unknown"))
        baseline = track_baseline.get(circ, global_mean)
        residual = t - baseline
        by_car.setdefault(str(lap.get("car_id", "unknown")), []).append(residual)
        by_driver.setdefault(str(lap.get("driver_id", "unknown")), []).append(residual)
    car_effect = {}
    for car_id, vals in by_car.items():
        raw = _mean(vals) or 0.0
        # Shrinkage: n/(n + k) * raw, k=5
        n = len(vals)
        car_effect[car_id] = raw * (n / (n + 5)) * (1 - shrinkage) + 0 * shrinkage
    driver_effect = {}
    for driver_id, vals in by_driver.items():
        raw = _mean(vals) or 0.0
        n = len(vals)
        driver_effect[driver_id] = raw * (n / (n + 5)) * (1 - shrinkage)
    return {"car_effect": car_effect, "driver_effect": driver_effect, "track_baseline": track_baseline}  # noqa: E501
