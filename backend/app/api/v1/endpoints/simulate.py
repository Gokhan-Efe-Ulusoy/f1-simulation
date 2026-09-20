"""POST /simulate/race and POST /simulate/monte-carlo — Phase 30 async."""

from __future__ import annotations

import time
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks

from app.api.v1.schemas import (
    MonteCarloRequest,
    MonteCarloResponse,
    RaceSimulationRequest,
    RaceSimulationResponse,
)
from app.core.errors import ErrorCode, error_response
from app.jobs.policies import MAX_ASYNC_MONTE_CARLO, MAX_SYNC_MONTE_CARLO
from app.jobs.queue import queue
from app.services.execution import (
    build_request_hash_for_montecarlo,
    build_request_hash_for_race,
    execute_monte_carlo,
    execute_single_race,
)
from app.services.hashing import result_hash
from app.services.store import store

router = APIRouter()


def _poll_url(sid: str) -> str:
    return f"/api/v1/simulation/{sid}"


@router.post(
    "/race",
    response_model=RaceSimulationResponse,
    summary="Simulate one deterministic race",
    description="Runs the production RaceEngine. Small jobs sync; large via async queue not needed for race (always sync). Persistent store with lifecycle.",  # noqa: E501
)
async def simulate_race_endpoint(req: RaceSimulationRequest, background_tasks: BackgroundTasks) -> Any:  # noqa: ARG001
    modifiers: dict[str, Any] = {}
    if req.enable_strategy:
        modifiers["strategy"] = True
    if req.enable_setup:
        modifiers["setup"] = True
    if req.enable_weather is False:
        modifiers["weather"] = {"enabled": False}
    elif req.enable_weather is True:
        modifiers["weather"] = {"enabled": True}
    if req.enable_race_control:
        modifiers["race_control"] = True

    request_hash = build_request_hash_for_race(req.race_id, req.seed, req.laps_override, modifiers)

    # idempotency: if same request_hash COMPLETED, return existing
    existing = queue.get_by_request_hash(request_hash)
    if existing and existing["status"] == "COMPLETED" and existing["simulation_type"] == "race":
        sid = existing["simulation_id"]
        rec = store.get(sid)
        if rec:
            rec["poll_url"] = _poll_url(sid)
            return rec
        # fallback to job result
        if existing.get("result"):
            return existing["result"]

    sid = f"sim_{uuid.uuid4().hex[:12]}"
    job_id = sid
    # lifecycle QUEUED -> RUNNING
    store.create(
        {
            "simulation_id": sid,
            "job_id": job_id,
            "type": "race",
            "simulation_type": "race",
            "race_id": req.race_id,
            "seed": req.seed,
            "request_hash": request_hash,
            "status": "QUEUED",
        },
        status="QUEUED",
    )
    # also enqueue job for tracking (for metrics/cancellation even for sync)
    try:
        _prio_race = max(0, min(100, int(req.priority))) if req.priority is not None else 50
        queue.enqueue(
            {
                "job_id": job_id,
                "simulation_id": sid,
                "request_hash": request_hash,
                "simulation_type": "race",
                "race_id": req.race_id,
                "seed": req.seed,
                "sample_count": None,
                "priority": _prio_race,
            }
        )
        # claim immediately for sync
        queue.claim(f"worker_sync_{job_id[:6]}")
    except Exception:
        pass

    store.set_status(sid, "RUNNING")
    # update job progress
    try:
        queue.update_progress(job_id, 0.05, "SIMULATING")
    except Exception:
        pass

    t0 = time.perf_counter()
    try:
        result = execute_single_race(
            race_id=req.race_id,
            seed=req.seed,
            laps_override=req.laps_override,
            modifiers=modifiers,
            track_id=req.track_id,
        )
        elapsed = time.perf_counter() - t0
        result["simulation_id"] = sid
        result["job_id"] = job_id
        result["status"] = "COMPLETED"
        result["simulation_type"] = "race"
        result["request_hash"] = request_hash
        result["result_hash"] = result_hash(result)
        result["execution_time"] = elapsed
        result["poll_url"] = _poll_url(sid)
        result["progress"] = 1.0
        result["current_stage"] = "COMPLETED"
        if "execution_metadata" not in result:
            result["execution_metadata"] = {"request_hash": request_hash, "execution_time": elapsed}
        if req.save_replay:
            store.create(
                {
                    **result,
                    "simulation_id": sid,
                    "job_id": job_id,
                    "type": "race",
                    "simulation_type": "race",
                    "race_id": req.race_id,
                    "seed": req.seed,
                    "request_hash": request_hash,
                    "result_hash": result["result_hash"],
                    "execution_time": elapsed,
                },
                status="COMPLETED",
            )
        else:
            store.complete(sid, result, execution_time=elapsed)
        try:
            queue.complete(job_id, result)
        except Exception:
            pass
        return result
    except ValueError as e:
        msg = str(e)
        code = ErrorCode.INVALID_CONFIGURATION
        if "race" in msg.lower() and "not found" in msg.lower():
            code = ErrorCode.RACE_NOT_FOUND
            store.fail(sid, msg, simulation_type="race", race_id=req.race_id)
            try:
                queue.fail(job_id, msg, retryable=False)
            except Exception:
                pass
            return error_response(code, msg, status_code=404)  # type: ignore[return-value]
        if "seed" in msg.lower():
            code = ErrorCode.INVALID_SEED
        if "laps" in msg.lower():
            code = ErrorCode.INVALID_LAP_RANGE
        store.fail(sid, msg, simulation_type="race", race_id=req.race_id)
        try:
            queue.fail(job_id, msg, retryable=False)
        except Exception:
            pass
        return error_response(code, msg, status_code=400)  # type: ignore[return-value]
    except Exception as e:
        err = f"simulation failed: {e}"
        store.fail(sid, err, simulation_type="race", race_id=req.race_id)
        try:
            queue.fail(job_id, err, retryable=False)
        except Exception:
            pass
        return error_response(ErrorCode.INTERNAL_SIMULATION_ERROR, err, status_code=500)  # type: ignore[return-value]


@router.post(
    "/monte-carlo",
    response_model=MonteCarloResponse,
    summary="Run Monte Carlo simulations",
    description="Vectorized Monte Carlo. Small N sync, large N async via queue. Persistent lifecycle, idempotent, bounded.",  # noqa: E501
)
async def monte_carlo_endpoint(req: MonteCarloRequest, background_tasks: BackgroundTasks) -> Any:
    modifiers: dict[str, Any] = {}
    if req.enable_setup:
        modifiers["setup"] = True
    if req.enable_strategy:
        modifiers["strategy"] = True
    if req.enable_weather is False:
        modifiers["weather"] = {"enabled": False}
    if req.enable_race_control is False:
        modifiers["race_control"] = {"enabled": False}

    request_hash = build_request_hash_for_montecarlo(req.race_id, req.seed, req.simulations, req.laps_override, modifiers)

    # idempotency
    existing = queue.get_by_request_hash(request_hash)
    if existing:
        if existing["status"] in ("COMPLETED", "QUEUED", "RUNNING"):
            sid_exist = existing["simulation_id"]
            # if completed, return result
            if existing["status"] == "COMPLETED" and existing.get("result"):
                # try store
                rec = store.get(sid_exist)
                if rec and rec.get("win_probabilities"):
                    rec["poll_url"] = _poll_url(sid_exist)
                    rec["job_id"] = existing["job_id"]
                    return rec
                # fallback to job result
                res = existing["result"]
                if isinstance(res, str):
                    import json

                    try:
                        res = json.loads(res)
                    except Exception:
                        pass
                if isinstance(res, dict):
                    res["poll_url"] = _poll_url(sid_exist)
                    return res
            # if queued/running, return job status
            poll = _poll_url(existing["simulation_id"])
            return {
                "simulation_id": existing["simulation_id"],
                "job_id": existing["job_id"],
                "race_id": existing["race_id"],
                "seed": existing["seed"],
                "N": existing.get("sample_count"),
                "simulations": existing.get("sample_count"),
                "status": existing["status"],
                "simulation_type": "monte_carlo",
                "request_hash": request_hash,
                "poll_url": poll,
                "progress": existing.get("progress", 0.0),
                "current_stage": existing.get("current_stage", "QUEUED"),
            }

    # decide sync vs async (priority does NOT affect RNG/result)
    is_async = req.simulations > MAX_SYNC_MONTE_CARLO
    if req.simulations > MAX_ASYNC_MONTE_CARLO:
        return error_response(ErrorCode.SIMULATION_LIMIT_EXCEEDED, f"simulations {req.simulations} exceeds max async {MAX_ASYNC_MONTE_CARLO}", status_code=400)  # type: ignore[return-value]
    _prio = max(0, min(100, int(req.priority))) if req.priority is not None else 50
    _cs = int(req.chunk_size) if req.chunk_size else 500

    sid = f"sim_{uuid.uuid4().hex[:12]}"
    job_id = sid

    if is_async:
        # async path: enqueue and return QUEUED immediately
        try:
            queue.enqueue(
                {
                    "job_id": job_id,
                    "simulation_id": sid,
                    "request_hash": request_hash,
                    "simulation_type": "monte_carlo",
                    "race_id": req.race_id,
                    "seed": req.seed,
                    "sample_count": req.simulations,
                    "priority": _prio,
                    "chunk_size": _cs,
                }
            )
        except RuntimeError as e:
            if "QUEUE_FULL" in str(e):
                return error_response(ErrorCode.SIMULATION_LIMIT_EXCEEDED, "queue full, try again later", status_code=429)  # type: ignore[return-value]
            raise
        store.create(
            {
                "simulation_id": sid,
                "job_id": job_id,
                "type": "monte_carlo",
                "simulation_type": "monte_carlo",
                "race_id": req.race_id,
                "seed": req.seed,
                "request_hash": request_hash,
                "status": "QUEUED",
                "progress": 0.0,
                "current_stage": "QUEUED",
            },
            status="QUEUED",
        )

        def _bg_task() -> None:
            # background worker
            from app.jobs.worker import Worker

            w = Worker(worker_id=f"bg_{job_id[:6]}")
            # claim and execute
            claimed = queue.claim(w.worker_id)
            if not claimed:
                # try to claim our specific job
                # fallback: directly execute if not claimed
                pass
            try:
                # update progress
                queue.update_progress(job_id, 0.05, "PREPARING")
                store.set_status(sid, "RUNNING")
                queue.update_progress(job_id, 0.1, "SIMULATING")
                t0 = time.perf_counter()
                result = execute_monte_carlo(
                    race_id=req.race_id,
                    seed=req.seed,
                    simulations=req.simulations,
                    laps_override=req.laps_override,
                    modifiers=modifiers,
                    chunk_size=_cs,
                )
                elapsed = time.perf_counter() - t0
                result["simulation_id"] = sid
                result["job_id"] = job_id
                result["status"] = "COMPLETED"
                result["simulation_type"] = "monte_carlo"
                result["request_hash"] = request_hash
                result["result_hash"] = result_hash(result)
                result["execution_time"] = elapsed
                result["poll_url"] = _poll_url(sid)
                result["progress"] = 1.0
                result["current_stage"] = "COMPLETED"
                store.create(
                    {
                        **result,
                        "simulation_id": sid,
                        "job_id": job_id,
                        "type": "monte_carlo",
                        "simulation_type": "monte_carlo",
                        "race_id": req.race_id,
                        "seed": req.seed,
                        "request_hash": request_hash,
                    },
                    status="COMPLETED",
                )
                queue.complete(job_id, result)
                store.complete(sid, result, execution_time=elapsed)
            except Exception as e:
                msg = str(e)
                store.fail(sid, msg, simulation_type="monte_carlo", race_id=req.race_id)
                try:
                    from app.jobs.policies import is_retryable_error

                    queue.fail(job_id, msg, retryable=is_retryable_error(msg))
                except Exception:
                    pass

        background_tasks.add_task(_bg_task)
        return {
            "simulation_id": sid,
            "job_id": job_id,
            "race_id": req.race_id,
            "seed": req.seed,
            "N": req.simulations,
            "simulations": req.simulations,
            "status": "QUEUED",
            "simulation_type": "monte_carlo",
            "request_hash": request_hash,
            "poll_url": _poll_url(sid),
            "progress": 0.0,
            "current_stage": "QUEUED",
        }

    # sync path
    store.create(
        {
            "simulation_id": sid,
            "job_id": job_id,
            "type": "monte_carlo",
            "simulation_type": "monte_carlo",
            "race_id": req.race_id,
            "seed": req.seed,
            "request_hash": request_hash,
            "status": "QUEUED",
        },
        status="QUEUED",
    )
    try:
        queue.enqueue(
            {
                "job_id": job_id,
                "simulation_id": sid,
                "request_hash": request_hash,
                "simulation_type": "monte_carlo",
                "race_id": req.race_id,
                "seed": req.seed,
                "sample_count": req.simulations,
                "priority": _prio,
                "chunk_size": _cs,
            }
        )
        queue.claim(f"worker_sync_{job_id[:6]}")
    except Exception:
        pass
    store.set_status(sid, "RUNNING")
    try:
        queue.update_progress(job_id, 0.05, "SIMULATING")
    except Exception:
        pass
    t0 = time.perf_counter()
    try:
        result = execute_monte_carlo(
            race_id=req.race_id,
            seed=req.seed,
            simulations=req.simulations,
            laps_override=req.laps_override,
            modifiers=modifiers,
            chunk_size=_cs,
        )
        elapsed = time.perf_counter() - t0
        result["simulation_id"] = sid
        result["job_id"] = job_id
        result["status"] = "COMPLETED"
        result["simulation_type"] = "monte_carlo"
        result["request_hash"] = request_hash
        result["result_hash"] = result_hash(result)
        result["execution_time"] = elapsed
        result["poll_url"] = _poll_url(sid)
        result["progress"] = 1.0
        result["current_stage"] = "COMPLETED"
        if req.save_replay:
            store.create(
                {
                    **result,
                    "simulation_id": sid,
                    "job_id": job_id,
                    "type": "monte_carlo",
                    "simulation_type": "monte_carlo",
                    "race_id": req.race_id,
                    "seed": req.seed,
                    "request_hash": request_hash,
                    "result_hash": result["result_hash"],
                    "execution_time": elapsed,
                },
                status="COMPLETED",
            )
        else:
            store.complete(sid, result, execution_time=elapsed)
        try:
            queue.complete(job_id, result)
        except Exception:
            pass
        return result
    except ValueError as e:
        msg = str(e)
        if "simulations" in msg.lower():
            store.fail(sid, msg, simulation_type="monte_carlo", race_id=req.race_id)
            try:
                queue.fail(job_id, msg, retryable=False)
            except Exception:
                pass
            return error_response(ErrorCode.SIMULATION_LIMIT_EXCEEDED, msg, status_code=400)  # type: ignore[return-value]
        if "seed" in msg.lower():
            store.fail(sid, msg, simulation_type="monte_carlo", race_id=req.race_id)
            try:
                queue.fail(job_id, msg, retryable=False)
            except Exception:
                pass
            return error_response(ErrorCode.INVALID_SEED, msg, status_code=400)  # type: ignore[return-value]
        if "laps" in msg.lower():
            store.fail(sid, msg, simulation_type="monte_carlo", race_id=req.race_id)
            try:
                queue.fail(job_id, msg, retryable=False)
            except Exception:
                pass
            return error_response(ErrorCode.INVALID_LAP_RANGE, msg, status_code=400)  # type: ignore[return-value]
        store.fail(sid, msg, simulation_type="monte_carlo", race_id=req.race_id)
        try:
            queue.fail(job_id, msg, retryable=False)
        except Exception:
            pass
        return error_response(ErrorCode.INVALID_CONFIGURATION, msg, status_code=400)  # type: ignore[return-value]
    except Exception as e:
        err = f"monte carlo failed: {e}"
        store.fail(sid, err, simulation_type="monte_carlo", race_id=req.race_id)
        try:
            queue.fail(job_id, err, retryable=False)
        except Exception:
            pass
        return error_response(ErrorCode.INTERNAL_SIMULATION_ERROR, err, status_code=500)  # type: ignore[return-value]
