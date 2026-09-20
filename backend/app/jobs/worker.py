"""Phase 30 — Worker abstraction."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

from app.jobs.cancellation import clear_cancellation, is_cancelled
from app.jobs.models import JobRecord
from app.jobs.policies import is_retryable_error
from app.jobs.queue import queue
from app.services.execution import execute_monte_carlo, execute_single_race
from app.services.hashing import result_hash
from app.core.database import SessionLocal


class Worker:
    def __init__(self, worker_id: str | None = None):
        self.worker_id = worker_id or f"worker_{uuid.uuid4().hex[:8]}"

    def _log(self, event: str, job: dict[str, Any] | None = None, **extra: Any) -> None:
        # structured logging
        payload = {
            "event": event,
            "worker_id": self.worker_id,
            "job_id": job.get("job_id") if job else None,
            "simulation_id": job.get("simulation_id") if job else None,
            "request_hash": job.get("request_hash") if job else None,
            "simulation_type": job.get("simulation_type") if job else None,
            "attempt": job.get("attempt") if job else None,
        }
        payload.update(extra)
        print(f"[worker] {event} {payload}")

    def process_one(self) -> bool:
        job = queue.claim(self.worker_id)
        if not job:
            return False
        self._log("job_claimed", job)
        queue.update_progress(job["job_id"], 0.05, "PREPARING")
        if is_cancelled(job["job_id"]):
            self._cancel_job(job)
            return True
        # timeout enforcement: record start
        import time as _time

        _t0 = _time.perf_counter()
        try:
            from app.core.settings import settings as _s

            _max_runtime = int(getattr(_s, "MAX_JOB_RUNTIME_SECONDS", 300))
        except Exception:
            _max_runtime = 300
        try:
            result = self._execute(job)
            # check timeout after execution (if exceeded, mark TIMEOUT not COMPLETED)
            try:
                _elapsed = _time.perf_counter() - _t0
                if _elapsed > _max_runtime:
                    try:
                        queue.timeout_job(job["job_id"], reason=f"job exceeded {_max_runtime}s")
                    except Exception:
                        pass
                    self._log("job_timeout", job, elapsed=_elapsed)
                    clear_cancellation(job["job_id"])
                    return True
            except Exception:
                pass
            if is_cancelled(job["job_id"]):
                self._cancel_job(job)
                return True
            # progress normalizing
            queue.update_progress(job["job_id"], 0.95, "NORMALIZING")
            # persist result
            queue.update_progress(job["job_id"], 0.98, "STORING")
            # also persist to SimulationRecord for GET /simulation compatibility
            self._persist_simulation(job, result)
            queue.complete(job["job_id"], result)
            clear_cancellation(job["job_id"])
            self._log("job_completed", job, result_hash=result_hash(result))
            return True
        except Exception as e:
            msg = str(e)
            # never expose stack trace to client, log internally
            print(f"[worker] job_failed {job['job_id']} error={msg}")
            retryable = is_retryable_error(msg)
            queue.fail(job["job_id"], msg, retryable=retryable)
            clear_cancellation(job["job_id"])
            self._log("job_failed", job, error=msg, retryable=retryable)
            return True

    def _cancel_job(self, job: dict[str, Any]) -> None:
        from datetime import datetime, timezone

        session = SessionLocal()
        try:
            rec = session.get(JobRecord, job["job_id"])
            if rec and rec.status == "RUNNING":
                rec.status = "CANCELLED"
                rec.cancelled_at = datetime.now(timezone.utc)
                rec.current_stage = "CANCELLED"
                rec.progress = 0.0
                session.commit()
                self._log("job_cancelled", job)
        finally:
            session.close()
        clear_cancellation(job["job_id"])

    def _execute(self, job: dict[str, Any]) -> dict[str, Any]:
        sim_type = job.get("simulation_type")
        race_id = job.get("race_id")
        seed = job.get("seed")
        sample_count = job.get("sample_count")
        # check cancellation at safe boundary before execution
        if is_cancelled(job["job_id"]):
            raise RuntimeError("cancelled before execution")
        if sim_type == "race":
            queue.update_progress(job["job_id"], 0.05, "SIMULATING")
            # chunking not needed for single race
            result = execute_single_race(race_id=race_id, seed=seed, laps_override=None, modifiers=None)
            return result
        elif sim_type == "monte_carlo":
            # Phase 31 deterministic chunked execution (global-index RNG, order/worker independent)
            total = int(sample_count or 1000)
            try:
                from app.core.settings import settings as _settings

                default_cs = int(getattr(_settings, "MONTECARLO_CHUNK_SIZE", 500))
            except Exception:
                default_cs = 500
            # job may carry chunk_size
            try:
                chunk_size = int(job.get("chunk_size") or default_cs)
            except Exception:
                chunk_size = default_cs
            chunk_size = max(1, min(5000, chunk_size))
            # progress per chunk, cancellation at chunk boundaries, timeout via heartbeat
            import math as _math

            num_chunks = _math.ceil(total / chunk_size) if total else 1
            # update job chunk metadata
            try:
                from app.core.database import SessionLocal as _SL
                from app.jobs.models import JobRecord as _JR

                _s = _SL()
                try:
                    _rec = _s.get(_JR, job["job_id"])
                    if _rec:
                        _rec.chunk_size = chunk_size
                        _rec.chunk_count = num_chunks
                        _rec.total_chunks = num_chunks
                        _rec.completed_chunks = 0
                        _s.commit()
                finally:
                    _s.close()
            except Exception:
                pass

            def _progress(frac: float, stage: str) -> None:
                # frac 0..1 within SIMULATING 0.05-0.95
                try:
                    p = 0.05 + frac * 0.90
                    queue.update_progress(job["job_id"], p, stage)
                except Exception:
                    pass

            def _cancel() -> bool:
                return bool(is_cancelled(job["job_id"]))

            if _cancel():
                raise RuntimeError("cancelled before execution")
            queue.update_progress(job["job_id"], 0.05, "SIMULATING")
            # Use chunked service path for determinism (identical to unchunked)
            result = execute_monte_carlo(
                race_id=race_id,
                seed=seed,
                simulations=total,
                laps_override=None,
                modifiers=None,
                chunk_size=chunk_size,
                progress_callback=_progress,
                cancel_check=_cancel,
            )
            # record completed chunks
            try:
                from app.core.database import SessionLocal as _SL2
                from app.jobs.models import JobRecord as _JR2

                _s2 = _SL2()
                try:
                    _rec2 = _s2.get(_JR2, job["job_id"])
                    if _rec2:
                        _rec2.completed_chunks = num_chunks
                        _s2.commit()
                finally:
                    _s2.close()
            except Exception:
                pass
            return result
        elif sim_type == "scenario":
            # scenario: need interventions from job payload (stored in result field as request)
            # For now, use stored request
            raise RuntimeError("scenario async not yet implemented")
        else:
            raise RuntimeError(f"unsupported simulation_type {sim_type}")

    def _persist_simulation(self, job: dict[str, Any], result: dict[str, Any]) -> None:
        # also write to SimulationRecord for GET /simulation/{simulation_id} compatibility
        from app.services.store import store

        sid = job.get("simulation_id")
        result["simulation_id"] = sid
        result["request_hash"] = job.get("request_hash")
        store.create(
            {
                **result,
                "simulation_id": sid,
                "type": job.get("simulation_type"),
                "simulation_type": job.get("simulation_type"),
                "race_id": job.get("race_id"),
                "seed": job.get("seed"),
                "request_hash": job.get("request_hash"),
            },
            status="COMPLETED",
        )

    def run_loop(self, poll_interval: float = 1.0, max_jobs: int | None = None) -> int:
        count = 0
        while True:
            if not self.process_one():
                break
            count += 1
            if max_jobs and count >= max_jobs:
                break
            time.sleep(poll_interval)
        return count
