"""Phase 32 — API contract tests (frontend schema → validation → service → engine)."""
from fastapi.testclient import TestClient

from app.main import create_app

client = TestClient(create_app())


def _race_id():
    r = client.get("/api/v1/races?limit=1")
    assert r.status_code == 200
    return r.json()["races"][0]["race_id"]


def test_01_valid_race_request():
    rid = _race_id()
    r = client.post("/api/v1/simulate/race", json={"race_id": rid, "seed": 42})
    assert r.status_code == 200
    assert r.json()["classification"]


def test_02_invalid_race():
    r = client.post(
        "/api/v1/simulate/race",
        json={"race_id": "no-such-race-xyz", "seed": 42},
    )
    # unknown race falls back to synthetic track OR 404; both structured
    assert r.status_code in (200, 404)
    if r.status_code == 404:
        assert r.json()["error"]["code"] == "RACE_NOT_FOUND"


def test_03_invalid_seed():
    rid = _race_id()
    r = client.post(
        "/api/v1/simulate/race",
        json={"race_id": rid, "seed": 9999999999},
    )
    assert r.status_code == 422


def test_04_invalid_laps():
    rid = _race_id()
    r = client.post(
        "/api/v1/simulate/race",
        json={"race_id": rid, "seed": 42, "laps_override": 999},
    )
    assert r.status_code == 422


def test_05_invalid_mc_n():
    rid = _race_id()
    r = client.post(
        "/api/v1/simulate/monte-carlo",
        json={"race_id": rid, "seed": 42, "simulations": 99999},
    )
    assert r.status_code == 422


def test_06_async_job_submission():
    rid = _race_id()
    r = client.post(
        "/api/v1/simulate/monte-carlo",
        json={"race_id": rid, "seed": 42, "simulations": 1500},
    )
    assert r.status_code == 200
    assert r.json()["status"] in ("QUEUED", "COMPLETED", "RUNNING")


def test_07_polling():
    rid = _race_id()
    sub = client.post(
        "/api/v1/simulate/race", json={"race_id": rid, "seed": 42}
    ).json()
    g = client.get(f"/api/v1/simulation/{sub['simulation_id']}")
    assert g.status_code == 200
    assert g.json()["status"].upper() in (
        "COMPLETED",
        "QUEUED",
        "RUNNING",
        "FAILED",
        "CANCELLED",
        "TIMEOUT",
    )


def test_08_completed_result():
    rid = _race_id()
    sub = client.post(
        "/api/v1/simulate/race", json={"race_id": rid, "seed": 42}
    ).json()
    assert sub["status"] == "COMPLETED"
    assert sub["provenance"]["dataset_version"] == "f1-dataset-v1.3"


def test_09_failed_result_structured():
    g = client.get("/api/v1/simulation/does-not-exist-xyz")
    assert g.status_code == 404
    assert "error" in g.json()


def test_10_duplicate_request():
    rid = _race_id()
    payload = {"race_id": rid, "seed": 42, "simulations": 10}
    a = client.post("/api/v1/simulate/monte-carlo", json=payload).json()
    b = client.post("/api/v1/simulate/monte-carlo", json=payload).json()
    assert a["request_hash"] == b["request_hash"]


def test_11_scenario_validation():
    rid = _race_id()
    r = client.post(
        "/api/v1/scenario/compare",
        json={
            "race_id": rid,
            "seed": 42,
            "simulations": 10,
            "interventions": [
                {
                    "family": "driver",
                    "op": "ADD_DELTA",
                    "target": "all",
                    "parameter": "pace_delta",
                    "value": 0.1,
                }
            ],
        },
    )
    assert r.status_code in (200, 400)


def test_12_leakage_rejection():
    rid = _race_id()
    r = client.post(
        "/api/v1/scenario/compare",
        json={
            "race_id": rid,
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
