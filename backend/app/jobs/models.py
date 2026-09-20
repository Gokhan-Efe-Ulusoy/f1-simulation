"""Phase 30 — Job model."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Index, Integer, String, Text

from app.core.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class JobRecord(Base):  # type: ignore[misc]
    __tablename__ = "jobs"

    job_id = Column(String(64), primary_key=True)
    simulation_id = Column(String(128), nullable=False, index=True)
    request_hash = Column(String(64), nullable=True, index=True)
    status = Column(String(32), nullable=False, index=True)  # QUEUED, RUNNING, COMPLETED, FAILED, CANCELLED, TIMEOUT
    simulation_type = Column(String(32), nullable=False, index=True)
    priority = Column(Integer, nullable=False, default=50)  # 0..100, LOW=10 NORMAL=50 HIGH=90; does NOT affect RNG
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    failed_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    progress = Column(Float, nullable=False, default=0.0)  # 0.0-1.0
    current_stage = Column(String(64), nullable=False, default="QUEUED")
    attempt = Column(Integer, nullable=False, default=1)
    max_attempts = Column(Integer, nullable=False, default=2)
    worker_id = Column(String(64), nullable=True)
    error = Column(Text, nullable=True)
    result_hash = Column(String(64), nullable=True)
    race_id = Column(String(128), nullable=True)
    seed = Column(Integer, nullable=True)
    sample_count = Column(Integer, nullable=True)
    result = Column(Text, nullable=True)  # JSON string
    heartbeat_at = Column(DateTime(timezone=True), nullable=True)
    timed_out_at = Column(DateTime(timezone=True), nullable=True)
    chunk_size = Column(Integer, nullable=True)
    chunk_count = Column(Integer, nullable=True)
    completed_chunks = Column(Integer, nullable=True, default=0)
    total_chunks = Column(Integer, nullable=True)

    __table_args__ = (
        Index("ix_jobs_request_hash", "request_hash"),
        Index("ix_jobs_status_created", "status", "created_at"),
    )

    def to_dict(self) -> dict:  # noqa: C901

        try:
            res = json.loads(self.result) if self.result else None
        except Exception:
            res = self.result
        try:
            err = json.loads(self.error) if self.error else None
        except Exception:
            err = self.error
        return {
            "job_id": self.job_id,
            "simulation_id": self.simulation_id,
            "request_hash": self.request_hash,
            "status": self.status,
            "simulation_type": self.simulation_type,
            "priority": self.priority,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "failed_at": self.failed_at.isoformat() if self.failed_at else None,
            "cancelled_at": self.cancelled_at.isoformat() if self.cancelled_at else None,
            "progress": self.progress,
            "current_stage": self.current_stage,
            "attempt": self.attempt,
            "max_attempts": self.max_attempts,
            "worker_id": self.worker_id,
            "error": err,
            "result_hash": self.result_hash,
            "race_id": self.race_id,
            "seed": self.seed,
            "sample_count": self.sample_count,
            "result": res,
            "heartbeat_at": self.heartbeat_at.isoformat() if self.heartbeat_at else None,
            "timed_out_at": self.timed_out_at.isoformat() if getattr(self, "timed_out_at", None) else None,
            "chunk_size": getattr(self, "chunk_size", None),
            "chunk_count": getattr(self, "chunk_count", None),
            "completed_chunks": getattr(self, "completed_chunks", 0),
            "total_chunks": getattr(self, "total_chunks", None),
        }
