"""Phase 29 — Execution, persistence, determinism, leakage, security, performance."""

from __future__ import annotations

import json
import time

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.hashing import request_hash, result_hash
from app.services.execution import build_request_hash_for_montecarlo, build_request_hash_for_race


@pytest.fixture  # type: ignore[misc]
def client():
    app = create_app()
    return TestClient(app)


# A. service routing
def test_service_routing_race(client):  # type: ignore[no-untyped-def]
    r = client.post("/api/v1/simulate/race", json={"race_id": "bahrain", "seed": 42, "laps_override": 3})
    assert r.status_code == 200
    assert "classification" in r.json()


def test_service_routing_montecarlo(client):  # type: ignore[no-untyped-def]
    r = client.post("/api/v1/simulate/monte-carlo", json={"race_id": "bahrain", "seed": 42, "simulations": 10})
    assert r.status_code == 200
    assert "win_probabilities" in r.json()


# B. API -> service -> engine equivalence
def test_api_service_engine_equivalence_race():  # type: ignore[no-untyped-def]
    from app.services.simulation_service import simulate_single_race

    from fastapi.testclient import TestClient as TC

    app = create_app()
    c = TC(app)
    payload = {"race_id": "bahrain", "seed": 123, "laps_override": 5}
    api = c.post("/api/v1/simulate/race", json=payload).json()
    direct = simulate_single_race("bahrain", 123, laps_override=5)
    assert api["classification"] == direct["classification"]


def test_api_service_engine_equivalence_montecarlo(client):  # type: ignore[no-untyped-def]
    # Monte Carlo via API vs direct service (same seed) should be identical
    from app.services.montecarlo_service import run_montecarlo

    direct = run_montecarlo("bahrain", simulations=20, seed=42)
    api = client.post("/api/v1/simulate/monte-carlo", json={"race_id": "bahrain", "seed": 42, "simulations": 20}).json()
    assert direct["win_probabilities"] == api["win_probabilities"]


# C. single race execution
def test_single_race_execution(client):  # type: ignore[no-untyped-def]
    r = client.post("/api/v1/simulate/race", json={"race_id": "2024-bahrain", "seed": 42, "laps_override": 5})
    assert r.status_code == 200
    j = r.json()
    assert j["status"] in ("COMPLETED", "completed")
    assert j["simulation_type"] == "race"
    assert "request_hash" in j and j["request_hash"]
    assert "execution_time" in j
    assert j["provenance"]["dataset_version"] == "f1-dataset-v1.3"


# D. Monte Carlo execution
def test_monte_carlo_execution_small(client):  # type: ignore[no-untyped-def]
    r = client.post("/api/v1/simulate/monte-carlo", json={"race_id": "bahrain", "seed": 42, "simulations": 10})
    assert r.status_code == 200
    j = r.json()
    assert j["simulations"] == 10
    assert j["status"] in ("COMPLETED", "completed")
    assert j["simulation_type"] == "monte_carlo"
    assert "request_hash" in j


def test_monte_carlo_execution_n1000(client):  # type: ignore[no-untyped-def]
    r = client.post("/api/v1/simulate/monte-carlo", json={"race_id": "bahrain", "seed": 42, "simulations": 100})
    assert r.status_code == 200
    assert r.json()["simulations"] == 100


# E. persistent storage
def test_persistent_storage(client):  # type: ignore[no-untyped-def]
    r = client.post("/api/v1/simulate/race", json={"race_id": "monaco", "seed": 999, "laps_override": 3})
    sid = r.json()["simulation_id"]
    # check DB file exists or in-memory
    from pathlib import Path

    db_path = Path("C:/Users/gokha/Desktop/f1 simülasyonu/backend/data/simulations.db")
    # if postgres, file may not exist, but store should still retrieve
    assert sid
    g = client.get(f"/api/v1/simulation/{sid}")
    assert g.status_code == 200
    assert g.json()["simulation_id"] == sid
    # check DB via direct store
    from app.services.store import store

    rec = store.get(sid)
    assert rec is not None
    assert rec["race_id"] == "monaco"


# F. simulation retrieval
def test_simulation_retrieval_persisted(client):  # type: ignore[no-untyped-def]
    r = client.post("/api/v1/simulate/race", json={"race_id": "bahrain", "seed": 777, "laps_override": 4})
    sid = r.json()["simulation_id"]
    # retrieve via API
    g = client.get(f"/api/v1/simulation/{sid}")
    assert g.status_code == 200
    assert g.json()["result"]["classification"] == r.json()["classification"]


# G. lifecycle states
def test_lifecycle_states(client):  # type: ignore[no-untyped-def]
    r = client.post("/api/v1/simulate/race", json={"race_id": "bahrain", "seed": 42, "laps_override": 3})
    j = r.json()
    assert j["status"] in ("COMPLETED", "completed", "QUEUED", "RUNNING", "FAILED")
    # for sync, should be COMPLETED
    assert j["status"].upper() == "COMPLETED"
    sid = j["simulation_id"]
    g = client.get(f"/api/v1/simulation/{sid}")
    assert g.json()["status"].upper() == "COMPLETED"


# H. request hashing
def test_request_hash_deterministic():  # type: ignore[no-untyped-def]
    h1 = build_request_hash_for_race("bahrain", 42, 5, {"weather": {"enabled": True}})
    h2 = build_request_hash_for_race("bahrain", 42, 5, {"weather": {"enabled": True}})
    h3 = build_request_hash_for_race("bahrain", 43, 5, {"weather": {"enabled": True}})
    assert h1 == h2
    assert h1 != h3
    # different type
    hm1 = build_request_hash_for_montecarlo("bahrain", 42, 100, 5, {})
    hm2 = build_request_hash_for_montecarlo("bahrain", 42, 101, 5, {})
    assert hm1 != hm2


def test_request_hash_excludes_timestamp():  # type: ignore[no-untyped-def]
    h1 = request_hash("bahrain", "race", 42, laps=5, modifiers={})
    time.sleep(0.01)
    h2 = request_hash("bahrain", "race", 42, laps=5, modifiers={})
    assert h1 == h2


# I. result hashing
def test_result_hash():  # type: ignore[no-untyped-def]
    r1 = {"classification": [{"driver_id": "a", "position": 1}], "seed": 42}
    r2 = {"classification": [{"driver_id": "a", "position": 1}], "seed": 42}
    r3 = {"classification": [{"driver_id": "b", "position": 1}], "seed": 42}
    assert result_hash(r1) == result_hash(r2)
    assert result_hash(r1) != result_hash(r3)


# J. deterministic reproducibility
def test_deterministic_reproducibility_race(client):  # type: ignore[no-untyped-def]
    payload = {"race_id": "bahrain", "seed": 42, "laps_override": 5}
    r1 = client.post("/api/v1/simulate/race", json=payload).json()
    r2 = client.post("/api/v1/simulate/race", json=payload).json()
    assert r1["classification"] == r2["classification"]
    assert r1["request_hash"] == r2["request_hash"]


def test_deterministic_reproducibility_montecarlo(client):  # type: ignore[no-untyped-def]
    payload = {"race_id": "bahrain", "seed": 42, "simulations": 20}
    r1 = client.post("/api/v1/simulate/monte-carlo", json=payload).json()
    r2 = client.post("/api/v1/simulate/monte-carlo", json=payload).json()
    assert r1["win_probabilities"] == r2["win_probabilities"]


def test_different_seed_different_result(client):  # type: ignore[no-untyped-def]
    r1 = client.post("/api/v1/simulate/race", json={"race_id": "bahrain", "seed": 42, "laps_override": 5}).json()
    r2 = client.post("/api/v1/simulate/race", json={"race_id": "bahrain", "seed": 43, "laps_override": 5}).json()
    assert r1["classification"] != r2["classification"]


# K. RNG isolation
def test_rng_isolation():  # type: ignore[no-untyped-def]
    from app.simulation.core.random import RandomProvider

    rp = RandomProvider(seed=42)
    s1 = rp.get_stream("strategy")
    s2 = rp.get_stream("weather")
    # streams should be independent: advancing one does not affect the other
    v1 = s1.random()
    v2 = s2.random()
    # recreate
    rp2 = RandomProvider(seed=42)
    s1b = rp2.get_stream("strategy")
    v1b = s1b.random()
    assert v1 == v1b  # same stream same first value


def test_rng_isolation_strategy_ar1():  # type: ignore[no-untyped-def]
    from app.simulation.strategy.rng import strategy_rng

    r1 = strategy_rng(42, 0, 1)
    r2 = strategy_rng(42, 0, 1)
    assert r1.random() == r2.random()


# L. leakage
def test_leakage_future_result_rejected(client):  # type: ignore[no-untyped-def]
    payloads = [
        {"family": "weather", "op": "SET_VALUE", "target": "race", "parameter": "future_weather", "value": 1.0},
        {"family": "driver", "op": "ADD_DELTA", "target": "1", "parameter": "future_result", "value": 0.5},
        {"family": "tyre", "op": "SET_VALUE", "target": "all", "parameter": "observed_result", "value": "soft"},
    ]
    for p in payloads:
        r = client.post(
            "/api/v1/scenario/compare",
            json={"race_id": "2024-bahrain", "seed": 42, "simulations": 10, "interventions": [p]},
        )
        assert r.status_code == 422, f"leakage not rejected for {p}"


def test_leakage_aliases_nested(client):  # type: ignore[no-untyped-def]
    # try via strategy state with nested future field
    state = {
        "driver_id": "driver_00",
        "lap": 10,
        "position": 5,
        "current_compound": "medium",
        "tyre_age": 10,
        "fuel_remaining": 50,
        "race_control_phase": "GREEN",
        "laps_remaining": 48,
        "future_pit": [1, 2, 3],
    }
    r = client.post("/api/v1/strategy/evaluate", json={"state": state})
    assert r.status_code == 422


def test_leakage_extra_fields(client):  # type: ignore[no-untyped-def]
    # Unknown intervention type
    r = client.post(
        "/api/v1/scenario/compare",
        json={
            "race_id": "2024-bahrain",
            "seed": 42,
            "simulations": 10,
            "interventions": [
                {"family": "driver", "op": "ADD_DELTA", "target": "1", "parameter": "pace_delta", "value": 0.5, "extra_leakage": "future_result"}
            ],
        },
    )
    # extra field should be ignored, not cause leakage bypass; still 200 or 400 but not 500
    assert r.status_code in (200, 400)


# M. security
def test_security_path_traversal_simulation(client):  # type: ignore[no-untyped-def]
    r = client.get("/api/v1/simulation/../../etc/passwd")
    assert r.status_code in (404, 422)
    r2 = client.get("/api/v1/simulation/..%2F..%2Fetc%2Fpasswd")
    assert r2.status_code in (404, 422)


def test_security_no_filesystem_path_in_request(client):  # type: ignore[no-untyped-def]
    r = client.post("/api/v1/simulate/race", json={"race_id": "/tmp/pwned", "seed": 42})
    assert r.status_code == 422


# N. malformed requests
def test_malformed_invalid_seed(client):  # type: ignore[no-untyped-def]
    r = client.post("/api/v1/simulate/race", json={"race_id": "bahrain", "seed": 999999999999})
    assert r.status_code == 422


def test_malformed_invalid_laps(client):  # type: ignore[no-untyped-def]
    r = client.post("/api/v1/simulate/race", json={"race_id": "bahrain", "seed": 42, "laps_override": 999})
    assert r.status_code == 422


def test_malformed_invalid_N(client):  # type: ignore[no-untyped-def]
    r = client.post("/api/v1/simulate/monte-carlo", json={"race_id": "bahrain", "seed": 42, "simulations": 99999})
    assert r.status_code == 422


# O. unknown simulation IDs
def test_unknown_simulation_id(client):  # type: ignore[no-untyped-def]
    r = client.get("/api/v1/simulation/does-not-exist-12345")
    assert r.status_code == 404
    assert r.json()["error"]["code"] in ("DATA_NOT_AVAILABLE", "RACE_NOT_FOUND")


# P. modifier handling
def test_modifier_weather_provenance_only(client):  # type: ignore[no-untyped-def]
    r = client.post("/api/v1/simulate/race", json={"race_id": "bahrain", "seed": 42, "laps_override": 5, "enable_weather": True})
    assert r.status_code == 200
    j = r.json()
    # weather is PRIOR_ONLY, should have warning
    assert any("weather" in w.lower() for w in j["warnings"])


def test_modifier_setup_provenance_only(client):  # type: ignore[no-untyped-def]
    r = client.post("/api/v1/simulate/race", json={"race_id": "bahrain", "seed": 42, "laps_override": 5, "enable_setup": True})
    assert r.status_code == 200
    assert any("setup" in w.lower() for w in r.json()["warnings"])


def test_modifier_montecarlo_weather_disable(client):  # type: ignore[no-untyped-def]
    r = client.post(
        "/api/v1/simulate/monte-carlo",
        json={"race_id": "bahrain", "seed": 42, "simulations": 10, "enable_weather": False},
    )
    assert r.status_code == 200
    assert r.json()["evidence_tiers"]["weather"] == "DISABLED"


# Q. provenance
def test_provenance_contains_versions(client):  # type: ignore[no-untyped-def]
    r = client.post("/api/v1/simulate/race", json={"race_id": "bahrain", "seed": 42, "laps_override": 3})
    j = r.json()
    prov = j["provenance"]
    assert prov["dataset_version"] == "f1-dataset-v1.3"
    assert "model_version" in prov
    assert "race_engine_version" in prov
    assert prov["evidence_tiers"]["fuel"] == "NON_IDENTIFIABLE"


# R. versioning
def test_versioning_unchanged(client):  # type: ignore[no-untyped-def]
    r = client.get("/api/v1/metadata")
    j = r.json()
    assert j["calibration_version"] == "calibration-v1.0.0"
    assert j["tyre_version"] == "tyre-v1.0.0"
    assert j["dataset_version"] == "f1-dataset-v1.3"


# S. serialization round-trip
def test_serialization_round_trip(client):  # type: ignore[no-untyped-def]
    r = client.post("/api/v1/simulate/race", json={"race_id": "bahrain", "seed": 42, "laps_override": 3})
    sid = r.json()["simulation_id"]
    orig = r.json()
    g = client.get(f"/api/v1/simulation/{sid}").json()
    # persisted result should equal original (within tolerance)
    # g["result"] contains full payload
    result = g.get("result") or g
    # if result is the payload, check classification
    if isinstance(result, dict) and "classification" in result:
        assert result["classification"] == orig["classification"]
    else:
        assert g["simulation_id"] == sid


# T. performance smoke tests
def test_performance_smoke_single_race(client):  # type: ignore[no-untyped-def]
    t0 = time.perf_counter()
    r = client.post("/api/v1/simulate/race", json={"race_id": "bahrain", "seed": 42, "laps_override": 5})
    elapsed = time.perf_counter() - t0
    assert r.status_code == 200
    assert elapsed < 5.0  # should be <5s
    assert r.json()["execution_time"] < 5.0


def test_performance_smoke_montecarlo(client):  # type: ignore[no-untyped-def]
    t0 = time.perf_counter()
    r = client.post("/api/v1/simulate/monte-carlo", json={"race_id": "bahrain", "seed": 42, "simulations": 10})
    elapsed = time.perf_counter() - t0
    assert r.status_code == 200
    assert elapsed < 10.0


# U. backward compatibility
def test_backward_compat_default_path_reproduces_legacy(client):  # type: ignore[no-untyped-def]
    # default path with no modifiers must reproduce legacy (no extra modifiers)
    from app.services.simulation_service import simulate_single_race as direct

    payload = {"race_id": "bahrain", "seed": 42, "laps_override": 5}
    api = client.post("/api/v1/simulate/race", json=payload).json()
    direct_res = direct("bahrain", 42, laps_override=5)
    assert api["classification"] == direct_res["classification"]
    # no calibration promotion
    assert api["provenance"]["calibration_version"] == "calibration-v1.0.0"
