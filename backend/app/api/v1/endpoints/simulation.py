"""GET /simulation/{simulation_id} and POST /simulation/{id}/cancel — Phase 30."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.core.errors import ErrorCode, error_response
from app.jobs.queue import queue
from app.services.store import store

router = APIRouter()


@router.get(
    "/{simulation_id}",
    summary="Get simulation result by ID",
    description="Retrieve persisted result (DB primary) or job status. Exposes progress, stage, attempt, error. Sanitized errors.",  # noqa: E501
)
async def get_simulation_endpoint(simulation_id: str) -> Any:
    if (
        ".." in simulation_id
        or "/" in simulation_id
        or "\\" in simulation_id
        or len(simulation_id) > 200
    ):
        return error_response(ErrorCode.VALIDATION_ERROR, "invalid simulation_id", status_code=422)  # type: ignore[return-value]  # noqa: E501
    # try job queue first (has progress, stage, etc.)
    job = queue.get_status(simulation_id)
    if job:
        # also try store for result
        rec = store.get(simulation_id)
        result = rec.get("result") if rec and isinstance(rec.get("result"), dict) else rec
        # if job has result, prefer job result
        if job.get("result"):
            result = job["result"]
        elif rec and isinstance(rec, dict) and rec.get("classification"):
            result = rec
        return {
            "simulation_id": job["simulation_id"],
            "job_id": job["job_id"],
            "status": job["status"],
            "simulation_type": job.get("simulation_type"),
            "request_hash": job.get("request_hash"),
            "progress": job.get("progress", 0.0),
            "current_stage": job.get("current_stage"),
            "created_at": job.get("created_at"),
            "queued_at": job.get("created_at"),
            "started_at": job.get("started_at"),
            "completed_at": job.get("completed_at"),
            "failed_at": job.get("failed_at"),
            "cancelled_at": job.get("cancelled_at"),
            "timed_out_at": job.get("timed_out_at"),
            "heartbeat_at": job.get("heartbeat_at"),
            "attempt": job.get("attempt"),
            "max_attempts": job.get("max_attempts"),
            "priority": job.get("priority"),
            "result": result,
            "result_hash": job.get("result_hash"),
            "error": job.get("error"),
            "race_id": job.get("race_id"),
            "seed": job.get("seed"),
            "poll_url": f"/api/v1/simulation/{job['simulation_id']}",
            "chunk_count": job.get("chunk_count"),
            "completed_chunks": job.get("completed_chunks"),
            "total_chunks": job.get("total_chunks"),
            "chunk_size": job.get("chunk_size"),
        }
    rec = store.get(simulation_id)
    if not rec:
        return error_response(
            ErrorCode.DATA_NOT_AVAILABLE,
            f"simulation {simulation_id!r} not found",
            status_code=404,
            details={"simulation_id": simulation_id},
        )  # type: ignore[return-value]
    # Normalize to job response shape for backward compat
    status = rec.get("status", "COMPLETED")
    # ensure uppercase for Phase30 but compat lower
    status_upper = str(status).upper()
    return {
        "simulation_id": simulation_id,
        "job_id": rec.get("job_id") or rec.get("simulation_id"),
        "status": status_upper,
        "simulation_type": rec.get("simulation_type") or rec.get("type"),
        "request_hash": rec.get("request_hash"),
        "result_hash": rec.get("result_hash"),
        "progress": 1.0 if status_upper == "COMPLETED" else 0.0,
        "current_stage": status_upper,
        "result": rec,
        "created_at": rec.get("created_at"),
        "started_at": rec.get("started_at"),
        "completed_at": rec.get("completed_at"),
        "error": rec.get("error"),
        "race_id": rec.get("race_id"),
        "seed": rec.get("seed"),
        "poll_url": f"/api/v1/simulation/{simulation_id}",
    }


@router.post(
    "/{simulation_id}/cancel",
    summary="Cancel simulation job",
    description="Cooperative cancellation: QUEUED -> CANCELLED immediately; RUNNING requests cancellation at next safe boundary (batch/lap). Honest if not cancellable.",  # noqa: E501
)
async def cancel_simulation_endpoint(simulation_id: str) -> Any:
    if (
        ".." in simulation_id
        or "/" in simulation_id
        or "\\" in simulation_id
        or len(simulation_id) > 200
    ):
        return error_response(ErrorCode.VALIDATION_ERROR, "invalid simulation_id", status_code=422)  # type: ignore[return-value]  # noqa: E501
    # try job queue
    job = queue.get_status(simulation_id)
    if job:
        ok = queue.cancel(simulation_id)
        if ok:
            # also update store
            store.set_status(simulation_id, "CANCELLED")
            updated = queue.get_status(simulation_id)
            return {
                "simulation_id": simulation_id,
                "job_id": simulation_id,
                "status": updated["status"] if updated else "CANCELLED",
                "cancelled": True,
            }
        return error_response(ErrorCode.INVALID_CONFIGURATION, f"cannot cancel job in status {job['status']}", status_code=400)  # type: ignore[return-value]
    # fallback to store
    rec = store.get(simulation_id)
    if not rec:
        return error_response(ErrorCode.DATA_NOT_AVAILABLE, f"simulation {simulation_id!r} not found", status_code=404, details={"simulation_id": simulation_id})  # type: ignore[return-value]
    status = str(rec.get("status", "")).upper()
    if status == "QUEUED":
        store.set_status(simulation_id, "CANCELLED")
        return {"simulation_id": simulation_id, "job_id": simulation_id, "status": "CANCELLED", "cancelled": True}
    return error_response(ErrorCode.INVALID_CONFIGURATION, f"cannot cancel job in status {status}", status_code=400)  # type: ignore[return-value]
