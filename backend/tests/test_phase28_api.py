"""Phase 28 — API tests: health, metadata, races, race, deterministic race, monte carlo, strategy, scenario, replay, leakage, limits, error model, provenance, regression."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.simulation.version import (
    MODEL_VERSION,
    RACEENGINE_VERSION,
    SIMULATION_VERSION,
)


@pytest.fixture  # type: ignore[misc]
def client():
    app = create_app()
    return TestClient(app)


# ---- health / metadata ----
def test_health(client):  # type: ignore[no-untyped-def]
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "healthy"


def test_metadata(client):  # type: ignore[no-untyped-def]
    r = client.get("/api/v1/metadata")
    assert r.status_code == 200
    j = r.json()
    assert j["dataset_version"] == "f1-dataset-v1.3"
    assert j["race_engine_version"] == RACEENGINE_VERSION
    assert j["model_version"] == MODEL_VERSION
    assert j["simulation_version"] == SIMULATION_VERSION
    assert j["evidence_tiers"]["fuel"] == "NON_IDENTIFIABLE"
    assert j["evidence_tiers"]["strategy"] == "PRIOR_ONLY"
    assert j["evidence_tiers"]["setup"] == "PRIOR_ONLY"


# ---- races ----
def test_race_listing(client):  # type: ignore[no-untyped-def]
    r = client.get("/api/v1/races?limit=2")
    assert r.status_code == 200
    j = r.json()
    assert "races" in j and "total" in j
    assert len(j["races"]) <= 2
    assert j["total"] >= 24


def test_race_filter_season(client):  # type: ignore[no-untyped-def]
    r = client.get("/api/v1/races?season=2024&limit=5")
    assert r.status_code == 200
    for race in r.json()["races"]:
        assert str(race["season_id"]) == "2024"


def test_race_lookup(client):  # type: ignore[no-untyped-def]
    r = client.get("/api/v1/races/2024-bahrain")
    assert r.status_code == 200
    assert r.json()["race_id"] == "2024-bahrain"


def test_invalid_race(client):  # type: ignore[no-untyped-def]
    r = client.get("/api/v1/races/does-not-exist-zzz")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "RACE_NOT_FOUND"


# ---- deterministic race ----
def test_deterministic_race(client):  # type: ignore[no-untyped-def]
    payload = {"race_id": "bahrain", "seed": 42, "laps_override": 5}
    r1 = client.post("/api/v1/simulate/race", json=payload)
    assert r1.status_code == 200
    j1 = r1.json()
    assert "simulation_id" in j1 and "classification" in j1 and "provenance" in j1
    assert j1["provenance"]["dataset_version"] == "f1-dataset-v1.3"
    assert "evidence_tiers" in j1
    assert j1["evidence_tiers"]["fuel"] == "NON_IDENTIFIABLE"
    # same seed => identical
    r2 = client.post("/api/v1/simulate/race", json=payload)
    assert r2.status_code == 200
    assert r2.json()["classification"] == j1["classification"]
    assert r2.json()["provenance"] == j1["provenance"]


def test_different_seed_produces_different_result(client):  # type: ignore[no-untyped-def]
    p1 = {"race_id": "bahrain", "seed": 42, "laps_override": 5}
    p2 = {"race_id": "bahrain", "seed": 999, "laps_override": 5}
    r1 = client.post("/api/v1/simulate/race", json=p1)
    r2 = client.post("/api/v1/simulate/race", json=p2)
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["classification"] != r2.json()["classification"]


def test_race_simulation_id_retrievable(client):  # type: ignore[no-untyped-def]
    payload = {"race_id": "monaco", "seed": 123, "laps_override": 3}
    r = client.post("/api/v1/simulate/race", json=payload)
    sid = r.json()["simulation_id"]
    g = client.get(f"/api/v1/simulation/{sid}")
    assert g.status_code == 200
    assert g.json()["simulation_id"] == sid
    assert g.json()["status"].lower() == "completed"


def test_invalid_laps(client):  # type: ignore[no-untyped-def]
    r = client.post("/api/v1/simulate/race", json={"race_id": "bahrain", "seed": 42, "laps_override": 999})
    assert r.status_code == 422  # pydantic validation before handler


# ---- Monte Carlo ----
def test_monte_carlo(client):  # type: ignore[no-untyped-def]
    r = client.post(
        "/api/v1/simulate/monte-carlo",
        json={"race_id": "bahrain", "seed": 42, "simulations": 10},
    )
    assert r.status_code == 200
    j = r.json()
    assert j["N"] == 10 and j["seed"] == 42
    assert "win_probabilities" in j and "podium_probabilities" in j
    assert "finish_position_distribution" in j
    assert "provenance" in j
    assert j["reproducibility"]["seed"] == 42


def test_monte_carlo_determinism(client):  # type: ignore[no-untyped-def]
    payload = {"race_id": "bahrain", "seed": 7, "simulations": 20}
    r1 = client.post("/api/v1/simulate/monte-carlo", json=payload)
    r2 = client.post("/api/v1/simulate/monte-carlo", json=payload)
    assert r1.json()["win_probabilities"] == r2.json()["win_probabilities"]
    assert r1.json()["podium_probabilities"] == r2.json()["podium_probabilities"]


def test_monte_carlo_limits(client):  # type: ignore[no-untyped-def]
    r = client.post(
        "/api/v1/simulate/monte-carlo",
        json={"race_id": "bahrain", "seed": 42, "simulations": 6000},
    )
    assert r.status_code == 422  # pydantic le=5000
    r2 = client.post(
        "/api/v1/simulate/monte-carlo",
        json={"race_id": "bahrain", "seed": 42, "simulations": 0},
    )
    assert r2.status_code == 422


def test_monte_carlo_seed_different(client):  # type: ignore[no-untyped-def]
    r1 = client.post("/api/v1/simulate/monte-carlo", json={"race_id": "bahrain", "seed": 42, "simulations": 20})
    r2 = client.post("/api/v1/simulate/monte-carlo", json={"race_id": "bahrain", "seed": 43, "simulations": 20})
    assert r1.json()["win_probabilities"] != r2.json()["win_probabilities"]


# ---- strategy ----
def test_strategy_evaluate(client):  # type: ignore[no-untyped-def]
    state = {
        "driver_id": "driver_00",
        "lap": 10,
        "position": 5,
        "gap_ahead": 1.2,
        "gap_behind": 0.8,
        "current_compound": "medium",
        "tyre_age": 15,
        "fuel_remaining": 50,
        "race_control_phase": "GREEN",
        "sector_flags": ["GREEN", "GREEN", "GREEN"],
        "weather_regime": "DRY",
        "wetness": 0.0,
        "laps_remaining": 48,
    }
    r = client.post("/api/v1/strategy/evaluate", json={"state": state, "track_pit_loss": 22.0, "seed": 42})
    assert r.status_code == 200
    j = r.json()
    assert "recommended_action" in j and "candidate_actions" in j
    assert "provenance" in j and "evidence_tier" in j


def test_strategy_leakage_rejected(client):  # type: ignore[no-untyped-def]
    state = {
        "driver_id": "driver_00",
        "lap": 10,
        "position": 5,
        "current_compound": "medium",
        "tyre_age": 15,
        "fuel_remaining": 50,
        "race_control_phase": "GREEN",
        "laps_remaining": 48,
        "future_result": "1",
    }
    r = client.post("/api/v1/strategy/evaluate", json={"state": state})
    assert r.status_code == 422


# ---- scenario ----
def test_scenario_valid(client):  # type: ignore[no-untyped-def]
    # use real historical race driver id
    from app.simulation.replay.state_builder import load_historical_race

    h = load_historical_race("2024-bahrain")
    did = h.drivers[0]["driver_id"]
    r = client.post(
        "/api/v1/scenario/compare",
        json={
            "race_id": "2024-bahrain",
            "seed": 42,
            "simulations": 10,
            "interventions": [
                {"family": "driver", "op": "ADD_DELTA", "target": did, "parameter": "pace_delta", "value": 0.5}
            ],
        },
    )
    assert r.status_code == 200
    j = r.json()
    assert "trace" in j and "comparison" in j and "provenance" in j


def test_scenario_leakage_rejected(client):  # type: ignore[no-untyped-def]
    r = client.post(
        "/api/v1/scenario/compare",
        json={
            "race_id": "2024-bahrain",
            "seed": 42,
            "simulations": 10,
            "interventions": [
                {
                    "family": "weather",
                    "op": "SET_VALUE",
                    "target": "race",
                    "parameter": "future_weather",
                    "value": 1.0,
                }
            ],
        },
    )
    assert r.status_code == 422


def test_scenario_invalid_intervention(client):  # type: ignore[no-untyped-def]
    r = client.post(
        "/api/v1/scenario/compare",
        json={
            "race_id": "2024-bahrain",
            "seed": 42,
            "simulations": 10,
            "interventions": [
                {
                    "family": "driver",
                    "op": "ADD_DELTA",
                    "target": "nonexistent_driver_xyz",
                    "parameter": "pace_delta",
                    "value": 0.5,
                }
            ],
        },
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "UNSUPPORTED_INTERVENTION"


# ---- replay ----
def test_replay(client):  # type: ignore[no-untyped-def]
    r = client.get("/api/v1/replay/2024-bahrain?simulations=5")
    assert r.status_code == 200
    j = r.json()
    assert "checkpoint_results" in j and "provenance" in j


def test_replay_checkpoint(client):  # type: ignore[no-untyped-def]
    r = client.get("/api/v1/replay/2024-bahrain?simulations=5&checkpoint=lap_5")
    assert r.status_code == 200
    j = r.json()
    assert j["checkpoint"] is not None
    assert "checkpoints" in j


def test_replay_invalid_race(client):  # type: ignore[no-untyped-def]
    r = client.get("/api/v1/replay/does-not-exist?simulations=5")
    assert r.status_code == 404


# ---- error model / security ----
def test_path_traversal_rejected(client):  # type: ignore[no-untyped-def]
    r = client.post("/api/v1/simulate/race", json={"race_id": "../etc/passwd", "seed": 42})
    assert r.status_code == 422
    r2 = client.get("/api/v1/races/../../etc/passwd")
    assert r2.status_code in (404, 422)


def test_openapi_generated(client):  # type: ignore[no-untyped-def]
    r = client.get("/openapi.json")
    assert r.status_code == 200
    j = r.json()
    paths = j.get("paths", {})
    assert "/api/v1/health" in paths
    assert "/api/v1/metadata" in paths
    assert "/api/v1/simulate/race" in paths
    assert "/api/v1/simulate/monte-carlo" in paths
    assert "/api/v1/strategy/evaluate" in paths
    assert "/api/v1/scenario/compare" in paths
    assert "/api/v1/replay/{race_id}" in paths


# ---- API / direct engine equivalence (regression) ----
def test_api_direct_engine_equivalence():  # type: ignore[no-untyped-def]
    """Direct RaceEngine vs API must produce same classification for same seed."""
    from fastapi.testclient import TestClient as TC

    from app.main import create_app as ca
    from app.services.simulation_service import simulate_single_race as direct

    app = ca()
    c = TC(app)
    payload = {"race_id": "bahrain", "seed": 42, "laps_override": 5}
    api_res = c.post("/api/v1/simulate/race", json=payload).json()
    direct_res = direct(race_id="bahrain", seed=42, laps_override=5)
    assert api_res["classification"] == direct_res["classification"]


def test_no_calibration_promotion(client):  # type: ignore[no-untyped-def]
    r = client.get("/api/v1/metadata")
    j = r.json()
    assert j["calibration_version"] == "calibration-v1.0.0"
    assert j["tyre_version"] == "tyre-v1.0.0"
    assert j["strategy_version"] == "strategy-v1.1.0"
    assert j["setup_version"] == "setup-v1.0.0"
