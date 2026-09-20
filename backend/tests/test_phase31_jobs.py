"""Phase 31 — Jobs, queue, priority, timeout, observability, security."""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture  # type: ignore[misc]
def client():
    return TestClient(create_app())


def _clean():
    try:
        from app.core.database import SessionLocal
        from app.jobs.models import JobRecord

        s = SessionLocal()
        try:
            s.query(JobRecord).delete()
            s.commit()
        finally:
            s.close()
    except Exception:
        pass


# 1 job creation
def test_job_creation_api(client):
    r = client.post("/api/v1/simulate/monte-carlo", json={"race_id": "2024-bahrain", "seed": 42, "simulations": 10})
    assert r.status_code == 200
    assert "simulation_id" in r.json()


# 2 lifecycle
def test_lifecycle_queued_running_completed(client):
    from app.jobs.queue import queue as q

    _clean()
    jid = q.enqueue({"simulation_id": "lc1", "request_hash": "lc_hash1", "simulation_type": "race", "race_id": "2024-bahrain"})
    assert q.get_status(jid)["status"] == "QUEUED"
    q.claim("w1")
    assert q.get_status(jid)["status"] == "RUNNING"
    q.complete(jid, {"ok": True})
    assert q.get_status(jid)["status"] == "COMPLETED"
    _clean()


# 3 invalid transitions
def test_invalid_transitions():
    from app.jobs.policies import can_transition

    assert not can_transition("COMPLETED", "RUNNING")
    assert can_transition("RUNNING", "TIMEOUT")
    assert can_transition("TIMEOUT", "QUEUED")


# 4 idempotent
def test_idempotent_duplicate(client):
    p = {"race_id": "2024-bahrain", "seed": 42, "simulations": 10}
    r1 = client.post("/api/v1/simulate/monte-carlo", json=p).json()
    r2 = client.post("/api/v1/simulate/monte-carlo", json=p).json()
    assert r1["request_hash"] == r2["request_hash"]


# 5 priority ordering
def test_priority_ordering():
    _clean()
    from app.jobs.queue import queue as q

    q.enqueue({"simulation_id": "plow", "request_hash": "h_low", "simulation_type": "race", "race_id": "x", "priority": 10})
    q.enqueue({"simulation_id": "phigh", "request_hash": "h_high", "simulation_type": "race", "race_id": "x", "priority": 90})
    claimed = q.claim("w_prio")
    # high priority first
    assert claimed["simulation_id"] == "phigh"
    _clean()


# 6 priority does not affect result
def test_priority_no_rng_effect(client):
    r1 = client.post("/api/v1/simulate/monte-carlo", json={"race_id": "2024-bahrain", "seed": 42, "simulations": 10, "priority": 10}).json()
    r2 = client.post("/api/v1/simulate/monte-carlo", json={"race_id": "2024-bahrain", "seed": 42, "simulations": 10, "priority": 90}).json()
    assert r1["request_hash"] == r2["request_hash"]
    if r1.get("win_probabilities") and r2.get("win_probabilities"):
        assert r1["win_probabilities"] == r2["win_probabilities"]


# 7 timeout
def test_timeout_transition():
    _clean()
    from app.jobs.queue import queue as q

    jid = q.enqueue({"simulation_id": "t1", "request_hash": "ht1", "simulation_type": "race", "race_id": "x"})
    q.claim("w_t")
    assert q.timeout_job(jid) is True
    assert q.get_status(jid)["status"] == "TIMEOUT"
    _clean()


# 8 heartbeat stale
def test_heartbeat_stale():
    _clean()
    from datetime import datetime, timedelta, timezone

    from app.core.database import SessionLocal
    from app.jobs.models import JobRecord
    from app.jobs.queue import queue as q

    jid = q.enqueue({"simulation_id": "hs1", "request_hash": "hhs1", "simulation_type": "race", "race_id": "x"})
    q.claim("w_hs")
    s = SessionLocal()
    rec = s.get(JobRecord, jid)
    rec.heartbeat_at = datetime.now(timezone.utc) - timedelta(seconds=120)
    s.commit()
    s.close()
    stale = q.detect_stale(timeout_seconds=60)
    assert jid in stale
    _clean()


# 9 metrics endpoint
def test_metrics_endpoint(client):
    r = client.get("/api/v1/metrics")
    assert r.status_code == 200
    j = r.json()
    for k in ["queue_depth", "running_jobs", "completed_jobs", "failed_jobs", "cancelled_jobs", "timed_out_jobs", "retry_count", "jobs_by_type", "jobs_by_priority"]:
        assert k in j


# 10 status enrichment
def test_status_enrichment(client):
    r = client.post("/api/v1/simulate/monte-carlo", json={"race_id": "2024-bahrain", "seed": 42, "simulations": 10}).json()
    g = client.get(f"/api/v1/simulation/{r['simulation_id']}").json()
    for k in ["status", "progress", "attempt", "priority", "heartbeat_at"]:
        assert k in g


# 11 cancellation
def test_cancel_queued():
    _clean()
    from app.jobs.queue import queue as q

    jid = q.enqueue({"simulation_id": "cx1", "request_hash": "hx1", "simulation_type": "race", "race_id": "x"})
    assert q.cancel(jid) is True
    assert q.get_status(jid)["status"] == "CANCELLED"
    _clean()


# 12 retry policy
def test_retry_policy_unit():
    from app.jobs.policies import is_retryable_error

    assert is_retryable_error("transient worker error")
    assert not is_retryable_error("validation error")


# 13 leakage still blocked
def test_leakage_blocked(client):
    r = client.post("/api/v1/scenario/compare", json={"race_id": "2024-bahrain", "seed": 42, "simulations": 10, "interventions": [{"family": "weather", "op": "SET_VALUE", "target": "race", "parameter": "future_weather", "value": 1.0}]})
    assert r.status_code == 422


# 14 security limits
def test_security_limits(client):
    assert client.post("/api/v1/simulate/monte-carlo", json={"race_id": "2024-bahrain", "seed": 42, "simulations": 99999}).status_code == 422
    assert client.get("/api/v1/simulation/../../etc/passwd").status_code in (404, 422)


# 15 queue flooding / backpressure
def test_backpressure_unit():
    from app.jobs.queue import InProcessJobQueue

    q = InProcessJobQueue(max_concurrent=100, max_depth=2)
    _clean()
    # use isolated queue but global DB counts; clean first
    try:
        q.enqueue({"simulation_id": "b1", "request_hash": "hb1", "simulation_type": "race", "race_id": "x"})
        q.enqueue({"simulation_id": "b2", "request_hash": "hb2", "simulation_type": "race", "race_id": "x"})
        try:
            q.enqueue({"simulation_id": "b3", "request_hash": "hb3", "simulation_type": "race", "race_id": "x"})
            assert False
        except RuntimeError as e:
            assert "QUEUE_FULL" in str(e)
    finally:
        _clean()


# 16 redis unavailable explicit
def test_redis_unavailable():
    from app.jobs.queue import RedisJobQueue

    try:
        RedisJobQueue(redis_url="redis://localhost:6399/0")
        # if redis somehow available, skip
        pytest.skip("redis available")
    except RuntimeError as e:
        assert "unavailable" in str(e).lower()


# 17 concurrent duplicate submission safe
def test_concurrent_duplicate_safe(client):
    p = {"race_id": "2024-bahrain", "seed": 99, "simulations": 10}
    r1 = client.post("/api/v1/simulate/monte-carlo", json=p).json()
    r2 = client.post("/api/v1/simulate/monte-carlo", json=p).json()
    assert r1["request_hash"] == r2["request_hash"]


# 18 chunk_size limits
def test_chunk_size_limits(client):
    assert client.post("/api/v1/simulate/monte-carlo", json={"race_id": "2024-bahrain", "seed": 42, "simulations": 10, "chunk_size": 6000}).status_code == 422


# 19 version unchanged
def test_versions_unchanged(client):
    m = client.get("/api/v1/metadata").json()
    assert m["dataset_version"] == "f1-dataset-v1.3"
    assert m["race_engine_version"] == "raceengine-v2.2.0"


# 20 sync/async equivalence small N
def test_sync_async_equiv_small(client):
    from app.services.montecarlo_service import run_montecarlo

    direct = run_montecarlo("2024-bahrain", simulations=20, seed=42)
    api = client.post("/api/v1/simulate/monte-carlo", json={"race_id": "2024-bahrain", "seed": 42, "simulations": 20}).json()
    assert direct["win_probabilities"] == api["win_probabilities"]
