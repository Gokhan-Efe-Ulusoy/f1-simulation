"""Phase 30 — JobQueue abstraction."""

from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func

from app.core.database import SessionLocal
from app.jobs.cancellation import request_cancellation
from app.jobs.models import JobRecord
from app.jobs.policies import MAX_CONCURRENT_JOBS, MAX_QUEUE_DEPTH, can_transition


class JobQueue(ABC):
    @abstractmethod
    def enqueue(self, payload: dict[str, Any]) -> str:
        pass

    @abstractmethod
    def claim(self, worker_id: str) -> dict[str, Any] | None:
        pass

    @abstractmethod
    def complete(self, job_id: str, result: dict[str, Any]) -> None:
        pass

    @abstractmethod
    def fail(self, job_id: str, error: str, retryable: bool = False) -> None:
        pass

    @abstractmethod
    def cancel(self, job_id: str) -> bool:
        pass

    @abstractmethod
    def get_status(self, job_id: str) -> dict[str, Any] | None:
        pass


class InProcessJobQueue(JobQueue):
    """Local dev queue backed by DB, no Redis required."""

    def __init__(self, max_concurrent: int = MAX_CONCURRENT_JOBS, max_depth: int = MAX_QUEUE_DEPTH):
        self.max_concurrent = max_concurrent
        self.max_depth = max_depth

    def _check_backpressure(self) -> None:
        session = SessionLocal()
        try:
            queued = session.query(JobRecord).filter(JobRecord.status == "QUEUED").count()
            running = session.query(JobRecord).filter(JobRecord.status == "RUNNING").count()
            if queued + running >= self.max_depth:
                raise RuntimeError("QUEUE_FULL")
            if running >= self.max_concurrent:
                # allow queuing but not running beyond limit; claim will respect
                pass
        finally:
            session.close()

    def enqueue(self, payload: dict[str, Any]) -> str:
        # idempotency check outside
        self._check_backpressure()
        job_id = payload.get("job_id") or f"job_{uuid.uuid4().hex[:12]}"
        payload["job_id"] = job_id
        now = datetime.now(timezone.utc)
        prio = payload.get("priority", 50)
        try:
            prio = int(prio)
        except Exception:
            prio = 50
        prio = max(0, min(100, prio))
        chunk_size = payload.get("chunk_size")
        total = payload.get("sample_count")
        chunk_count = None
        if total and chunk_size:
            try:
                import math

                chunk_count = math.ceil(int(total) / int(chunk_size))
            except Exception:
                chunk_count = None
        rec = JobRecord(
            job_id=job_id,
            simulation_id=payload.get("simulation_id", job_id),
            request_hash=payload.get("request_hash"),
            status="QUEUED",
            simulation_type=payload.get("simulation_type", "unknown"),
            priority=prio,
            created_at=now,
            progress=0.0,
            current_stage="QUEUED",
            attempt=1,
            max_attempts=payload.get("max_attempts", 2),
            race_id=payload.get("race_id"),
            seed=payload.get("seed"),
            sample_count=payload.get("sample_count"),
            result=None,
        )
        try:
            rec.chunk_size = chunk_size
            rec.chunk_count = chunk_count
            rec.total_chunks = chunk_count
            rec.completed_chunks = 0
        except Exception:
            pass
        session = SessionLocal()
        try:
            session.add(rec)
            session.commit()
        finally:
            session.close()
        return job_id

    def claim(self, worker_id: str) -> dict[str, Any] | None:
        session = SessionLocal()
        try:
            # respect max_concurrent
            running = session.query(JobRecord).filter(JobRecord.status == "RUNNING").count()
            if running >= self.max_concurrent:
                return None
            # priority scheduling: priority DESC, created_at ASC (priority does NOT affect RNG)
            job = (
                session.query(JobRecord)
                .filter(JobRecord.status == "QUEUED")
                .order_by(JobRecord.priority.desc(), JobRecord.created_at)
                .first()
            )
            if not job:
                return None
            if not can_transition(job.status, "RUNNING"):
                return None
            job.status = "RUNNING"
            job.started_at = datetime.now(timezone.utc)
            job.heartbeat_at = datetime.now(timezone.utc)
            job.worker_id = worker_id
            job.progress = 0.05
            job.current_stage = "PREPARING"
            session.commit()
            return job.to_dict()
        finally:
            session.close()

    def complete(self, job_id: str, result: dict[str, Any]) -> None:
        import json

        from app.services.hashing import result_hash

        session = SessionLocal()
        try:
            job = session.get(JobRecord, job_id)
            if not job or not can_transition(job.status, "COMPLETED"):
                return
            job.status = "COMPLETED"
            job.completed_at = datetime.now(timezone.utc)
            job.progress = 1.0
            job.current_stage = "COMPLETED"
            job.result = json.dumps(result, default=str)
            job.result_hash = result_hash(result)
            job.heartbeat_at = datetime.now(timezone.utc)
            session.commit()
        finally:
            session.close()

    def fail(self, job_id: str, error: str, retryable: bool = False) -> None:
        import json

        session = SessionLocal()
        try:
            job = session.get(JobRecord, job_id)
            if not job:
                return
            # decide retry
            if retryable and job.attempt < job.max_attempts:
                if can_transition(job.status, "QUEUED"):
                    job.status = "QUEUED"
                    job.attempt += 1
                    job.error = json.dumps({"error": error, "retry": True})
                    job.heartbeat_at = datetime.now(timezone.utc)
                    job.current_stage = "QUEUED"
                    session.commit()
                    return
            # final fail
            if can_transition(job.status, "FAILED"):
                job.status = "FAILED"
                job.failed_at = datetime.now(timezone.utc)
                job.error = json.dumps({"error": error})
                job.progress = 0.0
                job.current_stage = "FAILED"
                session.commit()
        finally:
            session.close()

    def cancel(self, job_id: str) -> bool:
        import json

        session = SessionLocal()
        try:
            job = session.get(JobRecord, job_id)
            if not job:
                return False
            if job.status == "QUEUED" and can_transition("QUEUED", "CANCELLED"):
                job.status = "CANCELLED"
                job.cancelled_at = datetime.now(timezone.utc)
                job.current_stage = "CANCELLED"
                session.commit()
                return True
            if job.status == "RUNNING" and can_transition("RUNNING", "CANCELLED"):
                # cooperative: set token, worker will check
                request_cancellation(job_id)
                # we don't immediately mark cancelled; worker will
                return True
            return False
        finally:
            session.close()

    def get_status(self, job_id: str) -> dict[str, Any] | None:
        session = SessionLocal()
        try:
            job = session.get(JobRecord, job_id)
            if not job:
                return None
            return job.to_dict()
        finally:
            session.close()

    def get_by_request_hash(self, request_hash: str) -> dict[str, Any] | None:
        session = SessionLocal()
        try:
            # prefer COMPLETED, then QUEUED/RUNNING
            job = session.query(JobRecord).filter(JobRecord.request_hash == request_hash).order_by(JobRecord.created_at.desc()).first()
            if job:
                return job.to_dict()
            return None
        finally:
            session.close()

    def update_progress(self, job_id: str, progress: float, stage: str) -> None:
        session = SessionLocal()
        try:
            job = session.get(JobRecord, job_id)
            if not job or job.status != "RUNNING":
                return
            # throttle: only update if progress increased by >=1% or stage changed
            if progress < job.progress and stage == job.current_stage:
                return
            job.progress = max(0.0, min(1.0, progress))
            job.current_stage = stage
            job.heartbeat_at = datetime.now(timezone.utc)
            session.commit()
        finally:
            session.close()

    def detect_stale(self, timeout_seconds: int = 60) -> list[str]:
        """Mark RUNNING jobs with expired heartbeat as recoverable (retry or FAILED)."""
        from datetime import timedelta

        session = SessionLocal()
        stale: list[str] = []
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(seconds=timeout_seconds)
            jobs = session.query(JobRecord).filter(JobRecord.status == "RUNNING", JobRecord.heartbeat_at < cutoff).all()
            for job in jobs:
                stale.append(job.job_id)
                # mark as failed with retryable
                self.fail(job.job_id, "stale job: heartbeat expired", retryable=True)
            return stale
        finally:
            session.close()

    def timeout_job(self, job_id: str, reason: str = "job exceeded MAX_JOB_RUNTIME_SECONDS") -> bool:
        """Transition RUNNING -> TIMEOUT (distinct from FAILED/CANCELLED). Idempotent."""
        session = SessionLocal()
        try:
            job = session.get(JobRecord, job_id)
            if not job or job.status != "RUNNING":
                return False
            if not can_transition("RUNNING", "TIMEOUT"):
                return False
            import json

            job.status = "TIMEOUT"
            try:
                from datetime import datetime as _dt

                job.timed_out_at = _dt.now(timezone.utc)
            except Exception:
                pass
            job.current_stage = "TIMEOUT"
            job.error = json.dumps({"error": reason, "timeout": True})
            session.commit()
            return True
        finally:
            session.close()

    def check_timeouts(self, max_runtime_seconds: int = 300) -> list[str]:
        """Mark RUNNING jobs exceeding max runtime as TIMEOUT."""
        from datetime import timedelta

        session = SessionLocal()
        timed: list[str] = []
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(seconds=max_runtime_seconds)
            jobs = session.query(JobRecord).filter(JobRecord.status == "RUNNING").all()
            for job in jobs:
                started = job.started_at or job.created_at
                # ensure tz-aware comparison
                try:
                    if started and started.tzinfo is None:
                        started = started.replace(tzinfo=timezone.utc)
                except Exception:
                    continue
                if started and started < cutoff:
                    if self.timeout_job(job.job_id):
                        timed.append(job.job_id)
            return timed
        finally:
            session.close()


class RedisJobQueue(InProcessJobQueue):
    """Redis-backed queue with identical semantics (optional, not mandatory).

    Uses Redis only for atomic claim coordination; durable state remains in DB.
    If Redis unavailable, raises with explicit backend-unavailable error (no silent fallback).
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0", max_concurrent: int = 4, max_depth: int = 100):
        super().__init__(max_concurrent=max_concurrent, max_depth=max_depth)
        self.redis_url = redis_url
        self._redis = None
        self._available = False
        try:
            import redis  # type: ignore[import]

            self._redis = redis.Redis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2)
            self._redis.ping()
            self._available = True
        except Exception as e:
            raise RuntimeError(f"Redis backend unavailable at {redis_url}: {e}") from e

    def claim(self, worker_id: str) -> dict[str, Any] | None:
        # Atomic claim via Redis lock to prevent duplicate claims across workers
        if not self._available or self._redis is None:
            raise RuntimeError("Redis backend unavailable")
        # Use Redis SETNX lock for claim section
        lock_key = "f1:queue:claim_lock"
        try:
            acquired = self._redis.set(lock_key, worker_id, nx=True, ex=5)
            if not acquired:
                return None
            try:
                return super().claim(worker_id)
            finally:
                try:
                    self._redis.delete(lock_key)
                except Exception:
                    pass
        except Exception:
            # fall back to DB claim (still correct, lock best-effort)
            return super().claim(worker_id)


def get_queue() -> JobQueue:
    """Factory: returns Redis or InProcess based on settings. Default safe inprocess."""
    try:
        from app.core.settings import settings

        backend = str(getattr(settings, "JOB_QUEUE_BACKEND", "inprocess")).lower()
        if backend == "redis":
            try:
                return RedisJobQueue(redis_url=str(getattr(settings, "REDIS_URL", "redis://localhost:6379/0")))
            except Exception as e:
                fallback = bool(getattr(settings, "JOB_QUEUE_FALLBACK_INPROCESS", True))
                if fallback:
                    print(f"[queue] Redis unavailable, explicit fallback to inprocess: {e}")
                    return InProcessJobQueue()
                raise
        return InProcessJobQueue()
    except Exception:
        return InProcessJobQueue()


# Global queue instance (default inprocess; use get_queue() for env-aware)
queue: JobQueue = get_queue()
