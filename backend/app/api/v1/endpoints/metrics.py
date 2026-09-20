"""GET /metrics — Phase 31 observability (no RNG effect)."""
from __future__ import annotations

from typing import Any

import numpy as np
from fastapi import APIRouter
from sqlalchemy import func

from app.core.database import SessionLocal
from app.jobs.models import JobRecord

router = APIRouter()


def _percentile(data: list[float], q: float) -> float | None:
    if not data:
        return None
    arr = sorted(data)
    k = (len(arr) - 1) * q
    f = int(k)
    c = min(f + 1, len(arr) - 1)
    if f == c:
        return float(arr[int(k)])
    d0 = k - f
    return float(arr[f] * (1 - d0) + arr[c] * d0)


@router.get(
    "",
    summary="Job queue metrics",
    description="Queue depth, running/completed/failed/cancelled/timed_out, retries, runtimes, by type/priority. No simulation RNG.",
)
async def get_metrics() -> dict[str, Any]:
    session = SessionLocal()
    try:
        q_depth = session.query(JobRecord).filter(JobRecord.status == "QUEUED").count()
        running = session.query(JobRecord).filter(JobRecord.status == "RUNNING").count()
        completed = session.query(JobRecord).filter(JobRecord.status == "COMPLETED").count()
        failed = session.query(JobRecord).filter(JobRecord.status == "FAILED").count()
        cancelled = session.query(JobRecord).filter(JobRecord.status == "CANCELLED").count()
        try:
            timed_out = session.query(JobRecord).filter(JobRecord.status == "TIMEOUT").count()
        except Exception:
            timed_out = 0
        # retry count = sum(attempt-1) for attempt>1
        try:
            retry_rows = session.query(JobRecord.attempt).all()
            retry_count = sum(max(0, (r[0] or 1) - 1) for r in retry_rows)
        except Exception:
            retry_count = 0
        # runtimes from completed jobs with started/completed
        runtimes: list[float] = []
        try:
            rows = session.query(JobRecord.started_at, JobRecord.completed_at).filter(JobRecord.status == "COMPLETED").all()
            for s, c in rows:
                if s and c:
                    try:
                        runtimes.append((c - s).total_seconds())
                    except Exception:
                        pass
        except Exception:
            pass
        avg = float(np.mean(runtimes)) if runtimes else None
        # jobs by type
        by_type: dict[str, int] = {}
        try:
            for sim_type, cnt in session.query(JobRecord.simulation_type, func.count()).group_by(JobRecord.simulation_type).all():
                by_type[str(sim_type)] = int(cnt)
        except Exception:
            pass
        # jobs by priority bucket
        by_prio: dict[str, int] = {"low": 0, "normal": 0, "high": 0}
        try:
            for (prio,) in session.query(JobRecord.priority).all():
                try:
                    p = int(prio or 50)
                except Exception:
                    p = 50
                if p < 33:
                    by_prio["low"] += 1
                elif p > 66:
                    by_prio["high"] += 1
                else:
                    by_prio["normal"] += 1
        except Exception:
            pass
        return {
            "queue_depth": q_depth,
            "running_jobs": running,
            "completed_jobs": completed,
            "failed_jobs": failed,
            "cancelled_jobs": cancelled,
            "timed_out_jobs": timed_out,
            "retry_count": retry_count,
            "average_runtime": avg,
            "p50_runtime": _percentile(runtimes, 0.5),
            "p95_runtime": _percentile(runtimes, 0.95),
            "p99_runtime": _percentile(runtimes, 0.99),
            "jobs_by_type": by_type,
            "jobs_by_priority": by_prio,
        }
    finally:
        session.close()
