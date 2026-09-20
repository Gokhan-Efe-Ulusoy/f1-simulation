"""Phase 9D tests: eras, regulations, feature extraction."""
from __future__ import annotations

from app.data.eras import BUILTIN_ERAS, eras_by_kind, season_eras
from app.data.features import (
    circuit_features,
    constructor_features,
    driver_features,
    era_features,
)
from app.data.regulations import curated_provider_tag, regulations_for_season


def _results():
    return [
        {"race_id": "s:r1", "driver_id": "d1", "constructor_id": "c1",
         "grid_position": 1, "final_position": 1, "status": "finished", "points": 25.0},
        {"race_id": "s:r1", "driver_id": "d2", "constructor_id": "c1",
         "grid_position": 4, "final_position": 2, "status": "finished", "points": 18.0},
        {"race_id": "s:r2", "driver_id": "d1", "constructor_id": "c1",
         "grid_position": 3, "final_position": 5, "status": "finished", "points": 10.0},
        {"race_id": "s:r2", "driver_id": "d2", "constructor_id": "c1",
         "grid_position": 2, "final_position": None, "status": "retired", "points": 0.0},
    ]


def test_season_eras_overlap_and_kinds() -> None:
    eras_2024 = season_eras(2024)
    assert "pu-v6-hybrid-2014+" in eras_2024
    assert "sport-drs-2011+" in eras_2024
    assert "pu-v8-2006-2013" not in eras_2024
    assert "pu-v8-2006-2013" in season_eras(2010)
    assert eras_by_kind(2024, "power_unit") == ["pu-v6-hybrid-2014+"]
    assert eras_2024 == sorted(eras_2024)
    assert all(e.start_year >= 1950 for e in BUILTIN_ERAS)


def test_regulations_high_confidence_first() -> None:
    rules_2024 = {r.domain: r for r in regulations_for_season(2024)}
    assert rules_2024["refuelling"].value == "banned"
    assert rules_2024["points_system"].value == "25-18-15-12-10-8-6-4-2-1"
    assert rules_2024["drs"].value == "enabled"
    assert curated_provider_tag() == "curated"
    rules_2005 = {r.domain: r.value for r in regulations_for_season(2005)}
    assert rules_2005["refuelling"] == "allowed"
    assert rules_2005["drs"] == "not_present"


def test_driver_features_observed_vs_derived() -> None:
    feats = {f.name: f for f in driver_features("d1", "s", _results())}
    assert feats["avg_grid"].value == 2.0
    assert feats["avg_grid"].feature_type == "observed"
    assert feats["avg_finish"].value == 3.0
    assert feats["consistency_pstdev"].feature_type == "derived"
    assert feats["dnf_rate"].value == 0.0
    assert feats["overtaking_proxy_mean_gain"].value == -1.0
    assert feats["wet_performance"].value is None  # unavailable, not estimated
    d2 = {f.name: f for f in driver_features("d2", "s", _results())}
    assert d2["dnf_rate"].value == 0.5
    assert d2["defending_proxy_top5_retention"].value == 0.5


def test_constructor_circuit_era_features() -> None:
    pits = [{"stationary_time_seconds": 2.4}, {"stationary_time_seconds": 2.6}]
    cons = {f.name: f for f in constructor_features("c1", "s", _results(), pits)}
    assert cons["qualifying_strength_avg_grid"].value == 2.5
    assert cons["pit_performance_mean_stationary_s"].value == 2.5
    assert cons["tyre_degradation_proxy"].value is None
    empty = {f.name: f for f in constructor_features("c9", "s", _results(), [])}
    assert empty["pit_performance_mean_stationary_s"].value is None
    assert empty["pit_performance_mean_stationary_s"].sample_size == 0
    races = [{"race_id": "s:r1", "circuit_id": "c:x"}, {"race_id": "s:r2", "circuit_id": "c:x"}]
    circ = {f.name: f for f in circuit_features("c:x", "s", races, _results())}
    assert circ["overtaking_proxy_total_gains"].value == 2.0
    assert circ["avg_lap_time_seconds"].value is None
    era = {f.name: f for f in era_features(
        "e", "s", [{"points": 25.0}, {"points": 18.0}, {"points": 10.0}])}
    assert era["field_spread_pstdev"] is not None
    assert era["field_spread_pstdev"].sample_size == 3


def test_feature_extraction_deterministic() -> None:
    first = [(f.feature_id, f.value) for f in driver_features("d1", "s", _results())]
    second = [(f.feature_id, f.value) for f in driver_features("d1", "s", _results())]
    assert first == second
