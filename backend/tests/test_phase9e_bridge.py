"""Phase 9E tests: scenario builder, calibration bridge, metrics, splits, benchmark."""
from __future__ import annotations

import pytest

from app.data.benchmark import run_benchmark
from app.data.calibration_bridge import (
    CalibratedParameter,
    CarCalibrationProfile,
    ConstructorCalibrationProfile,
    DriverCalibrationProfile,
    EraCalibrationProfile,
    FittedCalibrationSet,
    TrackCalibrationProfile,
)
from app.data.metrics import (
    brier_score,
    calibration_curve,
    dnf_rate_error,
    lap_time_error,
    mae,
    pit_stop_error,
    position_error,
    rank_correlation,
    rmse,
    tyre_degradation_error,
)
from app.data.scenario import build_scenario
from app.data.splits import TemporalSplit


def _param(name: str, value: float) -> CalibratedParameter:
    return CalibratedParameter(
        name=name, value=value, uncertainty=0.1, source_dataset="d",
        fitting_method="test", calibration_date="2026-01-01",
        model_version="0.2.0", dataset_version="f1-dataset-v0.1.0", confidence=0.8)


def test_scenario_builder_mapping_and_gaps() -> None:
    race = {"race_id": "2024-bahrain", "season_id": "2024",
            "circuit_id": "circuit:bahrain", "scheduled_laps": 57}
    results = [
        {"driver_id": "d1", "constructor_id": "c1", "car_id": "car1", "grid_position": 2},
        {"driver_id": "d2", "constructor_id": "c1", "car_id": "car1", "grid_position": 1},
        {"driver_id": "d3", "constructor_id": "c2", "car_id": "car2", "grid_position": None},
    ]
    scenario = build_scenario(race, results, drivers=[{"driver_id": "d1"}],
                              track_id_map={"circuit:bahrain": "bahrain"})
    assert scenario.scenario_id == "2024-bahrain"
    assert scenario.track_id == "bahrain"
    assert scenario.grid_order == ["d2", "d1"]
    assert scenario.total_laps == 57
    assert "grid_order:partial" in scenario.unavailable
    assert "driver:d2" in scenario.unavailable
    assert scenario.cars["d1"] == {"constructor_id": "c1", "car_id": "car1"}
    assert scenario.provenance_chain == ["canonical", "scenario"]


def test_scenario_missing_laps_flagged() -> None:
    scenario = build_scenario({"race_id": "r", "season_id": "s"}, [])
    assert scenario.total_laps is None
    assert "total_laps" in scenario.unavailable
    assert scenario.grid_order == []


def test_calibration_bridge_identity_and_projection() -> None:
    empty = FittedCalibrationSet()
    assert empty.tracks == {}
    native = empty.to_simulation_profile()
    assert native.track_calibration("monza").drs_effect_multiplier == 1.0
    assert native.driver_calibration("VER").overtaking_offset == 0.0

    fitted = FittedCalibrationSet(
        set_id="s1",
        tracks={"monza": TrackCalibrationProfile(
            track_id="monza",
            parameters={"drs_effect_multiplier": _param("drs_effect_multiplier", 1.2)})},
        drivers={"VER": DriverCalibrationProfile(
            driver_id="VER",
            parameters={"overtaking_offset": _param("overtaking_offset", 3.0),
                        "mistake_rate_multiplier": _param("mistake_rate_multiplier", 0.8)})},
        cars={"RB20": CarCalibrationProfile(
            car_id="RB20",
            parameters={"straight_line_multiplier": _param("straight_line_multiplier", 1.1)})},
        constructors={"RBR": ConstructorCalibrationProfile(constructor_id="RBR")},
        era=EraCalibrationProfile(
            era_id="hybrid",
            parameters={"incident_multiplier": _param("incident_multiplier", 0.9)}),
    )
    native = fitted.to_simulation_profile()
    assert native.profile_id == "s1"
    assert native.track_calibration("monza").drs_effect_multiplier == 1.2
    assert native.driver_calibration("VER").overtaking_offset == 3.0
    assert native.car_calibration("RB20").straight_line_multiplier == 1.1
    assert native.era.incident_multiplier == 0.9
    assert fitted.tracks["monza"].parameters["drs_effect_multiplier"].confidence == 0.8
    assert fitted.tracks["monza"].parameters["drs_effect_multiplier"].dataset_version


def test_metrics_known_values() -> None:
    assert mae([1.0, 2.0, 3.0], [1.0, 2.0, 4.0]) == 1.0 / 3.0
    assert rmse([0.0, 0.0], [3.0, 4.0]) == pytest.approx(3.5355339059)
    assert rmse([1.0, 2.0], [1.0, 2.0]) == 0.0
    assert mae([], []) is None
    assert mae([1.0], [1.0, 2.0]) is None
    assert rank_correlation([1.0, 2.0, 3.0], [3.0, 2.0, 1.0]) == pytest.approx(-1.0)
    assert rank_correlation([1.0], [1.0]) is None
    assert rank_correlation([1.0, 1.0], [1.0, 2.0]) is None
    assert position_error(["a", "b", "c"], ["b", "a", "c"]) == 2.0 / 3.0
    assert position_error(["a"], ["b"]) is None
    assert lap_time_error([90.0], [91.0]) == 1.0
    assert dnf_rate_error(0.1, 0.15) == pytest.approx(0.05)
    assert pit_stop_error(2, 3) == 1
    assert tyre_degradation_error([0.1], [0.2]) == 0.1
    assert brier_score([1.0, 0.0], [1, 0]) == 0.0
    assert brier_score([], []) is None
    curve = calibration_curve([0.1, 0.9, 0.2, 0.8], [0, 1, 0, 1], bins=2)
    assert len(curve) == 2
    assert curve[0]["count"] == 2.0 and curve[1]["count"] == 2.0
    assert curve[1]["observed_rate"] == 1.0
    assert calibration_curve([], [], bins=2) == []


def test_temporal_splits() -> None:
    split = TemporalSplit()
    assert split.assign(1999) == "train"
    assert split.assign(2000) == "train"
    assert split.assign(2005) == "validation"
    assert split.assign(2015) == "test"
    assert split.assign(2024) == "out_of_sample"
    assert split.describe()["train"] == (1950, 2000)
    custom = TemporalSplit(train_end=1990, validation_end=2000, test_end=2010)
    assert custom.assign(1995) == "validation"


def _stub_simulator(favorite: str):
    def simulate(index: int):
        order = ["d1", "d2", "d3"] if (index + len(favorite)) % 2 == 0 else ["d2", "d1", "d3"]
        return {"order": order,
                "lap_times": {"d1": [90.0], "d2": [90.5], "d3": [91.0]},
                "dnf_rate": 0.0,
                "pit_stops": {"d1": 1, "d2": 1, "d3": 2},
                "win_probabilities": {favorite: 0.6}}
    return simulate


def test_benchmark_distributions_and_metrics() -> None:
    bench = run_benchmark(
        "2024-bahrain", ["d1", "d2", "d3"],
        observed_lap_times={"d1": [90.0], "d2": [90.5], "d3": [91.0]},
        observed_dnf_rate=0.0,
        simulate=_stub_simulator("d1"), simulation_count=10,
        model_version="0.2.0", dataset_version="f1-dataset-v0.1.0")
    assert bench.race_id == "2024-bahrain"
    assert bench.simulation_count == 10
    assert set(bench.simulated_position_distribution) == {"d1", "d2", "d3"}
    assert all(len(v) == 10 for v in bench.simulated_position_distribution.values())
    assert bench.calibration_metrics["position_error"] is not None
    assert bench.calibration_metrics["lap_time_mae"] is not None
    assert bench.calibration_metrics["dnf_rate_error"] is not None
    assert bench.model_version == "0.2.0"
    assert bench.dataset_version == "f1-dataset-v0.1.0"
    assert set(bench.uncertainty) == {"d1", "d2", "d3"}


def test_benchmark_deterministic_and_requires_simulator() -> None:
    first = run_benchmark("r", ["d1", "d2"], simulate=_stub_simulator("d1"),
                          simulation_count=6)
    second = run_benchmark("r", ["d1", "d2"], simulate=_stub_simulator("d1"),
                           simulation_count=6)
    assert first.simulated_position_distribution == second.simulated_position_distribution
    assert first.calibration_metrics == second.calibration_metrics
    try:
        run_benchmark("r", ["d1"])
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError without simulator")
