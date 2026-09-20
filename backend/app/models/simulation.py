"""Phase 29 — Persistent simulation record."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Float, Index, Integer, String, Text

from app.core.database import Base


def _now() -> datetime:
    return datetime.now(UTC)


class SimulationRecord(Base):  # type: ignore[misc]
    __tablename__ = "simulations"

    simulation_id = Column(String(128), primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now, index=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)
    status = Column(String(32), nullable=False, index=True)  # QUEUED, RUNNING, COMPLETED, FAILED
    simulation_type = Column(String(32), nullable=False, index=True)  # race, monte_carlo, scenario, replay, strategy  # noqa: E501
    race_id = Column(String(128), nullable=False, index=True)
    seed = Column(Integer, nullable=True)
    sample_count = Column(Integer, nullable=True)  # N for monte carlo
    request_hash = Column(String(64), nullable=True, index=True)
    result_hash = Column(String(64), nullable=True)
    engine_version = Column(String(64), nullable=True)
    model_version = Column(String(64), nullable=True)
    dataset_version = Column(String(64), nullable=True)
    dataset_hash = Column(String(64), nullable=True)
    provenance_fingerprint = Column(String(64), nullable=True)
    execution_time = Column(Float, nullable=True)
    error = Column(Text, nullable=True)  # JSON string if failed
    result = Column(Text, nullable=True)  # JSON string (JSONB on postgres)

    __table_args__ = (
        Index("ix_simulations_race_created", "race_id", "created_at"),
        Index("ix_simulations_type_status", "simulation_type", "status"),
    )

    def to_dict(self) -> dict:
        try:
            res = json.loads(self.result) if self.result else None
        except Exception:
            res = self.result
        try:
            err = json.loads(self.error) if self.error else None
        except Exception:
            err = self.error
        return {
            "simulation_id": self.simulation_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "status": self.status,
            "simulation_type": self.simulation_type,
            "race_id": self.race_id,
            "seed": self.seed,
            "sample_count": self.sample_count,
            "request_hash": self.request_hash,
            "result_hash": self.result_hash,
            "engine_version": self.engine_version,
            "model_version": self.model_version,
            "dataset_version": self.dataset_version,
            "dataset_hash": self.dataset_hash,
            "provenance_fingerprint": self.provenance_fingerprint,
            "execution_time": self.execution_time,
            "error": err,
            "result": res,
        }
